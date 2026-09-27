"""Unit tests for benchmark.metrics — the scoring口径 must stay honest.

Each test pins one of the defects the metrics had before: evidence_hit skipping
command-less steps, issue evidence never counting, and prefix matching accepting
fabricated filenames. If any of these regress, the reported quality numbers stop
meaning what the README says they mean.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The benchmark package lives at the repo root, one level above backend/. The
# backend test suite inserts backend/src into sys.path via conftest.py, but not
# the repo root, so add it here to keep this test runnable either way (pytest
# from backend/, or the L1 smoke path with PYTHONPATH set).
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from benchmark.golden.schema import GoldenGuide, GoldenStep  # noqa: E402
from benchmark.metrics import compute  # noqa: E402
from benchmark.schema import GeneratedGuide, GenEvidence, GenStep  # noqa: E402

AVAILABLE = {
    "README.md",
    "Makefile",
    "docs/dev/contributing.rst",
    "docs",
    "src",
    "tests",
}
ISSUES = {"12", "42"}


def _golden() -> GoldenGuide:
    """A golden guide with both command steps (A/B) and evidence-only steps (C/D)."""
    return GoldenGuide(
        owner="o",
        repo="r",
        steps=[
            GoldenStep(order=1, stage="A 环境搭建", title="安装依赖",
                       expected_commands=["pip install -e ."], expected_outcome="成功",
                       evidence_sources=["Makefile#L2"]),
            GoldenStep(order=2, stage="B 测试基线", title="运行测试套件",
                       expected_commands=["pytest"], expected_outcome="42 passed",
                       evidence_sources=["Makefile#L4"]),
            GoldenStep(order=3, stage="C 选 issue", title="挑选首个 issue",
                       expected_commands=[], expected_outcome="选定一个",
                       evidence_sources=["docs/dev/contributing.rst#L120"]),
            GoldenStep(order=4, stage="D 首 PR", title="提交 PR",
                       expected_commands=[], expected_outcome="PR 已提交",
                       evidence_sources=["docs/dev/contributing.rst#L70"]),
        ],
    )


def _guide(evidences: dict[str, GenEvidence]) -> GeneratedGuide:
    """Build a guide whose step evidence is keyed by stage letter."""
    steps = []
    for i, (stage, title, cmd) in enumerate(
        [("A", "安装依赖", "pip install -e ."),
         ("B", "运行测试套件", "pytest"),
         ("C", "挑选首个 issue", None),
         ("D", "提交 PR", None)],
        start=1,
    ):
        steps.append(
            GenStep(step_id=i, stage=stage, title=title, command=cmd,
                    expected="", fail_hints=[], evidence=evidences.get(stage, GenEvidence()))
        )
    return GeneratedGuide(repo_url="https://github.com/o/r", unsuitable=False,
                          reasons=[], stages=steps)


_REAL_FILES = {
    "A": GenEvidence(kind="file", source="Makefile#L2", quote=""),
    "B": GenEvidence(kind="file", source="Makefile#L4", quote=""),
    "C": GenEvidence(kind="file", source="docs/dev/contributing.rst#L120", quote=""),
    "D": GenEvidence(kind="file", source="docs/dev/contributing.rst#L70", quote=""),
}


def test_perfect_replica_scores_full_marks_on_evidence():
    """A guide that mirrors golden exactly must score 100% evidence_hit."""
    m = compute(_golden(), _guide(_REAL_FILES), available_paths=AVAILABLE, issue_numbers=ISSUES)
    assert m.evidence_hit == 1.0
    assert m.assert_rate == 1.0


def test_commandless_steps_count_toward_evidence_hit():
    """C/D carry no command but DO carry evidence — they must be in the denominator.

    Regression guard: evidence_hit used to be computed over command-carrying
    steps only, which silently excluded the stages most prone to fabrication.
    """
    ev = dict(_REAL_FILES)
    ev["C"] = GenEvidence(kind="file", source="docs/不存在.md", quote="")  # fabricated
    m = compute(_golden(), _guide(ev), available_paths=AVAILABLE, issue_numbers=ISSUES)
    # 3 of 4 steps resolve, and C is detected as a miss.
    assert m.evidence_hit == 0.75, "无命令的 C/D 必须计入证据命中率的分母"


def test_issue_evidence_resolves_when_issue_exists():
    """V4 chunks are anchored to issue refs; those must be scoreable."""
    ev = dict(_REAL_FILES)
    ev["C"] = GenEvidence(kind="issue", source="#42", quote="")
    m = compute(_golden(), _guide(ev), available_paths=AVAILABLE, issue_numbers=ISSUES)
    assert m.evidence_hit == 1.0, "真实存在的 issue 引用应算命中"


def test_fabricated_issue_number_does_not_resolve():
    ev = dict(_REAL_FILES)
    ev["C"] = GenEvidence(kind="issue", source="#9999", quote="")
    m = compute(_golden(), _guide(ev), available_paths=AVAILABLE, issue_numbers=ISSUES)
    assert m.evidence_hit == 0.75, "编造的 issue 编号不得算命中"


def test_fabricated_filename_under_real_dir_does_not_resolve():
    """The prefix-match loophole: `docs/x.md` must not pass just because `docs/` exists."""
    ev = dict(_REAL_FILES)
    ev["C"] = GenEvidence(kind="file", source="docs/根本不存在.md", quote="")
    m = compute(_golden(), _guide(ev), available_paths=AVAILABLE, issue_numbers=ISSUES)
    assert m.evidence_hit == 0.75, "顶层目录存在不等于文件存在，不得放水"


def test_bare_url_is_not_a_valid_source():
    ev = dict(_REAL_FILES)
    ev["D"] = GenEvidence(kind="file", source="https://example.com/whatever", quote="")
    m = compute(_golden(), _guide(ev), available_paths=AVAILABLE, issue_numbers=ISSUES)
    assert m.evidence_hit == 0.75


def test_missing_evidence_counts_as_miss_not_as_absent():
    ev = dict(_REAL_FILES)
    ev["C"] = GenEvidence(kind="missing", source="", quote="")
    m = compute(_golden(), _guide(ev), available_paths=AVAILABLE, issue_numbers=ISSUES)
    assert m.evidence_hit == 0.75
    assert m.assert_rate == 0.75  # missing evidence also lowers 有据断言率


def test_path_lookup_is_case_insensitive():
    """`Makefile#L2` and `makefile#L4` are the same file; line anchors are ignored.

    With only `makefile` in the repo, the two Makefile-backed steps hit and the
    two docs-backed ones miss — 2 of 4.
    """
    m = compute(_golden(), _guide(_REAL_FILES), available_paths={"makefile"}, issue_numbers=set())
    assert m.evidence_hit == 0.5, "Makefile 大小写不同应命中，docs/ 不在集合里应落空"
