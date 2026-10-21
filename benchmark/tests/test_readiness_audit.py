from backend.core.generate.pipeline import build_guide
from backend.core.github.recon import RawSignals
from backend.core.github.models import RepoMeta
from benchmark.readiness_audit import describe


def test_pending_coverage_is_not_claimed_as_execution_or_user_success():
    guide = build_guide(RawSignals(meta=RepoMeta(owner='o',repo='r')),use_llm=False,check_suitability=False)
    report = describe(guide)
    assert report['structural_checks_passed'] is True
    assert all(stage['pending_items'] for stage in report['stage_coverage'].values())
    assert report['commands_executed'] is False
    assert report['user_task_success_measured'] is False
    assert report['independent_human_review'] == 'pending'


def test_absent_stage_fails_structural_checks():
    guide = build_guide(RawSignals(meta=RepoMeta(owner='o',repo='r')),use_llm=False,check_suitability=False)
    guide.steps = [s for s in guide.steps if s.stage != 'D']
    assert 'missing_stage:D' in describe(guide)['errors']
