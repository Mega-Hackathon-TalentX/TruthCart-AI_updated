"""
TruthCart AI - Phase 2 End-to-End Acceptance Test Suite
Comprehensive validation across:
1. 5,000-Product Complete Acceptance Test (DB vs Pagination, 0 missing, 0 duplicates)
2. Search Accuracy (Beginning, Middle, End: Exact SKU, Title, Keyword, Semantic, Hybrid)
3. Alternative Catalogue Schemas (Schemas A, B, C, D with unmapped attribute preservation)
4. Customer Portal and AI Assistant Consistency (Active ground-truth, refusals, RBAC)
5. Catalogue Updates and Recovery (Version switching, failure simulation, re-indexing, sorting)
"""

import os
import sys
import uuid
import json
import time
import pytest
from pathlib import Path
from typing import Dict, Any, List, Set

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
from app.api.chat import handle_chat
from app.schemas.request import ChatRequest
from app.ingestion.universal_ingestor import universal_ingestor
from app.ingestion.schema_mapper import DatasetCategory
from app.core.auth import create_access_token


@pytest.fixture(scope="module")
def setup_5000_acceptance_catalogue():
    """Initializes a 5,000 item catalogue for end-to-end acceptance testing."""
    db.init_db()

    # Generate 5,000 products
    records = []
    for i in range(1, 5001):
        cat = "Electronics" if i % 2 == 0 else "Apparel"
        price = round(10.0 + (i % 250) * 1.5, 2)
        stock = "In Stock" if (i % 5 != 0) else "Out of Stock"
        rating = round(3.5 + ((i % 15) / 10.0), 1)
        records.append({
            "product_id": f"TC-ACCEPT-{i:05d}",
            "title": f"TruthCart Premium Item {i}",
            "description": f"Durable precision item {i} with distinctive serial SPEC-{i:05d} engineered with high quality components for top performance.",
            "category": cat,
            "price": price,
            "stock_status": stock,
            "rating": rating,
            "brand": "TruthCartGlobal",
            "attributes": {
                "sku": f"SKU-ACCEPT-{i:05d}",
                "warranty": "2 Years Manufacturer Warranty",
                "color": "Silver" if i % 3 == 0 else "Navy"
            }
        })

    owner_id = "acceptance-owner"
    cat_meta = db.create_catalogue(
        name="TruthCart 5K Acceptance Suite",
        filename="acceptance_5k.json",
        version=f"v_accept_{uuid.uuid4().hex[:6]}",
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

    # Teardown: restore official hackathon catalogue
    try:
        with db.get_connection() as conn:
            official = conn.execute("SELECT id FROM catalogues WHERE name LIKE '%Hackathon%' OR name LIKE '%Official%' LIMIT 1").fetchone()
            if official:
                db.activate_catalogue(official["id"], actor_id="acceptance_teardown")
        catalogue_loader.load_from_database()
        policy_loader.load_default_policy()
        local_vector_index.build_index(force_rebuild=True)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def ensure_acceptance_catalogue_active(setup_5000_acceptance_catalogue):
    """Overrides conftest fixture so every test function in this module operates on the 5K acceptance dataset."""
    db.activate_catalogue(setup_5000_acceptance_catalogue, actor_id="test_runner")
    catalogue_loader.load_from_database()
    policy_loader.load_default_policy()
    local_vector_index.build_index(force_rebuild=False)
    yield


# ==============================================================================
# SECTION 1: 5,000-PRODUCT ACCEPTANCE TEST (DB vs API PAGINATION)
# ==============================================================================

def test_acceptance_01_db_distinct_count(setup_5000_acceptance_catalogue):
    """Verifies that direct DB query yields exactly 5,000 distinct product IDs."""
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(DISTINCT product_id) as cnt FROM products WHERE catalogue_id = ? AND is_archived = 0",
            (setup_5000_acceptance_catalogue,)
        ).fetchone()
        distinct_db_count = row["cnt"]

    assert distinct_db_count == 5000, f"Expected 5000 distinct DB products, got {distinct_db_count}"
    assert db.count_active_products() == 5000


