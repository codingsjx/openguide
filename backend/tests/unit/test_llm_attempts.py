import httpx
from backend.core.generate.llm import LLMClient


def test_json_fence_removal_is_lossless_and_does_not_repair_invalid_content():
    import pytest
    from backend.core.generate.llm import parse_json_object, LLMUnavailable
    obj, mode = parse_json_object('```json\n{"quote":"a\\nb", "steps":[]}\n```')
    assert obj['quote'] == 'a\nb' and mode == 'single_json_fence'
    for content in ('prefix\n```json\n{}\n```', '```json\n{}\n``` suffix', '{"quote":"a\nb"}', '```json\n{"steps":\n```'):
        with pytest.raises(LLMUnavailable): parse_json_object(content)


def test_product_linebreak_compatibility_keeps_values_and_rejects_truncation():
    import pytest
    from backend.core.generate.llm import parse_json_object, LLMUnavailable
    raw='{"quote":"line one\nline two\tend"}'
    obj, mode=parse_json_object(raw,allow_literal_linebreaks=True)
    assert obj['quote']=='line one\nline two\tend'
    assert mode=='literal_string_linebreaks'
    for broken in ('{"quote":"line\n', '{"quote":"line\x00other"}'):
        with pytest.raises(LLMUnavailable):parse_json_object(broken,allow_literal_linebreaks=True)


def test_interactive_timeout_does_not_retry(monkeypatch):
    import pytest
    import httpx
    from backend.core.generate.llm import LLMUnavailable
    client = LLMClient(timeout_s=25.0, retry_limit=0)
    client._key = 'test-placeholder'
    calls = []
    def fail(*args, **kwargs):
        calls.append(kwargs['timeout'])
        raise httpx.ReadTimeout('synthetic timeout')
    monkeypatch.setattr(httpx, 'post', fail)
    with pytest.raises(LLMUnavailable):
        client.chat_json([{'role': 'user', 'content': 'test'}])
    assert calls == [25.0]
    assert client.attempt_count == 1


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


def test_timing_records_never_log_keys_provider_urls_or_prompt_content(monkeypatch,caplog):
    import pytest
    from backend.core.generate.llm import LLMUnavailable
    client=LLMClient(timeout_s=40,retry_limit=0)
    client._key='private-test-key';client._base='https://provider.invalid/private-path'
    def fail(*a,**k):raise httpx.ReadTimeout('private provider diagnostic')
    monkeypatch.setattr(httpx,'post',fail)
    with pytest.raises(LLMUnavailable):client.chat_json([{'role':'user','content':'private prompt'}])
    assert client.request_events[0]['result']=='timeout'
    assert client.request_events[0]['elapsed_ms']>=0
    for value in ['private-test-key','private-path','private provider diagnostic','private prompt']:
        assert value not in caplog.text and value not in str(client.request_events)


def test_product_recovers_one_disconnect_with_remaining_wait_and_actual_accounting(monkeypatch):
    clock=[0.0];monkeypatch.setattr('time.perf_counter',lambda:clock[0])
    client=LLMClient(timeout_s=25,retry_limit=0,disconnect_retry_limit=1);client._key='test-placeholder'
    waits=[]
    def post(*a,**kw):
        waits.append(kw['timeout']);clock[0]+=3
        if len(waits)==1:raise httpx.RemoteProtocolError('private upstream disconnect')
        return httpx.Response(200,request=httpx.Request('POST','https://example.invalid'),json={'choices':[{'message':{'content':'{"steps":[]}'}}]})
    monkeypatch.setattr(httpx,'post',post)
    assert client.chat_json([{'role':'user','content':'test'}])=={'steps':[]}
    assert waits==[25,22] and client.attempt_count==2 and client.disconnect_retry_count==1
    assert client.trace[0]['disconnect_retries']==1
    assert client.request_events[0]['error_type']=='RemoteProtocolError'


def test_disconnect_recovery_never_retries_timeout_or_invalid_json(monkeypatch):
    import pytest
    from backend.core.generate.llm import LLMUnavailable
    for error in [httpx.ReadTimeout('fixture'),httpx.HTTPStatusError('fixture',request=httpx.Request('POST','https://example.invalid'),response=httpx.Response(401))]:
        client=LLMClient(timeout_s=25,retry_limit=0,disconnect_retry_limit=1);client._key='test-placeholder'
        def post(*a,**kw):raise error
        monkeypatch.setattr(httpx,'post',post)
        with pytest.raises(LLMUnavailable):client.chat_json([])
        assert client.attempt_count==1 and client.disconnect_retry_count==0
    client=LLMClient(retry_limit=0,disconnect_retry_limit=1);client._key='test-placeholder'
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:httpx.Response(200,request=httpx.Request('POST','https://example.invalid'),json={'choices':[{'message':{'content':'not JSON'}}]}))
    with pytest.raises(LLMUnavailable):client.chat_json([])
    assert client.attempt_count==1


def test_disconnect_recovery_is_bounded_and_research_default_stays_unchanged(monkeypatch):
    import pytest
    from backend.core.generate.llm import LLMUnavailable
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:(_ for _ in ()).throw(httpx.RemoteProtocolError('fixture')))
    for limit,expected in [(0,1),(1,2)]:
        client=LLMClient(timeout_s=25,retry_limit=0,disconnect_retry_limit=limit);client._key='test-placeholder'
        with pytest.raises(LLMUnavailable):client.chat_json([])
        assert client.attempt_count==expected
