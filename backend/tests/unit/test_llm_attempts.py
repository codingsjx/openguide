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
