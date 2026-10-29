import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db
from app.core.auth import create_access_token

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

# ==============================================================================
# 1. HIERARCHICAL CATEGORY DATA MODEL & RETRIEVAL TESTS
# ==============================================================================

def test_categories_api_returns_active_catalogue_categories():
    """Verifies that /api/products returns all distinct categories from active catalogue."""
    resp = client.get("/api/products")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert isinstance(data["categories"], list)
    assert len(data["categories"]) > 0

def test_parent_category_filtering_includes_children():
    """
    Selecting a top-level parent category such as 'Footwear' returns products
    belonging to that category or its subcategories.
    """
    resp = client.get("/api/products?category=Footwear")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    for p in data["products"]:
        cat_lower = p["category"].lower()
        title_lower = p["title"].lower()
        assert "footwear" in cat_lower or "footwear" in title_lower

def test_subcategory_filtering_returns_specific_subset():
    """Filtering by a subcategory returns products matching that subcategory."""
    # First get list of all categories
    resp = client.get("/api/products")
    categories = resp.json()["categories"]
    
    # Find a hierarchical category if available
    subcat = next((c for c in categories if ">>" in c), None)
    if subcat:
        resp_sub = client.get("/api/products", params={"category": subcat})
        assert resp_sub.status_code == 200
        sub_data = resp_sub.json()
        assert sub_data["total"] > 0
        for p in sub_data["products"]:
            assert subcat.lower() in p["category"].lower()

def test_clearing_category_restores_all_products():
    """Clearing category filter (no category query param) returns all active products."""
    resp_all = client.get("/api/products")
    total_all = resp_all.json()["total"]

    resp_filtered = client.get("/api/products?category=Footwear")
    total_filtered = resp_filtered.json()["total"]

    # Unfiltered count must be greater than or equal to filtered
    assert total_all >= total_filtered
    assert total_all > 0

def test_combined_category_and_price_filters():
    """Combining category and price filters applies both constraints correctly."""
    resp = client.get("/api/products?category=Footwear&max_price=4000")
    assert resp.status_code == 200
    data = resp.json()
    for p in data["products"]:
        assert p["price"] <= 4000
        assert "footwear" in p["category"].lower() or "footwear" in p["title"].lower()

def test_combined_category_and_stock_filters():
    """Combining category and in-stock filter returns only in-stock items."""
    resp = client.get("/api/products?category=Footwear&in_stock_only=true")
    assert resp.status_code == 200
    data = resp.json()
    for p in data["products"]:
        assert p["stock_status"].lower() in ("in stock", "instock", "1")

def test_nonexistent_category_returns_clean_empty_results():
    """Filtering by a non-existent category returns 0 products without errors."""
    resp = client.get("/api/products?category=NonExistentCategoryXYZ123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["products"]) == 0

# ==============================================================================
# 2. AUTHORIZATION & SECURITY TESTS (DEMO SWITCH PRESERVATION)
# ==============================================================================

def test_customer_token_cannot_access_owner_catalogue_api(customer_headers):
    """Customer accounts are strictly forbidden (403) from accessing owner catalogue endpoints."""
    resp = client.get("/api/catalogue/versions", headers=customer_headers)
    assert resp.status_code == 403
    assert "verified Store Owner privileges" in resp.json()["detail"]

def test_customer_token_cannot_access_owner_audit_api(customer_headers):
    """Customer accounts are strictly forbidden (403) from accessing owner audit logs."""
    resp = client.get("/api/audit-logs", headers=customer_headers)
    assert resp.status_code == 403

def test_customer_token_cannot_rebuild_knowledge_base(customer_headers):
    """Customer accounts cannot invoke knowledge-base rebuild."""
    resp = client.post("/api/catalogue/rebuild-index", headers=customer_headers)
    assert resp.status_code == 403

def test_customer_token_cannot_modify_products(customer_headers):
    """Customer accounts cannot directly mutate official product catalogue."""
    resp = client.put("/api/products/TC-FT-301", json={"price": 10.0}, headers=customer_headers)
    assert resp.status_code == 403

def test_unauthenticated_requests_to_owner_apis_rejected():
    """Unauthenticated requests to owner APIs are rejected with 401 Unauthorized."""
    resp = client.get("/api/catalogue/versions")
    assert resp.status_code == 401

def test_owner_token_succeeds_on_owner_endpoints(owner_headers):
    """Legitimate owner tokens are authorized on owner management endpoints."""
    resp = client.get("/api/catalogue/versions", headers=owner_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
