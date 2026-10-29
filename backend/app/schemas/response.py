from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

DecisionType = Literal["ANSWER", "CLARIFY", "REFUSE"]

class EvidenceItem(BaseModel):
    source_type: str = Field(..., description="Source type: product, policy, review, competitor, listing, specification, etc.")
    source_id: str = Field(..., description="Unique ID of source: product ID, policy section ID, review ID, etc.")
    field: str = Field(..., description="Exact field name: price, stock_status, material, return_window, etc.")
    value: Any = Field(..., description="Exact unmanipulated value retrieved from source")
    confidence: float = Field(1.0, description="Verification confidence level")

class EvidenceObject(BaseModel):
    decision: DecisionType = Field(..., description="Deterministic decision: ANSWER, CLARIFY, or REFUSE")
    query: str = Field(..., description="Shopper's query")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Verified supporting evidence items")
    unsupported_fields: List[str] = Field(default_factory=list, description="Fields requested by user but unsupported by ground truth")
    clarification_question: Optional[str] = Field(None, description="Specific follow-up question if decision is CLARIFY")
    refusal_reason: Optional[str] = Field(None, description="Honest, non-blaming refusal reason if decision is REFUSE")

class ProductResult(BaseModel):
    product_id: str
    title: str
    description: str
    category: str
    price: float
    stock_status: str
    rating: Optional[float] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    citation: str = Field(..., description="Citation marker e.g. [PRODUCT:TC-DEV-101]")

class ComparisonData(BaseModel):
    products: List[str] = Field(default_factory=list)
    product_titles: Dict[str, str] = Field(default_factory=dict)
    dimensions: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)

class ChatResponse(BaseModel):
    decision: DecisionType
    response_text: str
    products: List[ProductResult] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    evidence: EvidenceObject
    clarification_question: Optional[str] = None
    refusal_reason: Optional[str] = None
    comparison_data: Optional[ComparisonData] = None
    retrieval_status: str = Field(..., description="Structured, semantic, or policy retrieval summary")
    model_status: str = Field(..., description="Instruction model or rule-based fallback status")
    latency_ms: float
    token_cost: float = Field(default=0.0, description="Estimated token cost in USD for query (0.0 for offline local models)")
    conversation_id: str
    diagnostics: Optional[Dict[str, Any]] = Field(default=None, description="Structured retrieval and relevance diagnostics")

class ReadinessStatus(BaseModel):
    catalogue_ready: bool
    policy_ready: bool
    embedding_model_ready: bool
    instruction_model_ready: bool
    is_using_synthetic_fixtures: bool
    message: str

class HealthResponse(BaseModel):
    status: str = "ok"
    project_name: str
    team_name: str
    version: str
    data_readiness: ReadinessStatus
    model_readiness: Dict[str, Any]

class CatalogueStatusResponse(BaseModel):
    status: str
    is_ready: bool = False
    is_official: bool = True
    is_synthetic_fixture: bool = False
    records_loaded: int = 0
    records_rejected: int = 0
    duplicate_records: int = 0
    missing_fields_count: int = 0
    categories: List[str] = Field(default_factory=list)
    total_active_products: int = 0
    data_source_path: Optional[str] = None
    job_id: Optional[str] = None
    stage: Optional[str] = None
    progress_percent: Optional[float] = None
    total_records: Optional[int] = None
    processed_records: Optional[int] = None
    message: Optional[str] = None

class ActivationJobResponse(BaseModel):
    id: str
    dataset_id: str
    version: str
    status: str
    stage: str
    total_records: int
    processed_records: int
    embedded_records: int
    indexed_records: int
    failed_records: int
    skipped_records: int
    current_batch: int
    total_batches: int
    batch_size: int
    progress_percent: float
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    retry_count: int = 0
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    is_active: bool = False
    message: Optional[str] = None