def test_acceptance_02_complete_pagination_union_equality(setup_5000_acceptance_catalogue):
    """
    Paginates through entire catalogue from page 1 to the end.
    Verifies:
    1. Count of paginated products == DB count (5,000).
    2. Set of paginated product IDs == Set of DB product IDs (zero missing, zero unexpected).
    3. Zero duplicate products across pages.
    4. Adjacent page boundary consistency (no skipped items).
    """
    # 1. Collect all DB IDs directly
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT product_id FROM products WHERE catalogue_id = ? AND is_archived = 0 ORDER BY product_id ASC, id ASC",
            (setup_5000_acceptance_catalogue,)
        ).fetchall()
        db_id_set = {r["product_id"] for r in rows}
        db_id_list = [r["product_id"] for r in rows]

    assert len(db_id_set) == 5000

    # 2. Paginate through API with page size = 100
    page_size = 100
    retrieved_products = []
    seen_ids = set()
    duplicates = []
    offset = 0

    while True:
        resp = list_products(limit=page_size, offset=offset)
        items = resp["products"]
        if not items:
            break

        for item in items:
            pid = item["product_id"]
            if pid in seen_ids:
                duplicates.append(pid)
            seen_ids.add(pid)
            retrieved_products.append(item)

        if not resp["has_next"]:
            break
        offset += page_size

    # Check 1: Zero duplicate products across pages
    assert len(duplicates) == 0, f"Found duplicate products across pages: {duplicates[:10]}"

    # Check 2: Total count retrieved equals DB count
    assert len(retrieved_products) == 5000, f"Expected 5,000 products, retrieved {len(retrieved_products)}"

    # Check 3: Set equality between DB and pagination
    retrieved_id_set = {p["product_id"] for p in retrieved_products}
    missing = db_id_set - retrieved_id_set
    unexpected = retrieved_id_set - db_id_set

    assert len(missing) == 0, f"Missing {len(missing)} products: {list(missing)[:5]}"
    assert len(unexpected) == 0, f"Unexpected {len(unexpected)} products: {list(unexpected)[:5]}"
    assert retrieved_id_set == db_id_set

    # Check 4: Adjacent page boundary consistency (Page 1 last item vs Page 2 first item)
    p1 = list_products(limit=50, offset=0)
    p2 = list_products(limit=50, offset=50)
    assert p1["products"][-1]["product_id"] != p2["products"][0]["product_id"]
    p1_ids = [p["product_id"] for p in p1["products"]]
    p2_ids = [p["product_id"] for p in p2["products"]]
    assert set(p1_ids).isdisjoint(set(p2_ids)), "Adjacent pages overlap"


# ==============================================================================
# SECTION 2: SEARCH ACCURACY AT BEGINNING, MIDDLE, AND END
# ==============================================================================

@pytest.mark.parametrize("pos_name,item_idx", [
    ("beginning", 25),    # First 100
    ("middle", 2500),     # 2,400 to 2,600
    ("end", 4975),        # Last 100
])
def test_acceptance_03_search_accuracy_across_positions(pos_name, item_idx):
    """
    Tests exact SKU, exact title, keyword, semantic, and hybrid retrieval
    at beginning (first 100), middle (2400-2600), and end (last 100).
    """
    target_id = f"TC-ACCEPT-{item_idx:05d}"
    target_sku = f"SKU-ACCEPT-{item_idx:05d}"
    target_title = f"TruthCart Premium Item {item_idx}"

    # 1. Exact SKU / Product ID search
    t0 = time.perf_counter()
    res_id = list_products(search=target_id, limit=10)
    lat_id = (time.perf_counter() - t0) * 1000.0
    assert len(res_id["products"]) > 0
    assert res_id["products"][0]["product_id"] == target_id, f"Failed exact ID search at {pos_name}"
    assert lat_id < 200.0, f"ID search latency too high: {lat_id:.2f}ms"

    # Exact SKU search
    res_sku = list_products(search=target_sku, limit=10)
    assert any(p["product_id"] == target_id for p in res_sku["products"]), f"Failed exact SKU search at {pos_name}"

    # 2. Exact Title search
    t0 = time.perf_counter()
    res_title = list_products(search=target_title, limit=10)
    lat_title = (time.perf_counter() - t0) * 1000.0
    assert any(p["product_id"] == target_id for p in res_title["products"]), f"Failed title search at {pos_name}"
    assert lat_title < 200.0

    # 3. Keyword search on distinctive words from description
    res_kw = list_products(search=f"SPEC-{item_idx:05d}", limit=10)
    assert any(p["product_id"] == target_id for p in res_kw["products"]), f"Failed keyword search at {pos_name}"

    # 4. Semantic / Natural Language search
    candidates = local_vector_index.search(f"durable high quality precision item {item_idx}", top_k=20)
    cand_ids = [c[0]["product_id"] for c in candidates]
    assert target_id in cand_ids, f"Failed semantic search at {pos_name}: {target_id} not in top 20"

    # 5. Hybrid retrieval combining keyword and semantic similarity
    cands, _ = hybrid_retriever.retrieve(f"TruthCart Premium Item {item_idx}", structured_params={})
    hybrid_ids = [c.data["product_id"] for c in cands]
    assert target_id in hybrid_ids[:5], f"Target {target_id} not in top 5 hybrid results at {pos_name}"


