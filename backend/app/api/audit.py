from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query

from app.core.auth import require_owner
from app.db.database import db
from app.schemas.response import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])

@router.get("", response_model=List[AuditLogResponse])
def get_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    current_owner: dict = Depends(require_owner)
) -> List[AuditLogResponse]:
    """Owner Audit Trail: Immutable chronological record of system and owner actions. Demo sessions receive isolated demo audit entries."""
    if current_owner.get("is_demo"):
        from app.core.demo_data import DEMO_SYSTEM_STATS
        return [AuditLogResponse(**a) for a in DEMO_SYSTEM_STATS.get("recent_audits", [])]
    logs = db.get_audit_logs(limit=limit)
    res = []
    for l in logs:
        res.append(AuditLogResponse(
            id=l["id"],
            actor_id=l["actor_id"],
            actor_role=l["actor_role"],
            action=l["action"],
            target_id=l["target_id"],
            target_type=l["target_type"],
            details=l.get("details"),
            timestamp=l["timestamp"]
        ))
    return res
