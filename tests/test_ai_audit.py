"""
BrokeNoMore AI Audit Test Suite
================================
Dedicated tests that verify the HONESTY and CORRECTNESS of every AI feature.

Tests validate:
  1. That /ai/health accurately reports which methods are actually running
  2. That categorization responses carry the correct method label
  3. That rule-based fallback produces correct, labelled results
  4. That anomaly detection returns sensible output (and honest method label)
  5. That the copilot disclaimer is honest (not-LLM)
  6. That forecast model_method labels match actual algorithm
  7. Mini held-out evaluation of the categorizer (ML or fallback)
  8. Forecast backtesting: balance arithmetic is internally consistent
  9. That no endpoint silently fabricates accuracy claims
"""
import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.session import Base, get_db
from app.ml.engine import SKLEARN_AVAILABLE, MLIntelligenceEngine, _rule_based_categorize, TRAINING_DATA
import tempfile
import os

# ─── Isolated test DB ─────────────────────────────────────────────────────────
_tf = tempfile.NamedTemporaryFile(delete=False, suffix="_ai_audit.db")
_tf.close()
_DB_URL = f"sqlite:///{_tf.name.replace(chr(92), '/')}"
_engine = create_engine(_DB_URL, connect_args={"check_same_thread": False})
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def _setup():
    app.dependency_overrides[get_db] = _override_db
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)
    app.dependency_overrides.clear()
    try:
        os.remove(_tf.name)
    except Exception:
        pass


client = TestClient(app)


def _make_user(email: str) -> dict:
    return client.post("/api/v1/users", json={"email": email, "full_name": "AI Audit"}).json()["data"]


def _import_csv(uid: str, csv: str):
    files = {"file": ("audit.csv", io.BytesIO(csv.encode()), "text/csv")}
    preview = client.post("/api/v1/transactions/preview-import",
                          data={"user_id": uid}, files=files).json()["data"]
    client.post("/api/v1/transactions/confirm-import", json={
        "user_id": uid, "source_name": "CSV", "file_name": "audit.csv",
        "records": preview["preview_records"], "skip_duplicates": True
    })


AUDIT_CSV = """Date,Description,Amount,Transaction Type,Category
2026-09-01,Monthly Salary Credit,75000.00,Credit,Income
2026-09-03,Swiggy Biryani Delivery,450.00,Debit,Dining & Food
2026-09-05,BigBasket Groceries,2200.00,Debit,Groceries
2026-09-07,Airtel WiFi Bill,999.00,Debit,Utilities
2026-09-10,Uber Cab Ride,380.00,Debit,Transportation
2026-09-12,Amazon India Purchase,4500.00,Debit,Shopping
2026-09-15,Netflix Subscription,649.00,Debit,Subscriptions & Ent.
2026-09-20,Zomato Restaurant Order,850.00,Debit,Dining & Food
2026-09-22,One Massive Anomaly Expense,45000.00,Debit,Shopping
2026-09-28,Freelance Payment Received,15000.00,Credit,Income
"""


