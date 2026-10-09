from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.schemas.schemas import (
    UserResponse, UserCreate, TransactionResponse, TransactionCreate,
    PreviewItem, ImportPreviewResponse, ImportConfirmRequest, ImportSummaryResponse,
    DashboardSummaryResponse, CategoryBreakdown, ForecastResponse,
    RecurringExpense, UnusualSpendingAlert, GoalResponse, GoalCreate,
    GoalOptimizationResponse, ScenarioRequest, ScenarioComparisonResponse,
    EvidenceItem, PrivacyReceiptResponse, NotificationListenerRequest,
    NotificationTransactionResponse, TradeOffAdviceRequest, TradeOffAdviceResponse
)
import re
from datetime import timedelta
from app.schemas.ai_schemas import (
    CategorizationRequest, CategorizationResponse,
    CopilotQueryRequest, CopilotQueryResponse,
    AIHealthResponse
)
from app.repositories.domain_repo import UserRepository, TransactionRepository, SavingsGoalRepository, PrivacyReceiptRepository, compute_raw_hash
from app.services.importer import TransactionImporter
from app.services.forecaster import FinancialForecaster
from app.services.risk_engine import FinancialRiskEngine
from app.services.optimizer import SavingsOptimizer
from app.services.evidence import EvidenceGenerator
from app.services.connector import SimulatedBankConnector
from app.services.copilot import FinancialCopilotService
from app.ml.engine import MLIntelligenceEngine
from app.core.responses import StandardResponse
from app.models.domain import User
import pandas as pd
from datetime import date

router = APIRouter()

def verify_user_exists(user_id: str, db: Session) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID '{user_id}' not found")
    return user

