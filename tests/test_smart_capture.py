import pytest
from fastapi.testclient import TestClient
from app.main import app
from datetime import date

client = TestClient(app)

class TestSmartCapture:
    @classmethod
    def setup_class(cls):
        # Create a test user
        res = client.post("/api/v1/users", json={"email": "smart_capture_tester@example.com", "full_name": "Smart Capture Tester"})
        cls.user_id = res.json()["data"]["id"]

    def setup_method(self):
        # Clear transactions before each test method for test isolation
        client.delete(f"/api/v1/transactions/clear?user_id={self.user_id}")

    def test_smart_capture_sync_and_demo_isolation(self):
        # 1. Sync a batch of events: one demo event and one real event
        payload = {
            "user_id": self.user_id,
            "events": [
                {
                    "raw_text": "Paid Rs. 350.00 at Swiggy on 10-Oct-2026. Ref: 9812739",
                    "source_app": "com.phonepe.app",
                    "amount": 350.0,
                    "merchant": "Swiggy",
                    "txn_type": "debit",
                    "is_demo": True
                },
                {
                    "raw_text": "Rs. 1,200.00 debited from HDFC Bank at Shell Petrol on 10-Oct-2026",
                    "source_app": "com.google.android.apps.nbu.paisa.user",
                    "amount": 1200.0,
                    "merchant": "Shell Petrol",
                    "txn_type": "debit",
                    "is_demo": False
                }
            ],
            "auto_approve_high_confidence": False
        }

        response = client.post("/api/v1/smart-capture/sync", json=payload)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_received"] == 2
        assert data["demo_count"] == 1
        assert len(data["items"]) == 2

        demo_item = next(it for it in data["items"] if it["is_demo"])
        assert demo_item["status"] == "demo_staged"

        # Check ledger: nothing should be committed to real ledger yet
        txns_res = client.get(f"/api/v1/transactions?user_id={self.user_id}")
        txns = txns_res.json()["data"]
        assert len(txns) == 0, "Neither demo nor unapproved transactions should be silently in ledger"

    def test_smart_capture_duplicate_detection(self):
        # Send two identical events in the same sync batch
        payload = {
            "user_id": self.user_id,
            "events": [
                {
                    "raw_text": "Paid Rs 500 at Starbucks",
                    "amount": 500.0,
                    "merchant": "Starbucks Coffee",
                    "txn_type": "debit",
                    "is_demo": False,
                    "raw_hash": "starbucks_test_hash_unique"
                },
                {
                    "raw_text": "Paid Rs 500 at Starbucks",
                    "amount": 500.0,
                    "merchant": "Starbucks Coffee",
                    "txn_type": "debit",
                    "is_demo": False,
                    "raw_hash": "starbucks_test_hash_unique"
                }
            ]
        }
        response = client.post("/api/v1/smart-capture/sync", json=payload)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["duplicate_count"] == 1
        assert data["items"][1]["is_duplicate"] is True

    def test_smart_capture_approve_with_demo_protection(self):
        # Attempt to approve both a demo item and a real item
        approve_payload = {
            "user_id": self.user_id,
            "items": [
                {
                    "id": "item_demo_1",
                    "raw_text": "Demo simulation: Rs 99 at Netflix",
                    "source_app": "DEMO_SIMULATOR",
                    "txn_date": str(date.today()),
                    "description": "Netflix Subscription",
                    "amount": 99.0,
                    "txn_type": "debit",
                    "category": "Entertainment",
                    "confidence_score": 0.99,
                    "is_duplicate": False,
                    "is_demo": True,
                    "raw_hash": "hash_demo_isolated_1",
                    "status": "demo_staged"
                },
                {
                    "id": "item_real_1",
                    "raw_text": "Rs. 2500 debited at Reliance Smart",
                    "source_app": "HDFC_SMS",
                    "txn_date": str(date.today()),
                    "description": "Reliance Smart Supermarket",
                    "amount": 2500.0,
                    "txn_type": "debit",
                    "category": "Groceries",
                    "confidence_score": 0.92,
                    "is_duplicate": False,
                    "is_demo": False,
                    "raw_hash": "hash_real_supermarket_1",
                    "status": "pending_review"
                }
            ]
        }
        res = client.post("/api/v1/smart-capture/approve", json=approve_payload)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["approved_count"] == 1
        assert data["skipped_demo_count"] == 1, "Demo item must be skipped from entering real ledger"
        assert len(data["saved_transactions"]) == 1
        assert data["saved_transactions"][0]["description"] == "Reliance Smart Supermarket"

        # Verify real ledger has exactly the 1 real transaction
        txns_res = client.get(f"/api/v1/transactions?user_id={self.user_id}")
        txns = txns_res.json()["data"]
        assert len(txns) == 1
        assert txns[0]["description"] == "Reliance Smart Supermarket"

    def test_smart_capture_parse_endpoint(self):
        text = "Rs. 450.00 debited from a/c XX8219 at Swiggy on 09-Oct-2026."
        res = client.post(f"/api/v1/smart-capture/parse?user_id={self.user_id}&text={text}")
        assert res.status_code == 200
        item = res.json()["data"]
        assert item["amount"] == 450.0
        assert "Swiggy" in item["description"]
        assert item["txn_type"] == "debit"
        assert item["confidence_score"] > 0.5
