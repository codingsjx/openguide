"""DocFile index by lowercase repo path for evidence/source lookups."""

from __future__ import annotations

from backend.core.github.recon import RawSignals


def doc_path_index(sig: RawSignals) -> dict[str, str]:
    """Return {lowercased path: original path} for every fetched doc file."""
    return {f.path.lower(): f.path for f in sig.doc_files}
