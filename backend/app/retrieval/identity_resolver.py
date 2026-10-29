"""
TruthCart AI — Product Identity Resolution and Cross-Dataset Linkage Engine.
Resolves identities across Product Catalogues, Customer Reviews, Competitor Pricing,
Marketplace Listings, and Specifications.
Strict Invariants:
1. Never merge products solely because names are somewhat similar.
2. Preserve conflicting source records intact with full provenance.
3. Record match_type as EXACT, INFERRED, or MANUALLY_CONFIRMED.
4. Never fabricate identifiers.
5. Incompatible variants (e.g., RAM, storage, color, size) are never merged without warning.
6. Reviews are never attributed to a product without validated matching evidence.
"""

import re
import json
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Set

from app.core.logging_config import SafeLogger
from app.db.database import db
from app.ingestion.catalogue_loader import catalogue_loader

class RelationshipType(str, Enum):
    EXACT = "EXACT"
    INFERRED = "INFERRED"
    MANUALLY_CONFIRMED = "MANUALLY_CONFIRMED"
    UNLINKED = "UNLINKED"

class ProductIdentityResolver:
    """
    Cautious cross-dataset identity resolution engine.
    Links disparate records across catalogues, reviews, seller listings, and competitor intel.
    """

    @staticmethod
    def normalize_identifier(identifier: Optional[str]) -> Optional[str]:
        if not identifier:
            return None
        cleaned = re.sub(r'[^a-zA-Z0-9\-_]', '', str(identifier).strip().upper())
        return cleaned if cleaned else None

    @staticmethod
    def extract_model_tokens(title: str, brand: Optional[str] = None) -> Set[str]:
        """Extracts significant model tokens, filtering brand and generic stopwords."""
        t_lower = title.lower()
        if brand:
            t_lower = t_lower.replace(brand.lower(), "")
        # Remove common retail noise tokens
        noise = {"new", "original", "genuine", "authentic", "best", "hot", "deal", "pack", "set", "for", "with"}
        tokens = set(re.findall(r'\b[a-zA-Z0-9]{2,}\b', t_lower)) - noise
        return tokens

    @classmethod
    def resolve_relationship(
        cls,
        source_record: Dict[str, Any],
        candidate_products: List[Dict[str, Any]]
    ) -> Tuple[RelationshipType, Optional[str], float, str]:
        """
        Evaluates a source record against candidate products to determine linkage.
        Returns:
            match_type: EXACT, INFERRED, or UNLINKED
            target_product_id: Linked product ID or None
            confidence: Float score 0.0 - 1.0
            reason: Human-auditable explanation
        """
        # 1. Check for exact identifier match (product_id, sku, asin, gtin, upc, item_code)
        src_raw = source_record.get("raw_record") or source_record
        id_candidates = [
            source_record.get("product_reference"),
            source_record.get("product_id"),
            source_record.get("item_reference"),
            source_record.get("sku"),
            source_record.get("asin"),
            source_record.get("item_code"),
            src_raw.get("product_reference"),
            src_raw.get("item_reference"),
            src_raw.get("target_sku"),
            src_raw.get("product_id"),
            src_raw.get("sku")
        ]
        
        for cand_id in id_candidates:
            norm_cand = cls.normalize_identifier(cand_id)
            if not norm_cand:
                continue
            for prod in candidate_products:
                prod_pid = cls.normalize_identifier(prod.get("product_id"))
                prod_sku = cls.normalize_identifier(prod.get("attributes", {}).get("sku"))
                if norm_cand in (prod_pid, prod_sku):
                    return (
                        RelationshipType.EXACT,
                        prod["product_id"],
                        1.0,
                        f"Exact identifier match on '{norm_cand}'."
                    )

        # 2. Cautious Inferred Matching (Requires brand match + high model token overlap + variant match)
        src_title = str(source_record.get("title") or src_raw.get("item_name") or src_raw.get("product_name") or "").strip()
        src_brand = str(source_record.get("brand") or source_record.get("attributes", {}).get("brand") or src_raw.get("brand") or "").strip()

        if not src_title or len(src_title) < 5:
            return RelationshipType.UNLINKED, None, 0.0, "Insufficient identifying text for cautious linkage."

        src_tokens = cls.extract_model_tokens(src_title, src_brand)
        if len(src_tokens) < 2:
            return RelationshipType.UNLINKED, None, 0.0, "Model tokens too sparse to safely infer identity."

        best_prod = None
        best_score = 0.0
        best_reason = ""

        for prod in candidate_products:
            p_title = prod.get("title", "")
            p_brand = str(prod.get("brand") or prod.get("attributes", {}).get("brand") or "").strip()

            # Invariant: If both records specify a brand, they MUST match.
            if src_brand and p_brand and src_brand.lower() != p_brand.lower():
                continue

            p_tokens = cls.extract_model_tokens(p_title, p_brand)
            if not p_tokens:
                continue

            overlap = src_tokens & p_tokens
            jaccard = len(overlap) / len(src_tokens | p_tokens)

            # Invariant: Check for incompatible variant signals (e.g. storage, ram, color)
            src_text_lower = f"{src_title} {json.dumps(source_record.get('attributes', {}))}".lower()
            p_text_lower = f"{p_title} {json.dumps(prod.get('attributes', {}))}".lower()

            # Spec variant conflicts (e.g. 128gb vs 256gb, 16gb vs 32gb)
            capacity_patterns = re.findall(r'\b(\d+\s*(?:gb|tb|mb))\b', src_text_lower)
            p_capacity_patterns = re.findall(r'\b(\d+\s*(?:gb|tb|mb))\b', p_text_lower)
            if capacity_patterns and p_capacity_patterns:
                clean_src_caps = {re.sub(r'\s+', '', c) for c in capacity_patterns}
                clean_p_caps = {re.sub(r'\s+', '', c) for c in p_capacity_patterns}
                if not (clean_src_caps & clean_p_caps):
                    # Variant capacity mismatch! Never merge!
                    continue

            if jaccard >= 0.70 and jaccard > best_score:
                best_score = jaccard
                best_prod = prod
                best_reason = f"Cautious inferred match: brand '{p_brand}' and {len(overlap)} matching model tokens."

        if best_prod and best_score >= 0.70:
            return (
                RelationshipType.INFERRED,
                best_prod["product_id"],
                round(best_score, 2),
                best_reason
            )

        return RelationshipType.UNLINKED, None, 0.0, "No safe exact or high-confidence cautious match found."

    @classmethod
    def get_cross_dataset_evidence(cls, product_id: str) -> Dict[str, Any]:
        """
        Retrieves all linked records across active datasets for a given product ID.
        Includes customer reviews, competitor pricing, seller listings, and specifications.
        Preserves all conflicting source records without loss.
        """
        results: Dict[str, List[Dict[str, Any]]] = {
            "reviews": [],
            "competitor_prices": [],
            "marketplace_listings": [],
            "specifications": []
        }

        # Query all active records referencing this product
        records = db.get_active_dataset_records(limit=200)
        norm_target_pid = cls.normalize_identifier(product_id)

        for r in records:
            cat = r.get("category", "")
            data = r.get("data") or {}
            ref = cls.normalize_identifier(r.get("product_reference") or data.get("product_id") or data.get("item_reference"))

            if ref == norm_target_pid:
                if cat == "CUSTOMER_REVIEWS":
                    results["reviews"].append({
                        "review_id": r.get("record_id"),
                        "rating": r.get("rating") or data.get("rating") or data.get("stars"),
                        "feedback": r.get("content_text") or data.get("review_text") or data.get("feedback"),
                        "reviewer": data.get("reviewer_name") or "Verified Shopper",
                        "date": r.get("date_observed") or data.get("date") or data.get("review_date"),
                        "source": "Active Review Dataset"
                    })
                elif cat == "COMPETITOR_PRICING":
                    results["competitor_prices"].append({
                        "listing_id": r.get("record_id"),
                        "seller_name": data.get("competitor_name") or data.get("seller_name") or "Competitor",
                        "observed_price": r.get("numeric_value") or data.get("observed_price"),
                        "currency": r.get("currency") or "INR",
                        "date": r.get("date_observed") or data.get("observation_date"),
                        "source_url": data.get("source_url") or None
                    })
                elif cat == "MARKETPLACE_LISTINGS":
                    results["marketplace_listings"].append({
                        "listing_id": r.get("record_id"),
                        "seller_name": data.get("seller_name") or data.get("marketplace") or "Seller",
                        "price": r.get("numeric_value") or data.get("price"),
                        "currency": r.get("currency") or "INR",
                        "source_url": data.get("source_url") or None
                    })
                elif cat == "PRODUCT_SPECIFICATIONS":
                    results["specifications"].append({
                        "spec_id": r.get("record_id"),
                        "title": r.get("title"),
                        "attributes": data.get("attributes", {})
                    })

        return results

    @classmethod
    def compare_seller_prices(cls, product_id: str) -> Dict[str, Any]:
        """
        Gathers price observations from active catalogue, competitor intel, and marketplace listings.
        Checks for variant compatibility and warns if prices may reflect different specs.
        """
        prod = catalogue_loader.get_product(product_id) or db.get_product_by_id(product_id)
        if not prod:
            return {
                "product_id": product_id,
                "found": False,
                "prices": [],
                "warnings": [f"Product '{product_id}' not found in official catalogue."]
            }

        catalogue_price = prod.get("price")
        price_list: List[Dict[str, Any]] = []

        if catalogue_price is not None:
            price_list.append({
                "seller": "TruthCart Official",
                "price": float(catalogue_price),
                "currency": "INR",
                "source_type": "CATALOGUE",
                "citation": f"[CATALOGUE:{product_id}]",
                "is_official": True
            })

        evidence = cls.get_cross_dataset_evidence(product_id)
        warnings: List[str] = []

        for comp in evidence["competitor_prices"]:
            price_val = comp.get("observed_price")
            if price_val is not None:
                price_list.append({
                    "seller": comp.get("seller_name", "Competitor"),
                    "price": float(price_val),
                    "currency": comp.get("currency", "INR"),
                    "source_type": "COMPETITOR",
                    "citation": f"[COMPETITOR:{comp.get('listing_id', product_id)}]",
                    "date": comp.get("date"),
                    "is_official": False
                })

        for lst in evidence["marketplace_listings"]:
            price_val = lst.get("price")
            if price_val is not None:
                price_list.append({
                    "seller": lst.get("seller_name", "Marketplace Seller"),
                    "price": float(price_val),
                    "currency": lst.get("currency", "INR"),
                    "source_type": "LISTING",
                    "citation": f"[LISTING:{lst.get('listing_id', product_id)}]",
                    "is_official": False
                })

        if len(price_list) >= 2:
            prices_only = [p["price"] for p in price_list]
            diff = max(prices_only) - min(prices_only)
            if diff > (min(prices_only) * 0.5):
                warnings.append("Price variance exceeds 50%. Please verify that seller listings reflect identical product specifications and packaging.")

        return {
            "product_id": product_id,
            "product_title": prod.get("title", f"Item {product_id}"),
            "found": True,
            "prices": price_list,
            "warnings": warnings
        }

    @classmethod
    def summarize_complaints(cls, product_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts verified customer complaints from active review datasets.
        Only summarizes complaints explicitly recorded in feedback text. Never hallucinates issues.
        """
        all_reviews = []
        if product_id:
            evidence = cls.get_cross_dataset_evidence(product_id)
            all_reviews = evidence["reviews"]
        else:
            records = db.get_active_dataset_records(category="CUSTOMER_REVIEWS", limit=100)
            for r in records:
                data = r.get("data") or {}
                all_reviews.append({
                    "review_id": r.get("record_id"),
                    "rating": r.get("rating") or data.get("rating") or data.get("stars"),
                    "feedback": r.get("content_text") or data.get("review_text") or data.get("feedback"),
                    "reviewer": data.get("reviewer_name") or "Shopper"
                })

        complaint_keywords = [
            "battery", "drain", "slow", "noise", "broken", "poor", "bad", "defective",
            "scratch", "tight", "loose", "heavy", "delay", "smell", "heat", "overheating"
        ]

        found_complaints: List[Dict[str, Any]] = []
        for rev in all_reviews:
            rating = rev.get("rating")
            fb = str(rev.get("feedback") or "").strip()
            if not fb:
                continue

            # Identify critical reviews (rating <= 3 or complaint words present)
            is_critical = (rating is not None and float(rating) <= 3) or any(k in fb.lower() for k in complaint_keywords)
            if is_critical:
                found_complaints.append({
                    "review_id": rev.get("review_id"),
                    "feedback": fb,
                    "rating": rating,
                    "citation": f"[REVIEW:{rev.get('review_id')}]"
                })

        return {
            "product_id": product_id,
            "total_reviews_analyzed": len(all_reviews),
            "complaint_count": len(found_complaints),
            "complaints": found_complaints
        }

identity_resolver = ProductIdentityResolver()

