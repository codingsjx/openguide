"""Controlled real-model experiment; immutable input snapshots and raw outputs.

python -m benchmark.controlled_ablation --repos pallets/click --repeats 1
No execution of generated commands. Missing credentials/errors never use fake data.
Snapshot issues are time-stamped live state, not historical commit contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("USE_CHROMA", "false")

from backend.core.generate.llm import LLMClient
from backend.core.generate.pipeline import build_guide, audit_steps
from backend.core.github.client import GitHubClient
from backend.core.github.recon import RawSignals, recon, enrich_docs_and_tree
from backend.core.index.service import RepoIndex
from benchmark.golden.schema import iter_golden_guides
from benchmark.l3_ablation.baseline import NaiveBaseline
from benchmark.metrics import compute, merge_summary
from benchmark.verify_generated_guide import _load_backend_env, to_generated_guide
from benchmark.global_flat_index import GlobalFlatIndex
from benchmark.pinned_reference import load_references, validate_reference


class FrozenClient(GitHubClient):
    def __init__(self, owner, repo):
        super().__init__()
        info = self.get_repo(owner, repo)
        self.sha = self._get_json(f"/repos/{owner}/{repo}/commits/{info['default_branch']}")["sha"]

    def get_contents(self, owner, repo, path="", ref=None):
        return super().get_contents(owner, repo, path, ref=self.sha)

    def get_file_text(self, owner, repo, path, ref=None):
        return super().get_file_text(owner, repo, path, ref=self.sha)

    def get_git_tree(self, owner, repo, ref, recursive=True):
        return super().get_git_tree(owner, repo, self.sha, recursive)


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def run(args):
    _load_backend_env()
    if not LLMClient().available():
        raise SystemExit("真实模型实验需要本地 LLM_API_KEY；不会回退到替身")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "benchmark/reports" / f"controlled_{stamp}"
    out.mkdir(parents=True)
    sources = sorted((ROOT / "backend/src").rglob("*.py")) + sorted((ROOT / "benchmark").rglob("*.py"))
    code_hash = hashlib.sha256(b"\n".join(str(p.relative_to(ROOT)).encode() + b"\0" + p.read_bytes() for p in sources)).hexdigest()
    write(out / "manifest.json", {"started_at": stamp, "code_sha256": code_hash,
          "repeats": args.repeats, "retrieval": "local-token-overlap", "model": LLMClient().public_config(),
          "paired_audit": True, "golden_review_status": "pending_independent_human_review",
          "protocol": "2-global-flat-deduplicated", "reference_dir": args.reference_dir,
          "controls": {"routed_executable_boost": False, "flat_single_corpus": True,
              "flat_deduplicated": True, "stage_calls": 4, "snippets_per_stage": 4,
              "snippet_character_cap": 1200, "max_output_tokens_per_stage": 1800,
              "temperature": 0.2, "counterbalanced_arm_order": True}})
    rows, summaries, reference_checks = [], {}, {}
    arms = ("single_shot", "flat_rag", "layered_raw", "layered_verified")
    references = load_references(Path(args.reference_dir)) if args.reference_dir else iter_golden_guides()
    guides = [g for g in references if not args.repos or f"{g.owner}/{g.repo}" in args.repos]
    if not guides:
        raise SystemExit("没有匹配的 golden 仓库")
    for golden in guides:
        key = f"{golden.owner}/{golden.repo}"
        tag = key.replace("/", "__")
        snapshot_file = (Path(args.snapshot_dir) / f"{tag}.json") if args.snapshot_dir else out / f"{tag}.json"
        try:
            if args.snapshot_dir:
                snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
            elif args.git_dir:
                from benchmark.git_snapshot import snapshot_from_git
                snapshot = snapshot_from_git(Path(args.git_dir) / tag, golden.owner, golden.repo, stamp)
            else:
                client = FrozenClient(golden.owner, golden.repo)
                try:
                    sig = enrich_docs_and_tree(recon(golden.owner, golden.repo, client), client)
                    snapshot = {"sha": client.sha, "captured_at": stamp, "signals": sig.model_dump()}
                finally:
                    client.close()
        except Exception as exc:
            for repeat in range(args.repeats):
                for arm in arms:
                    rows.append({"repo": key, "arm": arm, "repeat": repeat,
                                 "status": "input_failed", "error_type": type(exc).__name__})
            write(out / "runs.json", rows)
            print(key, "input_failed", type(exc).__name__, flush=True)
            continue
        # Always copy exact inputs to the result directory, even on replay.
        write(out / f"{tag}.json", snapshot)
        sig = RawSignals.model_validate(snapshot["signals"])
        try:
            check = validate_reference(golden, sig, snapshot["sha"]) if args.reference_dir else {"source_rule_validation": "not_pinned", "quality_claim_eligible": False}
            reference_checks[key] = check
        except ValueError as exc:
            reference_checks[key] = {"source_rule_validation": "failed", "error": str(exc), "quality_claim_eligible": False}
            for repeat in range(args.repeats):
                for arm in arms:
                    rows.append({"repo": key, "arm": arm, "repeat": repeat, "status": "reference_failed"})
            write(out / "runs.json", rows)
            print(key, "reference_failed", flush=True)
            continue
        write(out / f"{tag}.golden.json", golden.model_dump())
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        index = RepoIndex(golden.owner, golden.repo, boost_executable=False)
        index.index(sig)
        flat_index = GlobalFlatIndex(sig)
        for repeat in range(args.repeats):
            raw_guide = None
            raw_elapsed, raw_attempts = 0.0, 0
            arm_order = arms if repeat % 2 == 0 else ("layered_raw", "layered_verified", "flat_rag", "single_shot")
            for arm in arm_order:
                llm = LLMClient()
                row = {"repo": key, "arm": arm, "repeat": repeat, "sha": snapshot["sha"],
                       "snapshot_sha256": digest, "config": llm.public_config(), "status": "failed",
                       "reference_validation": check, "arm_order": list(arm_order)}
                started = time.perf_counter()
                try:
                    if arm == "single_shot":
                        baseline = NaiveBaseline()
                        baseline._client = llm
                        generated = baseline.generate(golden.owner, golden.repo, sig)
                    elif arm == "layered_verified":
                        if raw_guide is None:
                            raise ValueError("配对的原始生成失败，禁止另行采样")
                        guide = raw_guide.model_copy(deep=True)
                        guide.steps = audit_steps(sig, index, guide.steps)
                        generated = to_generated_guide(guide)
                        row["paired_with"] = "layered_raw"
                    else:
                        guide = build_guide(sig, index=flat_index if arm == "flat_rag" else index,
                            use_llm=True, strict_llm=True, verify_evidence=False, llm_client=llm, check_suitability=False)
                        if guide.unsuitable:
                            raise ValueError("仓库被适用性判断拒绝，不能计为模型评测成功")
                        generated = to_generated_guide(guide)
                        if arm == "layered_raw":
                            raw_guide = guide
                    if not generated.stages:
                        raise ValueError("模型未产出有效步骤")
                    scope = getattr(golden, "evaluation_scope", ["A", "B", "C", "D"])
                    scoped = generated.model_copy(update={"stages": [s for s in generated.stages if s.stage.split()[0] in scope]})
                    metric = compute(golden, scoped, available_paths=set(sig.file_tree),
                        issue_numbers={str(i['number']) for i in sig.issues if not i.get('pull_request')})
                    incremental = time.perf_counter() - started
                    effective_elapsed = incremental + (raw_elapsed if arm == "layered_verified" else 0)
                    metric.elapsed_s = effective_elapsed
                    row.update(status="ok", generated=generated.model_dump(), metrics=metric.__dict__, evaluation_scope=scope,
                               measured_command_execution=False, end_to_end_elapsed_s=round(effective_elapsed,3))
                    summaries.setdefault(arm, []).append(metric)
                except Exception as exc:
                    # Provider error text can contain URLs; record only exception type.
                    row["error_type"] = type(exc).__name__
                row["elapsed_s"] = round(time.perf_counter() - started, 3)
                row["model_attempts"] = llm.attempt_count
                row["effective_pipeline_attempts"] = raw_attempts if arm == "layered_verified" else llm.attempt_count
                if arm == "layered_raw":
                    raw_elapsed, raw_attempts = row["elapsed_s"], llm.attempt_count
                row["trace"] = llm.trace
                rows.append(row)
                write(out / "runs.json", rows)
                print(key, arm, repeat, row["status"], flush=True)
    expected = len(guides) * args.repeats * len(arms)
    result = {"metric_version": "2-strict-command", "status": "complete" if len(rows) == expected and all(r['status']=='ok' for r in rows) else "incomplete",
        "expected_runs": expected, "successful_runs": sum(r['status']=='ok' for r in rows),
        "summaries_success_only": {k: merge_summary(v) for k,v in summaries.items()},
        "protocol": "2-global-flat-deduplicated", "reference_checks": reference_checks,
        "quality_claim_eligible": len(reference_checks) == len(guides) and all(c.get('quality_claim_eligible',False) for c in reference_checks.values()),
        "limitations": ["command_exec not measured", "golden annotations require review against snapshot SHA",
                        "single-shot differs in request count and token budget; routing effect uses flat_rag vs layered_raw",
                        "API model identity is provider-reported, not independently verified",
                        "postprocess arm includes evidence audit, make expansion, workflow normalization and context derivation",
                        "agent-reviewed references are not independent human ground truth"]}
    write(out / "summary.json", result)
    print(out, flush=True)
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repos", action="append")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--snapshot-dir")
    p.add_argument("--reference-dir", help="固定 SHA 的源码复核参考集；缺省仍使用旧参考集并禁止最终质量声明")
    p.add_argument("--git-dir", help="读取已有 owner__repo Git 工作目录；不抓取 issue/星标元数据")
    a = p.parse_args()
    if a.repeats < 1:
        p.error("repeats 必须至少为 1")
    raise SystemExit(run(a))
