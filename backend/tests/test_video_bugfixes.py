import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.ingestion.policy_loader import policy_loader
from app.retrieval.hybrid_retriever import hybrid_retriever
from app.retrieval.semantic_search import local_vector_index
from app.llm.query_understanding import query_understanding
from app.evidence_engine.decision_engine import decision_engine
from app.evidence_engine.citation_validator import citation_validator
from app.llm.model_loader import model_loader

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_video_test_environment():
    """Ensures database is initialized and official catalogue and policy are active."""
    db.init_db()
    with db.get_connection() as conn:
        official_cat = conn.execute("SELECT id FROM catalogues WHERE name LIKE '%Hackathon%' OR name LIKE '%Official%' LIMIT 1").fetchone()
        if official_cat:
            db.activate_catalogue(official_cat["id"], actor_id="setup_video")
    catalogue_loader.load_from_database()
    policy_loader.load_from_database()
    local_vector_index.build_index(force_rebuild=True)
    yield
    # Restore official catalogue & policy state after test
    catalogue_loader.load_from_database()
    policy_loader.load_from_database()

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 1: Footwear category query with matching products
# --------------------------------------------------------------------------
def test_01_footwear_category_with_matching_products():
    """Query: 'Is there any footwear available?' must return footwear products with grounded evidence."""
    query = "Is there any footwear available?"
    resp = client.post("/api/chat", json={"message": query})
    assert resp.status_code == 200
    data = resp.json()

    assert data["decision"] == "ANSWER"
    assert len(data["products"]) > 0
    pids = [p["product_id"] for p in data["products"]]
    # Verify Footwear SKUs are returned
    assert any(pid in ("TC-FT-301", "TC-FT-302", "TC-FT-303") for pid in pids)
    assert len(data["citations"]) > 0
    assert any("[PRODUCT:TC-FT-" in c for c in data["citations"])
    
    # Verify citations are valid
    is_valid, _, invalid_cits = citation_validator.validate_citations(
        data["response_text"],
        verified_product_ids=set(pids),
        verified_policy_ids=set()
    )
    assert is_valid is True
    assert len(invalid_cits) == 0

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 2: Slippers query when slippers do not exist
# --------------------------------------------------------------------------
def test_02_slippers_query_when_slippers_do_not_exist():
    """Query: 'I want slippers.' must state slippers are absent, offer verified footwear alternatives, without hallucinating."""
    query = "I want slippers."
    resp = client.post("/api/chat", json={"message": query})
    assert resp.status_code == 200
    data = resp.json()

    # System answers with explanation of absence + verified alternatives
    assert data["decision"] == "ANSWER"
    response_lower = data["response_text"].lower()
    assert "slipper" in response_lower
    # Offers verified footwear alternatives
    assert len(data["products"]) > 0
    pids = [p["product_id"] for p in data["products"]]
    assert any(pid in ("TC-FT-301", "TC-FT-302", "TC-FT-303") for pid in pids)
    assert any("[PRODUCT:TC-FT-" in c for c in data["citations"])

    # Citations are strictly validated
    is_valid, _, invalid_cits = citation_validator.validate_citations(
        data["response_text"],
        verified_product_ids=set(pids),
        verified_policy_ids=set()
    )
    assert is_valid is True

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 3: Budget filtering after footwear follow-up
# --------------------------------------------------------------------------
def test_03_budget_filtering_after_footwear_followup():
    """Query: 'Under 2000' after footwear conversation must refuse citing minimum price ₹3,299 without warranty routing."""
    conv_id = f"test-conv-{uuid.uuid4().hex[:6]}"
    
    # Step 1: User asks about footwear
    resp1 = client.post("/api/chat", json={
        "message": "Is there any footwear available?",
        "conversation_id": conv_id
    })
    assert resp1.status_code == 200

    # Step 2: User follows up with budget constraint
    resp2 = client.post("/api/chat", json={
        "message": "Under 2000",
        "conversation_id": conv_id
    })
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data2["decision"] == "REFUSE"
    # Must explain that lowest footwear price is 3,299
    resp_text = data2["response_text"]
    assert "3,299" in resp_text or "3299" in resp_text
    # Must NOT route to warranty policy!
    assert "warranty" not in resp_text.lower()
    assert not any("[POLICY:" in c for c in data2["citations"])
    # Cites the lowest priced footwear item
    assert any("[PRODUCT:TC-FT-301]" in c for c in data2["citations"])

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 4: Empty or missing active catalogue handling
# --------------------------------------------------------------------------
def test_04_empty_or_missing_active_catalogue():
    """When catalogue is unavailable, system returns clean refusal distinguishing it from 'no product matched'."""
    parsed = query_understanding.parse("Show me running shoes")
    was_ready = catalogue_loader.is_ready
    catalogue_loader.is_ready = False
    try:
        ev = decision_engine.evaluate("Show me running shoes", parsed, [], None)
        assert ev.decision == "REFUSE"
        assert "unsupported_fields" in ev.model_dump()
        assert "catalogue_data" in ev.unsupported_fields
        assert "catalogue" in ev.refusal_reason.lower()
    finally:
        catalogue_loader.is_ready = was_ready

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 5: Switching to a newly activated catalogue
# --------------------------------------------------------------------------
def test_05_switching_to_newly_activated_catalogue():
    """Switching active catalogue version updates the active flag and customer product lookup."""
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    token = owner_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    v_unique = f"v-switch-{uuid.uuid4().hex[:6]}"
    # 1. Import a new version
    import_resp = client.post("/api/catalogue/import", headers=headers, json={
        "name": f"Switch Test Catalogue {v_unique}",
        "version": v_unique,
        "filename": f"switch_{v_unique}.json",
        "records": [{
            "product_id": f"TC-SW-{uuid.uuid4().hex[:4]}",
            "title": "Switch Test Product",
            "description": "Verification product for activation switch",
            "category": "Electronics",
            "price": 4999.0,
            "stock_status": "In Stock",
            "rating": 4.5,
            "attributes": {"color": "Silver"}
        }],
        "valid_count": 1,
        "invalid_count": 0,
        "validation_report": {"valid": 1}
    })
    assert import_resp.status_code == 200
    cat_id = import_resp.json()["id"]

    # 2. Activate the new catalogue
    act_resp = client.post(f"/api/catalogue/{cat_id}/activate", headers=headers)
    assert act_resp.status_code == 200
    assert act_resp.json()["total_active_products"] == 1

    # 3. Verify search returns the new product
    prod_resp = client.get("/api/products?search=Switch")
    assert prod_resp.status_code == 200
    assert prod_resp.json()["total"] == 1

    # 4. Restore official v1.0.0 catalogue
    v1 = db.get_catalogue_by_version("v1.0.0")
    if v1:
        client.post(f"/api/catalogue/{v1['id']}/activate", headers=headers)

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 6: Duplicate catalogue upload prevention
# --------------------------------------------------------------------------
def test_06_duplicate_catalogue_upload_prevention():
    """Attempting to import an existing catalogue version returns HTTP 400."""
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    headers = {"Authorization": f"Bearer {owner_resp.json()['access_token']}"}

    dup_resp = client.post("/api/catalogue/import", headers=headers, json={
        "name": "Duplicate Attempt",
        "version": "v1.0.0",
        "filename": "catalogue.json",
        "records": [{"product_id": "TC-DUP-01", "title": "Dup", "category": "General", "price": 10.0, "stock_status": "In Stock"}],
        "valid_count": 1,
        "invalid_count": 0,
        "validation_report": {"valid": 1}
    })
    assert dup_resp.status_code == 400
    assert "already registered" in dup_resp.json()["detail"].lower()

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 7: Exactly one active catalogue version
# --------------------------------------------------------------------------
def test_07_exactly_one_active_catalogue_version():
    """Database must have exactly one active catalogue version per store deployment."""
    with db.get_connection() as conn:
        active_rows = conn.execute("SELECT id, version FROM catalogues WHERE is_active = 1").fetchall()
        assert len(active_rows) == 1, f"Expected exactly 1 active catalogue, found {len(active_rows)}"

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 8: Model-unavailable and fallback states
# --------------------------------------------------------------------------
def test_08_model_unavailable_and_fallback_states():
    """System readiness accurately reports local checkpoint state vs. deterministic rule generator."""
    resp = client.get("/api/system/readiness")
    assert resp.status_code == 200
    data = resp.json()

    model_rd = data["model_readiness"]
    # Does NOT falsely claim local checkpoint when only README.md exists
    assert model_rd["real_instruction_model_loaded"] is False
    assert model_rd["deterministic_fallback_active"] is True
    assert model_rd["status"] == "fallback_active"
    assert "Deterministic Grounded Rule Generator" in model_rd["fallback"]

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 9: Product queries not routed to warranty policy
# --------------------------------------------------------------------------
def test_09_product_queries_not_routed_to_warranty_policy():
    """Price, budget, and product queries must never be routed to warranty policy retrieval."""
    test_queries = [
        "Under 2000",
        "Show me shoes under 2000",
        "What is the cost of TC-EL-201?",
        "Find headphones under 5000"
    ]
    for q in test_queries:
        parsed = query_understanding.parse(q)
        assert parsed.get("is_policy_query") is False
        prods, pol = hybrid_retriever.retrieve(q, parsed)
        ev = decision_engine.evaluate(q, parsed, prods, pol)
        # Policy evidence must NEVER be returned for product queries
        policy_ev = [e for e in ev.evidence if e.source_type == "policy"]
        assert len(policy_ev) == 0, f"Query '{q}' was incorrectly routed to policy evidence: {policy_ev}"

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 10: One feedback submission producing one record
# --------------------------------------------------------------------------
def test_10_one_feedback_submission_producing_one_record():
    """One customer feedback form submission creates exactly one DB record."""
    cust_resp = client.post("/api/auth/login", json={
        "email": "customer@truthcart.ai",
        "password": "Customer123!"
    })
    token = cust_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with db.get_connection() as conn:
        count_before = conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"]

    unique_msg = f"Feedback regression test message {uuid.uuid4().hex[:6]}"
    fb_resp = client.post("/api/feedback", headers=headers, json={
        "feedback_type": "catalogue_issue",
        "message": unique_msg,
        "rating": 5
    })
    assert fb_resp.status_code == 200
    fb_id = fb_resp.json()["id"]

    with db.get_connection() as conn:
        count_after = conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"]
        assert count_after == count_before + 1
        row = conn.execute("SELECT * FROM feedback WHERE id = ?", (fb_id,)).fetchone()
        assert row is not None
        assert row["status"] == "PENDING"
        assert row["message"] == unique_msg

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 11: Customer isolation and owner authorization
# --------------------------------------------------------------------------
def test_11_customer_isolation_and_owner_authorization():
    """Customer A cannot see Customer B's feedback. Customer role receives 403 on owner endpoints."""
    # 1. Customer signup
    email_x = f"shopper_{uuid.uuid4().hex[:6]}@example.com"
    cust_x = client.post("/api/auth/signup", json={
        "full_name": "Shopper X",
        "email": email_x,
        "password": "Password123!"
    })
    assert cust_x.status_code == 200
    token_x = cust_x.json()["access_token"]
    headers_x = {"Authorization": f"Bearer {token_x}"}

    # 2. Customer X submits feedback
    client.post("/api/feedback", headers=headers_x, json={
        "feedback_type": "general_usability",
        "message": f"Private feedback from Shopper X {uuid.uuid4().hex[:4]}"
    })

    # 3. Customer Y views their feedback
    email_y = f"shopper_{uuid.uuid4().hex[:6]}@example.com"
    cust_y = client.post("/api/auth/signup", json={
        "full_name": "Shopper Y",
        "email": email_y,
        "password": "Password123!"
    })
    headers_y = {"Authorization": f"Bearer {cust_y.json()['access_token']}"}
    my_fbs = client.get("/api/feedback/my", headers=headers_y).json()
    assert all(f["customer_email"] == email_y for f in my_fbs)

    # 4. Customer attempts to access owner-only endpoints -> 403 Forbidden
    owner_fb_resp = client.get("/api/feedback/owner", headers=headers_x)
    assert owner_fb_resp.status_code == 403

    owner_vers_resp = client.get("/api/catalogue/versions", headers=headers_x)
    assert owner_vers_resp.status_code == 403

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 12: Feedback review without automatic product mutation
# --------------------------------------------------------------------------
def test_12_feedback_review_without_automatic_product_mutation():
    """Customer feedback and status changes never automatically mutate product data."""
    cust_resp = client.post("/api/auth/login", json={
        "email": "customer@truthcart.ai",
        "password": "Customer123!"
    })
    cust_headers = {"Authorization": f"Bearer {cust_resp.json()['access_token']}"}

    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    owner_headers = {"Authorization": f"Bearer {owner_resp.json()['access_token']}"}

    # Check original product price
    orig_prod = client.get("/api/products/TC-EL-201").json()
    orig_price = orig_prod["price"]

    # Customer submits feedback claiming price should be 100
    fb_resp = client.post("/api/feedback", headers=cust_headers, json={
        "feedback_type": "incorrect_product_info",
        "product_id": "TC-EL-201",
        "message": "This laptop should be 100 rupees!",
        "rating": 1
    })
    fb_id = fb_resp.json()["id"]

    # Product must remain unchanged!
    prod_check1 = client.get("/api/products/TC-EL-201").json()
    assert prod_check1["price"] == orig_price

    # Owner moves feedback to UNDER_REVIEW
    st_resp = client.put(f"/api/feedback/{fb_id}/status", headers=owner_headers, json={
        "status": "UNDER_REVIEW",
        "resolution_note": "Investigating claim against supplier invoice."
    })
    assert st_resp.status_code == 200

    # Product must STILL remain unchanged!
    prod_check2 = client.get("/api/products/TC-EL-201").json()
    assert prod_check2["price"] == orig_price

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 13: Verified product correction and index refresh
# --------------------------------------------------------------------------
def test_13_verified_product_correction_and_index_refresh():
    """Verified correction updates product in DB, audits change, and refreshes vector index."""
    owner_resp = client.post("/api/auth/owner-login", json={
        "email": "owner@truthcart.ai",
        "password": "AdminTruthCart2026!"
    })
    owner_headers = {"Authorization": f"Bearer {owner_resp.json()['access_token']}"}

    cust_resp = client.post("/api/auth/login", json={
        "email": "customer@truthcart.ai",
        "password": "Customer123!"
    })
    cust_headers = {"Authorization": f"Bearer {cust_resp.json()['access_token']}"}

    # Submit feedback on TC-EL-202
    fb_resp = client.post("/api/feedback", headers=cust_headers, json={
        "feedback_type": "incorrect_product_info",
        "product_id": "TC-EL-202",
        "message": "Stock status should be verified.",
        "rating": 5
    })
    fb_id = fb_resp.json()["id"]

    # Owner applies verified correction
    corr_resp = client.post("/api/feedback/verified-correction", headers=owner_headers, json={
        "feedback_id": fb_id,
        "product_id": "TC-EL-202",
        "updates": {"stock_status": "In Stock"},
        "resolution_note": "Physical warehouse stock count confirmed units available."
    })
    assert corr_resp.status_code == 200
    assert corr_resp.json()["status"] == "RESOLVED"

    # Verify audit log was recorded
    audit_resp = client.get("/api/audit-logs", headers=owner_headers)
    assert audit_resp.status_code == 200
    actions = [a["action"] for a in audit_resp.json()]
    assert "PRODUCT_UPDATED" in actions

    # Verify product in active catalogue is updated
    updated = client.get("/api/products/TC-EL-202").json()
    assert updated["stock_status"] == "In Stock"

