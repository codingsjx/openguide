"""Build + query a per-repo vector index from raw signals.

One-stop entry used by the API layer: index a repo once (docs + tree + issues →
four perspectives → upsert into chromadb per perspective), then answer searches
with perspective routing.
"""

from __future__ import annotations

from backend.core.index.perspectives import assemble_perspectives, chunk_text
from backend.core.index.retrieval import SearchResult, retrieve
from backend.core.index.vectorstore import Store
from backend.core.github.recon import RawSignals


class RepoIndex:
    """Owns the persistent store for one repo and indexes it on demand."""

    def __init__(self, owner: str, repo: str) -> None:
        self.owner = owner
        self.repo = repo
        self._store = Store(owner, repo)

    def index(self, sig: RawSignals) -> None:
        """Perspective-assemble + upsert (idempotent; safe to re-run)."""
        for doc in assemble_perspectives(sig):
            chunks = chunk_text(doc.text)
            metas = [{"perspective": doc.key, "title": doc.title}] * len(chunks)
            self._store.upsert(doc.key, chunks, metas)

    def search(self, query: str, kind: str | None = None, top_k: int = 5) -> SearchResult:
        return retrieve(self._store, query, kind=kind, top_k=top_k)


def build_repo_index(sig: RawSignals) -> RepoIndex:
    idx = RepoIndex(sig.meta.owner, sig.meta.repo)
    idx.index(sig)
    return idx
