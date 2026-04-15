from __future__ import annotations

from typing import Dict, List

import numpy as np
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()


class EmbeddingEngine:
    """Basic embedding engine with simple cosine-similarity helpers."""

    def __init__(self) -> None:
        self.model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

    def embed_text_chunks(self, chunks: List[str]) -> np.ndarray:
        """Embed a list of chunk strings."""
        if not chunks:
            return np.empty((0, 0), dtype=np.float32)

        vectors = self.model.embed_documents(chunks)
        return np.asarray(vectors, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed one user query string."""
        vector = self.model.embed_query(query)
        return np.asarray(vector, dtype=np.float32)

    def embed_query_multi_aspect(self, query: str) -> Dict[str, np.ndarray]:
        """
        Keep compatibility with retriever code that expects three query vectors.
        For a basic setup, we reuse one query embedding for all aspects.
        """
        q_vec = self.embed_query(query)
        return {
            "intent": q_vec,
            "context": q_vec,
            "entity": q_vec,
        }

    def adaptive_weights(self, query: str) -> Dict[str, float]:
        """Basic fixed weights (kept for compatibility)."""
        _ = query
        return {"intent": 0.33, "context": 0.34, "entity": 0.33}

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two vectors."""
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0.0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def compute_score(
        self,
        doc_vector: np.ndarray,
        query_vectors: Dict[str, np.ndarray],
        weights: Dict[str, float],
    ) -> float:
        """Weighted cosine score against intent/context/entity query vectors."""
        intent = self.cosine_similarity(doc_vector, query_vectors["intent"])
        context = self.cosine_similarity(doc_vector, query_vectors["context"])
        entity = self.cosine_similarity(doc_vector, query_vectors["entity"])

        return (
            weights["intent"] * intent
            + weights["context"] * context
            + weights["entity"] * entity
        )