# --------------------------------------------------------------------------
# MANDATORY REGRESSION TEST 14: Citation validation and unsupported-claim refusal
# --------------------------------------------------------------------------
def test_14_citation_validation_and_unsupported_claim_refusal():
    """Citation validator strictly validates claimed sources; unsupported claims are refused."""
    # 1. Unsupported product attribute query
    resp1 = client.post("/api/chat", json={"message": "What is the waterproof rating for TC-AP-101?"})
    assert resp1.status_code == 200
    assert resp1.json()["decision"] == "REFUSE"

    # 2. Out-of-catalogue product query
    resp2 = client.post("/api/chat", json={"message": "What is the discount on Sony PlayStation 5 Pro?"})
    assert resp2.status_code == 200
    assert resp2.json()["decision"] == "REFUSE"

    # 3. Direct CitationValidator unit check
    # Valid product citation
    is_valid, valid_cits, invalid_cits = citation_validator.validate_citations(
        "Product details: [PRODUCT:TC-EL-201] is in stock.",
        verified_product_ids={"TC-EL-201"},
        verified_policy_ids=set()
    )
    assert is_valid is True
    assert "[PRODUCT:TC-EL-201]" in valid_cits

    # Fabricated / ungrounded product citation
    is_valid_fake, valid_cits_fake, invalid_cits_fake = citation_validator.validate_citations(
        "Fabricated detail: [PRODUCT:TC-FAKE-999] was claimed.",
        verified_product_ids={"TC-EL-201"},
        verified_policy_ids=set()
    )
    assert is_valid_fake is False
    assert "[PRODUCT:TC-FAKE-999]" in invalid_cits_fake
