"""L3 ablation runner: naive single-shot baseline vs the layered pipeline.

Same golden repos, same golden guides, same metrics — only the generator changes.
That is what makes the comparison quotable.

Two arms per repo:
- naive   : one LLM call over a whole-repo dump, evidence taken at face value
- layered : four-perspective retrieval + stage prompts + 无证据不宣称 verify pass

Scoring: ``benchmark.metrics.compute`` against the real repo file list
(``sig.file_tree`` from the GitHub tree API), NOT against the set the layered
generator itself verified against — otherwise evidence_hit would be circular.

Networking: uses api.github.com only (recon + enrich). No clone, so the run is
fast and needs no local toolchain. ``command_exec`` is therefore left at its
neutral value here; the CLI/L2 path measures it where a clone exists.

Run:
  uv run python -m benchmark.l3_ablation.runner                 # fake arm (no key)
  uv run python -m benchmark.l3_ablation.runner --provider auto  # real LLM
  uv run python -m benchmark.l3_ablation.runner --repos psf/requests
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend" / "src"))

# Deterministic, no model download: the in-memory token-overlap store. Same
# default CI uses. Respect an explicit caller override.
os.environ.setdefault("USE_CHROMA", "false")

from benchmark.golden.schema import iter_golden_guides  # noqa: E402
from benchmark.l3_ablation.baseline import make_arm  # noqa: E402
from benchmark.metrics import MetricsResult, compute, merge_summary  # noqa: E402
from benchmark.verify_generated_guide import _load_backend_env  # noqa: E402

_REPORTS_DIR = ROOT / "benchmark" / "reports"


class _LayeredArm:
    """Adapter so both arms share the BaselineArm interface."""

    name = "layered-four-perspective"
    is_fake = False

    def __init__(self, use_llm: bool = False) -> None:
        self._use_llm = use_llm

    def generate(self, owner: str, repo: str, sig):
        from backend.core.generate.pipeline import build_guide
        from backend.core.index.service import RepoIndex

        idx = RepoIndex(owner, repo)
        idx.index(sig)
        guide = build_guide(sig, index=idx, use_llm=self._use_llm)
        from benchmark.verify_generated_guide import to_generated_guide

        return to_generated_guide(guide)


def _fetch_signals(owner: str, repo: str):
    """Recon + enrich via api.github.com. Shared by both arms."""
    from backend.core.github.client import GitHubClient
    from backend.core.github.recon import enrich_docs_and_tree, recon

    client = GitHubClient()
    try:
        sig = recon(owner, repo, client=client)
        sig = enrich_docs_and_tree(sig, client=client)
    finally:
        client.close()
    return sig


def _score(golden, gen, sig) -> MetricsResult:
    """Score one arm against golden, using the repo's real file list."""
    available = set(sig.file_tree)
    issues = {str(i.get("number")) for i in sig.issues if i.get("pull_request") is None}
    return compute(golden, gen, available_paths=available, issue_numbers=issues)


_METRIC_LABELS = (
    ("步骤完整率", "step_coverage"),
    ("证据命中率", "evidence_hit"),
    ("命令正确率", "command_correct"),
    ("有据断言率", "assert_rate"),
)


