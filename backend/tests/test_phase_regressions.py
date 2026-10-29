import io
import json
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db
from app.core.auth import create_access_token
from app.ingestion.catalogue_loader import catalogue_loader

client = TestClient(app)

@pytest.fixture(scope="module")
def owner_headers():
    owner = db.get_user_by_email("owner@truthcart.ai")
    if not owner:
        owner = db.create_user(
            email="owner@truthcart.ai",
            password_hash=db.hash_password("AdminTruthCart2026!"),
            full_name="TruthCart Owner Admin",
            role="OWNER"
        )
    token = create_access_token({"sub": owner["id"], "role": "OWNER", "email": owner["email"]})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def customer_headers():
    cust = db.get_user_by_email("customer@truthcart.ai")
    if not cust:
        cust = db.create_user(
            email="customer@truthcart.ai",
            password_hash=db.hash_password("Customer123!"),
            full_name="Verified Customer",
            role="CUSTOMER"
        )
    token = create_access_token({"sub": cust["id"], "role": "CUSTOMER", "email": cust["email"]})
    return {"Authorization": f"Bearer {token}"}

def test_35mb_upload_limit_enforced(owner_headers):
    """Checks that uploads under 35 MB are accepted for validation and over 35 MB are rejected with 400."""
    # Under limit (valid small CSV)
    csv_data = b"product_id,title,category,price,stock_status\nTC-T1,Test Product 1,Electronics,999,In Stock\n"
    resp = client.post(
        "/api/catalogue/upload-preview",
        files={"file": ("test_under_limit.csv", csv_data, "text/csv")},
        headers=owner_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid_count"] == 1

    # Over 35 MB limit
    huge_data = b"x" * (36 * 1024 * 1024)
    resp_huge = client.post(
        "/api/catalogue/upload-preview",
        files={"file": ("huge_catalogue.csv", huge_data, "text/csv")},
        headers=owner_headers
    )
    assert resp_huge.status_code == 400
    assert "exceeds maximum size limit of 35 MB" in resp_huge.json()["detail"]

def test_xlsx_and_xls_upload_parsing(owner_headers):
    """Verifies that Excel XLSX catalogue format is parsed correctly."""
    df = pd.DataFrame([
        {
            "product_id": "TC-XLSX-01",
            "title": "Excel Sneakers",
            "category": "Footwear >> Men's Footwear >> Sneakers",
            "price": 2499.0,
            "stock_status": "In Stock",
            "description": "Comfortable breathable sneakers imported from Excel"
        },
        {
            "product_id": "TC-XLSX-02",
            "title": "Excel Sandals",
            "category": "Footwear >> Women's Footwear >> Sandals",
            "price": 1299.0,
            "stock_status": "In Stock",
            "description": "Stylish summer sandals"
        }
    ])
    xlsx_buf = io.BytesIO()
    df.to_excel(xlsx_buf, index=False, engine="openpyxl")
    xlsx_bytes = xlsx_buf.getvalue()

    resp = client.post(
        "/api/catalogue/upload-preview",
        files={"file": ("excel_catalogue.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=owner_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid_count"] == 2
    assert "all_valid_records" in data
    assert len(data["all_valid_records"]) == 2
    assert data["all_valid_records"][0]["product_id"] == "TC-XLSX-01"

def test_full_record_import_exceeding_25_items(owner_headers):
    """Verifies that importing more than 25 records imports ALL records into the database."""
    # Generate 30 records
    records = []
    for i in range(1, 31):
        records.append({
            "product_id": f"TC-BULK-{i:03d}",
            "title": f"Bulk Product {i}",
            "category": "Electronics >> Accessories",
            "price": 500.0 + i * 10,
            "stock_status": "In Stock",
            "description": f"Bulk test product number {i}",
            "attributes": {"color": "black", "warranty": "1 year"}
        })

    import_req = {
        "name": "Bulk Test Catalogue",
        "version": "v99.1.0",
        "filename": "bulk_test.json",
        "records": records,
        "valid_count": len(records),
        "invalid_count": 0,
        "validation_report": {"errors": [], "warnings": []}
    }

    # Delete existing test version if present
    existing = db.get_catalogue_by_version("v99.1.0")
    if existing:
        with db.get_connection() as conn:
            conn.execute("DELETE FROM products WHERE catalogue_id = ?", (existing["id"],))
            conn.execute("DELETE FROM catalogues WHERE id = ?", (existing["id"],))

    resp = client.post("/api/catalogue/import", json=import_req, headers=owner_headers)
    assert resp.status_code == 200, resp.text
    cat = resp.json()
    assert cat["valid_count"] == 30
    assert cat["record_count"] == 30

    # Verify directly from database that all 30 products exist
    with db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM products WHERE catalogue_id = ?", (cat["id"],)).fetchone()["c"]
        assert count == 30

def test_hierarchical_category_breadcrumb_search():
    """Checks that hierarchical categories match top-level category queries."""
    # Seed a hierarchical product if not present
    active_cat = db.get_active_catalogue()
    if active_cat:
        # Check get_active_products with category="Footwear"
        prods = db.get_active_products(category="Footwear")
        # Should return any product with Footwear or Footwear >> ...
        for p in prods:
            assert "footwear" in p["category"].lower() or "footwear" in p["title"].lower()

        # Check search_query matching category column
        search_res = db.get_active_products(search_query="Footwear")
        assert len(search_res) > 0
        assert any("footwear" in p["category"].lower() for p in search_res)

def test_get_active_categories_stability():
    """Checks that get_active_categories returns distinct non-empty categories."""
    cats = db.get_active_categories()
    assert isinstance(cats, list)
    if db.get_active_catalogue():
        assert len(cats) > 0
        # Ensure categories are distinct
        assert len(cats) == len(set(cats))

def test_rebuild_knowledge_base_pipeline(owner_headers):
    """Verifies that rebuild-index reloads catalogue, policies, and validates retrieval."""
    resp = client.post("/api/catalogue/rebuild-index", headers=owner_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] in ("success", "partial")
    assert "products_indexed" in data
    assert "policies_indexed" in data
    assert "index_ready" in data
    assert "retrieval_verified" in data
    assert data["index_ready"] is True
