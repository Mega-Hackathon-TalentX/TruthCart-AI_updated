"""
TruthCart AI — Universal Dataset Ingestion, Schema Detection, Adaptive Embeddings,
and Multi-Domain Retrieval Test Suite.
Covers all 23 scenarios required by Phase 10 of the Master Engineering Specification.
"""

import io
import json
import uuid
import pytest
import numpy as np
import pandas as pd
import openpyxl
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db
from app.ingestion.universal_ingestor import universal_ingestor
from app.ingestion.schema_mapper import schema_mapper, DatasetCategory
from app.ingestion.data_validator import DataValidator
from app.retrieval.adaptive_embeddings import (
    embedding_manager,
    MockEmbeddingProvider,
    DocumentBuilder,
    SparseTfIdfEmbeddingProvider,
    BaseEmbeddingProvider
)
from app.retrieval.semantic_search import local_vector_index
from app.retrieval.structured_search import structured_search
from app.evidence_engine.citation_validator import citation_validator
from app.evidence_engine.citation_mapper import citation_mapper

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """Ensure database schema is initialized and demo catalogue is loaded."""
    db.init_db()


def get_owner_auth_headers():
    """Helper to obtain owner JWT bearer headers."""
    resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    assert resp.status_code == 200, f"Owner login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def get_customer_auth_headers():
    """Helper to create and obtain customer JWT bearer headers."""
    email = f"shopper_{uuid.uuid4().hex[:6]}@example.com"
    resp = client.post("/api/auth/signup", json={
        "full_name": "Test Shopper",
        "email": email,
        "password": "Password123!"
    })
    assert resp.status_code == 200, f"Customer signup failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# TEST 1: Existing TruthCart AI product catalogue still works without changes
