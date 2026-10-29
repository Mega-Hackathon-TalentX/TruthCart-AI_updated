import os
import uuid
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.retrieval.semantic_search import local_vector_index
from app.ingestion.activation_worker import activation_worker

client = TestClient(app)

def get_owner_headers():
    resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    assert resp.status_code == 200, f"Owner login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_small_dataset_sync_activation():
    """Small datasets (<= 50 records) activate promptly and remain 100% backwards-compatible."""
    headers = get_owner_headers()
    v_tag = f"v_small_{uuid.uuid4().hex[:6]}"

    records = [
        {
            "product_id": f"TC-SM-{i:03d}",
            "title": f"Small Test Gadget {i}",
            "description": f"Quality accessory number {i}",
            "category": "Electronics >> Accessories",
            "price": 499.0 + (i * 10),
            "stock_status": "In Stock",
            "rating": 4.5,
            "attributes": {"color": "Black", "weight": "150g"}
        }
        for i in range(1, 11)
    ]

    imp_resp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Small Test Catalogue",
        "filename": "small_catalogue.json",
        "version": v_tag,
        "valid_count": len(records),
        "invalid_count": 0,
        "records": records,
        "validation_report": {"valid": len(records), "errors": []},
        "category": "PRODUCT_CATALOGUE"
    })
    assert imp_resp.status_code == 200
    cat_id = imp_resp.json()["id"]

    # Small dataset synchronous activation
    act_resp = client.post(f"/api/catalogue/{cat_id}/activate", headers=headers)
    assert act_resp.status_code == 200
    data = act_resp.json()
    assert data["total_active_products"] == len(records)
    assert data["is_ready"] is True

    # Verify active in DB
    cat = db.get_catalogue_by_id(cat_id)
    assert cat["is_active"] == 1
    assert cat["status"] == "ACTIVE"


def test_large_dataset_5000_records_batched_activation():
    """
    Tests uploading and activating a 5,000-record catalogue.
    Verifies batch processing, non-blocking asynchronous response,
    job polling, progress updates, and completion.
    """
    headers = get_owner_headers()
    v_tag = f"v_large_{uuid.uuid4().hex[:6]}"

    # Generate 5,000 synthetic product records
    total_recs = 5000
    records = [
        {
            "product_id": f"TC-LG-{i:05d}",
            "title": f"High Capacity PowerCore {i}",
            "description": f"Universal portable battery model {i} with rapid charging.",
            "category": "Electronics >> Power Banks",
            "price": 1499.0 + (i % 500),
            "stock_status": "In Stock",
            "rating": 4.2,
            "attributes": {"capacity": f"{10000 + (i * 100)} mAh", "brand": "PowerCore"}
        }
        for i in range(1, total_recs + 1)
    ]

    # Step 1: Import 5,000 records
    imp_resp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Large 5000 Product Catalogue",
        "filename": "truthcart_products_5000.csv",
        "version": v_tag,
        "valid_count": total_recs,
        "invalid_count": 0,
        "records": records,
        "validation_report": {"valid": total_recs, "errors": []},
        "category": "MARKETPLACE_LISTINGS" # Test marketplace listings classification as well
    })
    assert imp_resp.status_code == 200
    cat_id = imp_resp.json()["id"]

    # Step 2: Trigger activation (should return asynchronously with job_id immediately)
    t0 = time.time()
    act_resp = client.post(f"/api/catalogue/{cat_id}/activate", headers=headers)
    t1 = time.time()

    assert act_resp.status_code == 200
    init_data = act_resp.json()
    assert t1 - t0 < 3.0, "Activation initiation must return promptly (< 3s)"
    assert init_data["job_id"] is not None
    assert init_data["status"] == "ACTIVATING"
    job_id = init_data["job_id"]

    # Step 3: Poll activation job endpoint until terminal state
    max_wait_seconds = 45
    poll_start = time.time()
    completed = False
    last_status = None
    last_progress = 0

    while time.time() - poll_start < max_wait_seconds:
        status_resp = client.get(f"/api/catalogue/jobs/{job_id}", headers=headers)
        assert status_resp.status_code == 200
        job_info = status_resp.json()
        last_status = job_info["status"]
        last_progress = job_info["progress_percent"]

        assert job_info["total_records"] == total_recs
        assert job_info["total_batches"] == 50 # 5000 / 100 = 50 batches

        if last_status == "ACTIVE":
            completed = True
            break
        elif last_status == "FAILED":
            pytest.fail(f"Activation job failed with error: {job_info.get('error_message')}")

        time.sleep(0.5)

    assert completed is True, f"Activation did not complete within {max_wait_seconds}s (last status: {last_status}, progress: {last_progress}%)"

    # Step 4: Verify catalogue and products are truly active
    cat = db.get_catalogue_by_id(cat_id)
    assert cat["is_active"] == 1
    assert cat["status"] == "ACTIVE"

    # Step 5: Test customer search against newly activated 5000-record dataset
    search_resp = client.get("/api/products?search=PowerCore+00042")
    assert search_resp.status_code == 200
    prod_data = search_resp.json()
    assert prod_data["total"] >= 1
    found_item = prod_data["products"][0]
    assert "PowerCore" in found_item["title"]


def test_duplicate_activation_click_protection():
    """Triggering activation while a job is running returns the active job rather than duplicate workers."""
    headers = get_owner_headers()
    v_tag = f"v_dup_{uuid.uuid4().hex[:6]}"

    records = [
        {"product_id": f"TC-D-{i}", "title": f"Item {i}", "price": 99.0, "stock_status": "In Stock", "category": "General"}
        for i in range(1, 150)
    ]

    imp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Dup Test Cat",
        "filename": "dup.csv",
        "version": v_tag,
        "valid_count": len(records),
        "invalid_count": 0,
        "records": records,
        "validation_report": {"valid": len(records)},
        "category": "PRODUCT_CATALOGUE"
    }).json()

    # First click
    call1 = client.post(f"/api/catalogue/{imp['id']}/activate", headers=headers).json()
    # Second click immediately
    call2 = client.post(f"/api/catalogue/{imp['id']}/activate", headers=headers).json()

    # Must return same job_id
    assert call1["job_id"] == call2["job_id"]


def test_already_active_catalogue_activation():
    """Activating an already active catalogue returns immediately with ACTIVE status and zero reprocessing."""
    headers = get_owner_headers()
    active_cat = db.get_active_catalogue()
    assert active_cat is not None

    resp = client.post(f"/api/catalogue/{active_cat['id']}/activate", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("Official Catalogue Active", "ACTIVE")
    assert "already active" in data.get("message", "").lower()