class QuestionEvaluationResult(BaseModel):
    question_id: str
    query: str
    expected_decision: Optional[str] = None
    actual_decision: str
    decision_match: Optional[bool] = None
    passed: bool = True
    failure_reason: Optional[str] = None
    citations: List[str] = Field(default_factory=list)
    citations_valid: bool
    has_unsupported_claims: bool
    latency_ms: float
    token_cost: float = Field(default=0.0, description="Token cost in USD for this query (0.0 for local model)")
    notes: Optional[str] = None
    evidence_preview: List[str] = Field(default_factory=list)

class EvaluationReportResponse(BaseModel):
    report_id: str
    timestamp: str
    dataset_name: str
    total_cases_available: int = 0
    total_cases_executed: int = 0
    total_cases_passed: int = 0
    total_cases_failed: int = 0
    total_cases_skipped: int = 0
    total_questions_tested: int
    successfully_evaluated: int
    groundedness_score: float
    answer_helpfulness_score: float
    refusal_accuracy: float
    clarification_accuracy: float
    unsupported_claim_rate: float
    citation_validity_rate: float
    citation_coverage_rate: float = 1.0
    avg_latency_ms: float
    latency_p50_ms: float = 0.0
    latency_p90_ms: float = 0.0
    latency_p99_ms: float = 0.0
    avg_token_cost: float = Field(default=0.0, description="Average token cost per query in USD")
    total_token_cost: float = Field(default=0.0, description="Total token cost for evaluation run in USD")
    data_readiness: Optional[str] = None
    model_readiness: Optional[str] = None
    compute_info: Dict[str, Any] = Field(default_factory=dict)
    details: List[QuestionEvaluationResult] = Field(default_factory=list)

# --- User & Auth Responses ---
class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_demo: bool = False
    created_at: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# --- Catalogue Management Responses ---
class CatalogueVersionResponse(BaseModel):
    id: str
    version: str
    name: str
    filename: str
    owner_id: str
    record_count: int
    valid_count: int
    invalid_count: int
    status: str
    is_active: bool
    created_at: str
    activated_at: Optional[str] = None
    category: Optional[str] = "PRODUCT_CATALOGUE"
    embedding_status: Optional[str] = "INDEXED"
    active_job_id: Optional[str] = None
    job_status: Optional[str] = None
    job_stage: Optional[str] = None
    processed_records: Optional[int] = None
    total_records: Optional[int] = None
    progress_percent: Optional[float] = None
    job_error: Optional[str] = None

class CataloguePreviewResponse(BaseModel):
    filename: str
    total_rows: int
    valid_count: int
    invalid_count: int
    preview_records: List[Dict[str, Any]] = Field(default_factory=list)
    all_valid_records: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    inferred_version: str
    detected_category: Optional[str] = "PRODUCT_CATALOGUE"
    category_confidence: Optional[float] = 1.0
    detected_format: Optional[str] = "CSV"
    available_sheets: List[str] = Field(default_factory=list)
    embedding_eligible: bool = True
    schema_mappings: Optional[Dict[str, Any]] = None

# --- Feedback Responses ---
class FeedbackResponse(BaseModel):
    id: str
    customer_id: str
    customer_email: str
    feedback_type: str
    product_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message: str
    rating: Optional[int] = None
    status: str
    is_demo: bool = False
    owner_resolution_note: Optional[str] = None
    created_at: str
    resolved_at: Optional[str] = None
    reviewed_by: Optional[str] = None

# --- Audit & System Responses ---
class AuditLogResponse(BaseModel):
    id: str
    actor_id: str
    actor_role: str
    action: str
    target_id: str
    target_type: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str

class SystemStatsResponse(BaseModel):
    active_catalogue: Optional[Dict[str, Any]] = None
    active_policy: Optional[Dict[str, Any]] = None
    total_valid_products: int
    feedback: Dict[str, int]
    last_evaluation: Optional[Dict[str, Any]] = None
    recent_audits: List[Dict[str, Any]] = Field(default_factory=list)

