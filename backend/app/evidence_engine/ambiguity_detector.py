from typing import List, Dict, Any, Optional, Tuple

class AmbiguityDetector:
    """Detects ambiguous user intents, multiple candidate ties, or conflicting constraints."""

    @staticmethod
    def detect_conflicting_constraints(parsed_query: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        min_p = parsed_query.get("min_price")
        max_p = parsed_query.get("max_price")
        if min_p is not None and max_p is not None and min_p > max_p:
            return True, f"Conflicting price constraints: minimum ₹{min_p:.0f} is higher than maximum ₹{max_p:.0f}."
        return False, None

    @staticmethod
    def check_candidate_ambiguity(
        candidates: List[Dict[str, Any]],
        parsed_query: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Determines whether candidate matches require clarification.
        If a query is very generic and returns multiple distinct items, ask a focused clarification.
        """
        # If query specified exact product ID, it is NOT ambiguous
        if parsed_query.get("product_id"):
            return False, None

        q_raw = parsed_query.get("query", "").lower()
        num_matches = len(candidates)
        if num_matches == 0:
            return False, None

        # If user asked for a specific item (e.g., "Apex 15 Stealth Gaming Laptop") and exactly 1 product matched
        if num_matches == 1:
            return False, None

        # If user mentioned a specific product title that matches the top candidate
        if candidates:
            top_title = candidates[0].get("title", "").strip().lower()
            if top_title and len(top_title) >= 8 and top_title in q_raw:
                return False, None

        # Direct availability checks (e.g. "Is there any footwear available?") are answered directly
        is_availability_query = any(phrase in q_raw for phrase in ["available", "in stock", "is there any", "do you have", "what footwear", "any footwear", "are there"])

        has_specific_filters = any([
            parsed_query.get("max_price") is not None,
            parsed_query.get("min_price") is not None,
            parsed_query.get("sort_by") is not None,
            parsed_query.get("min_reviews") is not None,
            parsed_query.get("brand"),
            parsed_query.get("color"),
            parsed_query.get("material"),
            parsed_query.get("required_attributes"),
            parsed_query.get("requested_subtype"),
            parsed_query.get("stock_required") is not None
        ])

        # If user asked a very broad generic query with multiple candidates (>= 2) without filters or availability check
        if not has_specific_filters and not is_availability_query and num_matches >= 2:
            category = parsed_query.get("category") or "products"
            brands = sorted(list({c.get("attributes", {}).get("brand") for c in candidates if c.get("attributes", {}).get("brand")}))
            if brands:
                return True, f"I found {num_matches} {category}. Could you specify your preferred brand (e.g., {', '.join(brands[:3])}) or a target price range?"
            return True, f"I found {num_matches} options matching '{category}'. Could you specify a preferred color, material, or budget?"

        return False, None


ambiguity_detector = AmbiguityDetector()
