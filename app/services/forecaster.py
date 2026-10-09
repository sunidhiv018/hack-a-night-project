import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple, Optional
from app.models.domain import Transaction
from app.schemas.schemas import ForecastDailyPoint, BufferBreachAlert, ForecastResponse, RecurringExpense, UnusualSpendingAlert

# Graceful sklearn fallback (DLL may be blocked by Windows AppControl)
try:
    from sklearn.linear_model import LinearRegression
    _SKLEARN_LR_AVAILABLE = True
except (ImportError, OSError):
    _SKLEARN_LR_AVAILABLE = False


class FinancialForecaster:
    @staticmethod
    def forecast_cashflow(
        transactions: List[Transaction],
        user_id: str,
        horizon_days: int = 90,
        safe_buffer: float = 5000.0,
        initial_balance: float = 25000.0,
        scenario_overrides: Optional[Dict[str, Any]] = None
    ) -> ForecastResponse:
        """
        Calculates baseline cash flow forecast or applies scenario parameters:
        - scenario_overrides: {
            'income_delay_days': int,
            'income_reduction_percent': float,
            'one_off_expenses': list of dicts {'description', 'amount', 'date'},
            'spending_category_changes': dict {'Category': %change}
          }
        """
        if not transactions:
            today = date.today()
            daily_timeline = []
            curr_bal = initial_balance
            for i in range(horizon_days):
                d = today + timedelta(days=i)
                daily_timeline.append(
                    ForecastDailyPoint(
                        date=d,
                        projected_balance=curr_bal,
                        projected_income=0.0,
                        projected_expense=0.0,
                        is_breach=curr_bal < safe_buffer,
                        confidence_lower=curr_bal * 0.95,
                        confidence_upper=curr_bal * 1.05
                    )
                )
            return ForecastResponse(
                user_id=user_id,
                horizon_days=horizon_days,
                start_balance=initial_balance,
                end_balance=curr_bal,
                safe_buffer=safe_buffer,
                breaches=[],
                daily_timeline=daily_timeline,
                model_method="EMPTY_HISTORICAL_BASELINE",
                explanations=["No historical transactions available. Projections assume flat balance."]
            )

        df = pd.DataFrame([
            {
                "id": t.id,
                "date": pd.to_datetime(t.txn_date),
                "amount": t.amount,
                "type": t.txn_type,
                "category": t.category,
                "description": t.description
            }
            for t in transactions
        ])

        df_income = df[df["type"] == "credit"]
        df_expense = df[df["type"] == "debit"]

        min_date = df["date"].min()
        max_date = df["date"].max()
        days_span = max((max_date - min_date).days, 1)

        daily_avg_expense = df_expense["amount"].sum() / days_span if not df_expense.empty else 0.0
        
        cat_daily_avg = {}
        if not df_expense.empty:
            cat_totals = df_expense.groupby("category")["amount"].sum()
            for cat, tot in cat_totals.items():
                cat_daily_avg[cat] = tot / days_span

        salary_txns = df_income[df_income["category"].str.lower().str.contains("income|salary|payroll")]
        avg_monthly_salary = salary_txns["amount"].mean() if not salary_txns.empty else (df_income["amount"].sum() / (days_span / 30.0) if not df_income.empty else 0.0)

        scenario = scenario_overrides or {}
        income_delay = scenario.get("income_delay_days", 0)
        income_reduction = scenario.get("income_reduction_percent", 0.0) / 100.0
        one_off_expenses = scenario.get("one_off_expenses", [])
        cat_changes = scenario.get("spending_category_changes", {})

        adjusted_monthly_salary = avg_monthly_salary * (1.0 - income_reduction)

        start_date = date.today()
        current_balance = initial_balance
        daily_timeline: List[ForecastDailyPoint] = []
        breaches: List[BufferBreachAlert] = []
        explanations: List[str] = []

        for i in range(horizon_days):
            d = start_date + timedelta(days=i)
            day_num = d.day

            day_income = 0.0
            effective_salary_day = 1 + income_delay
            if day_num == (effective_salary_day if effective_salary_day <= 28 else 28):
                day_income += adjusted_monthly_salary

            day_expense = 0.0
            for cat, base_avg in cat_daily_avg.items():
                multiplier = 1.0 + (cat_changes.get(cat, 0.0) / 100.0)
                day_expense += base_avg * max(0.0, multiplier)

            if not cat_daily_avg:
                day_expense = daily_avg_expense

            for ooff in one_off_expenses:
                o_date = pd.to_datetime(ooff.get("date")).date() if ooff.get("date") else None
                if o_date == d:
                    day_expense += float(ooff.get("amount", 0))

            current_balance = current_balance + day_income - day_expense

            is_breach = current_balance < safe_buffer
            
            uncertainty = (i + 1) * (daily_avg_expense * 0.05)
            c_lower = current_balance - uncertainty
            c_upper = current_balance + uncertainty

            daily_point = ForecastDailyPoint(
                date=d,
                projected_balance=round(current_balance, 2),
                projected_income=round(day_income, 2),
                projected_expense=round(day_expense, 2),
                is_breach=is_breach,
                confidence_lower=round(c_lower, 2),
                confidence_upper=round(c_upper, 2)
            )
            daily_timeline.append(daily_point)

            if is_breach:
                shortfall = safe_buffer - current_balance
                causes = []
                if day_expense > daily_avg_expense * 1.5:
                    causes.append("High projected daily expenditure")
                if income_delay > 0 and i < income_delay + 5:
                    causes.append(f"Income delay of {income_delay} days")
                if income_reduction > 0:
                    causes.append(f"Income reduction of {income_reduction*100}%")
                if not causes:
                    causes.append("Cumulative daily spending exceeding balance replenishment")

                breaches.append(
                    BufferBreachAlert(
                        date=d,
                        projected_balance=round(current_balance, 2),
                        safe_buffer=safe_buffer,
                        shortfall=round(shortfall, 2),
                        primary_causes=causes,
                        supporting_evidence=[
                            {"historical_avg_daily_expense": round(daily_avg_expense, 2)},
                            {"adjusted_monthly_income": round(adjusted_monthly_salary, 2)},
                            {"days_into_forecast": i}
                        ]
                    )
                )

        if breaches:
            explanations.append(f"Detected {len(breaches)} projected buffer breach(es) below minimum safety limit of ₹{safe_buffer:,.2f}.")
            explanations.append(f"Earliest projected breach occurs on {breaches[0].date} with a balance of ₹{breaches[0].projected_balance:,.2f}.")
        else:
            explanations.append(f"Cash flow remains healthy across the entire {horizon_days}-day forecast horizon.")

        return ForecastResponse(
            user_id=user_id,
            horizon_days=horizon_days,
            start_balance=initial_balance,
            end_balance=round(current_balance, 2),
            safe_buffer=safe_buffer,
            breaches=breaches,
            daily_timeline=daily_timeline,
            model_method="HISTORICAL_RUNRATE_LINEARTREND",
            explanations=explanations
        )

    @staticmethod
    def detect_recurring_expenses(transactions: List[Transaction]) -> List[RecurringExpense]:
        if not transactions:
            return []

        df = pd.DataFrame([
            {
                "id": t.id,
                "date": pd.to_datetime(t.txn_date),
                "desc": t.description,
                "amount": t.amount,
                "type": t.txn_type,
                "category": t.category
            }
            for t in transactions if t.txn_type == "debit"
        ])

        if df.empty:
            return []

        df["merchant"] = df["desc"].str.strip().str.upper().apply(lambda s: s.split()[0] if len(s.split()) > 0 else s)

        recurring: List[RecurringExpense] = []
        for merchant, group in df.groupby("merchant"):
            if len(group) >= 2:
                sorted_dates = group["date"].sort_values()
                diffs = sorted_dates.diff().dt.days.dropna()
                avg_diff = diffs.mean()
                avg_amt = group["amount"].mean()
                
                if 25 <= avg_diff <= 35:
                    freq = 30
                    conf = 0.90
                elif 6 <= avg_diff <= 8:
                    freq = 7
                    conf = 0.85
                else:
                    continue

                last_date = sorted_dates.max().date()
                next_date = last_date + timedelta(days=int(freq))

                recurring.append(
                    RecurringExpense(
                        merchant_pattern=merchant,
                        category=group["category"].iloc[0],
                        estimated_amount=round(float(avg_amt), 2),
                        frequency_days=freq,
                        next_expected_date=next_date,
                        confidence_score=conf,
                        transaction_ids=group["id"].tolist(),
                        reasoning=f"Found {len(group)} transactions with average gap of {avg_diff:.1f} days."
                    )
                )

        return recurring

    @staticmethod
    def detect_unusual_spending(transactions: List[Transaction], z_threshold: float = 2.0) -> List[UnusualSpendingAlert]:
        debits = [t for t in transactions if t.txn_type == "debit"]
        if len(debits) < 5:
            return []

        df = pd.DataFrame([
            {
                "id": t.id,
                "date": t.txn_date,
                "desc": t.description,
                "amount": t.amount,
                "category": t.category
            }
            for t in debits
        ])

        alerts: List[UnusualSpendingAlert] = []
        for cat, group in df.groupby("category"):
            if len(group) < 3:
                continue
            mean = group["amount"].mean()
            std = group["amount"].std()
            if std == 0 or pd.isna(std):
                continue

            for _, row in group.iterrows():
                z = (row["amount"] - mean) / std
                if z >= z_threshold:
                    alerts.append(
                        UnusualSpendingAlert(
                            transaction_id=row["id"],
                            txn_date=row["date"],
                            description=row["desc"],
                            amount=round(row["amount"], 2),
                            category=cat,
                            baseline_avg=round(mean, 2),
                            z_score=round(float(z), 2),
                            explanation=f"Spending of ₹{row['amount']:,.2f} is {z:.1f} std devs above category baseline average of ₹{mean:,.2f}."
                        )
                    )

        return sorted(alerts, key=lambda x: x.z_score, reverse=True)
