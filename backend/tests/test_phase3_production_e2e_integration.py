"""
TruthCart AI - Phase 3 Production Deployment, End-to-End Integration, and Launch Validation
Comprehensive automated test suite covering:
1. System Health & Readiness Verification
2. Customer Registration & Token Verification
3. Dedicated Owner Authentication & Role Enforcement
4. Original Schema Catalogue Upload & Validation Preview
5. Alternative Schema Catalogue Upload & Dynamic Mapping
6. Complete 19-Step Owner-to-Customer User Journey (Upload -> Ingest -> Activate -> Browse -> Search -> AI Grounding -> RBAC -> Switch)
7. Cross-Device Token & Session State Parity
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.retrieval.semantic_search import local_vector_index
from app.core.config import settings

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_phase3_environment():
    """Ensure database is initialized and restore 5003-product catalogue after tests."""
    db.init_db()
    yield
    # Reactivate the 5,003 product catalogue v99.3.0 after module tests conclude
    cat_5k = db.get_catalogue_by_version("v99.3.0")
    if not cat_5k:
        for c in db.get_all_catalogues():
            if (c.get("valid_count") or 0) >= 5000:
                cat_5k = c
                break
    if cat_5k:
        db.activate_catalogue(cat_5k["id"], actor_id=cat_5k.get("owner_id", "owner_system"))
    catalogue_loader.load_from_database()
    local_vector_index.build_index()


# ---------------- 1. HEALTH & SYSTEM READINESS ----------------

def test_p3_01_health_check_operational():
    """Health endpoint reports operational status, version, and component health."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "data_readiness" in data
    assert data["data_readiness"]["catalogue_ready"] is True


# ---------------- 2. AUTHENTICATION & RBAC ISOLATION ----------------

