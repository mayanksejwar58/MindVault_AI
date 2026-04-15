from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


class AdaptiveRetriever:
    def __init__(
        self,
        chunk_embeddings: np.ndarray,
        chunk_texts: List[str],
        alpha: float = 0.4,
        beta: float = 0.4,
        gamma: float = 0.2,
    ) -> None:
        self.chunk_embeddings = chunk_embeddings
        self.chunk_texts = chunk_texts
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        denom = float(np.linalg.norm(vec1) * np.linalg.norm(vec2))
        if denom == 0.0:
            return 0.0
        return float(np.dot(vec1, vec2) / denom)

    def compute_score(self, query_vectors: Dict[str, np.ndarray], chunk_vector: np.ndarray) -> float:
        intent_sim = self.cosine_similarity(query_vectors["intent"], chunk_vector)
        context_sim = self.cosine_similarity(query_vectors["context"], chunk_vector)
        entity_sim = self.cosine_similarity(query_vectors["entity"], chunk_vector)
        return (self.alpha * intent_sim) + (self.beta * context_sim) + (self.gamma * entity_sim)

    def retrieve(self, query_vectors: Dict[str, np.ndarray], top_k: int = 10) -> List[Tuple[str, float]]:
        if self.chunk_embeddings.size == 0 or not self.chunk_texts:
            return []

        scored: List[Tuple[str, float]] = []
        for idx, chunk_vector in enumerate(self.chunk_embeddings):
            score = self.compute_score(query_vectors, chunk_vector)
            scored.append((self.chunk_texts[idx], score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
