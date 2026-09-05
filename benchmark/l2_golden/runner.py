"""L2 golden-evaluation runner (skeleton).

Pipeline: for each golden repo → build profile → (M1/M2 待接入: 生成指南) →
score with benchmark.metrics → append jsonl + summary.

The actual guide generation lands in M1/M2; until then the runner exercises the
score/metrics pipeline against a *synthetic* generated guide so the metrics
machinery itself is testable and the output format is fixed.

Run:  uv run python -m benchmark.l2_golden
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.golden.schema import GoldenStep, iter_golden_guides  # noqa: E402
from benchmark.metrics import compute  # noqa: E402
from benchmark.report import human_summary, write_summary  # noqa: E402
from benchmark.schema import GeneratedGuide, GenEvidence, GenStep  # noqa: E402


def _synthetic_generated(owner: str, repo: str) -> GeneratedGuide:
    """Placeholder: produce a minimal generated guide for pipeline testing.

    Replaced in M2 by the real guide generator.
    """
    return GeneratedGuide(
        repo_url=f"https://github.com/{owner}/{repo}",
        stages=[
            GenStep(
                step_id=1,
                stage="A 环境搭建",
                title="安装开发依赖",
                command="pip install -e .[dev]",
                expected="成功安装 dev 依赖",
                fail_hints=["权限错误加 --user"],
                evidence=GenEvidence(kind="file", source="CONTRIBUTING.md#L22", quote="..."),
            )
        ],
    )


def main() -> int:
    guides = iter_golden_guides()
    print(f"golden guides 加载: {len(guides)}")
    if not guides:
        print("（尚无人工 golden guide，L2 未评分。请 C 填充 benchmark/golden/golden_guides/*.json）")
        return 1

    results = []
    for g in guides:
        gen = _synthetic_generated(g.owner, g.repo)
        res = compute(g, gen, available_paths=set())
        results.append(res)
        print(f"- {g.owner}/{g.repo}: coverage={res.step_coverage:.0%} "
              f"evidence={res.evidence_hit:.0%} assert={res.assert_rate:.0%}")
    print("\nL2 汇总:")
    print(human_summary(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
