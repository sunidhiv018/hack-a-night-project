import re
from datetime import date
from typing import Dict, Any, Optional, Tuple

def parse_gpay_notification(
    text: str,
    title: Optional[str] = "",
    package_name: Optional[str] = "com.google.android.apps.nfc.plugin.card.gp"
) -> Dict[str, Any]:
    """
    Deterministic & robust parser for Google Pay (GPay) Android notification content.
    Extracts amount, direction, merchant/counterparty, reference number, and confidence score.
    Rejects failed payments, pending requests, reminders, OTPs, and non-GPay packages.
    """
    text_clean = text.strip()
    title_clean = (title or "").strip()
    full_content = f"{title_clean} {text_clean}".strip()
    full_lower = full_content.lower()

    # 1. Package verification guardrail
    allowed_packages = [
        "com.google.android.apps.nfc.plugin.card.gp",
        "com.google.android.apps.walletnfcrel",
        "com.google.android.apps.pay.moneta",
        "com.gpay.autosync.test"
    ]
    if package_name and package_name not in allowed_packages:
        return {
            "is_valid": False,
            "status": "REJECTED_PACKAGE",
            "reason": f"Package '{package_name}' is not verified Google Pay application",
            "confidence": 0.0
        }

    # 2. Reject Failed, Pending, Request, OTP, or Security Notifications
    rejection_keywords = [
        "failed", "declined", "unsuccessful", "request", "requested", "reminding",
        "reminder", "otp", "code", "pin", "password", "security alert", "update available",
        "pending approval", "could not process"
    ]
    for rk in rejection_keywords:
        if rk in full_lower:
            return {
                "is_valid": False,
                "status": "REJECTED_NON_SETTLED",
                "reason": f"Notification represents pending/failed/request state: '{rk}'",
                "confidence": 0.0
            }

    # 3. Extract Amount (Supports Indian Rs., INR, ₹, comma-separated e.g. 1,450.50)
    amt_match = re.search(r'(?:paid|sent|received|credited|debited|got|rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)', full_content, re.IGNORECASE)
    if not amt_match:
        # Fallback search for bare currency format
        amt_match = re.search(r'(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)', full_content, re.IGNORECASE)

    amount = None
    if amt_match:
        try:
            raw_amt = amt_match.group(1).replace(',', '')
            amount = float(raw_amt)
        except ValueError:
            amount = None

    if amount is None or amount <= 0:
        return {
            "is_valid": False,
            "status": "AMBIGUOUS_AMOUNT",
            "reason": "Could not parse valid positive transaction amount",
            "confidence": 0.2
        }

    # 4. Extract Debit vs Credit Direction
    txn_type = "debit"
    if any(k in full_lower for k in ["received", "credited", "got", "received from", "added"]):
        txn_type = "credit"
    elif any(k in full_lower for k in ["paid", "sent", "debited", "transferred to", "spent"]):
        txn_type = "debit"

    # 5. Extract Reference / UTR Number
    ref_match = re.search(r'(?:ref|utr|txn id|reference|id)\s*[:\.]?\s*([A-Za-z0-9]{8,18})', full_content, re.IGNORECASE)
    ref_number = ref_match.group(1).strip() if ref_match else None

    # 6. Extract Merchant / Counterparty Description
    merchant = "GPay Merchant"
    # Patterns: "Paid Rs 450 to Swiggy", "Received Rs 1200 from Aarav", "Paid at Star Cafe"
    m_match = re.search(r'(?:paid|sent|transferred|credited|received)\s+(?:rs\.?|inr|₹)?\s*[\d,]+(?:\.\d+)?\s+(?:to|from|at)\s+([A-Za-z0-9\s&\'\.\-]+?)(?:\s+using|\s+ref|\s+on|\.|$)', full_content, re.IGNORECASE)
    if m_match:
        merchant = m_match.group(1).strip()
    else:
        # Secondary fallback pattern: "to Merchant" or "from Person"
        m_match2 = re.search(r'(?:to|from|at)\s+([A-Za-z0-9\s&\'\.\-]+?)(?:\s+using|\s+ref|\s+on|\.|$)', full_content, re.IGNORECASE)
        if m_match2:
            merchant = m_match2.group(1).strip()

    # Clean up merchant name trailing strings
    merchant = re.sub(r'\s+(using|gpay|google pay|via|ref).*$', '', merchant, flags=re.IGNORECASE).strip()
    if not merchant or len(merchant) < 2:
        merchant = "Google Pay Transaction"

    # 7. Confidence Score Calculation
    confidence = 0.5
    if amount > 0:
        confidence += 0.2
    if merchant and merchant != "Google Pay Transaction":
        confidence += 0.2
    if ref_number:
        confidence += 0.1

    is_high_confidence = confidence >= 0.8

    return {
        "is_valid": True,
        "status": "SUCCESS" if is_high_confidence else "AMBIGUOUS",
        "amount": amount,
        "txn_type": txn_type,
        "description": f"{merchant} (GPay)",
        "merchant_raw": merchant,
        "ref_number": ref_number,
        "confidence": round(confidence, 2),
        "is_high_confidence": is_high_confidence
    }
