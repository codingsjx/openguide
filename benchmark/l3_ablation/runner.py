"""L3 ablation skeleton: 朴素 baseline vs 分层管线 on the SAME golden repos.

M2 后接入真实生成器。骨架先定义两类 generator 的接口，保证 M2 接入即可跑：
- baseline_generate(repo)  : 朴素 clone→全文→单 LLM 总结（无证据）
- layered_generate(repo)   : 分层四视角 + schema + 证据（M2 后填）

口径红线：必须同批仓库、同 golden、同 metrics，避免口径漂移。
Run:  uv run python -m benchmark.l3_ablation
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.golden.schema import iter_golden_guides  # noqa: E402
from benchmark.metrics import compute  # noqa: E402
from benchmark.report import human_summary  # noqa: E402
from benchmark.schema import GeneratedGuide  # noqa: E402


def baseline_generate(owner: str, repo: str) -> GeneratedGuide:
    """朴素 baseline：无视角、无 schema、无证据。M2 后实现为真实朴素管线。"""
    raise NotImplementedError("M2 后接入：朴素 clone→全文→单 LLM 总结")


def layered_generate(owner: str, repo: str) -> GeneratedGuide:
    """分层管线：四视角 + schema + 证据锚点。M2 后接入真实生成。"""
    raise NotImplementedError("M2 后接入：四视角索引 + 决策树 + schema 生成")


def main() -> int:
    guides = iter_golden_guides()
    if not guides:
        print("（无 golden guide，先填 C 的 golden_guides/*.json）")
        return 1

    summary_rows: list[dict] = []
    for g in guides:
        row = {"repo": f"{g.owner}/{g.repo}"}
        for name, fn in (("baseline", baseline_generate), ("layered", layered_generate)):
            try:
                gen = fn(g.owner, g.repo)
                res = compute(g, gen, available_paths=set())
                row[f"{name}_coverage"] = res.step_coverage
                row[f"{name}_evidence"] = res.evidence_hit
                row[f"{name}_assert"] = res.assert_rate
            except NotImplementedError:
                row[f"{name}_coverage"] = None
        summary_rows.append(row)

    print("L3 消融（骨架，待 M2 接入真实生成）:")
    for r in summary_rows:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