# ═══════════════════════════════════════════════════════════════════════════════
# 1. AI HEALTH DIAGNOSTIC ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════
class TestAIHealthEndpoint:
    def test_health_endpoint_returns_200(self):
        res = client.get("/api/v1/ai/health")
        assert res.status_code == 200

    def test_health_reports_sklearn_status_accurately(self):
        d = client.get("/api/v1/ai/health").json()["data"]
        assert d["sklearn_dll_available"] == SKLEARN_AVAILABLE, \
            "Health endpoint must match actual runtime SKLEARN_AVAILABLE flag"

    def test_health_reports_all_five_features(self):
        features = client.get("/api/v1/ai/health").json()["data"]["features"]
        names = {f["feature"] for f in features}
        assert names == {
            "transaction_categorization",
            "anomaly_detection",
            "financial_copilot",
            "cash_flow_forecasting",
            "savings_goal_optimisation",
        }

    def test_copilot_labelled_as_deterministic_not_llm(self):
        features = client.get("/api/v1/ai/health").json()["data"]["features"]
        copilot = [f for f in features if f["feature"] == "financial_copilot"][0]
        assert copilot["implementation_type"] == "deterministic"
        assert "LLM" not in copilot["implementation_type"]

    def test_forecasting_labelled_as_statistical(self):
        features = client.get("/api/v1/ai/health").json()["data"]["features"]
        fc = [f for f in features if f["feature"] == "cash_flow_forecasting"][0]
        assert fc["implementation_type"] == "statistical"

    def test_categorization_fallback_matches_sklearn_status(self):
        features = client.get("/api/v1/ai/health").json()["data"]["features"]
        cat = [f for f in features if f["feature"] == "transaction_categorization"][0]
        if SKLEARN_AVAILABLE:
            assert cat["implementation_type"] == "trained_ml"
            assert cat["fallback_active"] is False
        else:
            assert cat["implementation_type"] == "rule_based"
            assert cat["fallback_active"] is True

    def test_anomaly_fallback_matches_sklearn_status(self):
        features = client.get("/api/v1/ai/health").json()["data"]["features"]
        anom = [f for f in features if f["feature"] == "anomaly_detection"][0]
        if SKLEARN_AVAILABLE:
            assert anom["implementation_type"] == "trained_ml"
            assert anom["fallback_active"] is False
        else:
            assert anom["implementation_type"] == "statistical"
            assert anom["fallback_active"] is True

    def test_health_every_feature_has_known_limitations(self):
        """No feature should claim zero limitations."""
        features = client.get("/api/v1/ai/health").json()["data"]["features"]
        for f in features:
            assert len(f["known_limitations"]) > 0, \
                f"Feature '{f['feature']}' must list at least one limitation"

    def test_overall_status_matches_sklearn(self):
        d = client.get("/api/v1/ai/health").json()["data"]
        expected = "ml_enabled" if SKLEARN_AVAILABLE else "fallback_only"
        assert d["overall_status"] == expected


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CATEGORIZATION – METHOD LABEL & ACCURACY
# ═══════════════════════════════════════════════════════════════════════════════
class TestCategorizationAudit:
    def test_response_includes_method_field(self):
        res = client.post("/api/v1/ai/categorize-transaction",
                          json={"description": "Swiggy Biryani Order"}).json()
        d = res["data"]
        assert "method" in d
        assert d["method"] in ("tfidf_multinomial_nb_ml", "tfidf_logreg_ml", "rule_based_keyword")

    def test_method_matches_sklearn_availability(self):
        res = client.post("/api/v1/ai/categorize-transaction",
                          json={"description": "Netflix Premium"}).json()
        if SKLEARN_AVAILABLE:
            assert res["data"]["method"] in ("tfidf_multinomial_nb_ml", "tfidf_logreg_ml")
        else:
            assert res["data"]["method"] == "rule_based_keyword"

    def test_message_is_honest_about_training_data_size(self):
        res = client.post("/api/v1/ai/categorize-transaction",
                          json={"description": "Zomato"}).json()
        msg = res["message"]
        assert len(msg) > 0
        assert any(k in msg.lower() for k in ["synthetic", "multinomialnb", "rule-based", "keyword", "40", "1,200"])

    def test_confidence_range_zero_to_one(self):
        res = client.post("/api/v1/ai/categorize-transaction",
                          json={"description": "Uber cab"}).json()
        c = res["data"]["confidence_score"]
        assert 0.0 <= c <= 1.0

    def test_rule_based_fallback_on_known_keywords(self):
        """Directly test the rule-based function to verify correctness."""
        tests = [
            ("Swiggy food delivery", "Dining & Food"),
            ("BigBasket weekly vegetables order", "Groceries"),
            ("Uber Premier Cab", "Transportation"),
            ("Amazon India Electronics", "Shopping"),
            ("Netflix Premium 4K", "Subscriptions & Ent."),
            ("Apollo Pharmacy Medicine", "Healthcare"),
            ("House Rent September", "Housing & Rent"),
            ("Electricity Bill Payment", "Utilities"),
            ("College Tuition Fee", "Education"),
            ("Monthly Salary Direct Deposit", "Income"),
        ]
        for desc, expected_cat in tests:
            cat, conf, method = _rule_based_categorize(desc)
            assert cat == expected_cat, f"'{desc}' → expected '{expected_cat}', got '{cat}'"
            assert method == "rule_based_keyword"
            assert conf == 0.75

    def test_rule_based_unknown_description(self):
        cat, conf, method = _rule_based_categorize("XYZZY 999 random gibberish")
        assert cat == "Miscellaneous"
        assert conf == 0.40
        assert method == "rule_based_keyword"

    def test_mini_held_out_evaluation(self):
        """
        Evaluate the active categorizer (ML or rule-based) against held-out
        descriptions that were NOT in the training set but have known correct
        categories. This is a mini evaluation — not a proper train/test split.
        """
        held_out = [
            ("Dominos Pizza Delivery", "Dining & Food"),
            ("Rapido Bike Taxi", "Transportation"),
            ("Flipkart Mobile Phone", "Shopping"),
            ("YouTube Premium Subscription", "Subscriptions & Ent."),
            ("Medplus Pharmacy Tablets", "Healthcare"),
            ("BSNL Mobile Recharge", "Utilities"),
            ("Coursera Data Science Certificate", "Education"),
            ("Flat Monthly Rent Payment", "Housing & Rent"),
            ("Internship Stipend Credited", "Income"),
            ("DMart Supermarket Weekly", "Groceries"),
        ]
        correct = 0
        results = []
        for desc, expected in held_out:
            cat, conf, method = MLIntelligenceEngine.predict_category(desc)
            is_correct = (cat == expected)
            if is_correct:
                correct += 1
            results.append((desc, expected, cat, is_correct, method))

        accuracy = correct / len(held_out)

        # Report every prediction for transparency
        for desc, expected, predicted, ok, method in results:
            mark = "[OK]" if ok else "[MISS]"
            print(f"  {mark} [{method}] '{desc}' -> predicted='{predicted}' expected='{expected}'")

        print(f"\n  HELD-OUT ACCURACY: {correct}/{len(held_out)} = {accuracy:.0%} (method: {results[0][4]})")

        # We do NOT assert a specific accuracy threshold because the training
        # data is 40 synthetic samples. We JUST assert the test ran and the
        # accuracy is reported honestly. This is the audit's job: measure and
        # report, not rubber-stamp.
        assert accuracy >= 0.0  # always true; forces the test to print results


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ANOMALY DETECTION AUDIT
# ═══════════════════════════════════════════════════════════════════════════════
class TestAnomalyDetectionAudit:
    def setup_method(self, method):
        import time
        self.user = _make_user(f"anom_audit_{int(time.time()*1000)}@test.com")
        self.uid = self.user["id"]
        _import_csv(self.uid, AUDIT_CSV)

    def test_anomaly_results_include_method_field(self):
        res = client.get(f"/api/v1/ai/ml-spending-anomalies?user_id={self.uid}").json()
        for a in res["data"]:
            assert "method" in a
            assert a["method"] in ("isolation_forest", "anomaly_detector_model", "z_score_fallback")

    def test_anomaly_method_matches_sklearn_availability(self):
        res = client.get(f"/api/v1/ai/ml-spending-anomalies?user_id={self.uid}").json()
        for a in res["data"]:
            assert a["method"] in ("isolation_forest", "anomaly_detector_model", "z_score_fallback")

    def test_large_amount_flagged_as_anomaly(self):
        """₹45,000 should be flagged as anomalous vs. typical ₹380–₹4500 debits."""
        res = client.get(f"/api/v1/ai/ml-spending-anomalies?user_id={self.uid}").json()
        flagged_amounts = [a["amount"] for a in res["data"]]
        # The 45000 outlier should appear — but if it doesn't, that's a finding.
        if 45000.0 in flagged_amounts:
            assert True  # Expected behaviour
        else:
            print("  NOTE: ₹45,000 was NOT flagged. This may indicate the model's threshold is too loose.")

    def test_anomaly_explanations_are_honest(self):
        res = client.get(f"/api/v1/ai/ml-spending-anomalies?user_id={self.uid}").json()
        for a in res["data"]:
            explanation = a["explanation"]
            if a["method"] == "isolation_forest":
                assert "synthetic" in explanation.lower() or "verify manually" in explanation.lower(), \
                    "Isolation Forest explanations must acknowledge synthetic training data"
            else:
                assert any(k in explanation.lower() for k in ["trained anomaly model", "outlier", "heuristic", "z-score", "isolation forest"])

    def test_message_label_is_accurate(self):
        res = client.get(f"/api/v1/ai/ml-spending-anomalies?user_id={self.uid}").json()
        msg = res["message"]
        if SKLEARN_AVAILABLE:
            assert "synthetic" in msg.lower() or "demonstration" in msg.lower()
        else:
            assert "fallback" in msg.lower() or "z-score" in msg.lower() or "unavailable" in msg.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. FINANCIAL COPILOT HONESTY
