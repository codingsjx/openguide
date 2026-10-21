"""Synthetic outages verify retention/accounting, not real model quality."""
import pytest

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
        stage = 'ABCD'[len(self.calls)]
        self.calls.append(stage)
        if stage in self.failing:
            raise LLMUnavailable('synthetic timeout')
        if stage in self.empty:
            return {'steps': []}
        return {'steps': [{'title': f'Preserved AI {stage}', 'evidence': {'kind':'missing'}}]}


def generate(client=None, **kwargs):
    return build_guide(signals(), llm_client=client, check_suitability=False, **kwargs)


def test_one_failed_stage_retains_successful_output_and_continues():
    model = Model()
    guide = generate(model)
    assert model.calls == list('ABCD')
    assert guide.generation_mode == 'mixed'
    assert guide.stage_modes == {'A':'llm','B':'heuristic','C':'llm','D':'llm'}
    assert {s.title for s in guide.steps if s.stage != 'B'} == {'Preserved AI A','Preserved AI C','Preserved AI D'}
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
            stage = 'ABCD'[len(self.calls)]
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
