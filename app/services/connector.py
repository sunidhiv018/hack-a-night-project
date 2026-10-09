import random
from datetime import date, timedelta
from typing import List, Dict, Any

class SimulatedBankConnector:
    """
    Clearly labeled demonstration connector representing an authorized financial data aggregator interface.
    NOTE: Consumer APIs like Google Pay or UPI apps do NOT expose public REST endpoints for user transaction history.
    This adapter simulates an authorized AA (Account Aggregator) sandbox stream for demo purposes.
    """
    
    DEMO_MERCHANTS = [
        ("Zomato Online", "Dining & Food", "debit", 250.0, 850.0),
        ("Swiggy Delivery", "Dining & Food", "debit", 180.0, 600.0),
        ("Blinkit Instant", "Groceries", "debit", 400.0, 1500.0),
        ("Uber Trip", "Transportation", "debit", 150.0, 450.0),
        ("Reliance Smart Mart", "Groceries", "debit", 1200.0, 4500.0),
        ("Amazon Pay Merchant", "Shopping", "debit", 500.0, 3500.0),
        ("Monthly Tech Salary", "Income", "credit", 75000.0, 75000.0),
        ("Netflix Subscription", "Subscriptions & Ent.", "debit", 649.0, 649.0),
        ("Electricity Utility Bill", "Utilities", "debit", 1800.0, 3200.0)
    ]

    @classmethod
    def fetch_simulated_transactions(cls, count: int = 25) -> List[Dict[str, Any]]:
        records = []
        today = date.today()

        # Always include at least 2 monthly salaries
        records.append({
            "txn_date": str(today - timedelta(days=5)),
            "description": "Monthly Tech Salary Direct Deposit",
            "amount": 75000.0,
            "txn_type": "credit",
            "category": "Income"
        })
        records.append({
            "txn_date": str(today - timedelta(days=35)),
            "description": "Monthly Tech Salary Direct Deposit",
            "amount": 75000.0,
            "txn_type": "credit",
            "category": "Income"
        })

        for i in range(count - 2):
            days_ago = random.randint(1, 60)
            txn_date = today - timedelta(days=days_ago)
            merchant, cat, t_type, min_a, max_a = random.choice(cls.DEMO_MERCHANTS)
            if merchant == "Monthly Tech Salary":
                continue # Already handled

            amt = round(random.uniform(min_a, max_a), 2)
            records.append({
                "txn_date": str(txn_date),
                "description": f"UPI-{merchant}-{random.randint(100000, 999999)}",
                "amount": amt,
                "txn_type": t_type,
                "category": cat
            })

        return sorted(records, key=lambda x: x["txn_date"], reverse=True)
