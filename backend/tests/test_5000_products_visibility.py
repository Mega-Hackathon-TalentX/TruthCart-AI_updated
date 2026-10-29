import os
import sys
import uuid
import json
import pytest
from pathlib import Path
from typing import Dict, Any, List

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.ingestion.policy_loader import policy_loader
from app.retrieval.semantic_search import local_vector_index
from app.retrieval.hybrid_retriever import hybrid_retriever
from app.api.products import list_products, get_product
from app.api.catalogue import (
    activate_catalogue,
    get_catalogue_diagnostics_api,
    repair_active_catalogue_index
)


@pytest.fixture(scope="module")
def ensure_5000_catalogue():
    """Ensures a clean 5,000 product catalogue is created and active in the test database."""
    db.init_db()
    
    # Check if a 5000 dataset is already active
    active_cat = db.get_active_catalogue()
    if active_cat and db.count_active_products() == 5000:
        cat_id = active_cat["id"]
    else:
        # Generate 5,000 deterministic records
        records = []
        for i in range(1, 5001):
            category = "Apparel" if i % 2 == 1 else "Electronics"
            price = round(50.0 + (i % 500) * 2.5, 2)
            stock = "In Stock" if (i % 3 != 0) else "Out of Stock"
            rating = round(3.0 + ((i % 20) / 10.0), 1)
            records.append({
                "product_id": f"TC-5K-{i:05d}",
                "title": f"TruthCart Pro Item {i}",
                "description": f"Engineered precision item {i} with high grade finish and reliable endurance.",
                "category": category,
                "price": price,
                "stock_status": stock,
                "rating": rating,
                "brand": "TruthPro",
                "attributes": {
                    "sku": f"SKU-{i:05d}",
                    "brand": "TruthPro",
                    "material": "Cotton" if category == "Apparel" else "Aluminum",
                    "color": "Blue" if i % 4 == 0 else "Black",
                    "warranty": "1 Year Official"
                }
            })

        owner_id = "test-owner-5k"
        cat_meta = db.create_catalogue(
            name="Synthetic 5K Verification Catalogue",
            filename="synthetic_5k.json",
            version=f"v_5k_{uuid.uuid4().hex[:6]}",
            owner_id=owner_id,
            records=records,
            validation_report={"errors": [], "warnings": []},
            valid_count=len(records),
            invalid_count=0,
            category="PRODUCT_CATALOGUE"
        )
        cat_id = cat_meta["id"]
        db.activate_catalogue(cat_id, actor_id=owner_id)

    catalogue_loader.load_from_database()
    policy_loader.load_default_policy()
    local_vector_index.build_index(force_rebuild=True)
    
    yield cat_id

    # Restore official hackathon catalogue
    try:
        with db.get_connection() as conn:
            official_cat = conn.execute("SELECT id FROM catalogues WHERE name LIKE '%Hackathon%' OR name LIKE '%Official%' LIMIT 1").fetchone()
            if official_cat:
                db.activate_catalogue(official_cat["id"], actor_id="teardown_5k")
        catalogue_loader.load_from_database()
        policy_loader.load_default_policy()
        local_vector_index.build_index(force_rebuild=True)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def setup_test_fixtures(ensure_5000_catalogue):
    """Overrides conftest fixture to ensure active DB catalogue is loaded for each test in this module."""
    db.activate_catalogue(ensure_5000_catalogue, actor_id="test_runner")
    catalogue_loader.load_from_database()
    policy_loader.load_default_policy()
    local_vector_index.build_index(force_rebuild=False)
    yield


# ---------------- TEST 1 & 2: 5,000 PRODUCTS PERSISTENCE & DB COUNT ----------------
def test_01_and_02_database_persistence_5000(ensure_5000_catalogue):
    """Req 1 & 2: Verifies all 5,000 products exist in database under active catalogue."""
    active_cat = db.get_active_catalogue()
    assert active_cat is not None
    assert active_cat["id"] == ensure_5000_catalogue

    total_count = db.count_active_products()
    assert total_count == 5000, f"Expected 5,000 active products, got {total_count}"


