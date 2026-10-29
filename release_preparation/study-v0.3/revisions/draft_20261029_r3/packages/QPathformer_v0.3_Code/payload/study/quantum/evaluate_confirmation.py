"""One-time released confirmation evaluation. No training or automatic release.

Guard failures occur before test access. Partial evaluations and failures remain
evidence and cannot be overwritten or resumed silently. The final exclusive
commit is written only after every report, count array and statistic is saved.
"""
import argparse
import importlib.metadata
import json
from datetime import datetime
import os
from pathlib import Path
import platform
import sys
import time
import traceback
import numpy as np
import qstudy as s
import replay
import evaluation_stats as stats
import numerical_verification as numerical

ROOT=s.ROOT
PROTOCOL=ROOT.parent/'governance/ANALYSIS_PROTOCOL.json'
PROTOCOL_SHA='7401f1ab9f805eed0a1cd97a86e1aab9be3c27746e0a529a991efdaf9e1766f5'
REGISTRATION=ROOT/'EVALUATION_REGISTRATION.json'
LOCK=ROOT/'CONFIRMATION_ENDPOINT_LOCK.json'
REVIEW=ROOT/'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json'
RELEASE=ROOT/'EVALUATION_RELEASE.json'
OUTPUT=ROOT/'confirmation_evaluation'
READOUT_METHODS=('encoding1','readout1','kmeans40')
SHOT_SEEDS=(801,802,803,804,805)
BUDGETS=(1024,4096)
ENDPOINT_FILES={'result_sha256':'result.json','config_sha256':'config.json',
    'selected_checkpoint_sha256':'selected_checkpoint.npz','last_checkpoint_sha256':'last_checkpoint.npz',
    'ledger_sha256':'ledger.jsonl','record_orders_sha256':'record_orders.npz',
    'endpoint_commit_sha256':'endpoint_commit.json','status_sha256':'status.json',
    'validation_predictions_sha256':'validation_predictions.csv'}


def require(condition,message):
    if not condition:raise RuntimeError(message)


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def relative_path(root,value):
    rel=Path(value)
    require(not rel.is_absolute() and '..' not in rel.parts,'Unsafe relative path')
    path=(root/rel).resolve();require(path.is_relative_to(root.resolve()),'Path outside registered root')
    return path


def read_bound(path):
    digest=s.digest(path);value=s.read_json(path)
    require(s.digest(path)==digest,'Metadata changed while reading')
    return value,digest


def expected_output_paths():
    paths={'ACCESS_EVENT.json','bootstrap_arrays.npz','readout/counts.npz','readout/summary.json','summary.json'}
    paths.update(f'seed_{seed}/{method}/{file}' for seed in s.SEEDS['B'] for method in s.METHODS for file in ('predictions.csv','report.json'))
    return paths


