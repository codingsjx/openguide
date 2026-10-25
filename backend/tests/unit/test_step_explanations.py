import json
from math import ceil
import pytest
import httpx
from backend.core.generate.pipeline import build_guide
from backend.core.generate.llm import LLMUnavailable
from backend.core.generate.schemas import Guide
from test_ai_workflow_retention import signals

TEXT = '先核对这一步的前置条件，再按页面中的原文操作核对结果；这是通用准备说明，实际运行后才能记录完成。'

class Explainer:
    def __init__(self, broken=False): self.calls = []; self.broken = broken
    def available(self): return True
    def chat_json(self, messages, **kwargs):
        payload = json.loads(messages[-1]['content']); self.calls.append(payload)
        items = [{'step_id': s['step_id'], 'text': TEXT} for s in payload['entries']]
        if self.broken and len(self.calls) == 1:
            items[0]['text'] = '请运行 pip install invented-package 解决所有问题。'
        return {'explanations': items}

def operations(g):
    return [{k:v for k,v in s.model_dump().items() if not k.startswith('ai_explanation')} for s in g.steps]

def test_every_step_can_receive_ai_tutoring_without_changing_any_operation():
    baseline = build_guide(signals(), use_llm=False, check_suitability=False)
    model = Explainer()
    result = build_guide(signals(), llm_client=model, explain_steps=True, check_suitability=False)
    assert operations(result) == operations(baseline)
    assert all(s.ai_explanation for s in result.steps)
    assert set(result.stage_modes.values()) == {'mixed'}
    assert result.generation_strategy == 'source_then_explain' and not result.stage_fallbacks
    assert all(s.ai_explanation_basis == 'general' for s in result.steps if s.evidence.kind == 'missing')
    assert any(s.stage == 'C' and s.ai_explanation for s in result.steps)
    Guide.model_validate(result.model_dump())

def test_only_rejected_ids_are_retried_and_good_notes_survive():
    model = Explainer(broken=True)
    g = build_guide(signals(), llm_client=model, explain_steps=True, check_suitability=False)
    assert len(model.calls) == ceil(len(g.steps) / 6) + 1
    assert [s['step_id'] for s in model.calls[1]['entries']] == [model.calls[0]['entries'][0]['step_id']]
    assert all(s.ai_explanation == TEXT for s in g.steps)
    assert 'invented-package' not in g.model_dump_json()

@pytest.mark.parametrize('extra', [{'command':'pip install forged'}, {'source':'invented.md'}])
def test_model_cannot_smuggle_operational_changes(extra):
    class Forged(Explainer):
        def chat_json(self,messages,**kwargs):
            obj = super().chat_json(messages,**kwargs)
            for item in obj['explanations']: item.update(extra)
            return obj
    g = build_guide(signals(),llm_client=Forged(),explain_steps=True,check_suitability=False)
    assert not any(s.ai_explanation for s in g.steps)
    assert all(s.generation_source == 'rules' for s in g.steps)
    assert g.generation_mode == 'heuristic'

def test_timeout_does_not_trigger_an_additional_content_retry():
    class Unavailable(Explainer):
        def chat_json(self, messages, **kwargs):
            self.calls.append(messages)
            raise LLMUnavailable('safe failure') from httpx.ReadTimeout('fixture')
    model=Unavailable()
    g=build_guide(signals(),llm_client=model,explain_steps=True,check_suitability=False)
    assert len(model.calls)==ceil(len(g.steps) / 6) and set(g.stage_fallbacks.values())=={'model_timeout'}
    assert not any(s.ai_explanation for s in g.steps)

def test_research_ignores_product_explanation_option():
    from test_ai_workflow_retention import PartialModel
    model=PartialModel()
    g=build_guide(signals(),llm_client=model,strict_llm=True,explain_steps=True,check_suitability=False)
    assert model.calls==list('ABCD') and not any(s.ai_explanation for s in g.steps)

def test_duplicate_ids_and_fabricated_versions_are_not_accepted():
    class Duplicate(Explainer):
        def chat_json(self,messages,**kwargs):
            obj=super().chat_json(messages,**kwargs)
            obj['explanations'][0]['text']='需要使用 Python 99.81 才能继续，这是通用检查。'
            obj['explanations'].append(dict(obj['explanations'][0]))
            return obj
    g=build_guide(signals(),llm_client=Duplicate(),explain_steps=True,check_suitability=False)
    assert not g.steps[0].ai_explanation and any(s.ai_explanation for s in g.steps[1:])
    assert '99.81' not in g.model_dump_json()

def test_explicit_denial_and_verified_context_paths_do_not_trigger_false_rejection():
    from backend.core.generate.explanations import _checked_text
    g=build_guide(signals(),use_llm=False,check_suitability=False)
    step=next(s for s in g.steps if s.command=='uv run pytest tests/ -q')
    assert _checked_text('先核对 backend/tests 的实际测试范围，来源匹配不代表测试已通过。',step)
    assert _checked_text('来源已经存在，测试已通过，可以直接提交改动。',step) is None
    assert _checked_text('不代表失败，但测试已通过，可以直接提交改动。',step) is None
    assert _checked_text('请查看 backend/invented.py 并核对这个文件的要求。',step) is None
    assert _checked_text('请查看backend/invented.py并核对这个文件的要求。',step) is None
    assert _checked_text('运行测试后核对 pytest 的输出，来源匹配不代表测试已通过。',step)
    generic=next(s for s in g.steps if s.stage=='D')
    assert _checked_text('先核对维护者要求，再按通用流程整理实际修改和验证记录。',generic)
    assert _checked_text('维护者要求先签署许可，这是通用准备的必要条件。',generic) is None

def test_only_same_component_existing_manifests_and_exact_operations_are_allowed():
    from backend.core.generate.explanations import _checked_text, _context_paths
    sig=signals();sig.file_tree.append('frontend/pnpm-lock.yaml')
    g=build_guide(sig,use_llm=False,check_suitability=False)
    step=next(s for s in g.steps if s.command=='pnpm install')
    paths=_context_paths(step,sig)
    assert 'package.json' in paths and 'pnpm-lock.yaml' in paths
    assert _checked_text('先核对 package.json 和 pnpm-lock.yaml，再按原文准备当前组件的依赖。',step,paths)
    assert _checked_text('按原文运行 pnpm install，再核对依赖准备过程是否正常结束。',step,paths)
    assert _checked_text('按原文运行 pnpm install --invented，再核对实际结果。',step,paths) is None
    assert _checked_text('按原文运行 pnpm install invented-package，再核对实际结果。',step,paths) is None
    assert _checked_text('核对 backend/pyproject.toml 再准备当前组件的依赖。',step,paths) is None

def test_large_workflow_stops_at_total_wait_budget_and_restores_client_setting(monkeypatch):
    from backend.core.generate.explanations import explain_guide
    from backend.core.generate.schemas import GuideStep
    clock=[0.0];monkeypatch.setattr('time.monotonic',lambda:clock[0])
    class Clocked(Explainer):
        _timeout_s=1.0
        def chat_json(self,*args,**kwargs):
            clock[0]+=self._timeout_s
            return super().chat_json(*args,**kwargs)
    g=Guide(repo_url='https://github.com/o/r',steps=[GuideStep(step_id=i,stage='D',title='通用准备') for i in range(1,26)])
    client=Clocked();explain_guide(g,client,signals())
    assert len(client.calls)==4 and client._timeout_s==1
    assert sum(bool(s.ai_explanation) for s in g.steps)==24
    assert g.stage_fallbacks['D']=='model_timeout'
