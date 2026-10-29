import re
from typing import Dict, Any, List, Optional
from app.schemas.response import EvidenceItem
from app.ingestion.catalogue_loader import catalogue_loader
from app.ingestion.policy_loader import policy_loader

class EvidenceChecker:
    """Verifies that individual factual claims correspond directly to ground truth records."""

    @staticmethod
    def extract_product_evidence(product: Dict[str, Any], requested_fields: List[str]) -> List[EvidenceItem]:
        """Extracts verified evidence items directly from catalogue or multi-domain dataset record."""
        items: List[EvidenceItem] = []
        pid = str(product.get("product_id") or product.get("record_id") or "UNKNOWN")
        raw_cat = str(product.get("category_type") or "product").lower()
        src_type = "product" if ("catalogue" in raw_cat or raw_cat == "product") else raw_cat.replace("datasetcategory.", "")

        # Core fields always verified if record matched
        if product.get("title"):
            items.append(EvidenceItem(
                source_type=src_type,
                source_id=pid,
                field="title",
                value=product["title"]
            ))
        if product.get("price") is not None and product.get("price") > 0:
            items.append(EvidenceItem(
                source_type=src_type,
                source_id=pid,
                field="price",
                value=f"₹{float(product['price']):,.2f}"
            ))
        if product.get("stock_status"):
            items.append(EvidenceItem(
                source_type=src_type,
                source_id=pid,
                field="stock_status",
                value=product["stock_status"]
            ))

        if product.get("category"):
            items.append(EvidenceItem(
                source_type=src_type,
                source_id=pid,
                field="category",
                value=product["category"]
            ))

        if product.get("review_text"):
            items.append(EvidenceItem(
                source_type=src_type,
                source_id=pid,
                field="review_text",
                value=product["review_text"]
            ))

        if product.get("observed_price") is not None:
            curr = product.get("currency", "INR")
            items.append(EvidenceItem(
                source_type=src_type,
                source_id=pid,
                field="observed_price",
                value=f"{curr} {float(product['observed_price']):,.2f}"
            ))

        # Check top-level brand and rating
        if product.get("brand"):
            items.append(EvidenceItem(
                source_type=src_type,
                source_id=pid,
                field="brand",
                value=str(product["brand"])
            ))

        if product.get("rating") is not None:
            try:
                rat_val = float(product["rating"])
                if rat_val > 0:
                    items.append(EvidenceItem(
                        source_type=src_type,
                        source_id=pid,
                        field="rating",
                        value=f"{rat_val:.1f} / 5.0"
                    ))
            except (ValueError, TypeError):
                pass

        # Check attributes
        attrs = product.get("attributes", {})
        if isinstance(attrs, dict):
            for req in requested_fields:
                req_lower = req.lower()
                req_norm = req_lower.replace("_", " ").replace("-", " ")
                if req_lower in attrs:
                    items.append(EvidenceItem(
                        source_type=src_type,
                        source_id=pid,
                        field=req_lower,
                        value=attrs[req_lower]
                    ))
                else:
                    # Check for attribute word boundary match (e.g. 'ram' matches 'ram_size', 'battery' matches 'battery_life')
                    for k, v in attrs.items():
                        k_norm = k.lower().replace("_", " ").replace("-", " ")
                        if (
                            re.search(r'\b' + re.escape(req_norm) + r'\b', k_norm) or
                            re.search(r'\b' + re.escape(k_norm) + r'\b', req_norm)
                        ):
                            items.append(EvidenceItem(
                                source_type=src_type,
                                source_id=pid,
                                field=k,
                                value=v
                            ))
                            break

        return items

    @staticmethod
    def extract_policy_evidence(section_id: str, field: str, matched_text: str) -> EvidenceItem:
        return EvidenceItem(
            source_type="policy",
            source_id=section_id,
            field=field,
            value=matched_text
        )

evidence_checker = EvidenceChecker()
