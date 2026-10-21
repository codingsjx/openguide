"""Audit fixed Git sources without executing repository code or calling models.

This is a structural/coverage report, not an independently verified quality score.
python -m benchmark.readiness_audit --git-dir _golden_work --output report.json
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from backend.core.generate.pipeline import build_guide
from backend.core.github.recon import RawSignals
from benchmark.git_snapshot import snapshot_from_git

REPOS = ('psf/requests', 'pallets/click', 'cookiecutter/cookiecutter', 'mochajs/mocha', 'camelot-dev/camelot')


def describe(guide):
    stages = {}
    errors = []
    for stage in 'ABCD':
        steps = [s for s in guide.steps if s.stage == stage]
        if not steps:
            errors.append(f'missing_stage:{stage}')
        stages[stage] = {
            'steps': len(steps), 'literal_commands': sum(s.command is not None for s in steps),
            'pending_items': sum(s.evidence.kind == 'missing' for s in steps),
            'steps_with_source': sum(s.evidence.kind != 'missing' for s in steps),
        }
    for step in guide.steps:
        if step.command and step.evidence.verification != 'command_verified':
            errors.append(f'unverified_command:{step.step_id}')
        if step.execution_record:
            errors.append(f'unexpected_execution_claim:{step.step_id}')
    return {
        'structural_checks_passed': not errors, 'errors': errors,
        'stage_coverage': stages,
        'commands': [{'stage': s.stage, 'command': s.command, 'source': s.evidence.source,
                      'line_start': s.evidence.line_start, 'verification': s.evidence.verification,
                      'working_directory': s.working_directory, 'missing_inputs': s.missing_inputs}
                     for s in guide.steps if s.command],
        'unknown_command_directories': sum(s.command is not None and s.directory_basis == 'unknown' for s in guide.steps),
        'missing_input_paths': sorted({path for s in guide.steps for path in s.missing_inputs}),
        'independent_human_review': 'pending', 'commands_executed': False,
        'user_task_success_measured': False,
    }


def run(git_dir: Path, repos: list[str], output: Path):
    captured = datetime.now(timezone.utc).isoformat()
    rows = []
    for repo in repos:
        owner, name = repo.split('/')
        try:
            snapshot = snapshot_from_git(git_dir / repo.replace('/', '__'), owner, name, captured)
            signals = RawSignals.model_validate(snapshot['signals'])
            guide = build_guide(signals, use_llm=False, check_suitability=False)
            digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
            row = {'repo': repo, 'commit_sha': snapshot['sha'], 'snapshot_sha256': digest,
                   'documents': len(signals.doc_files), 'status': 'inspected', **describe(guide)}
        except Exception as exc:
            row = {'repo': repo, 'status': 'input_or_generation_failed', 'error_type': type(exc).__name__,
                   'structural_checks_passed': False}
        rows.append(row)
        print(repo, row['status'], flush=True)
    report = {
        'captured_at': captured, 'mode': 'fixed-source-rule-structural-audit',
        'repositories_requested': len(repos), 'repositories_inspected': sum(r['status'] == 'inspected' for r in rows),
        'structural_checks_passed': all(r['structural_checks_passed'] for r in rows), 'records': rows,
        'limitations': ['No model calls or command execution.',
            'Git source capture does not measure live issue availability or community activity.',
            'Literal source matching does not establish semantic correctness or a successful setup.',
            'Pending steps and unknown directories are retained; structural success is not functional completeness.',
            'No independent human review or participant outcomes.'],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--git-dir', type=Path, required=True)
    parser.add_argument('--repo', action='append', choices=REPOS)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.git_dir, args.repo or list(REPOS), args.output)
    raise SystemExit(0 if result['structural_checks_passed'] else 1)
