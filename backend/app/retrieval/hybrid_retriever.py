import re
from typing import Dict, List, Optional, Any, Tuple
from app.retrieval.structured_search import structured_search_engine
from app.retrieval.semantic_search import local_vector_index, STOP_WORDS, stem_word
from app.retrieval.policy_search import policy_search_engine, PolicySection
from app.ingestion.catalogue_loader import catalogue_loader
from app.core.logging_config import SafeLogger

class CandidateEvidence:
    """Encapsulates a retrieved candidate record with scoring and provenance metadata."""
    def __init__(
        self,
        source_type: str, # "product" or "policy"
        source_id: str,
        data: Dict[str, Any],
        retrieval_method: str, # "structured", "semantic", "hybrid", "policy"
        score: float = 1.0,
        relevance_score: float = 0.0
    ):
        self.source_type = source_type
        self.source_id = source_id
        self.data = data
        self.retrieval_method = retrieval_method
        self.score = score
        self.relevance_score = relevance_score

class HybridRetriever:
    """
    Combines structured filtering, semantic vector similarity, and policy retrieval.
    Applies multi-signal relevance ranking across title, category, description,
    attributes, and semantic vector similarity.
    """

    def __init__(self):
        self.last_diagnostics: Dict[str, Any] = {}

    @staticmethod
    def _compute_relevance_score(
        prod: Dict[str, Any],
        query: str,
        structured_params: Dict[str, Any],
        semantic_score: float = 0.0,
        is_structured_match: bool = False
    ) -> float:
        """
        Computes a grounded multi-signal relevance score (0 - 100+).
        """
        score = 0.0
        q_lower = query.lower().strip()
        title_lower = prod.get("title", "").lower().strip()
        cat_lower = prod.get("category", "").lower().replace(">>", " ")
        desc_lower = prod.get("description", "").lower()
        attrs_lower = " ".join(f"{k} {v}" for k, v in prod.get("attributes", {}).items()).lower()
        pid = prod.get("product_id", "").upper().strip()

        # 1. Exact Product ID / SKU match (highest specificity)
        req_pid = (structured_params.get("product_id") or "").upper().strip()
        if (req_pid and pid == req_pid) or (pid and pid in q_lower.upper()):
            score += 100.0

        # Extract non-stop shopping terms
        words = [w for w in re.findall(r'\b[a-zA-Z0-9]{2,}\b', q_lower) if w not in STOP_WORDS]
        stemmed_words = [stem_word(w) for w in words]

        # 2. Exact Title Match
        if title_lower and (title_lower == q_lower or title_lower in q_lower):
            score += 40.0

        # 3. Title Word & Phrase Matches
        title_word_matches = 0
        for w, st in zip(words, stemmed_words):
            if w in title_lower:
                score += 12.0
                title_word_matches += 1
            elif st in title_lower:
                score += 8.0
                title_word_matches += 1

        # Multi-word phrase in title bonus
        if len(words) >= 2:
            phrase = " ".join(words)
            if phrase in title_lower:
                score += 20.0

        # 4. Category & Subcategory Matches
        for w, st in zip(words, stemmed_words):
            if w in cat_lower:
                score += 10.0
            elif st in cat_lower:
                score += 6.0

        # Explicit category parameter alignment
        if structured_params.get("category"):
            req_cat = structured_params["category"].lower()
            if req_cat in cat_lower or (req_cat in ("clothing", "apparel") and ("clothing" in cat_lower or "apparel" in cat_lower)):
                score += 15.0

        # 5. Description and Attributes Matches
        for w in words:
            if w in desc_lower or w in attrs_lower:
                score += 3.0

        # 6. Semantic Vector Similarity Signal
        if semantic_score > 0:
            score += (semantic_score * 40.0)

        # 7. Constraint Satisfaction & In-Stock Tie-breakers
        if prod.get("stock_status", "").lower() in ("in stock", "available", "instock"):
            score += 2.0

        if is_structured_match:
            score += 5.0

        rating = prod.get("rating")
        if rating is not None:
            score += (float(rating) * 0.5)

        return score

    def retrieve(
        self,
        query: str,
        structured_params: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> Tuple[List[CandidateEvidence], Optional[CandidateEvidence]]:
        """
        Executes hybrid retrieval and relevance ranking.
        Returns:
            product_candidates: Top candidate products ranked by multi-signal relevance.
            policy_candidate: Matching policy section if query pertains to policy, else None.
        """
        if structured_params is None:
            structured_params = {}
        product_candidates: List[CandidateEvidence] = []
        policy_candidate: Optional[CandidateEvidence] = None

        # 1. Policy Retrieval Check
        policy_matches = policy_search_engine.search(query)
        if policy_matches:
            top_sec, p_score = policy_matches[0]
            policy_candidate = CandidateEvidence(
                source_type="policy",
                source_id=top_sec.section_id,
                data=top_sec.to_dict(),
                retrieval_method="policy",
                score=p_score
            )

        # 2. Structured Product Search
        has_structured_filters = any(
            (bool(v) if isinstance(v, (dict, list, str)) else v is not None)
            for k, v in structured_params.items()
            if k in ("product_id", "max_price", "min_price", "category", "brand", "color", "material", "stock_required", "min_rating", "required_attributes", "sort_by", "min_reviews")
        )
        
        structured_map: Dict[str, Dict[str, Any]] = {}
        if has_structured_filters:
            matched_prods = structured_search_engine.search(**structured_params)
            for p in matched_prods:
                structured_map[p["product_id"]] = p

        # 3. Semantic Search (as complementary high-recall signal)
        semantic_results = local_vector_index.query(query, top_k=max(top_k * 4, 40), min_score=0.04)
        semantic_map: Dict[str, Tuple[Dict[str, Any], float]] = {}
        for p, score in semantic_results:
            p_key = p.get("product_id") or p.get("record_id")
            if not p_key:
                continue
            cat_p = catalogue_loader.get_product(p_key)
            if cat_p:
                if p_key not in semantic_map or score > semantic_map[p_key][1]:
                    semantic_map[p_key] = (cat_p, score)
            else:
                if p_key not in semantic_map or score > semantic_map[p_key][1]:
                    semantic_map[p_key] = (p, score)

        # 4. Merge candidates into unified candidate pool
        all_candidate_pids = set(structured_map.keys()) | set(semantic_map.keys())
        
        # If no candidates found with strict structured filters, retrieve semantic directly
        if not all_candidate_pids and not has_structured_filters:
            for p, score in semantic_results:
                pk = p.get("product_id") or p.get("record_id")
                if pk:
                    all_candidate_pids.add(pk)

        scored_candidates: List[CandidateEvidence] = []
        for pid in all_candidate_pids:
            cat_p = catalogue_loader.get_product(pid)
            if catalogue_loader.is_ready and not cat_p:
                continue
            prod = cat_p or structured_map.get(pid) or (semantic_map[pid][0] if pid in semantic_map else None)
            if not prod:
                continue

            # If candidate is a multi-domain record referencing a catalogue product, prefer the catalogue product
            if cat_p:
                prod = cat_p
            elif prod.get("product_id") and catalogue_loader.get_product(prod["product_id"]):
                prod = catalogue_loader.get_product(prod["product_id"])

            # Verify hard constraints if present
            if structured_params.get("max_price") is not None and prod.get("price") is not None:
                if prod["price"] > structured_params["max_price"]:
                    continue
            if structured_params.get("min_price") is not None and prod.get("price") is not None:
                if prod["price"] < structured_params["min_price"]:
                    continue
            if structured_params.get("stock_required") is True:
                stock_st = prod.get("stock_status", "").lower()
                if stock_st not in ("in stock", "available", "instock") and "in stock" not in stock_st:
                    continue
            if structured_params.get("category"):
                cat_lower = structured_params["category"].lower()
                prod_cat = prod.get("category", "").lower()
                prod_title = prod.get("title", "").lower()
                is_cat = (
                    cat_lower in prod_cat
                    or cat_lower in prod_title
                    or (cat_lower in ("clothing", "apparel", "fashion") and any(ac in prod_cat for ac in ("clothing", "apparel", "fashion")))
                )
                if not is_cat:
                    continue

            if structured_params.get("material"):
                mat_req = structured_params["material"].strip().lower()
                prod_mat = str(prod.get("attributes", {}).get("material", "")).strip().lower()
                prod_desc = prod.get("description", "").lower()
                prod_title = prod.get("title", "").lower()
                if mat_req not in prod_mat and mat_req not in prod_desc and mat_req not in prod_title:
                    continue

            if structured_params.get("color"):
                col_req = structured_params["color"].strip().lower()
                prod_col = str(prod.get("attributes", {}).get("color", "")).strip().lower()
                prod_title = prod.get("title", "").lower()
                if col_req not in prod_col and col_req not in prod_title:
                    continue

            if structured_params.get("brand"):
                brand_req = structured_params["brand"].strip().lower()
                prod_brand = str(prod.get("attributes", {}).get("brand", "")).strip().lower()
                prod_title = prod.get("title", "").lower()
                if brand_req not in prod_brand and brand_req not in prod_title:
                    continue

            if structured_params.get("required_attributes"):
                req_attrs = structured_params["required_attributes"]
                mismatch = False
                for rk, rv in req_attrs.items():
                    if not structured_search_engine.match_attribute(prod, rk, rv):
                        mismatch = True
                        break
                if mismatch:
                    continue

            sem_score = semantic_map.get(pid, (None, 0.0))[1]
            is_struct = pid in structured_map

            rel_score = self._compute_relevance_score(
                prod=prod,
                query=query,
                structured_params=structured_params,
                semantic_score=sem_score,
                is_structured_match=is_struct
            )

            # Assign retrieval method
            if is_struct and sem_score > 0:
                ret_method = "hybrid"
            elif is_struct:
                ret_method = "structured"
            else:
                ret_method = "semantic"

            # Normalized confidence score (0.0 - 1.0) for evidence engine
            normalized_score = min(1.0, max(0.2, (rel_score / 50.0)))

            src_type = "product" if (not prod.get("category_type") or "catalogue" in str(prod.get("category_type")).lower()) else str(prod.get("category_type")).lower().replace("datasetcategory.", "")
            scored_candidates.append(
                CandidateEvidence(
                    source_type=src_type,
                    source_id=pid,
                    data=prod,
                    retrieval_method=ret_method,
                    score=normalized_score,
                    relevance_score=rel_score
                )
            )

        # Sort candidates descending by multi-signal relevance score
        scored_candidates.sort(key=lambda c: c.relevance_score, reverse=True)
        final_top = scored_candidates[:top_k]

        methods_used = []
        if structured_map:
            methods_used.append("structured")
        if semantic_map:
            methods_used.append("semantic")
        if policy_candidate:
            methods_used.append("policy")

        self.last_diagnostics = {
            "query": query,
            "retrieval_methods": methods_used,
            "structured_candidates_count": len(structured_map),
            "semantic_candidates_count": len(semantic_map),
            "deduplicated_candidates_count": len(scored_candidates),
            "applied_filters": {k: v for k, v in structured_params.items() if v is not None},
            "vector_index_operational": local_vector_index.is_indexed,
            "catalogue_version": catalogue_loader.catalogue_version,
            "final_candidates_count": len(final_top)
        }

        return final_top, policy_candidate

hybrid_retriever = HybridRetriever()
