from __future__ import annotations

import json
import os
from threading import Lock
from typing import List

import numpy as np

from backend.embedding_engine import EmbeddingEngine
from backend.retriever import AdaptiveRetriever


class SearchIndex:
    """Disk-backed in-process search index for fast retrieval."""

    def __init__(self, index_dir: str) -> None:
        self.index_dir = index_dir
        self.texts_path = os.path.join(index_dir, "chunk_texts.json")
        self.embeddings_path = os.path.join(index_dir, "chunk_embeddings.npy")
        self._lock = Lock()
        self.chunk_texts: List[str] = []
        self.chunk_embeddings = np.empty((0, 0), dtype=np.float32)
        self.loaded = False
        os.makedirs(self.index_dir, exist_ok=True)

    def load(self) -> None:
        with self._lock:
            self._load_unlocked()

    def _load_unlocked(self) -> None:
        if os.path.exists(self.texts_path) and os.path.exists(self.embeddings_path):
            with open(self.texts_path, "r", encoding="utf-8") as fh:
                self.chunk_texts = json.load(fh)
            self.chunk_embeddings = np.load(self.embeddings_path).astype(np.float32)
        else:
            self.chunk_texts = []
            self.chunk_embeddings = np.empty((0, 0), dtype=np.float32)
        self.loaded = True

    def _save_unlocked(self) -> None:
        with open(self.texts_path, "w", encoding="utf-8") as fh:
            json.dump(self.chunk_texts, fh, ensure_ascii=False)
        np.save(self.embeddings_path, self.chunk_embeddings.astype(np.float32))

    def rebuild(self, chunk_texts: List[str], embedding_engine: EmbeddingEngine) -> None:
        clean_texts = [t for t in chunk_texts if isinstance(t, str) and t.strip()]
        embeddings = embedding_engine.embed_text_chunks(clean_texts)
        with self._lock:
            self.chunk_texts = clean_texts
            self.chunk_embeddings = embeddings
            self._save_unlocked()
            self.loaded = True

    def append_chunks(self, new_chunks: List[str], embedding_engine: EmbeddingEngine) -> int:
        clean_chunks = [t for t in new_chunks if isinstance(t, str) and t.strip()]
        if not clean_chunks:
            return 0

        with self._lock:
            if not self.loaded:
                self._load_unlocked()

            existing = set(self.chunk_texts)
            unique_chunks = [c for c in clean_chunks if c not in existing]
            if not unique_chunks:
                return 0

            new_embeddings = embedding_engine.embed_text_chunks(unique_chunks)
            if self.chunk_embeddings.size == 0:
                self.chunk_embeddings = new_embeddings
            else:
                self.chunk_embeddings = np.vstack([self.chunk_embeddings, new_embeddings]).astype(np.float32)
            self.chunk_texts.extend(unique_chunks)
            self._save_unlocked()
            return len(unique_chunks)

    def ensure_ready(self, source_chunk_texts: List[str], embedding_engine: EmbeddingEngine) -> None:
        expected_count = len([t for t in source_chunk_texts if isinstance(t, str) and t.strip()])
        with self._lock:
            if not self.loaded:
                self._load_unlocked()
            current_count = len(self.chunk_texts)

        if current_count != expected_count:
            self.rebuild(source_chunk_texts, embedding_engine)

    def get_retriever(self, alpha: float = 0.4, beta: float = 0.4, gamma: float = 0.2) -> AdaptiveRetriever:
        with self._lock:
            return AdaptiveRetriever(
                chunk_embeddings=self.chunk_embeddings,
                chunk_texts=self.chunk_texts,
                alpha=alpha,
                beta=beta,
                gamma=gamma,
            )

    def stats(self) -> dict:
        with self._lock:
            return {
                "loaded": self.loaded,
                "chunks": len(self.chunk_texts),
                "embeddings_shape": list(self.chunk_embeddings.shape),
                "index_dir": self.index_dir,
            }
