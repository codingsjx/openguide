"""One deduplicated corpus, not a merge of separately ranked perspectives."""
from backend.core.index.perspectives import assemble_perspective_chunks
from backend.core.index.vectorstore import Store
from backend.core.index.retrieval import SearchResult


class GlobalFlatIndex:
    def __init__(self, signals):
        self.store = Store(signals.meta.owner, signals.meta.repo, boost_executable=False)
        unique = {}
        for chunk in assemble_perspective_chunks(signals):
            unique.setdefault((chunk.source_path, chunk.kind, chunk.text), chunk)
        chunks = list(unique.values())
        self.corpus_size = len(chunks)
        self.store.upsert("flat", [c.text for c in chunks],
            [{"source": c.source_path, "kind": c.kind} for c in chunks])

    def search(self, query, kind=None, top_k=4):
        return SearchResult(query=query, kind="flat", perspective="flat",
            hits=self.store.query("flat", query, top_k))
