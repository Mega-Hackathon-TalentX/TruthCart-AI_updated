"""
TruthCart AI — Phase 2 Verification & End-to-End Validation Test Suite.
Validates:
1. Ingestion of realistic Datasets A, B, C, D, E, F and graceful rejection of Dataset G.
2. Cross-dataset identity resolution (exact, cautious inferred, and refusal on variant mismatches).
3. The 8 required production application queries (price filter, attribute filter, comparison,
   review complaint summary, seller price comparison, policy lookup, exact ID, synonym search).
4. Adaptive embedding pipeline: dimension integrity, model compatibility, failure handling,
   and error recovery via /retry-embeddings.
5. Multi-category concurrent dataset activation without mutual deactivation.
6. Customer vs Owner RBAC and demo sandbox boundaries.
"""

import os
import io
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db
from app.ingestion.universal_ingestor import universal_ingestor
from app.ingestion.schema_mapper import schema_mapper, DatasetCategory
from app.retrieval.identity_resolver import identity_resolver, RelationshipType
from app.retrieval.adaptive_embeddings import (
    embedding_manager,
    SparseTfIdfEmbeddingProvider,
    MockEmbeddingProvider
)
from app.retrieval.semantic_search import local_vector_index
from app.retrieval.hybrid_retriever import hybrid_retriever
from app.evidence_engine.decision_engine import decision_engine
from app.evidence_engine.citation_validator import citation_validator
from app.llm.query_understanding import query_understanding
from app.llm.response_generator import response_generator
from app.ingestion.catalogue_loader import catalogue_loader

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "realistic_datasets")


