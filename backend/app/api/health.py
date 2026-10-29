from app.core.auth import optional_current_user
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from app.core.config import settings
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.ingestion.policy_loader import policy_loader
from app.llm.model_loader import model_loader
from app.retrieval.semantic_search import local_vector_index
from app.schemas.response import HealthResponse, ReadinessStatus, SystemStatsResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    cat_status = catalogue_loader.get_status()
    pol_status = policy_loader.get_status()
    mod_status = model_loader.get_status()

    is_synthetic = cat_status["is_synthetic_fixture"] or pol_status["is_synthetic_fixture"]
    
    if cat_status["is_official"] and pol_status["is_official"]:
        msg = "Official Hackathon Data Active"
    elif is_synthetic:
        msg = "Running with Synthetic Development Fixtures"
    elif not cat_status["is_ready"] and not pol_status["is_ready"]:
        msg = "Awaiting Organiser Catalogue and Policy"
    elif not cat_status["is_ready"]:
        msg = "Awaiting Organiser Catalogue"
    else:
        msg = "Awaiting Organiser Policy"

    readiness = ReadinessStatus(
        catalogue_ready=cat_status["is_ready"],
        policy_ready=pol_status["is_ready"],
        embedding_model_ready=mod_status["embedding_model_ready"],
        instruction_model_ready=mod_status["instruction_model_ready"],
        is_using_synthetic_fixtures=is_synthetic,
        message=msg
    )

    return HealthResponse(
        status="ok",
        project_name=settings.PROJECT_NAME,
        team_name=settings.TEAM_NAME,
        version=settings.VERSION,
        data_readiness=readiness,
        model_readiness=mod_status
    )

@router.get("/system/stats")
def get_system_stats(
    demo: Optional[bool] = None,
    user: Optional[dict] = Depends(optional_current_user)
) -> Dict[str, Any]:
    """Calculates live operational metrics from SQLite database (or demo sandbox stats for demo users)."""
    user_dict = user if isinstance(user, dict) else None
    if demo is True or (user_dict and user_dict.get("is_demo")):
        from app.core.demo_data import DEMO_SYSTEM_STATS
        return DEMO_SYSTEM_STATS
    return db.get_system_stats()

@router.get("/system/readiness")
def get_detailed_readiness() -> Dict[str, Any]:
    """
    Returns separate, truthful readiness states for all 7 sub-systems:
    1. Model readiness
    2. Dataset readiness
    3. Catalogue database readiness
    4. Product index readiness
    5. Policy index readiness
    6. Evidence engine readiness
    7. API readiness
    """
    cat_status = catalogue_loader.get_status()
    pol_status = policy_loader.get_status()
    mod_status = model_loader.get_status()
    active_cat = db.get_active_catalogue()

    return {
        "model_readiness": {
            "status": "ready" if mod_status.get("real_instruction_model_loaded") else "fallback_active",
            "real_instruction_model_loaded": mod_status.get("real_instruction_model_loaded", False),
            "real_instruction_model_tested": mod_status.get("real_instruction_model_tested", False),
            "deterministic_fallback_active": mod_status.get("deterministic_fallback_active", True),
            "embedding_model_ready": mod_status.get("embedding_model_ready", False),
            "instruction_model_ready": mod_status.get("instruction_model_ready", False),
            "execution_mode": "Offline Local / CPU",
            "fallback": "Deterministic Grounded Rule Generator (Active)"
        },

        "dataset_readiness": {
            "status": "ready" if cat_status["is_ready"] else "awaiting_data",
            "is_official": cat_status["is_official"],
            "is_synthetic": cat_status["is_synthetic_fixture"],
            "records_loaded": cat_status["records_loaded"]
        },
        "catalogue_db_readiness": {
            "status": "ready" if active_cat else "awaiting_activation",
            "active_version": active_cat["version"] if active_cat else None,
            "active_name": active_cat["name"] if active_cat else None
        },
        "product_index_readiness": {
            "status": "ready" if local_vector_index.is_indexed else "not_built",
            "indexed_count": len(local_vector_index.doc_ids) if local_vector_index.is_indexed else 0
        },
        "policy_index_readiness": {
            "status": "ready" if pol_status["is_ready"] else "not_configured",
            "sections_count": pol_status.get("sections_count", 0)
        },
        "evidence_engine_readiness": {
            "status": "ready",
            "decision_modes": ["ANSWER", "CLARIFY", "REFUSE"],
            "citation_enforcement": "Strict [PRODUCT:ID] & [POLICY:ID]"
        },
        "api_readiness": {
            "status": "ready",
            "version": settings.VERSION,
            "team": settings.TEAM_NAME
        }
    }
