import pytest
from app.llm.query_understanding import query_understanding

def test_numeric_budget_extraction():
    parsed = query_understanding.parse("Blue shirt under 1000")
    assert parsed["max_price"] == 1000.0
    assert parsed["color"] == "Blue"
    assert parsed["category"] == "Apparel"

def test_k_multiplier_extraction():
    parsed = query_understanding.parse("Cotton shirt kavali under 2k")
    assert parsed["max_price"] == 2000.0
    assert parsed["material"] == "Cotton"
    assert parsed["category"] == "Apparel"

def test_product_id_extraction():
    parsed = query_understanding.parse("Price of product TC-DEV-101?")
    assert parsed["product_id"] == "TC-DEV-101"
    assert "price" in parsed["requested_attributes"]

def test_policy_query_understanding():
    parsed = query_understanding.parse("Can I return this product?")
    assert parsed["is_policy_query"] is True
    assert parsed["policy_topic"] == "RETURNS"
