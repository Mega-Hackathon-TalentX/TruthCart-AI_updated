from typing import Optional, List, Dict, Any

class RefusalHandler:
    """Generates polite, honest, transparent refusals when evidence is insufficient or absent."""

    @staticmethod
    def create_out_of_catalogue_refusal(query: str, search_term: Optional[str] = None) -> Dict[str, str]:
        item_desc = f" '{search_term}'" if search_term else ""
        return {
            "reason": f"Product{item_desc} not found in the currently loaded catalogue snapshot.",
            "response_text": (
                f"I couldn't find{item_desc} in the available product catalogue snapshot, "
                f"so I cannot confirm its price, specifications, or availability. "
                f"Please verify the product name or ID, or try searching for another item."
            )
        }

    @staticmethod
    def create_unsupported_attribute_refusal(product_title: str, product_id: str, missing_attribute: str) -> Dict[str, str]:
        return {
            "reason": f"Attribute '{missing_attribute}' is not documented for {product_id}.",
            "response_text": (
                f"The catalogue record for {product_title} [PRODUCT:{product_id}] "
                f"does not specify information regarding '{missing_attribute}'. "
                f"Please note that a missing field does not prove the product lacks this feature, "
                f"but indicates it is unrecorded in our official dataset. "
                f"To ensure 100% accuracy, I will not assume or fabricate unverified specifications."
            )
        }

    @staticmethod
    def create_unsupported_policy_refusal(topic: str, specific_query: str) -> Dict[str, str]:
        return {
            "reason": f"Policy document does not contain verified terms for '{specific_query}'.",
            "response_text": (
                f"The official store policy does not contain information regarding {specific_query}. "
                f"I cannot provide unverified terms, conditions, or guarantees outside the official documentation."
            )
        }

    @staticmethod
    def create_empty_catalogue_refusal() -> Dict[str, str]:
        return {
            "reason": "Official catalogue data is currently awaiting ingestion.",
            "response_text": (
                "The official product catalogue is currently awaiting ingestion. "
                "No live product facts or prices can be verified until the dataset is loaded."
            )
        }

    @staticmethod
    def create_prompt_injection_refusal() -> Dict[str, str]:
        return {
            "reason": "Security safeguard: Attempt to override evidence rules or bypass catalogue truth was blocked.",
            "response_text": (
                "I must decline this request. TruthCart AI operates strictly within verified catalogue "
                "and policy evidence and cannot override its evidence-verification safeguards."
            )
        }

refusal_handler = RefusalHandler()
