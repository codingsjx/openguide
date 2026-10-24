"""No network: page settings cannot overwrite another page or the CLI."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.generate import llm, session


def defaults(monkeypatch):
    monkeypatch.setattr(llm, 'get_settings', lambda: SimpleNamespace(llm_api_key='', llm_base_url='https://example.invalid/v1', llm_model='server-default'))
    monkeypatch.setattr(llm, '_OVERRIDE_KEY', '')
    monkeypatch.setattr(llm, '_OVERRIDE_BASE', '')
    monkeypatch.setattr(llm, '_OVERRIDE_MODEL', '')
    monkeypatch.setattr(session, '_settings', session.OrderedDict())


def test_http_settings_are_page_scoped_and_credentials_never_returned(monkeypatch):
    defaults(monkeypatch)
    client=TestClient(app)
    a={'X-OpenGuide-Session':'a'*32};b={'X-OpenGuide-Session':'b'*32}
    assert not client.get('/api/llm-config',headers=a).json()['configured']
    response=client.post('/api/llm-config',headers=a,json={'api_key':'test-only-credential-a','base_url':'https://a.invalid/v1','model':'model-a'})
    assert response.status_code==200 and response.json()=={'configured':True}
    assert client.get('/api/llm-config',headers=a).json()['configured']
    assert not client.get('/api/llm-config',headers=b).json()['configured']
    assert not client.get('/api/llm-config').json()['configured']
    assert 'test-only-credential' not in response.text
    # Both threaded API handlers and LLMClient must see the same request scope.
    seen=[]
    def inspect():
        model=llm.LLMClient();seen.append((model._key,model._model));return model.available()
    monkeypatch.setattr('backend.api.routes.settings.llm_configured',inspect)
    client.get('/api/llm-config',headers=a);client.get('/api/llm-config',headers=b)
    assert seen==[('test-only-credential-a','model-a'),('','server-default')]
    assert session.active_session.get() is None


def test_missing_or_invalid_session_cannot_mutate_process_defaults(monkeypatch):
    defaults(monkeypatch);client=TestClient(app)
    assert client.post('/api/llm-config',json={'api_key':'test-only'}).status_code==422
    assert client.post('/api/llm-config',headers={'X-OpenGuide-Session':'invalid'},json={'api_key':'test-only'}).status_code==400
    assert not llm.llm_configured()


def test_concurrent_sessions_expire_and_memory_is_bounded(monkeypatch):
    defaults(monkeypatch)
    clock=[1.0];monkeypatch.setattr(session,'monotonic',lambda:clock[0])
    def use(i):
        token=session.active_session.set(f'{i:032x}')
        try:
            llm.configure_llm(api_key=f'test-only-{i}',model=f'model-{i}')
            assert llm.LLMClient()._key==f'test-only-{i}'
        finally:session.active_session.reset(token)
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(use,range(16)))
    assert not llm.llm_configured()
    for i in range(16,150):use(i)
    assert len(session._settings)==session.MAX_SESSIONS
    clock[0]+=session.TTL_SECONDS
    token=session.active_session.set(f'{149:032x}')
    try:assert not llm.llm_configured()
    finally:session.active_session.reset(token)
    assert not session._settings
