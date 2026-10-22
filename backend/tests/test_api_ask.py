from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.github.models import RepoMeta, DocFile
from backend.core.github.recon import RawSignals
from backend.core.github.client import GitHubClientError


def test_fixed_revision_and_question_history_are_preserved(monkeypatch):
    sig=RawSignals(meta=RepoMeta(owner='o',repo='r'),doc_files=[DocFile(path='Makefile',name='Makefile',text='test:\n\tpython -m pytest tests')],file_tree=['tests/unit.py'])
    monkeypatch.setattr('backend.api.routes.ask.recon',lambda *a,**k:sig)
    def enrich(signals,**kwargs):
        assert signals.meta.default_branch=='b'*40
        return signals
    monkeypatch.setattr('backend.api.routes.ask.enrich_docs_and_tree',enrich)
    response=TestClient(app).post('/api/ask',json={'url':'o/r','question':'这条命令在哪里执行？','history':['测试怎么运行？'],'revision':'b'*40,'use_llm':False})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['context_used'] and result['revision']=='b'*40
    assert result['commands'][0]['command']=='python -m pytest tests'
    assert '/blob/'+'b'*40+'/' in result['sources'][0]['url']


def test_collection_outage_returns_next_step_without_fabricated_answer(monkeypatch):
    def unavailable(*args,**kwargs): raise GitHubClientError('fixture outage')
    monkeypatch.setattr('backend.api.routes.ask.recon',unavailable)
    response=TestClient(app).post('/api/ask',json={'url':'o/r','question':'如何安装？'})
    assert response.status_code==200
    data=response.json()
    assert data['status']=='unavailable' and not data['points'] and not data['sources']
    assert data['next_actions'] and data['links']


def test_history_and_question_limits_and_bad_repository_are_rejected():
    client=TestClient(app)
    for body in [
        {'url':'https://evil.test/o/r','question':'install'},
        {'url':'o/r','question':' '},
        {'url':'o/r','question':'x'*2001},
        {'url':'o/r','question':'install','history':['q']*7},
        {'url':'o/r','question':'install','revision':'main'},
    ]:
        assert client.post('/api/ask',json=body).status_code==422
