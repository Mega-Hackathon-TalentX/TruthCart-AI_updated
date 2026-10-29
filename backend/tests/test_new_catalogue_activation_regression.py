import os
import time
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db
from app.ingestion.universal_ingestor import universal_ingestor
from app.retrieval.semantic_search import local_vector_index
from app.retrieval.adaptive_embeddings import embedding_manager, BaseEmbeddingProvider

client = TestClient(app)

def get_owner_headers():
    resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

def wait_for_job(job_id: str, headers: dict, timeout_sec: float = 15.0):
    start = time.time()
    while time.time() - start < timeout_sec:
        res = client.get(f"/api/catalogue/jobs/{job_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        if data.get("status") in ("ACTIVE", "FAILED", "COMPLETED"):
            return data
        time.sleep(0.2)
    pytest.fail(f"Job {job_id} did not finish within {timeout_sec}s")


# 1. Activate previously working catalogue
def test_scenario_01_activate_previously_working_catalogue():
    headers = get_owner_headers()
    # Find v1.0.0 or any existing product catalogue
    cats = db.get_all_catalogues()
    v1 = next((c for c in cats if "1.0.0" in c["version"]), cats[0])
    
    res = client.post(f"/api/catalogue/{v1['id']}/activate?async_mode=false", headers=headers)
    assert res.status_code == 200
    
    active = db.get_active_catalogue()
    assert active is not None
    assert active["id"] == v1["id"]
    
    # Check products endpoint
    prod_res = client.get("/api/products")
    assert prod_res.status_code == 200
    assert prod_res.json()["total"] > 0


# 2. Activate a newly uploaded catalogue with the original supported schema
def test_scenario_02_activate_new_catalogue_original_schema():
    headers = get_owner_headers()
    v_new = f"v_orig_{uuid.uuid4().hex[:6]}"
    
    csv_text = """product_id,title,description,category,price,stock_status,rating,attributes
TC-ORIG-01,Original Cotton Polo,100% breathable pique cotton with rib collar,Apparel,1299.0,In Stock,4.6,"{""color"": ""Navy"", ""brand"": ""TalentPolo""}"
TC-ORIG-02,Original Denim Jacket,Heavyweight indigo denim with copper buttons,Apparel,3499.0,In Stock,4.8,"{""color"": ""Indigo"", ""brand"": ""TalentDenim""}"
"""
    files = {"file": ("orig_cat.csv", csv_text.encode("utf-8"), "text/csv")}
    prev = client.post("/api/catalogue/upload-preview", headers=headers, files=files).json()
    
    imp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Original Schema Cat",
        "filename": "orig_cat.csv",
        "version": v_new,
        "records": prev["all_valid_records"],
        "valid_count": prev["valid_count"],
        "invalid_count": prev["invalid_count"],
        "validation_report": {"errors": [], "warnings": []},
        "category": prev["detected_category"],
        "schema_mapping": prev["schema_mappings"]
    }).json()
    
    act = client.post(f"/api/catalogue/{imp['id']}/activate?async_mode=false", headers=headers)
    assert act.status_code == 200
    
    active = db.get_active_catalogue()
    assert active["version"] == v_new
    
    # Verify search
    search_res = client.get("/api/products?search=Polo").json()
    assert search_res["total"] >= 1
    assert any(p["product_id"] == "TC-ORIG-01" for p in search_res["products"])


# 3. Activate a newly uploaded catalogue with renamed columns
def test_scenario_03_activate_new_catalogue_renamed_columns():
    headers = get_owner_headers()
    v_renamed = f"v_ren_{uuid.uuid4().hex[:6]}"
    
    csv_text = """item_code,title,manufacturer,selling_price,technical_details
ITEM-REN-01,Anker Soundcore Motion Boom,Anker,8999.0,Titanium drivers with IPX7 waterproof rating and 24h playtime
ITEM-REN-02,Bose QuietComfort 45,Bose,21900.0,Acoustic noise cancelling with Aware mode and lightweight comfort
"""
    files = {"file": ("renamed_cat.csv", csv_text.encode("utf-8"), "text/csv")}
    prev = client.post("/api/catalogue/upload-preview", headers=headers, files=files).json()
    assert prev["detected_category"] == "PRODUCT_CATALOGUE"
    
    imp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Renamed Columns Cat",
        "filename": "renamed_cat.csv",
        "version": v_renamed,
        "records": prev["all_valid_records"],
        "valid_count": prev["valid_count"],
        "invalid_count": prev["invalid_count"],
        "validation_report": {"errors": [], "warnings": []},
        "category": prev["detected_category"],
        "schema_mapping": prev["schema_mappings"]
    }).json()
    
    act = client.post(f"/api/catalogue/{imp['id']}/activate?async_mode=false", headers=headers)
    assert act.status_code == 200
    
    # Check that technical_details is preserved as description and searchable
    search_res = client.get("/api/products?search=waterproof").json()
    assert search_res["total"] >= 1
    assert search_res["products"][0]["product_id"] == "ITEM-REN-01"


