import re
import os
import time
import math
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Protocol
from abc import ABC, abstractmethod
import numpy as np

from app.core.config import settings
from app.core.logging_config import SafeLogger
from app.ingestion.schema_mapper import DatasetCategory

class DocumentBuilder:
    """
    Constructs semantic embedding documents dynamically based on the dataset category
    and available fields. Never invents missing facts.
    """

    @classmethod
    def build_embedding_text(cls, record: Dict[str, Any], category: Optional[str] = None) -> Optional[str]:
        cat = category or record.get("category_type") or DatasetCategory.PRODUCT_CATALOGUE.value
        parts: List[str] = []

        # CATEGORY A: PRODUCT CATALOGUE
        if cat == DatasetCategory.PRODUCT_CATALOGUE.value:
            title = record.get("title")
            brand = record.get("brand") or record.get("attributes", {}).get("brand")
            category_name = record.get("category")
            desc = record.get("description")
            specs = record.get("attributes", {})

            if title:
                parts.append(f"Product: {title}")
            if brand:
                parts.append(f"Brand: {brand}")
            if category_name and category_name != "General":
                parts.append(f"Category: {category_name}")
            if desc:
                parts.append(f"Description: {desc}")
            if specs and isinstance(specs, dict):
                spec_str = ", ".join(f"{k}: {v}" for k, v in specs.items() if k not in ("brand", "raw_record"))
                if spec_str:
                    parts.append(f"Specifications: {spec_str}")

        # CATEGORY B: MARKETPLACE & SELLER LISTINGS
        elif cat == DatasetCategory.MARKETPLACE_LISTINGS.value:
            title = record.get("title")
            brand = record.get("brand") or record.get("attributes", {}).get("brand") or record.get("attributes", {}).get("manufacturer")
            category_name = record.get("category") or record.get("attributes", {}).get("subcategory") or record.get("attributes", {}).get("category")
            desc = record.get("description") or record.get("attributes", {}).get("details") or record.get("attributes", {}).get("specifications") or record.get("attributes", {}).get("technical_details")
            seller = record.get("seller_name") or record.get("attributes", {}).get("seller_name")
            market = record.get("marketplace") or record.get("attributes", {}).get("marketplace")
            price = record.get("price")
            curr = record.get("currency", "INR")
            stock = record.get("stock_status")
            specs = record.get("attributes", {})

            if title:
                parts.append(f"Listing: {title}")
            if brand:
                parts.append(f"Brand: {brand}")
            if category_name and str(category_name).strip() not in ("General", "MARKETPLACE_LISTINGS"):
                parts.append(f"Category: {category_name}")
            if desc:
                parts.append(f"Description: {desc}")
            if market:
                parts.append(f"Marketplace: {market}")
            if seller:
                parts.append(f"Seller: {seller}")
            if price is not None and price > 0:
                parts.append(f"Price: {curr} {price:,.2f}")
            if stock:
                parts.append(f"Availability: {stock}")
            if specs and isinstance(specs, dict):
                spec_str = ", ".join(f"{k}: {v}" for k, v in specs.items() if k not in ("brand", "seller_name", "marketplace", "raw_record", "id", "catalogue_id", "is_archived", "created_at", "updated_at"))
                if spec_str:
                    parts.append(f"Specifications: {spec_str}")

        # CATEGORY C: COMPETITOR PRICING
        elif cat == DatasetCategory.COMPETITOR_PRICING.value:
            prod_ref = record.get("product_id") or record.get("title")
            comp = record.get("competitor_name")
            obs_price = record.get("observed_price")
            curr = record.get("currency", "INR")
            date = record.get("observation_date")

            if prod_ref:
                parts.append(f"Product Reference: {prod_ref}")
            if comp:
                parts.append(f"Competitor: {comp}")
            if obs_price is not None:
                parts.append(f"Observed Price: {curr} {obs_price:,.2f}")
            if date:
                parts.append(f"Observation Date: {date}")

        # CATEGORY D: CUSTOMER REVIEWS
        elif cat == DatasetCategory.CUSTOMER_REVIEWS.value:
            prod_ref = record.get("product_id") or record.get("title")
            rating = record.get("rating")
            review_text = record.get("review_text")
            reviewer = record.get("reviewer_name")

            if prod_ref:
                parts.append(f"Product Reference: {prod_ref}")
            if rating is not None:
                parts.append(f"Rating: {rating}/5")
            if reviewer and reviewer.lower() != "anonymous":
                parts.append(f"Reviewer: {reviewer}")
            if review_text:
                parts.append(f"Review: {review_text}")

        # CATEGORY E: PRODUCT SPECIFICATIONS
        elif cat == DatasetCategory.PRODUCT_SPECIFICATIONS.value:
            title = record.get("title") or record.get("product_id")
            cat_name = record.get("category")
            specs = record.get("attributes", {})

            if title:
                parts.append(f"Product: {title}")
            if cat_name:
                parts.append(f"Category: {cat_name}")
            if specs and isinstance(specs, dict):
                spec_str = ", ".join(f"{k}: {v}" for k, v in specs.items())
                if spec_str:
                    parts.append(f"Specifications: {spec_str}")

        # CATEGORY F: POLICIES AND EVIDENCE
        elif cat == DatasetCategory.POLICIES_AND_EVIDENCE.value:
            p_type = record.get("policy_type")
            title = record.get("title")
            content = record.get("policy_content")
            source = record.get("source")

            if p_type:
                parts.append(f"Policy Type: {p_type}")
            if title:
                parts.append(f"Section: {title}")
            if content:
                parts.append(f"Terms: {content}")
            if source:
                parts.append(f"Source: {source}")

        # CATEGORY G: GENERIC
        else:
            title = record.get("title")
            brand = record.get("brand") or record.get("attributes", {}).get("brand") or record.get("attributes", {}).get("manufacturer")
            category_name = record.get("category") or record.get("attributes", {}).get("category")
            desc = record.get("description") or record.get("content_text") or record.get("attributes", {}).get("details") or record.get("attributes", {}).get("specifications")
            price = record.get("price")
            curr = record.get("currency", "INR")
            attrs = record.get("attributes", {})
            if title:
                parts.append(f"Title: {title}")
            if brand:
                parts.append(f"Brand: {brand}")
            if category_name and str(category_name).strip() not in ("General", "GENERIC_DATASET"):
                parts.append(f"Category: {category_name}")
            if desc:
                parts.append(f"Details: {desc}")
            if price is not None and price > 0:
                parts.append(f"Price: {curr} {price:,.2f}")
            if attrs and isinstance(attrs, dict):
                attr_str = ", ".join(f"{k}: {v}" for k, v in attrs.items() if not str(k).startswith("_") and k not in ("brand", "raw_record", "id", "catalogue_id", "is_archived", "created_at", "updated_at"))
                if attr_str:
                    parts.append(f"Attributes: {attr_str}")

        if not parts:
            return None

        joined = " | ".join(parts).strip()
        # Ensure text has meaningful semantic content
        if not joined:
            return None
        return joined


