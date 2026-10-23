from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.github.models import RepoMeta, DocFile
from backend.core.github.recon import RawSignals
from backend.core.github.client import GitHubClientError
import pytest


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


@pytest.mark.parametrize('seconds',[None,10,60,120])
def test_question_wait_setting_reaches_one_model_attempt(monkeypatch,seconds):
    from backend.core.ask.service import AnswerResult
    sig=RawSignals(meta=RepoMeta(owner='o',repo='r'))
    monkeypatch.setattr('backend.api.routes.ask.recon',lambda *a,**k:sig)
    monkeypatch.setattr('backend.api.routes.ask.enrich_docs_and_tree',lambda s,**k:s)
    def answer(sig,index,question,history,client):
        assert client._timeout_s==(40 if seconds is None else seconds)
        assert client._retry_limit==0
        return AnswerResult(repo_url='https://github.com/o/r',question=question,resolved_question=question)
    monkeypatch.setattr('backend.api.routes.ask.answer_question',answer)
    body={'url':'o/r','question':'tests?'}
    if seconds is not None:body['model_timeout_s']=seconds
    assert TestClient(app).post('/api/ask',json=body).status_code==200


@pytest.mark.parametrize('seconds',[0,121,10.5])
def test_invalid_question_wait_setting_is_rejected_before_network(monkeypatch,seconds):
    monkeypatch.setattr('backend.api.routes.ask.recon',lambda *a,**k:pytest.fail('unexpected network collection'))
    assert TestClient(app).post('/api/ask',json={'url':'o/r','question':'tests?','model_timeout_s':seconds}).status_code==422
