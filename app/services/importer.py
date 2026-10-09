import io
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Tuple, Optional
from app.repositories.domain_repo import compute_raw_hash, TransactionRepository
from app.schemas.schemas import PreviewItem, ImportPreviewResponse, ImportConfirmRequest, ImportSummaryResponse, TransactionCreate
from app.repositories.domain_repo import PrivacyReceiptRepository
from app.models.domain import User
from sqlalchemy.orm import Session
from fastapi import HTTPException
import uuid

# Maximum file size limit: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024

def categorize_description(desc: str) -> str:
    d = desc.lower()
    if any(k in d for k in ["salary", "payroll", "stipend", "interest credit", "refund", "cashback"]):
        return "Income"
    elif any(k in d for k in ["swiggy", "zomato", "restaurant", "cafe", "food", "mcdonalds", "starbucks"]):
        return "Dining & Food"
    elif any(k in d for k in ["supermarket", "grocery", "blinkit", "zepto", "bigbasket", "mart"]):
        return "Groceries"
    elif any(k in d for k in ["rent", "landlord", "housing"]):
        return "Housing & Rent"
    elif any(k in d for k in ["electricity", "water", "wifi", "internet", "recharge", "utility", "bill"]):
        return "Utilities"
    elif any(k in d for k in ["uber", "ola", "metro", "fuel", "petrol", "cab", "transport"]):
        return "Transportation"
    elif any(k in d for k in ["amazon", "flipkart", "myntra", "zara", "shopping", "store"]):
        return "Shopping"
    elif any(k in d for k in ["netflix", "spotify", "prime", "cinema", "movie"]):
        return "Subscriptions & Ent."
    elif any(k in d for k in ["hospital", "pharmacy", "doctor", "medical", "apollo"]):
        return "Healthcare"
    return "Miscellaneous"

