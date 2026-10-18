"""Export experiment statistics without redistributing source text/prompts."""
import argparse
import json
from pathlib import Path


def summarize(folder: Path) -> dict:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    runs = json.loads((folder / 'runs.json').read_text(encoding='utf-8'))
    records = []
    for row in runs:
        item = {k:row.get(k) for k in ['repo','arm','repeat','sha','snapshot_sha256','status','evaluation_scope',
            'reference_validation','elapsed_s','end_to_end_elapsed_s','model_attempts','effective_pipeline_attempts','arm_order','error_type']}
        item['reference_metrics'] = row.get('metrics')
        if item['reference_metrics']:
            item['reference_metrics'] = dict(item['reference_metrics'], command_exec=None)
        traces = row.get('trace',[])
        item['recorded_responses'] = len(traces)
        item['reported_total_tokens'] = sum(t.get('usage',{}).get('total_tokens',0) for t in traces)
        records.append(item)
    pairs = []
    for row in records:
        if row['arm'] != 'flat_rag':
            continue
        other = next((r for r in records if r['repo']==row['repo'] and r['repeat']==row['repeat'] and r['arm']=='layered_raw'), None)
        pair = {'repo':row['repo'],'repeat':row['repeat'],'evaluation_scope':row['evaluation_scope'],
            'eligible':bool(other and row['status']=='ok' and other['status']=='ok')}
        if pair['eligible']:
            pair['routed_minus_global_flat'] = {k:round(other['reference_metrics'][k]-row['reference_metrics'][k],4)
                for k in ['step_coverage','command_correct','command_coverage','evidence_hit']}
        pairs.append(pair)
    return {'kind':'controlled-reference-exploration','run_id':folder.name,'manifest':manifest,
        'status':summary['status'],'reference_checks':summary.get('reference_checks',{}),
        'quality_claim_eligible':summary.get('quality_claim_eligible',False),
        'model_attempts':sum(r['model_attempts'] or 0 for r in records),
        'recorded_responses':sum(r['recorded_responses'] for r in records),
        'reported_total_tokens':sum(r['reported_total_tokens'] for r in records),
        'records':records,'routing_pairs':pairs,
        'unmeasured':['command_execution','semantic_assertion_correctness','user_task_success','community_contribution'],
        'limitations':summary['limitations'] + ['Two repeats and narrow, different per-repo scopes do not establish statistical significance or general superiority',
            'Reference command match rate is not semantic correctness; source path hit is not entailment']}


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=summarize(args.folder)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(result['status'],'attempts',result['model_attempts'],'recorded_responses',result['recorded_responses'])
