from benchmark.golden.schema import GoldenStep, iter_golden_guides
from benchmark.schema import GeneratedGuide, GenEvidence, GenStep
from benchmark.metrics import compute, merge_summary

import pytest


def test_golden_guides_load_well_formed():
    guides = iter_golden_guides()
    assert guides, "golden_guides/ 下应有至少一个 *.json"
    for g in guides:
        assert g.owner and g.repo
        assert g.steps, f"{g.owner}/{g.repo} 无 steps"


def test_metrics_full_cover():
    golden = iter_golden_guides()[0]
    # A generated guide that mirrors every golden step exactly.
    gen_steps = [
        GenStep(
            step_id=i,
            stage=s.stage,
            title=s.title,
            command=(s.expected_commands[0] if s.expected_commands else None),
            expected=s.expected_outcome,
            evidence=GenEvidence(
                kind="file",
                source=(s.evidence_sources[0] if s.evidence_sources else "MISSING"),
            ),
        )
        for i, s in enumerate(golden.steps, start=1)
    ]
    gen = GeneratedGuide(repo_url=f"https://github.com/{golden.owner}/{golden.repo}", stages=gen_steps)
    res = compute(golden, gen)
    assert res.step_coverage == 1.0
    assert res.assert_rate == 1.0


def test_metrics_no_evidence_lowers_assert():
    golden = iter_golden_guides()[0]
    gen = GeneratedGuide(
        repo_url="x/y",
        stages=[
            GenStep(
                step_id=1,
                stage="A",
                title="随便写",
                command=None,
                expected="",
                evidence=GenEvidence(kind="missing", source="", quote=""),
            )
        ],
    )
    res = compute(golden, gen)
    assert res.assert_rate < 1.0
    assert res.step_coverage < 1.0


def test_summary_merge():
    golden = iter_golden_guides()[0]
    gen = GeneratedGuide(repo_url="x/y", stages=[])
    r = compute(golden, gen)
    s = merge_summary([r])
    assert "step_coverage" in s
