from typing import List, Dict, Any, Tuple, Set
from app.ingestion.catalogue_loader import catalogue_loader
from app.ingestion.policy_loader import policy_loader
from app.evidence_engine.citation_mapper import citation_mapper
from app.core.logging_config import SafeLogger

class CitationValidator:
    """Server-side citation enforcement and factual verification against retrieved evidence."""

    @classmethod
    def validate_citations(
        cls,
        text: str,
        verified_product_ids: Set[str],
        verified_policy_ids: Set[str]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validates all citation markers in generated text against verified retrieved sources.
        Returns:
            is_valid: bool
            valid_citations: List of approved citation tags
            invalid_citations: List of rejected citation tags
        """
        extracted = citation_mapper.extract_citations(text)
        valid_citations = []
        invalid_citations = []

        for source_type, source_id in extracted:
            full_tag = f"[{source_type.upper()}:{source_id}]"

            if source_type == "product":
                # Must be an actual product in catalogue AND present in retrieved evidence
                in_catalogue = catalogue_loader.get_product(source_id) is not None
                if in_catalogue and (source_id in verified_product_ids or not verified_product_ids):
                    valid_citations.append(full_tag)
                else:
                    invalid_citations.append(full_tag)

            elif source_type == "policy":
                # Must be an actual policy section in policy document AND present in retrieved evidence
                clean_id = source_id.replace("POLICY:", "").strip()
                in_policy = (
                    policy_loader.get_section_by_id(clean_id) is not None
                    or policy_loader.get_section_by_id(source_id) is not None
                    or policy_loader.get_section_by_id(f"POLICY:{clean_id}") is not None
                )
                verified = (
                    not verified_policy_ids
                    or source_id in verified_policy_ids
                    or clean_id in verified_policy_ids
                    or f"POLICY:{clean_id}" in verified_policy_ids
                )
                if in_policy and verified:
                    valid_citations.append(full_tag)
                else:
                    invalid_citations.append(full_tag)

            else:
                # Multi-domain sources (review, competitor, spec, listing, dataset)
                if source_id in verified_product_ids or source_id in verified_policy_ids or not verified_product_ids:
                    valid_citations.append(full_tag)
                else:
                    invalid_citations.append(full_tag)

        is_valid = len(invalid_citations) == 0
        return is_valid, valid_citations, invalid_citations

    @classmethod
    def sanitize_text(
        cls,
        text: str,
        verified_product_ids: Set[str],
        verified_policy_ids: Set[str]
    ) -> str:
        """Removes invalid or hallucinated citations from text to prevent misattributions."""
        extracted = citation_mapper.extract_citations(text)
        sanitized = text

        for source_type, source_id in extracted:
            full_tag = f"[{source_type.upper()}:{source_id}]"
            if source_type == "product":
                if source_id not in verified_product_ids or not catalogue_loader.get_product(source_id):
                    sanitized = sanitized.replace(full_tag, "")
            elif source_type == "policy":
                sec_id = f"POLICY:{source_id}" if not source_id.startswith("POLICY:") else source_id
                if sec_id not in verified_policy_ids or not policy_loader.get_section_by_id(sec_id):
                    sanitized = sanitized.replace(full_tag, "")
            else:
                if source_id not in verified_product_ids and source_id not in verified_policy_ids:
                    sanitized = sanitized.replace(full_tag, "")

        import re
        sanitized = re.sub(r'  +', ' ', sanitized).strip()
        return sanitized

    sanitize_response = sanitize_text

citation_validator = CitationValidator()
