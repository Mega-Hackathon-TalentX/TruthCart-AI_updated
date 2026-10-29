from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="The shopper's query message.")
    conversation_id: Optional[str] = Field(None, description="Optional conversation session ID for multi-turn tracking.")

class EvaluationRequest(BaseModel):
    dataset_name: Optional[str] = Field("sample_eval_questions.json", description="File name of evaluation questions dataset.")
    max_questions: Optional[int] = Field(None, ge=1, le=1000, description="Max questions to evaluate.")
    dry_run: bool = Field(False, description="Dry run mode without updating persisted evaluation reports.")

class CatalogueIngestRequest(BaseModel):
    file_path: Optional[str] = Field(None, description="Explicit path to product catalogue.")
    column_mapping: Optional[Dict[str, str]] = Field(None, description="Custom column name mapping dictionary.")
    use_synthetic: bool = Field(False, description="Whether to explicitly load development fixtures for testing.")

# --- Authentication Schemas ---
class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=150)
    password: str = Field(..., min_length=6, max_length=100)

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=150)
    password: str = Field(..., min_length=1, max_length=100)

class DemoSessionRequest(BaseModel):
    role: str = Field("CUSTOMER", description="Requested demo portal role: CUSTOMER or OWNER")

# --- Catalogue Management Schemas ---
class CatalogueImportConfirmRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    version: str = Field(..., min_length=1, max_length=50)
    filename: str = Field(..., min_length=1, max_length=255)
    records: List[Dict[str, Any]] = Field(..., description="List of validated records to import")
    validation_report: Dict[str, Any] = Field(default_factory=dict)
    valid_count: int
    invalid_count: int
    category: Optional[str] = "PRODUCT_CATALOGUE"
    schema_mapping: Optional[Dict[str, Any]] = None

# --- Product Management Schemas ---
class ProductUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = Field(None, ge=0.0)
    stock_status: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    attributes: Optional[Dict[str, Any]] = None

# --- Feedback Schemas ---
class FeedbackCreateRequest(BaseModel):
    feedback_type: str = Field(..., description="ai_answer, incorrect_product_info, missing_product, incorrect_attribute, recommendation_issue, catalogue_issue, general_usability")
    message: str = Field(..., min_length=3, max_length=3000)
    product_id: Optional[str] = None
    conversation_id: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    is_demo: Optional[bool] = False

class FeedbackStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="PENDING, UNDER_REVIEW, RESOLVED, REJECTED")
    resolution_note: Optional[str] = None

class VerifiedCorrectionRequest(BaseModel):
    feedback_id: str
    product_id: str
    updates: ProductUpdateRequest
    resolution_note: str

# --- Policy Management Schemas ---
class PolicyUpdateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    content: str = Field(..., min_length=10)
    version: str = Field(..., min_length=1, max_length=50)
