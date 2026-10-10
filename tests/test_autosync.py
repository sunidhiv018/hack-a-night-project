import pytest
from app.services.gpay_parser import parse_gpay_notification
from app.repositories.domain_repo import compute_raw_hash

class TestGPayParserAndAutoSyncSuite:
    """Comprehensive test suite for Milo AutoSync GPay parser, guardrails, and idempotency."""

    def test_successful_outgoing_gpay_payment(self):
        res = parse_gpay_notification(
            text="Paid Rs 450.00 to Swiggy using Google Pay. Ref 429104821094",
            title="Google Pay",
            package_name="com.google.android.apps.nfc.plugin.card.gp"
        )
        assert res["is_valid"] is True
        assert res["amount"] == 450.0
        assert res["txn_type"] == "debit"
        assert "Swiggy" in res["description"]
        assert res["ref_number"] == "429104821094"
        assert res["is_high_confidence"] is True

    def test_incoming_gpay_transfer(self):
        res = parse_gpay_notification(
            text="Received Rs 2,500.00 from Aarav Sharma on Google Pay. Ref 9948120481",
            title="Google Pay",
            package_name="com.google.android.apps.nfc.plugin.card.gp"
        )
        assert res["is_valid"] is True
        assert res["amount"] == 2500.0
        assert res["txn_type"] == "credit"
        assert "Aarav Sharma" in res["description"]

    def test_unverified_package_rejection_guardrail(self):
        res = parse_gpay_notification(
            text="Paid Rs 500.00 to Merchant",
            title="Malicious App",
            package_name="com.unverified.fakeapp"
        )
        assert res["is_valid"] is False
        assert res["status"] == "REJECTED_PACKAGE"

    def test_reject_failed_payment_notification(self):
        res = parse_gpay_notification(
            text="Payment of Rs 1,200 to Flipkart failed due to server error.",
            title="Google Pay",
            package_name="com.google.android.apps.nfc.plugin.card.gp"
        )
        assert res["is_valid"] is False
        assert res["status"] == "REJECTED_NON_SETTLED"

    def test_reject_pending_payment_request(self):
        res = parse_gpay_notification(
            text="Swiggy has requested Rs 350.00 from you.",
            title="Google Pay",
            package_name="com.google.android.apps.nfc.plugin.card.gp"
        )
        assert res["is_valid"] is False
        assert res["status"] == "REJECTED_NON_SETTLED"

    def test_indian_comma_number_format(self):
        res = parse_gpay_notification(
            text="Paid Rs 1,45,000.50 to HDFC Home Loan using Google Pay.",
            title="Google Pay",
            package_name="com.google.android.apps.nfc.plugin.card.gp"
        )
        assert res["is_valid"] is True
        assert res["amount"] == 145000.50

    def test_idempotent_hash_consistency(self):
        hash1 = compute_raw_hash("2026-10-10", "Swiggy (GPay)", 450.0, "debit")
        hash2 = compute_raw_hash("2026-10-10", "Swiggy (GPay)", 450.0, "debit")
        assert hash1 == hash2