def verify_guard():
    """Read metadata/checkpoint hashes only; no test payload or outcomes."""
    require(not OUTPUT.exists(),'Evaluation output already exists; do not rerun in place')
    require(np.__version__=='2.5.4','Exact registered NumPy 2.5.4 required for binomial count replay')
    require(s.digest(PROTOCOL)==PROTOCOL_SHA,'Registered analysis protocol changed')
    numerical.verify_protocol()
    reg,reg_hash=read_bound(REGISTRATION);lock,lock_hash=read_bound(LOCK);review,review_hash=read_bound(REVIEW);release,release_hash=read_bound(RELEASE)
    require(reg['status']=='REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS','Invalid registration status')
    require(reg['analysis_protocol_sha256']==PROTOCOL_SHA,'Registration protocol mismatch')
    require(reg['data_seal_sha256']==s.digest(ROOT/'data/DATA_SEAL.json'),'Registration data seal mismatch')
    require(reg.get('numerical_recovery_protocol_sha256')==numerical.PROTOCOL_SHA,'Registration recovery protocol mismatch')
    require(reg['method_order']==list(s.METHODS) and reg['training_seeds']==list(s.SEEDS['B']),'Registered scope differs')
    require(reg['readout']['methods']==list(READOUT_METHODS) and reg['readout']['budgets']==list(BUDGETS) and reg['readout']['shot_seeds']==list(SHOT_SEEDS),'Readout scope differs')
    for name,digest in reg['source_hashes'].items():require(s.digest(relative_path(ROOT,name))==digest,f'Registered source changed: {name}')
    require(reg['expected_output_paths']==sorted(expected_output_paths()),'Registered output inventory differs')
    require(reg['training_source_hashes']==s.source_hashes(),'Registered training sources changed')
    require(release.get('status')=='released_by_root' and release.get('study_id')=='QPATH-QMECH-v0.3','Root release missing')
    require(release.get('scope')=='all_65_registered_confirmation_endpoints_once','Wrong release scope')
    require(bool(release.get('release_id')) and bool(release.get('created_utc')),'Release identity missing')
    watched={REGISTRATION:reg_hash,LOCK:lock_hash,REVIEW:review_hash,RELEASE:release_hash,
             ROOT/'STAGE_B_FREEZE.json':s.digest(ROOT/'STAGE_B_FREEZE.json'),ROOT/'data/DATA_SEAL.json':s.digest(ROOT/'data/DATA_SEAL.json'),PROTOCOL:PROTOCOL_SHA,
             numerical.PROTOCOL_PATH:numerical.PROTOCOL_SHA}
    bindings={'registration_sha256':REGISTRATION,'endpoint_lock_sha256':LOCK,'independent_endpoint_review_sha256':REVIEW,
              'stage_freeze_sha256':ROOT/'STAGE_B_FREEZE.json','data_seal_sha256':ROOT/'data/DATA_SEAL.json','analysis_protocol_sha256':PROTOCOL,
              'numerical_recovery_protocol_sha256':numerical.PROTOCOL_PATH}
    for key,path in bindings.items():require(release.get(key)==watched[path],f'Release binding mismatch: {key}')
    require(lock.get('status')=='PASS' and lock.get('stage')=='B' and lock.get('endpoint_count')==65 and lock.get('test_accessed') is False,'Incomplete endpoint lock')
    require(lock['stage_freeze_sha256']==watched[ROOT/'STAGE_B_FREEZE.json'] and lock['data_seal_sha256']==watched[ROOT/'data/DATA_SEAL.json'],'Stale endpoint lock')
    require(lock['training_source_hashes']==s.source_hashes(),'Endpoint lock source mismatch')
    require(lock.get('numerical_recovery_protocol_sha256')==numerical.PROTOCOL_SHA,'Endpoint lock numerical protocol mismatch')
    for name,digest in lock['audit_sources'].items():require(s.digest(relative_path(ROOT,name))==digest,'Author audit source changed')
    require(review.get('status')=='PASS' and review.get('stage')=='B' and review.get('endpoint_count')==65,'Independent endpoint review incomplete')
    require(review.get('endpoint_lock_sha256')==watched[LOCK],'Independent review does not bind current lock')
    audit_path=relative_path(ROOT.parent,review['independent_audit_path'])
    independent,audit_hash=read_bound(audit_path)
    require(audit_hash==review['independent_audit_sha256'],'Independent audit changed')
    require(independent.get('status')=='PASS' and independent.get('stage')=='B' and independent.get('endpoint_count')==65 and independent.get('endpoint_lock_sha256')==lock_hash,'Independent audit scope/lock mismatch')
    require(independent.get('numerical_recovery_protocol_sha256')==numerical.PROTOCOL_SHA,'Independent audit numerical protocol mismatch')
    auditor_name='analysis/classical_review/audit_endpoints_v03.py'
    require(independent['auditor_sha256']==reg['external_source_hashes'][auditor_name],'Independent auditor source mismatch')
    for name,digest in reg['external_source_hashes'].items():
        path=relative_path(ROOT.parent,name);require(s.digest(path)==digest,'Registered external audit source changed');watched[path]=digest
    watched[audit_path]=audit_hash
    require(datetime.fromisoformat(release['created_utc'])>=datetime.fromisoformat(lock['created_utc']),'Release predates endpoint lock')
    require(datetime.fromisoformat(release['created_utc'])>=datetime.fromisoformat(independent['created_utc']),'Release predates independent audit')
    expected={(seed,method) for seed in s.SEEDS['B'] for method in s.METHODS}
    require(len(lock['endpoints'])==65 and {(r['seed'],r['method']) for r in lock['endpoints']}==expected,'Endpoint identities incomplete/duplicated')
    for row in lock['endpoints']:
        seed,method=row['seed'],row['method'];s.verify_freeze('B',seed,method)
        folder=ROOT/'stage_B'/f'seed_{seed}'/method
        require(row['path']==folder.relative_to(ROOT).as_posix(),'Unexpected endpoint path')
        require(not (folder/'failure.json').exists(),'Endpoint has a failure record')
        for key,filename in ENDPOINT_FILES.items():
            digest=s.digest(folder/filename);require(row.get(key)==digest,f'Endpoint changed: {seed}/{method}/{filename}')
            watched[folder/filename]=digest
        result=s.read_json(folder/'result.json');status=s.read_json(folder/'status.json')
        require(result['status']=='completed' and result['completed_rounds']==200 and result['optimizer_global_updates']==15000,'Endpoint horizon incomplete')
        require((result['method'],result['seed'],result['stage'],result['engineering'])==(method,seed,'B',False),'Result identity mismatch')
        require(status['status']=='completed' and status['round']==200,'Endpoint status changed')
    for name,digest in reg['source_hashes'].items():watched[relative_path(ROOT,name)]=digest
    for name,digest in s.source_hashes().items():watched[relative_path(ROOT,name)]=digest
    for row in lock['endpoints']:
        require(not (ROOT/row['path']/'failure.json').exists(),'Endpoint failure appeared during gate')
    for path,digest in watched.items():require(s.digest(path)==digest,'Metadata/source/endpoint changed during gate')
    return reg,lock,release,watched


