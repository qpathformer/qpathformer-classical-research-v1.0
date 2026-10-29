"""Independent metadata-only v0.8 protocol/matrix review; never launches work."""
from pathlib import Path
import collections
import datetime
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
GOV=ROOT/'governance'
HERE=Path(__file__).resolve().parent

def need(v,m):
    if not v:raise RuntimeError(m)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def binding(p):
    p=Path(p)
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def main():
    plan=read(GOV/'STUDY_PLAN.json');matrix=read(GOV/'RUN_MATRIX.json')
    analysis=read(GOV/'ANALYSIS_PROTOCOL.json');deploy=read(GOV/'DEPLOYMENT_PROTOCOL.json')
    repro=read(GOV/'REPRODUCTION_PROTOCOL.json');proposal=read(GOV/'approved_proposal/PROPOSED_STUDY_PLAN.json')
    study='QPATH-PRIORITY-ROUTING-v0.8'
    need(all(d['study_id']==study for d in (plan,matrix,analysis,deploy,repro)),'Study identifiers differ')
    bases={'MultiK':('qmulti_kmeans',70),'MultiHash':('qmulti_hash',70),
           'TrigK':('trig_kmeans',125),'TrigHash':('trig_hash',125),'TrigG121':('trig121_global',121)}
    arms=[b+'_'+s for b in bases for s in ('U','P')]
    need(proposal['arms']==arms and [a['id'] for a in plan['arms']]==arms,'Arms differ from approved proposal')
    for a in plan['arms']:
        need((a['implementation_role'],a['predictor_parameters'])==bases[a['base_model']],'Model implementation/capacity differs')
        need(a['sampling_policy']==('uniform' if a['id'].endswith('_U') else 'priority'),'Policy identity differs')
    pops=matrix['populations'];runs=matrix['runs'];popmap={p['population_id']:p for p in pops}
    need(len(popmap)==len(pops)==40,'Population count or uniqueness differs')
    need(collections.Counter(p['stage'] for p in pops)=={'engineering':4,'A':4,'B':32},'Population stage counts differ')
    families=['checkerboard','spiral','annulus','disks']
    for stage,n in [('engineering',1),('A',1),('B',8)]:
        need(collections.Counter(p['family'] for p in pops if p['stage']==stage)=={f:n for f in families},'Per-task populations differ')
    streams={}
    def walk(v):
        if isinstance(v,dict):
            if {'namespace','uint128_decimal'}.issubset(v):
                ns=v['namespace'];s=int(v['uint128_decimal'])
                need(s==int.from_bytes(hashlib.sha256(ns.encode('ascii')).digest()[:16],'little'),'Stream derivation differs')
                need(ns not in streams or streams[ns]==s,'Repeated namespace differs')
                streams[ns]=s
            else:
                for q in v.values():walk(q)
        elif isinstance(v,list):
            for q in v:walk(q)
    walk(matrix)
    need(len(streams)==len(set(streams.values()))==548==matrix['unique_proposed_stream_count'],'Stream count/collision')
    pop_roles={'coordinates','annulus_noise','split','record_ids','kmeans_initialization','hash_salt','boundary_diagnostic','deployment_order'}
    for p in pops:
        need((p['records'],p['train'],p['validation'],p['sealed_test'])==(8000,4800,1600,1600),'Split budgets differ')
        need(set(p['proposed_streams'])==pop_roles,'Population stream roles differ')
    need(len(runs)==len({r['run_id'] for r in runs})==760,'Run count or IDs differ')
    need(collections.Counter(r['stage'] for r in runs)=={'engineering':40,'A':80,'B':640},'Stage fit counts differ')
    grouped=collections.defaultdict(list)
    for r in runs:
        p=popmap[r['population_id']];stage=r['stage'];seed=r['training_seed_id']
        need(r['run_id']==f"{stage}/{r['population_id']}/seed_{seed}/{r['arm']}",'Canonical run ID differs')
        need(p['stage']==stage and p['family']==r['family'] and p['population_index']==r['population_index'],'Population binding differs')
        need(seed in {'engineering':[1500],'A':[1501,1502],'B':[1601,1602]}[stage],'Training seed differs')
        rounds=12 if stage=='engineering' else 200
        need(r['rounds']==rounds and r['updates_per_round']==75 and r['updates']==75*rounds and r['batch_size']==64,'Full budget differs')
        need(r['training_record_visits']==rounds*4800,'Sampled work count differs')
        need(r['arm'] in arms and r['base_model']==r['arm'].rsplit('_',1)[0],'Base arm differs')
        need(r['sampling_policy']==('uniform' if r['arm'].endswith('_U') else 'priority'),'Run sampling policy differs')
        need(set(r['paired_streams'])=={'training_order','paired_circuit_core_initialization','sampling_diagnostics'},'Paired stream roles differ')
        grouped[(p['population_id'],seed)].append(r)
    need(len(grouped)==76,'Population-seed group count differs')
    for rows in grouped.values():
        need([r['arm'] for r in rows]==arms,'Paired group lacks exact arm order')
        need(all(r['paired_streams']==rows[0]['paired_streams'] for r in rows),'Paired streams differ across arms')
    for k,v in proposal['priority'].items():need(plan['priority'][k]==v,'Priority law differs from approved plan')
    need(plan['training']['engineering']['rounds']==12 and plan['training']['engineering']['updates']==900,'Engineering transition not covered')
    need(plan['training']['early_stopping'] is False,'Early stopping forbidden')
    expected=[
        {'MultiK_P':1,'MultiK_U':-1},
        {'TrigK_P':1,'TrigK_U':-1},
        {'MultiK_P':1,'MultiK_U':-1,'MultiHash_P':-1,'MultiHash_U':1},
        {'TrigK_P':1,'TrigK_U':-1,'TrigHash_P':-1,'TrigHash_U':1},
        {'MultiK_P':1,'TrigG121_P':-1},
    ]
    need([v['weights'] for v in analysis['primary_contrasts']]==expected,'Primary contrast algebra differs')
    need(analysis['family_size']==20 and analysis['alpha_family']==.05 and analysis['nominal_per_contrast_confidence']==.9975,'Multiplicity rule differs')
    need(analysis['confirmation_count']==640 and analysis['populations_per_family']==8 and analysis['seeds_per_population']==2,'Inferential unit differs')
    need(deploy['circuit_models']==256 and deploy['representation_conditions_per_session']==2688,'Deployment representations differ')
    need(deploy['timed_trials_across_three_sessions']==120960 and deploy['warmup_trials_across_three_sessions']==16128,'Timing count arithmetic differs')
    expected_repro=['B/B_checkerboard_01/seed_1601/MultiK_P','B/B_spiral_01/seed_1601/TrigK_P',
                    'B/B_annulus_01/seed_1601/MultiHash_U','B/B_disks_01/seed_1601/TrigG121_U']
    need(repro['endpoints']==expected_repro and repro['count']==4,'Preselected reproduction identities differ')
    need(set(expected_repro).issubset({r['run_id'] for r in runs}),'Reproduction is not a real confirmation endpoint')
    need(plan['matrix_summary']==matrix['counts'],'Counts differ between protocol/matrix')
    needed=['STUDY_PLAN.json','RUN_MATRIX.json','ANALYSIS_PROTOCOL.json','DEPLOYMENT_PROTOCOL.json',
            'REPRODUCTION_PROTOCOL.json','LOCAL_READINESS_PROTOCOL.json','RESOURCE_ACCOUNTING_NOTES.json']
    receipt={'schema':'qpath-v08-independent-protocol-review-1','status':'PASS_METADATA_AND_APPROVED_PLAN_ALIGNMENT',
        'reviewer':'/root/etel_study_mapping','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'bindings':[binding(GOV/n) for n in needed],'approved_proposal':binding(GOV/'approved_proposal/PROPOSED_STUDY_PLAN.json'),
        'script':binding(__file__),'verified_runs':760,'verified_populations':40,'paired_population_seed_groups':76,
        'unique_streams_rederived':548,'counts':matrix['counts'],'primary_contrast_weights':expected,
        'findings':[],'clarifications_resolved':['Actual implementation roles normalized to existing five base models.',
             'Historical584000 explicitly refers to expected registered coordinates; all-available extras independently inventoried.'],
        'pending_gates':['Historical source/seed/coordinate freshness and independent data generation replay.',
             'Producer sampler/gradient source review and synthetic tests; no source freeze implied.',
             'Actual full-stage audit and test release after640B; no test outcomes inspected.'],
        'source_review_notes':['Selected predictors compared after equal full budgets; earliest validation minimum, no early stopping.',
            'Per-record full importance correction targets native data BCE; does not guarantee same Adam path.',
            'Hash counts match original train occupancy, not priority-exposure counts.',
            'Four later reproduction fits are not additional independent populations.',
            'Protocol remains classical-only; no finite-shot/noise campaign or hardware authorized.'],
        'data_generated_or_training_started_by_reviewer':False}
    out=HERE/'PROTOCOL_PEER_REVIEW_v01.json'
    with out.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps({'status':receipt['status'],'receipt':binding(out)}))

if __name__=='__main__':main()
