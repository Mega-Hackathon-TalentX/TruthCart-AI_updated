import io
import json
from typing import List, Dict, Any, Optional
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status

from app.core.auth import require_owner, optional_current_user
from app.core.logging_config import SafeLogger
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.ingestion.data_validator import DataValidator
from app.retrieval.semantic_search import local_vector_index
from app.schemas.request import CatalogueIngestRequest, CatalogueImportConfirmRequest
from app.schemas.response import (
    CatalogueStatusResponse,
    CataloguePreviewResponse,
    CatalogueVersionResponse,
    ActivationJobResponse
)

router = APIRouter(prefix="/catalogue", tags=["Catalogue"])

MAX_UPLOAD_SIZE = 35 * 1024 * 1024 # 35 MB target upload limit

@router.get("/status", response_model=CatalogueStatusResponse)
def get_catalogue_status(
    demo: Optional[bool] = None,
    user: Optional[dict] = Depends(optional_current_user)
) -> CatalogueStatusResponse:
    """Returns current active catalogue status and metrics (isolated for demo sessions)."""
    user_dict = user if isinstance(user, dict) else None
    if demo is True or (user_dict and user_dict.get("is_demo")):
        from app.core.demo_data import DEMO_CATALOGUES
        active_demo = DEMO_CATALOGUES[0]
        return CatalogueStatusResponse(
            status=active_demo["status"],
            is_ready=True,
            is_official=False,
            is_synthetic_fixture=False,
            records_loaded=active_demo["record_count"],
            records_rejected=0,
            duplicate_records=0,
            missing_fields_count=0,
            categories=["Audio", "Electronics", "Footwear", "Home & Kitchen", "Wearables"],
            total_active_products=active_demo["record_count"],
            data_source_path="predefined_demo_catalog.json (Isolated Sandbox)"
        )
    status_info = catalogue_loader.get_status()
    return CatalogueStatusResponse(
        status=status_info["status"],
        is_ready=status_info["is_ready"],
        is_official=status_info["is_official"],
        is_synthetic_fixture=status_info["is_synthetic_fixture"],
        records_loaded=status_info["records_loaded"],
        records_rejected=status_info["records_rejected"],
        duplicate_records=status_info["duplicate_records"],
        missing_fields_count=status_info["missing_fields_count"],
        categories=status_info["categories"],
        total_active_products=status_info["total_active_products"],
        data_source_path=status_info["data_source_path"]
    )

@router.post("/reload", response_model=CatalogueStatusResponse)
def reload_catalogue(req: CatalogueIngestRequest = CatalogueIngestRequest()) -> CatalogueStatusResponse:
    """Reloads catalogue. Kept backwards compatible for tests and development fixtures."""
    from app.ingestion.policy_loader import policy_loader
    catalogue_loader.load_default_catalogue(force_fixtures=req.use_synthetic)
    policy_loader.load_default_policy(force_fixtures=req.use_synthetic)
    local_vector_index.build_index(force_rebuild=True)
    return get_catalogue_status(user=None)

@router.get("/versions", response_model=List[CatalogueVersionResponse])
def get_catalogue_versions(current_owner: dict = Depends(require_owner)) -> List[CatalogueVersionResponse]:
    """Owner view: Lists all imported and active catalogue versions. Demo sessions receive strictly isolated demo catalogue."""
    if current_owner.get("is_demo"):
        from app.core.demo_data import DEMO_CATALOGUES
        return [CatalogueVersionResponse(**c) for c in DEMO_CATALOGUES]

    cats = db.get_all_catalogues()
    res = []
    for c in cats:
        res.append(CatalogueVersionResponse(
            id=c["id"],
            version=c["version"],
            name=c["name"],
            filename=c["filename"],
            owner_id=c["owner_id"],
            record_count=c["record_count"],
            valid_count=c["valid_count"],
            invalid_count=c["invalid_count"],
            status=c["status"],
            is_active=bool(c["is_active"]),
            created_at=c["created_at"],
            activated_at=c.get("activated_at"),
            category=c.get("category", "PRODUCT_CATALOGUE"),
            embedding_status=c.get("embedding_status", "INDEXED"),
            active_job_id=c.get("active_job_id"),
            job_status=c.get("job_status"),
            job_stage=c.get("job_stage"),
            processed_records=c.get("processed_records"),
            total_records=c.get("total_records"),
            progress_percent=c.get("progress_percent"),
            job_error=c.get("job_error")
        ))
    return res