def finite_shots(pop,probabilities,output):
    output.mkdir(exist_ok=False);arrays={};rows=[]
    for method in READOUT_METHODS:
        method_index=s.METHODS.index(method)
        for seed_index,seed in enumerate(s.SEEDS['B']):
            p=probabilities[method_index,seed_index]
            for budget in BUDGETS:
                measurements=[]
                for shot_seed in SHOT_SEEDS:
                    sequence=[seed,shot_seed,budget,method_index]
                    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(sequence)))
                    counts=rng.binomial(budget,np.clip(p,0,1)).astype(np.int64)
                    key=f'{method}_seed{seed}_shots{budget}_measurement{shot_seed}'
                    arrays[key]=counts;sampled=counts/budget
                    measurements.append({'shot_seed':shot_seed,'array_key':key,'seed_sequence':sequence,
                         'metrics':replay.metrics(pop['y'],sampled),'prediction_flip_fraction':float(np.mean((sampled>=.5)!=(p>=.5))),
                         'probability_mean_absolute_error':float(np.mean(abs(sampled-p)))})
                rows.append({'method':method,'training_seed':seed,'budget':budget,'ideal_metrics':replay.metrics(pop['y'],p),
                             'measurements':measurements,
                             'nested_mean_metrics':{name:float(np.mean([r['metrics'][name] for r in measurements])) for name in stats.METRICS},
                             'nested_mean_flip_fraction':float(np.mean([r['prediction_flip_fraction'] for r in measurements]))})
    np.savez_compressed(output/'counts.npz',**arrays)
    aggregates={}
    for method in READOUT_METHODS:
        aggregates[method]={}
        for budget in BUDGETS:
            selected=[r for r in rows if r['method']==method and r['budget']==budget]
            aggregates[method][str(budget)]={name:stats.describe([r['nested_mean_metrics'][name] for r in selected]) for name in stats.METRICS}
            aggregates[method][str(budget)]['prediction_flip_fraction']=stats.describe([r['nested_mean_flip_fraction'] for r in selected])
    result={'status':'completed','method_order':list(READOUT_METHODS),'budgets':list(BUDGETS),'shot_seeds':list(SHOT_SEEDS),
            'training_seeds':list(s.SEEDS['B']),'count_array_count':len(arrays),'records_per_array':len(pop['y']),
            'numpy':np.__version__,'rng':'Generator(PCG64(SeedSequence([training_seed, shot_seed, budget, registered_method_index])))',
            'ordering':'Each count array follows original confirmation test NPZ row order, also preserved in every predictions.csv.',
            'scope':'Ideal probability-level binomial simulation, not Aer circuit executions or physical shots. Five measurement replicates nested within each of five training checkpoints; independent budget draws, not a shared 1024-shot prefix. Across-training-seed summaries use five nested means, never n=25.',
            'represented_bernoulli_trials':sum(len(v)*int(k.split('_shots')[1].split('_')[0]) for k,v in arrays.items()),
            'counts_sha256':s.digest(output/'counts.npz'),'rows':rows,'aggregates':aggregates}
    write_new(output/'summary.json',result)
    return result


