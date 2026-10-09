from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
import re

from app.schemas.milo_schemas import (
    MiloChatMessageRequest, MiloChatMessageResponse, MiloMatchedTransaction,
    MiloActionLink, MiloHistoryItem, MiloHistoryResponse
)
from app.repositories.domain_repo import UserRepository, TransactionRepository, SavingsGoalRepository
from app.services.forecaster import FinancialForecaster
from app.services.risk_engine import FinancialRiskEngine
from app.services.optimizer import SavingsOptimizer
from app.services.evidence import EvidenceGenerator
from app.models.domain import User, Transaction, SavingsGoal

# In-memory session store for conversational turn history: { (user_id, session_id): [MiloHistoryItem, ...] }
_SESSION_STORE: Dict[str, List[Dict[str, Any]]] = {}

class MiloEngineService:
    @staticmethod
    def _get_session_key(user_id: str, session_id: str) -> str:
        return f"{user_id}:{session_id or 'default'}"

    @classmethod
    def get_history(cls, user_id: str, session_id: str = "default_session") -> List[Dict[str, Any]]:
        key = cls._get_session_key(user_id, session_id)
        return _SESSION_STORE.get(key, [])

    @classmethod
    def clear_history(cls, user_id: str, session_id: str = "default_session") -> bool:
        key = cls._get_session_key(user_id, session_id)
        if key in _SESSION_STORE:
            del _SESSION_STORE[key]
            return True
        return False

    @classmethod
    def _add_to_history(cls, user_id: str, session_id: str, role: str, text: str, intent: Optional[str] = None, matched_txns: List[MiloMatchedTransaction] = [], action_links: List[MiloActionLink] = []):
        key = cls._get_session_key(user_id, session_id)
        if key not in _SESSION_STORE:
            _SESSION_STORE[key] = []
        item = {
            "role": role,
            "text": text,
            "timestamp": datetime.now().isoformat(),
            "intent": intent,
            "matched_transactions": [t.model_dump() for t in matched_txns],
            "action_links": [a.model_dump() for a in action_links]
        }
        _SESSION_STORE[key].append(item)
        # Cap session history at 30 messages
        if len(_SESSION_STORE[key]) > 30:
            _SESSION_STORE[key] = _SESSION_STORE[key][-30:]

    @classmethod
    def process_message(cls, db: Session, req: MiloChatMessageRequest) -> MiloChatMessageResponse:
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(req.user_id)
        if not user:
            raise ValueError(f"User with ID '{req.user_id}' not found")

        tx_repo = TransactionRepository(db)
        all_txns = tx_repo.get_by_user(req.user_id, limit=500)
        history = cls.get_history(req.user_id, req.session_id)

        msg_text = req.message.strip()
        msg_lower = msg_text.lower()

        # Save user message to turn history
        cls._add_to_history(req.user_id, req.session_id, "user", msg_text)

        # Context Resolution: check previous turn context if query contains contextual pronouns ("that payment", "why?", "what if I delay it?")
        prev_context = cls._resolve_context(history, msg_lower)

        # Detect Security / Out-of-Scope Requests
        if any(term in msg_lower for term in ["pin", "password", "otp", "upi pin", "cvv", "card number", "tax return", "file tax", "lawyer"]):
            return cls._handle_out_of_scope(req.user_id, req.session_id, msg_text)

        # Route Intent
        intent = cls._classify_intent(msg_lower, prev_context)

        response: MiloChatMessageResponse = None

        if intent == "TRANSACTION_LOOKUP":
            response = cls._handle_transaction_lookup(db, req, all_txns, msg_lower, prev_context)
        elif intent == "SPENDING_ANALYSIS":
            response = cls._handle_spending_analysis(db, req, all_txns, msg_lower)
        elif intent == "RECURRING_EXPENSES":
            response = cls._handle_recurring_expenses(db, req, all_txns)
        elif intent == "CASHFLOW_FORECAST" or intent == "RISK_WARNING":
            response = cls._handle_cashflow_forecast(db, req, all_txns)
        elif intent == "SAVINGS_GOALS":
            response = cls._handle_savings_goals(db, req)
        elif intent == "SCENARIO_SIMULATION":
            response = cls._handle_scenario_simulation(db, req, all_txns, msg_lower, prev_context)
        elif intent == "GENERAL_EDUCATION":
            response = cls._handle_general_education(req, msg_lower)
        else:
            response = cls._handle_fallback(db, req, all_txns, msg_lower)

        # Set compatibility fields for frontend UI and test assertions
        response.reply = response.answer
        response.actions = [
            {
                "label": a.label,
                "target_tab": a.target_page,
                "action_type": a.action_type,
                "scenario_type": a.payload.get("scenario_type") if a.payload else None
            }
            for a in response.action_links
        ]

        # Record Milo turn in history
        cls._add_to_history(
            req.user_id, req.session_id, "milo", response.answer,
            intent=response.intent,
            matched_txns=response.matched_transactions,
            action_links=response.action_links
        )

        return response

    @classmethod
    def _resolve_context(cls, history: List[Dict[str, Any]], msg_lower: str) -> Dict[str, Any]:
        context = {"category": None, "transaction_id": None, "merchant": None, "amount": None}
        if not history:
            return context

        # Look backwards through history for previous turn context
        for item in reversed(history):
            if item.get("matched_transactions"):
                tx = item["matched_transactions"][0]
                context["transaction_id"] = tx.get("id")
                context["merchant"] = tx.get("description")
                context["category"] = tx.get("category")
                context["amount"] = tx.get("amount")
                break
            if item.get("intent") in ["SPENDING_ANALYSIS", "TRANSACTION_LOOKUP"]:
                text = item.get("text", "").lower()
                for cat in ["food", "dining", "shopping", "transport", "utilities", "entertainment"]:
                    if cat in text:
                        context["category"] = cat.capitalize()
                        break

        return context

    @classmethod
    def _classify_intent(cls, msg_lower: str, prev_context: Dict[str, Any]) -> str:
        # 1. Scenario Simulation / Time Machine keywords (Check first to avoid collision with general words like 'expense' or 'payment')
        if any(phrase in msg_lower for phrase in ["what happens if", "unexpected expense", "what if i delay", "delay salary", "delay payment", "buy a new", "extra expense", "what if"]):
            return "SCENARIO_SIMULATION"

        # 2. Transaction Lookup keywords / patterns
        txn_keywords = ["swiggy", "zomato", "uber", "ola", "amazon", "flipkart", "netflix", "rent", "salary", "payment", "merchant", "receipt", "txn", "transaction", "bought", "paid"]
        amount_match = re.search(r'(?:rs|inr|₹)?\s*(\d+[\d,.]*)', msg_lower)
        if any(kw in msg_lower for kw in txn_keywords) or ("that payment" in msg_lower and prev_context["merchant"]) or (amount_match and "what" in msg_lower and "what if" not in msg_lower):
            return "TRANSACTION_LOOKUP"

        # 3. Spending Analysis keywords
        if any(phrase in msg_lower for phrase in ["where did my money go", "spending breakdown", "expenses this month", "how much did i spend", "highest expense", "category breakdown", "spending summary"]):
            return "SPENDING_ANALYSIS"

        # 4. Recurring Expenses
        if any(phrase in msg_lower for phrase in ["recurring", "subscriptions", "review expenses", "which expenses can i review", "monthly bills", "fixed bills"]):
            return "RECURRING_EXPENSES"

        # 5. Cashflow Forecast & Risk Warnings
        if any(phrase in msg_lower for phrase in ["expected to fall", "why is my balance", "balance fall", "cashflow forecast", "risk warning", "buffer breach", "minimum balance", "out of cash"]):
            return "CASHFLOW_FORECAST"

        # 6. Savings Goals
        if any(phrase in msg_lower for phrase in ["savings goal", "on track", "emergency fund", "laptop fund", "vacation fund", "goal progress", "reach my goal"]):
            return "SAVINGS_GOALS"

        # 7. General Financial Education
        if any(phrase in msg_lower for phrase in ["50/30/20", "emergency buffer", "savings rate", "how to budget", "what is interest", "credit vs debit", "financial tips", "what is buffer"]):
            return "GENERAL_EDUCATION"

        return "GENERAL_HEURISTIC"

    @classmethod
    def _handle_transaction_lookup(cls, db: Session, req: MiloChatMessageRequest, all_txns: List[Transaction], msg_lower: str, prev_context: Dict[str, Any]) -> MiloChatMessageResponse:
        matched: List[Transaction] = []
        search_term = ""

        # Extract amount if present
        amount_match = re.search(r'(\d+[\d,.]*)', msg_lower)
        target_amount = float(amount_match.group(1).replace(',', '')) if amount_match else None

        # Check explicit merchant/keyword matches
        merchant_keywords = ["swiggy", "zomato", "uber", "ola", "amazon", "flipkart", "netflix", "rent", "salary", "electricity", "water", "myntra", "starbucks", "apple", "google"]
        found_kw = next((kw for kw in merchant_keywords if kw in msg_lower), None)

        if found_kw:
            search_term = found_kw
            matched = [t for t in all_txns if found_kw in t.description.lower() or found_kw in t.category.lower()]
        elif target_amount:
            search_term = f"₹{target_amount:,.2f}"
            matched = [t for t in all_txns if abs(t.amount - target_amount) < 1.0]
        elif "that payment" in msg_lower and prev_context.get("merchant"):
            search_term = prev_context["merchant"]
            matched = [t for t in all_txns if prev_context["merchant"].lower() in t.description.lower()]
        else:
            # Fallback search matching any word > 2 chars
            words = [w for w in msg_lower.split() if len(w) > 2 and w not in ["what", "show", "find", "my", "this", "that", "the", "for"]]
            for w in words:
                hits = [t for t in all_txns if w in t.description.lower() or w in t.category.lower()]
                if hits:
                    search_term = w
                    matched = hits
                    break

        if not all_txns:
            return MiloChatMessageResponse(
                session_id=req.session_id,
                intent="TRANSACTION_LOOKUP",
                answer="I checked your transaction ledger, but your account currently has no recorded transactions yet. Once you import a CSV statement or connect a bank account, I can search and highlight exact line items for you!",
                follow_up_question="Would you like me to guide you to the Data Import page to upload your first bank statement?",
                match_status="NO_MATCH",
                matched_transactions=[],
                action_links=[MiloActionLink(label="Import Transactions", target_page="import", action_type="NAVIGATE")],
                evidence={"recorded_transactions_count": 0}
            )

        if len(matched) == 1:
            tx = matched[0]
            matched_dto = MiloMatchedTransaction(
                id=tx.id,
                txn_date=tx.txn_date,
                description=tx.description,
                amount=tx.amount,
                category=tx.category,
                txn_type=tx.txn_type,
                source=tx.source
            )
            answer = (
                f"I found the exact recorded transaction you're looking for, my friend! 🔍\n\n"
                f"• **Merchant/Description**: {tx.description}\n"
                f"• **Amount**: ₹{tx.amount:,.2f} ({tx.txn_type.upper()})\n"
                f"• **Date**: {tx.txn_date.strftime('%d %b %Y')}\n"
                f"• **Category**: {tx.category}\n"
                f"• **Import Source**: {tx.source}\n\n"
                f"You can click **'View Transaction'** below to highlight this exact record in your ledger and verify it yourself!"
            )
            return MiloChatMessageResponse(
                session_id=req.session_id,
                intent="TRANSACTION_LOOKUP",
                answer=answer,
                follow_up_question=f"Would you like me to analyze if your spending in '{tx.category}' is higher than last month?",
                match_status="EXACT_MATCH",
                matched_transactions=[matched_dto],
                action_links=[
                    MiloActionLink(
                        label="View Transaction",
                        target_page="transactions",
                        action_type="SHOW_TRANSACTION",
                        payload={"txn_id": tx.id, "highlight_id": tx.id, "category": tx.category}
                    )
                ],
                evidence={"matched_id": tx.id, "raw_hash": tx.raw_hash, "amount": tx.amount, "txn_date": str(tx.txn_date)}
            )
        elif len(matched) > 1:
            matched_dtos = [
                MiloMatchedTransaction(
                    id=t.id, txn_date=t.txn_date, description=t.description,
                    amount=t.amount, category=t.category, txn_type=t.txn_type, source=t.source
                ) for t in matched[:4]
            ]
            candidates_text = "\n".join([f"  {idx+1}. **{t.description}** — ₹{t.amount:,.2f} on {t.txn_date.strftime('%d %b %Y')} ({t.category})" for idx, t in enumerate(matched[:4])])
            answer = (
                f"I found **{len(matched)} transactions** matching '{search_term}' in your database records:\n\n"
                f"{candidates_text}\n\n"
                f"Which specific record would you like to review or view in detail?"
            )
            return MiloChatMessageResponse(
                session_id=req.session_id,
                intent="TRANSACTION_LOOKUP",
                answer=answer,
                follow_up_question="Please specify the date or amount of the transaction you'd like to inspect.",
                match_status="MULTIPLE_MATCHES",
                matched_transactions=matched_dtos,
                action_links=[
                    MiloActionLink(
                        label="Open Transactions Ledger",
                        target_page="transactions",
                        action_type="NAVIGATE",
                        payload={"search": search_term}
                    )
                ],
                evidence={"candidates_count": len(matched), "query_term": search_term}
            )
        else:
            answer = (
                f"I searched your actual database records for **'{search_term or msg_lower}'**, but no matching transaction was found in your ledger.\n\n"
                f"This could mean the transaction is listed under a slightly different merchant name or hasn't been imported yet."
            )
            return MiloChatMessageResponse(
                session_id=req.session_id,
                intent="TRANSACTION_LOOKUP",
                answer=answer,
                follow_up_question="Would you like to search by category (e.g. Food, Shopping) or view your complete transaction history?",
                match_status="NO_MATCH",
                matched_transactions=[],
                action_links=[MiloActionLink(label="View All Transactions", target_page="transactions", action_type="NAVIGATE")],
                evidence={"search_term": search_term, "total_records_searched": len(all_txns)}
            )

    @classmethod
    def _handle_spending_analysis(cls, db: Session, req: MiloChatMessageRequest, all_txns: List[Transaction], msg_lower: str) -> MiloChatMessageResponse:
        if not all_txns:
            return MiloChatMessageResponse(
                session_id=req.session_id,
                intent="SPENDING_ANALYSIS",
                answer="You don't have any imported transactions yet, so I don't have recorded data to analyze your spending. Once you import your bank statement, I'll calculate your exact category breakdown!",
                follow_up_question="Would you like to import a bank statement CSV now?",
                match_status="NONE",
                action_links=[MiloActionLink(label="Import Statement Data", target_page="import", action_type="NAVIGATE")],
                evidence={"total_transactions": 0}
            )

        inc_txns = [t for t in all_txns if t.txn_type == "credit"]
        exp_txns = [t for t in all_txns if t.txn_type == "debit"]

        tot_inc = sum(t.amount for t in inc_txns)
        tot_exp = sum(t.amount for t in exp_txns)
        net_sav = tot_inc - tot_exp
        sav_rate = (net_sav / tot_inc * 100) if tot_inc > 0 else 0.0

        # Calculate category spending map
        cat_map: Dict[str, float] = {}
        for t in exp_txns:
            cat_map[t.category] = cat_map.get(t.category, 0.0) + t.amount

        top_cat = max(cat_map.items(), key=lambda x: x[1]) if cat_map else ("None", 0.0)
        top_cat_pct = (top_cat[1] / tot_exp * 100) if tot_exp > 0 else 0.0

        answer = (
            f"Here is your personalized monthly spending breakdown based on your **{len(all_txns)} recorded transactions**:\n\n"
            f"• **Total Income Recorded**: ₹{tot_inc:,.2f}\n"
            f"• **Total Expenses Recorded**: ₹{tot_exp:,.2f}\n"
            f"• **Net Savings**: ₹{net_sav:,.2f} (Savings Rate: **{sav_rate:.1f}%**)\n"
            f"• **Top Expense Driver**: **{top_cat[0]}** at **₹{top_cat[1]:,.2f}** ({top_cat_pct:.1f}% of all expenses)\n\n"
            f"Your money went primarily towards {top_cat[0]}. You can view the complete breakdown on your Dashboard!"
        )

        return MiloChatMessageResponse(
            session_id=req.session_id,
            intent="SPENDING_ANALYSIS",
            answer=answer,
            follow_up_question=f"Would you like to see how reducing spending on {top_cat[0]} by 15% accelerates your top savings goal?",
            match_status="NONE",
            action_links=[
                MiloActionLink(label="View Analytics Dashboard", target_page="dashboard", action_type="NAVIGATE"),
                MiloActionLink(label="Open Reports Explorer", target_page="reports", action_type="NAVIGATE")
            ],
            evidence={
                "recorded_income": tot_inc,
                "recorded_expenses": tot_exp,
                "net_savings": net_sav,
                "top_category": top_cat[0],
                "top_category_amount": top_cat[1]
            }
        )

    @classmethod
    def _handle_recurring_expenses(cls, db: Session, req: MiloChatMessageRequest, all_txns: List[Transaction]) -> MiloChatMessageResponse:
        recurring = FinancialForecaster.detect_recurring_expenses(req.user_id, db)
        
        if not recurring:
            answer = "I audited your transaction records, but I didn't detect any recurring monthly subscriptions or fixed bills yet. All your recorded expenses appear to be variable or one-off items."
            return MiloChatMessageResponse(
                session_id=req.session_id,
                intent="RECURRING_EXPENSES",
                answer=answer,
                follow_up_question="Would you like to review your highest variable spending categories instead?",
                match_status="NONE",
                action_links=[MiloActionLink(label="View Transactions", target_page="transactions", action_type="NAVIGATE")],
                evidence={"recurring_count": 0}
            )

        items_text = "\n".join([f"• **{r['merchant']}** — ₹{r['amount']:,.2f} / month ({r['category']})" for r in recurring[:5]])
        total_rec = sum(r['amount'] for r in recurring)

        answer = (
            f"I identified **{len(recurring)} recurring expenses** in your actual statement records, totaling **₹{total_rec:,.2f}/month**:\n\n"
            f"{items_text}\n\n"
            f"These recurring commitments account for fixed monthly outflows from your account balance."
        )

        return MiloChatMessageResponse(
            session_id=req.session_id,
            intent="RECURRING_EXPENSES",
            answer=answer,
            follow_up_question="Is one of these recurring bills expected to change next month, or would you like to model a budget reduction?",
            match_status="NONE",
            action_links=[MiloActionLink(label="Review Cashflow Forecast", target_page="forecasts", action_type="NAVIGATE")],
            evidence={"recurring_items": recurring, "total_recurring_monthly": total_rec}
        )

    @classmethod
    def _handle_cashflow_forecast(cls, db: Session, req: MiloChatMessageRequest, all_txns: List[Transaction]) -> MiloChatMessageResponse:
        if not all_txns:
            return MiloChatMessageResponse(
                session_id=req.session_id,
                intent="CASHFLOW_FORECAST",
                answer="I can't generate a cash-flow forecast yet because you don't have any imported transaction records. Import your bank statement to calculate your future safety buffer timeline!",
                follow_up_question="Would you like to import a bank statement CSV now?",
                match_status="NONE",
                action_links=[MiloActionLink(label="Import Statement", target_page="import", action_type="NAVIGATE")],
                evidence={"total_transactions": 0}
            )

        eval_result = FinancialRiskEngine.calculate_personalized_risk(transactions=all_txns)
        
        start_bal = eval_result["current_balance"]
        risk_level = eval_result["risk_level"]
        breach_detected = eval_result["breach_detected"]
        days_until = eval_result["days_until_breach"]
        shortfall = eval_result["max_shortfall"]
        obligations = [b["merchant"] for b in eval_result["contributing_recurring_bills"]]

        if breach_detected:
            answer = (
                f"⚠️ **Cash-Flow Alert**: Your account balance is projected to fall below your **₹{eval_result['safety_buffer']:,.2f} safety buffer** in **{days_until} days**.\n\n"
                f"• **Current Balance**: ₹{start_bal:,.2f}\n"
                f"• **Risk Rating**: **{risk_level}**\n"
                f"• **Maximum Shortfall**: ₹{shortfall:,.2f}\n"
                f"• **Key Contributing Bills**: {', '.join(obligations) if obligations else 'Upcoming recurring expenses'}\n\n"
                f"This drop is driven by upcoming scheduled commitments exceeding expected interim income."
            )
        else:
            answer = (
                f"✅ **Healthy Cash-Flow Status**: Your cash-flow forecast shows your balance will remain safely **above your ₹{eval_result['safety_buffer']:,.2f} safety buffer** over the next 45 days!\n\n"
                f"• **Current Balance**: ₹{start_bal:,.2f}\n"
                f"• **Risk Rating**: **LOW**\n"
                f"• **Buffer Status**: Secure (No breaches detected)\n\n"
                f"You have a healthy liquidity buffer for your upcoming routine expenses."
            )

        return MiloChatMessageResponse(
            session_id=req.session_id,
            intent="CASHFLOW_FORECAST",
            answer=answer,
            follow_up_question="Would you like to simulate delaying a major payment or running a scenario in the Financial Time Machine?",
            match_status="NONE",
            action_links=[
                MiloActionLink(label="Open Risk Timeline", target_page="forecasts", action_type="NAVIGATE"),
                MiloActionLink(label="Test in Time Machine", target_page="time-machine", action_type="NAVIGATE")
            ],
            evidence=eval_result
        )

    @classmethod
    def _handle_savings_goals(cls, db: Session, req: MiloChatMessageRequest) -> MiloChatMessageResponse:
        goal_repo = SavingsGoalRepository(db)
        goals = goal_repo.get_by_user(req.user_id)

        if not goals:
            answer = "You don't have any active savings goals set up yet! Setting a clear goal (like an Emergency Fund or New Laptop) is the best way to direct your monthly surplus."
            return MiloChatMessageResponse(
                session_id=req.session_id,
                intent="SAVINGS_GOALS",
                answer=answer,
                follow_up_question="What financial milestone would you like to save for first?",
                match_status="NONE",
                action_links=[MiloActionLink(label="Create a Savings Goal", target_page="savings", action_type="NAVIGATE")],
                evidence={"goals_count": 0}
            )

        tx_repo = TransactionRepository(db)
        all_txns = tx_repo.get_by_user(req.user_id, limit=500)
        opt_res = SavingsOptimizer.optimize_goal_allocations(goals=goals, user_id=req.user_id, transactions=all_txns)

        goals_text = "\n".join([
            f"• **{g.name}**: Saved ₹{g.current_amount:,.2f} of ₹{g.target_amount:,.2f} (Target Date: {g.target_date.strftime('%d %b %Y')})"
            for g in goals[:4]
        ])

        surplus = opt_res.monthly_available_surplus

        answer = (
            f"Here is your personalized Savings Goal progress:\n\n"
            f"{goals_text}\n\n"
            f"• **Available Monthly Surplus**: **₹{surplus:,.2f}/month**\n"
            f"• **Optimizer Status**: Allocating surplus by goal priority score."
        )

        return MiloChatMessageResponse(
            session_id=req.session_id,
            intent="SAVINGS_GOALS",
            answer=answer,
            follow_up_question="Would you like to see how reducing discretionary spending by 10% accelerates your top priority goal?",
            match_status="NONE",
            action_links=[MiloActionLink(label="View Savings Goals Optimizer", target_page="savings", action_type="NAVIGATE")],
            evidence=opt_res.model_dump()
        )

    @classmethod
    def _handle_scenario_simulation(cls, db: Session, req: MiloChatMessageRequest, all_txns: List[Transaction], msg_lower: str, prev_context: Dict[str, Any]) -> MiloChatMessageResponse:
        # Extract potential expense amount if mentioned
        amount_match = re.search(r'(\d+[\d,.]*)', msg_lower)
        expense_amt = float(amount_match.group(1).replace(',', '')) if amount_match else 15000.0

        scenario_date = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")

        scenario_params = {
            "horizon_days": 60,
            "one_off_expenses": [{"description": "Simulated Unexpected Expense", "amount": expense_amt, "date": scenario_date}],
            "income_delay_days": 0,
            "income_reduction_percent": 0.0,
            "spending_category_changes": {}
        }

        baseline_forecast = FinancialForecaster.forecast_cashflow(transactions=all_txns, user_id=req.user_id)
        scenario_forecast = FinancialForecaster.forecast_cashflow(transactions=all_txns, user_id=req.user_id, scenario_overrides=scenario_params)

        baseline_end = baseline_forecast.end_balance
        scenario_end = scenario_forecast.end_balance
        diff = baseline_end - scenario_end
        breach_delta = len(scenario_forecast.breaches) - len(baseline_forecast.breaches)

        answer = (
            f"🧪 **Financial Time Machine Scenario Preview**:\n\n"
            f"I ran a simulation of a hypothetical **₹{expense_amt:,.2f} expense** on {scenario_date}:\n\n"
            f"• **Baseline Projected End Balance**: ₹{baseline_end:,.2f}\n"
            f"• **Scenario Projected End Balance**: ₹{scenario_end:,.2f}\n"
            f"• **Net Impact**: **-₹{abs(diff):,.2f}**\n"
            f"• **Buffer Breach Impact**: {breach_delta} additional buffer breaches\n\n"
            f"*(Note: This is a sandbox scenario preview only. Your actual database transaction ledger remains completely unmodified.)*"
        )

        return MiloChatMessageResponse(
            session_id=req.session_id,
            intent="SCENARIO_SIMULATION",
            answer=answer,
            follow_up_question="Would you like to open the Financial Time Machine to run custom delay or category reduction scenarios?",
            match_status="NONE",
            action_links=[
                MiloActionLink(
                    label="Preview in Financial Time Machine",
                    target_page="time-machine",
                    action_type="PREVIEW_SCENARIO",
                    payload=scenario_params
                )
            ],
            evidence={"baseline_end": baseline_end, "scenario_end": scenario_end, "diff": diff, "breach_delta": breach_delta}
        )

    @classmethod
    def _handle_general_education(cls, req: MiloChatMessageRequest, msg_lower: str) -> MiloChatMessageResponse:
        if "50/30/20" in msg_lower:
            answer = (
                "The **50/30/20 Budgeting Rule** is a simple, effective guideline for managing your money:\n\n"
                "• **50% Needs**: Essential living costs like rent, utilities, and basic groceries.\n"
                "• **30% Wants**: Discretionary choices like dining out, shopping, and entertainment.\n"
                "• **20% Savings**: Building your emergency fund, investments, and future goals.\n\n"
                "Think of it like dividing your paycheck into three buckets before spending!"
            )
        elif "buffer" in msg_lower:
            answer = (
                "A **Safety Buffer** is a minimum liquidity threshold (like ₹3,000 or 1 month's expenses) "
                "kept in your account to protect you from unexpected bill timings or overdraft fees.\n\n"
                "BrokeNoMore automatically monitors your cash-flow forecast against your safety buffer so you're alerted before a breach happens!"
            )
        else:
            answer = (
                "Building financial health comes down to 3 core habits:\n\n"
                "1. **Tracking Inflows vs Outflows**: Knowing where every rupee goes.\n"
                "2. **Maintaining a Safety Buffer**: Keeping 1-3 months of expenses liquid for surprises.\n"
                "3. **Prioritizing Savings Goals**: Automatically setting aside a portion of income before spending."
            )

        return MiloChatMessageResponse(
            session_id=req.session_id,
            intent="GENERAL_EDUCATION",
            answer=answer,
            follow_up_question="Would you like me to check your recorded savings rate to see how close you are to the 20% savings target?",
            match_status="NONE",
            action_links=[MiloActionLink(label="View Analytics Dashboard", target_page="dashboard", action_type="NAVIGATE")],
            evidence={"topic": "education"}
        )

    @classmethod
    def _handle_out_of_scope(cls, user_id: str, session_id: str, msg_text: str) -> MiloChatMessageResponse:
        answer = (
            "🔒 **Security Notice**: For your protection, Milo will **NEVER** request your banking passwords, OTPs, UPI PINs, or confidential credentials.\n\n"
            "I'm here to provide educational decision support and analyze your imported BrokeNoMore statements safely. Please refrain from entering secret codes or sensitive credentials!"
        )
        resp = MiloChatMessageResponse(
            session_id=session_id,
            intent="OUT_OF_SCOPE",
            answer=answer,
            follow_up_question="What money management topic or recorded expense can I help you check today?",
            match_status="NONE",
            action_links=[MiloActionLink(label="Return to Dashboard", target_page="dashboard", action_type="NAVIGATE")],
            evidence={"security_triggered": True}
        )
        resp.reply = answer
        resp.actions = [
            {"label": a.label, "target_tab": a.target_page, "action_type": a.action_type, "scenario_type": None}
            for a in resp.action_links
        ]
        return resp

    @classmethod
    def _handle_fallback(cls, db: Session, req: MiloChatMessageRequest, all_txns: List[Transaction], msg_lower: str) -> MiloChatMessageResponse:
        if not all_txns:
            answer = (
                "Hey friend! I'm **Milo — Your Money Buddy**. I'm here to help you understand your spending, track your forecast, and reach your savings goals!\n\n"
                "Since you haven't imported any transactions yet, I don't have recorded data to analyze your personal numbers."
            )
            return MiloChatMessageResponse(
                session_id=req.session_id,
                intent="GENERAL_EDUCATION",
                answer=answer,
                follow_up_question="Would you like to import a bank statement CSV to get started?",
                match_status="NONE",
                action_links=[MiloActionLink(label="Import Statement Data", target_page="import", action_type="NAVIGATE")],
                evidence={"total_transactions": 0}
            )

        tot_inc = sum(t.amount for t in all_txns if t.txn_type == "credit")
        tot_exp = sum(t.amount for t in all_txns if t.txn_type == "debit")
        net = tot_inc - tot_exp

        answer = (
            f"Hey friend! Based on your **{len(all_txns)} recorded transactions**, your current net balance surplus is **₹{net:,.2f}** "
            f"(Total Income: ₹{tot_inc:,.2f}, Total Expenses: ₹{tot_exp:,.2f}).\n\n"
            f"I can help you look up specific transactions, analyze your top expense drivers, check your cash-flow forecast, or simulate financial scenarios in the Time Machine!"
        )

        return MiloChatMessageResponse(
            session_id=req.session_id,
            intent="SPENDING_ANALYSIS",
            answer=answer,
            follow_up_question="What financial question can I answer for you today?",
            match_status="NONE",
            action_links=[
                MiloActionLink(label="View Analytics Dashboard", target_page="dashboard", action_type="NAVIGATE"),
                MiloActionLink(label="View All Transactions", target_page="transactions", action_type="NAVIGATE")
            ],
            evidence={"total_transactions": len(all_txns), "net_surplus": net}
        )
