from datetime import datetime, timezone
import pytest

from backend.core.generate.pipeline import build_guide, audit_steps
from backend.core.generate.llm import LLMUnavailable
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.index.service import RepoIndex
from backend.core.github.recon import _age_days, _commit_recent
from test_pipeline import make_signals


def test_strict_model_mode_never_falls_back():
    class MissingClient:
        def available(self):
            return False
    with pytest.raises(LLMUnavailable):
        build_guide(make_signals(), strict_llm=True, llm_client=MissingClient())


def test_audit_does_not_backfill_unrelated_source_for_wrong_command():
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    step = GuideStep(step_id=1, stage="B", title="运行测试", command="pytest imaginary_tests",
                     evidence=Evidence(source="README.md"))
    result = audit_steps(sig, idx, [step])[0]
    assert result.evidence.kind == "missing"
    assert result.command is None


def test_reindex_removes_deleted_issues_and_does_not_duplicate_docs():
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    count = len(idx._store._rows["v3"])
    idx.index(sig)
    assert len(idx._store._rows["v3"]) == count
    sig.issues = []
    idx.index(sig)
    assert idx.search("good first issue", kind="issue").hits == []


def test_recent_commit_uses_actual_date():
    cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert not _commit_recent({"commit": {"committer": {"date": "2020-01-01T00:00:00Z"}}}, cutoff)
    assert _commit_recent({"commit": {"committer": {"date": "2026-10-10T00:00:00Z"}}}, cutoff)
    assert _age_days("2020-01-01T00:00:00Z") > 0


def test_test_command_cannot_masquerade_as_installation():
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    step = GuideStep(step_id=1, stage="A", title="安装环境", command="pytest",
                     evidence=Evidence(source="README.md"))
    result = audit_steps(sig, idx, [step])[0]
    assert result.command is None
    assert result.evidence.kind == "missing"


def test_symlink_checkout_requirement_is_shown_in_guide():
    sig = make_signals()
    sig.symlink_paths = ['tests/certs/ca']
    guide = build_guide(sig, use_llm=False)
    assert any('符号链接' in warning and 'Windows' in warning for warning in guide.warnings)
