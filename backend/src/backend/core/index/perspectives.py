"""Four-perspective document assembly (module 2 of the pipeline).

Perspectives reorganise a raw repo along the *newcomer reading path* rather than
the file layout, so a newcomer's cross-file questions ("how do I set this up?")
can be answered by retrieving a single coherent text.

Perspectives:
- V1 entry & conventions  : README + CONTRIBUTING + community + license
- V2 architecture map     : file tree + top-level package/docstrings + main entry
- V3 executable path      : build config + scripts/Makefile/workflows + install docs
- V4 issue slots          : good-first-issue titles/bodies + touched files
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.github.recon import RawSignals

# Repo-relative "seed files" whose text is most relevant to V1/V3 (kept cheap:
# we reuse doc_files already fetched during recon).
_V1_FILES = ("readme.md", "readme.rst", "contributing.md", "contributing")
_V3_FILES = ("makefile", "dockerfile")
_V3_ROOT_BUILD = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
                  "package.json", "cargo.toml", "go.mod", "gemfile")


@dataclass
class PerspectiveDoc:
    """One assembled perspective document ready for chunking/indexing."""

    key: str  # v1 | v2 | v3 | v4
    title: str
    text: str
    # 0..1 weighting used by the retriever for activate-by-default vs lazy.
    activate_default: bool


def _doc_by_path(sig: RawSignals, name_lower: str) -> str | None:
    for f in sig.doc_files:
        if f.path.lower() == name_lower or f.name.lower() == name_lower:
            return f.text
    return None


def _top_level_dirs(file_tree: list[str]) -> list[str]:
    dirs: set[str] = set()
    for p in file_tree:
        parts = p.split("/")
        if len(parts) >= 2:
            dirs.add(parts[0])
    return sorted(dirs)


def assemble_perspectives(sig: RawSignals) -> list[PerspectiveDoc]:
    docs: list[PerspectiveDoc] = []

    # ---- V1: entry & conventions ------------------------------------------
    parts: list[str] = []
    for name in _V1_FILES:
        text = _doc_by_path(sig, name)
        if text:
            parts.append(f"===== {name} =====")
            parts.append(text)
    if sig.meta.description:
        parts.insert(0, f"仓库描述: {sig.meta.description}")
    v1_text = "\n\n".join(parts).strip()
    docs.append(PerspectiveDoc(key="v1", title="入口与约定",
                               text=v1_text, activate_default=True))

    # ---- V2: architecture map ---------------------------------------------
    v2_parts = [f"文件树（{len(sig.file_tree)} 个文件）:"]
    if sig.file_tree:
        v2_parts.append("\n".join(sig.file_tree[:400]))  # cap long trees
    v2_parts.append(f"顶层目录: {', '.join(_top_level_dirs(sig.file_tree))}")
    v2_text = "\n".join(v2_parts).strip()
    docs.append(PerspectiveDoc(key="v2", title="架构地图",
                               text=v2_text, activate_default=False))

    # ---- V3: executable path ----------------------------------------------
    v3_parts: list[str] = []
    for name in _V1_FILES:  # CONTRIBUTING/README often hold runnable steps
        if name in _V3_FILES:
            continue
        text = _doc_by_path(sig, name)
        if text and any(k in text.lower() for k in ("install", "setup", "test", "make", "pip")):
            v3_parts.append(f"===== {name} =====")
            v3_parts.append(text)
    for name in _V3_FILES:
        text = _doc_by_path(sig, name)
        if text:
            v3_parts.append(f"===== {name} =====")
            v3_parts.append(text)
    # Build files themselves are code, not prose; the docs that mention them
    # are more useful. If we have no prose at all, include the build file text.
    if not v3_parts:
        v3_parts.append("（该仓库未抓到安装/测试相关文档，需结合 V1/V2 与代码上下文）")
    docs.append(PerspectiveDoc(key="v3", title="可执行路径",
                               text="\n\n".join(v3_parts).strip(),
                               activate_default=True))

    # ---- V4: issue slots --------------------------------------------------
    v4_lines: list[str] = []
    seen = 0
    for iss in sig.issues:
        if iss.get("pull_request"):
            continue  # PRs, not issues
        num = iss.get("number")
        title = iss.get("title", "")
        body = (iss.get("body") or "")[:600]
        labels = ", ".join(l.get("name", "") for l in iss.get("labels", []))
        state = iss.get("state", "")
        line = f"issue #{num} [{labels}] {title}\n{body}"
        v4_lines.append(line)
        seen += 1
        if seen >= 15:
            break
    v4_text = "\n\n".join(v4_lines) if v4_lines else "（暂无 good-first-issue / help-wanted）"
    docs.append(PerspectiveDoc(key="v4", title="可贡献 issue 槽位",
                               text=v4_text, activate_default=False))
    return docs


def chunk_text(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    """Simple overlap chunking on paragraph/line boundaries. Deterministic.

    A real embedding store can chunk this way cheaply; keep char-level so it is
    reproducible offline (no tokeniser dependency in the assembly layer).
    """
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        # Try to break on a newline near the boundary to keep chunk semantics.
        if end < len(text):
            nl = text.rfind("\n", start + size // 2, end)
            if nl != -1 and nl > start:
                end = nl + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [c for c in chunks if c]