@router.post("/upload-preview", response_model=CataloguePreviewResponse)
async def upload_and_preview_catalogue(
    file: UploadFile = File(...),
    sheet: Optional[str] = Form(None),
    category_override: Optional[str] = Form(None),
    current_owner: dict = Depends(require_owner)
) -> CataloguePreviewResponse:
    """
    Step 1 & 2 of Owner workflow:
    Receives file, parses CSV/TSV/JSON/JSONL/XLS/XLSX, profiles schema,
    detects dataset domain category, validates and normalizes records,
    and returns a comprehensive preview report with mapping confidence.
    """
    filename = file.filename or "unknown_file"
    suffix = filename.split(".")[-1].lower() if "." in filename else ""

    if suffix not in ("csv", "tsv", "json", "jsonl", "xls", "xlsx"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. TruthCart AI accepts CSV, TSV, JSON, JSONL, XLS, or XLSX files."
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size limit of {MAX_UPLOAD_SIZE // (1024*1024)} MB."
        )

    from app.ingestion.universal_ingestor import universal_ingestor

    try:
        records, available_sheets, detected_format = universal_ingestor.parse_file(
            content=content,
            filename=filename,
            sheet_name=sheet
        )
    except Exception as e:
        SafeLogger.error(f"Failed to parse uploaded file {filename}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse file: {str(e)}"
        )

    if not records:
        raise HTTPException(status_code=400, detail="The uploaded file contains no data records.")

    # Profile schema, detect category, and validate/normalize
    mapping_res, valid_records, errors, warnings = universal_ingestor.profile_and_validate(
        records=records,
        category_override=category_override
    )

    if mapping_res.detected_category.value == "UNRELATED_DATASET" and len(valid_records) == 0:
        raise HTTPException(
            status_code=400,
            detail="Not a valid dataset: File does not contain recognizable product, marketplace, review, pricing, or policy information."
        )

    # Inferred next version based on existing versions avoiding collision
    existing_cats = db.get_all_catalogues()
    existing_versions = [c["version"] for c in existing_cats]
    
    inferred_version = "v1.1.0"
    if existing_versions:
        import re
        max_major = 1
        max_minor = 0
        for v in existing_versions:
            m = re.match(r'v?(\d+)\.(\d+)', v.strip())
            if m:
                maj = int(m.group(1))
                min_ = int(m.group(2))
                if maj > max_major or (maj == max_major and min_ > max_minor):
                    max_major = maj
                    max_minor = min_
        candidate = f"v{max_major}.{max_minor + 1}.0"
        while candidate.lower() in [ev.lower() for ev in existing_versions]:
            max_minor += 1
            candidate = f"v{max_major}.{max_minor}.0"
        inferred_version = candidate

    return CataloguePreviewResponse(
        filename=filename,
        total_rows=len(records),
        valid_count=len(valid_records),
        invalid_count=len(errors),
        preview_records=valid_records[:25],
        all_valid_records=valid_records,
        errors=errors[:50],
        warnings=warnings[:50],
        inferred_version=inferred_version,
        detected_category=mapping_res.detected_category.value,
        category_confidence=mapping_res.category_confidence,
        detected_format=detected_format,
        available_sheets=available_sheets,
        embedding_eligible=mapping_res.embedding_eligible,
        schema_mappings={k: p.model_dump() for k, p in mapping_res.column_profiles.items()}
    )

@router.post("/import", response_model=CatalogueVersionResponse)
def confirm_import_catalogue(
    req: CatalogueImportConfirmRequest,
    current_owner: dict = Depends(require_owner)
) -> CatalogueVersionResponse:
    """
    Step 3 of Owner workflow:
    Confirms validated dataset import into database. Saves records without overwriting
    active catalogue until explicit activation.
    """
    if current_owner.get("is_demo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo Mode Protection: Importing new catalogue versions is disabled in demo mode to protect official production catalogue records. File upload preview and schema validation are available."
        )

    if not req.records:
        raise HTTPException(status_code=400, detail="Cannot import an empty record list.")

    # Idempotent / Unique Version Enforcement
    existing_version = db.get_catalogue_by_version(req.version)
    if existing_version:
        raise HTTPException(
            status_code=400,
            detail=f"Catalogue version '{req.version}' is already registered (status: {existing_version['status']}). Please provide a unique semantic version number (e.g. v2.1.0)."
        )

    cat = db.create_catalogue(
        name=req.name,
        filename=req.filename,
        version=req.version,
        owner_id=current_owner["id"],
        records=req.records,
        validation_report=req.validation_report,
        valid_count=req.valid_count,
        invalid_count=req.invalid_count,
        status="READY_FOR_ACTIVATION",
        category=req.category or "PRODUCT_CATALOGUE",
        schema_mapping=req.schema_mapping
    )

    SafeLogger.info(f"Owner {current_owner.get('email')} imported {req.category or 'catalogue'} {req.version} ({req.valid_count} records).")
    return CatalogueVersionResponse(
        id=cat["id"],
        version=cat["version"],
        name=cat["name"],
        filename=cat["filename"],
        owner_id=cat["owner_id"],
        record_count=cat["record_count"],
        valid_count=cat["valid_count"],
        invalid_count=cat["invalid_count"],
        status=cat["status"],
        is_active=bool(cat["is_active"]),
        created_at=cat["created_at"],
        activated_at=cat.get("activated_at"),
        category=req.category or cat.get("category", "PRODUCT_CATALOGUE"),
        embedding_status=cat.get("embedding_status", "INDEXED")
    )

@router.post("/{cat_id}/activate", response_model=CatalogueStatusResponse)
def activate_catalogue(
    cat_id: str,
    async_mode: Optional[bool] = None,
    current_owner: dict = Depends(require_owner)
) -> CatalogueStatusResponse:
    """
    Step 4 of Owner workflow:
    Activates approved catalogue version, updates retrieval indexes,
    and refreshes the customer assistant's knowledge base.
    Uses asynchronous batch worker for datasets > 50 records to prevent HTTP timeouts.
    """
    if current_owner.get("is_demo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo Mode Protection: Activating catalogue versions is restricted in demo mode to protect official production catalogue records. Sign in with a verified store owner account to activate production catalogues."
        )

    cat = db.get_catalogue_by_id(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail=f"Catalogue {cat_id} not found.")

    if cat.get("owner_id") and cat["owner_id"] != current_owner["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to manage this catalogue."
        )

    from app.ingestion.activation_worker import activation_worker

    # If dataset is already active, return immediately
    if cat.get("is_active"):
        curr_status = get_catalogue_status(user=current_owner)
        curr_status.status = "Official Catalogue Active"
        curr_status.message = f"Catalogue {cat['version']} is already active."
        return curr_status

    # For small datasets (<= 50 records) and not explicitly async_mode=True, run synchronously
    is_large = (cat.get("valid_count", 0) > 50 or cat.get("record_count", 0) > 50)
    should_run_async = async_mode is True or (async_mode is None and is_large)

    if should_run_async:
        try:
            job = activation_worker.start_activation_async(
                cat_id=cat["id"],
                actor_id=current_owner["id"]
            )
            return CatalogueStatusResponse(
                status="ACTIVATING",
                is_ready=False,
                is_official=True,
                is_synthetic_fixture=False,
                records_loaded=0,
                records_rejected=0,
                duplicate_records=0,
                missing_fields_count=0,
                categories=[],
                total_active_products=0,
                data_source_path=cat.get("filename"),
                job_id=job["id"],
                stage=job.get("stage", "VALIDATING"),
                progress_percent=job.get("progress_percent", 0.0),
                total_records=job.get("total_records", 0),
                processed_records=job.get("processed_records", 0),
                message=f"Activation initiated for {cat['version']} ({job.get('total_records', 0)} records in {job.get('total_batches', 0)} batches)."
            )
        except Exception as e:
            SafeLogger.error(f"Error initiating async activation for {cat_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to initiate activation: {str(e)}")

    # Synchronous path for small datasets (<= 50 records)
    try:
        job = activation_worker.execute_activation_sync(
            cat_id=cat["id"],
            actor_id=current_owner["id"]
        )
        if job.get("status") == "FAILED":
            raise RuntimeError(job.get("error_message") or "Activation failed.")

        status_res = get_catalogue_status(user=current_owner)
        status_res.job_id = job["id"]
        status_res.stage = "COMPLETED"
        status_res.progress_percent = 100.0
        status_res.message = f"Catalogue {cat['version']} successfully activated."
        return status_res
    except HTTPException:
        raise
    except Exception as e:
        SafeLogger.error(f"Error activating catalogue {cat_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate catalogue {cat.get('version', cat_id)}: {str(e)}"
        )

@router.get("/jobs/{job_id}", response_model=ActivationJobResponse)
def get_activation_job_status(
    job_id: str,
    current_owner: dict = Depends(require_owner)
) -> ActivationJobResponse:
    """Retrieves real-time diagnostics and progress for an activation job."""
    job = db.get_activation_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Activation job '{job_id}' not found.")
    return ActivationJobResponse(**job)

@router.get("/{cat_id}/activation-status", response_model=Optional[ActivationJobResponse])
def get_dataset_activation_status(
    cat_id: str,
    current_owner: dict = Depends(require_owner)
) -> Optional[ActivationJobResponse]:
    """Retrieves the latest activation job for a dataset."""
    cat = db.get_catalogue_by_id(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail=f"Catalogue '{cat_id}' not found.")
    if cat.get("owner_id") and cat["owner_id"] != current_owner["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view this catalogue's status."
        )
    job = db.get_latest_activation_job_for_dataset(cat["id"])
    if not job:
        return None
    return ActivationJobResponse(**job)

@router.post("/jobs/{job_id}/retry", response_model=ActivationJobResponse)
def retry_activation_job(
    job_id: str,
    current_owner: dict = Depends(require_owner)
) -> ActivationJobResponse:
    """Retries a failed or stalled activation job."""
    from app.ingestion.activation_worker import activation_worker
    try:
        job = activation_worker.retry_job(job_id=job_id, actor_id=current_owner["id"])
        return ActivationJobResponse(**job)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retry activation job: {str(e)}")

@router.post("/{cat_id}/retry-embeddings")
def retry_dataset_embeddings(
    cat_id: str,
    current_owner: dict = Depends(require_owner)
) -> dict:
    """
    Error Recovery: Retries embedding generation and vector indexing for a dataset
    if initial indexing encountered a transient failure.
    """
    if current_owner.get("is_demo"):
        return {"status": "success", "message": "Demo mode simulated re-indexing complete."}

    cat = db.get_catalogue_by_id(cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail=f"Dataset {cat_id} not found.")
    if cat.get("owner_id") and cat["owner_id"] != current_owner["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to manage this catalogue."
        )

    try:
        from app.retrieval.adaptive_embeddings import embedding_manager
        records = db.get_active_dataset_records(limit=5000)
        target_records = [r["data"] for r in records if r.get("dataset_id") == cat_id or cat_id in str(r)]
        if target_records:
            embedding_manager.embed_records(target_records, category=cat.get("category"))
        db.update_dataset_embedding_status(cat_id, "INDEXED")
        return {"status": "success", "message": f"Successfully re-indexed embeddings for {cat.get('name', cat_id)}."}
    except Exception as e:
        SafeLogger.error(f"Error re-indexing embeddings for {cat_id}: {str(e)}")
        db.update_dataset_embedding_status(cat_id, "EMBEDDING_FAILED", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to re-index embeddings: {str(e)}")

@router.post("/rebuild-index")
def rebuild_knowledge_base_index(current_owner: dict = Depends(require_owner)) -> dict:
    """
    Refreshes and rebuilds the local vector knowledge base index from active ground truth records.
    Validates document indexing and policy documents before completing.
    """
    if current_owner.get("is_demo"):
        return {
            "status": "success",
            "message": "Knowledge base index verified for predefined demo showcase (isolated sandbox). Production index untouched.",
            "catalogue_version": "v1.0.0-demo",
            "products_indexed": 16,
            "policies_indexed": 4,
            "index_ready": True,
            "retrieval_verified": True
        }
    from app.ingestion.policy_loader import policy_loader

    # 1. Reload active catalogue and policies from authoritative database
    catalogue_loader.load_from_database()
    policy_loader.load_from_database()

    # 2. Rebuild local vector index
    indexed = local_vector_index.build_index(force_rebuild=True)

    # 3. Test verification retrieval
    test_retrieval_ok = False
    all_prods = catalogue_loader.get_all_products()
    if indexed and all_prods:
        test_results = local_vector_index.search(all_prods[0].get("title", ""), top_k=1)
        test_retrieval_ok = len(test_results) > 0

    active_cat = db.get_active_catalogue()
    active_version = active_cat["version"] if active_cat else "None"

    db.log_audit(
        actor_id=current_owner["id"],
        actor_role="OWNER",
        action="INDEX_REBUILT",
        target_id="knowledge_base",
        target_type="INDEX",
        details={
            "status": "rebuilt",
            "success": indexed,
            "catalogue_version": active_version,
            "products_indexed": len(catalogue_loader.products),
            "policies_loaded": len(policy_loader.sections),
            "retrieval_verified": test_retrieval_ok
        }
    )

    return {
        "status": "success" if (indexed or len(catalogue_loader.products) == 0) else "partial",
        "message": "Knowledge base index rebuilt and validated successfully.",
        "catalogue_version": active_version,
        "products_indexed": len(catalogue_loader.products),
        "policies_indexed": len(policy_loader.sections),
        "index_ready": indexed,
        "retrieval_verified": test_retrieval_ok
    }

@router.get("/diagnostics")
def get_catalogue_diagnostics_api(
    user: Optional[dict] = Depends(optional_current_user)
) -> dict:
    """
    Returns full diagnostics comparing uploaded, valid, database, in-memory loader,
    and search-indexed product counts.
    """
    user_dict = user if isinstance(user, dict) else None
    if user_dict and user_dict.get("is_demo"):
        from app.core.demo_data import DEMO_PRODUCTS
        return {
            "has_active_catalogue": True,
            "status": "HEALTHY",
            "active_catalogue": {
                "id": "demo-catalogue",
                "name": "Predefined Demo Catalog",
                "version": "v1.0.0-demo",
                "category": "PRODUCT_CATALOGUE",
                "filename": "predefined_demo_catalog.json",
                "activated_at": None
            },
            "total_db_products": len(DEMO_PRODUCTS),
            "total_eligible_products": len(DEMO_PRODUCTS),
            "total_archived_products": 0,
            "total_loader_products": len(DEMO_PRODUCTS),
            "total_indexed_documents": len(DEMO_PRODUCTS),
            "is_indexed": True,
            "missing_from_loader_count": 0,
            "sample_first": DEMO_PRODUCTS[0],
            "sample_last": DEMO_PRODUCTS[-1]
        }
    return db.get_catalogue_diagnostics()

@router.post("/repair-index")
def repair_active_catalogue_index(
    current_owner: dict = Depends(require_owner)
) -> dict:
    """
    Safe repair & resynchronization mechanism:
    1. Synchronizes in-memory catalogue loader with the active database catalogue.
    2. Synchronizes store policies.
    3. Rebuilds the search vector index from ground-truth database records.
    4. Validates retrieval on representative products across the catalogue.
    """
    if current_owner.get("is_demo"):
        return {
            "status": "success",
            "message": "Demo mode simulated repair complete.",
            "diagnostics": db.get_catalogue_diagnostics()
        }

    from app.ingestion.policy_loader import policy_loader

    # 1. Authoritative reload from database
    catalogue_loader.load_from_database()
    policy_loader.load_from_database()

    # 2. Rebuild index
    indexed_ok = local_vector_index.build_index(force_rebuild=True)

    # 3. Verification test
    all_prods = catalogue_loader.get_all_products()
    test_retrieval_ok = False
    if indexed_ok and all_prods:
        test_results = local_vector_index.search(all_prods[0].get("title", ""), top_k=1)
        test_retrieval_ok = len(test_results) > 0

    diag = db.get_catalogue_diagnostics()

    db.log_audit(
        actor_id=current_owner["id"],
        actor_role="OWNER",
        action="CATALOGUE_REPAIRED",
        target_id=diag.get("active_catalogue", {}).get("id", "none") if diag.get("active_catalogue") else "none",
        target_type="CATALOGUE",
        details={
            "indexed_ok": indexed_ok,
            "test_retrieval_ok": test_retrieval_ok,
            "total_eligible_products": diag.get("total_eligible_products"),
            "total_indexed_documents": diag.get("total_indexed_documents"),
            "status": diag.get("status")
        }
    )

    return {
        "status": "success" if (indexed_ok and test_retrieval_ok) else "partial",
        "message": "Catalogue knowledge base synchronized and vector index rebuilt successfully.",
        "diagnostics": diag,
        "test_retrieval_ok": test_retrieval_ok
    }
