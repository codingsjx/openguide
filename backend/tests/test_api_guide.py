"""API tests for /api/guide using hermetic patches (no network, no LLM)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.generate.schemas import Guide
import pytest


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
    assert body['issue_discovery']['candidates'][0]['url'] == 'https://github.com/o/lib/issues/3'
    assert body['issue_discovery']['search_links']
    assert body['requested_mode'] == 'rules' and not body['stage_fallbacks']
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


@pytest.mark.parametrize('seconds', [None,10,60,120])
def test_selected_timeout_reaches_model_client_and_export(monkeypatch,seconds):
    monkeypatch.setattr('backend.api.routes.guide.recon',lambda *a,**k:_fake_signals())
    monkeypatch.setattr('backend.api.routes.guide.enrich_docs_and_tree',lambda s,**k:s)
    received={}
    def model(**kwargs):
        received.update(kwargs)
        return object()
    monkeypatch.setattr('backend.api.routes.guide.LLMClient',model)
    monkeypatch.setattr('backend.api.routes.guide.build_guide',lambda *a,**k:Guide(repo_url='https://github.com/o/lib'))
    body={'url':'o/lib'}
    if seconds is not None: body['model_timeout_s']=seconds
    response=TestClient(app).post('/api/guide',json=body)
    assert response.status_code==200,response.text
    assert received['timeout_s']==(25 if seconds is None else seconds)
    assert received['retry_limit']==0
    assert response.json()['model_timeout_s']==(25 if seconds is None else seconds)


@pytest.mark.parametrize('seconds', [0,9,121,100000,25.5,'invalid'])
def test_invalid_timeout_is_rejected_before_any_github_or_model_request(monkeypatch,seconds):
    def unexpected(*a,**k): raise AssertionError('must validate before network calls')
    monkeypatch.setattr('backend.api.routes.guide.GitHubClient',unexpected)
    response=TestClient(app).post('/api/guide',json={'url':'o/lib','model_timeout_s':seconds})
    assert response.status_code==422


def test_rules_request_does_not_instantiate_model_client(monkeypatch):
    monkeypatch.setattr('backend.api.routes.guide.recon',lambda *a,**k:_fake_signals())
    monkeypatch.setattr('backend.api.routes.guide.enrich_docs_and_tree',lambda s,**k:s)
    def unexpected(**kwargs): raise AssertionError('rules do not call the model')
    monkeypatch.setattr('backend.api.routes.guide.LLMClient',unexpected)
    response=TestClient(app).post('/api/guide',json={'url':'o/lib','use_llm':False,'model_timeout_s':120})
    assert response.status_code==200,response.text
    assert response.json()['model_timeout_s'] is None
