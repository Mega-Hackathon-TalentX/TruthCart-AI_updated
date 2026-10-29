import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

from app.core.config import settings
from app.core.logging_config import SafeLogger
from app.ingestion.data_validator import DataValidator

# Canonical column mapping fallbacks
DEFAULT_COLUMN_MAPPINGS = {
    "product_id": ["product_id", "id", "sku", "item_id", "prod_id", "item_code", "listing_id", "record_id", "asin", "code"],
    "title": ["title", "name", "product_name", "item_name", "headline", "item_heading", "product_title", "listing_title"],
    "description": ["description", "desc", "details", "summary", "about", "technical_details", "product_details", "body"],
    "category": ["category", "product_category", "cat", "department", "subcategory", "product_type"],
    "price": ["price", "mrp", "current_price", "cost", "selling_price", "price_inr", "selling_rate", "retail_price"],
    "stock_status": ["stock_status", "stock", "availability", "in_stock", "available", "inventory_status", "stock_quantity"],
    "rating": ["rating", "customer_rating", "score", "stars", "avg_rating", "review_rating"],
    "brand": ["brand", "brand_name", "manufacturer", "make", "vendor"],
    "attributes": ["attributes", "specs", "specifications", "features", "properties"]
}

class CatalogueLoader:
    """Ingests and validates product catalogues from CSV and JSON formats."""

    def __init__(self):
        self.products: Dict[str, Dict[str, Any]] = {}
        self.records_loaded: int = 0
        self.records_rejected: int = 0
        self.duplicate_records: int = 0
        self.missing_fields_count: int = 0
        self.is_official: bool = False
        self.is_synthetic_fixture: bool = False
        self.source_path: Optional[str] = None
        self.is_ready: bool = False

    def clear(self) -> None:
        self.products.clear()
        self.records_loaded = 0
        self.records_rejected = 0
        self.duplicate_records = 0
        self.missing_fields_count = 0
        self.is_official = False
        self.is_synthetic_fixture = False
        self.source_path = None
        self.is_ready = False

    @property
    def catalogue_version(self) -> str:
        if self.source_path and "(" in self.source_path and ")" in self.source_path:
            return self.source_path.split("(")[-1].rstrip(")")
        return "v1.0.0"

    def _resolve_headers(self, columns: List[str], custom_mapping: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Resolves file columns to canonical keys."""
        mapping = {}
        cols_lower = {str(c).strip().lower(): c for c in columns}

        if custom_mapping:
            for canonical, col_name in custom_mapping.items():
                if col_name in columns:
                    mapping[canonical] = col_name
                elif col_name.lower() in cols_lower:
                    mapping[canonical] = cols_lower[col_name.lower()]

        for canonical, candidates in DEFAULT_COLUMN_MAPPINGS.items():
            if canonical in mapping:
                continue
            for cand in candidates:
                if cand in cols_lower:
                    mapping[canonical] = cols_lower[cand]
                    break
        return mapping

    def load_from_records(
        self,
        records: List[Dict[str, Any]],
        is_official: bool,
        is_synthetic: bool,
        source_name: str,
        custom_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Loads records from list of dicts with validation and metrics tracking."""
        self.clear()
        self.is_official = is_official
        self.is_synthetic_fixture = is_synthetic
        self.source_path = source_name

        if not records:
            self.is_ready = False
            return self.get_status()

        # Build column mapping from keys of first record
        keys = list(records[0].keys())
        header_map = self._resolve_headers(keys, custom_mapping)

        for raw_item in records:
            # Remap keys to canonical names
            mapped = {}
            for canonical, file_key in header_map.items():
                if file_key in raw_item:
                    mapped[canonical] = raw_item[file_key]
            
            # Carry over any extra fields into attributes if not already present
            attrs = mapped.get("attributes")
            if not isinstance(attrs, dict):
                attrs = DataValidator.parse_attributes(attrs)
            for k, v in raw_item.items():
                if k not in header_map.values() and k not in mapped and k not in ("id", "catalogue_id", "is_archived", "created_at", "updated_at"):
                    attrs[str(k).strip().lower()] = v
            if mapped.get("brand") and "brand" not in attrs:
                attrs["brand"] = mapped["brand"]
            mapped["attributes"] = attrs

            valid, reason, normalized = DataValidator.validate_record(mapped)
            if not valid:
                self.records_rejected += 1
                if "Missing" in str(reason):
                    self.missing_fields_count += 1
                continue

            # Ensure brand and details are populated on normalized product
            if mapped.get("brand") and not normalized.get("brand"):
                normalized["brand"] = str(mapped["brand"]).strip()
            elif normalized.get("attributes", {}).get("brand") and not normalized.get("brand"):
                normalized["brand"] = str(normalized["attributes"]["brand"]).strip()

            if not normalized.get("description") and normalized.get("attributes", {}).get("details"):
                normalized["description"] = str(normalized["attributes"]["details"]).strip()

            prod_id = normalized["product_id"]
            if prod_id in self.products:
                self.duplicate_records += 1
                # Preserve first occurrence to prevent duplicate overwriting
                continue

            self.products[prod_id] = normalized
            self.records_loaded += 1

        self.is_ready = self.records_loaded > 0
        SafeLogger.info(
            f"Catalogue loaded from {source_name}: {self.records_loaded} valid, "
            f"{self.records_rejected} rejected, {self.duplicate_records} duplicates."
        )
        return self.get_status()

    def load_file(self, file_path: Path, is_official: bool = False, is_synthetic: bool = False, custom_mapping: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Loads catalogue from a JSON or CSV file path."""
        if not file_path.exists():
            SafeLogger.warning(f"Catalogue file not found at: {file_path}")
            return self.get_status()

        suffix = file_path.suffix.lower()
        records: List[Dict[str, Any]] = []

        try:
            if suffix == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict):
                        # Some datasets wrap lists in a key e.g. {"products": [...]}
                        for v in data.values():
                            if isinstance(v, list):
                                records = v
                                break
            elif suffix in (".csv", ".tsv"):
                sep = "\t" if suffix == ".tsv" else ","
                df = pd.read_csv(file_path, sep=sep, dtype=object)
                records = df.to_dict(orient="records")
            else:
                SafeLogger.error(f"Unsupported catalogue file format: {suffix}")
                return self.get_status()
        except Exception as e:
            SafeLogger.error(f"Error parsing catalogue file {file_path.name}: {str(e)}")
            return self.get_status()

        return self.load_from_records(
            records=records,
            is_official=is_official,
            is_synthetic=is_synthetic,
            source_name=file_path.name,
            custom_mapping=custom_mapping
        )

    def load_default_catalogue(self, force_fixtures: bool = False) -> Dict[str, Any]:
        """
        Loads catalogue following strict organiser rules:
        1. Checks official products directory for CSV or JSON.
        2. If official file exists, loads it (is_official=True).
        3. If official does NOT exist:
           - If force_fixtures OR settings.LOAD_SYNTHETIC_DEV_DATA_WHEN_EMPTY is True, loads dev fixtures (is_synthetic=True).
           - Otherwise, leaves state as NOT READY ("Awaiting organiser catalogue").
        """
        if force_fixtures:
            dev_dir = settings.get_dev_fixtures_path()
            fixture_json = dev_dir / "sample_catalogue.json"
            if fixture_json.exists():
                SafeLogger.info("Loading isolated synthetic development fixtures (forced).")
                return self.load_file(fixture_json, is_official=False, is_synthetic=True)

        # 1. Check database for active catalogue first
        try:
            from app.db.database import db
            db.init_db()
            active_cat = db.get_active_catalogue()
            if active_cat:
                SafeLogger.info(f"Loading active catalogue from database: {active_cat['name']} ({active_cat['version']})")
                return self.load_from_database()
        except Exception as e:
            SafeLogger.warning(f"Could not load catalogue from database: {str(e)}")

        official_dir = settings.get_products_path()
        official_files = []
        if official_dir.exists():
            for ext in ("*.csv", "*.json"):
                for p in official_dir.glob(ext):
                    if not p.name.lower().startswith("readme") and not p.name.startswith("."):
                        official_files.append(p)

        # 2. Load official file if present
        if official_files:
            target_file = official_files[0]
            SafeLogger.info(f"Official organiser catalogue detected: {target_file.name}")
            return self.load_file(target_file, is_official=True, is_synthetic=False)

        # 3. Check if synthetic fixtures should be loaded for testing/dev
        if settings.LOAD_SYNTHETIC_DEV_DATA_WHEN_EMPTY:
            dev_dir = settings.get_dev_fixtures_path()
            fixture_json = dev_dir / "sample_catalogue.json"
            if fixture_json.exists():
                SafeLogger.info("Loading isolated synthetic development fixtures.")
                return self.load_file(fixture_json, is_official=False, is_synthetic=True)

        # 4. Official catalogue is not available
        self.clear()
        SafeLogger.info("Official organiser catalogue not yet provided. System in 'Awaiting organiser catalogue' status.")
        return self.get_status()

    def load_from_database(self) -> Dict[str, Any]:
        """Loads active catalogue products directly from persistent database."""
        from app.db.database import db
        active_cat = db.get_active_catalogue()
        if not active_cat:
            self.clear()
            return self.get_status()

        products = db.get_active_products()
        source_name = f"{active_cat['name']} ({active_cat['version']})"
        return self.load_from_records(
            records=products,
            is_official=True,
            is_synthetic=False,
            source_name=source_name
        )

    def get_status(self) -> Dict[str, Any]:
        categories = sorted(list({p["category"] for p in self.products.values() if p.get("category")}))
        if self.is_ready:
            status_text = "Official Catalogue Active" if self.is_official else "Development Fixture Loaded (Synthetic)"
        else:
            status_text = "Awaiting Organiser Catalogue"

        return {
            "status": status_text,
            "is_ready": self.is_ready,
            "is_official": self.is_official,
            "is_synthetic_fixture": self.is_synthetic_fixture,
            "records_loaded": self.records_loaded,
            "records_rejected": self.records_rejected,
            "duplicate_records": self.duplicate_records,
            "missing_fields_count": self.missing_fields_count,
            "categories": categories,
            "total_active_products": len(self.products),
            "data_source_path": self.source_path
        }

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Exact lookup by product ID with case-insensitive fallback."""
        if not self.is_ready:
            self.load_from_database()
        pid_clean = str(product_id).strip()
        if pid_clean in self.products:
            return self.products[pid_clean]
        # Case-insensitive in-memory lookup
        pid_upper = pid_clean.upper()
        for k, v in self.products.items():
            if k.upper() == pid_upper:
                return v
        try:
            from app.db.database import db
            prod = db.get_product_by_id(pid_clean)
            if prod:
                return prod
        except Exception:
            pass
        return None

    def get_all_products(self) -> List[Dict[str, Any]]:
        if not self.is_ready:
            self.load_from_database()
        return list(self.products.values())


catalogue_loader = CatalogueLoader()
