from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class CategorizationRequest(BaseModel):
    description: str
    amount: Optional[float] = 0.0

class CategorizationResponse(BaseModel):
    predicted_category: str
    confidence_score: float
    description: str
    method: str = "unknown"          # "tfidf_logreg_ml", "rule_based_keyword", or "unknown"

class CopilotQueryRequest(BaseModel):
    user_id: str
    query: str

class CopilotQueryResponse(BaseModel):
    query: str
    answer: str
    evidence: Dict[str, Any]
    disclaimer: str

# ── AI Health / Diagnostic ─────────────────────────────────────────────────
class AIFeatureStatus(BaseModel):
    feature: str
    implementation_type: str        # "trained_ml", "statistical", "rule_based", "deterministic", "llm"
    model_available: bool
    model_artifact_path: Optional[str] = None
    model_version: Optional[str] = None
    dataset_size: Optional[int] = None
    training_date: Optional[str] = None
    evaluation_metrics: Optional[Dict[str, Any]] = None
    fallback_active: bool
    fallback_method: Optional[str] = None
    known_limitations: List[str]
    notes: str

class AIHealthResponse(BaseModel):
    sklearn_dll_available: bool
    features: List[AIFeatureStatus]
    overall_status: str             # "ml_enabled", "fallback_only"
    disclaimer: str