class TransactionImporter:
    @staticmethod
    def detect_and_normalize_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        original_cols = [str(c) for c in df.columns]
        col_map = {}
        for c in df.columns:
            clow = str(c).strip().lower()
            if any(k in clow for k in ["date", "txn_date", "timestamp"]):
                col_map[c] = "txn_date"
            elif any(k in clow for k in ["desc", "description", "narration", "particulars", "remarks"]):
                col_map[c] = "description"
            elif clow in ["amount", "txn_amount", "val", "value"]:
                col_map[c] = "amount"
            elif clow in ["debit", "dr", "withdrawal", "debit_amount"]:
                col_map[c] = "debit"
            elif clow in ["credit", "cr", "deposit", "credit_amount"]:
                col_map[c] = "credit"
            elif clow in ["type", "txn_type", "transaction_type"] or \
                    ("type" in clow and ("txn" in clow or "transaction" in clow)):
                col_map[c] = "txn_type"
            elif clow in ["category", "cat"]:
                col_map[c] = "category"

        df = df.rename(columns=col_map)
        return df, original_cols

    @classmethod
    def parse_file_to_preview(cls, file_bytes: bytes, filename: str, user_id: str, db: Session) -> ImportPreviewResponse:
        # Check User Existence
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check File Size Limit
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File size exceeds maximum allowed limit of 10 MB")

        if len(file_bytes) == 0:
            return ImportPreviewResponse(
                total_rows=0, valid_rows=0, duplicate_rows=0, new_rows=0, preview_records=[], detected_columns=[]
            )

        is_excel = filename.endswith(".xlsx") or filename.endswith(".xls")
        try:
            if is_excel:
                df = pd.read_excel(io.BytesIO(file_bytes))
            else:
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
                except Exception:
                    df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin1")
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed file format. Unable to parse spreadsheet.")

        if df.empty:
            return ImportPreviewResponse(
                total_rows=0, valid_rows=0, duplicate_rows=0, new_rows=0, preview_records=[], detected_columns=[]
            )

        df, detected_cols = cls.detect_and_normalize_columns(df)

        preview_items: List[PreviewItem] = []
        txn_repo = TransactionRepository(db)

        existing_txns = txn_repo.get_by_user(user_id, limit=5000)
        existing_hash_map = {t.raw_hash: t.id for t in existing_txns}

        valid_count = 0
        dup_count = 0

        for _, row in df.iterrows():
            try:
                raw_date = row.get("txn_date")
                if pd.isna(raw_date):
                    continue
                parsed_date = pd.to_datetime(raw_date).date()

                desc = str(row.get("description", "Imported Transaction")).strip()

                amount = 0.0
                txn_type = "debit"

                if "debit" in row and "credit" in row:
                    dr = row.get("debit")
                    cr = row.get("credit")
                    if pd.notna(dr) and float(dr) > 0:
                        amount = float(dr)
                        txn_type = "debit"
                    elif pd.notna(cr) and float(cr) > 0:
                        amount = float(cr)
                        txn_type = "credit"
                    else:
                        continue
                elif "amount" in row:
                    amt_val = float(row.get("amount", 0))
                    if amt_val < 0:
                        amount = abs(amt_val)
                        txn_type = "debit"
                    else:
                        amount = amt_val
                        raw_type = str(row.get("txn_type", "debit")).lower()
                        txn_type = "credit" if "credit" in raw_type or "cr" in raw_type else "debit"
                else:
                    continue

                if amount <= 0:
                    continue

                cat = str(row.get("category", "")).strip()
                if not cat or cat.lower() == "nan" or cat.lower() == "uncategorized":
                    cat = categorize_description(desc)

                r_hash = compute_raw_hash(str(parsed_date), desc, amount, txn_type)
                is_dup = r_hash in existing_hash_map
                dup_of_id = existing_hash_map.get(r_hash)

                if is_dup:
                    dup_count += 1
                else:
                    valid_count += 1

                preview_items.append(
                    PreviewItem(
                        txn_date=parsed_date,
                        description=desc,
                        amount=amount,
                        txn_type=txn_type,
                        category=cat,
                        raw_hash=r_hash,
                        is_duplicate=is_dup,
                        duplicate_of_id=dup_of_id
                    )
                )

            except Exception:
                continue

        return ImportPreviewResponse(
            total_rows=len(df),
            valid_rows=valid_count,
            duplicate_rows=dup_count,
            new_rows=valid_count,
            preview_records=preview_items,
            detected_columns=detected_cols
        )

    @classmethod
    def confirm_and_save(cls, req: ImportConfirmRequest, db: Session) -> ImportSummaryResponse:
        user = db.query(User).filter(User.id == req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        txn_repo = TransactionRepository(db)
        receipt_repo = PrivacyReceiptRepository(db)
        batch_id = str(uuid.uuid4())

        txns_to_create: List[TransactionCreate] = []
        hashes: List[str] = []
        skipped_dups = 0

        for item in req.records:
            if req.skip_duplicates and item.is_duplicate:
                skipped_dups += 1
                continue

            txns_to_create.append(
                TransactionCreate(
                    user_id=req.user_id,
                    txn_date=item.txn_date,
                    description=item.description,
                    amount=item.amount,
                    txn_type=item.txn_type,
                    category=item.category,
                    source=req.source_name
                )
            )
            hashes.append(item.raw_hash)

        saved = txn_repo.bulk_create(txns_to_create, hashes, import_batch_id=batch_id)

        receipt = receipt_repo.create(
            user_id=req.user_id,
            source_name=req.source_name,
            file_name=req.file_name,
            processed=len(req.records),
            imported=len(saved),
            duplicates=skipped_dups
        )

        return ImportSummaryResponse(
            receipt_id=receipt.id,
            source_name=receipt.source_name,
            file_name=receipt.file_name or "N/A",
            records_processed=receipt.records_processed,
            records_imported=receipt.records_imported,
            duplicates_skipped=receipt.duplicates_skipped,
            import_timestamp=receipt.import_timestamp
        )
