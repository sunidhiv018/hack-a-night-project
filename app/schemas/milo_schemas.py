from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime

class MiloChatMessageRequest(BaseModel):
    user_id: str
    message: str = Field(..., max_length=1000)
    session_id: Optional[str] = "default_session"
    context_page: Optional[str] = "dashboard"

class MiloMatchedTransaction(BaseModel):
    id: str
    txn_date: date
    description: str
    amount: float
    category: str
    txn_type: str
    source: str = "CSV_IMPORT"

class MiloActionLink(BaseModel):
    label: str
    target_page: str  # "transactions", "dashboard", "forecasts", "savings", "time-machine"
    action_type: str  # "NAVIGATE", "SHOW_TRANSACTION", "OPEN_DRAWER", "PREVIEW_SCENARIO"
    payload: Optional[Dict[str, Any]] = None

class MiloChatMessageResponse(BaseModel):
    session_id: str
    intent: str  # GENERAL_EDUCATION, TRANSACTION_LOOKUP, SPENDING_ANALYSIS, RECURRING_EXPENSES, CASHFLOW_FORECAST, RISK_WARNING, SAVINGS_GOALS, SCENARIO_SIMULATION, OUT_OF_SCOPE
    answer: str
    reply: Optional[str] = None
    follow_up_question: Optional[str] = None
    match_status: str = "NONE"  # NONE, EXACT_MATCH, MULTIPLE_MATCHES, NO_MATCH, AMBIGUOUS
    matched_transactions: List[MiloMatchedTransaction] = []
    action_links: List[MiloActionLink] = []
    actions: Optional[List[Dict[str, Any]]] = []
    evidence: Dict[str, Any] = {}
    disclaimer: str = "Milo provides decision support and financial education based on recorded figures. It is not professional investment or tax advice."

class MiloHistoryItem(BaseModel):
    role: str  # "user" or "milo"
    text: str
    timestamp: str
    intent: Optional[str] = None
    matched_transactions: List[MiloMatchedTransaction] = []
    action_links: List[MiloActionLink] = []

class MiloHistoryResponse(BaseModel):
    user_id: str
    session_id: str
    messages: List[MiloHistoryItem]
