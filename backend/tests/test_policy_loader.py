import pytest
from app.ingestion.policy_loader import policy_loader

def test_policy_sections_loaded():
    assert policy_loader.is_ready is True
    assert len(policy_loader.sections) >= 3

    returns_sec = policy_loader.get_section_by_topic("RETURNS")
    assert returns_sec is not None
    assert returns_sec.section_id == "POLICY:RETURNS"
    assert "14" in returns_sec.content

    shipping_sec = policy_loader.get_section_by_topic("SHIPPING")
    assert shipping_sec is not None
    assert "Standard Shipping" in shipping_sec.content

    warranty_sec = policy_loader.get_section_by_topic("WARRANTY")
    assert warranty_sec is not None
    assert "1-year" in warranty_sec.content or "1-Year" in warranty_sec.content

def test_traceable_section_by_id():
    sec = policy_loader.get_section_by_id("POLICY:RETURNS")
    assert sec is not None
    assert sec.topic == "RETURNS"