def _compare_block(result: dict) -> str:
    n = result["naive_summary"]
    l = result["layered_summary"]
    lines = [f"{'指标':<14}{'naive':>10}{'layered':>10}{'差值':>10}"]
    for label, attr in _METRIC_LABELS:
        nv, lv = n.get(attr, 0.0), l.get(attr, 0.0)
        lines.append(f"{label:<14}{nv:>9.0%}{lv:>10.0%}{lv - nv:>+10.0%}")
    lines.append(f"{'仓库数':<14}{n.get('n_repos', 0):>10}{l.get('n_repos', 0):>10}")
    # Latency (成本/延迟): the layered arm does strictly more work per repo, so
    # the report must state what that costs in wall-clock time, not only the
    # quality it buys.
    if "elapsed_s_mean" in n or "elapsed_s_mean" in l:
        lines.append(
            f"{'单仓库耗时(s)':<12}{n.get('elapsed_s_mean', 0.0):>10.2f}"
            f"{l.get('elapsed_s_mean', 0.0):>10.2f}"
            f"{l.get('elapsed_s_mean', 0.0) - n.get('elapsed_s_mean', 0.0):>+10.2f}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="L3 消融：朴素单次生成 vs 分层四视角管线")
    parser.add_argument("--provider", choices=["fake", "auto"], default="fake",
                        help="fake 用确定性替身（无需 API Key）；auto 调真实模型")
    parser.add_argument("--repos", action="append", default=None,
                        help="限定 owner/repo，可重复；默认跑全部 golden 仓库")
    parser.add_argument("--layered-llm", action="store_true",
                        help="分层臂也走真实 LLM（默认走离线启发式，便于对拍）")
    args = parser.parse_args()

    _load_backend_env()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    guides = iter_golden_guides()
    if args.repos:
        want = set(args.repos)
        guides = [g for g in guides if f"{g.owner}/{g.repo}" in want]
    if not guides:
        print("（无匹配的 golden guide）")
        return 1

    arm = make_arm(args.provider)
    layered_arm = _LayeredArm(use_llm=args.layered_llm)
    print(f"L3 消融：baseline = {arm.name} | grounded = {layered_arm.name}")
    if arm.is_fake:
        print("⚠ fake 臂是确定性替身，只证明指标能检出『无据断言』，不代表模型质量\n")

    naive_rows: list[MetricsResult] = []
    layered_rows: list[MetricsResult] = []
    per_repo: list[dict] = []

    for g in guides:
        key = f"{g.owner}/{g.repo}"
        print(f"{'=' * 70}\n{key}\n{'=' * 70}")
        try:
            sig = _fetch_signals(g.owner, g.repo)
        except Exception as exc:  # noqa: BLE001 - network/API failure per repo
            print(f"  [跳过] 抓取失败：{exc}")
            continue

        # Time each arm separately: generation latency is the "成本" half of the
        # ablation claim (quality bought per second spent).
        t0 = time.perf_counter()
        naive_guide = arm.generate(g.owner, g.repo, sig)
        naive_elapsed = time.perf_counter() - t0

        t0 = time.perf_counter()
        layered_guide = layered_arm.generate(g.owner, g.repo, sig)
        layered_elapsed = time.perf_counter() - t0

        naive = _score(g, naive_guide, sig)
        layered = _score(g, layered_guide, sig)
        naive.elapsed_s = round(naive_elapsed, 2)
        layered.elapsed_s = round(layered_elapsed, 2)
        naive_rows.append(naive)
        layered_rows.append(layered)

        print(f"  {'指标':<12}{'naive':>10}{'layered':>10}")
        for label, attr in _METRIC_LABELS:
            print(f"  {label:<12}{getattr(naive, attr):>9.0%}{getattr(layered, attr):>10.0%}")
        print(f"  {'耗时(s)':<11}{naive_elapsed:>10.2f}{layered_elapsed:>10.2f}")
        per_repo.append({
            "repo": key,
            "naive": {k: getattr(naive, k) for _, k in _METRIC_LABELS},
            "layered": {k: getattr(layered, k) for _, k in _METRIC_LABELS},
            "naive_elapsed_s": naive.elapsed_s,
            "layered_elapsed_s": layered.elapsed_s,
        })

    if not per_repo:
        print("\n没有可评分的仓库。")
        return 1

    result = {
        "run": "l3_ablation",
        "ts": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "baseline_arm": arm.name,
        "baseline_is_fake": arm.is_fake,
        "layered_llm": args.layered_llm,
        "repos": per_repo,
        "naive_summary": merge_summary(naive_rows),
        "layered_summary": merge_summary(layered_rows),
    }

    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = _REPORTS_DIR / f"l3_ablation_{result['ts']}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print("L3 汇总（同批仓库、同 golden、同指标）")
    print("=" * 70)
    print(_compare_block(result))
    print(f"\n已写出 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