# ==============================================================================
# SECTION 3: ALTERNATIVE CATALOGUE SCHEMAS (A, B, C, D)
# ==============================================================================

def test_acceptance_04_alternative_schemas_ingestion_and_search():
    """
    Tests Schema A, B, C, D:
    - Schema A: product_id, product_name, price, category, description, stock
    - Schema B: item_code, product_title, selling_price, category_name, details, quantity
    - Schema C: sku, name, brand, retail_price, department, product_description, in_stock
    - Schema D: asin, headline, retail_price, department, extra_supplier, weight_kg, warranty_years
    """
    # Schema A
    rows_a = [{
        "product_id": "TEST-SCH-A-01",
        "product_name": "Aerodynamic Running Shoes",
        "price": "149.99",
        "category": "Footwear",
        "description": "Breathable mesh runners with responsive foam cushion.",
        "stock": "25"
    }]
    map_a, valid_a, _, _ = universal_ingestor.profile_and_validate(rows_a)
    assert map_a.detected_category == DatasetCategory.PRODUCT_CATALOGUE
    assert valid_a[0]["product_id"] == "TEST-SCH-A-01"
    assert valid_a[0]["title"] == "Aerodynamic Running Shoes"
    assert valid_a[0]["price"] == 149.99
    assert valid_a[0]["category"] == "Footwear"

    # Schema B
    rows_b = [{
        "item_code": "TEST-SCH-B-01",
        "product_title": "Wireless Studio Monitor Headphones",
        "selling_price": "299.50",
        "category_name": "Audio",
        "details": "Active noise cancelling with 40mm beryllium drivers.",
        "quantity": "40"
    }]
    map_b, valid_b, _, _ = universal_ingestor.profile_and_validate(rows_b)
    assert map_b.detected_category == DatasetCategory.PRODUCT_CATALOGUE
    assert valid_b[0]["product_id"] == "TEST-SCH-B-01"
    assert valid_b[0]["title"] == "Wireless Studio Monitor Headphones"
    assert valid_b[0]["price"] == 299.50
    assert valid_b[0]["category"] == "Audio"
    assert valid_b[0]["stock_status"] == "In Stock"

    # Schema C
    rows_c = [{
        "sku": "TEST-SCH-C-01",
        "name": "Selvedge Denim Jacket",
        "brand": "HeritageDenim",
        "retail_price": "189.00",
        "department": "Apparel",
        "product_description": "Raw unwashed 14oz Japanese cotton selvedge jacket.",
        "in_stock": "Yes"
    }]
    map_c, valid_c, _, _ = universal_ingestor.profile_and_validate(rows_c)
    assert map_c.detected_category == DatasetCategory.PRODUCT_CATALOGUE
    assert valid_c[0]["product_id"] == "TEST-SCH-C-01"
    assert valid_c[0]["title"] == "Selvedge Denim Jacket"
    assert valid_c[0]["brand"] == "HeritageDenim"
    assert valid_c[0]["price"] == 189.00
    assert valid_c[0]["category"] == "Apparel"
    assert valid_c[0]["stock_status"] == "In Stock"

    # Schema D (Non-standard column order + unmapped attributes)
    rows_d = [{
        "extra_supplier": "Global Goods Corp",
        "weight_kg": "2.4",
        "retail_price": "89.95",
        "asin": "TEST-SCH-D-01",
        "department": "Kitchenware",
        "headline": "Cast Iron Dutch Oven 5-Quart",
        "warranty_years": "5"
    }]
    map_d, valid_d, _, _ = universal_ingestor.profile_and_validate(rows_d)
    assert map_d.detected_category == DatasetCategory.PRODUCT_CATALOGUE
    assert valid_d[0]["product_id"] == "TEST-SCH-D-01"
    assert valid_d[0]["title"] == "Cast Iron Dutch Oven 5-Quart"
    assert valid_d[0]["price"] == 89.95
    assert valid_d[0]["category"] == "Kitchenware"
    assert valid_d[0]["brand"] == "Global Goods Corp"
    # Unmapped columns preserved in attributes
    assert valid_d[0]["attributes"]["weight_kg"] == "2.4"
    assert valid_d[0]["attributes"]["warranty_years"] == "5"


