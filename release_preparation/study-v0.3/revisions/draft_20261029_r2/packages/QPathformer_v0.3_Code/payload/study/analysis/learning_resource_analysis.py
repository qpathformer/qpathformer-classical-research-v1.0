"""Descriptive validation milestones and resources; no test/model execution.

Added during Stage A at the user's request. The 97% rule is an observational
summary, not the registered checkpoint rule, stopping rule or primary analysis.
All original sources, runs and endpoint artifacts remain unchanged.
"""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'quantum'
THRESHOLD=.97
METHODS=('scheduled','min_depth2','untied_assigned','fixed1','fixed2','fixed4','encoding1','readout1','hash40','kmeans40','ensemble40','mlp41','mlp129')
SEEDS={'A':(501,502,503),'B':(601,602,603,604,605)}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def require(condition,message):
    if not condition:raise RuntimeError(message)


def description(values):
    values=list(values)
    return {'n':len(values),'values':values,'mean':statistics.mean(values) if values else None,
            'sample_sd':statistics.stdev(values) if len(values)>1 else None}


def add_work(items):
    total={}
    for work in items:
        for key,value in work.items():total[key]=total.get(key,0)+value
    return total


def crossing_events(ledger,preparation):
    hits=[entry['validation']['macro_f1']>=THRESHOLD for entry in ledger]
    first=next((i for i,hit in enumerate(hits) if hit),None)
    sustained=next((i for i in range(len(hits)-2) if all(hits[i:i+3])),None)
    charged=sum(preparation[key] for key in ('generation_seconds_charged','joint_router_fit_seconds_charged','train_validation_route_cache_seconds_charged'))
    def snapshot(index):
        if index is None:return None
        entry=ledger[index];round_number=entry['round']
        return {'round':round_number,'optimizer_updates':entry['optimizer_updates'],
                'model_record_visits':4800*round_number,'validation_macro_f1':entry['validation']['macro_f1'],
                'logged_elapsed_seconds':entry['elapsed_seconds'],'charged_elapsed_seconds':entry['elapsed_seconds']+charged,
                'training_work':entry['work_cumulative']['training'],'validation_work':entry['work_cumulative']['validation']}
    return {'first_at_or_above_97_percent':snapshot(first),'first_of_three_consecutive':snapshot(sustained),
            'three_check_confirmation':snapshot(None if sustained is None else sustained+2)}


