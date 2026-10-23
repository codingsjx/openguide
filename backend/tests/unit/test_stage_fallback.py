"""Synthetic outages verify retention/accounting, not real model quality."""
import pytest
import re

from backend.core.generate.pipeline import build_guide
from backend.core.generate.llm import LLMUnavailable
from backend.core.github.models import RepoMeta, DocFile
from backend.core.github.recon import RawSignals


def signals():
    texts = {
        'README.md': '# Setup\ngit clone https://github.com/o/r.git\npython -m venv .venv\npip install -e .[dev]\n',
        'Makefile': 'test:\n\tpython -m pytest tests\n',
        'CONTRIBUTING.md': '# Contributions\nFork the repository and create a branch.\nRun tests before submitting changes.\nOpen a pull request and follow the template.\nDiscuss changes during review.\n',
    }
    return RawSignals(meta=RepoMeta(owner='o', repo='r', license='MIT'),
        doc_files=[DocFile(path=p,name=p,text=t) for p,t in texts.items()],
        file_tree=list(texts) + ['tests/test_example.py'])


class Model:
    def __init__(self, failing=('B',), empty=()):
        self.failing, self.empty, self.calls = failing, empty, []
    def available(self): return True
    def chat_json(self, *args, **kwargs):
        stage = re.search(r'Stage ([ABCD])', args[0][-1]['content'])[1]
        self.calls.append(stage)
        if stage in self.failing:
            raise LLMUnavailable('synthetic timeout')
        if stage in self.empty:
            return {'steps': []}
        evidence = {'kind':'missing'}
        if stage == 'A':
            evidence = {'kind':'file','source':'README.md','quote':'pip install -e .[dev]'}
        elif stage == 'D':
            evidence = {'kind':'file','source':'CONTRIBUTING.md','quote':'Fork the repository and create a branch.'}
        return {'steps': [{'title': f'Preserved AI {stage}',
            'command':'pip install -e .[dev]' if stage=='A' else None,'evidence': evidence}]}


def generate(client=None, **kwargs):
    return build_guide(signals(), llm_client=client, check_suitability=False, **kwargs)


def test_one_failed_stage_retains_successful_output_and_continues():
    model = Model()
    guide = generate(model)
    assert model.calls == list('ABD')
    assert guide.stage_fallbacks['C'] == 'no_stage_evidence'
    assert guide.generation_mode == 'mixed'
    assert guide.stage_modes == {'A':'llm','B':'heuristic','C':'heuristic','D':'llm'}
    assert {s.title for s in guide.steps if s.stage in ('A', 'D')} == {'Preserved AI A','Preserved AI D'}
    assert '检索入口' in next(s.title for s in guide.steps if s.stage == 'C')
    assert guide.issue_discovery.status == 'empty'
    test = next(s for s in guide.steps if s.stage == 'B')
    assert test.command == 'python -m pytest tests'
    assert test.evidence.verification == 'command_verified'
    assert any('测试基线' in warning for warning in guide.warnings)


def test_strict_evaluation_still_raises_instead_of_using_rules():
    model = Model()
    with pytest.raises(LLMUnavailable): generate(model, strict_llm=True)
    assert model.calls == ['A','B']


def test_empty_stage_is_locally_replaced():
    guide = generate(Model(failing=(), empty=('D',)))
    assert guide.stage_modes['D'] == 'heuristic'
    assert guide.stage_fallbacks['D'] == 'invalid_output'
    assert any(s.stage == 'D' and s.evidence.verification == 'quote_verified' for s in guide.steps)


def test_all_failures_and_rule_only_keep_all_stages():
    for guide in (generate(Model(failing='ABCD')), generate(use_llm=False)):
        assert guide.generation_mode == 'heuristic'
        assert {s.stage for s in guide.steps} == set('ABCD')
        setup = [s.command for s in guide.steps if s.stage == 'A' and s.command]
        assert 'git clone https://github.com/o/r.git' in setup
        assert 'pip install -e .[dev]' in setup
        assert all(s.command is None for s in guide.steps if s.stage == 'D')
        assert len({s.step_id for s in guide.steps}) == len(guide.steps)


def test_no_sources_produces_pending_items_instead_of_invented_commands():
    guide = build_guide(RawSignals(meta=RepoMeta(owner='o',repo='empty')), use_llm=False, check_suitability=False)
    assert {s.stage for s in guide.steps} == set('ABCD')
    assert all(s.command is None and s.evidence.kind == 'missing' for s in guide.steps)


def test_audited_clone_cannot_remove_pr_entry_point():
    class CloneInPR(Model):
        def chat_json(self, *args, **kwargs):
            stage = re.search(r'Stage ([ABCD])', args[0][-1]['content'])[1]
            if stage == 'D':
                self.calls.append(stage)
                return {'steps':[{'title':'Clone in wrong stage',
                    'command':'git clone https://github.com/o/r.git',
                    'evidence':{'kind':'file','source':'README.md'}}]}
            return super().chat_json(*args, **kwargs)
    guide = generate(CloneInPR(failing=()))
    assert {s.stage for s in guide.steps} == set('ABCD')
    assert guide.stage_modes['D'] == 'heuristic'
    assert all(not s.command for s in guide.steps if s.stage == 'D')