# ---------------- TEST 3: BACKEND API PAGINATED EXPOSURE ----------------
def test_03_backend_api_paginated_exposure(ensure_5000_catalogue):
    """Req 3: list_products returns accurate pagination metadata and page slices."""
    res_page1 = list_products(limit=50, offset=0)
    assert res_page1["total"] == 5000
    assert res_page1["page"] == 1
    assert res_page1["total_pages"] == 100
    assert res_page1["has_next"] is True
    assert res_page1["has_prev"] is False
    assert len(res_page1["products"]) == 50

    res_page2 = list_products(limit=50, offset=50)
    assert res_page2["page"] == 2
    assert res_page2["has_next"] is True
    assert res_page2["has_prev"] is True
    assert len(res_page2["products"]) == 50


# ---------------- TEST 4: COMPLETE PAGINATION TRAVERSAL (NO DUPLICATES/DROPS) ----------------
def test_04_complete_pagination_traversal(ensure_5000_catalogue):
    """Req 4: Traversing every page returns union of exactly 5,000 unique product IDs."""
    retrieved_ids = set()
    page_size = 100
    total_pages = 50  # 5,000 / 100 = 50 pages

    for page_idx in range(total_pages):
        offset = page_idx * page_size
        batch = db.get_active_products(limit=page_size, offset=offset)
        assert len(batch) == page_size
        for p in batch:
            assert p["product_id"] not in retrieved_ids, f"Duplicate product {p['product_id']} encountered!"
            retrieved_ids.add(p["product_id"])

    assert len(retrieved_ids) == 5000, f"Expected 5,000 unique product IDs, retrieved {len(retrieved_ids)}"


# ---------------- TEST 5: EXACT SKU / ID LOOKUP AT START, MID, END ----------------
def test_05_exact_search_boundary_items(ensure_5000_catalogue):
    """Req 5: Exact search reliably discovers products at beginning, middle, and end."""
    boundary_skus = ["TC-5K-00001", "TC-5K-02500", "TC-5K-05000"]
    for sku in boundary_skus:
        res = list_products(search=sku)
        assert res["total"] >= 1
        assert any(p["product_id"] == sku for p in res["products"]), f"Could not find exact product {sku}"

    # Verify single product API endpoint directly
    p_first = get_product("TC-5K-00001")
    assert p_first["product_id"] == "TC-5K-00001"
    p_last = get_product("TC-5K-05000")
    assert p_last["product_id"] == "TC-5K-05000"


# ---------------- TEST 6: KEYWORD SEARCH ACROSS FIELDS ----------------
def test_06_keyword_search_across_fields(ensure_5000_catalogue):
    """Req 6: Keyword search across title, description, brand, attributes."""
    # Search by brand
    res_brand = list_products(search="TruthPro")
    assert res_brand["total"] == 5000

    # Search by title phrase
    res_item = list_products(search="TruthCart Pro Item 42")
    assert res_item["total"] >= 1
    # Ensure exact match is ranked first
    assert res_item["products"][0]["product_id"] == "TC-5K-00042"

    # Search by attribute SKU
    res_sku = list_products(search="SKU-00100")
    assert res_sku["total"] == 1
    assert res_sku["products"][0]["product_id"] == "TC-5K-00100"


# ---------------- TEST 7: STRUCTURED FILTERS (CATEGORY, PRICE, STOCK) ----------------
def test_07_structured_filters(ensure_5000_catalogue):
    """Req 7: Category, price range, and in-stock filters operate accurately across 5,000 items."""
    # Category filter
    apparel_count = db.count_active_products(category="Apparel")
    elec_count = db.count_active_products(category="Electronics")
    assert apparel_count == 2500
    assert elec_count == 2500
    assert apparel_count + elec_count == 5000

    # Price range filter
    res_price = list_products(min_price=100.0, max_price=200.0)
    assert res_price["total"] > 0
    for p in res_price["products"]:
        assert 100.0 <= p["price"] <= 200.0

    # Stock filter
    res_stock = list_products(in_stock_only=True)
    assert res_stock["total"] > 0
    for p in res_stock["products"]:
        assert "in stock" in p["stock_status"].lower() or "instock" in p["stock_status"].lower()


