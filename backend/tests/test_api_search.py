"""API route tests for /api/search using the hermetic (no-chroma) fallback.

Enrichment/recon are patched to avoid network; the Store falls back to the
in-memory token-overlap path, so these are fast and offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root importable (backend + benchmark share the conftest on the
# backend side; here we add backend/src for the API import).
BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.main import app  # noqa: E402


def test_search_route_happy_path(monkeypatch):
    """Feed a synthetic repo via patched recon so no network is hit."""

    def fake_recon(owner, repo, client=None):
        from backend.core.github.models import DocFile, RepoMeta
        from backend.core.github.recon import RawSignals

        return RawSignals(
            meta=RepoMeta(owner="o", repo="r", stars=5, default_branch="main", pushed_at=""),
            language_bytes={"python": 100},
            root_entries={"readme.md": "README.md", "contributing.md": "CONTRIBUTING.md"},
            has_docs_dir=True,
            doc_files=[
                DocFile(path="README.md", name="README.md", text="Install with pip install -e .[dev]. Run pytest."),
                DocFile(path="CONTRIBUTING.md", name="CONTRIBUTING.md", text="Fork and PR. Set up venv."),
            ],
            issues=[
                {"number": 1, "title": "Add example", "body": "show sample", "state": "open",
                 "labels": [{"name": "good first issue"}], "pull_request": None},
            ],
            file_tree=["README.md", "src/lib.py", "tests/test_lib.py"],
        )

    monkeypatch.setattr("backend.api.routes.search.recon", fake_recon)
    monkeypatch.setattr("backend.api.routes.search.enrich_docs_and_tree", lambda s, client=None: s)

    c = TestClient(app)
    r = c.post(
        "/api/search",
        json={"url": "o/r", "query": "how do I install and run tests", "kind": None},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query"]
    assert body["kind"] in ("setup", "test")
    assert body["hits"], "should return evidence chunks"


def test_search_route_rejects_bad_url():
    c = TestClient(app)
    r = c.post("/api/search", json={"url": "https://example.com/x", "query": "hi"})
    assert r.status_code == 422
