"""
BrokeNoMore Personalized Financial Risk Engine
=============================================
Computes forward-looking cash-flow risk, buffer breach timelines, and shortfall severity.

Key Inputs:
- Current account balance
- Historical transaction ledger
- Detected recurring bills (with confidence scores)
- Configurable safety buffer (default ₹5,000)
- Forecast horizons (7, 14, 30, 60 days)

Outputs:
- Forward balance timeline with confidence bands
- Risk Level: LOW, MODERATE, HIGH, CRITICAL
- Earliest estimated buffer breach date & days remaining
- Expected shortfall amount (in ₹)
- Contributing bills & evidence list
- Transparent assumptions statement
"""
import datetime
from datetime import date
from typing import List, Dict, Any, Optional
import numpy as np
from app.services.forecaster import FinancialForecaster

class FinancialRiskEngine:
    @staticmethod
    def calculate_personalized_risk(
        transactions: List[Dict[str, Any]],
        current_balance: float = 0.0,
        safety_buffer: float = 5000.0,
        horizon_days: int = 30,
        expected_monthly_income: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculates forward risk timeline, buffer breach date, shortfall, and evidence.
        """
        # Convert dicts or objects to Transaction-like objects
        txn_objs = []
        for t in transactions:
            if hasattr(t, "amount"):
                txn_objs.append(t)
            else:
                txn_date_val = t.get("txn_date", date.today().isoformat())
                if isinstance(txn_date_val, str):
                    try:
                        txn_date_val = date.fromisoformat(txn_date_val)
                    except ValueError:
                        txn_date_val = date.today()
                mock_t = type("MockTxn", (), {
                    "id": t.get("id", "temp_id"),
                    "txn_date": txn_date_val,
                    "description": t.get("description", ""),
                    "amount": float(t.get("amount", 0.0)),
                    "txn_type": t.get("txn_type", "debit"),
                    "category": t.get("category", "Miscellaneous")
                })()
                txn_objs.append(mock_t)

        # Step 1: Run deterministic forecaster
        forecast_res = FinancialForecaster.forecast_cashflow(
            transactions=txn_objs,
            user_id="risk_engine_user",
            horizon_days=horizon_days,
            safe_buffer=safety_buffer,
            initial_balance=current_balance
        )

        timeline = [pt.model_dump() for pt in forecast_res.daily_timeline]
        breach_alerts = [b.model_dump() for b in forecast_res.breaches]
        recurring_bills_raw = FinancialForecaster.detect_recurring_expenses(txn_objs)
        recurring_bills = [r.model_dump() for r in recurring_bills_raw]

        # Step 2: Determine risk level & breach metrics
        if not timeline:
            return {
                "risk_level": "LOW",
                "risk_score": 0.0,
                "current_balance": current_balance,
                "safety_buffer": safety_buffer,
                "min_projected_balance": current_balance,
                "end_projected_balance": current_balance,
                "breach_detected": False,
                "earliest_breach_date": None,
                "days_until_breach": None,
                "max_shortfall": 0.0,
                "horizon_days": horizon_days,
                "timeline": [],
                "buffer_breaches": [],
                "contributing_recurring_bills": [],
                "assumptions": [
                    "No historical transactions found.",
                    f"Baseline starting balance set to ₹{current_balance:,.2f}.",
                    f"Safety buffer target set to ₹{safety_buffer:,.2f}."
                ],
                "explanation": f"No transaction history available. Risk level is LOW by default with stable projected balance of ₹{current_balance:,.2f}."
            }

        min_balance = min(pt["projected_balance"] for pt in timeline)
        end_balance = timeline[-1]["projected_balance"]
        
        breach_detected = len(breach_alerts) > 0
        earliest_breach_date = breach_alerts[0]["date"] if breach_detected else None
        
        if earliest_breach_date:
            today = datetime.date.today()
            if isinstance(earliest_breach_date, datetime.date):
                breach_dt = earliest_breach_date
            else:
                breach_dt = datetime.date.fromisoformat(str(earliest_breach_date))
            days_until_breach = max(0, (breach_dt - today).days)
        else:
            days_until_breach = None

        max_shortfall = max(0.0, safety_buffer - min_balance)

        # Categorize Risk Level
        if min_balance < 0:
            risk_level = "CRITICAL"
            risk_score = 0.95
        elif breach_detected and days_until_breach is not None and days_until_breach <= 7:
            risk_level = "HIGH"
            risk_score = 0.80
        elif breach_detected:
            risk_level = "MODERATE"
            risk_score = 0.55
        else:
            risk_level = "LOW"
            risk_score = 0.15

        # Format contributing bills with provenance
        contributing_bills = []
        for bill in recurring_bills:
            amt = bill.get("estimated_amount", 0.0)
            merchant = bill.get("merchant_pattern", "Unknown Merchant")
            contributing_bills.append({
                "merchant": merchant,
                "estimated_monthly_amount": amt,
                "frequency": "Monthly",
                "confidence_type": "inferred_from_history",
                "evidence": f"Detected recurring obligation for '{merchant}' averaging ₹{amt:,.2f}."
            })

        # Explicit transparency assumptions
        assumptions = [
            f"Current starting balance: ₹{current_balance:,.2f}.",
            f"Configured minimum safety buffer: ₹{safety_buffer:,.2f}.",
            f"Analysis horizon: {horizon_days} days.",
            f"Inferred recurring monthly obligations: {len(recurring_bills)} bills totaling ₹{sum(b.get('estimated_amount', 0.0) for b in recurring_bills):,.2f}."
        ]

        if expected_monthly_income:
            assumptions.append(f"User-provided expected monthly income: ₹{expected_monthly_income:,.2f}.")

        # Narrative explanation
        if risk_level == "CRITICAL":
            explanation = (
                f"CRITICAL RISK: Projected balance will drop below zero to ₹{min_balance:,.2f} "
                f"on {earliest_breach_date} ({days_until_breach} days remaining). "
                f"Immediate cash-flow intervention required before shortfall of ₹{max_shortfall:,.2f} occurs."
            )
        elif risk_level == "HIGH":
            explanation = (
                f"HIGH RISK: Projected balance will breach your ₹{safety_buffer:,.2f} safety buffer "
                f"in {days_until_breach} days on {earliest_breach_date}. "
                f"Minimum projected balance: ₹{min_balance:,.2f}."
            )
        elif risk_level == "MODERATE":
            explanation = (
                f"MODERATE RISK: Safety buffer breach projected on {earliest_breach_date} "
                f"within the {horizon_days}-day horizon. Estimated buffer shortfall: ₹{max_shortfall:,.2f}."
            )
        else:
            explanation = (
                f"LOW RISK: Projected balance remains safely above your ₹{safety_buffer:,.2f} buffer "
                f"throughout the next {horizon_days} days. Minimum projected balance: ₹{min_balance:,.2f}."
            )

        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "current_balance": current_balance,
            "safety_buffer": safety_buffer,
            "min_projected_balance": min_balance,
            "end_projected_balance": end_balance,
            "breach_detected": breach_detected,
            "earliest_breach_date": earliest_breach_date,
            "days_until_breach": days_until_breach,
            "max_shortfall": max_shortfall,
            "horizon_days": horizon_days,
            "timeline": timeline,
            "buffer_breaches": breach_alerts,
            "contributing_recurring_bills": contributing_bills,
            "assumptions": assumptions,
            "explanation": explanation
        }