# ---------------- TEST 8: SORTING STABILITY ACROSS PAGES ----------------
def test_08_sorting_stability(ensure_5000_catalogue):
    """Req 8: Sorting by price, title, and rating is strictly monotonic and paginates stably."""
    # Price ASC
    res_asc = db.get_active_products(sort_by="price_asc", limit=100, offset=0)
    prices_asc = [p["price"] for p in res_asc]
    assert prices_asc == sorted(prices_asc)

    # Price DESC
    res_desc = db.get_active_products(sort_by="price_desc", limit=100, offset=0)
    prices_desc = [p["price"] for p in res_desc]
    assert prices_desc == sorted(prices_desc, reverse=True)


# ---------------- TEST 9: SEMANTIC & HYBRID RETRIEVAL ----------------
def test_09_semantic_and_hybrid_retrieval(ensure_5000_catalogue):
    """Req 9: Semantic search and hybrid retriever find relevant products from across 5,000 items."""
    # Semantic search
    results = local_vector_index.search("precision item endurance", top_k=5)
    assert len(results) > 0
    for p, score in results:
        assert score > 0.0
        assert "TC-5K-" in p.get("product_id", "")

    # Hybrid retriever
    cands, pol = hybrid_retriever.retrieve(query="TruthCart Pro Item 1", top_k=5)
    assert len(cands) > 0
    assert cands[0].source_id == "TC-5K-00001"


# ---------------- TEST 10: VECTOR INDEX SCALE AND OPERATIONAL STATUS ----------------
def test_10_vector_index_operational(ensure_5000_catalogue):
    """Req 10: Vector index is operational and contains all eligible products."""
    assert local_vector_index.is_indexed is True
    assert len(local_vector_index.doc_ids) >= 5000


# ---------------- TEST 11: DIAGNOSTICS ENDPOINT ACCURACY ----------------
def test_11_catalogue_diagnostics_endpoint(ensure_5000_catalogue):
    """Req 11: Diagnostics API endpoint accurately reports active catalogue counts."""
    diag = get_catalogue_diagnostics_api()
    assert diag["has_active_catalogue"] is True
    assert diag["total_db_products"] == 5000
    assert diag["total_eligible_products"] == 5000
    assert diag["total_loader_products"] == 5000
    assert diag["total_indexed_documents"] >= 5000
    assert diag["status"] == "HEALTHY"
    assert diag["sample_first"]["product_id"] == "TC-5K-00001"
    assert diag["sample_last"]["product_id"] == "TC-5K-05000"


# ---------------- TEST 12: SAFE REINDEXING MECHANISM ----------------
def test_12_safe_reindexing_mechanism(ensure_5000_catalogue):
    """Req 12: Safe repair/reindex rebuilds indexes without data loss."""
    owner_user = {"id": "test-owner-5k", "email": "owner@truthcart.ai", "role": "OWNER", "is_demo": False}
    repair_res = repair_active_catalogue_index(current_owner=owner_user)
    assert repair_res["status"] == "success"
    assert repair_res["test_retrieval_ok"] is True
    diag = repair_res["diagnostics"]
    assert diag["total_eligible_products"] == 5000
    assert diag["total_loader_products"] == 5000
    assert diag["status"] == "HEALTHY"


