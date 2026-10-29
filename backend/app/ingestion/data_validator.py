import re
import json
from typing import Any, Dict, Optional, Tuple, List
from app.ingestion.schema_mapper import DatasetCategory

class DataValidator:
    """Validates and normalizes raw records across diverse domain categories without altering ground truths."""

    @staticmethod
    def parse_price(val: Any) -> Optional[float]:
        """Safely parses prices from diverse formats (numbers, currency strings) to float."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            try:
                price = float(val)
                return price if price >= 0 else None
            except (ValueError, TypeError):
                return None

        # String parsing
        s = str(val).strip()
        if not s or s.lower() in ("nan", "null", "none", "n/a"):
            return None

        # Remove currency symbols (₹, $, €, £) and commas
        cleaned = re.sub(r'[^\d.]', '', s)
        try:
            price = float(cleaned)
            return price if price >= 0 else None
        except ValueError:
            return None

    @staticmethod
    def normalize_stock_status(val: Any) -> str:
        """Normalizes stock status to standard 'In Stock' or 'Out of Stock'."""
        if val is None:
            return "In Stock"
        if isinstance(val, (int, float)):
            return "In Stock" if val > 0 else "Out of Stock"
        s = str(val).strip().lower()
        if s in ("1", "true", "in stock", "in_stock", "available", "yes", "instock"):
            return "In Stock"
        if s in ("0", "false", "out of stock", "out_of_stock", "unavailable", "no", "sold out"):
            return "Out of Stock"
        try:
            num = float(s)
            return "In Stock" if num > 0 else "Out of Stock"
        except ValueError:
            pass
        return str(val).strip()

    @staticmethod
    def parse_attributes(val: Any) -> Dict[str, Any]:
        """Parses attributes from dictionary, JSON string, or semicolon/comma key:value pairs."""
        if val is None:
            return {}
        if isinstance(val, dict):
            return {str(k).strip().lower(): v for k, v in val.items()}
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return {}
            # Try JSON format
            if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, dict):
                        return {str(k).strip().lower(): v for k, v in parsed.items()}
                except json.JSONDecodeError:
                    pass
            # Try key:value; key2:value2 format
            attrs = {}
            pairs = re.split(r'[;,]\s*', s)
            for pair in pairs:
                if ':' in pair:
                    k, v = pair.split(':', 1)
                    attrs[k.strip().lower()] = v.strip()
                elif '=' in pair:
                    k, v = pair.split('=', 1)
                    attrs[k.strip().lower()] = v.strip()
            if attrs:
                return attrs
            # Free-form textual specifications/details
            return {"details": s}
        return {}

    @classmethod
    def validate_record(cls, raw: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Legacy strict validator: requires product_id, title, and valid numeric price.
        Preserved for 100% backward compatibility with existing tests.
        """
        prod_id = raw.get("product_id")
        if prod_id is None or str(prod_id).strip() == "" or str(prod_id).lower() in ("nan", "none", "null"):
            return False, "Missing or empty product_id", None

        title = raw.get("title")
        if title is None or str(title).strip() == "":
            return False, "Missing or empty title", None

        raw_price = raw.get("price")
        parsed_price = cls.parse_price(raw_price)
        if parsed_price is None:
            return False, f"Invalid or missing numeric price: {raw_price}", None

        normalized = {
            "product_id": str(prod_id).strip(),
            "title": str(title).strip(),
            "description": str(raw.get("description", "")).strip(),
            "category": str(raw.get("category", "General")).strip(),
            "price": parsed_price,
            "stock_status": cls.normalize_stock_status(raw.get("stock_status")),
            "rating": float(raw.get("rating")) if raw.get("rating") is not None and str(raw.get("rating")).replace('.','',1).isdigit() else None,
            "attributes": cls.parse_attributes(raw.get("attributes")),
            "raw_record": raw
        }
        return True, None, normalized

    @classmethod
    def validate_flexible_record(
        cls,
        raw: Dict[str, Any],
        category: DatasetCategory,
        field_mappings: Dict[str, str], # canonical -> original_col
        row_idx: int = 1
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Domain-aware flexible validator that normalizes records according to their detected category.
        Never fabricates customer IDs or falsifies facts, but safely derives record references.
        """
        if not raw or not isinstance(raw, dict):
            return False, "Record is empty or not a valid key-value object", None

        # Helper to extract value using canonical name
        def get_val(canonical: str, default: Any = None) -> Any:
            orig_col = field_mappings.get(canonical)
            if orig_col and orig_col in raw and raw[orig_col] is not None:
                return raw[orig_col]
            # Case-insensitive check
            if orig_col:
                for k, v in raw.items():
                    if k.strip().lower() == orig_col.strip().lower() and v is not None:
                        return v
            # Direct canonical key fallback
            if canonical in raw and raw[canonical] is not None:
                return raw[canonical]
            return default

        # Collect unmapped fields into attributes dictionary
        mapped_orig_cols = {v.strip().lower() for v in field_mappings.values() if v}
        attributes = {}
        # First check if there is an explicit attributes/specs column
        raw_attrs = get_val("attributes")
        if raw_attrs:
            attributes.update(cls.parse_attributes(raw_attrs))
        for k, v in raw.items():
            if str(k).strip().lower() not in mapped_orig_cols and str(k).strip().lower() != "attributes":
                attributes[str(k).strip().lower()] = v

        # ---------------- UNRELATED DATASET ----------------
        if category == DatasetCategory.UNRELATED_DATASET:
            return False, f"Row {row_idx}: Unrelated dataset does not contain recognizable commerce, product, review, or policy data", None

        # ---------------- CATEGORY A: PRODUCT CATALOGUE ----------------
        if category == DatasetCategory.PRODUCT_CATALOGUE:
            raw_id = get_val("product_id")
            if not raw_id:
                raw_id = get_val("sku") or get_val("item_code") or get_val("listing_id")
            is_generated_id = False
            if not raw_id or str(raw_id).strip() == "" or str(raw_id).lower() in ("nan", "none", "null"):
                prod_id = f"TC-GEN-{row_idx:05d}"
                is_generated_id = True
            else:
                prod_id = str(raw_id).strip()

            raw_title = get_val("title")
            if not raw_title or str(raw_title).strip() == "":
                # Try finding first non-empty string column as title
                string_cands = [str(v).strip() for k, v in raw.items() if isinstance(v, str) and len(str(v).strip()) > 2]
                title = string_cands[0] if string_cands else f"Item {prod_id}"
            else:
                title = str(raw_title).strip()

            raw_price = get_val("price")
            parsed_price = cls.parse_price(raw_price) if raw_price is not None else 0.0
            if parsed_price is None:
                parsed_price = 0.0

            desc = str(get_val("description", "")).strip()
            if not desc and attributes:
                desc = str(attributes.get("details") or attributes.get("specifications") or attributes.get("technical_details") or attributes.get("features") or "").strip()

            brand = str(get_val("brand", "")).strip() or None
            if brand and "brand" not in attributes:
                attributes["brand"] = brand

            normalized = {
                "product_id": prod_id,
                "title": title,
                "description": desc,
                "category": str(get_val("category", "General")).strip(),
                "price": parsed_price,
                "stock_status": cls.normalize_stock_status(get_val("stock_status")),
                "rating": float(get_val("rating")) if get_val("rating") is not None and str(get_val("rating")).replace('.','',1).isdigit() else None,
                "brand": brand,
                "attributes": attributes,
                "category_type": DatasetCategory.PRODUCT_CATALOGUE.value,
                "is_generated_id": is_generated_id,
                "raw_record": raw
            }
            return True, None, normalized

        # ---------------- CATEGORY B: MARKETPLACE & SELLER LISTINGS ----------------
        elif category == DatasetCategory.MARKETPLACE_LISTINGS:
            raw_id = get_val("listing_id") or get_val("product_id") or f"LISTING-{row_idx:05d}"
            title = str(get_val("title", f"Listing {raw_id}")).strip()
            seller = str(get_val("seller_name", "Unknown Seller")).strip()
            marketplace = str(get_val("marketplace", "Marketplace")).strip()
            price = cls.parse_price(get_val("price")) or 0.0

            desc = str(get_val("description", "")).strip()
            if not desc and attributes:
                desc = str(attributes.get("details") or attributes.get("specifications") or attributes.get("technical_details") or attributes.get("features") or "").strip()

            brand = str(get_val("brand", "")).strip() or None
            if brand and "brand" not in attributes:
                attributes["brand"] = brand
            if seller and "seller_name" not in attributes:
                attributes["seller_name"] = seller

            cat_name = str(get_val("category", "General")).strip()
            raw_rating = get_val("rating")
            rating = float(raw_rating) if raw_rating is not None and str(raw_rating).replace('.','',1).isdigit() else None

            normalized = {
                "record_id": str(raw_id).strip(),
                "product_id": str(get_val("product_id", raw_id)).strip(),
                "title": title,
                "description": desc,
                "category": cat_name,
                "brand": brand,
                "seller_name": seller,
                "marketplace": marketplace,
                "price": price,
                "rating": rating,
                "currency": str(get_val("currency", "INR")).strip().upper(),
                "stock_status": cls.normalize_stock_status(get_val("stock_status")),
                "source_url": str(get_val("source_url", "")).strip() or None,
                "attributes": attributes,
                "category_type": DatasetCategory.MARKETPLACE_LISTINGS.value,
                "raw_record": raw
            }
            return True, None, normalized

        # ---------------- CATEGORY C: COMPETITOR PRICING ----------------
        elif category == DatasetCategory.COMPETITOR_PRICING:
            product_ref = str(raw.get("product_reference") or raw.get("item_reference") or get_val("product_id") or get_val("title") or f"PROD-REF-{row_idx:05d}").strip()
            competitor = str(get_val("competitor_name") or get_val("seller_name") or get_val("marketplace") or "Competitor").strip()
            obs_price = cls.parse_price(get_val("competitor_price") or get_val("price"))
            if obs_price is None:
                return False, f"Competitor record row {row_idx} missing valid observed price", None

            listing_id = str(raw.get("listing_id") or get_val("record_id") or f"COMP-{row_idx:05d}").strip()

            normalized = {
                "record_id": listing_id,
                "product_id": product_ref,
                "title": str(get_val("title", product_ref)).strip(),
                "seller_name": competitor,
                "competitor_name": competitor,
                "observed_price": obs_price,
                "price": obs_price,
                "currency": str(get_val("currency", "INR")).strip().upper(),
                "observation_date": str(get_val("date", "")).strip() or None,
                "source_url": str(get_val("source_url", "")).strip() or None,
                "attributes": attributes,
                "category_type": DatasetCategory.COMPETITOR_PRICING.value,
                "raw_record": raw
            }
            return True, None, normalized

        # ---------------- CATEGORY D: CUSTOMER REVIEWS ----------------
        elif category == DatasetCategory.CUSTOMER_REVIEWS:
            review_text = str(get_val("review_text", "")).strip()
            raw_rating = get_val("rating")
            rating = float(raw_rating) if raw_rating is not None and str(raw_rating).replace('.','',1).isdigit() else None

            if not review_text and rating is None:
                return False, f"Review record row {row_idx} contains neither review text nor rating", None

            product_ref = str(raw.get("item_reference") or raw.get("product_reference") or get_val("product_id") or get_val("title") or "General Feedback").strip()
            review_id = str(raw.get("review_id") or get_val("record_id") or f"REV-{row_idx:05d}").strip()

            normalized = {
                "record_id": review_id,
                "product_id": product_ref,
                "title": f"Review for {product_ref}",
                "review_text": review_text,
                "rating": rating,
                "reviewer_name": str(get_val("reviewer_name", "Anonymous")).strip(),
                "review_date": str(get_val("date", "")).strip() or None,
                "attributes": attributes,
                "category_type": DatasetCategory.CUSTOMER_REVIEWS.value,
                "raw_record": raw
            }
            return True, None, normalized

        # ---------------- CATEGORY E: PRODUCT SPECIFICATIONS ----------------
        elif category == DatasetCategory.PRODUCT_SPECIFICATIONS:
            raw_id = get_val("product_id") or f"SPEC-{row_idx:05d}"
            title = str(get_val("title", f"Specification {raw_id}")).strip()

            normalized = {
                "record_id": str(raw_id).strip(),
                "product_id": str(raw_id).strip(),
                "title": title,
                "category": str(get_val("category", "Specifications")).strip(),
                "attributes": attributes,
                "category_type": DatasetCategory.PRODUCT_SPECIFICATIONS.value,
                "raw_record": raw
            }
            return True, None, normalized

        # ---------------- CATEGORY F: POLICIES AND EVIDENCE ----------------
        elif category == DatasetCategory.POLICIES_AND_EVIDENCE:
            content = str(get_val("policy_content", "")).strip()
            title = str(get_val("title") or get_val("policy_type") or f"Policy Section {row_idx}").strip()
            if not content and not title:
                return False, f"Policy row {row_idx} missing both title and content", None

            normalized = {
                "record_id": f"POL-{row_idx:05d}",
                "title": title,
                "policy_type": str(get_val("policy_type", "General Policy")).strip(),
                "policy_content": content or title,
                "effective_date": str(get_val("date", "")).strip() or None,
                "source": str(get_val("source_url", "Official Policy")).strip(),
                "attributes": attributes,
                "category_type": DatasetCategory.POLICIES_AND_EVIDENCE.value,
                "raw_record": raw
            }
            return True, None, normalized

        # ---------------- CATEGORY G: GENERIC DATASET ----------------
        else:
            raw_id = get_val("product_id") or get_val("record_id") or f"REC-{row_idx:05d}"
            title = str(get_val("title") or f"Record {raw_id}").strip()
            desc = str(get_val("description") or get_val("content", "")).strip()
            if not desc and attributes:
                desc = str(attributes.get("details") or attributes.get("specifications") or attributes.get("technical_details") or "").strip()

            price = cls.parse_price(get_val("price")) or 0.0
            stock = cls.normalize_stock_status(get_val("stock_status"))
            cat_name = str(get_val("category", "General")).strip()
            brand = str(get_val("brand", "")).strip() or None
            if brand and "brand" not in attributes:
                attributes["brand"] = brand

            raw_rating = get_val("rating")
            rating = float(raw_rating) if raw_rating is not None and str(raw_rating).replace('.','',1).isdigit() else None

            normalized = {
                "record_id": str(raw_id).strip(),
                "product_id": str(raw_id).strip(),
                "title": title,
                "description": desc,
                "category": cat_name,
                "price": price,
                "stock_status": stock,
                "rating": rating,
                "brand": brand,
                "attributes": attributes,
                "category_type": DatasetCategory.GENERIC_DATASET.value,
                "raw_record": raw
            }
            return True, None, normalized
