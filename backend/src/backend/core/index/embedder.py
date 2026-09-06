"""Embedding facade.

OpenGuide's retrieval defers embedding to the vector store's own default
(no external embedding function) so upsert and query are always dimension-
consistent. This module exists for tests and future explicit-embedding needs:
a local open-source embedder, or a deterministic hermetic hash fallback when
no real model is configured.
"""

from __future__ import annotations

from functools import lru_cache

from backend.config import get_settings


class EmbedderError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_embedder() -> "Embedder":
    settings = get_settings()
    return Embedder(model_name=settings.embedding_model or "")


class Embedder:
    """Optional sentence-transformers embedder, with hermetic hash fallback.

    Not used by the chromadb path (which embeds internally). Kept as a facade
    so tests / offline demo can compute embeddings without the model download.
    """

    def __init__(self, model_name: str = "") -> None:
        self._model_name = model_name
        self._model = None
        self._fallback = not model_name

    def _load(self):
        if self._model is not None or self._fallback:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(self._model_name)
        except Exception:  # noqa: BLE001 - model download/net failure
            self._fallback = True
            self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._load()
        if self._fallback or self._model is None:
            return self._hash_embed(texts)
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    @staticmethod
    def _hash_embed(texts: list[str]) -> list[list[float]]:
        """Deterministic surrogate for hermetic tests: fixed-dim token hashing."""
        import hashlib

        from backend.config import get_settings

        dim = get_settings().embedding_dim
        out: list[list[float]] = []
        for t in texts:
            vec = [0.0] * dim
            for tok in t.split():
                h = int(hashlib.sha256(tok.encode()).hexdigest()[:8], 16)
                vec[h % dim] += 1.0
            norm = sum(x * x for x in vec) ** 0.5
            out.append([x / norm if norm else 0.0 for x in vec])
        return out
