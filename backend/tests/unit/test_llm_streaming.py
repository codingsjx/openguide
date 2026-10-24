from contextlib import contextmanager
import json
import httpx
import pytest
from backend.core.generate.llm import LLMClient,LLMUnavailable


def install_stream(monkeypatch,body,content_type='text/event-stream'):
    @contextmanager
    def stream(*a,**kw):
        assert kw['json']['stream'] is True
        response=httpx.Response(200,headers={'content-type':content_type},content=body,request=httpx.Request('POST','https://example.invalid'))
        try:yield response
        finally:response.close()
    monkeypatch.setattr(httpx,'stream',stream)


def client():
    c=LLMClient(stream_json=True,retry_limit=0,disconnect_retry_limit=1);c._key='test-placeholder';return c


def event(data):return 'data: '+json.dumps(data)+'\n\n'


def test_stream_assembles_only_visible_json_and_retains_usage_and_provenance(monkeypatch):
    body=event({'id':'fixture-id','model':'provider-model','choices':[{'index':0,'delta':{'reasoning_content':'private hidden reasoning','content':'{"steps":'}}]})
    body+=event({'choices':[{'index':0,'delta':{'content':'[]}'},'finish_reason':'stop'}]})
    body+=event({'choices':[],'usage':{'total_tokens':123}})+'data: [DONE]\n\n'
    install_stream(monkeypatch,body)
    c=client();assert c.chat_json([])=={'steps':[]}
    assert c.trace[0]['content']=='{"steps":[]}' and c.trace[0]['usage']['total_tokens']==123
    assert c.trace[0]['response_streamed'] and c.trace[0]['response_id']=='fixture-id'
    assert 'private hidden reasoning' not in str(c.trace)
    assert c.attempt_count==1


@pytest.mark.parametrize('suffix',['',event({'choices':[{'delta':{},'finish_reason':'length'}]})+'data: [DONE]\n\n'])
def test_stream_without_completion_or_truncated_generation_is_not_accepted(monkeypatch,suffix):
    install_stream(monkeypatch,event({'choices':[{'delta':{'content':'{"steps":[]}'}}]})+suffix)
    c=client()
    with pytest.raises(LLMUnavailable):c.chat_json([])
    assert c.attempt_count==1 and c.disconnect_retry_count==0


def test_provider_ignoring_stream_can_return_a_complete_normal_json_response(monkeypatch):
    install_stream(monkeypatch,json.dumps({'choices':[{'message':{'content':'{"steps":[]}'}}]}),'application/json')
    c=client();assert c.chat_json([])=={'steps':[]}
    assert not c.trace[0]['response_streamed'] and c.trace[0]['usage']=={}


def test_partial_stream_connection_failure_never_reissues_product_request(monkeypatch):
    class Broken(httpx.SyncByteStream):
        def __iter__(self):
            yield event({'choices':[{'delta':{'content':'{"steps":['}}]}).encode()
            raise httpx.RemoteProtocolError('fixture interrupted output')
    @contextmanager
    def stream(*a,**kw):
        response=httpx.Response(200,headers={'content-type':'text/event-stream'},stream=Broken(),request=httpx.Request('POST','https://example.invalid'))
        try:yield response
        finally:response.close()
    monkeypatch.setattr(httpx,'stream',stream)
    c=client()
    with pytest.raises(LLMUnavailable):c.chat_json([])
    assert c.attempt_count==1 and c.disconnect_retry_count==0 and not c.trace
