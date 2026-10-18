"""Re-score saved real outputs with current audit, without new model calls.

Example: python -m benchmark.replay_audit benchmark/reports/controlled_... ...
Produces local paired audit records. This is software replay, not new LLM data.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))
import os
os.environ.setdefault("USE_CHROMA", "false")

from backend.core.generate.schemas import GuideStep
from backend.core.generate.pipeline import audit_steps
from backend.core.generate.evidence import verify_step_evidence
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex
from benchmark.metrics import compute
from benchmark.golden.schema import GoldenGuide
from benchmark.schema import GeneratedGuide, GenStep


def replay(folder: Path):
    runs = json.loads((folder / "runs.json").read_text(encoding="utf-8"))
    output = []
    for row in runs:
        if row.get("arm") != "layered_raw" or row.get("status") != "ok":
            continue
        tag = row["repo"].replace("/", "__")
        snapshot = json.loads((folder / f"{tag}.json").read_text(encoding="utf-8"))
        sig = RawSignals.model_validate(snapshot["signals"])
        golden = GoldenGuide.model_validate_json((folder / f"{tag}.golden.json").read_text(encoding="utf-8"))
        raw = GeneratedGuide.model_validate(row["generated"])
        steps = [GuideStep.model_validate(s.model_dump()) for s in raw.stages]
        idx = RepoIndex(sig.meta.owner, sig.meta.repo)
        idx.index(sig)
        unsupported = sum(bool(s.command) and verify_step_evidence(s, sig).verification != "command_verified" for s in steps)
        audited = audit_steps(sig, idx, steps)
        after = GeneratedGuide(repo_url=raw.repo_url, stages=[GenStep.model_validate(s.model_dump()) for s in audited])
        params = {"available_paths": set(sig.file_tree), "issue_numbers": {str(i['number']) for i in sig.issues if not i.get('pull_request')}}
        output.append({"repo": row["repo"], "repeat": row["repeat"], "sha": snapshot["sha"],
            "before": compute(golden, raw, **params).__dict__, "after": compute(golden, after, **params).__dict__,
            "commands_before": sum(bool(s.command) for s in raw.stages),
            "commands_after": sum(bool(s.command) for s in after.stages),
            "commands_without_literal_support_before": unsupported,
            "audited_steps": [s.model_dump() for s in audited],
            "limitations": "literal support only; no execution or semantic correctness proof"})
    (folder / "current_audit_replay.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("folders", nargs="+")
    args = p.parse_args()
    for folder in args.folders:
        rows = replay(Path(folder))
        print(folder, "paired_replays", len(rows))
