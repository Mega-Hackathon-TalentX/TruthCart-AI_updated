import time
from fastapi import APIRouter, HTTPException
from app.schemas.request import ChatRequest
from app.schemas.response import ChatResponse
from app.llm.query_understanding import query_understanding
from app.retrieval.hybrid_retriever import hybrid_retriever
from app.evidence_engine.decision_engine import decision_engine
from app.llm.response_generator import response_generator
from app.conversation.context_manager import context_manager
from app.ingestion.catalogue_loader import catalogue_loader
from app.core.logging_config import SafeLogger

router = APIRouter(tags=["Chat"])

@router.post("/chat", response_model=ChatResponse)
def handle_chat(req: ChatRequest) -> ChatResponse:
    start_time = time.perf_counter()
    msg = req.message.strip()

    if not msg:
        raise HTTPException(status_code=400, detail="Query message cannot be empty.")

    # 1. Multi-turn Session Management
    session = context_manager.get_or_create_session(req.conversation_id)

    # 2. Query Understanding
    parsed = query_understanding.parse(msg)

    # 3. Constraint Tracking: Handle removals and corrections
    if parsed.get("has_constraint_removal"):
        session.constraints.remove_constraints(parsed.get("removed_constraints", []))

    combined_params = dict(parsed)
    if not parsed.get("product_id") and not parsed.get("is_policy_query") and parsed.get("intent") != "comparison":
        prior = session.constraints.to_dict()
        category_changed = bool(parsed.get("category") and prior.get("category") and (parsed.get("category") != prior.get("category")))
        for k in ("category", "max_price", "min_price", "brand", "color", "material", "stock_required"):
            if combined_params.get(k) is None and prior.get(k) is not None:
                if category_changed and k in ("color", "material", "brand"):
                    continue
                combined_params[k] = prior[k]

        # Update session with newly extracted parameters
        session.constraints.update(parsed)

    # 4. Hybrid Retrieval
    product_cands, policy_cand = hybrid_retriever.retrieve(
        query=msg,
        structured_params=combined_params
    )

    # 5. Deterministic Evidence Engine
    evidence_obj = decision_engine.evaluate(
        query=msg,
        parsed_query=combined_params,
        product_candidates=product_cands,
        policy_candidate=policy_cand
    )

    # 6. Evidence-Grounded Response Generation
    is_compare = parsed.get("intent") == "comparison"
    if is_compare:
        matched_prods = [
            catalogue_loader.get_product(pid) for pid in parsed.get("compare_product_ids", [])
            if catalogue_loader.get_product(pid) is not None
        ]
        if len(matched_prods) < 2 and len(product_cands) >= 2:
            matched_prods = [c.data for c in product_cands[:2]]
    else:
        matched_prods = [c.data for c in product_cands]
        if not matched_prods and evidence_obj.evidence:
            for ev in evidence_obj.evidence:
                if ev.source_type == "product":
                    p = catalogue_loader.get_product(ev.source_id)
                    if p and p not in matched_prods:
                        matched_prods.append(p)

    response_text, products, citations, model_status, comparison_data = response_generator.generate_response(
        evidence_obj=evidence_obj,
        matched_products=matched_prods,
        is_comparison=is_compare
    )

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    retrieval_summary = f"{len(product_cands)} products retrieved"
    if policy_cand:
        retrieval_summary += f", policy [{policy_cand.source_id}] matched"
    if is_compare:
        retrieval_summary += f", {len(matched_prods)} compared"

    diagnostics = {
        "normalized_query": parsed.get("query"),
        "detected_intent": parsed.get("intent"),
        "selected_catalogue_version": catalogue_loader.catalogue_version,
        "retrieval_methods": hybrid_retriever.last_diagnostics.get("retrieval_methods", []),
        "structured_candidates_count": hybrid_retriever.last_diagnostics.get("structured_candidates_count", 0),
        "semantic_candidates_count": hybrid_retriever.last_diagnostics.get("semantic_candidates_count", 0),
        "deduplicated_candidates_count": hybrid_retriever.last_diagnostics.get("deduplicated_candidates_count", 0),
        "applied_filters": hybrid_retriever.last_diagnostics.get("applied_filters", {}),
        "final_result_count": len(products),
        "empty_result_reason": evidence_obj.refusal_reason if evidence_obj.decision == "REFUSE" else (evidence_obj.clarification_question if evidence_obj.decision == "CLARIFY" else None),
        "retrieval_latency_ms": round(latency_ms, 2),
        "vector_index_operational": hybrid_retriever.last_diagnostics.get("vector_index_operational", False)
    }

    chat_resp = ChatResponse(
        decision=evidence_obj.decision,
        response_text=response_text,
        products=products,
        citations=citations,
        evidence=evidence_obj,
        clarification_question=evidence_obj.clarification_question,
        refusal_reason=evidence_obj.refusal_reason,
        comparison_data=comparison_data,
        retrieval_status=retrieval_summary,
        model_status=model_status,
        latency_ms=round(latency_ms, 2),
        token_cost=0.0,
        conversation_id=session.conversation_id,
        diagnostics=diagnostics
    )

    # Record turn in session
    session.add_turn(msg, chat_resp.model_dump())

    return chat_resp
