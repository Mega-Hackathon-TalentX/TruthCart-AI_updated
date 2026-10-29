import pytest
from app.llm.query_understanding import query_understanding
from app.retrieval.hybrid_retriever import hybrid_retriever
from app.evidence_engine.decision_engine import decision_engine
from app.llm.response_generator import response_generator

def test_guardrail_unsupported_product_claim_rejected():
    # User asks for non-existent product
    query = "What is the discount on Sony PlayStation 5 Pro?"
    parsed = query_understanding.parse(query)
    cands, pol = hybrid_retriever.retrieve(query, parsed)
    decision = decision_engine.evaluate(query, parsed, cands, pol)

    assert decision.decision == "REFUSE"
    # Response generator cannot override REFUSE
    text, prods, cits, _, _ = response_generator.generate_response(decision, [])
    assert "unable to verify" in text.lower() or "not found" in text.lower()
    assert len(prods) == 0

def test_guardrail_unsupported_policy_claim_rejected():
    # User asks for international shipping to Canada
    query = "Do you deliver to Canada?"
    parsed = query_understanding.parse(query)
    cands, pol = hybrid_retriever.retrieve(query, parsed)
    decision = decision_engine.evaluate(query, parsed, cands, pol)

    assert decision.decision == "REFUSE"
    assert "international" in str(decision.refusal_reason).lower() or "not support" in str(decision.refusal_reason).lower()

def test_guardrail_conflicting_constraints_clarified():
    # User specifies min price higher than max price
    query = "Show me laptops above 80000 and under 50000"
    parsed = query_understanding.parse(query)
    cands, pol = hybrid_retriever.retrieve(query, parsed)
    decision = decision_engine.evaluate(query, parsed, cands, pol)

    assert decision.decision == "CLARIFY"
    assert "contradictory" in decision.clarification_question.lower() or "conflicting" in decision.clarification_question.lower()
