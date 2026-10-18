"""Regression cases from the competition-readiness audit (no network)."""
import pytest

from backend.core.generate.evidence import resolve_evidence_source, verify_step_evidence
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals
from benchmark.metrics import _command_matches_stage


@pytest.fixture
def signals():
    return RawSignals(meta=RepoMeta(owner="o", repo="r"),
        root_entries={"docs": "docs"}, file_tree=["docs/run.md"],
        doc_files=[DocFile(path="docs/run.md", name="run.md", text="# Tests\npytest tests\n")],
        issues=[{"number": 7, "title": "Fix docs", "state": "open"}])


@pytest.mark.parametrize("source", [
    "docs", "docs/fake.md", "docs/run.md#L999", "docs/run.md#L0", "docs/run.md#L2-L1",
    "https://github.com/other/repo/issues/7", "https://github.com.evil.test/o/r/issues/7",
    "https://github.com/o/r/blob/wrong/docs/run.md", "docs/../run.md",
])
def test_rejects_fabricated_or_cross_repo_sources(signals, source):
    assert resolve_evidence_source(source, signals).kind == "missing"


def test_existing_file_does_not_support_arbitrary_command(signals):
    step = GuideStep(step_id=1, stage="B", title="Tests", command="python fake.py",
                     evidence=Evidence(source="docs/run.md"))
    assert verify_step_evidence(step, signals).kind == "missing"


def test_command_verified_with_exact_line(signals):
    step = GuideStep(step_id=1, stage="B", title="Tests", command="pytest tests",
                     evidence=Evidence(source="docs/run.md#L2", quote="pytest tests"))
    ev = verify_step_evidence(step, signals)
    assert ev.verification == "command_verified"
    assert (ev.line_start, ev.line_end) == (2, 2)


def test_fabricated_quote_rejected(signals):
    step = GuideStep(step_id=1, stage="B", title="Tests",
                     evidence=Evidence(source="docs/run.md", quote="all tests always pass"))
    assert verify_step_evidence(step, signals).kind == "missing"


def test_dependency_name_is_not_a_runnable_command(signals):
    signals.doc_files[0].text = "pytest>=9.0\n"
    step = GuideStep(step_id=1, stage="B", title="Tests", command="pytest",
                     evidence=Evidence(source="docs/run.md"))
    assert verify_step_evidence(step, signals).kind == "missing"


@pytest.mark.parametrize("generated,reference", [
    ("python delete_everything.py", "python -m pytest tests"),
    ("pip uninstall project", "pip install project"),
    ("npm run build", "npm test"),
    ("pytest tests/other", "pytest tests/unit"),
    ("pytest tests; echo pass", "pytest tests"),
])
def test_command_scoring_rejects_wrong_action(generated, reference):
    assert not _command_matches_stage(generated, [reference])


def test_command_scoring_allows_pytest_wrapper_and_verbosity():
    assert _command_matches_stage("python -m pytest tests -q", ["pytest tests"])
