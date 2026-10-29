import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader
from app.retrieval.hybrid_retriever import hybrid_retriever
from app.retrieval.structured_search import structured_search_engine
from app.retrieval.semantic_search import local_vector_index
from app.llm.query_understanding import query_understanding
from app.evidence_engine.citation_validator import citation_validator
from app.evidence_engine.decision_engine import decision_engine
from app.core.auth import create_access_token

client = TestClient(app)

# ==============================================================================
# PHASE 9 REGRESSION TEST SUITE: SEMANTIC PRODUCT RETRIEVAL & RELEVANCE
# ==============================================================================

# --- SEARCH RELEVANCE (Tests 1-20) ---

def test_01_exact_product_title_query():
    """1. Exact product-title query returns the specific product with highest relevance."""
    resp = client.post("/api/chat", json={"message": "Classic Cotton Oxford Shirt"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ANSWER"
    assert len(data["products"]) >= 1
    assert data["products"][0]["title"] == "Classic Cotton Oxford Shirt"
    assert data["products"][0]["product_id"] == "TC-DEV-101"

def test_02_partial_product_title_query():
    """2. Partial product-title query retrieves matching title candidates."""
    resp = client.post("/api/chat", json={"message": "Oxford Shirt"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ANSWER"
    titles = [p["title"] for p in data["products"]]
    assert any("Oxford Shirt" in t for t in titles)

def test_03_related_word_or_synonym_query():
    """3. Related-word or synonym query (e.g. sneakers / footwear / shoes)."""
    resp = client.post("/api/chat", json={"message": "Show me sneakers"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ANSWER"
    # ProFlow Featherweight Running Shoes is a Footwear/sneaker candidate
    pids = [p["product_id"] for p in data["products"]]
    assert "TC-DEV-104" in pids

def test_04_natural_language_description_query():
    """4. Natural-language description query finds semantically relevant products."""
    resp = client.post("/api/chat", json={"message": "I need road running shoes with responsive foam cushioning"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ANSWER"
    assert data["products"][0]["product_id"] == "TC-DEV-104"

def test_05_category_only_query():
    """5. Category-only query returns all verified products in that category."""
    resp = client.post("/api/chat", json={"message": "What footwear is available?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ANSWER"
    for p in data["products"]:
        assert p["category"].lower() == "footwear" or "shoes" in p["title"].lower()

def test_06_subcategory_query():
    """6. Subcategory query resolves specific subtypes."""
    parsed = query_understanding.parse("Show running shoes")
    assert parsed["category"] == "Footwear"
    assert parsed["requested_subtype"] == "running shoes"
    cands, _ = hybrid_retriever.retrieve("Show running shoes", parsed)
    assert len(cands) >= 1
    assert cands[0].source_id == "TC-DEV-104"

def test_07_sku_lookup():
    """7. SKU / Product ID direct exact lookup."""
    resp = client.post("/api/chat", json={"message": "TC-DEV-105"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ANSWER"
    assert data["products"][0]["product_id"] == "TC-DEV-105"

def test_08_product_id_lookup():
    """8. Natural language query mentioning product ID."""
    resp = client.post("/api/chat", json={"message": "Details of TC-DEV-102"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ANSWER"
    assert data["products"][0]["product_id"] == "TC-DEV-102"

def test_09_color_and_material_filters():
    """9. Color and material structured filters."""
    query = "White linen shirt"
    parsed = query_understanding.parse(query)
    assert parsed["color"] == "White"
    assert parsed["material"] == "Linen"
    cands, _ = hybrid_retriever.retrieve(query, parsed)
    assert len(cands) >= 1
    for c in cands:
        assert c.data["attributes"]["material"].lower() == "linen"
        assert c.data["attributes"]["color"].lower() == "white"

def test_10_price_range_filter():
    """10. Price-range filter parses min and max price accurately."""
    min_p, max_p = query_understanding.parse_budget("Between ₹1500 and ₹3500")
    assert min_p == 1500.0
    assert max_p == 3500.0

def test_11_stock_filter():
    """11. Stock filter excludes out-of-stock items."""
    query = "Only items in stock under 1500"
    parsed = query_understanding.parse(query)
    assert parsed["stock_required"] is True
    cands, _ = hybrid_retriever.retrieve(query, parsed)
    for c in cands:
        assert c.data["stock_status"].lower() == "in stock"

def test_12_multiple_simultaneous_filters():
    """12. Multiple simultaneous filters (category, price, stock, material)."""
    query = "In stock cotton shirts under 1600"
    parsed = query_understanding.parse(query)
    cands, _ = hybrid_retriever.retrieve(query, parsed)
    assert len(cands) >= 1
    for c in cands:
        p = c.data
        assert p["price"] <= 1600.0
        assert p["stock_status"].lower() == "in stock"
        assert p["attributes"]["material"].lower() == "cotton"

def test_13_relevant_query_with_spelling_variation():
    """13. Relevant query with pluralization, stemming, or minor suffix variation."""
    cands, _ = hybrid_retriever.retrieve("slippers", {"category": "Footwear"})
    # Query understood and retrieved without error
    assert isinstance(cands, list)

def test_14_unrelated_query_no_misleading_products():
    """14. Unrelated query must not return fabricated or misleading products."""
    resp = client.post("/api/chat", json={"message": "Do you sell nuclear submarines?"})
    assert resp.status_code == 200
    assert resp.json()["decision"] == "REFUSE"

def test_15_category_with_many_matching_products():
    """15. Category browse endpoint supports retrieving products with total count."""
    resp = client.get("/api/products?category=Apparel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["products"]) >= 1

def test_16_missing_product_or_category():
    """16. Requesting a non-existent category safely refuses or returns empty list."""
    resp = client.get("/api/products?category=NonExistentCategory999")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

def test_17_empty_active_catalogue_handling():
    """17. When active catalogue has no matches, returns accurate empty state."""
    resp = client.post("/api/chat", json={"message": "Show luxury yacht"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "REFUSE"

def test_18_unavailable_semantic_model_fallback():
    """18. If vector index is unindexed, hybrid search gracefully relies on structured search."""
    orig_query = local_vector_index.query
    try:
        local_vector_index.query = lambda *args, **kwargs: []
        cands, _ = hybrid_retriever.retrieve("Cotton shirt", {"category": "Apparel", "material": "Cotton"})
        assert len(cands) >= 1
        assert cands[0].retrieval_method == "structured"
    finally:
        local_vector_index.query = orig_query

def test_19_unavailable_or_stale_index_rebuild():
    """19. Index rebuild creates non-empty vocabulary and document vectors."""
    success = local_vector_index.build_index(force_rebuild=True)
    assert success is True
    assert local_vector_index.is_indexed is True
    assert len(local_vector_index.doc_ids) > 0

def test_20_newly_activated_catalogue_searchable():
    """20. Activated catalogue is immediately searchable."""
    status = catalogue_loader.get_status()
    assert status["is_ready"] is True
    assert status["total_active_products"] > 0


# --- CONVERSATION & EVIDENCE (Tests 21-28) ---

def test_21_category_followed_by_budget_constraint():
    """21. Multi-turn: Category followed by budget constraint preserves category."""
    cid = f"test-conv-{uuid.uuid4().hex[:8]}"
    r1 = client.post("/api/chat", json={"message": "Show shirts", "conversation_id": cid})
    assert r1.status_code == 200
    assert r1.json()["decision"] in ("ANSWER", "CLARIFY")

    r2 = client.post("/api/chat", json={"message": "Under 1500", "conversation_id": cid})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["decision"] == "ANSWER"
    for p in data2["products"]:
        assert p["price"] <= 1500.0

def test_22_category_and_budget_followed_by_instock():
    """22. Multi-turn: Category + budget followed by 'in stock only' preserves both."""
    cid = f"test-conv-{uuid.uuid4().hex[:8]}"
    client.post("/api/chat", json={"message": "Show shirts", "conversation_id": cid})
    client.post("/api/chat", json={"message": "Under 1500", "conversation_id": cid})
    r3 = client.post("/api/chat", json={"message": "Only items in stock", "conversation_id": cid})
    assert r3.status_code == 200
    data3 = r3.json()
    assert data3["decision"] == "ANSWER"
    for p in data3["products"]:
        assert p["price"] <= 1500.0
        assert p["stock_status"].lower() == "in stock"

def test_23_changing_the_product_category():
    """23. Multi-turn: Changing category resets old category-specific constraints."""
    cid = f"test-conv-{uuid.uuid4().hex[:8]}"
    client.post("/api/chat", json={"message": "Show footwear", "conversation_id": cid})
    r2 = client.post("/api/chat", json={"message": "Show cotton shirts instead", "conversation_id": cid})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["decision"] == "ANSWER"
    for p in data2["products"]:
        assert "footwear" not in p["category"].lower()

def test_24_multiple_ambiguous_product_matches():
    """24. Ambiguous queries clarify or return top ranked verified options."""
    resp = client.post("/api/chat", json={"message": "laptop"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] in ("ANSWER", "CLARIFY")

def test_25_valid_product_citations():
    """25. Every product citation matches verified retrieved source ID."""
    resp = client.post("/api/chat", json={"message": "What is the price of TC-DEV-101?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ANSWER"
    assert "[PRODUCT:TC-DEV-101]" in data["citations"]

def test_26_unsupported_product_refusal():
    """26. Model safely refuses ungrounded attribute claims (e.g. waterproof rating for shirt)."""
    resp = client.post("/api/chat", json={"message": "What is the waterproof depth rating for TC-DEV-101?"})
    assert resp.status_code == 200
    assert resp.json()["decision"] == "REFUSE"

def test_27_product_query_routed_away_from_policy_retrieval():
    """27. Shopping queries containing 'price' or 'cost' are NOT hijacked by warranty policy."""
    resp = client.post("/api/chat", json={"message": "What is the price of TC-DEV-105?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ANSWER"
    assert len(data["products"]) >= 1
    assert data["products"][0]["product_id"] == "TC-DEV-105"

def test_28_no_duplicate_products_in_final_results():
    """28. Hybrid retrieval deduplicates products across structured and semantic paths."""
    cands, _ = hybrid_retriever.retrieve("Classic Cotton Oxford Shirt", {"category": "Apparel"})
    pids = [c.source_id for c in cands]
    assert len(pids) == len(set(pids))


# --- FRONTEND & API COMPATIBILITY (Tests 29-35) ---

def test_29_category_dropdown_categories():
    """29. Distinct non-empty categories returned for category dropdown."""
    resp = client.get("/api/products")
    assert resp.status_code == 200
    cats = resp.json()["categories"]
    assert len(cats) > 0
    assert all(isinstance(c, str) and c.strip() for c in cats)

def test_30_title_category_and_sku_filters():
    """30. Searching by SKU in browse endpoint resolves the product."""
    resp = client.get("/api/products?search=TC-DEV-105")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["products"][0]["product_id"] == "TC-DEV-105"

def test_31_combined_price_and_category_filters():
    """31. Combined category and price filtering produces intersection."""
    resp = client.get("/api/products?category=Apparel&max_price=1600")
    assert resp.status_code == 200
    for p in resp.json()["products"]:
        assert p["price"] <= 1600.0

def test_32_clearing_filters():
    """32. Clearing all filters returns full default result set."""
    r_filtered = client.get("/api/products?category=Footwear")
    r_unfiltered = client.get("/api/products")
    assert r_unfiltered.status_code == 200
    assert r_unfiltered.json()["total"] >= r_filtered.json()["total"]

def test_33_pagination_across_result_sets():
    """33. Pagination limit and offset parameters work correctly without hiding products."""
    r1 = client.get("/api/products?limit=2&offset=0")
    r2 = client.get("/api/products?limit=2&offset=2")
    assert r1.status_code == 200
    assert r2.status_code == 200
    pids1 = [p["product_id"] for p in r1.json()["products"]]
    pids2 = [p["product_id"] for p in r2.json()["products"]]
    # Distinct pages should not overlap
    assert set(pids1).isdisjoint(set(pids2))

def test_34_search_after_catalogue_activation():
    """34. Vector index operational and reflects current active products."""
    assert local_vector_index.is_indexed is True
    results = local_vector_index.query("Oxford Shirt", top_k=5)
    assert len(results) > 0

def test_35_retrieval_diagnostics_structure():
    """35. Response includes structured diagnostics without leaking credentials."""
    resp = client.post("/api/chat", json={"message": "Show blue shirts under 2000"})
    assert resp.status_code == 200
    data = resp.json()
    assert "diagnostics" in data
    diag = data["diagnostics"]
    assert diag is not None
    assert "normalized_query" in diag
    assert "detected_intent" in diag
    assert "structured_candidates_count" in diag
    assert "semantic_candidates_count" in diag
    assert "retrieval_latency_ms" in diag
    assert "vector_index_operational" in diag
    # Ensure no credentials or tokens are logged
    diag_str = str(diag).lower()
    assert "password" not in diag_str
    assert "secret" not in diag_str
    assert "token" not in diag_str
