import re
import json
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field

class DatasetCategory(str, Enum):
    PRODUCT_CATALOGUE = "PRODUCT_CATALOGUE"
    MARKETPLACE_LISTINGS = "MARKETPLACE_LISTINGS"
    COMPETITOR_PRICING = "COMPETITOR_PRICING"
    CUSTOMER_REVIEWS = "CUSTOMER_REVIEWS"
    PRODUCT_SPECIFICATIONS = "PRODUCT_SPECIFICATIONS"
    POLICIES_AND_EVIDENCE = "POLICIES_AND_EVIDENCE"
    GENERIC_DATASET = "GENERIC_DATASET"
    UNRELATED_DATASET = "UNRELATED_DATASET"

class ColumnProfile(BaseModel):
    original_name: str
    inferred_type: str # string, numeric, date, url, boolean, dict, list
    sample_values: List[Any] = Field(default_factory=list)
    null_ratio: float = 0.0
    mapped_field: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""

class SchemaMappingResult(BaseModel):
    detected_category: DatasetCategory
    category_confidence: float
    column_profiles: Dict[str, ColumnProfile]
    field_mappings: Dict[str, str] # canonical_field -> original_column
    embedding_eligible: bool
    summary: str
    warnings: List[str] = Field(default_factory=list)

# Canonical aliases and semantic signals
CANONICAL_FIELD_ALIASES: Dict[str, List[str]] = {
    # Identifiers
    "product_id": [
        "product_id", "prod_id", "item_id", "sku", "item_code", "listing_id",
        "asin", "product_code", "model_number", "id", "pid", "code", "article_no",
        "inventory_id", "barcode", "upc", "ean", "warehouse_sku", "stock_code", "catalog_number"
    ],
    "customer_id": [
        "customer_id", "user_id", "shopper_id", "account_id", "buyer_id", "client_id"
    ],
    # Titles & Names
    "title": [
        "title", "product_name", "product_title", "item_name", "name", "headline",
        "listing_title", "product", "item", "article_title", "model_name", "item_description"
    ],
    # Descriptions & Content
    "description": [
        "description", "desc", "details", "summary", "about", "overview",
        "long_description", "short_description", "body", "product_details", "product_description"
    ],
    # Categories & Taxonomies
    "category": [
        "category", "category_name", "product_category", "cat", "cat_name", "department", "genre", "segment",
        "product_type", "type", "class", "family", "sub_category", "taxonomy", "categories", "main_category"
    ],
    # Monetary & Prices
    "price": [
        "price", "mrp", "current_price", "cost", "selling_price", "amount",
        "price_inr", "retail_price", "offer_price", "discounted_price", "final_price",
        "sale_price", "listing_price", "unit_price", "value", "inr", "wholesale_cost", "wholesale_price"
    ],
    "competitor_price": [
        "competitor_price", "observed_price", "market_price", "benchmark_price",
        "external_price", "other_price", "competitor_cost"
    ],
    "currency": [
        "currency", "currency_code", "curr", "fx", "denomination"
    ],
    # Inventory & Availability
    "stock_status": [
        "stock_status", "stock", "availability", "in_stock", "available",
        "quantity", "inventory", "stock_count", "in_stock_flag", "status"
    ],
    # Ratings & Scores
    "rating": [
        "rating", "customer_rating", "score", "stars", "avg_rating", "review_rating",
        "user_rating", "product_rating", "rank"
    ],
    "review_count": [
        "review_count", "num_reviews", "ratings_count", "reviews_total", "total_reviews"
    ],
    # Brands & Manufacturers
    "brand": [
        "brand", "brand_name", "manufacturer", "make", "vendor", "designer", "company", "supplier", "supplier_vendor"
    ],
    # Specifications & Attributes
    "attributes": [
        "attributes", "specs", "specifications", "features", "properties",
        "technical_details", "parameters", "metadata", "variants"
    ],
    # Marketplace & Seller
    "seller_name": [
        "seller", "seller_name", "merchant", "vendor_name", "retailer", "store", "dealer", "competitor", "competitor_name"
    ],
    "marketplace": [
        "marketplace", "platform", "channel", "source", "site", "portal"
    ],
    "source_url": [
        "source_url", "url", "link", "product_url", "web_link", "href", "listing_url"
    ],
    # Reviews
    "review_text": [
        "review_text", "review", "feedback", "customer_review", "review_content",
        "body", "testimonial", "opinion", "user_comment", "remarks"
    ],
    "reviewer_name": [
        "reviewer", "reviewer_name", "author", "customer_name", "user_name"
    ],
    # Dates
    "date": [
        "date", "review_date", "observation_date", "created_at", "updated_at",
        "timestamp", "published_date", "crawled_at"
    ],
    # Policies
    "policy_type": [
        "policy_type", "section", "topic", "category", "type", "policy_name"
    ],
    "policy_content": [
        "policy_content", "terms", "policy_text", "clauses", "rules", "guidelines",
        "warranty_terms", "return_policy", "shipping_policy"
    ]
}

