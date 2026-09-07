"""Four-perspective document assembly (module 2 of the pipeline).

Perspectives reorganise a raw repo along the *newcomer reading path* rather than
the file layout, so a newcomer's cross-file questions ("how do I set this up?")
can be answered by retrieving a single coherent text.

Perspectives:
- V1 entry & conventions  : README + CONTRIBUTING + community + license
- V2 architecture map     : file tree + top-level package/docstrings + main entry
- V3 executable path      : build config + scripts/Makefile/workflows + install docs
- V4 issue slots          : good-first-issue titles/bodies + touched files

Each assembled chunk keeps its *real* repo-relative source (a file path for
V1/V3 docs, an issue ref like `#12` for V4). That source is what the generator
cites as evidence, and what the evidence verifier checks against the repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.core.github.recon import RawSignals

# Repo-relative "seed files" whose text is most relevant to V1/V3 (kept cheap:
# we reuse doc_files already fetched during recon).
_V1_FILES = ("readme.md", "readme.rst", "contributing.md", "contributing")
_V3_FILES = ("makefile", "dockerfile")


@dataclass
class PerspectiveChunk:
    """One indexed chunk: text + which repo file/issue it came from."""

    perspective: str  # v1 | v2 | v3 | v4
    text: str
    # Real repo-relative path (file kind) OR issue ref "#12" (issue kind).
    source_path: str = ""
    kind: str = "file"  # file | issue | synthetic


def _doc_by_path(sig: RawSignals, name_lower: str) -> str | None:
    for f in sig.doc_files:
        if f.path.lower() == name_lower or f.name.lower() == name_lower:
            return f.text
    return None


def _emit_doc_chunks(perspective: str, path: str, text: str, out: list[PerspectiveChunk]) -> None:
    """Chunk one doc file and append chunks tagged with that real path."""
    if not text:
        return
    header = f"===== {path} ====="
    body = text
    # Keep header on first chunk for provenance.
    chunks = chunk_text(body, size=700, overlap=80)
    for i, c in enumerate(chunks):
        prefix = header if i == 0 else ""
        out.append(
            PerspectiveChunk(
                perspective=perspective,
                text=(prefix + "\n" + c).strip() if prefix else c,
                source_path=path,
                kind="file",
            )
        )


def assemble_perspective_chunks(sig: RawSignals) -> list[PerspectiveChunk]:
    """Build all perspective chunks, each tagged with a real repo source.

    Returns flat list; the service groups by perspective for upsert.
    """
    chunks: list[PerspectiveChunk] = []

    # ---- V1: entry & conventions (per-doc real source) ---------------------
    for name in _V1_FILES:
        text = _doc_by_path(sig, name)
        if text:
            _emit_doc_chunks("v1", name, text, chunks)
    if sig.meta.description and not chunks:
        chunks.append(
            PerspectiveChunk(
                perspective="v1",
                text=f"仓库描述: {sig.meta.description}",
                source_path="",
                kind="synthetic",
            )
        )

    # ---- V2: architecture map ---------------------------------------------
    if sig.file_tree:
        tree_text = "\n".join(sig.file_tree[:400])
        chunks.append(
            PerspectiveChunk(
                perspective="v2",
                text=f"文件树（{len(sig.file_tree)} 个文件）:\n{tree_text}",
                source_path="",
                kind="synthetic",
            )
        )

    # ---- V3: executable path (real doc source when available) -------------
    # Any fetched doc that actually carries runnable steps counts as a source:
    # README / CONTRIBUTING / Makefile / Dockerfile AND key docs like
    # docs/dev/contributing.rst that got pulled by deep recon. This is what lets
    # a "how do I run tests" stage find the real file that documents it.
    _RUN_KEYWORDS = ("install", "setup", "test", "make", "pip", "clone",
                     "environment", "virtualenv", "venv", "tox", "develop", "usage")
    v3_paths: list[str] = []
    for d in sig.doc_files:
        low = d.path.lower()
        if low.startswith(".") or low.endswith(("license",)) or "/license" in low:
            continue
        if any(k in low for k in ("readme", "contribut")):
            v3_paths.append(d.path)
            continue
        if any(k in d.text.lower() for k in _RUN_KEYWORDS):
            v3_paths.append(d.path)
    # Dedupe preserving order.
    seen: set[str] = set()
    v3_paths = [p for p in v3_paths if not (p in seen or seen.add(p))]
    for path in v3_paths:
        for d in sig.doc_files:
            if d.path == path:
                _emit_doc_chunks("v3", path, d.text, chunks)
                break

    # ---- V4: issue slots (real issue refs) --------------------------------
    seen = 0
    for iss in sig.issues:
        if iss.get("pull_request"):
            continue  # PRs, not issues
        num = iss.get("number")
        title = iss.get("title", "")
        body = (iss.get("body") or "")[:600]
        labels = ", ".join(l.get("name", "") for l in iss.get("labels", []))
        line = f"issue #{num} [{labels}] {title}\n{body}"
        chunks.append(
            PerspectiveChunk(
                perspective="v4",
                text=line.strip(),
                source_path=f"#{num}",
                kind="issue",
            )
        )
        seen += 1
        if seen >= 15:
            break

    return chunks


def chunk_text(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    """Simple overlap chunking on paragraph/line boundaries. Deterministic."""
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            nl = text.rfind("\n", start + size // 2, end)
            if nl != -1 and nl > start:
                end = nl + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [c for c in chunks if c]


# Keep a small view for callers that want the doc-summary shape.
@dataclass
class PerspectiveDoc:
    key: str
    title: str
    text: str
    activate_default: bool
    source_path: str = ""
    kind: str = "file"


def assemble_perspectives(sig: RawSignals) -> list[PerspectiveDoc]:
    """Group perspective chunks into docs (source per chunk retained in text via
    `===== path =====` header). Legacy convenience wrapper."""
    from collections import OrderedDict

    groups: "OrderedDict[str, list[str]]" = OrderedDict()
    for c in assemble_perspective_chunks(sig):
        groups.setdefault(c.perspective, []).append(c.text)
    docs: list[PerspectiveDoc] = []
    for key, texts in groups.items():
        docs.append(
            PerspectiveDoc(
                key=key,
                title={"v1": "入口与约定", "v2": "架构地图", "v3": "可执行路径", "v4": "可贡献 issue 槽位"}.get(key, key),
                text="\n\n".join(texts),
                activate_default=key in ("v1", "v3"),
            )
        )
    return docs