def summarize_numerical(reports):
    totals={key:sum(r['numerical_verification']['counts'][key] for r in reports) for key in
            ('n','canonical_near_band','reference_near_band','union_near_band','class_disagreements','outside_band_class_disagreements')}
    methods={}
    for method in s.METHODS:
        selected=[r for r in reports if r['method']==method]
        methods[method]={'per_seed_counts':[{'seed':r['seed'],**r['numerical_verification']['counts']} for r in selected],
            'sensitivity':{case:{metric:stats.describe([r['numerical_verification']['sensitivity'][case][metric] for r in selected])
                               for metric in ('macro_f1','accuracy')} for case in numerical.CASES},
            'raw_reference_minus_canonical':{metric:stats.describe([r['numerical_verification']['raw_reference_minus_canonical'][metric] for r in selected])
                                             for metric in ('bce','macro_f1','accuracy')}}
    return {'protocol_sha256':numerical.PROTOCOL_SHA,'band_half_width':float(numerical.BAND),'totals_over_checkpoint_record_pairs':totals,
            'exact_class_agreement':totals['class_disagreements']==0,
            'endpoints_with_disagreements':[{'seed':r['seed'],'method':r['method']} for r in reports if r['numerical_verification']['counts']['class_disagreements']],
            'endpoints_with_canonical_ambiguity':[{'seed':r['seed'],'method':r['method']} for r in reports if r['numerical_verification']['counts']['canonical_near_band']],
            'methods':methods,'scope':'Counts sum checkpoint-record pairs, not unique people or independent training samples. All four sensitivity assignments are retained. Label-assisted extrema are numerical diagnostics, not attainable models or statistical intervals. Canonical metrics/BCE/comparisons/count draws are unchanged.'}