class IntelligentSchemaMapper:
    """
    Analyzes arbitrary tabular or JSON dataset schemas, infers column types,
    maps columns semantically using names and sample values, and classifies
    the dataset into appropriate domain categories.
    """

    @staticmethod
    def infer_type(values: List[Any]) -> str:
        """Infers data type from a list of non-null sample values."""
        non_null = [v for v in values if v is not None and str(v).strip() != "" and str(v).lower() not in ("nan", "null", "none")]
        if not non_null:
            return "string"

        # Check for complex types (dict/list)
        if any(isinstance(v, (dict, list)) for v in non_null):
            return "dict" if any(isinstance(v, dict) for v in non_null) else "list"

        # Check for URL
        url_count = sum(1 for v in non_null if str(v).startswith("http://") or str(v).startswith("https://"))
        if url_count / len(non_null) > 0.6:
            return "url"

        # Check for date format
        date_pattern = re.compile(r'^\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4}')
        date_count = sum(1 for v in non_null if date_pattern.match(str(v).strip()))
        if date_count / len(non_null) > 0.6:
            return "date"

        # Check for numeric or currency strings
        numeric_count = 0
        for v in non_null:
            if isinstance(v, (int, float)):
                numeric_count += 1
            else:
                s = re.sub(r'[₹$€£,]', '', str(v)).strip()
                try:
                    float(s)
                    numeric_count += 1
                except ValueError:
                    pass
        if numeric_count / len(non_null) > 0.7:
            return "numeric"

        # Check for boolean
        bool_terms = {"true", "false", "yes", "no", "0", "1"}
        if all(str(v).strip().lower() in bool_terms for v in non_null):
            return "boolean"

        return "string"

    @classmethod
    def match_column_to_canonical(cls, col_name: str, sample_values: List[Any], col_type: str) -> Tuple[Optional[str], float, str]:
        """
        Calculates semantic match score between a column and canonical fields.
        Returns: (matched_canonical_field, confidence, reasoning)
        """
        clean_name = re.sub(r'[\s_\-\.]+', '_', col_name.strip().lower())

        best_field: Optional[str] = None
        best_score: float = 0.0
        best_reasoning: str = ""

        for canonical, aliases in CANONICAL_FIELD_ALIASES.items():
            score = 0.0
            reasoning_parts = []

            # Exact name match
            if clean_name in aliases:
                score += 0.8
                reasoning_parts.append(f"Direct alias match with '{clean_name}'")
            elif any(alias in clean_name for alias in aliases):
                score += 0.5
                reasoning_parts.append(f"Partial alias match in '{clean_name}'")

            # Value-based validation and reinforcement
            if canonical in ("price", "competitor_price"):
                if col_type == "numeric":
                    score += 0.2
                    reasoning_parts.append("Numeric value aligns with price")
                elif any(re.search(r'[₹$€£]', str(v)) for v in sample_values):
                    score += 0.3
                    reasoning_parts.append("Currency symbol found in sample values")

            elif canonical == "rating":
                if col_type == "numeric":
                    # Check if numbers are on typical rating scale (1-5 or 1-10)
                    nums = []
                    for v in sample_values:
                        try:
                            nums.append(float(v))
                        except (ValueError, TypeError):
                            pass
                    if nums and all(0.0 <= n <= 10.0 for n in nums):
                        score += 0.25
                        reasoning_parts.append("Numeric range 0-10 aligns with rating")

            elif canonical == "review_text":
                # Check average text length
                text_lengths = [len(str(v).split()) for v in sample_values if v is not None]
                if text_lengths and (sum(text_lengths) / len(text_lengths)) > 5:
                    score += 0.3
                    reasoning_parts.append("Multi-word text samples align with review text")

            elif canonical == "source_url":
                if col_type == "url":
                    score += 0.4
                    reasoning_parts.append("Valid URL values confirmed")

            elif canonical == "attributes":
                if col_type in ("dict", "list"):
                    score += 0.4
                    reasoning_parts.append("Structured dictionary/list values confirmed")

            if score > best_score:
                best_score = min(1.0, score)
                best_field = canonical
                best_reasoning = "; ".join(reasoning_parts)

        return (best_field, best_score, best_reasoning) if best_score >= 0.45 else (None, 0.0, "No confident match")

    @classmethod
    def profile_and_map(
        cls,
        records: List[Dict[str, Any]],
        owner_mapping_overrides: Optional[Dict[str, str]] = None,
        category_override: Optional[DatasetCategory] = None
    ) -> SchemaMappingResult:
        """
        Profiles dataset records, maps columns to canonical fields,
        infers the domain category, and evaluates embedding eligibility.
        """
        if not records:
            return SchemaMappingResult(
                detected_category=DatasetCategory.UNRELATED_DATASET,
                category_confidence=0.0,
                column_profiles={},
                field_mappings={},
                embedding_eligible=False,
                summary="Empty dataset with 0 records",
                warnings=["Uploaded dataset contains no data rows"]
            )

        # 1. Collect all distinct columns across sample records
        sample_size = min(len(records), 100)
        sample_records = records[:sample_size]

        all_cols: List[str] = []
        for r in sample_records:
            for k in r.keys():
                if k not in all_cols:
                    all_cols.append(k)

        column_profiles: Dict[str, ColumnProfile] = {}
        field_mappings: Dict[str, str] = {} # canonical -> original_name
        reverse_mappings: Dict[str, str] = {} # original_name -> canonical

        for col in all_cols:
            col_samples = [r.get(col) for r in sample_records if r.get(col) is not None]
            null_count = sum(1 for r in sample_records if r.get(col) is None or str(r.get(col)).strip() == "")
            null_ratio = null_count / sample_size
            col_type = cls.infer_type(col_samples)

            matched_canonical, confidence, reasoning = cls.match_column_to_canonical(col, col_samples[:10], col_type)

            # Apply owner overrides if specified
            if owner_mapping_overrides and col in owner_mapping_overrides:
                matched_canonical = owner_mapping_overrides[col]
                confidence = 1.0
                reasoning = "Owner explicit override"
            elif owner_mapping_overrides and col.lower() in owner_mapping_overrides:
                matched_canonical = owner_mapping_overrides[col.lower()]
                confidence = 1.0
                reasoning = "Owner explicit override"

            column_profiles[col] = ColumnProfile(
                original_name=col,
                inferred_type=col_type,
                sample_values=col_samples[:5],
                null_ratio=round(null_ratio, 3),
                mapped_field=matched_canonical,
                confidence=round(confidence, 2),
                reasoning=reasoning
            )

            if matched_canonical and matched_canonical not in field_mappings:
                field_mappings[matched_canonical] = col
                reverse_mappings[col] = matched_canonical

        # 2. Dataset Category Detection
        detected_category, cat_confidence, cat_reason = cls._detect_dataset_category(field_mappings, column_profiles, sample_records)

        if category_override:
            detected_category = category_override
            cat_confidence = 1.0
            cat_reason = f"Owner override to {category_override.value}"

        # 3. Embedding eligibility: Requires meaningful textual content (title, description, review_text, content)
        has_text_content = any(
            f in field_mappings for f in ["title", "description", "review_text", "policy_content", "attributes"]
        ) or any(
            p.inferred_type == "string" and p.null_ratio < 0.8
            for p in column_profiles.values()
        )
        embedding_eligible = has_text_content and detected_category != DatasetCategory.UNRELATED_DATASET

        warnings: List[str] = []
        if detected_category == DatasetCategory.UNRELATED_DATASET:
            warnings.append("Dataset does not exhibit standard retail, product, listing, review, or policy domain signals.")
        if not field_mappings.get("product_id") and not field_mappings.get("title") and detected_category == DatasetCategory.PRODUCT_CATALOGUE:
            warnings.append("No explicit product ID or title column found; fallback record identifiers will be assigned.")

        summary = f"Detected {detected_category.value} (Confidence: {cat_confidence*100:.1f}%). {cat_reason}"

        return SchemaMappingResult(
            detected_category=detected_category,
            category_confidence=round(cat_confidence, 2),
            column_profiles=column_profiles,
            field_mappings=field_mappings,
            embedding_eligible=embedding_eligible,
            summary=summary,
            warnings=warnings
        )

    @staticmethod
    def _detect_dataset_category(
        field_mappings: Dict[str, str],
        profiles: Dict[str, ColumnProfile],
        sample_records: List[Dict[str, Any]]
    ) -> Tuple[DatasetCategory, float, str]:
        """Classifies the dataset category based on mapped fields and column distributions."""
        mapped_keys = set(field_mappings.keys())
        orig_cols_lower = [p.original_name.lower() for p in profiles.values()]

        # Explicit Unrelated Domain Filter (medical, clinical, server/sys logs, sports telemetry)
        unrelated_signals = {
            "patient", "systolic", "diastolic", "glucose", "diagnosis", "blood_pressure",
            "cholesterol", "symptom", "dosage", "prescription", "heart_rate", "biopsy",
            "server_ip", "stacktrace", "cpu_usage", "touchdown", "quarterback", "innings"
        }
        all_col_words = set()
        for col_name in orig_cols_lower:
            all_col_words.update(re.findall(r'[a-zA-Z]+', col_name))

        if any(w in unrelated_signals for w in all_col_words):
            return DatasetCategory.UNRELATED_DATASET, 0.95, "Explicitly non-commerce/unrelated domain signals detected (e.g. medical or server logs)."

        # Category F: Policies and Evidence (must not be confused with products that have warranty attributes or specs)
        has_product_identifiers = ("title" in mapped_keys or "product_id" in mapped_keys) and "price" in mapped_keys
        if not has_product_identifiers:
            if "policy_content" in mapped_keys or "policy_type" in mapped_keys or any(any(w in col for w in ("policy", "policy_terms", "terms_and_conditions", "policy_text", "clauses", "shipping_rule")) for col in orig_cols_lower):
                return DatasetCategory.POLICIES_AND_EVIDENCE, 0.92, "Identified policy clauses, terms, or evidence documents."

        # Category D: Customer Reviews
        if "review_text" in mapped_keys or ("rating" in mapped_keys and "reviewer_name" in mapped_keys):
            return DatasetCategory.CUSTOMER_REVIEWS, 0.95, "Identified customer review and feedback columns."

        # Category C: Competitor Pricing & Market Research
        if "competitor_price" in mapped_keys or ("price" in mapped_keys and any("competitor" in col or "observed" in col for col in orig_cols_lower)):
            return DatasetCategory.COMPETITOR_PRICING, 0.92, "Identified competitor pricing or market observation fields."

        # Category B: Marketplace & Seller Listings
        if ("marketplace" in mapped_keys or "seller_name" in mapped_keys or "source_url" in mapped_keys) and "price" in mapped_keys:
            return DatasetCategory.MARKETPLACE_LISTINGS, 0.88, "Identified multi-seller or marketplace listing attributes."

        # Category A: Product Catalogues (both product_id and title, or either + retail price/stock/category)
        if ("title" in mapped_keys and "product_id" in mapped_keys) or (
            ("title" in mapped_keys or "product_id" in mapped_keys) and ("price" in mapped_keys or "stock_status" in mapped_keys or "category" in mapped_keys)
        ):
            return DatasetCategory.PRODUCT_CATALOGUE, 0.95, "Identified core retail product catalogue attributes."

        # Category E: Product Specifications & Comparisons
        if "attributes" in mapped_keys and ("title" in mapped_keys or "product_id" in mapped_keys) and "price" not in mapped_keys:
            return DatasetCategory.PRODUCT_SPECIFICATIONS, 0.85, "Identified technical specification attributes without catalog pricing."

        # Category G: Generic Structured Data (must exhibit retail/commerce/entity signals)
        retail_signals = {
            "product", "item", "sku", "store", "shop", "price", "cost", "brand", "vendor",
            "seller", "inventory", "stock", "warehouse", "location", "tax", "fee", "shipping",
            "delivery", "packaging", "order", "catalog", "catalogue", "review", "policy", "rating",
            "title", "name", "description", "category", "attribute", "spec", "model", "amount", "unit"
        }
        has_retail_signal = any(w in retail_signals for w in all_col_words) or len(mapped_keys) > 0
        if has_retail_signal and len(profiles) >= 2:
            return DatasetCategory.GENERIC_DATASET, 0.65, "Relevant structured dataset without rigid catalogue structure."

        # Unrelated
        return DatasetCategory.UNRELATED_DATASET, 0.20, "No commerce, product, policy, or review domain signals detected."

schema_mapper = IntelligentSchemaMapper()

