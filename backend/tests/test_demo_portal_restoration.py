import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db

client = TestClient(app)

# ==============================================================================
# DEMO RESTORATION & STRICT ISOLATION TEST SUITE
# ==============================================================================

def test_01_create_customer_demo_session():
    """Requirement 1 & 2: 'Try Customer Demo' provisions an isolated customer demo session."""
    resp = client.post("/api/auth/demo-session", json={"role": "CUSTOMER"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "CUSTOMER"
    assert data["user"]["is_demo"] is True
    assert "customer" in data["user"]["email"]

def test_02_create_owner_demo_session():
    """Requirement 1 & 3: 'Try Owner Demo' provisions an isolated owner demo session."""
    resp = client.post("/api/auth/demo-session", json={"role": "OWNER"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "OWNER"
    assert data["user"]["is_demo"] is True
    assert "owner" in data["user"]["email"]

def test_03_customer_demo_can_browse_and_filter_products():
    """Requirement 4: Customer demo can browse products and use category, price, and stock filters."""
    demo_resp = client.post("/api/auth/demo-session", json={"role": "CUSTOMER"}).json()
    token = demo_resp["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Browse all products
    resp = client.get("/api/products", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] > 0

    # 2. Category filtering
    resp_cat = client.get("/api/products?category=Footwear", headers=headers)
    assert resp_cat.status_code == 200
    assert resp_cat.json()["total"] > 0

    # 3. Price filtering
    resp_price = client.get("/api/products?max_price=3000", headers=headers)
    assert resp_price.status_code == 200
    for p in resp_price.json()["products"]:
        assert p["price"] <= 3000

    # 4. Stock filtering
    resp_stock = client.get("/api/products?in_stock_only=true", headers=headers)
    assert resp_stock.status_code == 200

def test_04_owner_demo_displays_owner_dashboard():
    """Requirement 5: Owner demo displays system stats, catalogue versions, and owner dashboard."""
    demo_resp = client.post("/api/auth/demo-session", json={"role": "OWNER"}).json()
    token = demo_resp["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. System stats
    resp_stats = client.get("/api/system/stats", headers=headers)
    assert resp_stats.status_code == 200

    # 2. Catalogue versions
    resp_versions = client.get("/api/catalogue/versions", headers=headers)
    assert resp_versions.status_code == 200
    assert isinstance(resp_versions.json(), list)

    # 3. Product catalogue view
    resp_prods = client.get("/api/products", headers=headers)
    assert resp_prods.status_code == 200

def test_05_demo_only_portal_switching_works():
    """Requirement 6: Switching between customer demo and owner demo works without credentials."""
    # Start in customer demo
    cust_demo = client.post("/api/auth/demo-session", json={"role": "CUSTOMER"}).json()
    cust_token = cust_demo["access_token"]
    assert cust_demo["user"]["role"] == "CUSTOMER"
    assert cust_demo["user"]["is_demo"] is True

    # Switch to owner demo
    owner_demo = client.post("/api/auth/demo-session", json={"role": "OWNER"}).json()
    owner_token = owner_demo["access_token"]
    assert owner_demo["user"]["role"] == "OWNER"
    assert owner_demo["user"]["is_demo"] is True

    # Customer token cannot access owner APIs, but owner demo token can
    resp_forbidden = client.get("/api/catalogue/versions", headers={"Authorization": f"Bearer {cust_token}"})
    assert resp_forbidden.status_code == 403

    resp_allowed = client.get("/api/catalogue/versions", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp_allowed.status_code == 200

def test_06_real_customer_cannot_access_owner_apis_and_is_not_demo():
    """Requirement 7: Real registered customer does not have is_demo and cannot access owner APIs."""
    clean_email = f"real_customer_{id(test_06_real_customer_cannot_access_owner_apis_and_is_not_demo)}@example.com"
    reg_resp = client.post("/api/auth/signup", json={
        "email": clean_email,
        "full_name": "Real Shopper",
        "password": "Password123!"
    })
    assert reg_resp.status_code == 200
    data = reg_resp.json()
    assert data["user"]["role"] == "CUSTOMER"
    assert data["user"]["is_demo"] is False

    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify session profile via /auth/me
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["is_demo"] is False
    assert me_resp.json()["role"] == "CUSTOMER"

    # Strictly forbidden from owner endpoints
    resp = client.get("/api/catalogue/versions", headers=headers)
    assert resp.status_code == 403

def test_07_real_owner_session_does_not_inherit_demo_state():
    """Requirement 8: Real owner sessions do not inherit demo state."""
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    assert owner_resp.status_code == 200
    data = owner_resp.json()
    assert data["user"]["role"] == "OWNER"
    assert data["user"]["is_demo"] is False

    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["is_demo"] is False

def test_08_demo_owner_cannot_access_real_customer_feedback():
    """Requirement 9: Demo sessions cannot view real customer feedback data."""
    # First submit a real customer feedback
    real_email = f"real_feedback_user_{id(test_08_demo_owner_cannot_access_real_customer_feedback)}@example.com"
    real_user = client.post("/api/auth/signup", json={
        "email": real_email,
        "full_name": "Private Customer",
        "password": "Password123!"
    }).json()
    real_token = real_user["access_token"]

    secret_msg = "PRIVATE_CONFIDENTIAL_FEEDBACK_MESSAGE_12345"
    fb_sub = client.post("/api/feedback", json={
        "feedback_type": "catalogue_issue",
        "message": secret_msg,
        "rating": 5
    }, headers={"Authorization": f"Bearer {real_token}"})
    assert fb_sub.status_code == 200

    # Now inspect feedback as demo owner
    demo_owner = client.post("/api/auth/demo-session", json={"role": "OWNER"}).json()
    demo_token = demo_owner["access_token"]
    owner_fb_resp = client.get("/api/feedback/owner", headers={"Authorization": f"Bearer {demo_token}"})
    assert owner_fb_resp.status_code == 200

    # Ensure demo owner feedback list NEVER contains private real customer feedback
    owner_feedbacks = owner_fb_resp.json()
    messages = [f["message"] for f in owner_feedbacks]
    assert secret_msg not in messages

def test_09_demo_mutations_cannot_alter_production_catalogue():
    """Requirement 10: Demo sessions cannot activate or import production catalogue versions."""
    demo_owner = client.post("/api/auth/demo-session", json={"role": "OWNER"}).json()
    demo_token = demo_owner["access_token"]
    headers = {"Authorization": f"Bearer {demo_token}"}

    # Attempt to activate catalogue
    resp = client.post("/api/catalogue/v1.0.0/activate", headers=headers)
    assert resp.status_code == 403
    assert "Demo Mode Protection" in resp.json()["detail"]

    # Attempt to import catalogue
    resp_imp = client.post("/api/catalogue/import", json={
        "name": "Demo Malicious Import",
        "version": "v9.9.9",
        "filename": "fake.csv",
        "records": [{"product_id": "TC-FAKE-01", "title": "Fake Product", "price": 10.0, "category": "Footwear"}],
        "valid_count": 1,
        "invalid_count": 0
    }, headers=headers)
    assert resp_imp.status_code == 403
    assert "Demo Mode Protection" in resp_imp.json()["detail"]

def test_10_demo_mutations_cannot_alter_official_product_records():
    """Requirement 10: Demo sessions cannot update or archive official products."""
    demo_owner = client.post("/api/auth/demo-session", json={"role": "OWNER"}).json()
    demo_token = demo_owner["access_token"]
    headers = {"Authorization": f"Bearer {demo_token}"}

    # Attempt to alter product price
    resp = client.put("/api/products/TC-FT-301", json={"price": 1.0}, headers=headers)
    assert resp.status_code == 403
    assert "Demo Mode Protection" in resp.json()["detail"]

    # Attempt to archive product
    resp_del = client.delete("/api/products/TC-FT-301", headers=headers)
    assert resp_del.status_code == 403
    assert "Demo Mode Protection" in resp_del.json()["detail"]

def test_11_normal_login_and_registration_continue_to_work():
    """Requirement 11: Normal customer login, customer registration, and owner login succeed."""
    # 1. Customer registration
    reg_email = f"normal_user_{id(test_11_normal_login_and_registration_continue_to_work)}@example.com"
    reg = client.post("/api/auth/signup", json={
        "email": reg_email,
        "full_name": "Standard User",
        "password": "ValidPassword123!"
    })
    assert reg.status_code == 200

    # 2. Customer login
    login_resp = client.post("/api/auth/login", json={
        "email": reg_email,
        "password": "ValidPassword123!"
    })
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["role"] == "CUSTOMER"

    # 3. Owner login
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    assert owner_resp.status_code == 200
    assert owner_resp.json()["user"]["role"] == "OWNER"

def test_12_logout_and_session_revalidation():
    """Requirement 12 & 13: Exiting demo mode or reloading preserves verified session state."""
    demo_cust = client.post("/api/auth/demo-session", json={"role": "CUSTOMER"}).json()
    headers = {"Authorization": f"Bearer {demo_cust['access_token']}"}

    # Verify session persists across reloads via /auth/me
    reload_resp = client.get("/api/auth/me", headers=headers)
    assert reload_resp.status_code == 200
    assert reload_resp.json()["is_demo"] is True

    # Logout
    logout_resp = client.post("/api/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
