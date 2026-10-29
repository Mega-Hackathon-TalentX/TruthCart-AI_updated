import pytest
from app.evidence_engine.citation_validator import citation_validator
from app.evidence_engine.citation_mapper import citation_mapper

def test_valid_product_citation():
    text = "The price is ₹1,499.00 [PRODUCT:TC-DEV-101]."
    is_valid, valid_cits, invalid_cits = citation_validator.validate_citations(
        text=text,
        verified_product_ids={"TC-DEV-101"},
        verified_policy_ids=set()
    )
    assert is_valid is True
    assert "[PRODUCT:TC-DEV-101]" in valid_cits
    assert len(invalid_cits) == 0

def test_invalid_hallucinated_product_citation():
    text = "The price of the phone is ₹89,999 [PRODUCT:NON-EXISTENT-999]."
    is_valid, valid_cits, invalid_cits = citation_validator.validate_citations(
        text=text,
        verified_product_ids=set(),
        verified_policy_ids=set()
    )
    assert is_valid is False
    assert "[PRODUCT:NON-EXISTENT-999]" in invalid_cits

def test_citation_sanitization():
    text = "Grounded claim [PRODUCT:TC-DEV-101] and fake claim [PRODUCT:FAKE-ID]."
    sanitized = citation_validator.sanitize_text(
        text=text,
        verified_product_ids={"TC-DEV-101"},
        verified_policy_ids=set()
    )
    assert "[PRODUCT:TC-DEV-101]" in sanitized
    assert "[PRODUCT:FAKE-ID]" not in sanitized

def test_valid_policy_citation():
    text = "Returns are accepted within 14 days [POLICY:RETURNS]."
    is_valid, valid_cits, invalid_cits = citation_validator.validate_citations(
        text=text,
        verified_product_ids=set(),
        verified_policy_ids={"POLICY:RETURNS"}
    )
    assert is_valid is True
    assert "[POLICY:RETURNS]" in valid_cits
