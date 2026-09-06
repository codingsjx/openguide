"""Evidence verification: "无证据不宣称".

A generated step's `evidence.source` must resolve to something real we actually
fetched from the repo (a doc file, a root build file, or an issue/PR reference).
If it does not, the step's evidence is downgraded to kind="missing" so the
frontend and the benchmark both treat "claimed without a source" as absent.

`verify_step` is shared by generation and by benchmark L2 (evidence_hit) to
keep the audit the same everywhere.
"""

from __future__ import annotations

import re

from backend.core.github.recon import RawSignals
from backend.core.generate.schemas import Evidence

# Issue refs like "#42" / "issues/42" / a full github issue url.
_ISSUE_RE = re.compile(r"(?:issues?/)?(\d{1,6})$")
_GH_ISSUE_URL_RE = re.compile(r"github\.com/[^/]+/[^/]+/issues/(\d{1,6})")


def available_sources(sig: RawSignals) -> set[str]:
    """Lowercased repo-relative paths we actually hold (doc files + root build + tree)."""
    paths: set[str] = set()
    for f in sig.doc_files:
        paths.add(f.path.lower())
    paths.update(k for k in sig.root_entries)
    paths.update(p.lower() for p in sig.file_tree)
    return paths


def resolve_evidence_source(source: str, sig: RawSignals) -> Evidence:
    """Return an Evidence with kind set according to whether source is real.

    Handles:
    - repo file path "docs/install.md#L3"  (path must be in available_sources)
    - issue ref "#42" or ".../issues/42"   (must exist in sig.issues numbers)
    - github blob URL fallback -> file path extraction when it matches a file
    """
    avail = available_sources(sig)
    issue_numbers = {
        i.get("number") for i in sig.issues if i.get("pull_request") is None
    }
    src = (source or "").strip()
    if not src:
        return Evidence(kind="missing", source="", quote="")

    m = _GH_ISSUE_URL_RE.search(src)
    if m and int(m.group(1)) in issue_numbers:
        return Evidence(kind="issue", source=f"#{m.group(1)}", quote="")

    # Plain "#N" shorthand (no leading path).
    bare = src.strip()
    if bare.startswith("#") and bare[1:].isdigit():
        num = int(bare[1:])
        if num in issue_numbers:
            return Evidence(kind="issue", source=f"#{num}", quote="")
        return Evidence(kind="missing", source=src, quote="")

    # "issues/N" / "pull/N" prefixed refs.
    path_part = src.split("#", 1)[0].strip("/")
    if path_part.startswith(("issues/", "pull/")):
        m2 = _ISSUE_RE.search(path_part)
        if m2 and int(m2.group(1)) in issue_numbers:
            return Evidence(kind="issue", source=f"#{m2.group(1)}", quote="")

    # Treat "#L3"-style suffix: strip, then look up file path.
    norm = src.split(" ", 1)[0].split("#", 1)[0].lower().strip("/")
    # Possible full blob URL: extract /owner/repo/blob/ref/<path>.
    blob = re.search(r"blob/[^/]+/(.+)", src.lower())
    if blob:
        norm = blob.group(1).split("#", 1)[0]

    if norm in avail or any(norm.startswith(p + "/") for p in avail if p.count("/") == 0):
        return Evidence(kind="file", source=src, quote="")
    return Evidence(kind="missing", source=src, quote="")