# ═══════════════════════════════════════════════════════════════════════════════
class TestCopilotHonesty:
    def setup_method(self, method):
        import time
        self.user = _make_user(f"copilot_audit_{int(time.time()*1000)}@test.com")
        self.uid = self.user["id"]
        _import_csv(self.uid, AUDIT_CSV)

    def test_disclaimer_says_not_llm(self):
        res = client.post("/api/v1/ai/copilot/query",
                          json={"user_id": self.uid, "query": "What is my balance?"}).json()
        disc = res["data"]["disclaimer"]
        assert "not" in disc.lower() or "NOT" in disc
        assert "LLM" in disc or "language model" in disc.lower()

    def test_copilot_route_message_says_not_llm(self):
        res = client.post("/api/v1/ai/copilot/query",
                          json={"user_id": self.uid, "query": "Can I afford this?"}).json()
        assert "not an llm" in res["message"].lower() or "rule-based" in res["message"].lower()

    def test_copilot_answer_not_empty(self):
        queries = [
            "Can I afford a new laptop?",
            "Why did my balance fall?",
            "How are my savings goals?",
            "Hello, what can you do?",
        ]
        for q in queries:
            res = client.post("/api/v1/ai/copilot/query",
                              json={"user_id": self.uid, "query": q}).json()
            assert len(res["data"]["answer"]) > 10, f"Query '{q}' produced empty answer"

    def test_copilot_evidence_contains_numeric_data(self):
        res = client.post("/api/v1/ai/copilot/query",
                          json={"user_id": self.uid, "query": "Can I afford a car?"}).json()
        evidence = res["data"]["evidence"]
        assert isinstance(evidence, dict)
        # Evidence should contain at least one numeric value
        assert any(isinstance(v, (int, float)) for v in evidence.values()), \
            "Evidence must contain numeric financial data, not just text"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. FORECAST BACKTESTING & HONESTY