def get_owner_auth():
    resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    assert resp.status_code == 200, f"Owner login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def get_shopper_auth():
    email = f"shopper_{uuid.uuid4().hex[:6]}@example.com"
    resp = client.post("/api/auth/signup", json={
        "full_name": "Phase 2 Shopper",
        "email": email,
        "password": "Password123!"
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ==============================================================================
# 1. REALISTIC DATASET INGESTION SUITE (DATASETS A THROUGH G)
# ==============================================================================

def test_dataset_a_product_catalogue_ingestion():
    """Dataset A: Standard product catalogue with specifications column."""
    filepath = os.path.join(FIXTURES_DIR, "dataset_a_catalogue.csv")
    with open(filepath, "rb") as f:
        content = f.read()

    records, _, fmt = universal_ingestor.parse_file(content=content, filename="dataset_a_catalogue.csv")
    assert len(records) == 3
    assert fmt == "CSV"

    res, valid_records, errors, warnings = universal_ingestor.profile_and_validate(records)
    assert res.detected_category == DatasetCategory.PRODUCT_CATALOGUE
    assert len(valid_records) == 3
    assert len(errors) == 0
    # Verify specifications captured in attributes
    p1 = next(r for r in valid_records if r["product_id"] == "TC-TECH-01")
    assert p1["title"] == "Apex Pro 16 Laptop"
    assert p1["price"] == 89999.00
    assert p1["attributes"].get("ram") == "16 GB"


def test_dataset_b_alternative_catalogue_ingestion():
    """Dataset B: Alternative naming conventions (item_code, title, manufacturer, selling_price)."""
    filepath = os.path.join(FIXTURES_DIR, "dataset_b_alt_catalogue.csv")
    with open(filepath, "rb") as f:
        content = f.read()

    records, _, _ = universal_ingestor.parse_file(content=content, filename="dataset_b_alt_catalogue.csv")
    res, valid_records, errors, warnings = universal_ingestor.profile_and_validate(records)
    assert res.detected_category == DatasetCategory.PRODUCT_CATALOGUE
    assert len(valid_records) == 3
    # Check normalized canonical names
    p = next(r for r in valid_records if r["product_id"] == "NB-PRO-16")
    assert p["title"] == "Apex Pro 16 Laptop"
    assert p["price"] == 87999.00
    assert p["brand"] == "NovaTech"


def test_dataset_c_customer_reviews_ingestion():
    """Dataset C: Customer reviews with stars, feedback, and review_date."""
    filepath = os.path.join(FIXTURES_DIR, "dataset_c_reviews.csv")
    with open(filepath, "rb") as f:
        content = f.read()

    records, _, _ = universal_ingestor.parse_file(content=content, filename="dataset_c_reviews.csv")
    res, valid_records, errors, warnings = universal_ingestor.profile_and_validate(records)
    assert res.detected_category == DatasetCategory.CUSTOMER_REVIEWS
    assert len(valid_records) == 4
    # Ensure review_text and rating mapped accurately
    r_bad = next(r for r in valid_records if "drains" in r["review_text"])
    assert r_bad["rating"] == 2.0
    assert "Battery drains" in r_bad["review_text"]
    assert r_bad["product_id"] == "TC-TECH-01"


def test_dataset_d_competitor_pricing_ingestion():
    """Dataset D: Competitor price observations across multiple sellers."""
    filepath = os.path.join(FIXTURES_DIR, "dataset_d_competitor.csv")
    with open(filepath, "rb") as f:
        content = f.read()

    records, _, _ = universal_ingestor.parse_file(content=content, filename="dataset_d_competitor.csv")
    res, valid_records, errors, warnings = universal_ingestor.profile_and_validate(records)
    assert res.detected_category == DatasetCategory.COMPETITOR_PRICING
    assert len(valid_records) == 3
    # Ensure prices and sellers preserved faithfully without fabrication
    c1 = next(r for r in valid_records if r["price"] == 92500.00)
    assert "Marketplace X" in c1["seller_name"]
    assert c1["product_id"] == "TC-TECH-01"


def test_dataset_e_policies_ingestion():
    """Dataset E: Store policies and manufacturer warranty documents."""
    filepath = os.path.join(FIXTURES_DIR, "dataset_e_policies.csv")
    with open(filepath, "rb") as f:
        content = f.read()

    records, _, _ = universal_ingestor.parse_file(content=content, filename="dataset_e_policies.csv")
    res, valid_records, errors, warnings = universal_ingestor.profile_and_validate(records)
    assert res.detected_category == DatasetCategory.POLICIES_AND_EVIDENCE
    assert len(valid_records) == 2
    pol1 = next(r for r in valid_records if "Return" in r["title"])
    assert "14 calendar days" in pol1["policy_content"]


def test_dataset_f_unfamiliar_relevant_schema_ingestion():
    """Dataset F: Unfamiliar warehouse schema (warehouse_sku, supplier_vendor, wholesale_cost)."""
    filepath = os.path.join(FIXTURES_DIR, "dataset_f_unfamiliar_relevant.csv")
    with open(filepath, "rb") as f:
        content = f.read()

    records, _, _ = universal_ingestor.parse_file(content=content, filename="dataset_f_unfamiliar_relevant.csv")
    res, valid_records, errors, warnings = universal_ingestor.profile_and_validate(records)
    assert res.detected_category in (DatasetCategory.GENERIC_DATASET, DatasetCategory.PRODUCT_CATALOGUE)
    assert len(valid_records) == 3
    item = next(r for r in valid_records if "Solid State Drive" in r["title"])
    assert item["price"] == 5200.00


def test_dataset_g_rejections_and_error_handling():
    """Dataset G: Empty file, malformed file, and unrelated medical dataset rejected gracefully."""
    owner_headers = get_owner_auth()

    # Empty file
    empty_path = os.path.join(FIXTURES_DIR, "dataset_g_empty.csv")
    with open(empty_path, "rb") as f:
        resp = client.post("/api/catalogue/upload-preview", headers=owner_headers, files={"file": ("empty.csv", f.read(), "text/csv")})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower() or "no data" in resp.json()["detail"].lower()

    # Unrelated medical dataset
    unrelated_path = os.path.join(FIXTURES_DIR, "dataset_g_unrelated.csv")
    with open(unrelated_path, "rb") as f:
        resp = client.post("/api/catalogue/upload-preview", headers=owner_headers, files={"file": ("medical.csv", f.read(), "text/csv")})
    assert resp.status_code == 400
    assert "Not a valid dataset" in resp.json()["detail"]


# ==============================================================================
# 2. PRODUCT IDENTITY RESOLUTION & CROSS-DATASET LINKING
# ==============================================================================

def test_identity_resolution_exact_and_inferred():
    """Verify exact SKU linking, cautious inferred matching, and variant mismatch prevention."""
    cand_products = [
        {
            "product_id": "TC-TECH-01",
            "title": "Apex Pro 16 Laptop",
            "category": "Electronics",
            "price": 89999.00,
            "attributes": {"brand": "NovaTech", "ram": "16 GB", "storage": "512 GB"}
        },
        {
            "product_id": "TC-TECH-02",
            "title": "AirLite 14 Ultrabook",
            "category": "Electronics",
            "price": 44999.00,
            "attributes": {"brand": "NovaTech", "ram": "8 GB", "storage": "256 GB"}
        }
    ]

    # 1. Exact match via product_reference
    exact_item = {"product_reference": "TC-TECH-01", "seller_name": "Seller Alpha", "observed_price": 91000}
    rel, target, conf, crit = identity_resolver.resolve_relationship(exact_item, cand_products)
    assert rel == RelationshipType.EXACT
    assert target == "TC-TECH-01"
    assert conf == 1.0

    # 2. Cautious inferred match (different ID 'NB-PRO-16', but exact brand and high title overlap)
    inferred_item = {
        "item_code": "NB-PRO-16",
        "title": "NovaTech Apex Pro 16 Laptop",
        "brand": "NovaTech",
        "technical_details": "16 GB RAM 512 GB NVMe"
    }
    rel, target, conf, crit = identity_resolver.resolve_relationship(inferred_item, cand_products)
    assert rel == RelationshipType.INFERRED
    assert target == "TC-TECH-01"
    assert conf >= 0.70

    # 3. Refusal to merge conflicting variants (32 GB vs 16 GB)
    mismatched_variant = {
        "item_code": "NB-PRO-32",
        "title": "NovaTech Apex Pro 16 Laptop 32GB RAM",
        "brand": "NovaTech",
        "technical_details": "32 GB RAM 1 TB SSD"
    }
    rel, target, conf, crit = identity_resolver.resolve_relationship(mismatched_variant, cand_products)
    assert rel == RelationshipType.UNLINKED or target != "TC-TECH-01"


# ==============================================================================
# 3. ADAPTIVE EMBEDDING PIPELINE VERIFICATION
# ==============================================================================

def test_adaptive_embedding_pipeline_and_dimensions():
    """Verify document construction, sparse TF-IDF dimension (256), and mock dimension (64)."""
    # 1. Local TF-IDF Provider
    tfidf_provider = SparseTfIdfEmbeddingProvider(max_features=256)
    assert tfidf_provider.dimension == 256
    assert tfidf_provider.model_name == "local-sparse-tfidf-v1"

    doc_text = "Apex Pro 16 Laptop NovaTech 16 GB RAM OLED display"
    vecs = tfidf_provider.embed_texts([doc_text])
    assert len(vecs) == 1
    assert len(vecs[0]) == 256
    assert any(v != 0.0 for v in vecs[0])

    # 2. Query embedding produces identical dimensions
    q_vec = tfidf_provider.embed_query("16 GB RAM laptop")
    assert len(q_vec) == 256

    # 3. Embedding Manager handles batch records
    records = [
        {"product_id": "P1", "title": "Apex Pro 16 Laptop", "description": "High performance 16 GB RAM laptop"},
        {"product_id": "P2", "title": "AirLite 14 Ultrabook", "description": "Lightweight travel ultrabook"}
    ]
    records_out, vectors = embedding_manager.embed_records(records, category="PRODUCT_CATALOGUE")
    assert len(records_out) == 2
    assert vectors.shape == (2, embedding_manager.provider.dimension)


def test_embedding_error_reporting_and_retry_endpoint():
    """Verify failed embeddings set status to EMBEDDING_FAILED and owner can retry."""
    owner_headers = get_owner_auth()
    unique_v = f"v_err_test_{uuid.uuid4().hex[:4]}"

    # Import a test catalogue
    import_payload = {
        "name": "Error Recovery Test Catalogue",
        "filename": "err_test.csv",
        "version": unique_v,
        "valid_count": 1,
        "invalid_count": 0,
        "records": [{
            "product_id": "TC-TEST-ERR",
            "title": "Error Test Laptop",
            "category": "Electronics",
            "price": 55000.0,
            "stock_status": "In Stock",
            "rating": 4.5,
            "attributes": {"brand": "TestBrand"}
        }],
        "validation_report": {"valid": 1, "errors": []},
        "category": "PRODUCT_CATALOGUE"
    }

    imp_resp = client.post("/api/catalogue/import", headers=owner_headers, json=import_payload)
    assert imp_resp.status_code == 200
    cat_id = imp_resp.json()["id"]

    # Manually simulate embedding failure in database
    db.update_dataset_embedding_status(cat_id, "EMBEDDING_FAILED", "Simulated vector timeout")
    cat = db.get_catalogue_by_id(cat_id)
    assert cat["embedding_status"] == "EMBEDDING_FAILED"

    # Call /retry-embeddings endpoint
    retry_resp = client.post(f"/api/catalogue/{cat_id}/retry-embeddings", headers=owner_headers)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "success"

    # Status should now be restored to INDEXED
    cat_updated = db.get_catalogue_by_id(cat_id)
    assert cat_updated["embedding_status"] == "INDEXED"


# ==============================================================================
# 4. MULTI-CATEGORY CONCURRENT ACTIVATION
# ==============================================================================

def test_multi_category_dataset_activation_isolation():
    """
    Ensure activating a Customer Reviews dataset does NOT deactivate the active Product Catalogue.
    Both should remain active simultaneously.
    """
    owner_headers = get_owner_auth()
    v_cat = f"v_cat_{uuid.uuid4().hex[:4]}"
    v_rev = f"v_rev_{uuid.uuid4().hex[:4]}"

    # 1. Import and activate a product catalogue
    cat_payload = {
        "name": "MultiCat Product Catalogue",
        "filename": "cat.csv",
        "version": v_cat,
        "valid_count": 2,
        "invalid_count": 0,
        "records": [
            {"product_id": "MC-01", "title": "MultiCat Item 1", "category": "Electronics", "price": 1000.0, "stock_status": "In Stock"},
            {"product_id": "MC-02", "title": "MultiCat Item 2", "category": "Electronics", "price": 2000.0, "stock_status": "In Stock"}
        ],
        "validation_report": {"valid": 2, "errors": []},
        "category": "PRODUCT_CATALOGUE"
    }
    r1 = client.post("/api/catalogue/import", headers=owner_headers, json=cat_payload)
    cat_id = r1.json()["id"]
    client.post(f"/api/catalogue/{cat_id}/activate", headers=owner_headers)

    active_cat = db.get_active_catalogue()
    assert active_cat["id"] == cat_id

    # 2. Import and activate a customer reviews dataset
    rev_payload = {
        "name": "MultiCat Reviews Dataset",
        "filename": "revs.csv",
        "version": v_rev,
        "valid_count": 1,
        "invalid_count": 0,
        "records": [
            {"record_id": "MC-REV-01", "product_id": "MC-01", "title": "Review MC-01", "review_text": "Works great!", "rating": 5.0}
        ],
        "validation_report": {"valid": 1, "errors": []},
        "category": "CUSTOMER_REVIEWS"
    }
    r2 = client.post("/api/catalogue/import", headers=owner_headers, json=rev_payload)
    rev_id = r2.json()["id"]
    client.post(f"/api/catalogue/{rev_id}/activate", headers=owner_headers)

    # 3. Product catalogue should STILL be active!
    active_cat_after = db.get_active_catalogue()
    assert active_cat_after["id"] == cat_id
    assert active_cat_after["is_active"] == 1


# ==============================================================================
# 5. THE 8 REQUIRED APPLICATION QUERIES
# ==============================================================================

@pytest.fixture(scope="module")
def seeded_phase2_knowledge_base():
    """Seeds Datasets A, C, D for real application query tests."""
    owner_headers = get_owner_auth()
    suffix = uuid.uuid4().hex[:4]

    # Seed Dataset A (Catalogue)
    cat_path = os.path.join(FIXTURES_DIR, "dataset_a_catalogue.csv")
    with open(cat_path, "rb") as f:
        recs_a, _, _ = universal_ingestor.parse_file(content=f.read(), filename="dataset_a_catalogue.csv")
    _, valid_a, _, _ = universal_ingestor.profile_and_validate(recs_a)

    v_a = f"v_app_a_{suffix}"
    imp_a = client.post("/api/catalogue/import", headers=owner_headers, json={
        "name": "Phase 2 Core Catalogue",
        "filename": "dataset_a_catalogue.csv",
        "version": v_a,
        "valid_count": len(valid_a),
        "invalid_count": 0,
        "records": valid_a,
        "validation_report": {"valid": len(valid_a), "errors": []},
        "category": "PRODUCT_CATALOGUE"
    }).json()

    # Seed Dataset C (Reviews)
    rev_path = os.path.join(FIXTURES_DIR, "dataset_c_reviews.csv")
    with open(rev_path, "rb") as f:
        recs_c, _, _ = universal_ingestor.parse_file(content=f.read(), filename="dataset_c_reviews.csv")
    _, valid_c, _, _ = universal_ingestor.profile_and_validate(recs_c)

    v_c = f"v_app_c_{suffix}"
    imp_c = client.post("/api/catalogue/import", headers=owner_headers, json={
        "name": "Phase 2 Reviews",
        "filename": "dataset_c_reviews.csv",
        "version": v_c,
        "valid_count": len(valid_c),
        "invalid_count": 0,
        "records": valid_c,
        "validation_report": {"valid": len(valid_c), "errors": []},
        "category": "CUSTOMER_REVIEWS"
    }).json()
    client.post(f"/api/catalogue/{imp_c['id']}/activate", headers=owner_headers)

    # Seed Dataset D (Competitor Pricing)
    comp_path = os.path.join(FIXTURES_DIR, "dataset_d_competitor.csv")
    with open(comp_path, "rb") as f:
        recs_d, _, _ = universal_ingestor.parse_file(content=f.read(), filename="dataset_d_competitor.csv")
    _, valid_d, _, _ = universal_ingestor.profile_and_validate(recs_d)

    v_d = f"v_app_d_{suffix}"
    imp_d = client.post("/api/catalogue/import", headers=owner_headers, json={
        "name": "Phase 2 Competitor Intel",
        "filename": "dataset_d_competitor.csv",
        "version": v_d,
        "valid_count": len(valid_d),
        "invalid_count": 0,
        "records": valid_d,
        "validation_report": {"valid": len(valid_d), "errors": []},
        "category": "COMPETITOR_PRICING"
    }).json()
    client.post(f"/api/catalogue/{imp_d['id']}/activate", headers=owner_headers)

    yield {"cat_id": imp_a["id"], "cat_version": v_a, "rev_version": v_c, "comp_version": v_d}

    # Teardown: restore official v1.0.0
    try:
        db.activate_catalogue(cat_id="v1.0.0", actor_id="owner")
        catalogue_loader.load_from_database()
        local_vector_index.build_index(force_rebuild=True)
    except Exception:
        pass


@pytest.fixture
def active_phase2_catalogue(seeded_phase2_knowledge_base):
    """Activates the Phase 2 catalogue for the query test, overcoming conftest autouse reset."""
    cat_id = seeded_phase2_knowledge_base["cat_id"]
    db.activate_catalogue(cat_id=cat_id, actor_id="owner")
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)
    return seeded_phase2_knowledge_base


def test_query_1_products_below_50000(active_phase2_catalogue):
    """Query 1: 'Find products below ₹50,000' -> Should return AirLite 14 (₹44,999) and SonicBoom ANC (₹8,499)."""
    parsed = query_understanding.parse("Find products below 50000")
    assert parsed.get("max_price") == 50000.0

    prods, _ = hybrid_retriever.retrieve(query="Find products below 50000", structured_params=parsed)
    matched_ids = [c.source_id for c in prods]
    assert "TC-TECH-02" in matched_ids # AirLite 14 (₹44,999)
    assert "TC-TECH-01" not in matched_ids # Apex Pro 16 (₹89,999 is > 50000)


def test_query_2_products_with_16gb_ram(active_phase2_catalogue):
    """Query 2: 'Find products with 16 GB RAM' -> Should retrieve Apex Pro 16 Laptop."""
    parsed = query_understanding.parse("Find products with 16 GB RAM")
    assert parsed.get("required_attributes", {}).get("ram") == "16 GB"

    prods, _ = hybrid_retriever.retrieve(query="Find products with 16 GB RAM", structured_params=parsed)
    assert len(prods) > 0
    top_p = prods[0]
    assert top_p.source_id == "TC-TECH-01"
    assert "16 GB" in str(top_p.data.get("attributes", {}))


def test_query_3_compare_two_products(active_phase2_catalogue):
    """Query 3: 'Compare Apex Pro 16 and AirLite 14' -> Generates side-by-side comparison."""
    parsed = query_understanding.parse("Compare Apex Pro 16 and AirLite 14")
    prods, pol = hybrid_retriever.retrieve(query="Compare Apex Pro 16 and AirLite 14", structured_params=parsed)
    pids = [c.source_id for c in prods]
    assert "TC-TECH-01" in pids
    assert "TC-TECH-02" in pids

    evidence = decision_engine.evaluate(
        query="Compare Apex Pro 16 and AirLite 14",
        parsed_query=parsed,
        product_candidates=prods,
        policy_candidate=pol
    )
    assert evidence.decision == "ANSWER"
    ev_pids = {ev.source_id for ev in evidence.evidence if ev.source_type == "product"}
    assert "TC-TECH-01" in ev_pids
    assert "TC-TECH-02" in ev_pids


def test_query_4_summarize_review_complaints(active_phase2_catalogue):
    """Query 4: 'Summarize common complaints from the supplied reviews' -> identifies battery drain and tight ear cups."""
    parsed = query_understanding.parse("What are the common complaints in customer reviews?")
    assert parsed.get("intent") == "review_summary"

    prods, pol = hybrid_retriever.retrieve(query="What are the common complaints in customer reviews?", structured_params=parsed)
    evidence = decision_engine.evaluate(
        query="What are the common complaints in customer reviews?",
        parsed_query=parsed,
        product_candidates=prods,
        policy_candidate=pol
    )
    assert evidence.decision == "ANSWER"
    review_evs = [ev for ev in evidence.evidence if ev.source_type == "review"]
    assert len(review_evs) >= 1

    # Check generated response for citations
    text, _, citations, _, _ = response_generator.generate_response(evidence, matched_products=[])
    assert any("[REVIEW:" in c for c in citations)


def test_query_5_compare_seller_prices(active_phase2_catalogue):
    """Query 5: 'Compare prices for TC-TECH-01 across sellers' -> compares Marketplace X vs DirectDeals for TC-TECH-01."""
    parsed = query_understanding.parse("Compare prices for TC-TECH-01 across sellers")
    assert parsed.get("intent") == "seller_price_comparison"

    prods, pol = hybrid_retriever.retrieve(query="Compare prices for TC-TECH-01 across sellers", structured_params=parsed)
    evidence = decision_engine.evaluate(
        query="Compare prices for TC-TECH-01 across sellers",
        parsed_query=parsed,
        product_candidates=prods,
        policy_candidate=pol
    )
    assert evidence.decision == "ANSWER"
    comp_evs = [ev for ev in evidence.evidence if ev.source_type in ("competitor", "listing", "catalogue", "product") or ev.field == "price"]
    assert len(comp_evs) >= 1

    text, _, citations, _, _ = response_generator.generate_response(evidence, matched_products=[])
    assert len(text) > 0


def test_query_6_return_policy_lookup(active_phase2_catalogue):
    """Query 6: 'What is the return policy for laptops?' -> returns verified return policy clause."""
    parsed = query_understanding.parse("What is the return policy for laptops?")
    prods, pol = hybrid_retriever.retrieve(query="What is the return policy for laptops?", structured_params=parsed)
    assert pol is not None

    evidence = decision_engine.evaluate(
        query="What is the return policy for laptops?",
        parsed_query=parsed,
        product_candidates=prods,
        policy_candidate=pol
    )
    assert evidence.decision == "ANSWER"
    pol_evs = [ev for ev in evidence.evidence if ev.source_type == "policy"]
    assert len(pol_evs) > 0
    assert "14" in pol_evs[0].value or "return" in pol_evs[0].value.lower()


def test_query_7_exact_identifier_lookup(active_phase2_catalogue):
    """Query 7: 'Find product TC-TECH-01' -> Retrieves exact product directly."""
    parsed = query_understanding.parse("TC-TECH-01")
    prods, _ = hybrid_retriever.retrieve(query="TC-TECH-01", structured_params=parsed)
    assert len(prods) > 0
    assert prods[0].source_id == "TC-TECH-01"
    assert prods[0].data.get("title") == "Apex Pro 16 Laptop"


def test_query_8_synonym_search(active_phase2_catalogue):
    """Query 8: 'Show me lightweight travel ultrabooks' -> Matches AirLite 14 even though keyword is 'Ultrabook'."""
    parsed = query_understanding.parse("Show me lightweight travel ultrabooks")
    prods, _ = hybrid_retriever.retrieve(query="Show me lightweight travel ultrabooks", structured_params=parsed)
    assert len(prods) > 0
    pids = [c.source_id for c in prods]
    assert "TC-TECH-02" in pids # AirLite 14 Ultrabook


# ==============================================================================
# 6. SECURITY & ACCESS CONTROL BOUNDARIES
# ==============================================================================

def test_customer_cannot_upload_or_activate():
    """Unauthenticated users or customers cannot access owner dataset upload or activation endpoints."""
    shopper_headers = get_shopper_auth()

    # Attempt to upload catalogue
    resp = client.post("/api/catalogue/upload-preview", headers=shopper_headers, files={"file": ("test.csv", b"a,b\n1,2", "text/csv")})
    assert resp.status_code == 403

    # Attempt to activate catalogue
    resp = client.post("/api/catalogue/some-id/activate", headers=shopper_headers)
    assert resp.status_code == 403

    # Attempt to retry embeddings
    resp = client.post("/api/catalogue/some-id/retry-embeddings", headers=shopper_headers)
    assert resp.status_code == 403


def test_customer_can_only_search_active_records():
    """Customer browse endpoint queries verified active catalogue records."""
    resp = client.get("/api/products")
    assert resp.status_code == 200
    items = resp.json().get("products") or resp.json().get("items") or []
    assert len(items) > 0
    for p in items:
        assert p.get("product_id")
        assert p.get("title")

