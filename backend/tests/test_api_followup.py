"""Follow-up revision, schema and evidence contract without network/model calls."""
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.core.github.recon import RawSignals
from backend.core.github.models import RepoMeta, DocFile


def test_followup_preserves_stage_and_fixed_revision(monkeypatch):
    sha = 'b' * 40
    sig = RawSignals(meta=RepoMeta(owner='o', repo='r'), doc_files=[
        DocFile(path='CONTRIBUTING.md', name='CONTRIBUTING.md', text='Fork branch commit push PR.')])
    monkeypatch.setattr('backend.api.routes.followup.recon', lambda *a, **k: sig)
    def enrich(signals, **kwargs):
        assert signals.meta.default_branch == sha
        return signals
    monkeypatch.setattr('backend.api.routes.followup.enrich_docs_and_tree', enrich)
    response = TestClient(app).post('/api/followup', json={
        'url':'o/r', 'intent':'granular', 'revision':sha,
        'step':{'stage':'D','title':'Fork branch commit PR'}})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['revision'] == sha
    assert data['evidence'][0]['source'] == 'CONTRIBUTING.md'
    assert data['evidence'][0]['verification'] == 'quote_verified'


def test_invalid_followup_step_is_not_silently_changed_to_stage_a():
    response = TestClient(app).post('/api/followup', json={
        'url':'o/r','intent':'granular','step':{'stage':'invalid','title':'Test'}})
    assert response.status_code == 422


def test_diagnose_uses_interactive_timeout_without_retries(monkeypatch):
    from backend.core.followup.service import FollowupResult
    sig = RawSignals(meta=RepoMeta(owner='o', repo='r'))
    monkeypatch.setattr('backend.api.routes.followup.recon', lambda *a, **k: sig)
    monkeypatch.setattr('backend.api.routes.followup.enrich_docs_and_tree', lambda s, **k: s)
    def diagnose(index, step, log, client):
        assert client._timeout_s == 25.0 and client._retry_limit == 0
        return FollowupResult(intent='diagnose', text='fixture only', mode='rules')
    monkeypatch.setattr('backend.api.routes.followup.diagnose', diagnose)
    response = TestClient(app).post('/api/followup', json={
        'url':'o/r', 'intent':'diagnose', 'step':{'stage':'B','title':'Tests'}, 'log_text':'fixture'})
    assert response.status_code == 200


def test_github_outage_does_not_block_local_path_diagnosis(monkeypatch):
    from backend.core.github.client import GitHubClientError
    def unavailable(*args, **kwargs): raise GitHubClientError('fixture outage')
    monkeypatch.setattr('backend.api.routes.followup.recon', unavailable)
    response = TestClient(app).post('/api/followup', json={
        'url':'o/r','intent':'diagnose','revision':'b' * 40,
        'step':{'stage':'B','title':'Run tests'},
        'log_text':'OSError: Could not find a suitable TLS CA certificate bundle, invalid path: tests/certs/ca.crt'})
    assert response.status_code == 200
    body = response.json()
    assert body['revision'] == 'b' * 40
    assert len(body['local_checks']) == 3 and not body['evidence']
    assert any('仓库资料暂时无法取得' in w for w in body['warnings'])
