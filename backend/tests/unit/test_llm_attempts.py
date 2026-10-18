import httpx
from backend.core.generate.llm import LLMClient


def test_retry_attempts_are_distinct_from_recorded_responses(monkeypatch):
    client = LLMClient(); client._key = 'test-placeholder'
    responses = iter([
        httpx.Response(500, request=httpx.Request('POST','https://provider.invalid')),
        httpx.Response(200, request=httpx.Request('POST','https://provider.invalid'), json={
            'id':'test-response','model':'provider-reported-model',
            'choices':[{'message':{'content':'{"steps": []}'}}], 'usage':{'total_tokens':10}}),
    ])
    monkeypatch.setattr(httpx,'post',lambda *args, **kwargs: next(responses))
    monkeypatch.setattr('time.sleep',lambda *_: None)
    assert client.chat_json([{'role':'user','content':'test'}],retries=1) == {'steps': []}
    assert client.attempt_count == 2 and len(client.trace) == 1
    assert client.trace[0]['response_id'] == 'test-response'
    assert client.trace[0]['attempt'] == 2
