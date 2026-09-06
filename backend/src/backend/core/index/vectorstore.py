"""Vector store facade over chromadb, one collection per repo.

Collections are named `repo__{owner}_{repo}__{perspective}` and persist under
Settings.vectorstore_dir so repeat runs (demo/benchmark) don't rebuild.

Embeddings come from the Embedder facade. When chromadb is unavailable or an
embedder falls back, retrieval still works through a linear-scan fallback in
this module so tests and constrained envs are hermetic.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.config import get_settings
from backend.core.index.embedder import get_embedder


@dataclass
class Hit:
    text: str
    perspective: str
    score: float
    meta: dict


class Store:
    """Thin wrapper: per-(repo,perspective) upsert + query with fallback."""

    def __init__(self, owner: str, repo: str, persist_dir: str | None = None) -> None:
        settings = get_settings()
        self.owner = owner
        self.repo = repo
        self.persist_dir = persist_dir or settings.vectorstore_dir
        self._client = None
        self._embed_fn = None
        self._collections: dict[str, object] = {}
        self._rows: dict[str, list[dict]] = {}  # fallback in-memory store
        if settings.use_chroma:
            self._init_chromadb()

    # -- lifecycle ----------------------------------------------------------

    def _init_chromadb(self):
        try:
            import chromadb  # type: ignore
            from chromadb.utils import embedding_functions  # type: ignore

            # Deterministic embedder: ONNX all-MiniLM-L6-v2 (384-d). Explicit
            # function avoids chromadb default-download races on the first call
            # and pins consistent embeddings for upsert + query.
            self._embed_fn = embedding_functions.ONNXMiniLM_L6_V2()
            self._client = chromadb.PersistentClient(path=self.persist_dir)
        except Exception:  # noqa: BLE001 - chromadb may not be installed/test env
            self._embed_fn = None
            self._client = None

    def _coll_name(self, perspective: str) -> str:
        safe = f"{self.owner}_{self.repo}".replace("/", "_").replace("-", "_").replace(".", "_")
        return f"repo__{safe}__{perspective}"

    # -- writes -------------------------------------------------------------

    def upsert(self, perspective: str, texts: list[str], metadatas: list[dict] | None = None) -> None:
        if not texts:
            return
        if metadatas is None:
            metadatas = [{"perspective": perspective}] * len(texts)
        # chromadb rejects empty metadata dicts; guarantee at least one key.
        metas = [
            m if (m and isinstance(m, dict) and m) else {"perspective": perspective}
            for m in metadatas
        ]
        if self._client is not None:
            coll = self._get_coll(perspective, create=True)
            ids = [f"{perspective}_{i}" for i in range(len(texts))]
            # Deterministic per-call ids; in a real pipeline you'd compute a hash.
            coll.upsert(ids=ids, documents=texts, embeddings=self._embed_fn(texts), metadatas=metas)
        else:
            self._rows.setdefault(perspective, []).extend(
                [{"text": t, "meta": m} for t, m in zip(texts, metas)]
            )

    def _get_coll(self, perspective: str, create: bool = False):
        from chromadb.config import Settings as CdbSettings  # type: ignore

        key = (self.persist_dir, perspective)
        if key in self._collections:
            return self._collections[key]
        # Chroma collection without its own embedding function; we pass
        # embeddings explicitly on both upsert and query for consistency.
        coll = self._client.get_or_create_collection(
            name=self._coll_name(perspective),
            embedding_function=None,
        )
        self._collections[key] = coll
        return coll

    # -- reads --------------------------------------------------------------

    def query(self, perspective: str, query_text: str, top_k: int = 5) -> list[Hit]:
        if self._client is not None:
            try:
                return self._query_chroma(perspective, query_text, top_k)
            except Exception:  # noqa: BLE001 - fallback on any chroma error
                pass
        return self._query_fallback(perspective, query_text, top_k)

    def _query_chroma(self, perspective: str, query_text: str, top_k: int) -> list[Hit]:
        # Embed the query with the same function used at upsert time.
        emb = self._embed_fn([query_text])[0]
        coll = self._get_coll(perspective, create=False)
        res = coll.query(query_embeddings=[emb], n_results=top_k)
        hits: list[Hit] = []
        ids = (res.get("ids") or [[]])[0] or []
        docs = (res.get("documents") or [[]])[0] or []
        metas = (res.get("metadatas") or [[]])[0] or []
        distances = (res.get("distances") or [[]])[0] or []
        for i in range(min(len(ids), len(docs))):
            hits.append(
                Hit(
                    text=docs[i],
                    perspective=perspective,
                    score=float(distances[i]) if i < len(distances) else 0.0,
                    meta=metas[i] if i < len(metas) else {},
                )
            )
        return hits

    def _query_fallback(self, perspective: str, query_text: str, top_k: int) -> list[Hit]:
        rows = self._rows.get(perspective, [])
        if not rows:
            return []
        # Token-overlap similarity (deterministic, hermetic for tests).
        q = set(query_text.lower().split())
        scored = []
        for r in rows:
            words = set(r["text"].lower().split())
            inter = len(q & words)
            if inter:
                scored.append((inter, r))
        scored.sort(key=lambda x: -x[0])
        return [
            Hit(text=r["text"], perspective=perspective, score=float(s), meta=r["meta"])
            for s, r in scored[:top_k]
        ]