def analyze(stage,output):
    require(not output.exists(),'Output must be new; preserve previous derived evidence')
    lock_path=Q/('STAGE_A_ENDPOINT_LOCK.json' if stage=='A' else 'CONFIRMATION_ENDPOINT_LOCK.json')
    lock=read(lock_path);lock_hash=digest(lock_path)
    require(lock['status']=='PASS' and lock['stage']==stage and lock['endpoint_count']==13*len(SEEDS[stage]),'Stage endpoint lock incomplete')
    require({(r['seed'],r['method']) for r in lock['endpoints']}=={(seed,method) for seed in SEEDS[stage] for method in METHODS},'Stage matrix differs')
    stage_status=read(Q/f'stage_{stage}/stage_status.json');require(stage_status['status']=='completed','Stage launcher is not completed')
    rows=[];watched={lock_path:lock_hash,Q/f'stage_{stage}/stage_status.json':digest(Q/f'stage_{stage}/stage_status.json')}
    for endpoint in lock['endpoints']:
        folder=Q/f'stage_{stage}'/f'seed_{endpoint["seed"]}'/endpoint['method']
        for key,file in [('result_sha256','result.json'),('ledger_sha256','ledger.jsonl'),('status_sha256','status.json')]:
            require(digest(folder/file)==endpoint[key],'Locked endpoint changed');watched[folder/file]=endpoint[key]
        result=read(folder/'result.json');ledger=[json.loads(line) for line in (folder/'ledger.jsonl').read_text().splitlines()]
        require(result['completed_rounds']==200 and result['optimizer_global_updates']==15000 and len(ledger)==200,'Wrong full horizon')
        events=crossing_events(ledger,result['preparation'])
        counters={'optimizer_training':result['work']['training'],'full_round_validation':result['work']['validation'],
                  'selected_validation_replay':result['work']['selected_validation_replay'],
                  'selected_training_gradient_diagnostics':add_work(group['work'] for group in result['diagnostics']['train_groups'].values()),
                  'inference_one_warmup_three_timed':result['inference']['work_separate_from_training'],
                  'cached_inference_comparison_reconstructed':endpoint['reconstructed_cached_comparison_work']}
        rows.append({'seed':endpoint['seed'],'method':endpoint['method'],'selected_round_by_BCE':result['selected_round'],
                     'selected_validation':result['selected_validation'],'milestones':events,'parameter_count':result['parameter_count'],
                     'training_seconds':result['training_seconds'],'charged_training_seconds':result['charged_training_seconds'],
                     'endpoint_total_seconds':result['total_seconds'],'preparation':result['preparation'],'work_separate_categories':counters,
                     'bank_training_record_visits':result['bank_training_record_visits'],
                     'executed_depth_training_record_visits':result['executed_depth_training_record_visits'],
                     'layer_training_record_exposure':result['layer_training_record_exposure'],
                     'inference':result['inference'],'training_clipped_probabilities':result['training_clipped_probabilities'],
                     'maximum_batch_gradient_norm':max(entry['maximum_batch_gradient_norm'] for entry in ledger),
                     'mean_round_mean_batch_gradient_norm':statistics.mean(entry['mean_batch_gradient_norm'] for entry in ledger),
                     'endpoint_result_sha256':endpoint['result_sha256'],'ledger_sha256':endpoint['ledger_sha256']})
    aggregates={}
    for method in METHODS:
        selected=[row for row in rows if row['method']==method]
        aggregate={'n_registered_runs':len(selected),'selected_validation':{name:description(r['selected_validation'][name] for r in selected) for name in ('bce','macro_f1','accuracy')},
                   'training_seconds':description(r['training_seconds'] for r in selected),
                   'charged_training_seconds':description(r['charged_training_seconds'] for r in selected),
                   'inference_seconds_per_record':description(r['inference']['mean_seconds_per_record'] for r in selected),
                   'training_clipped_probabilities':description(r['training_clipped_probabilities'] for r in selected),'milestones':{}}
        for event in ('first_at_or_above_97_percent','first_of_three_consecutive','three_check_confirmation'):
            reached=[r for r in selected if r['milestones'][event] is not None]
            aggregate['milestones'][event]={'reached':len(reached),'registered':len(selected),'nonreaching_seeds':[r['seed'] for r in selected if r['milestones'][event] is None],
                 'updates_among_reaching_only':description(r['milestones'][event]['optimizer_updates'] for r in reached),
                 'charged_seconds_among_reaching_only':description(r['milestones'][event]['charged_elapsed_seconds'] for r in reached),
                 'interpretation':'Conditional descriptive values only; nonreachers remain explicit and are never imputed as zero. Full15000-update budget remains charged.'}
        aggregates[method]=aggregate
    for path,value in watched.items():require(digest(path)==value,'Inputs changed during summary')
    result={'status':'completed','stage':stage,'created_utc':datetime.now(timezone.utc).isoformat(),'test_accessed':False,
            'classification':'Descriptive validation/resource supplement added during Stage A; no model, budget, checkpoint or primary-analysis change',
            'threshold':THRESHOLD,'threshold_scale':'Macro F1 fraction;0.97 means97 percent. Threshold comparison is >=.',
            'resolution':'One complete validation check per75optimizerupdates/4800model-record visits. First sustained crossing starts at the first of three consecutive checks; confirmation occurs two rounds/150updates later. Crossing can reverse thereafter.',
            'cost_scope':'All registered full budgets remain charged. Training elapsed includes within-loop validation/checkpoint writing. Charged elapsed adds fixed generation plus applicable joint router fit/cache preparation, repeatedly charged per arm. Endpoint total includes post-training diagnostics. Timing was concurrent, not isolated, and cannot establish hardware efficiency. Summing charged arm times is not project wall time.',
            'counter_scope':'All training, repeated validation, selected validation replay, selected training gradient diagnostics, four inference passes and fifth cached comparison are separate. Cached comparison work is reconstructed per documented addendum, without altering frozen artifacts. Author/independent matrix replay and Aer/binomial evaluation are outside these counters.',
            'stage_observed_wall_seconds':stage_status['observed_wall_seconds'],'rows':rows,'aggregates':aggregates,
            'source_sha256':digest(__file__),'endpoint_lock_sha256':lock_hash,
            'user_addendum_sha256':digest(ROOT/'governance/USER_REQUEST_ADDENDUM_01.json'),
            'resource_addendum_sha256':digest(Q/'RESOURCE_ACCOUNTING_ADDENDUM.json')}
    output.mkdir(parents=True,exist_ok=False)
    with (output/'learning_resources.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    with (output/'validation_milestones.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['stage','method','seed','event','reached','round','optimizer_updates','model_record_visits','training_circuit_examples','training_layer_applications','logged_elapsed_seconds','charged_elapsed_seconds','selected_round_by_BCE','full_budget_updates'])
        for row in rows:
            for name,event in row['milestones'].items():
                writer.writerow([stage,row['method'],row['seed'],name,event is not None,
                    event['round'] if event else '',event['optimizer_updates'] if event else '',event['model_record_visits'] if event else '',
                    event['training_work']['circuit_examples'] if event else '',event['training_work']['layer_applications'] if event else '',
                    event['logged_elapsed_seconds'] if event else '',event['charged_elapsed_seconds'] if event else '',row['selected_round_by_BCE'],15000])
    print(json.dumps({'status':'completed','stage':stage,'runs':len(rows),'output':str(output),'test_accessed':False}))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=['A','B'],required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();analyze(args.stage,args.output)


if __name__=='__main__':main()