# ---------------- EMBEDDING PROVIDER ABSTRACTIONS ----------------

class BaseEmbeddingProvider(ABC):
    """Abstract interface for embedding generation providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Embeds a batch of texts. Returns array of shape (N, dimension)."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> np.ndarray:
        """Embeds a single query string. Returns 1D array of shape (dimension,)."""
        pass


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic mock provider for automated testing and CI.
    Generates consistent unit-normalized vectors from string hashes.
    Zero external network calls, zero cost.
    """

    def __init__(self, dimension: int = 64, model_name: str = "mock-truthcart-v1"):
        self._dim = dimension
        self._model = model_name

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model

    def _hash_vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            vec[0] = 1.0
            return vec

        for w in words:
            h = int(hashlib.md5(w.encode('utf-8')).hexdigest()[:8], 16)
            idx = h % self._dim
            vec[idx] += 1.0

        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        vectors = [self._hash_vector(t) for t in texts]
        return np.array(vectors, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        return self._hash_vector(query)


class SparseTfIdfEmbeddingProvider(BaseEmbeddingProvider):
    """
    Built-in lightweight offline TF-IDF embedding provider.
    Runs entirely on CPU with zero network dependencies.
    """

    def __init__(self, max_features: int = 256, model_name: str = "local-sparse-tfidf-v1"):
        self._dim = max_features
        self._model = model_name
        self.vocabulary: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model

    def fit(self, texts: List[str]) -> None:
        """Builds vocabulary from texts."""
        df: Dict[str, int] = {}
        for t in texts:
            words = set(re.findall(r'\b[a-zA-Z0-9]{2,}\b', t.lower()))
            for w in words:
                df[w] = df.get(w, 0) + 1

        sorted_vocab = sorted(df.keys(), key=lambda w: df[w], reverse=True)[:self._dim]
        self.vocabulary = {w: i for i, w in enumerate(sorted_vocab)}
        total_docs = max(len(texts), 1)
        self.idf = {w: math.log((total_docs + 1) / (df.get(w, 0) + 1)) + 1.0 for w in self.vocabulary}

    def _embed_single(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        words = re.findall(r'\b[a-zA-Z0-9]{2,}\b', text.lower())
        if not words or not self.vocabulary:
            return vec

        for w in words:
            if w in self.vocabulary:
                idx = self.vocabulary[w]
                vec[idx] += self.idf.get(w, 1.0)

        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not self.vocabulary:
            self.fit(texts)
        vectors = [self._embed_single(t) for t in texts]
        return np.array(vectors, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        return self._embed_single(query)


class AdaptiveEmbeddingManager:
    """
    Orchestrates embedding generation, model versioning, dimension validation,
    caching, retries, and retrieval vector index synchronization.
    """

    def __init__(self):
        self.provider: BaseEmbeddingProvider = self._select_provider()
        self.cache: Dict[str, np.ndarray] = {} # text_hash -> vector
        self.current_model_version = self.provider.model_name
        self.current_dimension = self.provider.dimension

    def _select_provider(self) -> BaseEmbeddingProvider:
        provider_type = os.getenv("EMBEDDING_PROVIDER", "local_tfidf").lower().strip()
        if provider_type == "mock":
            dim = int(os.getenv("EMBEDDING_DIMENSION", "64"))
            return MockEmbeddingProvider(dimension=dim)
        # Default: safe, offline, fast sparse TF-IDF
        return SparseTfIdfEmbeddingProvider(max_features=256)

    def set_provider(self, provider: BaseEmbeddingProvider) -> None:
        """Safely updates provider and resets incompatible cache."""
        if provider.dimension != self.current_dimension or provider.model_name != self.current_model_version:
            SafeLogger.info(f"Embedding provider switched to {provider.model_name} (dim={provider.dimension}). Invalidating vector cache.")
            self.cache.clear()
        self.provider = provider
        self.current_model_version = provider.model_name
        self.current_dimension = provider.dimension

    def embed_records(self, records: List[Dict[str, Any]], category: Optional[str] = None) -> Tuple[List[Dict[str, Any]], np.ndarray]:
        """
        Filters records for embedding eligibility, builds domain-aware text representations,
        and generates validated vector embeddings in batches.
        """
        eligible_records: List[Dict[str, Any]] = []
        texts_to_embed: List[str] = []

        for r in records:
            text = DocumentBuilder.build_embedding_text(r, category)
            if text:
                rec_copy = dict(r)
                rec_copy["_embedding_text"] = text
                eligible_records.append(rec_copy)
                texts_to_embed.append(text)

        if not texts_to_embed:
            return [], np.empty((0, self.current_dimension), dtype=np.float32)

        # Vector generation with caching & dimension verification
        vectors = []
        uncached_texts = []
        uncached_indices = []

        for idx, t in enumerate(texts_to_embed):
            h = hashlib.sha256(t.encode('utf-8')).hexdigest()
            if h in self.cache and len(self.cache[h]) == self.current_dimension:
                vectors.append((idx, self.cache[h]))
            else:
                uncached_texts.append(t)
                uncached_indices.append((idx, h))

        if uncached_texts:
            new_vectors = self.provider.embed_texts(uncached_texts, batch_size=32)
            # Dimension check
            if new_vectors.shape[1] != self.current_dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: provider returned {new_vectors.shape[1]}, "
                    f"expected {self.current_dimension}"
                )
            for (idx, h), vec in zip(uncached_indices, new_vectors):
                self.cache[h] = vec
                vectors.append((idx, vec))

        # Re-sort to preserve original eligible record order
        vectors.sort(key=lambda x: x[0])
        final_matrix = np.array([v[1] for v in vectors], dtype=np.float32)
        return eligible_records, final_matrix

    def embed_query(self, query: str) -> np.ndarray:
        q_vec = self.provider.embed_query(query)
        if len(q_vec) != self.current_dimension:
            raise ValueError(f"Query vector dimension {len(q_vec)} differs from index dimension {self.current_dimension}")
        return q_vec

    def reindex_all_active_records(self, provider: Optional[BaseEmbeddingProvider] = None) -> Dict[str, Any]:
        """
        Reindexes all active dataset records using the active or newly specified provider.
        Invalidates stale caches and refreshes vector representations.
        """
        if provider:
            self.set_provider(provider)

        from app.db.database import db
        records = db.get_active_dataset_records(limit=10000)
        if not records:
            from app.ingestion.catalogue_loader import catalogue_loader
            records = catalogue_loader.get_all_products()

        data_records = [r.get("data") or r for r in records]
        eligible, matrix = self.embed_records(data_records)
        return {
            "model_version": self.current_model_version,
            "dimension": self.current_dimension,
            "records_indexed": len(eligible),
            "matrix_shape": list(matrix.shape)
        }

embedding_manager = AdaptiveEmbeddingManager()

