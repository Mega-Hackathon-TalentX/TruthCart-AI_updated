from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import get_current_user, require_customer, require_owner
from app.core.logging_config import SafeLogger
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.retrieval.semantic_search import local_vector_index
from app.schemas.request import (
    FeedbackCreateRequest,
    FeedbackStatusUpdateRequest,
    VerifiedCorrectionRequest
)
from app.schemas.response import FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["Customer Feedback"])

@router.post("", response_model=FeedbackResponse)
def submit_feedback(
    req: FeedbackCreateRequest,
    current_customer: dict = Depends(require_customer)
) -> FeedbackResponse:
    """
    Customer submits feedback.
    CRITICAL RULE: Persists in database as PENDING. NEVER automatically updates product data.
    """
    fb_is_demo = bool(req.is_demo or current_customer.get("is_demo", False))
    fb = db.create_feedback(
        customer_id=current_customer["id"],
        customer_email=current_customer["email"],
        feedback_type=req.feedback_type,
        message=req.message,
        product_id=req.product_id,
        conversation_id=req.conversation_id,
        rating=req.rating,
        is_demo=fb_is_demo
    )

    SafeLogger.info(f"Customer {current_customer['email']} submitted feedback {fb['id']} (type: {req.feedback_type}, demo: {fb_is_demo}).")
    return FeedbackResponse(**fb)

@router.get("/my", response_model=List[FeedbackResponse])
def get_my_feedback(
    current_customer: dict = Depends(require_customer)
) -> List[FeedbackResponse]:
    """
    Privacy Enforcement:
    Customer can see ONLY their own submitted feedback and review progress.
    """
    feedbacks = db.get_feedback_for_customer(customer_id=current_customer["id"])
    return [FeedbackResponse(**f) for f in feedbacks]

@router.get("/owner", response_model=List[FeedbackResponse])
def get_owner_feedback(
    status_filter: Optional[str] = Query(None, alias="status"),
    feedback_type: Optional[str] = Query(None, alias="type"),
    product_id: Optional[str] = Query(None),
    is_demo: Optional[bool] = Query(None),
    current_owner: dict = Depends(require_owner)
) -> List[FeedbackResponse]:
    """Owner Feedback Dashboard: Lists customer reports with status filtering."""
    # Strict customer privacy: demo owner sessions can ONLY see demo feedback!
    if current_owner.get("is_demo"):
        is_demo = True

    feedbacks = db.get_all_feedback_for_owner(
        status=status_filter,
        feedback_type=feedback_type,
        product_id=product_id,
        is_demo=is_demo
    )
    return [FeedbackResponse(**f) for f in feedbacks]

@router.put("/{feedback_id}/status", response_model=FeedbackResponse)
def update_feedback_status(
    feedback_id: str,
    req: FeedbackStatusUpdateRequest,
    current_owner: dict = Depends(require_owner)
) -> FeedbackResponse:
    """
    Owner updates feedback review status (UNDER_REVIEW, RESOLVED, REJECTED)
    with a resolution or rejection reason.
    """
    fb = db.get_feedback_by_id(feedback_id)
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback record not found.")

    if current_owner.get("is_demo") and not fb.get("is_demo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo Mode Protection: Demo owner sessions cannot modify official production feedback records."
        )

    updated = db.update_feedback_status(
        feedback_id=feedback_id,
        status=req.status,
        owner_id=current_owner["id"],
        resolution_note=req.resolution_note
    )

    SafeLogger.info(f"Owner {current_owner['email']} marked feedback {feedback_id} as {req.status}.")
    return FeedbackResponse(**updated)

@router.post("/verified-correction", response_model=FeedbackResponse)
def apply_verified_correction(
    req: VerifiedCorrectionRequest,
    current_owner: dict = Depends(require_owner)
) -> FeedbackResponse:
    """
    CRITICAL WORKFLOW:
    Owner conducts human verification of customer feedback, approves verified facts,
    updates official product attributes in database, audits changes, refreshes knowledge base,
    and marks the feedback as RESOLVED.
    """
    if current_owner.get("is_demo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo Mode Protection: Modifying official product catalogue records via feedback correction is disabled in demo mode. Sign in with a verified store owner account to apply permanent corrections."
        )

    fb = db.get_feedback_by_id(req.feedback_id)
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback record not found.")

    updates = {k: v for k, v in req.updates.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Correction must specify at least one verified product attribute.")

    # 1. Update product in database with audit
    db.update_product(
        product_id=req.product_id,
        updates=updates,
        actor_id=current_owner["id"]
    )

    # 2. Synchronize active catalogue in-memory and local vector index
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)

    # 3. Mark feedback as RESOLVED with resolution note
    note = req.resolution_note or f"Verified by store owner: updated {list(updates.keys())}."
    resolved_fb = db.update_feedback_status(
        feedback_id=req.feedback_id,
        status="RESOLVED",
        owner_id=current_owner["id"],
        resolution_note=note
    )

    SafeLogger.info(f"Verified correction applied by owner {current_owner['email']} on product {req.product_id}.")
    return FeedbackResponse(**resolved_fb)
