import httpx
import pytest
from backend.core.generate.llm import LLMClient, LLMUnavailable

def test_service_retry_is_bounded_and_does_not_retry_auth_or_rate_limit(monkeypatch):
    monkeypatch.setattr('time.sleep',lambda *_:None)
    for status in (401,403,429,502,503,504):
        c=LLMClient(timeout_s=20,retry_limit=0,disconnect_retry_limit=1,service_retry_limit=1);c._key='test-placeholder'
        def fail(*a,**k):
            r=httpx.Response(status,request=httpx.Request('POST','https://example.invalid'));r.raise_for_status()
        monkeypatch.setattr(httpx,'post',fail)
        with pytest.raises(LLMUnavailable):c.chat_json([])
        assert c.attempt_count==(2 if status in (502,503,504) else 1)
        assert c.service_retry_count==(1 if status in (502,503,504) else 0)

def test_service_and_disconnect_share_one_recovery_budget(monkeypatch):
    c=LLMClient(timeout_s=20,retry_limit=0,disconnect_retry_limit=1,service_retry_limit=1);c._key='test-placeholder'
    errors=iter([httpx.RemoteProtocolError('fixture'),httpx.HTTPStatusError('fixture',request=httpx.Request('POST','https://example.invalid'),response=httpx.Response(503))])
    def mixed(*a,**k):raise next(errors)
    monkeypatch.setattr(httpx,'post',mixed)
    with pytest.raises(LLMUnavailable):c.chat_json([])
    assert c.attempt_count==2 and c.disconnect_retry_count==1 and c.service_retry_count==0

def test_service_recovers_with_only_the_remaining_wait(monkeypatch):
    clock=[0.0];waits=[]
    monkeypatch.setattr('time.perf_counter',lambda:clock[0])
    monkeypatch.setattr('time.sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    c=LLMClient(timeout_s=25,retry_limit=0,service_retry_limit=1);c._key='test-placeholder'
    def post(*a,**kw):
        waits.append(kw['timeout']);clock[0]+=3
        return httpx.Response(503 if len(waits)==1 else 200,request=httpx.Request('POST','https://example.invalid'),
            json={'choices':[{'message':{'content':'{"ok":true}'}}]})
    monkeypatch.setattr(httpx,'post',post)
    assert c.chat_json([])=={'ok':True}
    assert waits==[25,21.75] and c.service_retry_count==1 and c.attempt_count==2

def test_question_preserves_verified_points_while_discarding_invented_operations():
    from backend.core.ask.service import AnswerSource, _model_points
    source=AnswerSource(id='S1',kind='file',source='README.md',quote='Use Python 3.12 for development.',url='https://example.invalid')
    bad={'text':'运行 pip install fabricated-package 即可。','source_id':'S1','quote':source.quote}
    good={'text':'开发环境需按说明核对 Python 3.12 版本。','source_id':'S1','quote':source.quote}
    rejected=[]
    points=_model_points({'points':[bad,good]},[source],rejected=rejected)
    assert len(points)==1 and points[0].text==good['text'] and len(rejected)==1
    with pytest.raises(LLMUnavailable):_model_points({'points':[bad,good]},[source])

def test_tool_name_in_chinese_prose_is_not_an_unverified_command():
    from backend.core.ask.service import AnswerSource, _model_points
    source=AnswerSource(id='S1',kind='file',source='README.md',quote='Run pytest and inspect test output.',url='https://example.invalid')
    result=_model_points({'points':[{'text':'请核对 pytest 的实际输出，再判断测试情况。','source_id':'S1','quote':source.quote}]},[source])
    assert len(result)==1
    with pytest.raises(LLMUnavailable):
        _model_points({'points':[{'text':'请运行 pytest invented_tests 并提交结果。','source_id':'S1','quote':source.quote}]},[source])

def test_valid_looking_json_is_rejected_when_provider_reports_truncation(monkeypatch):
    c=LLMClient(retry_limit=0);c._key='test-placeholder'
    monkeypatch.setattr(httpx,'post',lambda *a,**k:httpx.Response(200,request=httpx.Request('POST','https://example.invalid'),
        json={'choices':[{'message':{'content':'{"ok":true}'},'finish_reason':'length'}]}))
    with pytest.raises(LLMUnavailable,match='输出上限'):c.chat_json([])
    assert c.attempt_count==1 and c.trace[0]['finish_reason']=='length'
