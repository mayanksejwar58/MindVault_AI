from __future__ import annotations

from typing import List, Tuple

from backend.embedding_engine import EmbeddingEngine
from backend.reranker import CrossEncoderReranker
from backend.retriever import AdaptiveRetriever


class RAGPipeline:
    def __init__(
        self,
        embedding_engine: EmbeddingEngine,
        retriever: AdaptiveRetriever,
        reranker: CrossEncoderReranker,
    ) -> None:
        self.embedding_engine = embedding_engine
        self.retriever = retriever
        self.reranker = reranker

    def process_query(self, query: str, retrieve_k: int = 10, final_k: int = 3) -> List[str]:
        query_vectors = self.embedding_engine.embed_query_multi_aspect(query)
        retrieved = self.retriever.retrieve(query_vectors, top_k=retrieve_k)
        candidates = [chunk for chunk, _ in retrieved]
        if not candidates:
            return []
        reranked = self.reranker.rerank(query, candidates)
        return [chunk for chunk, _ in reranked[:final_k]]

    def process_query_with_scores(
        self, query: str, retrieve_k: int = 10, final_k: int = 3
    ) -> List[Tuple[str, float]]:
        query_vectors = self.embedding_engine.embed_query_multi_aspect(query)
        retrieved = self.retriever.retrieve(query_vectors, top_k=retrieve_k)
        candidates = [chunk for chunk, _ in retrieved]
        if not candidates:
            return []
        reranked = self.reranker.rerank(query, candidates)
        return reranked[:final_k]