def evaluate():
    registration,lock,release,watched=verify_guard()
    OUTPUT.mkdir(exist_ok=False);started=time.perf_counter()
    try:
        write_new(OUTPUT/'ACCESS_EVENT.json',{'event':'ROOT_RELEASE_VERIFIED_BEFORE_CONFIRMATION_TEST_LOAD','created_utc':s.now(),
                  'release_id':release['release_id'],'release_sha256':s.digest(RELEASE),'registration_sha256':s.digest(REGISTRATION),
                  'endpoint_lock_sha256':s.digest(LOCK),'test_payload':'data/confirmation_SEALED_test.npz'})
        testpath=ROOT/'data/confirmation_SEALED_test.npz';seal=s.read_json(ROOT/'data/DATA_SEAL.json')
        require(s.digest(testpath)==seal['files'][testpath.name]['sha256'],'Sealed confirmation data changed')
        with np.load(testpath,allow_pickle=False) as data:pop={name:data[name] for name in data.files}
        require(len(pop['y'])==1600 and len(set(map(int,pop['ids'])))==1600,'Wrong confirmation population')
        require(np.isfinite(pop['x']).all() and set(np.unique(pop['y']))=={0,1},'Invalid confirmation data')
        probabilities=np.empty((len(s.METHODS),5,1600));reports=[]
        by_identity={(r['seed'],r['method']):r for r in lock['endpoints']}
        for seed_index,seed in enumerate(s.SEEDS['B']):
            for method_index,method in enumerate(s.METHODS):
                row=by_identity[seed,method];folder=ROOT/row['path'];destination=OUTPUT/f'seed_{seed}'/method
                destination.mkdir(parents=True,exist_ok=False)
                with np.load(folder/'selected_checkpoint.npz',allow_pickle=False) as checkpoint:parameters=checkpoint['parameters'].copy()
                model=s.Model(method,seed);model.parameters[:]=parameters
                p=model.predict_population(pop);oracle=replay.predict(method,parameters,pop['x'],pop['depth'],pop['hash_route'],pop['kmeans_route'])
                verification=numerical.verify_pair(pop,p,oracle);error=verification['maximum_probability_error']
                metric=replay.metrics(pop['y'],p);s.save_predictions(destination/'predictions.csv',pop,p)
                report={'status':'completed','seed':seed,'method':method,'stage':'B','selected_round':row['selected_round'],
                        'selected_checkpoint_sha256':row['selected_checkpoint_sha256'],'training_result_sha256':row['result_sha256'],
                        'config_sha256':row['config_sha256'],'test_payload_sha256':seal['files'][testpath.name]['sha256'],
                        'predictions_sha256':s.digest(destination/'predictions.csv'),'metrics':metric,
                        'by_original_depth':{str(d):replay.metrics(pop['y'][pop['depth']==d],p[pop['depth']==d]) for d in range(1,5)},
                        'by_route':{kind:{str(k):replay.metrics(pop['y'][pop[kind+'_route']==k],p[pop[kind+'_route']==k]) for k in range(5) if np.any(pop[kind+'_route']==k)} for kind in ('hash','kmeans')},
                        'author_replay_maximum_probability_error':error,'author_replay_threshold_disagreements':int(np.sum((p>=.5)!=(oracle>=.5))),
                        'numerical_verification':verification,
                        'evaluation_forward_work':model.accounting(pop['x'],pop['depth'],model.route_for(pop)),
                        'author_replay_scope':'Separate scalar matrix/MLP endpoint mapping; additional verification computation, outside training and timed inference.',
                        'completed_utc':s.now()}
                write_new(destination/'report.json',report);reports.append(report);probabilities[method_index,seed_index]=p
        protocol=s.read_json(PROTOCOL);summary,boot=stats.summarize(pop['y'],probabilities,list(s.METHODS),protocol)
        np.savez_compressed(OUTPUT/'bootstrap_arrays.npz',metric_means=boot,method_order=np.asarray(s.METHODS),metric_order=np.asarray(stats.METRICS))
        readout=finite_shots(pop,probabilities,OUTPUT/'readout')
        for path,digest in watched.items():require(s.digest(path)==digest,'Bound metadata or endpoint changed during evaluation')
        for row in lock['endpoints']:require(not (ROOT/row['path']/'failure.json').exists(),'Endpoint failure appeared during evaluation')
        summary.update({'status':'completed','study_id':'QPATH-QMECH-v0.3','release_id':release['release_id'],
             'report_count':len(reports),'maximum_author_replay_probability_error':max(r['author_replay_maximum_probability_error'] for r in reports),
             'author_replay_threshold_disagreements':sum(r['author_replay_threshold_disagreements'] for r in reports),
             'endpoint_lock_sha256':s.digest(LOCK),'registration_sha256':s.digest(REGISTRATION),'analysis_protocol_sha256':PROTOCOL_SHA,
             'test_payload_sha256':seal['files'][testpath.name]['sha256'],'bootstrap_sha256':s.digest(OUTPUT/'bootstrap_arrays.npz'),
             'readout_summary_sha256':s.digest(OUTPUT/'readout/summary.json'),'elapsed_seconds':time.perf_counter()-started,
             'numerical_recovery_protocol_sha256':numerical.PROTOCOL_SHA,'numerical_verification':summarize_numerical(reports),
             'environment':{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
                            'numpy':np.__version__,'scipy':importlib.metadata.version('scipy')},'completed_utc':s.now()})
        write_new(OUTPUT/'summary.json',summary)
        inventory={p.relative_to(OUTPUT).as_posix():{'sha256':s.digest(p),'bytes':p.stat().st_size} for p in sorted(OUTPUT.rglob('*')) if p.is_file()}
        require(len(reports)==65 and readout['count_array_count']==150,'Incomplete evaluation output')
        require(set(inventory)==expected_output_paths(),'Unexpected completed output inventory')
        write_new(OUTPUT/'EVALUATION_COMMIT.json',{'status':'completed','study_id':'QPATH-QMECH-v0.3',
                  'report_count':65,'prediction_file_count':65,'count_array_count':150,'payload_count':len(inventory),
                  'release_id':release['release_id'],'release_sha256':s.digest(RELEASE),'registration_sha256':s.digest(REGISTRATION),
                  'endpoint_lock_sha256':s.digest(LOCK),'completed_utc':s.now(),'files':inventory})
        print(json.dumps({'status':'completed','output':str(OUTPUT),'reports':65,'count_arrays':150,'commit_sha256':s.digest(OUTPUT/'EVALUATION_COMMIT.json')}))
    except BaseException as error:
        write_new(OUTPUT/'FAILURE.json',{'status':'failed','created_utc':s.now(),'error':str(error),'traceback':traceback.format_exc(),
                  'policy':'Preserve this partial output. No automatic resume, overwrite, tuning or retraining; root review required.'})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--evaluate',action='store_true',required=True)
    parser.parse_args();evaluate()


if __name__=='__main__':main()
