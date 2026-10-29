import pytest
from app.retrieval.structured_search import structured_search_engine

def test_exact_product_id_lookup():
    results = structured_search_engine.search(product_id="TC-DEV-101")
    assert len(results) == 1
    assert results[0]["title"] == "Classic Cotton Oxford Shirt"
    assert results[0]["price"] == 1499.0

def test_numeric_price_filtering():
    # Shirts under 1500
    results = structured_search_engine.search(category="Apparel", max_price=1500.0)
    assert len(results) >= 1
    for r in results:
        assert r["price"] <= 1500.0

def test_stock_status_filter():
    # Only in stock items
    in_stock_results = structured_search_engine.search(category="Apparel", stock_required=True)
    for r in in_stock_results:
        assert r["stock_status"].lower() in ("in stock", "available")
    
    # TC-DEV-103 is Out of Stock, so it should not be in in_stock_results
    ids = [r["product_id"] for r in in_stock_results]
    assert "TC-DEV-103" not in ids

def test_attribute_matching():
    # Material matching: Linen
    results = structured_search_engine.search(category="Apparel", material="Linen")
    assert len(results) == 1
    assert results[0]["product_id"] == "TC-DEV-102"
