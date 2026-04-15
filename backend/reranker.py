from __future__ import annotations

from threading import Lock
from typing import List, Tuple
import logging

try:
    from fastembed.rerank.cross_encoder import TextCrossEncoder
except Exception as exc:
    TextCrossEncoder = None
    _FASTEMBED_IMPORT_ERROR = exc
else:
    _FASTEMBED_IMPORT_ERROR = None


class CrossEncoderReranker:
    """
    Cross-Encoder Reranker
    - Re-ranks top retrieved documents
    - Improves final answer quality
    """

    def __init__(self, model_name: str = "Xenova/ms-marco-MiniLM-L-6-v2") -> None:
        self.model_name = model_name
        self.model = None
        self._model_lock = Lock()

    def _get_model(self):
        if TextCrossEncoder is None:
            raise RuntimeError(
                "fastembed is not installed. Run: pip install fastembed"
            ) from _FASTEMBED_IMPORT_ERROR

        with self._model_lock:
            if self.model is None:
                logging.info(f"Loading reranker model: {self.model_name}")
                self.model = TextCrossEncoder(self.model_name)

        return self.model

    def rerank(self, query: str, candidates: List[str]) -> List[Tuple[str, float]]:
        if not candidates:
            return []

        model = self._get_model()

        try:
            scores = list(model.rerank(query, candidates))
        except Exception as e:
            logging.error(f"Reranking failed: {e}")
            return [(c, 0.0) for c in candidates]

        ranked = list(zip(candidates, [float(s) for s in scores]))

        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked