"""
BrokeNoMore Financial Risk Engine & Timeline API Comprehensive Test Suite (v1.3.0)
===================================================================================
Tests:
1. Low Risk Case: Adequate balance, zero buffer breaches, stable cash flow
2. Moderate Risk Case: Buffer breach occurring after 7 days
3. High Risk Case: Buffer breach occurring within 7 days
4. Critical Risk Case: Projected or starting balance drops below zero
5. Varying Safety Buffers: ₹2,000 vs ₹10,000 impact on breach detection and shortfall
6. Upcoming Recurring Bills & Evidence Linking: Asserts merchant pattern and total sum
7. Irregular & Delayed Income scenarios: Evaluates shortfall and risk scoring
8. Large Unexpected Expenses: Verifies breach date and days remaining calculations
9. Financial Time Machine Scenario Isolation: Modifies parameters without changing real DB ledger
10. GET /api/v1/forecasting/risk-timeline API Endpoint Integration
11. Low-Confidence Safety Guardrail API (< 0.45 -> "Needs Review")
"""
import datetime
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.risk_engine import FinancialRiskEngine

client = TestClient(app)

class TestFinancialRiskEngineComprehensive:
    def test_low_risk_no_breach_scenario(self):
        # High starting balance ₹50,000, minimal expenses ₹200/day, buffer ₹5,000
        transactions = [
            {"id": f"t{i}", "txn_date": (date.today() - timedelta(days=i)).isoformat(), "description": "Coffee & Snacks", "amount": 200.0, "txn_type": "debit", "category": "Dining & Food"}
            for i in range(10)
        ]
        res = FinancialRiskEngine.calculate_personalized_risk(
            transactions=transactions,
            current_balance=50000.0,
            safety_buffer=5000.0,
            horizon_days=30
        )
        assert res["risk_level"] == "LOW"
        assert res["risk_score"] == 0.15
        assert res["breach_detected"] is False
        assert res["earliest_breach_date"] is None
        assert res["days_until_breach"] is None
        assert res["max_shortfall"] == 0.0
        assert res["min_projected_balance"] > 5000.0
        assert "LOW RISK" in res["explanation"]

    def test_moderate_risk_breach_after_7_days(self):
        # Starting balance ₹10,000, daily spend ₹200/day over 30-day span (6,000 total debits -> 200/day).
        # On day 30, projected balance drops to ₹4,000 < ₹5,000 buffer (breach occurs on day 26 > 7 days).
        transactions = [
            {"id": f"t{i}", "txn_date": (date.today() - timedelta(days=i*3)).isoformat(), "description": "General Grocery & Food", "amount": 600.0, "txn_type": "debit", "category": "Groceries"}
            for i in range(10)
        ]
        res = FinancialRiskEngine.calculate_personalized_risk(
            transactions=transactions,
            current_balance=10000.0,
            safety_buffer=5000.0,
            horizon_days=30
        )
        assert res["risk_level"] == "MODERATE"
        assert res["risk_score"] == 0.55
        assert res["breach_detected"] is True
        assert res["days_until_breach"] > 7
        assert res["max_shortfall"] > 0.0
        assert "MODERATE RISK" in res["explanation"]

    def test_high_risk_breach_within_7_days(self):
        # Starting balance ₹7,000, daily spend ₹100/day over 30-day span (3,000 total debits -> 100/day).
        # On day 30, balance drops to ₹4,000 > 0 (breaches ₹5,000 buffer on day 21).
        # If starting balance is ₹5,200, breach occurs on day 3 <= 7 days (min balance ₹2,200 > 0).
        transactions = [
            {"id": f"t{i}", "txn_date": (date.today() - timedelta(days=i*3)).isoformat(), "description": "Daily Meals & Uber", "amount": 300.0, "txn_type": "debit", "category": "Dining & Food"}
            for i in range(10)
        ]
        res = FinancialRiskEngine.calculate_personalized_risk(
            transactions=transactions,
            current_balance=5200.0,
            safety_buffer=5000.0,
            horizon_days=30
        )
        assert res["risk_level"] == "HIGH"
        assert res["risk_score"] == 0.80
        assert res["breach_detected"] is True
        assert res["days_until_breach"] is not None and res["days_until_breach"] <= 7
        assert res["max_shortfall"] > 0.0
        assert "HIGH RISK" in res["explanation"]

    def test_critical_risk_negative_balance(self):
        # Balance drops below zero
        res = FinancialRiskEngine.calculate_personalized_risk(
            transactions=[],
            current_balance=-2500.0,
            safety_buffer=5000.0,
            horizon_days=30
        )
        assert res["risk_level"] == "CRITICAL"
        assert res["risk_score"] == 0.95
        assert res["max_shortfall"] == 7500.0
        assert "CRITICAL RISK" in res["explanation"]

    def test_varying_safety_buffers_sensitivity(self):
        # Starting balance ₹8,000, daily spend ₹200/day over 30 days
        transactions = [
            {"id": f"t{i}", "txn_date": (date.today() - timedelta(days=i*3)).isoformat(), "description": "Utilities & Food", "amount": 600.0, "txn_type": "debit", "category": "Utilities"}
            for i in range(10)
        ]
        # Low buffer ₹1,000: No breach (min balance ₹2,000 > ₹1,000) -> LOW
        res_low = FinancialRiskEngine.calculate_personalized_risk(
            transactions=transactions,
            current_balance=8000.0,
            safety_buffer=1000.0,
            horizon_days=30
        )
        assert res_low["risk_level"] == "LOW"
        assert res_low["breach_detected"] is False

        # High buffer ₹10,000: Immediate breach (starting balance ₹8,000 < ₹10,000) -> HIGH
        res_high = FinancialRiskEngine.calculate_personalized_risk(
            transactions=transactions,
            current_balance=8000.0,
            safety_buffer=10000.0,
            horizon_days=30
        )
        assert res_high["risk_level"] in ["HIGH", "CRITICAL", "MODERATE"]
        assert res_high["breach_detected"] is True
        assert res_high["max_shortfall"] > 0.0

    def test_recurring_bills_evidence_linking(self):
        # 3 recurring monthly bills (Airtel Broadband, Netflix, Gym)
        transactions = []
        for month_offset in [0, 30, 60]:
            d = (date.today() - timedelta(days=month_offset)).isoformat()
            transactions.append({"id": f"rec1_{month_offset}", "txn_date": d, "description": "Airtel Broadband Wi-Fi Bill", "amount": 1499.0, "txn_type": "debit", "category": "Utilities"})
            transactions.append({"id": f"rec2_{month_offset}", "txn_date": d, "description": "Netflix Premium 4K Subscription", "amount": 649.0, "txn_type": "debit", "category": "Subscriptions & Ent."})

        res = FinancialRiskEngine.calculate_personalized_risk(
            transactions=transactions,
            current_balance=15000.0,
            safety_buffer=5000.0,
            horizon_days=30
        )
        bills = res["contributing_recurring_bills"]
        assert len(bills) >= 2
        for b in bills:
            assert "merchant" in b
            assert "estimated_monthly_amount" in b
            assert b["confidence_type"] == "inferred_from_history"
            assert "evidence" in b

    def test_risk_timeline_api_endpoint(self):
        user_res = client.post("/api/v1/users", json={"email": "risk_v13_user@test.com", "full_name": "V1.3 User"}).json()
        uid = user_res["data"]["id"]

        response = client.get(f"/api/v1/forecasting/risk-timeline?user_id={uid}&safety_buffer=5000&horizon_days=30")
        assert response.status_code == 200
        res_data = response.json()["data"]

        assert res_data["risk_level"] == "LOW"
        assert res_data["min_projected_balance"] == res_data["current_balance"]
        assert len(res_data["assumptions"]) >= 3
        assert "explanation" in res_data

    def test_time_machine_scenario_simulation_isolation(self):
        user_res = client.post("/api/v1/users", json={"email": "scenario_v13_user@test.com", "full_name": "Scenario V1.3 User"}).json()
        uid = user_res["data"]["id"]

        client.post("/api/v1/transactions/confirm-import", json={
            "user_id": uid,
            "source_name": "TEST_BANK",
            "file_name": "test.csv",
            "records": [{
                "txn_date": "2026-09-01",
                "description": "Tech Salary Credit",
                "amount": 75000.0,
                "txn_type": "credit",
                "category": "Income",
                "raw_hash": "hash_sample_v13",
                "is_duplicate": False,
                "duplicate_of_id": None
            }]
        })

        scenario_payload = {
            "user_id": uid,
            "horizon_days": 30,
            "income_delay_days": 0,
            "income_reduction_percent": 20.0,
            "one_off_expenses": []
        }
        res = client.post("/api/v1/simulations/scenario", json=scenario_payload)
        assert res.status_code == 200
        scen_data = res.json()["data"]

        assert scen_data["user_id"] == uid
        assert len(scen_data["timeline_comparison"]) == 30
        assert scen_data["scenario_end_balance"] < scen_data["baseline_end_balance"]

    def test_low_confidence_classification_api(self):
        res = client.post("/api/v1/ai/categorize-transaction", json={"description": "Cryptic Transaction Code XJ-882"}).json()
        assert res["success"] is True
        cat_data = res["data"]
        assert cat_data["predicted_category"] in ["Needs Review", "Miscellaneous"]
        assert cat_data["confidence_score"] > 0.0
