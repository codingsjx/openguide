"""Validate fixed source references without calling a model or running commands."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))
from backend.core.github.recon import RawSignals
from benchmark.pinned_reference import load_references, validate_reference


def audit(reference_dir: Path, snapshots: Path) -> dict:
    rows = []
    for ref in load_references(reference_dir):
        tag = f"{ref.owner}__{ref.repo}"
        try:
            snapshot = json.loads((snapshots / f"{tag}.json").read_text(encoding="utf-8"))
            result = validate_reference(ref, RawSignals.model_validate(snapshot["signals"]), snapshot["sha"])
            rows.append({"repo": f"{ref.owner}/{ref.repo}", **result, "steps": len(ref.steps),
                "citations": sum(len(s.citations) for s in ref.steps)})
        except (ValueError, OSError) as exc:
            rows.append({"repo": f"{ref.owner}/{ref.repo}", "source_rule_validation": "failed", "error_type": type(exc).__name__, "quality_claim_eligible": False})
    return {"kind": "pinned-source-reference-audit", "rows": rows,
        "status": "source_checks_passed" if rows and all(r['source_rule_validation']=='passed' for r in rows) else "failed",
        "independent_human_review_complete": False,
        "limitations": ["literal source checks are not independent human annotation", "no commands executed by this audit"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--references", type=Path, default=ROOT / "benchmark/golden/pinned")
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.references, args.snapshots)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["status"], "references", len(result["rows"]))
    raise SystemExit(0 if result["status"] == "source_checks_passed" else 1)
