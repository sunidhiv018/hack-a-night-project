import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Float, DateTime, Date, Boolean, Text, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

class TransactionType(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("SavingsGoal", back_populates="user", cascade="all, delete-orphan")
    import_receipts = relationship("PrivacyReceipt", back_populates="user", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    txn_date = Column(Date, nullable=False, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    txn_type = Column(String, nullable=False) # debit / credit
    category = Column(String, nullable=False, index=True, default="Uncategorized")
    source = Column(String, nullable=False, default="CSV_IMPORT") # CSV_IMPORT, EXCEL_IMPORT, BANK_CONNECTOR
    raw_hash = Column(String, nullable=False, index=True) # for duplicate detection
    import_batch_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")

class SavingsGoal(Base):
    __tablename__ = "savings_goals"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    target_date = Column(Date, nullable=False)
    priority = Column(Integer, default=1) # 1 = Highest
    category = Column(String, default="General")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="goals")

class PrivacyReceipt(Base):
    __tablename__ = "privacy_receipts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    source_name = Column(String, nullable=False) # e.g. HDFC_CSV, SBI_EXCEL, MOCK_UPI
    file_name = Column(String, nullable=True)
    records_processed = Column(Integer, default=0)
    records_imported = Column(Integer, default=0)
    duplicates_skipped = Column(Integer, default=0)
    import_timestamp = Column(DateTime, default=datetime.utcnow)
    data_scope = Column(String, default="TRANSACTION_HISTORY_READ_ONLY")
    data_retention = Column(String, default="LOCAL_TENANT_ISOLATED")

    user = relationship("User", back_populates="import_receipts")