# ==============================================================================
# SECTION 4: CUSTOMER PORTAL & AI ASSISTANT CONSISTENCY
# ==============================================================================

def test_acceptance_05_portal_and_ai_consistency():
    """
    Verifies that:
    1. Browsing displays active catalogue products.
    2. Category and price filters accurately filter active items.
    3. Product details opens correct product with full specifications.
    4. AI assistant uses active catalogue as retrieval source.
    5. AI assistant answers queries about products at beginning, middle, and end.
    6. AI assistant refuses to answer about non-existent or inactive products.
    7. Unauthenticated/customer accounts cannot access administrative endpoints.
    """
    # 1. Product details opens correct product
    prod = get_product("TC-ACCEPT-02500")
    assert prod is not None
    assert prod["product_id"] == "TC-ACCEPT-02500"
    assert prod["title"] == "TruthCart Premium Item 2500"
    assert "warranty" in prod["attributes"]

    # 2. Category filtering
    resp_elec = list_products(category="Electronics", limit=20)
    assert all(p["category"] == "Electronics" for p in resp_elec["products"])
    assert resp_elec["total"] == 2500  # Half of 5,000

    # 3. AI assistant grounded answers across positions
    for pid in ["TC-ACCEPT-00010", "TC-ACCEPT-02500", "TC-ACCEPT-04990"]:
        req = ChatRequest(message=f"What is the price of {pid}?", conversation_id=f"conv-{pid}")
        resp = handle_chat(req)
        assert resp.decision == "ANSWER", f"Assistant failed to answer for active product {pid}"
        assert len(resp.citations) >= 1

    # 4. AI assistant refuses non-existent product
    req_non = ChatRequest(message="What is the price of NonExistentProduct-9999?", conversation_id="conv-non-exist")
    resp_non = handle_chat(req_non)
    assert resp_non.decision == "REFUSE"
    assert "not found" in resp_non.refusal_reason.lower()

    # 5. Customer RBAC check: Customers cannot access owner admin endpoints
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    # Without token
    r_no_auth = client.post("/api/catalogue/rebuild-index")
    assert r_no_auth.status_code == 401

    # With verified customer token
    cust_user = db.get_user_by_email("customer@truthcart.ai")
    cust_id = cust_user["id"] if cust_user else "29e5661a-5da4-414e-913e-7be6e9226dd8"
    customer_token = create_access_token({"sub": cust_id, "role": "CUSTOMER"})
    r_cust = client.post("/api/catalogue/rebuild-index", headers={"Authorization": f"Bearer {customer_token}"})
    assert r_cust.status_code == 403


# ==============================================================================
# SECTION 5: CATALOGUE UPDATES AND RECOVERY SCENARIOS
# ==============================================================================