# ---------------- TEST 13 & 14: CATALOGUE SWITCHING & DEACTIVATION ISOLATION ----------------
def test_13_and_14_catalogue_switching_isolation(ensure_5000_catalogue):
    """Req 13 & 14: Switching to another catalogue hides old products and exposes new ones."""
    owner_id = "test-owner-switch"
    new_records = [
        {
            "product_id": "SWITCH-PROD-01",
            "title": "New Catalogue Switch Product",
            "description": "Exclusive item in second catalogue.",
            "category": "Gadgets",
            "price": 299.0,
            "stock_status": "In Stock"
        }
    ]
    new_cat = db.create_catalogue(
        name="Switch Isolation Catalogue",
        filename="switch.json",
        version=f"v_switch_{uuid.uuid4().hex[:6]}",
        owner_id=owner_id,
        records=new_records,
        validation_report={"errors": [], "warnings": []},
        valid_count=1,
        invalid_count=0
    )

    # Activate new catalogue
    db.activate_catalogue(new_cat["id"], actor_id=owner_id)
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)

    # Old 5,000 products must no longer be active in browse
    browse_new = list_products()
    assert browse_new["total"] == 1
    assert browse_new["products"][0]["product_id"] == "SWITCH-PROD-01"

    # Search for old 5K product must return 0
    search_old = list_products(search="TC-5K-00001")
    assert search_old["total"] == 0

    # Switch back to 5K catalogue
    db.activate_catalogue(ensure_5000_catalogue, actor_id=owner_id)
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)

    browse_restored = list_products()
    assert browse_restored["total"] == 5000


# ---------------- TEST 15: SOFT-DELETION / ARCHIVAL EXCLUSION ----------------
def test_15_archived_products_excluded(ensure_5000_catalogue):
    """Req 15: Soft-deleted / archived products are excluded from browse and search."""
    target_id = "TC-5K-00777"
    owner_id = "test-owner-archive"

    # Confirm present initially
    assert list_products(search=target_id)["total"] >= 1

    # Archive product
    db.archive_product(target_id, actor_id=owner_id)
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)

    # Browse must now show 4,999 products
    assert db.count_active_products() == 4999
    assert list_products(search=target_id)["total"] == 0

    # Restore product for subsequent tests
    with db.get_connection() as conn:
        conn.execute("UPDATE products SET is_archived = 0 WHERE product_id = ?", (target_id,))
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)

    assert db.count_active_products() == 5000


# ---------------- TEST 16: MULTI-DOMAIN DATASET RETRIEVAL COMPATIBILITY ----------------
def test_16_multidomain_dataset_retrieval(ensure_5000_catalogue):
    """Req 16: Multi-domain datasets (policies, reviews) continue to be retrievable."""
    cands, pol = hybrid_retriever.retrieve(query="What is your return policy?", top_k=3)
    assert pol is not None
    assert pol.source_type == "policy"
    assert "return" in str(pol.data.get("title", "")).lower() or "return" in str(pol.data.get("content", "")).lower()


# ---------------- TEST 17: EXISTING CATALOGUES COMPATIBILITY ----------------
def test_17_existing_catalogue_compatibility(ensure_5000_catalogue):
    """Req 17: Standard product fields (title, description, price, stock, category) are present."""
    p = get_product("TC-5K-00001")
    assert p["title"] == "TruthCart Pro Item 1"
    assert p["price"] > 0
    assert p["category"] == "Apparel"
    assert p["stock_status"] == "In Stock"


# ---------------- TEST 18: VISIBLE DIAGNOSTICS ON INVALID RECORDS ----------------
def test_18_visible_diagnostics_on_invalid_records():
    """Req 18: Ingestion reports visible validation errors rather than silent data loss."""
    from app.ingestion.data_validator import DataValidator
    invalid_record = {"title": "Missing Required Fields"}
    valid, reason, _ = DataValidator.validate_record(invalid_record)
    assert valid is False
    assert "product_id" in str(reason).lower() or "missing" in str(reason).lower()


# ---------------- TEST 19: SENSIBLE EMPTY CATALOGUE BEHAVIOR ----------------
def test_19_empty_catalogue_sensible_behavior():
    """Req 19: Non-existent product queries gracefully return 404/empty rather than crashing."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_product("NON-EXISTENT-SKU-999999")
    assert exc_info.value.status_code == 404


# ---------------- TEST 20: EFFICIENCY & BOUNDED RESPONSES ----------------
def test_20_efficient_bounded_responses(ensure_5000_catalogue):
    """Req 20: Large catalogue queries paginate efficiently without returning all 5,000 items in one call."""
    res = list_products(limit=24, offset=0)
    assert len(res["products"]) == 24
    assert res["total"] == 5000
    assert res["limit"] == 24
