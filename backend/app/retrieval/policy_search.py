import re
from typing import List, Tuple, Optional, Any
from app.ingestion.policy_loader import policy_loader, PolicySection

POLICY_TOPIC_KEYWORDS = {
    "RETURNS": ["return", "returns", "exchange", "refund", "refunds", "cancel", "cancellation", "replace", "replacement", "final sale", "hygiene", "return window"],
    "SHIPPING": ["shipping", "ship", "delivery", "delivered", "deliver", "delivering", "dispatch", "courier", "express", "standard", "pincode", "pin code", "fee", "charges", "rates", "free shipping", "timeline", "shipment"],
    "WARRANTY": ["warranty", "guarantee", "defect", "defects", "hardware", "liquid damage", "physical drop", "invoice", "claim", "repair"],
    "STOCK": ["stock", "inventory", "stock status", "in stock", "low stock", "units left", "stock accuracy"],
    "PRICE": ["price policy", "mrp", "checkout price", "hidden fees", "unknown fees", "final price"],
    "UNCERTAINTY": ["not specify", "doesn't specify", "catalogue doesn't contain", "why can't you answer", "missing answer", "say when", "uncertainty"],
    "COMPARISONS": ["product comparisons", "compare only fields", "missing for either item"],
    "FEEDBACK": ["customer feedback", "feedback change", "review overwrite", "feedback review"],
    "PROVENANCE": ["synthetic", "demo products", "real products", "real brand", "test data", "test fixture", "real listings", "నిజమైన ఉత్పత్తుల"],
    "CITATIONS": ["citation", "citations", "how should product-specific", "evidenced", "show the evidence", "cite"]
}

class PolicySearchEngine:
    """Retrieves grounded policy sections strictly matching shopper policy questions."""

    @staticmethod
    def detect_policy_topic(query: str) -> Optional[str]:
        q_lower = query.lower()
        topic_scores = {topic: 0 for topic in POLICY_TOPIC_KEYWORDS}

        for topic, keywords in POLICY_TOPIC_KEYWORDS.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', q_lower):
                    topic_scores[topic] += 1

        best_topic = max(topic_scores, key=topic_scores.get)
        if topic_scores[best_topic] > 0:
            return best_topic
        return None

    def search(self, query: str) -> List[Tuple[PolicySection, float]]:
        """Searches policy document sections based on topic detection and keyword overlap."""
        if not policy_loader.is_ready:
            policy_loader.load_from_database()
        if not policy_loader.is_ready:
            return []

        q_lower = query.lower()
        topic = self.detect_policy_topic(query)

        # A query must either trigger a policy topic or explicitly contain policy-intent words
        has_policy_intent = topic is not None or any(
            re.search(r'\b' + re.escape(w) + r'\b', q_lower)
            for w in ["policy", "policies", "terms", "coverage", "covered", "rule", "rules"]
        )

        if not has_policy_intent:
            return []

        matches: List[Tuple[PolicySection, float]] = []
        all_sections = policy_loader.get_all_sections()

        for sec in all_sections:
            score = 0.0
            # Direct topic match
            if topic and sec.topic == topic:
                score += 2.0

            # Content keyword matches with domain-specific terms (ignoring generic stop words)
            from app.retrieval.semantic_search import STOP_WORDS
            sec_text_lower = f"{sec.title} {sec.content}".lower()
            q_words = [
                w for w in re.findall(r'\b[a-zA-Z]{3,}\b', q_lower)
                if w not in STOP_WORDS and w not in ("under", "above", "have", "want", "need", "show", "tell", "cost", "price")
            ]
            matched_words = 0
            for w in q_words:
                if w in sec_text_lower:
                    matched_words += 1

            if q_words:
                score += (matched_words / len(q_words)) * 1.5

            if score > 0.8:
                matches.append((sec, score))

        # Sort descending by score
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

policy_search_engine = PolicySearchEngine()

