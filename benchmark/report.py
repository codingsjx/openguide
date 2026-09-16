"""Report helpers: persist metrics to jsonl + emit a human-readable summary.

Reports land in benchmark/reports/ and are part of the submission evidence.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from benchmark.metrics import MetricsResult, merge_summary

_REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def append_result(repo_key: str, result: MetricsResult, run_tag: str) -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    line = {
        "run": run_tag,
        "ts": _now_stamp(),
        "repo": repo_key,
        **asdict(result),
    }
    with (_REPORTS_DIR / f"l2_{run_tag}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def write_summary(results: list[MetricsResult], run_tag: str) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = merge_summary(results)
    out = _REPORTS_DIR / f"summary_{run_tag}_{_now_stamp()}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def human_summary(results: list[MetricsResult]) -> str:
    s = merge_summary(results)
    if not s:
        return "（无结果）"
    return (
        f"仓库数 {s['n_repos']} | golden 步骤 {s['total_golden_steps']} | "
        f"生成步骤 {s['total_gen_steps']}\n"
        f"步骤完整率 {s['step_coverage']:.0%} | 证据命中率 {s['evidence_hit']:.0%} | "
        f"命令正确率 {s['command_correct']:.0%} | 命令可执行率 {s['command_exec']:.0%} | "
        f"有据断言率 {s['assert_rate']:.0%}"
    )
