"""L2 golden-evaluation runner.

Pipeline: for each golden repo → call the real backend generator → score the
generated guide against the golden reference with the full five metrics →
append jsonl + summary.

Reuses ``benchmark.verify_generated_guide.evaluate_repo`` so L2, the CLI script
and L3 all run the exact same pipeline (no duplicate logic, no drift).

Run:  uv run python -m benchmark.l2_golden.runner
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.golden.schema import iter_golden_guides  # noqa: E402
from benchmark.report import append_result, human_summary, write_summary  # noqa: E402
from benchmark.verify_generated_guide import evaluate_repo, _load_backend_env  # noqa: E402


def main() -> int:
    _load_backend_env()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    guides = iter_golden_guides()
    print(f"golden guides 加载: {len(guides)}")
    if not guides:
        print("（尚无人工 golden guide，L2 未评分。请 C 填充 benchmark/golden/golden_guides/*.json）")
        return 1

    results = []
    for g in guides:
        print(f"\n{'='*70}\n{g.owner}/{g.repo}\n{'='*70}")
        r = evaluate_repo(g.owner, g.repo)
        if not r["ok"]:
            print(f"  [失败] {r['error']}")
            continue
        m = r["metrics"]
        if m is None:
            print("  （无 golden 参照，跳过）")
            continue
        results.append(m)
        print(f"  步骤完整率 {m.step_coverage:.0%} | 证据命中率 {m.evidence_hit:.0%} | "
              f"命令正确率 {m.command_correct:.0%} | 命令可执行率 {m.command_exec:.0%} | "
              f"有据断言率 {m.assert_rate:.0%}")
        append_result(f"{g.owner}/{g.repo}", m, "l2")

    print("\nL2 汇总:")
    print(human_summary(results))
    write_summary(results, "l2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