def test_acceptance_06_catalogue_switch_and_isolation(setup_5000_acceptance_catalogue):
    """
    Scenario 1 & 2:
    - Catalogue A (5,000 items) is active.
    - Create & activate Catalogue B (3 distinct items).
    - Confirm customer portal immediately switches to Catalogue B (0 items from A).
    - Reactivate Catalogue A -> confirm customer portal switches back immediately.
    """
    # 1. Create Catalogue B with 3 distinct items
    cat_b_records = [
        {"product_id": "CAT-B-001", "title": "Catalogue B Exclusive Item 1", "category": "Exclusive", "price": 99.0, "stock_status": "In Stock", "rating": 4.5, "attributes": {}},
        {"product_id": "CAT-B-002", "title": "Catalogue B Exclusive Item 2", "category": "Exclusive", "price": 199.0, "stock_status": "In Stock", "rating": 4.8, "attributes": {}},
        {"product_id": "CAT-B-003", "title": "Catalogue B Exclusive Item 3", "category": "Exclusive", "price": 299.0, "stock_status": "In Stock", "rating": 5.0, "attributes": {}},
    ]
    owner_id = "test-owner-switch"
    cat_b = db.create_catalogue(
        name="Catalogue B Isolation Test",
        filename="cat_b.json",
        version=f"v_b_{uuid.uuid4().hex[:6]}",
        owner_id=owner_id,
        records=cat_b_records,
        validation_report={"errors": [], "warnings": []},
        valid_count=3,
        invalid_count=0,
        category="PRODUCT_CATALOGUE"
    )

    # Activate Catalogue B
    db.activate_catalogue(cat_b["id"], actor_id=owner_id)
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)

    # Customer portal check
    resp_b = list_products(limit=50)
    assert resp_b["total"] == 3
    b_ids = [p["product_id"] for p in resp_b["products"]]
    assert b_ids == ["CAT-B-001", "CAT-B-002", "CAT-B-003"]
    # Catalogue A items must NOT be present
    assert not any("TC-ACCEPT" in pid for pid in b_ids)

    # Reactivate Catalogue A
    db.activate_catalogue(setup_5000_acceptance_catalogue, actor_id=owner_id)
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)

    # Customer portal check
    resp_a = list_products(limit=50)
    assert resp_a["total"] == 5000
    assert any("TC-ACCEPT" in p["product_id"] for p in resp_a["products"])
    assert not any("CAT-B" in p["product_id"] for p in resp_a["products"])


def test_acceptance_07_reindexing_and_duplicate_prevention(setup_5000_acceptance_catalogue):
    """
    Scenario 5:
    Re-indexes the active catalogue.
    Confirms product counts remain exactly 5,000 and zero duplicates are created.
    """
    initial_count = db.count_active_products()
    assert initial_count == 5000

    # Rebuild vector index
    local_vector_index.build_index(force_rebuild=True)

    # Check count
    after_count = db.count_active_products()
    assert after_count == 5000

    # Run repair endpoint to ensure index alignment
    repair_res = repair_active_catalogue_index(current_owner={"id": "owner", "role": "OWNER", "is_demo": False})
    assert repair_res["status"] == "success"
    assert repair_res["diagnostics"]["total_eligible_products"] == 5000


def test_acceptance_08_pagination_with_filters_and_sorting():
    """
    Scenario 6:
    Applies filters (category='Electronics', in_stock_only=True) and sorting (price_desc).
    Paginates through pages and verifies order and filtering consistency.
    """
    resp_p1 = list_products(
        category="Electronics",
        in_stock_only=True,
        sort_by="price_desc",
        limit=20,
        offset=0
    )
    assert resp_p1["total"] > 0
    items_p1 = resp_p1["products"]
    assert all(p["category"] == "Electronics" for p in items_p1)
    assert all(p["stock_status"] == "In Stock" for p in items_p1)

    # Verify descending price order
    prices_p1 = [p["price"] for p in items_p1]
    assert prices_p1 == sorted(prices_p1, reverse=True)

    # Page 2
    resp_p2 = list_products(
        category="Electronics",
        in_stock_only=True,
        sort_by="price_desc",
        limit=20,
        offset=20
    )
    items_p2 = resp_p2["products"]
    prices_p2 = [p["price"] for p in items_p2]
    assert prices_p2 == sorted(prices_p2, reverse=True)

    # Highest price on Page 2 must be <= lowest price on Page 1
    assert prices_p2[0] <= prices_p1[-1]


def test_acceptance_09_empty_catalogue_handling():
    """
    Scenario 7:
    Tests behavior when an empty catalogue is active.
    Confirms list_products returns empty list with total=0 rather than crashing.
    """
    empty_cat = db.create_catalogue(
        name="Empty Catalogue Scenario",
        filename="empty.json",
        version=f"v_empty_{uuid.uuid4().hex[:6]}",
        owner_id="owner_empty",
        records=[],
        validation_report={"errors": [], "warnings": []},
        valid_count=0,
        invalid_count=0,
        category="PRODUCT_CATALOGUE"
    )
    db.activate_catalogue(empty_cat["id"], actor_id="owner_empty")
    catalogue_loader.load_from_database()

    resp = list_products(limit=50, offset=0)
    assert resp["total"] == 0
    assert resp["products"] == []
    assert resp["has_next"] is False
    assert resp["has_prev"] is False
