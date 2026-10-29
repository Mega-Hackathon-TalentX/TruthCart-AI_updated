import io
import re
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union
import pandas as pd

from app.core.logging_config import SafeLogger
from app.ingestion.schema_mapper import (
    schema_mapper,
    DatasetCategory,
    SchemaMappingResult,
    ColumnProfile
)
from app.ingestion.data_validator import DataValidator
from app.retrieval.adaptive_embeddings import embedding_manager

class UniversalDatasetIngestor:
    """
    Universal domain-aware ingestion pipeline supporting CSV, TSV, JSON, JSONL, XLS, XLSX.
    Executes schema profiling, category detection, semantic column mapping,
    data-quality validation, and adaptive embedding generation.
    """

    MAX_SAFE_ROWS = 50000

    @classmethod
    def sanitize_cell_value(cls, val: Any) -> Any:
        """Sanitizes potential spreadsheet formula injection risks (=, +, -, @)."""
        if isinstance(val, str) and len(val) > 0:
            if val[0] in ('=', '+', '-', '@') and not re.match(r'^[\+\-]?\d+(\.\d+)?$', val.strip()):
                return "'" + val
        return val

    @classmethod
    def parse_file(
        cls,
        content: bytes,
        filename: str,
        sheet_name: Optional[Union[str, int]] = None
    ) -> Tuple[List[Dict[str, Any]], List[str], str]:
        """
        Parses uploaded file content with encoding auto-detection and multi-sheet support.
        Returns:
            records: List of parsed row dicts
            available_sheets: List of sheet names (for Excel)
            detected_format: String representation of format
        """
        suffix = filename.split(".")[-1].lower() if "." in filename else ""
        records: List[Dict[str, Any]] = []
        available_sheets: List[str] = []

        if suffix not in ("csv", "tsv", "json", "jsonl", "xls", "xlsx"):
            raise ValueError(f"Unsupported file format '.{suffix}'. Supported: CSV, TSV, JSON, JSONL, XLS, XLSX")

        if not content or len(content.strip()) == 0:
            raise ValueError("File is empty or contains no readable data.")

        # 1. JSON / JSONL parsing
        if suffix in ("json", "jsonl"):
            # Try utf-8 then latin-1
            text = ""
            for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
                try:
                    text = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if not text:
                raise ValueError("Could not decode file content with UTF-8 or standard encodings.")

            # Try parsing JSONL (line-by-line JSON)
            if suffix == "jsonl" or "\n{" in text or "\r\n{" in text:
                jsonl_records = []
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                is_jsonl = True
                for line in lines:
                    try:
                        parsed_line = json.loads(line)
                        if isinstance(parsed_line, dict):
                            jsonl_records.append(parsed_line)
                    except json.JSONDecodeError:
                        is_jsonl = False
                        break
                if is_jsonl and jsonl_records:
                    records = jsonl_records

            # Standard JSON array / object parsing
            if not records:
                try:
                    parsed_json = json.loads(text)
                    if isinstance(parsed_json, list):
                        records = [r for r in parsed_json if isinstance(r, dict)]
                    elif isinstance(parsed_json, dict):
                        # Find list value in dictionary
                        for val in parsed_json.values():
                            if isinstance(val, list):
                                records = [r for r in val if isinstance(r, dict)]
                                break
                        if not records:
                            # Single-object record
                            records = [parsed_json]
                except json.JSONDecodeError as e:
                    raise ValueError(f"Malformed JSON content: {str(e)}")

            detected_format = "JSONL" if suffix == "jsonl" else "JSON"

        # 2. Excel (XLS, XLSX) parsing
        elif suffix in ("xls", "xlsx"):
            try:
                excel_file = pd.ExcelFile(io.BytesIO(content))
                available_sheets = excel_file.sheet_names
                target_sheet = sheet_name if sheet_name in available_sheets else (available_sheets[0] if available_sheets else 0)
                df = pd.read_excel(excel_file, sheet_name=target_sheet, dtype=object)
                df = df.where(pd.notnull(df), None)
                records = df.to_dict(orient="records")
                detected_format = f"Excel ({suffix.upper()})"
            except Exception as e:
                raise ValueError(f"Failed to parse Excel workbook: {str(e)}")

        # 3. CSV / TSV parsing
        else:
            sep = "\t" if suffix == "tsv" else ","
            for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
                try:
                    df = pd.read_csv(io.BytesIO(content), sep=sep, encoding=enc, dtype=object)
                    df = df.where(pd.notnull(df), None)
                    records = df.to_dict(orient="records")
                    break
                except Exception:
                    continue
            if not records and len(content) > 0:
                raise ValueError(f"Could not parse tabular {suffix.upper()} file. Please check delimiter and row consistency.")
            detected_format = "TSV" if suffix == "tsv" else "CSV"

        # Sanitize values
        sanitized_records = []
        for r in records[:cls.MAX_SAFE_ROWS]:
            clean_r = {}
            for k, v in r.items():
                if k is not None:
                    clean_r[str(k).strip()] = cls.sanitize_cell_value(v)
            if any(v is not None and str(v).strip() != "" for v in clean_r.values()):
                sanitized_records.append(clean_r)

        return sanitized_records, available_sheets, detected_format

    @classmethod
    def profile_and_validate(
        cls,
        records: List[Dict[str, Any]],
        owner_mappings: Optional[Dict[str, str]] = None,
        category_override: Optional[str] = None
    ) -> Tuple[SchemaMappingResult, List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        """
        Profiles the dataset schema, detects the domain category,
        and validates/normalizes all records.
        Returns:
            mapping_result: SchemaMappingResult
            valid_records: List of normalized records
            errors: List of row validation errors
            warnings: List of quality warnings
        """
        cat_enum = None
        if category_override:
            try:
                cat_enum = DatasetCategory(category_override)
            except ValueError:
                cat_enum = None

        mapping_result = schema_mapper.profile_and_map(
            records=records,
            owner_mapping_overrides=owner_mappings,
            category_override=cat_enum
        )

        valid_records: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        warnings: List[str] = list(mapping_result.warnings)
        seen_ids = set()

        category = mapping_result.detected_category
        field_mappings = mapping_result.field_mappings

        for idx, raw_row in enumerate(records, start=1):
            valid, reason, normalized = DataValidator.validate_flexible_record(
                raw=raw_row,
                category=category,
                field_mappings=field_mappings,
                row_idx=idx
            )
            if not valid or not normalized:
                errors.append({
                    "row": idx,
                    "record_id": raw_row.get("product_id") or raw_row.get("id") or f"Row {idx}",
                    "issue": reason or "Failed validation"
                })
                continue

            rec_id = normalized.get("record_id") or normalized.get("product_id") or f"ROW-{idx}"
            if rec_id in seen_ids:
                warnings.append(f"Row {idx}: Duplicate record identifier '{rec_id}' detected. Later occurrence skipped.")
                continue
            seen_ids.add(rec_id)

            valid_records.append(normalized)

        return mapping_result, valid_records, errors, warnings

universal_ingestor = UniversalDatasetIngestor()

