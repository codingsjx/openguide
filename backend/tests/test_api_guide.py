"""API tests for /api/guide using hermetic patches (no network, no LLM)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals


def _fake_signals() -> RawSignals:
    docs = [
        ("README.md", "# Lib\nInstall with `pip install -e .[dev]`.\nRun `pytest`."),
        ("CONTRIBUTING.md", "Fork. Branch. Commit. Push. PR."),
    ]
    return RawSignals(
        meta=RepoMeta(owner="o", repo="lib", stars=30, default_branch="main",
                      pushed_at="", license="MIT"),
        language_bytes={"python": 100},
        root_entries={"readme.md": "README.md", "contributing.md": "CONTRIBUTING.md"},
        has_docs_dir=True,
        doc_files=[DocFile(path=p, name=p.split("/")[-1], text=t) for p, t in docs],
        issues=[
            {"number": 3, "title": "Add example", "body": "show sample", "state": "open",
             "labels": [{"name": "good first issue"}], "pull_request": None},
        ],
        commits_30d=8,
        file_tree=["README.md", "src/lib.py", "tests/test_lib.py"],
    )


def test_guide_route_heuristic(monkeypatch):
    monkeypatch.setattr("backend.api.routes.guide.recon", lambda o, r, client=None: _fake_signals())
    monkeypatch.setattr(
        "backend.api.routes.guide.enrich_docs_and_tree", lambda s, client=None: s
    )
    c = TestClient(app)
    r = c.post("/api/guide", json={"url": "o/lib", "use_llm": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["owner"] == "o"
    assert body["repo"] == "lib"
    assert body["unsuitable"] is False
    assert body["steps"], "guide should contain steps"
    # Steps reference at least setup stage.
    assert any(s["stage"] == "A" for s in body["steps"])
    # Every step carries evidence with a valid kind.
    for s in body["steps"]:
        assert s["evidence"]["kind"] in {"file", "issue", "missing"}
    # Serialisable roundtrip is implied by response_model.


def test_guide_route_rejects_bad_url():
    c = TestClient(app)
    r = c.post("/api/guide", json={"url": "https://example.com/x"})
    assert r.status_code == 422
