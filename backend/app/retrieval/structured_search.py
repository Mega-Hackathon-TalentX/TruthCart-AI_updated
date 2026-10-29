import re
from typing import Dict, List, Optional, Any
from app.ingestion.catalogue_loader import catalogue_loader

class StructuredSearchEngine:
    """Deterministic structured filtering on ground-truth catalogue attributes."""

    @staticmethod
    def match_attribute(prod: Dict[str, Any], attr_key: str, target_val: str) -> bool:
        """Checks if product attributes or title/desc match the target attribute value."""
        target_lower = str(target_val).strip().lower()
        if not target_lower:
            return True

        # 0. Check top-level dictionary fields directly
        val_top = prod.get(attr_key) or (prod.get("brand") if attr_key == "brand" else None)
        if val_top and target_lower in str(val_top).strip().lower():
            return True

        attrs = prod.get("attributes", {})
        if isinstance(attrs, str):
            try:
                import json
                attrs = json.loads(attrs)
            except Exception:
                attrs = {}
        if not isinstance(attrs, dict):
            attrs = {}
        # 1. Direct attribute match
        for k, v in attrs.items():
            if attr_key.lower() in k.lower():
                if isinstance(v, list):
                    if any(re.search(r'\b' + re.escape(target_lower) + r'\b', str(item).lower()) for item in v):
                        return True
                elif re.search(r'\b' + re.escape(target_lower) + r'\b', str(v).lower()):
                    return True

        # 2. Key-agnostic search in attribute values
        for v in attrs.values():
            if isinstance(v, list):
                if any(re.search(r'\b' + re.escape(target_lower) + r'\b', str(item).lower()) for item in v):
                    return True
            elif re.search(r'\b' + re.escape(target_lower) + r'\b', str(v).lower()):
                return True

        # 3. Mentioned in title or description
        title = prod.get("title", "").lower()
        desc = prod.get("description", "").lower()
        if re.search(r'\b' + re.escape(target_lower) + r'\b', title) or re.search(r'\b' + re.escape(target_lower) + r'\b', desc):
            return True

        return False

    @staticmethod
    def has_attribute(prod: Dict[str, Any], attr_key: str) -> bool:
        """Checks if a product catalogue record actually contains the specified attribute."""
        key_lower = attr_key.strip().lower()
        if not key_lower:
            return False
        
        # Check core fields (must have valid non-empty values)
        if key_lower in ("price", "cost", "mrp"):
            try:
                return prod.get("price") is not None and float(prod.get("price", 0)) > 0
            except (ValueError, TypeError):
                return False

        if key_lower in ("stock", "stock_status", "availability"):
            return bool(prod.get("stock_status"))

        if key_lower in ("category", "department"):
            return bool(prod.get("category"))

        if key_lower in ("brand", "make", "manufacturer"):
            attrs = prod.get("attributes", {}) if isinstance(prod.get("attributes"), dict) else {}
            return bool(prod.get("brand") or attrs.get("brand"))

        if key_lower in ("rating", "score"):
            try:
                return prod.get("rating") is not None and float(prod.get("rating", 0)) > 0
            except (ValueError, TypeError):
                return False

        # Check attributes dictionary
        attrs = prod.get("attributes", {})
        if isinstance(attrs, dict):
            for k, v in attrs.items():
                k_clean = k.lower().replace("_", " ").replace("-", " ")
                if (key_lower in k_clean or k_clean in key_lower) and v is not None and str(v).strip():
                    return True

        return False

    def search(
        self,
        product_id: Optional[str] = None,
        title: Optional[str] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        color: Optional[str] = None,
        material: Optional[str] = None,
        stock_required: Optional[bool] = None,
        min_rating: Optional[float] = None,
        required_attributes: Optional[Dict[str, str]] = None,
        keyword: Optional[str] = None,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Filters catalogue records deterministically. Returns matching products."""
        all_products = catalogue_loader.get_all_products()
        if not all_products:
            return []

        # 1. Exact product_id filter (Highest specificity)
        if product_id:
            pid_clean = product_id.strip().upper()
            matched = [
                p for p in all_products
                if p.get("product_id", "").upper() == pid_clean
            ]
            if matched:
                return matched
            # Try partial ID match if exact not found
            matched = [
                p for p in all_products
                if pid_clean in p.get("product_id", "").upper()
            ]
            if matched:
                return matched

        results = []
        for p in all_products:
            # Title filter (if specified)
            if title:
                title_clean = title.strip().lower()
                prod_title_clean = p.get("title", "").strip().lower()
                if title_clean != prod_title_clean and title_clean not in prod_title_clean:
                    continue

            # Price constraints
            price = p.get("price")
            if price is not None:
                if max_price is not None and price > max_price:
                    continue
                if min_price is not None and price < min_price:
                    continue
            elif max_price is not None or min_price is not None:
                continue

            # Stock requirement
            if stock_required is True:
                stock_status = p.get("stock_status", "").lower()
                if stock_status not in ("in stock", "available", "yes", "instock") and "in stock" not in stock_status:
                    continue

            # Rating constraint
            if min_rating is not None:
                rating = p.get("rating")
                if rating is None or rating < min_rating:
                    continue

            # Category filter (supports hierarchical paths and clothing/apparel equivalence)
            if category:
                cat_lower = category.strip().lower()
                prod_cat = p.get("category", "").lower()
                prod_title = p.get("title", "").lower()
                is_cat_match = (
                    cat_lower in prod_cat
                    or cat_lower in prod_title
                    or (cat_lower in ("apparel", "clothing", "fashion") and ("apparel" in prod_cat or "clothing" in prod_cat or "fashion" in prod_cat))
                )
                if not is_cat_match:
                    continue

            # Brand filter
            if brand:
                if not self.match_attribute(p, "brand", brand):
                    continue

            # Color filter
            if color:
                if not self.match_attribute(p, "color", color):
                    continue

            # Material filter
            if material:
                if not self.match_attribute(p, "material", material):
                    continue

            # Custom attribute filters
            if required_attributes:
                mismatch = False
                for req_k, req_v in required_attributes.items():
                    if not self.match_attribute(p, req_k, req_v):
                        mismatch = True
                        break
                if mismatch:
                    continue

            # General keyword filter (if provided)
            if keyword:
                kw_lower = keyword.strip().lower()
                content = f"{p.get('product_id', '')} {p.get('title', '')} {p.get('description', '')} {p.get('category', '')}".lower()
                if kw_lower not in content:
                    continue

            results.append(p)

        # Review count filter
        min_reviews = kwargs.get("min_reviews")
        if min_reviews is not None:
            filtered_by_reviews = [
                p for p in results
                if int(p.get("attributes", {}).get("review_count") or p.get("review_count") or 0) >= min_reviews
            ]
            if filtered_by_reviews:
                results = filtered_by_reviews

        # Deterministic sorting
        sort_by = kwargs.get("sort_by")
        if sort_by == "rating_desc":
            results.sort(key=lambda p: float(p.get("rating") or 0.0), reverse=True)
        elif sort_by == "price_asc":
            results.sort(key=lambda p: float(p.get("price") or 0.0))
        elif sort_by == "price_desc":
            results.sort(key=lambda p: float(p.get("price") or 0.0), reverse=True)

        return results

structured_search_engine = StructuredSearchEngine()
structured_search = structured_search_engine