def test_tox_templates_and_publish_environments_are_not_direct_setup_commands():
    from backend.core.generate.heuristic import generate_stage
    from backend.core.generate.pipeline import _STAGE_CMD_PATTERNS
    sig = RawSignals(meta=RepoMeta(owner='o',repo='r'),doc_files=[
        DocFile(path='Makefile',name='Makefile',text='python -m venv .publishenv\npython -m pip install -r requirements-dev.txt\n'),
        DocFile(path='tox.ini',name='tox.ini',text='pytest {posargs:tests}\n')])
    snippets=[{'source':d.path,'text':d.text,'meta_kind':'file'} for d in sig.doc_files]
    setup=generate_stage(sig,'A',snippets,_STAGE_CMD_PATTERNS['A'])
    tests=generate_stage(sig,'B',snippets,_STAGE_CMD_PATTERNS['B'])
    assert not any(s.command and 'publish' in s.command for s in setup)
    assert all(s.command is None for s in tests)


def test_placeholder_clone_and_version_queries_are_not_onboarding_commands():
    from backend.core.generate.heuristic import generate_stage
    from backend.core.generate.pipeline import _STAGE_CMD_PATTERNS
    text='git clone git@github.com:your_name_here/repo.git\nnox --version\npytest -k TestFindHooks\n'
    sig=RawSignals(meta=RepoMeta(owner='o',repo='r'),doc_files=[DocFile(path='CONTRIBUTING.md',name='CONTRIBUTING.md',text=text)])
    snippets=[{'source':'CONTRIBUTING.md','text':text}]
    setup=generate_stage(sig,'A',snippets,_STAGE_CMD_PATTERNS['A'])
    tests=generate_stage(sig,'B',snippets,_STAGE_CMD_PATTERNS['B'])
    assert all(s.command is None for s in setup)
    assert tests[0].command=='pytest -k TestFindHooks'
    assert '局部测试' in tests[0].title


def test_product_replaces_unsubstantiated_pr_stage_but_strict_model_keeps_it():
    class UnsupportedPR(Model):
        def chat_json(self, *args, **kwargs):
            result = super().chat_json(*args, **kwargs)
            if self.calls[-1] == 'D':
                result['steps'][0]['evidence'] = {'kind':'missing'}
            return result
    product = generate(UnsupportedPR(failing=()))
    assert product.stage_modes['D'] == 'heuristic'
    assert all(s.evidence.verification == 'quote_verified' for s in product.steps if s.stage == 'D')
    strict = generate(UnsupportedPR(failing=()), strict_llm=True)
    assert strict.stage_modes['D'] == 'llm'
    assert any(s.stage == 'D' and s.evidence.kind == 'missing' for s in strict.steps)


def test_special_ci_install_is_not_a_required_setup_command():
    from backend.core.generate.pipeline import audit_steps, _build_index
    from backend.core.generate.schemas import GuideStep, Evidence
    sig=signals()
    path='.github/workflows/typecheck.yml'
    sig.doc_files.append(DocFile(path=path,name='typecheck.yml',text='run: python -m pip install -e . --group typecheck'))
    step=GuideStep(step_id=1,stage='A',title='Install project',command='python -m pip install -e . --group typecheck',evidence=Evidence(source=path))
    result=audit_steps(sig,_build_index(sig),[step])[0]
    assert result.command is None and '专项 CI' in result.expected


def test_user_selected_rules_are_not_reported_as_model_failure():
    guide = generate(use_llm=False)
    assert guide.requested_mode == 'rules'
    assert not guide.stage_fallbacks


def test_missing_configuration_is_explicit_for_all_stages():
    class NotConfigured:
        def available(self): return False
    guide = generate(NotConfigured())
    assert guide.requested_mode == 'ai'
    assert guide.stage_fallbacks == {s:'not_configured' for s in 'ABCD'}


def test_timeout_and_unverified_evidence_have_separate_safe_reasons():
    import httpx
    class Timeout(Model):
        def chat_json(self, *args, **kwargs):
            if len(self.calls) == 1:
                self.calls.append('B')
                raise LLMUnavailable('private provider details') from httpx.ReadTimeout('fixture timeout')
            return super().chat_json(*args, **kwargs)
    guide = generate(Timeout())
    assert guide.stage_fallbacks['B'] == 'model_timeout'
    assert guide.stage_fallbacks['C'] == 'no_stage_evidence'
    assert 'private provider details' not in guide.model_dump_json()


@pytest.mark.parametrize('status,expected', [(401,'model_auth_failed'), (403,'model_auth_failed'), (429,'model_rate_limited')])
def test_provider_failures_export_only_safe_categories(status, expected):
    import httpx
    from backend.core.generate.pipeline import _fallback_reason
    request = httpx.Request('POST', 'https://provider.invalid/private')
    cause = httpx.HTTPStatusError('private failure', request=request, response=httpx.Response(status,request=request))
    error = LLMUnavailable('private provider details'); error.__cause__ = cause
    assert _fallback_reason(error) == expected
