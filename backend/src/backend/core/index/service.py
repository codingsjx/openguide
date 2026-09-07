"""Build + query a per-repo vector index from raw signals.

One-stop entry used by the API layer: index a repo once (docs + tree + issues →
four perspectives → upsert into chromadb per perspective), then answer searches
with perspective routing.
"""

from __future__ import annotations

from backend.core.index.perspectives import assemble_perspective_chunks
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
        """Assemble perspective chunks (each with a real source) + upsert."""
        per_perspective: dict[str, list[dict]] = {}
        for c in assemble_perspective_chunks(sig):
            per_perspective.setdefault(c.perspective, []).append(
                {
                    "text": c.text,
                    "source": c.source_path,
                    "kind": c.kind,
                    "perspective": c.perspective,
                }
            )
        for perspective, rows in per_perspective.items():
            texts = [r["text"] for r in rows]
            metas = [
                {
                    "perspective": perspective,
                    "source": r["source"],
                    "kind": r["kind"],
                }
                for r in rows
            ]
            self._store.upsert(perspective, texts, metas)

    def search(
        self, query: str, kind: str | None = None, top_k: int = 5, any_perspective: bool = False
    ) -> SearchResult:
        return retrieve(self._store, query, kind=kind, top_k=top_k, any_perspective=any_perspective)


def build_repo_index(sig: RawSignals) -> RepoIndex:
    idx = RepoIndex(sig.meta.owner, sig.meta.repo)
    idx.index(sig)
    return idx
