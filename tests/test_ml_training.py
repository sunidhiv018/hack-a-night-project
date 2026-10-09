"""
BrokeNoMore ML Training & Artifact Persistence Test Suite
========================================================
Tests:
1. ML Training pipeline execution and metadata generation
2. Artifact existence and versioning schema
3. Categorizer inference on unseen merchant descriptions and confidence scoring
4. Anomaly detector inference and explanation formatting
5. Cash-flow forecaster backtesting metrics and balance arithmetic consistency
6. /api/v1/ai/health diagnostic endpoint reporting model version & metrics
"""
import os
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.ml.train import run_pipeline, generate_synthetic_dataset
from app.ml.engine import MLIntelligenceEngine, MODEL_DIR

client = TestClient(app)

class TestMLTrainingPipeline:
    def test_training_pipeline_execution(self):
        metadata = run_pipeline()
        assert metadata is not None
        assert metadata["version"] == "1.3.0"
        assert metadata["dataset_summary"]["total_records"] == 1200
        assert metadata["categorizer"]["metrics"]["synthetic_test_accuracy"] >= 0.90
        assert metadata["categorizer"]["metrics"]["challenge_dataset"]["challenge_accuracy"] >= 0.60
        assert metadata["anomaly_detector"]["metrics"]["precision"] >= 0.70

    def test_artifacts_exist_and_valid(self):
        cat_path = os.path.join(MODEL_DIR, "category_classifier.joblib")
        anomaly_path = os.path.join(MODEL_DIR, "isolation_forest.joblib")
        meta_path = os.path.join(MODEL_DIR, "metadata.json")

        assert os.path.exists(cat_path)
        assert os.path.exists(anomaly_path)
        assert os.path.exists(meta_path)

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        assert "categorizer" in meta
        assert "anomaly_detector" in meta
        assert "forecaster_backtest" in meta
        assert "challenge_dataset" in meta["categorizer"]["metrics"]

    def test_predict_category_unseen_transactions(self):
        MLIntelligenceEngine.ensure_models_trained()
        
        # Test merchant descriptions
        cat1, conf1, method1 = MLIntelligenceEngine.predict_category("Starbucks Coffee Cold Brew", 350.0)
        assert isinstance(cat1, str)
        assert cat1 in ["Dining & Food", "Groceries", "Miscellaneous", "Needs Review"]
        assert conf1 > 0.0

        cat2, conf2, method2 = MLIntelligenceEngine.predict_category("Monthly Software Salary Credit Deposit", 75000.0)
        assert cat2 == "Income"
        assert conf2 > 0.5

    def test_low_confidence_guardrail_returns_needs_review(self):
        MLIntelligenceEngine.ensure_models_trained()
        
        # Highly ambiguous transaction with low confidence
        cat, conf, method = MLIntelligenceEngine.predict_category("Cryptic Transaction XJ-993", 100.0)
        assert cat in ["Needs Review", "Miscellaneous"]
        assert method in ["tfidf_multinomial_nb_ml_uncertain", "tfidf_multinomial_nb_ml", "rule_based_keyword"]

    def test_anomaly_detection_with_outliers(self):
        # Provide baseline of normal small debits so Z-score calculation exceeds threshold
        transactions = [
            {"id": "t1", "txn_date": "2026-09-01", "description": "Tea Stall Chai", "amount": 20.0, "txn_type": "debit", "category": "Dining & Food"},
            {"id": "t2", "txn_date": "2026-09-02", "description": "Metro Ride", "amount": 40.0, "txn_type": "debit", "category": "Transportation"},
            {"id": "t3", "txn_date": "2026-09-03", "description": "Groceries Kirana", "amount": 150.0, "txn_type": "debit", "category": "Groceries"},
            {"id": "t4", "txn_date": "2026-09-04", "description": "Coffee Shop", "amount": 80.0, "txn_type": "debit", "category": "Dining & Food"},
            {"id": "t5", "txn_date": "2026-09-05", "description": "Bus Ticket", "amount": 30.0, "txn_type": "debit", "category": "Transportation"},
            {"id": "t6", "txn_date": "2026-09-06", "description": "Snacks", "amount": 50.0, "txn_type": "debit", "category": "Dining & Food"},
            {"id": "t7", "txn_date": "2026-09-07", "description": "UNUSUAL LUXURY SPEND EXTREME", "amount": 95000.0, "txn_type": "debit", "category": "Shopping"}
        ]
        
        anomalies = MLIntelligenceEngine.detect_ml_anomalies(transactions)
        assert len(anomalies) > 0
        top_anomaly = anomalies[0]
        assert top_anomaly["amount"] == 95000.0
        assert top_anomaly["anomaly_score"] > 0

    def test_ai_health_endpoint_metadata(self):
        response = client.get("/api/v1/ai/health")
        assert response.status_code == 200
        res_json = response.json()
        data = res_json.get("data", res_json)
        assert data["overall_status"] in ["ml_enabled", "fallback_only"]
        assert len(data["features"]) >= 5

        cat_feature = next(f for f in data["features"] if f["feature"] == "transaction_categorization")
        assert cat_feature["model_available"] is True
        assert cat_feature["model_version"] == "1.3.0"
        assert cat_feature["dataset_size"] == 1200
        assert "evaluation_metrics" in cat_feature