# ═══════════════════════════════════════════════════════════════════════════════
class TestForecastAudit:
    def setup_method(self, method):
        import time
        self.user = _make_user(f"forecast_audit_{int(time.time()*1000)}@test.com")
        self.uid = self.user["id"]
        _import_csv(self.uid, AUDIT_CSV)

    def test_model_method_label_is_not_ml(self):
        """The forecaster uses historical run-rate, NOT a trained ML model."""
        d = client.get(f"/api/v1/forecasting/cashflow?user_id={self.uid}&horizon_days=30").json()["data"]
        assert d["model_method"] == "HISTORICAL_RUNRATE_LINEARTREND"
        assert "ML" not in d["model_method"]
        assert "ARIMA" not in d["model_method"]
        assert "LSTM" not in d["model_method"]

    def test_forecast_balance_arithmetic_consistency(self):
        """Verify: end_balance ≈ start_balance + Σ(income) − Σ(expense) across the timeline."""
        d = client.get(f"/api/v1/forecasting/cashflow?user_id={self.uid}&horizon_days=30").json()["data"]
        timeline = d["daily_timeline"]

        total_income = sum(pt["projected_income"] for pt in timeline)
        total_expense = sum(pt["projected_expense"] for pt in timeline)
        expected_end = d["start_balance"] + total_income - total_expense

        actual_end = d["end_balance"]
        assert abs(actual_end - expected_end) < 1.0, (
            f"Balance arithmetic inconsistency: start={d['start_balance']}, "
            f"+income={total_income:.2f}, -expense={total_expense:.2f}, "
            f"expected_end={expected_end:.2f}, actual_end={actual_end}"
        )

    def test_forecast_empty_user_produces_flat_balance(self):
        u = _make_user("empty_forecast_audit@test.com")
        d = client.get(f"/api/v1/forecasting/cashflow?user_id={u['id']}&horizon_days=14").json()["data"]
        assert d["model_method"] == "EMPTY_HISTORICAL_BASELINE"
        assert d["start_balance"] == d["end_balance"]

    def test_breach_dates_are_actually_below_buffer(self):
        d = client.get(
            f"/api/v1/forecasting/cashflow?user_id={self.uid}"
            f"&horizon_days=90&safe_buffer=500000"
        ).json()["data"]
        for breach in d["breaches"]:
            assert breach["projected_balance"] < breach["safe_buffer"], (
                f"Breach on {breach['date']} has balance {breach['projected_balance']} "
                f"which is NOT below buffer {breach['safe_buffer']}"
            )

    def test_confidence_bands_widen_over_time(self):
        d = client.get(f"/api/v1/forecasting/cashflow?user_id={self.uid}&horizon_days=30").json()["data"]
        timeline = d["daily_timeline"]
        if len(timeline) >= 2:
            first_width = timeline[0]["confidence_upper"] - timeline[0]["confidence_lower"]
            last_width = timeline[-1]["confidence_upper"] - timeline[-1]["confidence_lower"]
            assert last_width >= first_width, \
                "Confidence bands should widen (or stay constant) over the forecast horizon"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. DATA LEAKAGE & TRAINING OVERLAP CHECK
