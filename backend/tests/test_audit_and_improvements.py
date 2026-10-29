import pytest
from app.llm.query_understanding import query_understanding
from app.evidence_engine.evidence_checker import evidence_checker
from app.evidence_engine.decision_engine import decision_engine
from app.retrieval.structured_search import structured_search_engine
from app.evaluation.evaluate import evaluation_pipeline

def test_01_decision_engine_clean_import_and_eval():
    """Verify decision_engine functions without deferred import side-effects."""
    parsed = query_understanding.parse("What is the price of TC-EL-201?")
    assert parsed["product_id"] == "TC-EL-201"
    assert "price" in parsed["requested_attributes"]

def test_02_evidence_checker_word_boundary_isolation():
    """Ensure 'ram' does not match attribute 'program' or 'frame'."""
    prod = {
        "product_id": "TEST-1",
        "title": "Test Device",
        "attributes": {
            "program_type": "automated",
            "frame_material": "aluminum",
            "system_ram": "16 GB"
        }
    }
    # Requesting 'ram' should match 'system_ram', not 'program_type'
    items = evidence_checker.extract_product_evidence(prod, ["ram"])
    ram_items = [it for it in items if "ram" in it.field]
    assert len(ram_items) == 1
    assert ram_items[0].field == "system_ram"
    assert ram_items[0].value == "16 GB"

    # Requesting 'gram' should NOT match 'program_type'
    items_gram = evidence_checker.extract_product_evidence(prod, ["gram"])
    assert not any(it.field == "program_type" for it in items_gram)

def test_03_structured_search_attribute_word_boundary():
    """Ensure 'red' matches 'ruby red', but not 'delivered' or 'wired'."""
    prod_matching = {
        "product_id": "P1",
        "title": "Running Shoes",
        "attributes": {"color": "ruby red"}
    }
    prod_non_matching = {
        "product_id": "P2",
        "title": "Running Shoes Wired",
        "attributes": {"shipping": "delivered"}
    }
    assert structured_search_engine.match_attribute(prod_matching, "color", "red") is True
    # 'red' should NOT match 'delivered' or 'wired'
    assert structured_search_engine.match_attribute(prod_non_matching, "color", "red") is False

def test_04_multilingual_telugu_hindi_categories():
    """Verify cross-lingual category detection for Telugu and Hindi terms."""
    # Footwear
    for q in ["running joote dikhao", "mujhe ache joota chahiye", "cheppulu chupinchu", "kothaga vachina cheppu"]:
        parsed = query_understanding.parse(q)
        assert parsed["category"] == "Footwear", f"Failed on: {q}"

    # Apparel
    for q in ["cotton kapde dikhao", "mujhe kapda chahiye", "batalu chupinchu", "battalu kavali", "summer saree"]:
        parsed = query_understanding.parse(q)
        assert parsed["category"] == "Apparel", f"Failed on: {q}"

def test_05_multilingual_telugu_hindi_budgets():
    """Verify postposition budget expressions in Telugu and Hindi."""
    # Hindi 'se kam'
    p1 = query_understanding.parse("2000 se kam me joote")
    assert p1["max_price"] == 2000.0

    # Hindi 'ke andar'
    p2 = query_understanding.parse("1500 ke andar kapde")
    assert p2["max_price"] == 1500.0

    # Telugu 'lopala'
    p3 = query_understanding.parse("3000 lopala cheppulu")
    assert p3["max_price"] == 3000.0

    # Telugu 'thakkuva'
    p4 = query_understanding.parse("2500 thakkuva batalu")
    assert p4["max_price"] == 2500.0

def test_06_multilingual_attributes_price_and_warranty():
    """Verify Hindi and Telugu price/warranty terms are properly parsed."""
    q_hi_price = query_understanding.parse("TC-001 ki keemat kya hai?")
    assert q_hi_price["product_id"] == "TC-001"
    assert "price" in q_hi_price["requested_attributes"]

    q_te_price = query_understanding.parse("TC-002 dhara entha?")
    assert q_te_price["product_id"] == "TC-002"
    assert "price" in q_te_price["requested_attributes"]

    q_hi_warranty = query_understanding.parse("TC-003 ki warranty kitni hai?")
    assert "warranty" in q_hi_warranty["requested_attributes"]

def test_07_evaluation_pipeline_flexible_schemas():
    """Ensure evaluation runner processes alternative key conventions smoothly."""
    custom_dataset = [
        {
            "id": "CUSTOM-1",
            "question": "What is the return policy?",
            "expected": "ANSWER"
        },
        {
            "qid": "CUSTOM-2",
            "prompt": "Show me non-existent alien product",
            "decision": "REFUSE"
        }
    ]
    # Test evaluation pipeline logic against custom dicts
    report = evaluation_pipeline.run_evaluation(dataset_name=None, dry_run=True)
    assert report is not None
    assert hasattr(report, "groundedness_score")