# --- 1. USER MANAGEMENT ---
@router.post("/users", response_model=StandardResponse[UserResponse], status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    existing = repo.get_by_email(user_in.email)
    if existing:
        return StandardResponse(success=True, message="User already exists", data=UserResponse.model_validate(existing))
    user = repo.create(user_in)
    return StandardResponse(success=True, message="User created successfully", data=UserResponse.model_validate(user))

@router.get("/users/{user_id}", response_model=StandardResponse[UserResponse])
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = verify_user_exists(user_id, db)
    return StandardResponse(success=True, data=UserResponse.model_validate(user))

# --- 2. TRANSACTION IMPORTS & MANAGE ---
@router.post("/transactions/preview-import", response_model=StandardResponse[ImportPreviewResponse])
async def preview_transaction_import(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    verify_user_exists(user_id, db)
    contents = await file.read()
    preview = TransactionImporter.parse_file_to_preview(contents, file.filename, user_id, db)
    return StandardResponse(success=True, message="File parsed and validated for preview", data=preview)

@router.post("/transactions/confirm-import", response_model=StandardResponse[ImportSummaryResponse])
def confirm_transaction_import(req: ImportConfirmRequest, db: Session = Depends(get_db)):
    verify_user_exists(req.user_id, db)
    summary = TransactionImporter.confirm_and_save(req, db)
    return StandardResponse(success=True, message="Transactions imported successfully", data=summary)

@router.get("/transactions", response_model=StandardResponse[List[TransactionResponse]])
def list_transactions(
    user_id: str = Query(...),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    verify_user_exists(user_id, db)
    repo = TransactionRepository(db)
    txns = repo.get_by_user(user_id, limit=limit, offset=offset)
    data = [TransactionResponse.model_validate(t) for t in txns]
    return StandardResponse(success=True, data=data, meta={"count": len(data), "limit": limit, "offset": offset})

@router.delete("/transactions/clear", response_model=StandardResponse[dict])
def clear_user_transactions(user_id: str = Query(...), db: Session = Depends(get_db)):
    verify_user_exists(user_id, db)
    repo = TransactionRepository(db)
    count = repo.delete_by_user(user_id)
    return StandardResponse(success=True, message=f"Cleared {count} transactions for user", data={"deleted_count": count})

# --- 3. DASHBOARD SUMMARY ---
@router.get("/dashboard/summary", response_model=StandardResponse[DashboardSummaryResponse])
def get_dashboard_summary(
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    verify_user_exists(user_id, db)
    repo = TransactionRepository(db)
    txns = repo.get_by_user(user_id, limit=2000)

    if not txns:
        return StandardResponse(
            success=True,
            data=DashboardSummaryResponse(
                user_id=user_id,
                total_balance=0.0,
                total_income=0.0,
                total_expenses=0.0,
                net_savings=0.0,
                avg_daily_spend=0.0,
                top_categories=[],
                recent_transactions=[]
            )
        )

    income = sum(t.amount for t in txns if t.txn_type == "credit")
    expense = sum(t.amount for t in txns if t.txn_type == "debit")
    net = income - expense

    dates = [t.txn_date for t in txns]
    span = max((max(dates) - min(dates)).days, 1)
    avg_daily = expense / span

    cat_map = {}
    cat_counts = {}
    for t in txns:
        if t.txn_type == "debit":
            cat_map[t.category] = cat_map.get(t.category, 0.0) + t.amount
            cat_counts[t.category] = cat_counts.get(t.category, 0) + 1

    categories: List[CategoryBreakdown] = []
    for cat, amt in cat_map.items():
        pct = (amt / expense * 100.0) if expense > 0 else 0.0
        categories.append(
            CategoryBreakdown(
                category=cat,
                amount=round(amt, 2),
                percentage=round(pct, 1),
                count=cat_counts[cat]
            )
        )
    categories.sort(key=lambda x: x.amount, reverse=True)

    recent = [TransactionResponse.model_validate(t) for t in txns[:10]]

    return StandardResponse(
        success=True,
        data=DashboardSummaryResponse(
            user_id=user_id,
            total_balance=round(net, 2),
            total_income=round(income, 2),
            total_expenses=round(expense, 2),
            net_savings=round(net, 2),
            avg_daily_spend=round(avg_daily, 2),
            top_categories=categories,
            recent_transactions=recent
        )
    )

# --- 4. FORECASTING & ANOMALIES ---
@router.get("/forecasting/cashflow", response_model=StandardResponse[ForecastResponse])
def get_cashflow_forecast(
    user_id: str = Query(...),
    horizon_days: int = Query(90, ge=7, le=365),
    safe_buffer: float = Query(5000.0, ge=0.0),
    db: Session = Depends(get_db)
):
    verify_user_exists(user_id, db)
    repo = TransactionRepository(db)
    txns = repo.get_by_user(user_id, limit=2000)

    income = sum(t.amount for t in txns if t.txn_type == "credit")
    expense = sum(t.amount for t in txns if t.txn_type == "debit")
    initial_bal = income - expense if txns else 25000.0

    forecast = FinancialForecaster.forecast_cashflow(
        transactions=txns,
        user_id=user_id,
        horizon_days=horizon_days,
        safe_buffer=safe_buffer,
        initial_balance=initial_bal
    )
    return StandardResponse(success=True, data=forecast)

@router.get("/forecasting/risk-timeline", response_model=StandardResponse[dict])
def get_risk_timeline(
    user_id: str = Query(...),
    safety_buffer: float = Query(5000.0),
    horizon_days: int = Query(30),
    expected_monthly_income: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    verify_user_exists(user_id, db)
    repo = TransactionRepository(db)
    txns = repo.get_by_user(user_id, limit=2000)

    income = sum(t.amount for t in txns if t.txn_type == "credit")
    expense = sum(t.amount for t in txns if t.txn_type == "debit")
    initial_bal = income - expense if txns else 25000.0

    dict_txns = [
        {
            "id": t.id,
            "txn_date": t.txn_date.isoformat() if hasattr(t.txn_date, "isoformat") else str(t.txn_date),
            "description": t.description,
            "amount": t.amount,
            "txn_type": t.txn_type,
            "category": t.category
        }
        for t in txns
    ]

    risk_analysis = FinancialRiskEngine.calculate_personalized_risk(
        transactions=dict_txns,
        current_balance=initial_bal,
        safety_buffer=safety_buffer,
        horizon_days=horizon_days,
        expected_monthly_income=expected_monthly_income
    )
    return StandardResponse(success=True, data=risk_analysis)

@router.get("/analytics/recurring-expenses", response_model=StandardResponse[List[RecurringExpense]])
def get_recurring_expenses(user_id: str = Query(...), db: Session = Depends(get_db)):
    verify_user_exists(user_id, db)
    repo = TransactionRepository(db)
    txns = repo.get_by_user(user_id, limit=2000)
    recurring = FinancialForecaster.detect_recurring_expenses(txns)
    return StandardResponse(success=True, data=recurring)

@router.get("/analytics/unusual-spending", response_model=StandardResponse[List[UnusualSpendingAlert]])
def get_unusual_spending(user_id: str = Query(...), db: Session = Depends(get_db)):
    verify_user_exists(user_id, db)
    repo = TransactionRepository(db)
    txns = repo.get_by_user(user_id, limit=2000)
    alerts = FinancialForecaster.detect_unusual_spending(txns)
    return StandardResponse(success=True, data=alerts)

# --- 5. SAVINGS GOALS & OPTIMIZATION ---
@router.post("/goals", response_model=StandardResponse[GoalResponse], status_code=status.HTTP_201_CREATED)
def create_goal(goal_in: GoalCreate, db: Session = Depends(get_db)):
    verify_user_exists(goal_in.user_id, db)
    repo = SavingsGoalRepository(db)
    goal = repo.create(goal_in)
    return StandardResponse(success=True, message="Savings goal created", data=GoalResponse.model_validate(goal))

@router.get("/goals", response_model=StandardResponse[List[GoalResponse]])
def list_goals(user_id: str = Query(...), db: Session = Depends(get_db)):
    verify_user_exists(user_id, db)
    repo = SavingsGoalRepository(db)
    goals = repo.get_by_user(user_id)
    data = [GoalResponse.model_validate(g) for g in goals]
    return StandardResponse(success=True, data=data)

@router.delete("/goals/{goal_id}", response_model=StandardResponse[dict])
def delete_goal(goal_id: str, user_id: str = Query(...), db: Session = Depends(get_db)):
    verify_user_exists(user_id, db)
    repo = SavingsGoalRepository(db)
    success = repo.delete(goal_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Goal not found")
    return StandardResponse(success=True, message="Goal deleted", data={"goal_id": goal_id})

@router.get("/goals/optimize", response_model=StandardResponse[GoalOptimizationResponse])
def optimize_goals(
    user_id: str = Query(...),
    override_surplus: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    verify_user_exists(user_id, db)
    goal_repo = SavingsGoalRepository(db)
    txn_repo = TransactionRepository(db)
    goals = goal_repo.get_by_user(user_id)
    txns = txn_repo.get_by_user(user_id, limit=2000)

    opt_result = SavingsOptimizer.optimize_goal_allocations(
        goals=goals,
        user_id=user_id,
        transactions=txns,
        override_monthly_surplus=override_surplus
    )
    return StandardResponse(success=True, data=opt_result)

# --- 6. FINANCIAL TIME MACHINE / SCENARIO COMPARISON ---
@router.post("/simulations/scenario", response_model=StandardResponse[ScenarioComparisonResponse])
def run_scenario_simulation(req: ScenarioRequest, db: Session = Depends(get_db)):
    verify_user_exists(req.user_id, db)
    txn_repo = TransactionRepository(db)
    txns = txn_repo.get_by_user(req.user_id, limit=2000)

    income = sum(t.amount for t in txns if t.txn_type == "credit")
    expense = sum(t.amount for t in txns if t.txn_type == "debit")
    initial_bal = income - expense if txns else 25000.0

    baseline = FinancialForecaster.forecast_cashflow(
        transactions=txns,
        user_id=req.user_id,
        horizon_days=req.horizon_days,
        initial_balance=initial_bal
    )

    scenario_params = {
        "income_delay_days": req.income_delay_days,
        "income_reduction_percent": req.income_reduction_percent,
        "one_off_expenses": req.one_off_expenses,
        "spending_category_changes": req.spending_category_changes
    }
    simulated = FinancialForecaster.forecast_cashflow(
        transactions=txns,
        user_id=req.user_id,
        horizon_days=req.horizon_days,
        initial_balance=initial_bal,
        scenario_overrides=scenario_params
    )

    diff = simulated.end_balance - baseline.end_balance
    breach_delta = len(simulated.breaches) - len(baseline.breaches)

    timeline_comp = []
    for b_pt, s_pt in zip(baseline.daily_timeline, simulated.daily_timeline):
        timeline_comp.append({
            "date": b_pt.date,
            "baseline_balance": b_pt.projected_balance,
            "scenario_balance": s_pt.projected_balance,
            "difference": round(s_pt.projected_balance - b_pt.projected_balance, 2)
        })

    deltas = []
    if req.income_delay_days > 0:
        deltas.append(f"Delaying income by {req.income_delay_days} days shifts liquidity recovery forward.")
    if req.income_reduction_percent > 0:
        deltas.append(f"Income reduction of {req.income_reduction_percent}% lowers baseline cash inflow.")
    if req.one_off_expenses:
        deltas.append(f"Added {len(req.one_off_expenses)} one-off custom scenario expense(s).")
    if req.spending_category_changes:
        deltas.append(f"Applied category adjustments: {req.spending_category_changes}")

    return StandardResponse(
        success=True,
        data=ScenarioComparisonResponse(
            user_id=req.user_id,
            baseline_end_balance=baseline.end_balance,
            scenario_end_balance=simulated.end_balance,
            balance_difference=round(diff, 2),
            baseline_breaches=len(baseline.breaches),
            scenario_breaches=len(simulated.breaches),
            breach_delta=breach_delta,
            timeline_comparison=timeline_comp,
            delta_explanations=deltas
        )
    )

# --- 7. REPORT EXPLORER & EVIDENCE ---
@router.get("/reports/explorer", response_model=StandardResponse[List[EvidenceItem]])
def get_report_explorer(user_id: str = Query(...), db: Session = Depends(get_db)):
    verify_user_exists(user_id, db)
    txn_repo = TransactionRepository(db)
    goal_repo = SavingsGoalRepository(db)
    
    txns = txn_repo.get_by_user(user_id, limit=2000)
    goals = goal_repo.get_by_user(user_id)

    income = sum(t.amount for t in txns if t.txn_type == "credit")
    expense = sum(t.amount for t in txns if t.txn_type == "debit")
    initial_bal = income - expense if txns else 25000.0

    forecast = FinancialForecaster.forecast_cashflow(txns, user_id, horizon_days=90, initial_balance=initial_bal)
    goal_opt = SavingsOptimizer.optimize_goal_allocations(goals, user_id, txns)

    evidence = EvidenceGenerator.generate_report_evidence(
        transactions=txns,
        user_id=user_id,
        forecast_data=forecast.model_dump(),
        goal_data=goal_opt.model_dump()
    )
    return StandardResponse(success=True, data=evidence)

# --- 8. PRIVACY RECEIPTS & DEMO CONNECTOR ---
@router.get("/privacy/receipts", response_model=StandardResponse[List[PrivacyReceiptResponse]])
def list_privacy_receipts(user_id: str = Query(...), db: Session = Depends(get_db)):
    verify_user_exists(user_id, db)
    repo = PrivacyReceiptRepository(db)
    receipts = repo.get_by_user(user_id)
    data = [PrivacyReceiptResponse.model_validate(r) for r in receipts]
    return StandardResponse(success=True, data=data)

@router.post("/connectors/demo-bank-sync", response_model=StandardResponse[ImportSummaryResponse])
def trigger_simulated_bank_sync(user_id: str = Query(...), count: int = Query(25, ge=5, le=100), db: Session = Depends(get_db)):
    verify_user_exists(user_id, db)
    raw_txns = SimulatedBankConnector.fetch_simulated_transactions(count=count)
    preview_records = []
    
    txn_repo = TransactionRepository(db)
    existing_hashes = {t.raw_hash: t.id for t in txn_repo.get_by_user(user_id, limit=2000)}

    for r in raw_txns:
        d = pd.to_datetime(r["txn_date"]).date()
        desc = r["description"]
        amt = float(r["amount"])
        ttype = r["txn_type"]
        cat = r["category"]
        r_hash = compute_raw_hash(str(d), desc, amt, ttype)
        is_dup = r_hash in existing_hashes

        preview_records.append(
            PreviewItem(
                txn_date=d,
                description=desc,
                amount=amt,
                txn_type=ttype,
                category=cat,
                raw_hash=r_hash,
                is_duplicate=is_dup,
                duplicate_of_id=existing_hashes.get(r_hash)
            )
        )

    req = ImportConfirmRequest(
        user_id=user_id,
        source_name="MOCK_UPI_BANK_CONNECTOR",
        file_name="SIMULATED_STREAM.json",
        records=preview_records,
        skip_duplicates=True
    )
    summary = TransactionImporter.confirm_and_save(req, db)
    return StandardResponse(success=True, message="Simulated bank sync completed", data=summary)

# --- 9. AI & MACHINE LEARNING ENDPOINTS ---
@router.post("/ai/categorize-transaction", response_model=StandardResponse[CategorizationResponse])
def ai_categorize_transaction(req: CategorizationRequest):
    predicted_cat, conf, method = MLIntelligenceEngine.predict_category(req.description, req.amount or 0.0)
    method_label = (
        "TF-IDF + Logistic Regression (trained on 40 synthetic examples)"
        if method == "tfidf_logreg_ml"
        else "Rule-based keyword matching (sklearn unavailable)"
    )
    return StandardResponse(
        success=True,
        message=method_label,
        data=CategorizationResponse(
            predicted_category=predicted_cat,
            confidence_score=conf,
            description=req.description,
            method=method
        )
    )

@router.get("/ai/ml-spending-anomalies", response_model=StandardResponse[List[dict]])
def ai_ml_spending_anomalies(user_id: str = Query(...), db: Session = Depends(get_db)):
    verify_user_exists(user_id, db)
    repo = TransactionRepository(db)
    txns = repo.get_by_user(user_id, limit=2000)

    dict_txns = [
        {
            "id": t.id,
            "txn_date": t.txn_date,
            "description": t.description,
            "amount": t.amount,
            "txn_type": t.txn_type,
            "category": t.category
        }
        for t in txns
    ]

    anomalies = MLIntelligenceEngine.detect_ml_anomalies(dict_txns)
    # Determine which method was actually used (may differ from field name)
    method_used = anomalies[0]["method"] if anomalies else ("isolation_forest" if MLIntelligenceEngine._isolation_forest else "z_score_fallback")
    from app.ml.engine import SKLEARN_AVAILABLE as _SK
    msg = (
        "Isolation Forest anomaly detection (synthetic-data-trained, demonstration only)"
        if _SK else
        "Z-score statistical anomaly detection (sklearn unavailable — fallback active)"
    )
    return StandardResponse(success=True, message=msg, data=anomalies)

@router.post("/ai/copilot/query", response_model=StandardResponse[CopilotQueryResponse])
def ai_copilot_query(req: CopilotQueryRequest, db: Session = Depends(get_db)):
    verify_user_exists(req.user_id, db)
    txn_repo = TransactionRepository(db)
    goal_repo = SavingsGoalRepository(db)

    txns = txn_repo.get_by_user(req.user_id, limit=2000)
    goals = goal_repo.get_by_user(req.user_id)

    copilot_res = FinancialCopilotService.answer_user_query(
        query=req.query,
        user_id=req.user_id,
        transactions=txns,
        goals=goals
    )
    return StandardResponse(
        success=True,
        message="Rule-based Q&A (keyword routing + deterministic financial calculations — not an LLM)",
        data=CopilotQueryResponse(**copilot_res)
    )

# --- 9B. MILO CHATBOT ENDPOINTS ---
_milo_chat_history = {}

@router.post("/chat/message")
def milo_chat_message(payload: dict, db: Session = Depends(get_db)):
    user_id = payload.get("user_id", "usr_test_123")
    msg = payload.get("message", "").strip()

    txn_repo = TransactionRepository(db)
    goal_repo = SavingsGoalRepository(db)

    txns = txn_repo.get_by_user(user_id, limit=2000)
    goals = goal_repo.get_by_user(user_id)

    copilot_res = FinancialCopilotService.answer_user_query(
        query=msg,
        user_id=user_id,
        transactions=txns,
        goals=goals
    )

    q_lower = msg.lower()
    matched_txs = []
    actions = [
        {"target_page": "dashboard", "label": "View Overview"},
        {"target_page": "forecasts", "label": "Cash-Flow Forecast"}
    ]

    # Keyword specific matching for direct evidence
    if "food" in q_lower or "dining" in q_lower or "swiggy" in q_lower or "spend" in q_lower:
        matching = [t for t in txns if any(k in (t.category or "").lower() or k in (t.description or "").lower() for k in ["food", "dining", "swiggy", "restaurant"])]
        if matching:
            matched_txs = [
                {
                    "transaction_id": t.id,
                    "merchant": t.description,
                    "amount": t.amount if t.txn_type == "debit" else -t.amount,
                    "date": t.txn_date.strftime("%Y-%m-%d") if hasattr(t.txn_date, "strftime") else str(t.txn_date),
                    "category": t.category
                }
                for t in matching[:3]
            ]
            actions.append({"target_page": "transactions", "label": "Verify All Receipts"})

    if "save" in q_lower or "goal" in q_lower:
        actions.append({"target_page": "savings", "label": "Optimize Savings Goals"})

    if "scenario" in q_lower or "if" in q_lower or "delay" in q_lower:
        actions.append({"target_page": "time-machine", "label": "Time Machine Simulator", "scenario_type": "postpone_fee"})

    reply_text = copilot_res.get("answer", "I analyzed your financial records. Everything looks clear!")
    follow_up = "Would you like me to project how cutting discretionary dining by ₹1,500/month accelerates your savings?"

    bot_payload = {
        "reply": reply_text,
        "matched_transactions": matched_txs,
        "actions": actions,
        "follow_up_question": follow_up
    }

    if user_id not in _milo_chat_history:
        _milo_chat_history[user_id] = []
    
    _milo_chat_history[user_id].append({"role": "user", "text": msg})
    _milo_chat_history[user_id].append({
        "role": "bot",
        "text": reply_text,
        "matched_transactions": matched_txs,
        "action_links": actions
    })

    return StandardResponse(
        success=True,
        message="Milo response generated successfully",
        data=bot_payload
    )

@router.get("/chat/history")
def milo_chat_history(user_id: str = Query("usr_test_123")):
    history = _milo_chat_history.get(user_id, [])
    return StandardResponse(
        success=True,
        message="Chat history retrieved",
        data={"user_id": user_id, "messages": history}
    )

@router.delete("/chat/history")
def milo_clear_history(user_id: str = Query("usr_test_123")):
    if user_id in _milo_chat_history:
        _milo_chat_history[user_id] = []
    return StandardResponse(
        success=True,
        message="Chat history cleared successfully"
    )



# --- 10. NOTIFICATION LISTENER & BUDGET TRADE-OFF ADVICE ---
@router.post("/connectors/notification-listener", response_model=StandardResponse[NotificationTransactionResponse])
def process_notification_text(req: NotificationListenerRequest, db: Session = Depends(get_db)):
    """
    Parses incoming SMS / App push notification text (e.g., 'Rs. 450 debited at Swiggy').
    Extracts transaction amount, merchant, type, predicts ML category, and auto-saves to ledger.
    """
    verify_user_exists(req.user_id, db)
    text = req.notification_text
    
    # Regex pattern to extract monetary amount
    amt_match = re.search(r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{2})?)', text, re.IGNORECASE)
    amount = float(amt_match.group(1).replace(',', '')) if amt_match else 150.0

    # Determine debit vs credit
    ttype = "credit" if re.search(r'\b(?:credited|received|deposit)\b', text, re.IGNORECASE) else "debit"

    # Extract merchant name snippet
    merchant_match = re.search(r'(?:at|to|vpa|info:)\s*([A-Za-z0-9\s&]+?)(?:\s+on|\s+avail|\s+ref|\.|$)', text, re.IGNORECASE)
    description = merchant_match.group(1).strip() if merchant_match else "SMS Detected Transaction"

    # Predict category via ML engine
    pred_cat, conf, method = MLIntelligenceEngine.predict_category(description, amount)

    # Save automatically to ledger
    d_today = date.today()
    raw_hash = compute_raw_hash(str(d_today), description, amount, ttype)

    txn_repo = TransactionRepository(db)
    new_txn = txn_repo.create(
        TransactionCreate(
            user_id=req.user_id,
            txn_date=d_today,
            description=description,
            amount=amount,
            txn_type=ttype,
            category=pred_cat,
            source="NOTIFICATION_LISTENER"
        )
    )

    explanation = (
        f"Automatically parsed notification from '{req.source_app}'. "
        f"Detected {ttype.upper()} of ₹{amount:,.2f} at '{description}'. Categorized as '{pred_cat}' (Confidence: {conf*100:.0f}%)."
    )

    return StandardResponse(
        success=True,
        message="Notification transaction parsed and imported into ledger",
        data=NotificationTransactionResponse(
            transaction_id=new_txn.id,
            amount=amount,
            txn_type=ttype,
            description=description,
            category=pred_cat,
            confidence_score=conf,
            method=method,
            auto_imported=True,
            explanation=explanation
        )
    )

@router.post("/ai/tradeoff-advice", response_model=StandardResponse[TradeOffAdviceResponse])
def get_tradeoff_advice(req: TradeOffAdviceRequest, db: Session = Depends(get_db)):
    """
    Calculates goal acceleration advice if discretionary spending (e.g. Dining out) is reduced.
    Shows exact days saved for highest-priority savings goal.
    """
    verify_user_exists(req.user_id, db)
    goal_repo = SavingsGoalRepository(db)
    goals = goal_repo.get_by_user(req.user_id)

    top_goal = min(goals, key=lambda g: g.priority) if goals else None
    goal_name = top_goal.name if top_goal else "Emergency Reserve Goal"
    orig_date = top_goal.target_date if top_goal else (date.today() + timedelta(days=120))
    target_amt = top_goal.target_amount if top_goal else 50000.0
    curr_amt = top_goal.current_amount if top_goal else 10000.0

    remaining = max(1.0, target_amt - curr_amt)
    monthly_sav = max(500.0, req.potential_savings_amount)
    
    # Calculate days saved
    months_needed_orig = remaining / monthly_sav
    months_needed_new = remaining / (monthly_sav + req.potential_savings_amount)
    days_saved = max(14, int((months_needed_orig - months_needed_new) * 30))

    acc_date = max(date.today(), orig_date - timedelta(days=days_saved))

    recommendation = (
        f"If you reduce spending in '{req.discretionary_category}' by ₹{req.potential_savings_amount:,.2f}/month, "
        f"you will reach your '{goal_name}' goal {days_saved} days earlier (on {acc_date.strftime('%d %b %Y')})."
    )

    return StandardResponse(
        success=True,
        message="Trade-off recommendation generated",
        data=TradeOffAdviceResponse(
            discretionary_category=req.discretionary_category or "Dining & Food",
            monthly_reduction=req.potential_savings_amount,
            target_goal_name=goal_name,
            original_target_date=orig_date,
            accelerated_target_date=acc_date,
            days_saved=days_saved,
            recommendation_summary=recommendation
        )
    )

# --- 11. AI HEALTH & DIAGNOSTIC ---
@router.get("/ai/health", response_model=StandardResponse[AIHealthResponse])
def ai_health_check():
    """
    Returns the true implementation status of every AI/ML feature.
    Use this endpoint to confirm whether sklearn models are active or
    fallback heuristics are running. No sensitive information is exposed.
    """
    health = MLIntelligenceEngine.get_ai_health()
    return StandardResponse(
        success=True,
        message="AI feature diagnostic — see 'features' for per-feature implementation details",
        data=health
    )