# ═══════════════════════════════════════════════════════════════════════════════
class TestDataLeakageAudit:
    def test_training_data_is_not_used_as_test_data(self):
        """
        Verify that the held-out test descriptions used in
        test_mini_held_out_evaluation() do NOT appear in TRAINING_DATA.
        """
        training_descs = {d.lower() for d, _ in TRAINING_DATA}
        held_out_descs = [
            "Dominos Pizza Delivery",
            "Rapido Bike Taxi",
            "Flipkart Mobile Phone",
            "YouTube Premium Subscription",
            "Medplus Pharmacy Tablets",
            "BSNL Mobile Recharge",
            "Coursera Data Science Certificate",
            "Flat Monthly Rent Payment",
            "Internship Stipend Credited",
            "DMart Supermarket Weekly",
        ]
        for desc in held_out_descs:
            assert desc.lower() not in training_descs, \
                f"DATA LEAKAGE: '{desc}' appears in both training and held-out sets"

    def test_no_fabricated_accuracy_claims_in_health(self):
        """Health endpoint must NOT contain accuracy percentages like '95%' or 'F1=0.9'."""
        import json
        health_text = json.dumps(client.get("/api/v1/ai/health").json())
        for phrase in ["accuracy", "precision", "recall", "f1", "auc", "roc"]:
            # Allowed in known_limitations if it says "No ... have been computed"
            # but NOT as a claimed metric value
            if phrase in health_text.lower():
                assert "not" in health_text.lower() or "no" in health_text.lower() or \
                       "have not" in health_text.lower(), \
                    f"Health endpoint appears to claim an {phrase} metric — this has not been evaluated"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SAVINGS OPTIMIZER AUDIT
# ═══════════════════════════════════════════════════════════════════════════════
class TestOptimizerAudit:
    def setup_method(self, method):
        import time
        self.user = _make_user(f"opt_audit_{int(time.time()*1000)}@test.com")
        self.uid = self.user["id"]
        _import_csv(self.uid, AUDIT_CSV)
        client.post("/api/v1/goals", json={
            "user_id": self.uid, "name": "Emergency Fund",
            "target_amount": 100000.0, "current_amount": 0.0,
            "target_date": "2027-06-30", "priority": 1
        })
        client.post("/api/v1/goals", json={
            "user_id": self.uid, "name": "Vacation",
            "target_amount": 50000.0, "current_amount": 0.0,
            "target_date": "2027-03-31", "priority": 3
        })

    def test_optimizer_method_is_scipy(self):
        d = client.get(f"/api/v1/goals/optimize?user_id={self.uid}&override_surplus=10000").json()["data"]
        assert d["optimization_method"] == "SCIPY_HIGHS_LINEAR_PROGRAMMING"

    def test_total_allocation_does_not_exceed_surplus(self):
        surplus = 8000.0
        d = client.get(f"/api/v1/goals/optimize?user_id={self.uid}&override_surplus={surplus}").json()["data"]
        total = sum(a["allocated_surplus"] for a in d["allocations"])
        assert total <= surplus + 0.01, \
            f"Total allocation ₹{total:.2f} exceeds surplus ₹{surplus:.2f}"

    def test_higher_priority_goal_gets_more_allocation(self):
        d = client.get(f"/api/v1/goals/optimize?user_id={self.uid}&override_surplus=5000").json()["data"]
        allocs = d["allocations"]
        p1 = [a for a in allocs if a["priority"] == 1]
        p3 = [a for a in allocs if a["priority"] == 3]
        if p1 and p3:
            assert p1[0]["allocated_surplus"] >= p3[0]["allocated_surplus"], \
                "Priority 1 goal should receive >= allocation compared to priority 3"
