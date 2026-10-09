import pytest
from fastapi.testclient import TestClient
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile

from app.main import app
from app.db.session import Base, get_db
from app.models.domain import User, Transaction, SavingsGoal
from app.services.milo_engine import MiloEngineService

test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
test_db_file.close()

SQLALCHEMY_DATABASE_URL = f"sqlite:///{test_db_file.name.replace(chr(92), '/')}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    db.query(Transaction).delete()
    db.query(SavingsGoal).delete()
    db.query(User).delete()
    db.commit()

    user1 = User(id="usr_milo_1", full_name="Alice Test", email="alice@test.com", created_at=datetime.utcnow())
    user2 = User(id="usr_milo_2", full_name="Bob Isolation", email="bob@test.com", created_at=datetime.utcnow())
    db.add_all([user1, user2])
    db.commit()

    # Seed transactions for user1
    t1 = Transaction(
        id="tx_milo_101",
        user_id="usr_milo_1",
        amount=-2500.0,
        txn_type="debit",
        description="Swiggy Gourmet",
        category="Dining out",
        txn_date=date(2026, 4, 10),
        raw_hash="hash_swiggy_1"
    )
    t2 = Transaction(
        id="tx_milo_102",
        user_id="usr_milo_1",
        amount=-1499.0,
        txn_type="debit",
        description="Netflix India",
        category="Subscriptions",
        txn_date=date(2026, 4, 12),
        raw_hash="hash_netflix_1"
    )
    t3 = Transaction(
        id="tx_milo_103",
        user_id="usr_milo_1",
        amount=50000.0,
        txn_type="credit",
        description="Acme Corp Salary",
        category="Income",
        txn_date=date(2026, 4, 1),
        raw_hash="hash_salary_1"
    )
    db.add_all([t1, t2, t3])

    # Seed goal for user1
    g1 = SavingsGoal(
        id="goal_milo_1",
        user_id="usr_milo_1",
        name="Emergency Reserve",
        target_amount=100000.0,
        current_amount=40000.0,
        target_date=date(2026, 12, 31),
        priority=1
    )
    db.add(g1)
    db.commit()

    # Seed transaction for user2 (Isolation test)
    t_bob = Transaction(
        id="tx_bob_999",
        user_id="usr_milo_2",
        amount=-9999.0,
        txn_type="debit",
        description="Secret Bob Shop",
        category="Shopping",
        txn_date=date(2026, 4, 15),
        raw_hash="hash_bob_1"
    )
    db.add(t_bob)
    db.commit()
    db.close()
    
    # Clear Milo Engine history store before each test
    MiloEngineService.clear_history("usr_milo_1")
    MiloEngineService.clear_history("usr_milo_2")

def test_milo_starter_question_spending():
    resp = client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "Where did my money go this month?"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    reply = data["data"]["reply"]
    assert "Dining out" in reply or "Subscriptions" in reply or "₹" in reply
    assert data["data"]["intent"] == "SPENDING_ANALYSIS"

def test_milo_exact_transaction_lookup():
    resp = client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "Can you check my Netflix payment?"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["match_status"] == "EXACT_MATCH"
    assert len(data["matched_transactions"]) == 1
    tx = data["matched_transactions"][0]
    assert tx["description"] == "Netflix India"
    assert tx["amount"] == -1499.0
    assert "View Transaction" in [a["label"] for a in data["actions"]]

def test_milo_no_match_transaction_lookup():
    resp = client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "Show me transaction for Rolex Watch"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["match_status"] == "NO_MATCH"
    assert len(data["matched_transactions"]) == 0
    assert "no matching transaction" in data["reply"].lower()

def test_milo_conversational_follow_up():
    # Turn 1: Lookup Netflix
    r1 = client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "Check my Netflix subscription payment"
    })
    assert r1.status_code == 200

    # Turn 2: Follow up "is that payment recurring?"
    r2 = client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "is that payment recurring?"
    })
    assert r2.status_code == 200
    reply2 = r2.json()["data"]["reply"]
    assert "Netflix India" in reply2 or "recurring" in reply2.lower()

def test_milo_user_data_isolation():
    # User 1 tries to ask about Bob's transaction merchant
    resp = client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "Find Secret Bob Shop transaction"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["match_status"] == "NO_MATCH"
    assert len(data["matched_transactions"]) == 0

def test_milo_security_refusal():
    resp = client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "My UPI PIN is 1234, can you transfer money?"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "PIN" in data["reply"] or "security" in data["reply"].lower()
    assert data["intent"] == "OUT_OF_SCOPE"

def test_milo_savings_goal_optimizer():
    resp = client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "Am I on track for my savings goal?"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["intent"] == "SAVINGS_GOALS"
    assert "Emergency Reserve" in data["reply"]
    assert "₹40,000" in data["reply"] or "40000" in data["reply"]

def test_milo_scenario_simulation_confirmation():
    resp = client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "What happens if I have an unexpected expense of 10000?"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["intent"] == "SCENARIO_SIMULATION"
    assert any("Financial Time Machine" in a["label"] for a in data["actions"])
    # Ensure sandbox output preview didn't modify actual ledger count
    db = TestingSessionLocal()
    count = db.query(Transaction).filter(Transaction.user_id == "usr_milo_1").count()
    assert count == 3
    db.close()

def test_milo_history_endpoints():
    # Send message first
    client.post("/api/v1/chat/message", json={
        "user_id": "usr_milo_1",
        "message": "Hello Milo!"
    })
    # Fetch history
    h_resp = client.get("/api/v1/chat/history?user_id=usr_milo_1")
    assert h_resp.status_code == 200
    h_data = h_resp.json()["data"]
    assert h_data["user_id"] == "usr_milo_1"
    assert len(h_data["messages"]) >= 2  # user msg + bot reply

    # Clear history
    c_resp = client.delete("/api/v1/chat/history?user_id=usr_milo_1")
    assert c_resp.status_code == 200

    # Fetch history again
    h_resp2 = client.get("/api/v1/chat/history?user_id=usr_milo_1")
    assert len(h_resp2.json()["data"]["messages"]) == 0