# 4. Activate a catalogue containing optional fields that are missing
def test_scenario_04_activate_catalogue_missing_optional_fields():
    headers = get_owner_headers()
    v_missing = f"v_miss_{uuid.uuid4().hex[:6]}"
    
    csv_text = """sku,item_name,mrp,stock_quantity
TC-MIN-01,Minimalist White Tee,599.0,50
TC-MIN-02,Minimalist Black Socks,299.0,0
"""
    files = {"file": ("minimal_cat.csv", csv_text.encode("utf-8"), "text/csv")}
    prev = client.post("/api/catalogue/upload-preview", headers=headers, files=files).json()
    
    imp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Minimal Cat",
        "filename": "minimal_cat.csv",
        "version": v_missing,
        "records": prev["all_valid_records"],
        "valid_count": prev["valid_count"],
        "invalid_count": prev["invalid_count"],
        "validation_report": {"errors": [], "warnings": []},
        "category": prev["detected_category"],
        "schema_mapping": prev["schema_mappings"]
    }).json()
    
    act = client.post(f"/api/catalogue/{imp['id']}/activate?async_mode=false", headers=headers)
    assert act.status_code == 200
    
    # Check in-stock filter: TC-MIN-01 has 50 (>0 -> In Stock), TC-MIN-02 has 0 (Out of Stock)
    instock_res = client.get("/api/products?in_stock_only=true").json()
    assert any(p["product_id"] == "TC-MIN-01" for p in instock_res["products"])
    assert not any(p["product_id"] == "TC-MIN-02" for p in instock_res["products"])


# 5. Activate a catalogue containing approximately 5,000 synthetic records
def test_scenario_05_activate_5000_records_async():
    headers = get_owner_headers()
    v_5k = f"v_5k_{uuid.uuid4().hex[:6]}"
    
    # Generate 5000 lightweight synthetic records
    records = []
    for i in range(1, 5001):
        records.append({
            "product_id": f"TC-5K-{i:05d}",
            "title": f"TruthCart Pro Item {i}",
            "description": f"Durable precision item number {i} with high performance finish.",
            "category": "Electronics" if i % 2 == 0 else "Apparel",
            "price": float(100 + (i % 500)),
            "stock_status": "In Stock" if i % 10 != 0 else "Out of Stock",
            "rating": 4.0 + ((i % 10) / 10.0),
            "attributes": {"brand": "TruthPro", "sku": f"SKU-{i:05d}"}
        })
        
    imp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Synthetic 5K Suite Cat",
        "filename": "truthcart_5k.json",
        "version": v_5k,
        "records": records,
        "valid_count": 5000,
        "invalid_count": 0,
        "validation_report": {"errors": [], "warnings": []},
        "category": "PRODUCT_CATALOGUE"
    }).json()
    
    act_res = client.post(f"/api/catalogue/{imp['id']}/activate?async_mode=true", headers=headers)
    assert act_res.status_code == 200
    job_id = act_res.json()["job_id"]
    
    job_final = wait_for_job(job_id, headers, timeout_sec=25.0)
    assert job_final["status"] == "ACTIVE"
    assert job_final["processed_records"] == 5000
    
    # Verify active in DB
    active = db.get_active_catalogue()
    assert active["version"] == v_5k


# 6. Verify that newly generated embeddings are stored or indexed correctly
def test_scenario_06_verify_embeddings_indexed():
    from app.ingestion.catalogue_loader import catalogue_loader
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)
    results = local_vector_index.search("Durable precision item", top_k=5)
    assert len(results) > 0
    top_prod, score = results[0]
    assert "TruthCart Pro Item" in top_prod.get("title", "")
    assert score > 0.0


# 7. Verify that the activated catalogue appears in search
def test_scenario_07_activated_catalogue_appears_in_search():
    from app.ingestion.catalogue_loader import catalogue_loader
    catalogue_loader.load_from_database()
    search_res = client.get("/api/products?search=TC-5K-00042").json()
    assert search_res["total"] == 1
    assert search_res["products"][0]["product_id"] == "TC-5K-00042"
    assert search_res["products"][0]["title"] == "TruthCart Pro Item 42"


# 8. Verify that semantic search can retrieve a newly uploaded record
def test_scenario_08_semantic_search_retrieves_record():
    from app.ingestion.catalogue_loader import catalogue_loader
    catalogue_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)
    results = local_vector_index.search("high performance finish apparel", top_k=5)
    assert len(results) > 0
    assert any("TruthCart Pro Item" in r[0].get("title", "") for r in results)


# 9. Verify that exact product identifiers work
def test_scenario_09_exact_product_identifier_lookup():
    from app.ingestion.catalogue_loader import catalogue_loader
    catalogue_loader.load_from_database()
    res = client.get("/api/products/TC-5K-00100")
    assert res.status_code == 200
    data = res.json()
    assert data["product_id"] == "TC-5K-00100"
    assert data["title"] == "TruthCart Pro Item 100"


