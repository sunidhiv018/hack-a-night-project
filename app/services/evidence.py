from typing import List, Dict, Any
from app.models.domain import Transaction
from app.schemas.schemas import EvidenceItem, TransactionResponse
from app.services.forecaster import FinancialForecaster
from app.services.optimizer import SavingsOptimizer

class EvidenceGenerator:
    @staticmethod
    def generate_report_evidence(
        transactions: List[Transaction],
        user_id: str,
        forecast_data: Dict[str, Any],
        goal_data: Dict[str, Any]
    ) -> List[EvidenceItem]:
        """Generate structured evidence items with calculations and transaction trace for the UI Report Explorer."""
        items: List[EvidenceItem] = []

        # Convert transactions to Pydantic responses for output
        txn_responses = [TransactionResponse.model_validate(t) for t in transactions]

        # 1. Cash Flow Forecast Evidence Item
        breaches = forecast_data.get("breaches", [])
        if breaches:
            earliest_breach = breaches[0]
            # Find supporting transactions in the past 30 days that contribute to high spending
            top_expenses = sorted([t for t in txn_responses if t.txn_type == "debit"], key=lambda x: x.amount, reverse=True)[:5]

            items.append(
                EvidenceItem(
                    title="Upcoming Cash-Flow Buffer Deficit",
                    recommendation=f"Reduce discretionary dining/shopping spending by ₹{earliest_breach.get('shortfall', 0):,.2f} before {earliest_breach.get('date')} to maintain safe buffer.",
                    supporting_transactions=top_expenses,
                    calculation_details={
                        "projected_balance": earliest_breach.get("projected_balance"),
                        "safe_buffer_limit": earliest_breach.get("safe_buffer"),
                        "shortfall_amount": earliest_breach.get("shortfall"),
                        "causes": earliest_breach.get("primary_causes")
                    },
                    assumptions=[
                        "Historical daily average spending continues at baseline rate.",
                        "Income arrives according to user schedule."
                    ],
                    projected_impact=f"Avoids falling below the ₹{earliest_breach.get('safe_buffer', 5000):,.2f} safety threshold on {earliest_breach.get('date')}."
                )
            )
        else:
            items.append(
                EvidenceItem(
                    title="Healthy Liquidity Reserve",
                    recommendation="Maintain current spending patterns and consider allocating excess monthly surplus into high-priority savings goals.",
                    supporting_transactions=txn_responses[:5],
                    calculation_details={
                        "start_balance": forecast_data.get("start_balance"),
                        "end_balance": forecast_data.get("end_balance"),
                        "horizon_days": forecast_data.get("horizon_days")
                    },
                    assumptions=["No major unexpected unbudgeted lump-sum expenses occur."],
                    projected_impact="Sustains financial stability with zero buffer breaches over the next quarter."
                )
            )

        # 2. Goal Conflict Evidence Item
        conflicts = goal_data.get("conflicts_detected", [])
        allocations = goal_data.get("allocations", [])
        if conflicts:
            items.append(
                EvidenceItem(
                    title="Savings Goal Over-allocation Conflict",
                    recommendation="Adjust target dates or increase net monthly surplus to resolve goal deadline conflicts.",
                    supporting_transactions=[t for t in txn_responses if t.txn_type == "debit"][:5],
                    calculation_details={
                        "monthly_available_surplus": goal_data.get("monthly_available_surplus"),
                        "conflicts": conflicts,
                        "allocated_goals_count": len(allocations)
                    },
                    assumptions=["SciPy optimization prioritized higher-priority goals over lower-priority ones."],
                    projected_impact="Ensures high-priority goals (e.g. Emergency Fund) remain on track without defaulting on other commitments."
                )
            )

        return items
