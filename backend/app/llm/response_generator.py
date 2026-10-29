from typing import Dict, List, Optional, Any, Tuple
from app.schemas.response import EvidenceObject, ProductResult, ComparisonData
from app.evidence_engine.citation_mapper import citation_mapper
from app.evidence_engine.citation_validator import citation_validator
from app.llm.model_adapter import local_model_adapter
from app.llm.model_loader import model_loader
from app.ingestion.catalogue_loader import catalogue_loader

class ResponseGenerator:
    """
    Evidence-grounded response generator.
    Strict Invariant: Never overrides the Evidence Engine decision and strictly enforces citations.
    """

    def generate_response(
        self,
        evidence_obj: EvidenceObject,
        matched_products: List[Dict[str, Any]],
        is_comparison: bool = False
    ) -> Tuple[str, List[ProductResult], List[str], str, Optional[ComparisonData]]:
        """
        Generates text, product cards, citations, model status, and optional comparison data
        based strictly on the Evidence Object.
        """
        decision = evidence_obj.decision
        product_results: List[ProductResult] = []
        citations: List[str] = []
        comparison_data: Optional[ComparisonData] = None
        model_status = "Local Instruction Model" if model_loader.instruction_model_loaded else "Deterministic Grounded Generator (Active)"

        # 1. CLARIFY Decision
        if decision == "CLARIFY":
            text = evidence_obj.clarification_question or "Could you please specify more details regarding the product you are looking for?"
            return text, [], [], model_status, None

        # 2. REFUSE Decision
        if decision == "REFUSE":
            reason = evidence_obj.refusal_reason or "I could not find sufficient verified evidence in the catalogue to confirm this claim."
            text = f"I am unable to verify that request. {reason}"
            refusal_citations = []
            verified_pids = set()
            for ev in evidence_obj.evidence:
                if ev.source_type == "product":
                    verified_pids.add(ev.source_id)
                    tag = citation_mapper.format_product_citation(ev.source_id)
                    if tag in text and tag not in refusal_citations:
                        refusal_citations.append(tag)
            is_valid, valid_cits, _ = citation_validator.validate_citations(text, verified_pids, set())
            if not is_valid:
                text = citation_validator.sanitize_text(text, verified_pids, set())
            return text, [], refusal_citations, model_status, None


        # 3. ANSWER Decision
        verified_pids = set()
        verified_policy_ids = set()

        for ev in evidence_obj.evidence:
            if ev.source_type == "product":
                verified_pids.add(ev.source_id)
            elif ev.source_type == "policy":
                verified_policy_ids.add(ev.source_id)

        # Policy Answer
        if verified_policy_ids:
            policy_ev = next((ev for ev in evidence_obj.evidence if ev.source_type == "policy"), None)
            if policy_ev:
                sec_id = policy_ev.source_id
                citation_tag = citation_mapper.format_policy_citation(sec_id)
                citations.append(citation_tag)
                text = f"According to the official store policy {citation_tag}:\n\n{policy_ev.value}"
                return text, [], citations, model_status, None

        # Customer Review Complaints Summary Answer
        review_evs = [ev for ev in evidence_obj.evidence if ev.source_type == "review"]
        if review_evs:
            lines = ["Summary of verified customer complaints from feedback records:"]
            for rev in review_evs:
                cit = f"[REVIEW:{rev.source_id}]"
                citations.append(cit)
                lines.append(f"• {rev.value} {cit}")
            text = "\n".join(lines)
            return text, [], citations, model_status, None

        # Seller / Competitor Price Comparison Answer
        comp_evs = [ev for ev in evidence_obj.evidence if ev.source_type in ("competitor", "listing")]
        if comp_evs:
            lines = ["Price comparison across verified sellers:"]
            for ev in evidence_obj.evidence:
                cit = citation_mapper.format_citation(ev.source_type, ev.source_id)
                citations.append(cit)
                lines.append(f"• {ev.value} {cit}")
            if evidence_obj.unsupported_fields:
                lines.append("")
                for warn in evidence_obj.unsupported_fields:
                    lines.append(f"⚠️ {warn}")
            text = "\n".join(lines)
            return text, [], citations, model_status, None

        # Assemble Product Results
        for p in matched_products:
            pid = str(p.get("product_id") or p.get("record_id") or "UNKNOWN")
            if pid in verified_pids or not verified_pids:
                citation_tag = citation_mapper.format_product_citation(pid)
                citations.append(citation_tag)

                raw_p = p.get("price")
                try:
                    price_val = float(raw_p) if raw_p is not None else 0.0
                except (ValueError, TypeError):
                    price_val = 0.0

                prod_result = ProductResult(
                    product_id=pid,
                    title=str(p.get("title", f"Item {pid}")),
                    description=str(p.get("description") or p.get("content_text") or p.get("review_text") or ""),
                    category=str(p.get("category", "General")),
                    price=price_val,
                    stock_status=str(p.get("stock_status", "Available")),
                    rating=float(p["rating"]) if p.get("rating") is not None and str(p.get("rating")).replace('.','',1).isdigit() else None,
                    attributes=p.get("attributes", {}) if isinstance(p.get("attributes"), dict) else {},
                    citation=citation_tag
                )
                product_results.append(prod_result)

        # Comparison Formatting
        if is_comparison and len(product_results) >= 2:
            p1 = product_results[0]
            p2 = product_results[1]
            
            # Find all attribute keys across both products
            all_attr_keys = sorted(list(set(list(p1.attributes.keys()) + list(p2.attributes.keys()))))
            
            p1_price_str = f"₹{p1.price:,.2f}" if p1.price > 0 else "[Price unlisted]"
            p2_price_str = f"₹{p2.price:,.2f}" if p2.price > 0 else "[Price unlisted]"

            dimensions: Dict[str, Dict[str, Any]] = {
                "Price": {p1.product_id: p1_price_str, p2.product_id: p2_price_str},
                "Stock Status": {p1.product_id: p1.stock_status, p2.product_id: p2.stock_status},
                "Category": {p1.product_id: p1.category, p2.product_id: p2.category}
            }

            for k in all_attr_keys:
                val1 = p1.attributes.get(k, "Not specified in catalogue record")
                val2 = p2.attributes.get(k, "Not specified in catalogue record")
                dim_name = k.replace("_", " ").title()
                dimensions[dim_name] = {p1.product_id: val1, p2.product_id: val2}

            comparison_data = ComparisonData(
                products=[p1.product_id, p2.product_id],
                product_titles={p1.product_id: p1.title, p2.product_id: p2.title},
                dimensions=dimensions,
                notes=["Missing attributes indicate unrecorded specifications in the catalogue snapshot, not necessarily absence."]
            )

            # Generate natural language comparison text
            lines = [
                f"Side-by-side comparison between {p1.title} {p1.citation} and {p2.title} {p2.citation}:",
                f"• Price: {p1.product_id} is {p1_price_str} vs {p2.product_id} is {p2_price_str}",
                f"• Availability: {p1.product_id} [{p1.stock_status}] vs {p2.product_id} [{p2.stock_status}]"
            ]
            for k in all_attr_keys[:4]:
                v1 = p1.attributes.get(k, "Unspecified")
                v2 = p2.attributes.get(k, "Unspecified")
                lines.append(f"• {k.title()}: {p1.product_id} ({v1}) vs {p2.product_id} ({v2})")

            text = "\n".join(lines)
        else:
            # Standard Catalogue List Answer
            text_lines = []
            for prod in product_results:
                stock_label = prod.stock_status
                attrs = prod.attributes
                attr_summary = ", ".join([f"{k}: {v}" for k, v in list(attrs.items())[:3]])
                price_str = f"₹{prod.price:,.2f}" if prod.price > 0 else "[Price unlisted]"
                line = (
                    f"• {prod.title} {prod.citation} — {price_str} "
                    f"[{stock_label}]"
                )
                if attr_summary:
                    line += f" ({attr_summary})"
                text_lines.append(line)

            if text_lines:
                if any(str(f).startswith("subtype:") for f in evidence_obj.unsupported_fields):
                    sub_f = next(str(f) for f in evidence_obj.unsupported_fields if str(f).startswith("subtype:"))
                    sub_name = sub_f.split(":", 1)[1]
                    header = f"We do not have {sub_name} in our official catalogue. However, here are verified alternatives available from our catalogue:"
                else:
                    header = f"Here {'is the product' if len(text_lines) == 1 else 'are the products'} matching your request directly from our catalogue:"
                text = header + "\n" + "\n".join(text_lines)
            else:
                text = "I verified the requested items in our catalogue."


        # Server-side validation check
        is_valid, valid_cits, _ = citation_validator.validate_citations(text, verified_pids, verified_policy_ids)
        if not is_valid:
            text = citation_validator.sanitize_text(text, verified_pids, verified_policy_ids)

        return text, product_results, list(set(citations)), model_status, comparison_data

response_generator = ResponseGenerator()
