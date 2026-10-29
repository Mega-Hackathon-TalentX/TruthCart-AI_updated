import pytest
from app.conversation.context_manager import context_manager
from app.llm.query_understanding import query_understanding
from app.retrieval.hybrid_retriever import hybrid_retriever

def test_multi_turn_constraint_retention():
    session = context_manager.get_or_create_session("test-session-123")
    session.constraints.clear()

    # Turn 1: "Show me shirts under 2000"
    turn1_query = "Show me shirts under 2000"
    p1 = query_understanding.parse(turn1_query)
    session.constraints.update(p1)

    assert session.constraints.category == "Apparel"
    assert session.constraints.max_price == 2000.0

    # Turn 2: "I prefer cotton"
    turn2_query = "I prefer cotton"
    p2 = query_understanding.parse(turn2_query)
    session.constraints.update(p2)

    # Both constraints retained!
    assert session.constraints.category == "Apparel"
    assert session.constraints.max_price == 2000.0
    assert session.constraints.material == "Cotton"

    # Search with combined constraints returns TC-DEV-101 (cotton shirt @ 1499)
    combined = session.constraints.to_dict()
    matches, _ = hybrid_retriever.retrieve(turn2_query, combined)
    assert len(matches) >= 1
    assert matches[0].source_id == "TC-DEV-101"