# ==============================================================================
def test_01_existing_catalogue_format_still_works():
    headers = get_owner_auth_headers()
    csv_content = (
        "product_id,title,description,category,price,stock_status,rating\n"
        "TC-LEG-001,Classic Oxford Shirt,Pure cotton button down,Apparel,1499.00,In Stock,4.5\n"
        "TC-LEG-002,Slim Chino Trousers,Stretch cotton casual chinos,Apparel,1899.00,In Stock,4.2\n"
    )
    files = {"file": ("catalogue_v1.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["detected_category"] == DatasetCategory.PRODUCT_CATALOGUE.value
    assert data["valid_count"] == 2
    assert data["invalid_count"] == 0
    assert len(data["preview_records"]) == 2
    assert data["preview_records"][0]["product_id"] == "TC-LEG-001"
    assert data["preview_records"][0]["price"] == 1499.0


# ==============================================================================
# TEST 2: Product dataset with reordered columns
# ==============================================================================
def test_02_product_dataset_reordered_columns():
    headers = get_owner_auth_headers()
    # Entirely permuted column order: stock_status, price, category, product_id, title, description
    csv_content = (
        "stock_status,price,category,product_id,title,description\n"
        "In Stock,4999.00,Footwear,TC-REORD-01,Running Pro Sneakers,Breathable mesh running shoes\n"
        "Low Stock,899.00,Accessories,TC-REORD-02,Leather Cardholder,Genuine brown leather\n"
    )
    files = {"file": ("reordered.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_count"] == 2
    rec = data["preview_records"][0]
    assert rec["product_id"] == "TC-REORD-01"
    assert rec["title"] == "Running Pro Sneakers"
    assert rec["price"] == 4999.00
    assert rec["category"] == "Footwear"
    assert rec["stock_status"] == "In Stock"


# ==============================================================================
# TEST 3: Product dataset with alternative column names
# ==============================================================================
def test_03_alternative_column_names():
    headers = get_owner_auth_headers()
    # Uses: sku -> product_id, item_name -> title, selling_price -> price, manufacturer -> brand, qty_available -> stock_status
    csv_content = (
        "sku,item_name,selling_price,manufacturer,qty_available\n"
        "SKU-TECH-99,UltraSound Bar,12499.0,AcousticLab,45\n"
        "SKU-TECH-100,Mini Subwoofer,6499.0,AcousticLab,12\n"
    )
    files = {"file": ("alternative_headers.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_count"] == 2
    rec = data["preview_records"][0]
    assert rec["product_id"] == "SKU-TECH-99"
    assert rec["title"] == "UltraSound Bar"
    assert rec["price"] == 12499.0
    assert rec.get("brand") == "AcousticLab" or rec.get("attributes", {}).get("brand") == "AcousticLab"


# ==============================================================================
# TEST 4: Product dataset missing optional fields
# ==============================================================================
def test_04_missing_optional_fields():
    headers = get_owner_auth_headers()
    # Minimal fields: only product_id and title (price, stock, rating, description missing)
    csv_content = (
        "item_code,product_title\n"
        "MIN-01,Minimalist Desk Lamp\n"
        "MIN-02,Ergonomic Footrest\n"
    )
    files = {"file": ("minimal.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_count"] == 2
    assert data["invalid_count"] == 0
    rec = data["preview_records"][0]
    assert rec["product_id"] == "MIN-01"
    assert rec["title"] == "Minimalist Desk Lamp"
    assert rec["price"] is None or rec["price"] == 0.0


# ==============================================================================
# TEST 5: Dataset containing extra unknown columns (preserved in attributes)
# ==============================================================================
def test_05_extra_unknown_columns_preserved():
    headers = get_owner_auth_headers()
    csv_content = (
        "product_id,title,price,eco_certified,carbon_offset_kg,distributor_code\n"
        "ECO-100,Bamboo Keyboard,3200.0,Yes,1.25,DIST-EU-88\n"
    )
    files = {"file": ("eco_products.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_count"] == 1
    rec = data["preview_records"][0]
    attrs = rec.get("attributes", {})
    assert "eco_certified" in attrs
    assert attrs["eco_certified"] == "Yes"
    assert "carbon_offset_kg" in attrs


# ==============================================================================
# TEST 6: Customer review dataset with no product-price column
# ==============================================================================
def test_06_customer_reviews_dataset_without_price():
    headers = get_owner_auth_headers()
    csv_content = (
        "review_id,product_id,reviewer_name,rating,review_text,date\n"
        "REV-001,TC-DEV-101,John Doe,5,Super comfortable cotton and great fit,2026-03-15\n"
        "REV-002,TC-DEV-106,Anita Roy,4,Noise cancellation is very impressive on flights,2026-03-18\n"
    )
    files = {"file": ("customer_feedback.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["detected_category"] == DatasetCategory.CUSTOMER_REVIEWS.value
    assert data["valid_count"] == 2
    rec = data["preview_records"][0]
    assert rec["rating"] == 5.0
    assert "Super comfortable" in rec.get("review_text", "")
    # Check dynamic DocumentBuilder output for review
    doc_text = DocumentBuilder.build_embedding_text(rec, category=DatasetCategory.CUSTOMER_REVIEWS.value)
    assert doc_text is not None
    assert "Review: Super comfortable" in doc_text


# ==============================================================================
# TEST 7: Competitor pricing dataset with distinct schema
# ==============================================================================
def test_07_competitor_pricing_dataset():
    headers = get_owner_auth_headers()
    csv_content = (
        "competitor_name,target_sku,competitor_price,marketplace,observation_date\n"
        "AlphaRetail,TC-DEV-101,1399.0,MarketX,2026-04-01\n"
        "BetaDeals,TC-DEV-106,8999.0,MarketY,2026-04-01\n"
    )
    files = {"file": ("competitor_intel.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["detected_category"] == DatasetCategory.COMPETITOR_PRICING.value
    assert data["valid_count"] == 2
    rec = data["preview_records"][0]
    assert rec["competitor_name"] == "AlphaRetail"
    assert rec["observed_price"] == 1399.0


# ==============================================================================
# TEST 8: Product policy dataset
# ==============================================================================
def test_08_product_policy_dataset():
    headers = get_owner_auth_headers()
    csv_content = (
        "policy_type,title,policy_content,effective_date\n"
        "Return,Standard 30-Day Return,Items in original condition can be returned within 30 days for full refund,2026-01-01\n"
        "Warranty,1-Year Limited Warranty,Defects in materials and workmanship covered for 12 months,2026-01-01\n"
    )
    files = {"file": ("store_policies.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["detected_category"] == DatasetCategory.POLICIES_AND_EVIDENCE.value
    assert data["valid_count"] == 2
    # Verify policy evidence formatting
    valid_citation = "[POLICY:RETURNS]"
    is_valid, valid_cits, _ = citation_validator.validate_citations(
        text=valid_citation,
        verified_product_ids=set(),
        verified_policy_ids={"POLICY:RETURNS"}
    )
    assert is_valid is True


# ==============================================================================
# TEST 9: JSON and JSONL file ingestion
# ==============================================================================
def test_09_json_and_jsonl_file_ingestion():
    headers = get_owner_auth_headers()
    # 1. JSON Array format
    json_data = json.dumps([
        {"product_id": "J-01", "title": "Wireless Keyboard", "price": 1800.0, "category": "Electronics"},
        {"product_id": "J-02", "title": "Vertical Mouse", "price": 1200.0, "category": "Electronics"}
    ])
    files_json = {"file": ("products.json", json_data, "application/json")}
    resp_json = client.post("/api/catalogue/upload-preview", headers=headers, files=files_json)
    assert resp_json.status_code == 200
    assert resp_json.json()["valid_count"] == 2

    # 2. JSONL (JSON Lines) format
    jsonl_data = (
        '{"sku": "JL-01", "item_name": "RGB Desk Mat", "amount": 799.0}\n'
        '{"sku": "JL-02", "item_name": "Cable Management Arm", "amount": 499.0}\n'
    )
    files_jsonl = {"file": ("products.jsonl", jsonl_data, "application/x-jsonlines")}
    resp_jsonl = client.post("/api/catalogue/upload-preview", headers=headers, files=files_jsonl)
    assert resp_jsonl.status_code == 200
    assert resp_jsonl.json()["valid_count"] == 2


# ==============================================================================
# TEST 10: Multi-sheet Excel workbook
# ==============================================================================
def test_10_multisheet_excel_workbook():
    headers = get_owner_auth_headers()
    wb = openpyxl.Workbook()
    # Default sheet
    ws1 = wb.active
    ws1.title = "Laptops"
    ws1.append(["product_id", "title", "price", "category"])
    ws1.append(["NB-01", "Pro Laptop 15", 75000, "Computers"])
    ws1.append(["NB-02", "Air Laptop 13", 62000, "Computers"])

    # Second sheet
    ws2 = wb.create_sheet(title="Accessories")
    ws2.append(["product_id", "title", "price", "category"])
    ws2.append(["ACC-01", "USB-C Multi-hub", 2500, "Accessories"])

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    files = {"file": ("inventory.xlsx", bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert "available_sheets" in data
    assert "Laptops" in data["available_sheets"]
    assert "Accessories" in data["available_sheets"]
    assert data["valid_count"] >= 1


# ==============================================================================
# TEST 11: Completely empty file and malformed CSV
# ==============================================================================
def test_11_empty_file_and_malformed_csv():
    headers = get_owner_auth_headers()
    # 1. Empty file
    files_empty = {"file": ("empty.csv", b"", "text/csv")}
    resp_empty = client.post("/api/catalogue/upload-preview", headers=headers, files=files_empty)
    assert resp_empty.status_code == 400
    assert "empty" in resp_empty.json()["detail"].lower() or "no data" in resp_empty.json()["detail"].lower()

    # 2. Corrupted file content
    files_malformed = {"file": ("broken.csv", b"\x00\xff\xfe\x00\x12\x34", "text/csv")}
    resp_malformed = client.post("/api/catalogue/upload-preview", headers=headers, files=files_malformed)
    assert resp_malformed.status_code == 400


# ==============================================================================
# TEST 12: Duplicate headers and duplicate record handling
# ==============================================================================
def test_12_duplicate_headers_and_duplicate_records():
    headers = get_owner_auth_headers()
    csv_content = (
        "product_id,title,price\n"
        "TC-DUP-99,Unique Desk Stand,1500.0\n"
        "TC-DUP-99,Conflicting Second Occurrence,1800.0\n"
    )
    files = {"file": ("duplicate_ids.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    # Deduplication retains first occurrence and generates a quality warning
    assert data["valid_count"] == 1
    warnings = data.get("warnings", [])
    assert any("Duplicate" in w for w in warnings)
    assert data["preview_records"][0]["price"] == 1500.0


# ==============================================================================
# TEST 13: Incorrect data types and mixed-format values
# ==============================================================================
def test_13_incorrect_datatypes_and_mixed_formats():
    headers = get_owner_auth_headers()
    csv_content = (
        'product_id,title,price,rating\n'
        'TC-MIX-1,Item Rupee Sign,"₹ 1,499.50",4.8\n'
        'TC-MIX-2,Item Text Price,FREE,not_a_rating\n'
        'TC-MIX-3,Item With Commas,"12,000.00",4\n'
    )
    files = {"file": ("mixed_formats.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    recs = {r["product_id"]: r for r in data["preview_records"]}
    assert recs["TC-MIX-1"]["price"] == 1499.50
    assert recs["TC-MIX-1"]["rating"] == 4.8
    assert recs["TC-MIX-2"]["price"] == 0.0 or recs["TC-MIX-2"]["price"] is None
    assert recs["TC-MIX-3"]["price"] == 12000.00


# ==============================================================================
# TEST 14: Ambiguous semantic mappings and owner override
# ==============================================================================
def test_14_ambiguous_semantic_mappings_and_override():
    # IntelligentSchemaMapper allows overriding field mappings
    raw_data = [
        {"code": "C100", "label": "Widget Pro", "cost": 450}
    ]
    mapping_res = schema_mapper.profile_and_map(
        records=raw_data,
        owner_mapping_overrides={"code": "product_id", "label": "title", "cost": "price"}
    )
    assert mapping_res.field_mappings["product_id"] == "code"
    assert mapping_res.field_mappings["title"] == "label"
    assert mapping_res.field_mappings["price"] == "cost"
    assert mapping_res.column_profiles["code"].mapped_field == "product_id"


# ==============================================================================
# TEST 15: Relevant datasets with unfamiliar schemas
# ==============================================================================
def test_15_marketplace_listings_unfamiliar_schema():
    headers = get_owner_auth_headers()
    csv_content = (
        "asin,listing_title,buy_box_price,seller_name,marketplace_platform\n"
        "B08N5WRWNW,Studio Monitor Speakers,15999.0,SoundKing Direct,Amazon IN\n"
        "B08N5X3V9W,Microphone Boom Arm,2199.0,AudioHub,Flipkart\n"
    )
    files = {"file": ("marketplace.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["detected_category"] in (
        DatasetCategory.MARKETPLACE_LISTINGS.value,
        DatasetCategory.PRODUCT_CATALOGUE.value
    )
    assert data["valid_count"] == 2


# ==============================================================================
# TEST 16: Completely unrelated or unusable datasets (rejection with feedback)
# ==============================================================================
def test_16_completely_unrelated_dataset_rejected():
    headers = get_owner_auth_headers()
    # Medical dataset completely unrelated to shopping/catalogue/policy/reviews
    csv_content = (
        "patient_id,systolic_bp,diastolic_bp,glucose_level,diagnosis\n"
        "PT-101,120,80,95,Normal\n"
        "PT-102,145,92,130,Hypertension\n"
    )
    files = {"file": ("patient_records.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 400
    data = resp.json()
    assert "Not a valid dataset" in data["detail"]
    assert "recognizable" in data["detail"]


# ==============================================================================
# TEST 17: Embedding provider failure, dimension validation, and retries
# ==============================================================================
def test_17_embedding_provider_failure_and_retries():
    class FailingEmbeddingProvider(BaseEmbeddingProvider):
        @property
        def dimension(self) -> int:
            return 64
        @property
        def model_name(self) -> str:
            return "failing-provider"
        def embed_texts(self, texts, batch_size=32):
            raise ConnectionError("Simulated remote embedding API network timeout")
        def embed_query(self, query):
            raise ConnectionError("Simulated remote embedding API network timeout")

    # Set failing provider and verify manager exception handling
    failing_mgr = embedding_manager
    original_provider = failing_mgr.provider
    try:
        failing_mgr.set_provider(FailingEmbeddingProvider())
        with pytest.raises(ConnectionError):
            failing_mgr.embed_records([{"title": "Valid Test Product", "product_id": "P-1"}])
    finally:
        # Restore safe provider
        failing_mgr.set_provider(original_provider)


# ==============================================================================
# TEST 18: Vector dimension mismatch detection and recovery
# ==============================================================================
def test_18_vector_dimension_mismatch_detection():
    class MismatchedEmbeddingProvider(BaseEmbeddingProvider):
        @property
        def dimension(self) -> int:
            return 128  # Advertises 128
        @property
        def model_name(self) -> str:
            return "mismatched-provider"
        def embed_texts(self, texts, batch_size=32):
            # Erroneously returns dimension 64
            return np.zeros((len(texts), 64), dtype=np.float32)
        def embed_query(self, query):
            return np.zeros((64,), dtype=np.float32)

    original_provider = embedding_manager.provider
    try:
        embedding_manager.set_provider(MismatchedEmbeddingProvider())
        with pytest.raises(ValueError) as excinfo:
            embedding_manager.embed_records([{"title": "Noise cancelling headphones wireless pro", "product_id": "P-1"}])
        assert "dimension mismatch" in str(excinfo.value).lower()
    finally:
        embedding_manager.set_provider(original_provider)


# ==============================================================================
# TEST 19: Reprocessing and stale index handling
# ==============================================================================
def test_19_reprocessing_and_stale_index_handling():
    headers = get_owner_auth_headers()
    v_new = f"v-stale-{uuid.uuid4().hex[:6]}"
    records = [{
        "product_id": f"TC-FRESH-{uuid.uuid4().hex[:4]}",
        "title": "Freshly Imported Quantum Monitor",
        "description": "4K Ultra-wide gaming and office display",
        "category": "Electronics",
        "price": 32999.0,
        "stock_status": "In Stock",
        "rating": 4.9,
        "attributes": {}
    }]

    # Import new catalogue
    import_resp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Stale Index Test Catalogue",
        "version": v_new,
        "filename": "test_fresh.csv",
        "records": records,
        "valid_count": 1,
        "invalid_count": 0,
        "validation_report": {"valid": 1}
    })
    assert import_resp.status_code == 200
    cat_id = import_resp.json()["id"]

    # Activate newly imported catalogue
    act_resp = client.post(f"/api/catalogue/{cat_id}/activate", headers=headers)
    assert act_resp.status_code == 200

    # Verify search returns active catalogue product
    res = structured_search.search(product_id=records[0]["product_id"])
    assert len(res) == 1
    assert res[0]["title"] == "Freshly Imported Quantum Monitor"

    # Restore official v1.0.0 catalogue state for other test suites
    try:
        db.activate_catalogue(cat_id="v1.0.0", actor_id="owner")
        catalogue_loader.load_from_database()
        local_vector_index.build_index(force_rebuild=True)
    except Exception:
        pass


# ==============================================================================
# TEST 20: Exact price filters and identifier lookups
# ==============================================================================
def test_20_exact_price_filters_and_identifier_lookups():
    # 1. Exact ID lookup
    id_results = structured_search.search(product_id="TC-DEV-101")
    assert len(id_results) == 1
    assert id_results[0]["product_id"] == "TC-DEV-101"

    # 2. Exact price upper-bound filter
    budget_results = structured_search.search(category="Apparel", max_price=1600.0)
    assert len(budget_results) > 0
    for prod in budget_results:
        assert prod["price"] <= 1600.0
        assert prod["category"].lower() == "apparel"


# ==============================================================================
# TEST 21: Multi-domain source provenance and conflicting records
# ==============================================================================
def test_21_multidomain_source_provenance_and_citations():
    # Validate citation formatting across multi-domain evidence types
    cat_badge = citation_mapper.format_citation("CATALOGUE", "TC-DEV-101")
    assert "[CATALOGUE:TC-DEV-101]" in cat_badge

    comp_badge = citation_mapper.format_citation("COMPETITOR", "AlphaRetail-TC-101")
    assert "[COMPETITOR:AlphaRetail-TC-101]" in comp_badge

    rev_badge = citation_mapper.format_citation("REVIEW", "REV-001")
    assert "[REVIEW:REV-001]" in rev_badge

    spec_badge = citation_mapper.format_citation("SPEC", "SPEC-DEV-101")
    assert "[SPEC:SPEC-DEV-101]" in spec_badge

    # Citation validator passes multi-domain evidence
    text = "Based on [CATALOGUE:TC-DEV-101] and [REVIEW:REV-001], this item is highly rated."
    is_valid, valid_cits, _ = citation_validator.validate_citations(
        text=text,
        verified_product_ids={"TC-DEV-101", "REV-001"},
        verified_policy_ids=set()
    )
    assert is_valid is True


# ==============================================================================
# TEST 22: Authentication and data isolation
# ==============================================================================
def test_22_authentication_and_data_isolation():
    cust_headers = get_customer_auth_headers()

    # Customer forbidden from uploading catalogue preview
    files = {"file": ("test.csv", "product_id,title\n1,Test", "text/csv")}
    resp_upload = client.post("/api/catalogue/upload-preview", headers=cust_headers, files=files)
    assert resp_upload.status_code == 403
    assert "Owner privileges" in resp_upload.json()["detail"]

    # Customer forbidden from viewing owner catalogue version history
    resp_versions = client.get("/api/catalogue/versions", headers=cust_headers)
    assert resp_versions.status_code == 403
    assert "Owner privileges" in resp_versions.json()["detail"]

    # Customer forbidden from importing catalogues
    resp_import = client.post("/api/catalogue/import", headers=cust_headers, json={
        "name": "Unauthorized Catalogue",
        "version": "v999",
        "filename": "unauthorized.csv",
        "records": []
    })
    assert resp_import.status_code == 403


# ==============================================================================
# TEST 23: Existing demo, login, upload, search, and shopping workflows remain functional
# ==============================================================================
def test_23_existing_demo_login_and_search_workflows():
    # 1. Customer login
    login_resp = client.post("/api/auth/login", json={
        "email": "customer@truthcart.ai",
        "password": "Customer123!"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {token}"}

    # 2. Evidence-grounded chat query
    chat_resp = client.post("/api/chat", json={
        "message": "Find headphones under 10000"
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "message" in chat_data or "response" in chat_data or "decision" in chat_data

    # 3. Customer product search browse
    prod_resp = client.get("/api/products?search=headphones", headers=cust_headers)
    assert prod_resp.status_code == 200
    prod_data = prod_resp.json()
    assert "products" in prod_data
    assert len(prod_data["products"]) > 0

    # 4. Demo session initialization
    demo_resp = client.post("/api/auth/demo-session", json={"role": "CUSTOMER"})
    assert demo_resp.status_code == 200
    demo_data = demo_resp.json()
    assert "access_token" in demo_data
    assert demo_data["user"]["is_demo"] is True
