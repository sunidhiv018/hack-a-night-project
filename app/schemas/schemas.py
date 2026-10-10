from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import date, datetime

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime

# Transaction Schemas
class TransactionBase(BaseModel):
    txn_date: date
    description: str
    amount: float = Field(..., gt=0)
    txn_type: str = Field(..., pattern="^(debit|credit)$")
    category: str = "Uncategorized"

class TransactionCreate(TransactionBase):
    user_id: str
    source: str = "CSV_IMPORT"

class TransactionResponse(TransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    source: str
    raw_hash: str
    created_at: datetime

# Import Schemas
class PreviewItem(BaseModel):
    txn_date: date
    description: str
    amount: float
    txn_type: str
    category: str
    raw_hash: str
    is_duplicate: bool
    duplicate_of_id: Optional[str] = None

class ImportPreviewResponse(BaseModel):
    total_rows: int
    valid_rows: int
    duplicate_rows: int
    new_rows: int
    preview_records: List[PreviewItem]
    detected_columns: List[str]

class ImportConfirmRequest(BaseModel):
    user_id: str
    source_name: str
    file_name: str
    records: List[PreviewItem]
    skip_duplicates: bool = True

class ImportSummaryResponse(BaseModel):
    receipt_id: str
    source_name: str
    file_name: str
    records_processed: int
    records_imported: int
    duplicates_skipped: int
    import_timestamp: datetime

class NotificationListenerRequest(BaseModel):
    user_id: str
    notification_text: str  # e.g., "Paid Rs 450.00 to Swiggy using Google Pay. Ref 429104821094"
    notification_title: Optional[str] = "Google Pay"
    source_app: Optional[str] = "com.google.android.apps.nfc.plugin.card.gp"
    package_name: Optional[str] = "com.google.android.apps.nfc.plugin.card.gp"
    ref_number: Optional[str] = None
    post_time: Optional[int] = None

class NotificationTransactionResponse(BaseModel):
    transaction_id: Optional[str] = None
    amount: float
    txn_type: str
    description: str
    category: str
    confidence_score: float
    method: str
    auto_imported: bool
    is_pending_review: bool = False
    pending_review_id: Optional[str] = None
    explanation: str

class PendingReviewItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    source_app: str
    raw_title: Optional[str] = None
    raw_text: str
    parsed_amount: Optional[float] = None
    parsed_merchant: Optional[str] = None
    parsed_direction: Optional[str] = None
    reason: str
    confidence_score: float
    created_at: datetime

class AutoSyncStatusResponse(BaseModel):
    user_id: str
    is_connected: bool
    package_verified: bool
    permission_state: str
    last_successful_sync: Optional[datetime] = None
    imported_notification_count: int
    pending_review_count: int
    duplicates_prevented_count: int
    data_retention_policy: str


class TradeOffAdviceRequest(BaseModel):
    user_id: str
    discretionary_category: Optional[str] = "Dining & Food"
    potential_savings_amount: float = 1500.0

class TradeOffAdviceResponse(BaseModel):
    discretionary_category: str
    monthly_reduction: float
    target_goal_name: str
    original_target_date: date
    accelerated_target_date: date
    days_saved: int
    recommendation_summary: str

# Dashboard & Analytics Schemas
class CategoryBreakdown(BaseModel):
    category: str
    amount: float
    percentage: float
    count: int

class DashboardSummaryResponse(BaseModel):
    user_id: str
    total_balance: float
    total_income: float
    total_expenses: float
    net_savings: float
    avg_daily_spend: float
    top_categories: List[CategoryBreakdown]
    recent_transactions: List[TransactionResponse]

# Forecasting & Breaches
class ForecastDailyPoint(BaseModel):
    date: date
    projected_balance: float
    projected_income: float
    projected_expense: float
    is_breach: bool
    confidence_lower: float
    confidence_upper: float

class BufferBreachAlert(BaseModel):
    date: date
    projected_balance: float
    safe_buffer: float
    shortfall: float
    primary_causes: List[str]
    supporting_evidence: List[Dict[str, Any]]

class ForecastResponse(BaseModel):
    user_id: str
    horizon_days: int
    start_balance: float
    end_balance: float
    safe_buffer: float
    breaches: List[BufferBreachAlert]
    daily_timeline: List[ForecastDailyPoint]
    model_method: str
    explanations: List[str]

# Recurring & Unusual Expenses
class RecurringExpense(BaseModel):
    merchant_pattern: str
    category: str
    estimated_amount: float
    frequency_days: int
    next_expected_date: date
    confidence_score: float
    transaction_ids: List[str]
    reasoning: str

class UnusualSpendingAlert(BaseModel):
    transaction_id: str
    txn_date: date
    description: str
    amount: float
    category: str
    baseline_avg: float
    z_score: float
    explanation: str

# Savings Goals & Optimization
class GoalBase(BaseModel):
    name: str
    target_amount: float = Field(..., gt=0)
    current_amount: float = Field(default=0.0, ge=0)
    target_date: date
    priority: int = Field(default=1, ge=1)
    category: str = "General"

class GoalCreate(GoalBase):
    user_id: str

class GoalResponse(GoalBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    created_at: datetime

class GoalAllocationItem(BaseModel):
    goal_id: str
    goal_name: str
    target_amount: float
    target_date: date
    priority: int
    recommended_monthly_savings: float
    allocated_surplus: float
    completion_percentage: float
    projected_completion_date: Optional[date]
    is_feasible: bool
    reasoning: str

class GoalOptimizationResponse(BaseModel):
    user_id: str
    monthly_available_surplus: float
    allocations: List[GoalAllocationItem]
    conflicts_detected: List[str]
    optimization_method: str

# Financial Time Machine / Scenario Simulation
class ScenarioRequest(BaseModel):
    user_id: str
    horizon_days: int = 90
    income_delay_days: int = 0
    income_reduction_percent: float = 0.0
    one_off_expenses: List[Dict[str, Any]] = []   # [{"description": "...", "amount": 15000, "date": "2026-10-25"}]
    spending_category_changes: Dict[str, float] = {}  # {"Dining": 20.0, "Shopping": -30.0} pct change

class ScenarioComparisonResponse(BaseModel):
    user_id: str
    baseline_end_balance: float
    scenario_end_balance: float
    balance_difference: float
    baseline_breaches: int
    scenario_breaches: int
    breach_delta: int
    timeline_comparison: List[Dict[str, Any]]
    delta_explanations: List[str]

# Report Explorer / Evidence Schemas
class EvidenceItem(BaseModel):
    title: str
    recommendation: str
    supporting_transactions: List[TransactionResponse]
    calculation_details: Dict[str, Any]
    assumptions: List[str]
    projected_impact: str

class PrivacyReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_name: str
    file_name: Optional[str] = None
    records_processed: int
    records_imported: int
    duplicates_skipped: int
    import_timestamp: datetime
    data_scope: str
    data_retention: str


# BrokeBuddy Smart Capture Schemas
class SmartCaptureEvent(BaseModel):
    raw_text: str
    source_app: Optional[str] = "UNKNOWN"
    timestamp: Optional[str] = None
    amount: Optional[float] = None
    merchant: Optional[str] = None
    txn_type: Optional[str] = "debit"
    category: Optional[str] = None
    is_demo: bool = False
    raw_hash: Optional[str] = None

class SmartCaptureSyncItem(BaseModel):
    id: str
    raw_text: str
    source_app: str
    txn_date: date
    description: str
    amount: float
    txn_type: str
    category: str
    confidence_score: float
    is_duplicate: bool = False
    duplicate_reason: Optional[str] = None
    is_demo: bool = False
    raw_hash: str
    status: str = "pending_review"  # "pending_review", "demo_staged", "auto_imported"

class SmartCaptureSyncRequest(BaseModel):
    user_id: str
    events: List[SmartCaptureEvent]
    auto_approve_high_confidence: bool = False

class SmartCaptureSyncResponse(BaseModel):
    total_received: int
    processed_count: int
    duplicate_count: int
    demo_count: int
    items: List[SmartCaptureSyncItem]

class SmartCaptureApproveRequest(BaseModel):
    user_id: str
    items: List[SmartCaptureSyncItem]

class SmartCaptureApproveResponse(BaseModel):
    approved_count: int
    skipped_demo_count: int
    skipped_duplicate_count: int
    saved_transactions: List[TransactionResponse]

