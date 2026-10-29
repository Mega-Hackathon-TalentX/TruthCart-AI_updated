import pytest
import json
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import db

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def init_test_db():
    db.init_db()

import uuid

# --- 1. AUTHENTICATION WORKFLOWS ---
def test_01_customer_signup_success():
    email = f"testshopper_{uuid.uuid4().hex[:6]}@example.com"
    resp = client.post("/api/auth/signup", json={
        "full_name": "Test Customer",
        "email": email,
        "password": "Password123!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "CUSTOMER"
    assert data["user"]["email"] == email

def test_02_public_signup_cannot_create_owner():
    email = f"sneaky_{uuid.uuid4().hex[:6]}@example.com"
    # Trying to send role in payload does not change role; role is strictly CUSTOMER
    resp = client.post("/api/auth/signup", json={
        "full_name": "Sneaky User",
        "email": email,
        "password": "Password123!",
        "role": "OWNER"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "CUSTOMER"

def test_03_owner_login_success():
    resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "OWNER"
    assert "access_token" in data

def test_04_invalid_credentials_rejected():
    resp = client.post("/api/auth/login", json={
        "email": "owner@truthcart.ai",
        "password": "WrongPassword999!"
    })
    assert resp.status_code == 401

def test_05_customer_forbidden_from_owner_endpoint():
    # 1. Log in as customer
    cust_resp = client.post("/api/auth/login", json={
        "email": "customer@truthcart.ai",
        "password": "Customer123!"
    })
    token = cust_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Attempt to call owner-only endpoint
    owner_resp = client.get("/api/catalogue/versions", headers=headers)
    assert owner_resp.status_code == 403
    assert "Owner privileges" in owner_resp.json()["detail"]

# --- 2. CATALOGUE & PERSISTENCE WORKFLOWS ---
def test_06_owner_catalogue_upload_preview():
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    token = owner_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    csv_data = (
        "product_id,title,category,price,stock_status\n"
        "TC-TEST-901,Test Laptop 14,Electronics,45000,In Stock\n"
        "TC-TEST-902,Test Mouse Wireless,Electronics,1200,In Stock\n"
    )
    files = {"file": ("test_catalog.csv", csv_data, "text/csv")}

    preview_resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert preview_resp.status_code == 200
    pdata = preview_resp.json()
    assert pdata["valid_count"] == 2
    assert pdata["invalid_count"] == 0
    assert len(pdata["preview_records"]) == 2

def test_07_invalid_catalogue_file_rejected():
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    token = owner_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    files = {"file": ("bad_file.exe", b"binarycontent", "application/octet-stream")}
    resp = client.post("/api/catalogue/upload-preview", headers=headers, files=files)
    assert resp.status_code == 400
    assert "Unsupported file format" in resp.json()["detail"]

def test_08_owner_import_and_activate():
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    token = owner_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    records = [
        {
            "product_id": "TC-IMPORT-01",
            "title": "Quantum Smart Watch",
            "description": "Fitness tracking smartwatch with AMOLED display.",
            "category": "Electronics",
            "price": 3499.0,
            "stock_status": "In Stock",
            "rating": 4.6,
            "attributes": {"battery": "7 days", "waterproof": "IP68"}
        }
    ]

    unique_version = f"v2.{uuid.uuid4().hex[:4]}.0"
    import_resp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Summer Tech 2026",
        "version": unique_version,
        "filename": "summer_tech.json",
        "records": records,
        "valid_count": 1,
        "invalid_count": 0,
        "validation_report": {"valid": 1}
    })
    assert import_resp.status_code == 200
    cat_id = import_resp.json()["id"]

    # Test Duplicate version rejection
    dup_resp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Duplicate Attempt",
        "version": unique_version,
        "filename": "summer_tech.json",
        "records": records,
        "valid_count": 1,
        "invalid_count": 0,
        "validation_report": {"valid": 1}
    })
    assert dup_resp.status_code == 400
    assert "already registered" in dup_resp.json()["detail"]

    # Activate version
    activate_resp = client.post(f"/api/catalogue/{cat_id}/activate", headers=headers)
    assert activate_resp.status_code == 200
    assert activate_resp.json()["total_active_products"] == 1

    # Verify customer search reflects newly activated catalogue
    search_resp = client.get("/api/products?search=Quantum")
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] == 1
    assert search_resp.json()["products"][0]["product_id"] == "TC-IMPORT-01"

    # Catalogue remains active for tests 09, 10, 11