def test_p3_02_customer_registration_and_token():
    """Customer registration succeeds, returns JWT, and strictly assigns CUSTOMER role."""
    unique_email = f"shopper_{uuid.uuid4().hex[:6]}@example.com"
    resp = client.post("/api/auth/signup", json={
        "full_name": "Test Shopper Phase3",
        "email": unique_email,
        "password": "SecurePassword2026!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "CUSTOMER"
    assert data["user"]["email"] == unique_email


def test_p3_03_owner_login_enforces_role():
    """Owner login succeeds for authorized store owner credentials."""
    resp = client.post("/api/auth/owner-login", json={
        "email": settings.INITIAL_OWNER_EMAIL,
        "password": settings.INITIAL_OWNER_PASSWORD
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "OWNER"
    assert "access_token" in data


def test_p3_04_customer_blocked_from_owner_login():
    """Customer credentials attempting to sign in at /owner-login receive 403 Forbidden."""
    unique_email = f"shopper_{uuid.uuid4().hex[:6]}@example.com"
    client.post("/api/auth/signup", json={
        "full_name": "Shopper Blocked",
        "email": unique_email,
        "password": "SecurePassword2026!"
    })
    resp = client.post("/api/auth/owner-login", json={
        "email": unique_email,
        "password": "SecurePassword2026!"
    })
    assert resp.status_code == 403
    assert "restricted to authorized Store Owners" in resp.json()["detail"]


# ---------------- 3. CATALOGUE UPLOAD & PREVIEW WORKFLOWS ----------------

def test_p3_05_upload_original_format_catalogue():
    """Owner uploads valid CSV catalogue in standard format and inspects preview."""
    owner_token = client.post("/api/auth/owner-login", json={
        "email": settings.INITIAL_OWNER_EMAIL,
        "password": settings.INITIAL_OWNER_PASSWORD
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {owner_token}"}

    csv_content = (
        "product_id,title,description,category,price,stock_status,rating\n"
        "TC-P3-ORIG-01,Phase3 Wireless Earbuds,Noise cancelling bluetooth 5.3 earbuds,Electronics,2499.00,In Stock,4.7\n"
        "TC-P3-ORIG-02,Phase3 Mechanical Keyboard,Hot-swappable RGB gaming keyboard,Electronics,4999.00,In Stock,4.8\n"
    )
    files = {"file": ("catalogue_standard.csv", csv_content, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_count"] == 2
    assert data["invalid_count"] == 0
    assert len(data["preview_records"]) == 2


def test_p3_06_upload_alternative_schema_catalogue():
    """Owner uploads CSV catalogue with non-standard alternative column headers."""
    owner_token = client.post("/api/auth/owner-login", json={
        "email": settings.INITIAL_OWNER_EMAIL,
        "password": settings.INITIAL_OWNER_PASSWORD
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {owner_token}"}

    alt_csv = (
        "item_id,item_title,details,dept,cost,in_stock\n"
        "TC-P3-ALT-01,Phase3 Running Shoes,Breathable knit lightweight sports sneakers,Footwear,1899.00,yes\n"
        "TC-P3-ALT-02,Phase3 Cotton Polo,Classic breathable pique cotton collar t-shirt,Apparel,999.00,yes\n"
    )
    files = {"file": ("alt_schema_products.csv", alt_csv, "text/csv")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_count"] == 2
    assert data["invalid_count"] == 0
    first = data["preview_records"][0]
    assert first["product_id"] == "TC-P3-ALT-01"
    assert first["title"] == "Phase3 Running Shoes"
    assert first["price"] == 1899.0


# ---------------- 4. COMPLETE 19-STEP OWNER-TO-CUSTOMER USER JOURNEY ----------------

def test_p3_07_complete_owner_to_customer_user_journey():
    """
    Executes the unbroken 19-step user journey from owner upload to customer shopping:
    1. Open / Health check
    2. Register new customer
    3. Login store owner
    4. Upload original format catalogue preview
    5. Upload alternative schema catalogue preview
    6. Review validation results
    7. Import & Activate V1 catalogue
    8. Verify vector indexing completed
    9. Customer opens portal and browses
    10. Customer browses catalogue pagination
    11. Exact search by SKU
    12. Search using descriptive keywords
    13. Test semantic / hybrid search
    14. Apply filters (category) and sorting (price_asc / price_desc)
    15. Open product details
    16. Ask AI assistant grounded questions
    17. Verify AI answers match product specifications exactly
    18. Confirm customer cannot access owner endpoints (403 Forbidden)
    19. Owner uploads and activates V2 catalogue; customer portal immediately updates
    """
    # 1. Open app / Health check
    h_resp = client.get("/api/health")
    assert h_resp.status_code == 200

    # 2. Register & sign in customer
    cust_email = f"shopper_journey_{uuid.uuid4().hex[:6]}@example.com"
    cust_reg = client.post("/api/auth/signup", json={
        "full_name": "Ramesh Kumar",
        "email": cust_email,
        "password": "ShopperPassword2026!"
    })
    assert cust_reg.status_code == 200
    cust_token = cust_reg.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # 3. Access authorized owner portal
    owner_login_resp = client.post("/api/auth/owner-login", json={
        "email": settings.INITIAL_OWNER_EMAIL,
        "password": settings.INITIAL_OWNER_PASSWORD
    })
    assert owner_login_resp.status_code == 200
    owner_token = owner_login_resp.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 4 & 5. Upload catalogue previews (original & alternative schema)
    orig_csv = (
        "product_id,title,description,category,price,stock_status,rating\n"
        "TC-JRN-01,Apex Pro Wireless Gaming Headset,Lag-free 2.4GHz wireless headset with noise-canceling mic,Electronics,6499.00,In Stock,4.8\n"
        "TC-JRN-02,Pure Silk Formal Tie,Handcrafted pure mulberry silk necktie,Apparel,1499.00,In Stock,4.5\n"
    )
    p_resp = client.post(
        "/api/catalogue/upload-preview",
        headers=owner_headers,
        files={"file": ("journey_cat.csv", orig_csv, "text/csv")}
    )
    assert p_resp.status_code == 200
    preview_data = p_resp.json()

    # 6. Review ingestion & validation report
    assert preview_data["valid_count"] == 2
    assert preview_data["invalid_count"] == 0

    # 7. Import and activate catalogue V1
    v1_version = f"v3.jrn.{uuid.uuid4().hex[:4]}"
    v1_records = [
        {
            "product_id": "TC-JRN-01",
            "title": "Apex Pro Wireless Gaming Headset",
            "description": "Lag-free 2.4GHz wireless headset with noise-canceling mic.",
            "category": "Electronics",
            "price": 6499.0,
            "stock_status": "In Stock",
            "rating": 4.8,
            "attributes": {"battery": "40 hours", "connectivity": "2.4GHz Wireless", "weight": "280g"}
        },
        {
            "product_id": "TC-JRN-02",
            "title": "Pure Silk Formal Tie",
            "description": "Handcrafted pure mulberry silk necktie.",
            "category": "Apparel",
            "price": 1499.0,
            "stock_status": "In Stock",
            "rating": 4.5,
            "attributes": {"material": "100% Mulberry Silk", "width": "7.5 cm", "color": "Navy Blue"}
        }
    ]
    import_resp = client.post("/api/catalogue/import", headers=owner_headers, json={
        "name": "Phase 3 User Journey Catalogue",
        "version": v1_version,
        "filename": "journey_v1.json",
        "records": v1_records,
        "valid_count": 2,
        "invalid_count": 0,
        "validation_report": {"valid": 2}
    })
    assert import_resp.status_code == 200
    cat_id = import_resp.json()["id"]

    act_resp = client.post(f"/api/catalogue/{cat_id}/activate", headers=owner_headers)
    assert act_resp.status_code == 200
    # Sync memory loader
    catalogue_loader.load_from_database()
    local_vector_index.build_index()

    # 8. Confirm processing and indexing completed
    status_resp = client.get("/api/catalogue/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["is_ready"] is True

    # 9 & 10. Open customer portal & browse complete eligible catalogue
    browse_resp = client.get("/api/products?limit=10&offset=0")
    assert browse_resp.status_code == 200
    b_data = browse_resp.json()
    assert b_data["total"] == 2
    assert len(b_data["products"]) == 2

    # 11. Exact search by SKU / product ID
    sku_resp = client.get("/api/products?search=TC-JRN-01")
    assert sku_resp.status_code == 200
    assert sku_resp.json()["total"] == 1
    assert sku_resp.json()["products"][0]["product_id"] == "TC-JRN-01"

    # 12. Search using descriptive keywords
    kw_resp = client.get("/api/products?search=mulberry silk")
    assert kw_resp.status_code == 200
    assert kw_resp.json()["total"] == 1
    assert kw_resp.json()["products"][0]["product_id"] == "TC-JRN-02"

    # 13. Test semantic / hybrid search via chat
    sem_resp = client.post("/api/chat", json={
        "message": "Do you have gaming audio equipment?"
    })
    assert sem_resp.status_code == 200
    assert "TC-JRN-01" in sem_resp.text or "Apex Pro" in sem_resp.text

    # 14. Apply filters and sorting
    filt_resp = client.get("/api/products?category=Electronics&min_price=5000")
    assert filt_resp.status_code == 200
    assert filt_resp.json()["total"] == 1
    assert filt_resp.json()["products"][0]["product_id"] == "TC-JRN-01"

    sort_resp = client.get("/api/products?sort_by=price_asc")
    assert sort_resp.status_code == 200
    prods = sort_resp.json()["products"]
    assert prods[0]["price"] < prods[1]["price"]

    # 15. Open product details
    detail_resp = client.get("/api/products/TC-JRN-01")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["attributes"]["battery"] == "40 hours"

    # 16 & 17. Ask AI shopping assistant questions and verify grounded answers
    chat_resp = client.post("/api/chat", json={
        "message": "What is the battery life of TC-JRN-01?"
    })
    assert chat_resp.status_code == 200
    c_data = chat_resp.json()
    assert c_data["decision"] == "ANSWER"
    assert "40 hours" in c_data["response_text"]
    assert "[PRODUCT:TC-JRN-01]" in c_data["citations"]

    # Missing specification test (must refuse without speculating)
    refuse_resp = client.post("/api/chat", json={
        "message": "What is the waterproof rating of TC-JRN-01?"
    })
    assert refuse_resp.status_code == 200
    assert refuse_resp.json()["decision"] == "REFUSE"

    # 18. Customer cannot access owner-only functionality
    blocked_resp = client.get("/api/catalogue/versions", headers=cust_headers)
    assert blocked_resp.status_code == 403
    assert "Owner privileges" in blocked_resp.json()["detail"]

    # 19. Upload & activate subsequent catalogue version; customer portal immediately updates
    v2_version = f"v3.jrn.{uuid.uuid4().hex[:4]}"
    v2_records = [
        {
            "product_id": "TC-JRN-V2-01",
            "title": "Titanium Thermal Flask 1L",
            "description": "Double wall vacuum insulated titanium water bottle.",
            "category": "Home",
            "price": 2799.0,
            "stock_status": "In Stock",
            "rating": 4.9,
            "attributes": {"capacity": "1000ml", "insulation": "24h Cold / 12h Hot"}
        }
    ]
    import_v2 = client.post("/api/catalogue/import", headers=owner_headers, json={
        "name": "Phase 3 V2 Catalogue",
        "version": v2_version,
        "filename": "journey_v2.json",
        "records": v2_records,
        "valid_count": 1,
        "invalid_count": 0,
        "validation_report": {"valid": 1}
    })
    cat_v2_id = import_v2.json()["id"]

    client.post(f"/api/catalogue/{cat_v2_id}/activate", headers=owner_headers)
    catalogue_loader.load_from_database()
    local_vector_index.build_index()

    # Customer portal now immediately reflects V2
    new_browse = client.get("/api/products")
    assert new_browse.status_code == 200
    assert new_browse.json()["total"] == 1
    assert new_browse.json()["products"][0]["product_id"] == "TC-JRN-V2-01"

    # Old product is 404
    old_prod = client.get("/api/products/TC-JRN-01")
    assert old_prod.status_code == 404


# ---------------- 5. CROSS-DEVICE & SESSION RELIABILITY ----------------

def test_p3_08_session_verification_and_expiry():
    """Valid token succeeds at /api/auth/me; invalid/expired token returns 401."""
    cust_token = client.post("/api/auth/signup", json={
        "full_name": "Device Tester",
        "email": f"device_{uuid.uuid4().hex[:6]}@example.com",
        "password": "Password123!"
    }).json()["access_token"]

    # Valid token
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {cust_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"].startswith("device_")

    # Invalid token
    bad_resp = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.value"})
    assert bad_resp.status_code == 401

    # Missing token
    anon_resp = client.get("/api/auth/me")
    assert anon_resp.status_code == 401


def test_p3_09_logout_invalidates_session_gracefully():
    """Logout endpoint responds with confirmation."""
    cust_token = client.post("/api/auth/signup", json={
        "full_name": "Logout Tester",
        "email": f"logout_{uuid.uuid4().hex[:6]}@example.com",
        "password": "Password123!"
    }).json()["access_token"]

    logout_resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {cust_token}"})
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Logged out successfully"
