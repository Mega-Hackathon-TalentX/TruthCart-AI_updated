import pytest
from app.llm.query_understanding import query_understanding
from app.retrieval.hybrid_retriever import hybrid_retriever
from app.evidence_engine.decision_engine import decision_engine

def test_evidence_engine_answer_decision():
    query = "What is the price of TC-DEV-101?"
    parsed = query_understanding.parse(query)
    product_cands, policy_cand = hybrid_retriever.retrieve(query, parsed)
    evidence_obj = decision_engine.evaluate(query, parsed, product_cands, policy_cand)

    assert evidence_obj.decision == "ANSWER"
    assert len(evidence_obj.evidence) > 0
    # Price must be verified in evidence
    price_ev = next((e for e in evidence_obj.evidence if e.field == "price"), None)
    assert price_ev is not None
    assert "1,499" in str(price_ev.value)

def test_evidence_engine_clarify_decision():
    # Ambiguous generic query with multiple matches
    query = "Show me shirts"
    parsed = query_understanding.parse(query)
    product_cands, policy_cand = hybrid_retriever.retrieve(query, parsed)
    evidence_obj = decision_engine.evaluate(query, parsed, product_cands, policy_cand)

    assert evidence_obj.decision == "CLARIFY"
    assert evidence_obj.clarification_question is not None
    assert "?" in evidence_obj.clarification_question

def test_evidence_engine_refuse_out_of_catalogue():
    query = "Do you have iPhone 15 Pro Max?"
    parsed = query_understanding.parse(query)
    product_cands, policy_cand = hybrid_retriever.retrieve(query, parsed)
    evidence_obj = decision_engine.evaluate(query, parsed, product_cands, policy_cand)

    assert evidence_obj.decision == "REFUSE"
    assert evidence_obj.refusal_reason is not None

def test_evidence_engine_refuse_unsupported_attribute():
    query = "What is the battery life of TC-DEV-101 cotton shirt?"
    parsed = query_understanding.parse(query)
    product_cands, policy_cand = hybrid_retriever.retrieve(query, parsed)
    evidence_obj = decision_engine.evaluate(query, parsed, product_cands, policy_cand)

    assert evidence_obj.decision == "REFUSE"
    assert "battery" in str(evidence_obj.unsupported_fields).lower()