# 10. Verify that numeric price filters work
def test_scenario_10_numeric_price_filters():
    from app.ingestion.catalogue_loader import catalogue_loader
    catalogue_loader.load_from_database()
    res = client.get("/api/products?min_price=150.0&max_price=160.0").json()
    assert res["total"] > 0
    for p in res["products"]:
        assert 150.0 <= p["price"] <= 160.0


# 11. Verify that an embedding provider failure produces a meaningful error
def test_scenario_11_embedding_provider_failure_reports_error():
    headers = get_owner_headers()
    v_fail = f"v_fail_{uuid.uuid4().hex[:6]}"
    
    # Import a catalogue
    imp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Fail Test Cat",
        "filename": "fail.json",
        "version": v_fail,
        "records": [{"product_id": "TC-F1", "title": "Fail Item", "price": 100.0, "category": "General"}],
        "valid_count": 1,
        "invalid_count": 0,
        "validation_report": {"errors": [], "warnings": []},
        "category": "PRODUCT_CATALOGUE"
    }).json()
    
    # Temporarily set a failing provider
    class FailingProvider(BaseEmbeddingProvider):
        @property
        def dimension(self) -> int:
            return 256
        @property
        def model_name(self) -> str:
            return "failing-provider"
        def embed_texts(self, texts, batch_size=32):
            raise ConnectionError("Mock embedding provider connection timed out.")
        def embed_query(self, query):
            raise ConnectionError("Mock query error.")
            
    old_provider = embedding_manager.provider
    try:
        embedding_manager.provider = FailingProvider()
        act_res = client.post(f"/api/catalogue/{imp['id']}/activate?async_mode=true", headers=headers)
        job_id = act_res.json()["job_id"]
        job_final = wait_for_job(job_id, headers, timeout_sec=10.0)
        assert job_final["status"] == "FAILED"
        assert "timed out" in str(job_final.get("error_message"))
        assert job_final["error_category"] == "EMBEDDING_FAILURE"
    finally:
        embedding_manager.provider = old_provider


# 12. Verify that vector-indexing failure does not produce a false Active status
def test_scenario_12_indexing_failure_no_false_active():
    headers = get_owner_headers()
    # Check catalogue table: Fail Test Cat should NOT be active
    cats = db.get_all_catalogues()
    fail_cat = next((c for c in cats if "Fail Test Cat" in c["name"]), None)
    assert fail_cat is not None
    assert fail_cat["is_active"] == 0
    assert fail_cat["status"] != "ACTIVE"


# 13. Verify that retrying activation does not create duplicate vectors or records
def test_scenario_13_retry_activation_idempotency():
    headers = get_owner_headers()
    # Re-activate the 5k dataset
    cats = db.get_all_catalogues()
    cat_5k = next((c for c in cats if "Synthetic 5K" in c["name"]), None)
    assert cat_5k is not None
    
    # Count products in DB before
    with db.get_connection() as conn:
        before_cnt = conn.execute("SELECT COUNT(*) as c FROM products WHERE catalogue_id = ?", (cat_5k["id"],)).fetchone()["c"]
        
    # Re-activate
    res = client.post(f"/api/catalogue/{cat_5k['id']}/activate?async_mode=true", headers=headers)
    if res.json().get("job_id"):
        wait_for_job(res.json()["job_id"], headers, timeout_sec=20.0)
        
    with db.get_connection() as conn:
        after_cnt = conn.execute("SELECT COUNT(*) as c FROM products WHERE catalogue_id = ?", (cat_5k["id"],)).fetchone()["c"]
        
    assert before_cnt == after_cnt == 5000


# 14. Verify that the old catalogue remains active and searchable after the fix
def test_scenario_14_switch_back_to_old_catalogue():
    headers = get_owner_headers()
    cats = db.get_all_catalogues()
    v1 = next((c for c in cats if "1.0.0" in c["version"]), cats[0])
    
    res = client.post(f"/api/catalogue/{v1['id']}/activate?async_mode=false", headers=headers)
    assert res.status_code == 200
    
    active = db.get_active_catalogue()
    assert active["id"] == v1["id"]
    
    # Products from v1 are visible
    prods = client.get("/api/products").json()
    assert prods["total"] > 0


# 15. Verify that frontend activation progress reaches a terminal state
def test_scenario_15_terminal_state_contract():
    headers = get_owner_headers()
    cats = client.get("/api/catalogue/versions", headers=headers).json()
    for cat in cats:
        # Every catalogue version must either be inactive, active, failed, or ready
        assert cat["status"] in ("ACTIVE", "ARCHIVED", "READY_FOR_ACTIVATION", "FAILED", "INDEX_BUILDING")
        if cat["is_active"]:
            assert cat["status"] == "ACTIVE"

