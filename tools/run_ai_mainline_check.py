"""Repeat the product guide path without running any generated command.

Uses the operator's backend/.env. Explicit --capture-live permits collection;
otherwise --snapshot-dir must contain owner__repo-signals.json (RawSignals).
Raw prompts, responses and snapshots stay under ignored _run_cache/.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'backend/src')]


def run(args):
    destination=args.output.resolve()
    snapshots=args.snapshot_dir.resolve() if args.snapshot_dir else None
    raw=ROOT/'_run_cache'/('mainline-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    raw.mkdir(parents=True)
    os.chdir(ROOT/'backend')
    os.environ.setdefault('USE_CHROMA','false')
    from backend.core.generate.llm import LLMClient
    from backend.config import get_settings
    from backend.core.generate.pipeline import build_guide
    from backend.core.github.recon import RawSignals,recon,enrich_docs_and_tree
    from backend.core.github.client import GitHubClient
    from benchmark.controlled_ablation import source_digest
    if not LLMClient().available():raise SystemExit('Configure backend/.env locally; no fake-model fallback is used for this check')
    code=source_digest();rows=[]
    for target in args.repo:
        repo,_,revision=target.partition('@')
        owner,name=repo.split('/');tag=repo.replace('/','__')
        if snapshots:
            sig=RawSignals.model_validate_json((snapshots/f'{tag}-signals.json').read_text(encoding='utf-8'))
        else:
            client=GitHubClient()
            try:
                sig=recon(owner,name,client)
                if revision:sig.meta=sig.meta.model_copy(update={'default_branch':revision})
                sig=enrich_docs_and_tree(sig,client)
            finally:client.close()
        if (sig.meta.owner.lower(),sig.meta.repo.lower())!=(owner.lower(),name.lower()):raise ValueError('Snapshot belongs to a different repository')
        if revision and sig.meta.default_branch!=revision:raise ValueError('Snapshot revision mismatch')
        snapshot=json.dumps(sig.model_dump(),ensure_ascii=False,sort_keys=True)
        (raw/f'{tag}-signals.json').write_text(snapshot,encoding='utf-8')
        for repeat in range(args.repeats):
            client=LLMClient(timeout_s=args.timeout,retry_limit=0,disconnect_retry_limit=1,allow_literal_linebreaks=True,stream_json=get_settings().llm_streaming)
            start=time.perf_counter()
            row={'repo':repo,'repeat':repeat,'source_revision':sig.meta.default_branch,'input_sha256':hashlib.sha256(snapshot.encode()).hexdigest(),'code_sha256':code}
            try:
                guide=build_guide(sig,llm_client=client)
                (raw/f'{tag}-{repeat}-guide.json').write_text(guide.model_dump_json(indent=2),encoding='utf-8')
                row.update(status='returned',generation_mode=guide.generation_mode,stage_modes=guide.stage_modes,stage_fallbacks=guide.stage_fallbacks,
                    ai_steps=sum(s.generation_source=='llm' and s.evidence.verification in {'quote_verified','command_verified'} for s in guide.steps),
                    rule_steps=sum(s.generation_source=='rules' for s in guide.steps),commands=sum(s.command is not None for s in guide.steps),
                    unverified_commands=sum(s.command is not None and s.evidence.verification!='command_verified' for s in guide.steps),
                    unknown_directories=sum(s.command is not None and s.working_directory is None and s.directory_basis!='clone_destination' for s in guide.steps))
            except Exception as exc:row.update(status='failed',error_type=type(exc).__name__)
            row['ready_for_manual_review']=bool(row.get('ai_steps',0)>0 and row.get('commands',0)>0 and
                row.get('unverified_commands',1)==0 and row.get('unknown_directories',1)==0)
            usage_complete=bool(client.trace) and all(isinstance(t.get('usage',{}).get('total_tokens'),int) for t in client.trace)
            row.update(elapsed_s=round(time.perf_counter()-start,3),attempts=client.attempt_count,disconnect_retries=client.disconnect_retry_count,
                response_count=len(client.trace),reported_total_tokens=sum(t['usage']['total_tokens'] for t in client.trace) if usage_complete else None,
                token_usage_complete=usage_complete,streaming_requested=get_settings().llm_streaming,
                streamed_responses=sum(bool(t.get('response_streamed')) for t in client.trace))
            (raw/f'{tag}-{repeat}-trace.json').write_text(json.dumps({'trace':client.trace,'events':client.request_events},ensure_ascii=False,indent=2),encoding='utf-8')
            rows.append(row)
            report={'kind':'product-mainline-repeat-check','code_sha256':code,'source_code_unchanged':source_digest()==code,
                'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'records':rows,
                'expected_cases':len(args.repo)*args.repeats,'completed_cases':len(rows),
                'limitations':['Product protocol, not the strict controlled experiment; do not pool scores.',
                    'Repeated fixed inputs do not establish general reliability or independent sampling.',
                    'No generated command is executed; source matching is not semantic correctness.',
                    'No human participants or upstream contribution outcomes.']}
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(repo,repeat,row['status'],row.get('generation_mode'),flush=True)
            if not report['source_code_unchanged']:raise RuntimeError('Source changed during validation; do not use this result')
    return 0 if all(row['ready_for_manual_review'] for row in rows) else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',action='append',required=True,help='owner/repo, optionally @40-character SHA')
    p.add_argument('--snapshot-dir',type=Path)
    p.add_argument('--capture-live',action='store_true')
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--timeout',type=int,default=45)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if not a.snapshot_dir and not a.capture_live:p.error('Choose --snapshot-dir or explicitly --capture-live')
    if not 1<=a.repeats<=10 or not 10<=a.timeout<=120:p.error('repeats: 1–10; timeout: 10–120 seconds')
    for target in a.repo:
        if not re.fullmatch(r'[\w.-]+/[\w.-]+(?:@[0-9a-f]{40})?',target) or any(x in {'.','..'} for x in target.partition('@')[0].split('/')):
            p.error('Invalid public repository/revision')
    raise SystemExit(run(a))
