import hashlib
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.domain import User, Transaction, SavingsGoal, PrivacyReceipt
from app.schemas.schemas import UserCreate, TransactionCreate, GoalCreate

def compute_raw_hash(txn_date: str, description: str, amount: float, txn_type: str) -> str:
    raw_str = f"{str(txn_date).strip()}|{description.strip().lower()}|{float(amount):.2f}|{txn_type.strip().lower()}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, user_in: UserCreate) -> User:
        user = User(email=user_in.email, full_name=user_in.full_name)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

class TransactionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user(self, user_id: str, limit: int = 500, offset: int = 0) -> List[Transaction]:
        return self.db.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.txn_date.desc()).offset(offset).limit(limit).all()

    def get_by_hashes(self, user_id: str, hashes: List[str]) -> List[Transaction]:
        if not hashes:
            return []
        return self.db.query(Transaction).filter(Transaction.user_id == user_id, Transaction.raw_hash.in_(hashes)).all()

    def create(self, txn_in: TransactionCreate, raw_hash: Optional[str] = None) -> Transaction:
        h = raw_hash or compute_raw_hash(str(txn_in.txn_date), txn_in.description, txn_in.amount, txn_in.txn_type)
        obj = Transaction(
            user_id=txn_in.user_id,
            txn_date=txn_in.txn_date,
            description=txn_in.description,
            amount=txn_in.amount,
            txn_type=txn_in.txn_type,
            category=txn_in.category,
            source=txn_in.source,
            raw_hash=h
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def bulk_create(self, transactions: List[TransactionCreate], raw_hashes: List[str], import_batch_id: Optional[str] = None) -> List[Transaction]:
        db_objs = []
        for t, h in zip(transactions, raw_hashes):
            obj = Transaction(
                user_id=t.user_id,
                txn_date=t.txn_date,
                description=t.description,
                amount=t.amount,
                txn_type=t.txn_type,
                category=t.category,
                source=t.source,
                raw_hash=h,
                import_batch_id=import_batch_id
            )
            db_objs.append(obj)
        self.db.add_all(db_objs)
        self.db.commit()
        for obj in db_objs:
            self.db.refresh(obj)
        return db_objs

    def delete_by_user(self, user_id: str) -> int:
        num = self.db.query(Transaction).filter(Transaction.user_id == user_id).delete()
        self.db.commit()
        return num

class SavingsGoalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user(self, user_id: str) -> List[SavingsGoal]:
        return self.db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id).order_by(SavingsGoal.priority.asc()).all()

    def create(self, goal_in: GoalCreate) -> SavingsGoal:
        goal = SavingsGoal(
            user_id=goal_in.user_id,
            name=goal_in.name,
            target_amount=goal_in.target_amount,
            current_amount=goal_in.current_amount,
            target_date=goal_in.target_date,
            priority=goal_in.priority,
            category=goal_in.category
        )
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def delete(self, goal_id: str, user_id: str) -> bool:
        obj = self.db.query(SavingsGoal).filter(SavingsGoal.id == goal_id, SavingsGoal.user_id == user_id).first()
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False

class PrivacyReceiptRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: str, source_name: str, file_name: Optional[str], processed: int, imported: int, duplicates: int) -> PrivacyReceipt:
        receipt = PrivacyReceipt(
            user_id=user_id,
            source_name=source_name,
            file_name=file_name,
            records_processed=processed,
            records_imported=imported,
            duplicates_skipped=duplicates
        )
        self.db.add(receipt)
        self.db.commit()
        self.db.refresh(receipt)
        return receipt

    def get_by_user(self, user_id: str) -> List[PrivacyReceipt]:
        return self.db.query(PrivacyReceipt).filter(PrivacyReceipt.user_id == user_id).order_by(PrivacyReceipt.import_timestamp.desc()).all()
