from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import require_owner
from app.core.logging_config import SafeLogger
from app.db.database import db
from app.ingestion.policy_loader import policy_loader, PolicyLoader
from app.schemas.request import PolicyUpdateRequest

router = APIRouter(prefix="/policies", tags=["Policies"])

@router.get("/active")
def get_active_policy() -> Dict[str, Any]:
    """Retrieves current active store policies and parsed sections."""
    active_pol = db.get_active_policy()
    if not active_pol:
        return {
            "is_ready": False,
            "title": "Awaiting Official Policies",
            "version": "None",
            "content": "",
            "sections": {}
        }
    return {
        "is_ready": True,
        "id": active_pol["id"],
        "title": active_pol["title"],
        "version": active_pol["version"],
        "content": active_pol["content"],
        "sections": active_pol.get("sections", {}),
        "created_at": active_pol["created_at"],
        "updated_at": active_pol["updated_at"]
    }

@router.post("/update")
def update_policy(
    req: PolicyUpdateRequest,
    current_owner: dict = Depends(require_owner)
) -> Dict[str, Any]:
    if current_owner.get("is_demo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo Mode Protection: Modifying store policies is restricted in demo sessions. Log in with a verified store owner account to update official store policies."
        )
    """
    Owner updates or uploads official store policies.
    Parses sections, updates database, audits change, and reloads policy retriever.
    """
    if len(req.content.strip()) < 20:
        raise HTTPException(status_code=400, detail="Policy text is too short to be a valid document.")

    temp_loader = PolicyLoader()
    temp_loader.parse_text(
        text=req.content,
        is_official=True,
        is_synthetic=False,
        source_name=f"owner_upload_{req.version}"
    )

    if not temp_loader.sections:
        raise HTTPException(
            status_code=400,
            detail="Could not extract any policy sections. Ensure section headers match format '=== SECTION: TOPIC ==='."
        )

    sections_dict = {sec_id: sec.to_dict() for sec_id, sec in temp_loader.sections.items()}

    # Save and activate in database
    saved = db.save_policy(
        title=req.title,
        content=req.content,
        version=req.version,
        sections=sections_dict,
        actor_id=current_owner["id"]
    )

    # Reload in-memory policy loader
    policy_loader.load_from_database()

    SafeLogger.info(f"Owner {current_owner['email']} updated store policy to {req.version} ({len(sections_dict)} sections).")
    return {
        "status": "success",
        "message": f"Policy {req.version} updated and activated.",
        "policy": saved
    }