# --- 3. CUSTOMER FEEDBACK & VERIFIED CORRECTIONS ---
def test_09_customer_feedback_persists_as_pending():
    cust_resp = client.post("/api/auth/login", json={
        "email": "customer@truthcart.ai",
        "password": "Customer123!"
    })
    token = cust_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    fb_resp = client.post("/api/feedback", headers=headers, json={
        "feedback_type": "incorrect_product_info",
        "product_id": "TC-IMPORT-01",
        "message": "The battery life stated is 7 days, but my product box says 10 days.",
        "rating": 4
    })
    assert fb_resp.status_code == 200
    fb_data = fb_resp.json()
    assert fb_data["status"] == "PENDING"
    assert fb_data["product_id"] == "TC-IMPORT-01"

    # CRITICAL RULE: Official product was NOT changed automatically!
    prod_resp = client.get("/api/products/TC-IMPORT-01")
    assert prod_resp.status_code == 200
    assert prod_resp.json()["attributes"]["battery"] == "7 days"

def test_10_customer_feedback_privacy_isolation():
    # 1. Customer A submits feedback
    cust_a = client.post("/api/auth/login", json={
        "email": "customer@truthcart.ai",
        "password": "Customer123!"
    })
    headers_a = {"Authorization": f"Bearer {cust_a.json()['access_token']}"}
    client.post("/api/feedback", headers=headers_a, json={
        "feedback_type": "general_usability",
        "message": "Private message from Customer A"
    })

    # 2. Customer B views their feedback
    email_b = f"customerb_{uuid.uuid4().hex[:6]}@example.com"
    cust_b = client.post("/api/auth/signup", json={
        "full_name": "Customer B",
        "email": email_b,
        "password": "Password123!"
    })
    headers_b = {"Authorization": f"Bearer {cust_b.json()['access_token']}"}
    my_fb_resp = client.get("/api/feedback/my", headers=headers_b)
    assert my_fb_resp.status_code == 200
    my_fbs = my_fb_resp.json()
    # Customer B cannot see Customer A's feedback
    for f in my_fbs:
        assert f["customer_email"] != "customer@truthcart.ai"

def test_11_owner_verified_correction_updates_product_and_index():
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    token = owner_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch pending feedback for the imported product
    fb_list = client.get("/api/feedback/owner?status=PENDING", headers=headers).json()
    assert len(fb_list) > 0
    target_fb = next((f for f in fb_list if f.get("product_id") == "TC-IMPORT-01"), None)
    assert target_fb is not None, "Pending feedback for TC-IMPORT-01 should exist"

    # Owner applies verified correction after inspecting official vendor invoice/box
    corr_resp = client.post("/api/feedback/verified-correction", headers=headers, json={
        "feedback_id": target_fb["id"],
        "product_id": target_fb["product_id"],
        "updates": {
            "attributes": {"battery": "10 days", "waterproof": "IP68"}
        },
        "resolution_note": "Verified with manufacturer packaging; battery specification updated to 10 days."
    })
    assert corr_resp.status_code == 200
    assert corr_resp.json()["status"] == "RESOLVED"

    # Official product in active catalogue is now updated
    updated_prod = client.get(f"/api/products/{target_fb['product_id']}").json()
    assert updated_prod["attributes"]["battery"] == "10 days"

    # Restore v1.0.0 official catalogue as active
    v1 = db.get_catalogue_by_version("v1.0.0")
    if v1:
        client.post(f"/api/catalogue/{v1['id']}/activate", headers=headers)

def test_12_audit_trail_recorded():
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    token = owner_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    audit_resp = client.get("/api/audit-logs", headers=headers)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) > 0
    actions = [l["action"] for l in logs]
    assert any("CATALOGUE" in a or "PRODUCT" in a or "FEEDBACK" in a for a in actions)

def test_13_system_stats_real_data():
    stats_resp = client.get("/api/system/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "active_catalogue" in stats
    assert "feedback" in stats
    assert stats["feedback"]["total"] >= 1
    assert "total_valid_products" in stats

def test_14_detailed_readiness():
    readiness_resp = client.get("/api/system/readiness")
    assert readiness_resp.status_code == 200
    rd = readiness_resp.json()
    assert "model_readiness" in rd
    assert "dataset_readiness" in rd
    assert "catalogue_db_readiness" in rd
    assert "product_index_readiness" in rd
    assert "policy_index_readiness" in rd
    assert "evidence_engine_readiness" in rd
    assert "api_readiness" in rd
