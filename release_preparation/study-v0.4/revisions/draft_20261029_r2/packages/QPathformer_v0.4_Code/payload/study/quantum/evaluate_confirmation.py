"""One exclusive, root-released evaluation of all135 v0.4 endpoints.

No training, automatic release, retry, scenario tuning or test model selection.
Every guard runs before sealed payload loading; final commit follows all outputs.
"""
from datetime import datetime
import argparse
import json
from pathlib import Path
import platform
import sys
import time
import traceback
import numpy as np
import study as s
import verification as v
from path_mapping import remap_recorded,endpoint_folder
sys.path.insert(0,str(s.ROOT.parent/'analysis'))
import statistics_v04 as stats

ROOT=s.ROOT; STUDY_ROOT=ROOT.parent
REGISTRATION=ROOT/'EVALUATION_REGISTRATION.json'
LOCK=ROOT/'CONFIRMATION_ENDPOINT_LOCK.json'
REVIEW=ROOT/'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json'
RELEASE=ROOT/'EVALUATION_RELEASE.json'
OUTPUT=ROOT/'confirmation_evaluation'
PROTOCOL=STUDY_ROOT/'governance/ANALYSIS_PROTOCOL.json'
READINESS_PROTOCOL=STUDY_ROOT/'governance/LOCAL_READINESS_PROTOCOL.json'


def safe_path(root,relative):
    p=Path(relative);s.require(not p.is_absolute() and '..' not in p.parts,'Unsafe registered relative path')
    result=(root/p).resolve();s.require(result.is_relative_to(root.resolve()),'Registered path escapes root')
    return result


def read_bound(path):
    h=s.digest(path);obj=s.read_json(path);s.require(s.digest(path)==h,'Metadata changed while reading')
    return obj,h


def expected_output_paths():
    paths={'ACCESS_EVENT.json','summary.json'}
    for population in s.POPULATIONS['B']:
        paths.update(f'{population}/statistics/{name}' for name in ('bootstrap_counts.npy','population_summary.json'))
        paths.update(f'{population}/seed_{seed}/{method}/{name}' for seed in s.SEEDS['B'] for method in s.METHODS for name in ('predictions.csv','report.json'))
    return paths


def verify_guard(output_must_be_absent=True):
    """Metadata and hashes only; this function never loads any test array."""
    if output_must_be_absent:s.require(not OUTPUT.exists(),'Evaluation output exists; do not rerun in place')
    s.require(np.__version__=='2.5.4','Registered NumPy2.5.4 required for exact bootstrap/count replay')
    reg,rh=read_bound(REGISTRATION);lock,lh=read_bound(LOCK);review,ih=read_bound(REVIEW);release,eh=read_bound(RELEASE)
    s.require(reg.get('status')=='REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS','Evaluation not registered')
    s.require(reg['methods']==list(s.METHODS) and reg['training_seeds']==list(s.SEEDS['B']) and reg['populations']==list(s.POPULATIONS['B']),'Evaluation scope mismatch')
    s.require(reg['expected_output_paths']==sorted(expected_output_paths()),'Registered output schema mismatch')
    s.require(reg['training_source_hashes']==s.source_hashes(),'Registered training sources changed')
    watched={REGISTRATION:rh,LOCK:lh,REVIEW:ih,RELEASE:eh}
    for name,digest in reg['source_hashes'].items():
        path=safe_path(STUDY_ROOT,name);s.require(s.digest(path)==digest,'Registered source changed: '+name);watched[path]=digest
    for name,digest in s.source_hashes().items():watched[ROOT/name]=digest
    bindings={'registration_sha256':REGISTRATION,'endpoint_lock_sha256':LOCK,'independent_endpoint_review_sha256':REVIEW,
              'stage_freeze_sha256':ROOT/'STAGE_B_FREEZE.json','data_seal_sha256':ROOT/'data/DATA_SEAL.json',
              'analysis_protocol_sha256':PROTOCOL,'readiness_protocol_sha256':READINESS_PROTOCOL}
    for key,path in bindings.items():
        actual=s.digest(path);s.require(release.get(key)==actual,'Release binding differs: '+key);watched[path]=actual
    s.require(reg['analysis_protocol_sha256']==watched[PROTOCOL] and reg['readiness_protocol_sha256']==watched[READINESS_PROTOCOL],'Registered protocols changed')
    s.require(reg['data_seal_sha256']==watched[ROOT/'data/DATA_SEAL.json'],'Registered data changed')
    s.require(release.get('status')=='released_by_root' and release.get('study_id')=='QPATH-ROUTING-v0.4','No root release')
    s.require(release.get('scope')=='all_135_registered_confirmation_endpoints_once','Wrong release scope')
    s.require(bool(release.get('release_id')) and bool(release.get('created_utc')),'Missing release identity')
    s.require(lock.get('status')=='PASS' and lock.get('stage')=='B' and lock.get('endpoint_count')==135 and lock.get('engineering') is False,'Incomplete author endpoint lock')
    s.require(lock['source_hashes']==s.source_hashes() and lock['data_seal_sha256']==watched[ROOT/'data/DATA_SEAL.json'],'Stale author lock')
    s.require(lock['stage_freeze_sha256']==watched[ROOT/'STAGE_B_FREEZE.json'] and lock['analysis_protocol_sha256']==watched[PROTOCOL],'Author lock protocol/freeze mismatch')
    for path,digest in lock['audit_source_hashes'].items():
        current=remap_recorded(path,reg['original_working_root'],STUDY_ROOT)
        s.require(s.digest(current)==digest,'Author audit source changed');watched[current]=digest
    s.require(review.get('status')=='PASS' and review.get('stage')=='B' and review.get('endpoint_count')==135,'Incomplete independent endpoint review')
    s.require(review.get('endpoint_lock_sha256')==lh,'Independent review does not bind author lock')
    audit_path=safe_path(STUDY_ROOT,review['independent_audit_path']);independent,ah=read_bound(audit_path)
    s.require(ah==review['independent_audit_sha256'],'Independent audit changed')
    s.require(independent.get('status')=='PASS' and independent.get('stage')=='B' and independent.get('endpoint_count')==135,'Independent audit incomplete')
    s.require(independent.get('engineering') is False and independent.get('data_seal_sha256')==watched[ROOT/'data/DATA_SEAL.json'],'Independent audit engineering/data scope differs')
    s.require(independent.get('endpoint_lock_sha256')==lh and independent.get('analysis_protocol_sha256')==watched[PROTOCOL],'Independent audit lock/protocol mismatch')
    s.require(independent.get('validation_rounds_replayed')==27000,'Independent audit did not replay every validation round')
    auditor=safe_path(STUDY_ROOT,reg['independent_auditor_path'])
    s.require(independent.get('auditor_sha256')==s.digest(auditor)==reg['source_hashes'][reg['independent_auditor_path']],'Independent auditor source changed')
    for name,digest in independent['independent_source_sha256'].items():
        path=auditor.parent/name;relative=path.relative_to(STUDY_ROOT).as_posix()
        s.require(s.digest(path)==digest==reg['source_hashes'].get(relative),'Independent oracle/auditor source changed')
    watched[audit_path]=ah
    ready_path=STUDY_ROOT/'analysis/independent_replay/ANALYSIS_READY.json';ready,ready_hash=read_bound(ready_path)
    s.require(release.get('independent_replay_ready_sha256')==ready_hash,'Root release does not bind independent replay readiness')
    s.require(ready.get('status')=='READY_BEFORE_CONFIRMATION_TEST_ACCESS' and ready.get('study_id')=='QPATH-ROUTING-v0.4','Independent replay not ready')
    s.require(ready.get('registration_sha256')==rh and ready.get('analysis_protocol_sha256')==watched[PROTOCOL],'Independent replay registry/protocol mismatch')
    watched[ready_path]=ready_hash
    for group in ('source_hashes','evidence_hashes'):
        s.require(bool(ready[group]),'Empty independent replay readiness inventory')
        for name,digest in ready[group].items():
            path=safe_path(STUDY_ROOT,name);s.require(s.digest(path)==digest,'Independent replay readiness source/evidence changed')
            watched[path]=digest
    oracle=safe_path(STUDY_ROOT,ready['independent_oracle_path'])
    s.require(s.digest(oracle)==ready['independent_oracle_sha256'],'Independent replay oracle changed')
    watched[oracle]=ready['independent_oracle_sha256']
    for previous in (lock['created_utc'],independent['created_utc']):
        s.require(datetime.fromisoformat(release['created_utc'])>=datetime.fromisoformat(previous),'Release predates completed audit')
    stage_status=ROOT/'stage_B/stage_status.json';st,sh=read_bound(stage_status);watched[stage_status]=sh
    s.require(st['status']=='completed' and st['committed_endpoints']==135 and len(st['exits'])==5 and all(x['exit_code']==0 for x in st['exits']),'Stage workers not closed complete')
    expected={(pop,seed,method) for pop in s.POPULATIONS['B'] for seed in s.SEEDS['B'] for method in s.METHODS}
    s.require(len(lock['endpoints'])==135 and {(r['population'],r['seed'],r['method']) for r in lock['endpoints']}==expected,'Incomplete or duplicate endpoint identities')
    s.require(len(independent['endpoints'])==135 and {(r['population'],r['seed'],r['method']) for r in independent['endpoints']}==expected,'Independent endpoint identities incomplete/duplicated')
    independent_rows={(r['population'],r['seed'],r['method']):r for r in independent['endpoints']}
    for row in lock['endpoints']:
        pop,seed,method=row['population'],row['seed'],row['method'];s.verify_freeze('B',pop,seed,method)
        folder=endpoint_folder(ROOT,pop,seed,method)
        s.require(remap_recorded(row['path'],reg['original_working_root'],STUDY_ROOT)==folder.resolve(),'Endpoint path mismatch')
        audited=independent_rows[(pop,seed,method)]
        s.require(audited['endpoint_commit_sha256']==row['endpoint_commit_sha256'] and audited['rounds_verified']==200 and audited['validation_predictions_replayed']==320000,'Independent endpoint commit/horizon differs')
        s.require(not (folder/'failure.json').exists(),'Endpoint failure present')
        s.require(s.digest(folder/'endpoint_commit.json')==row['endpoint_commit_sha256'],'Endpoint commit changed')
        watched[folder/'endpoint_commit.json']=row['endpoint_commit_sha256']
        actual={p.name for p in folder.iterdir() if p.is_file() and p.name!='endpoint_commit.json'}
        s.require(actual==set(row['files']),'Endpoint payload inventory changed')
        for name,meta in row['files'].items():
            s.require(Path(name).name==name,'Unsafe endpoint filename');p=folder/name
            s.require(not p.is_symlink() and p.stat().st_size==meta['bytes'] and s.digest(p)==meta['sha256'],'Endpoint payload changed: '+name)
            watched[p]=meta['sha256']
        result=s.read_json(folder/'result.json');status=s.read_json(folder/'status.json')
        s.require(result['status']=='completed' and result['completed_rounds']==200 and result['optimizer_global_updates']==15000,'Incomplete endpoint horizon')
        s.require((result['population'],result['seed'],result['method'],result['stage'],result['engineering'])==(pop,seed,method,'B',False),'Endpoint identity changed')
        s.require(status['status']=='completed' and status['round']==200,'Endpoint status changed')
    for path,digest in watched.items():s.require(s.digest(path)==digest,'Bound source/evidence changed during gate')
    return reg,lock,release,watched


def summarize_numerical(reports):
    keys=('n','canonical_near_band','reference_near_band','union_near_band','class_disagreements','outside_band_class_disagreements')
    totals={k:sum(r['numerical_verification']['counts'][k] for r in reports) for k in keys}
    methods={}
    for method in s.METHODS:
        selected=[r for r in reports if r['method']==method]
        methods[method]={'per_seed_counts':[{'seed':r['seed'],**r['numerical_verification']['counts']} for r in selected],
            'sensitivity':{case:{metric:{'seed_values':[r['numerical_verification']['sensitivity'][case][metric] for r in selected],
                'mean':float(np.mean([r['numerical_verification']['sensitivity'][case][metric] for r in selected])),
                'sample_sd':float(np.std([r['numerical_verification']['sensitivity'][case][metric] for r in selected],ddof=1))}
                for metric in ('macro_f1','accuracy')} for case in ('all_ambiguous_to0','all_ambiguous_to1','label_assisted_all_incorrect','label_assisted_all_correct')}}
    return {'counts':totals,'exact_class_agreement':totals['class_disagreements']==0,'methods':methods,
            'scope':'Checkpoint-record counts are not independent task replicates. Sensitivities use canonical near-band mask; label-assisted extrema are diagnostics, never fitted performance or statistical intervals.'}


def evaluate_payloads(populations,endpoint_rows,output,endpoint_root=None):
    """Internal output builder; public CLI always runs verify_guard first.

    Synthetic test fixtures can supply arrays/checkpoints without any test read.
    """
    output=Path(output);summaries={};all_reports=[]
    for population in s.POPULATIONS['B']:
        pop=populations[population];p_all=np.empty((5,9,len(pop['y'])),dtype=np.float64);reports=[]
        for si,seed in enumerate(s.SEEDS['B']):
            for mi,method in enumerate(s.METHODS):
                row=endpoint_rows[(population,seed,method)]
                folder=endpoint_folder(ROOT if endpoint_root is None else endpoint_root,population,seed,method);model=s.Model(method,seed)
                with np.load(folder/'selected_checkpoint.npz',allow_pickle=False) as c:model.parameters[:]=c['parameters']
                p=model.predict_population(pop);oracle=v.scalar_reference(method,model.parameters,pop['x'],model.route_for(pop))
                numerical=v.verify_pair(pop,p,oracle);p_all[si,mi]=p
                dest=output/population/f'seed_{seed}'/method;dest.mkdir(parents=True,exist_ok=False)
                s.save_predictions(dest/'predictions.csv',pop,p)
                report={'population':population,'seed':seed,'method':method,'selected_round':row['selected_round'],
                    'checkpoint_sha256':s.digest(folder/'selected_checkpoint.npz'),'metrics':s.metrics(pop['y'],p),
                    'numerical_verification':numerical,'prediction_sha256':s.digest(dest/'predictions.csv'),
                    'by_route':{kind:{str(k):s.metrics(pop['y'][pop[kind+'_route']==k],p[pop[kind+'_route']==k]) for k in range(5) if np.any(pop[kind+'_route']==k)} for kind in ('hash','kmeans')},
                    'route_counts':{kind:np.bincount(pop[kind+'_route'],minlength=5).tolist() for kind in ('hash','kmeans')}}
                s.write_json(dest/'report.json',report,True);reports.append(report);all_reports.append(report)
        summary=stats.analyse_population(population,pop['y'],p_all,list(s.SEEDS['B']),list(s.METHODS),output/population/'statistics')
        summaries[population]={'statistics':summary,'numerical_verification':summarize_numerical(reports)}
    return summaries,all_reports


def finish_commit(output,release,reg,lock,watched,summaries,reports,elapsed):
    summary={'status':'completed','study_id':'QPATH-ROUTING-v0.4','report_count':len(reports),'population_order':list(s.POPULATIONS['B']),
        'method_order':list(s.METHODS),'training_seeds':list(s.SEEDS['B']),'populations':summaries,
        'release_id':release['release_id'],'registration_sha256':s.digest(REGISTRATION),'endpoint_lock_sha256':s.digest(LOCK),
        'analysis_protocol_sha256':s.digest(PROTOCOL),'elapsed_seconds':elapsed,'completed_utc':s.now(),
        'environment':{'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'executable':sys.executable}}
    s.write_json(output/'summary.json',summary,True)
    for path,digest in watched.items():s.require(s.digest(path)==digest,'Bound input changed during evaluation')
    inventory={p.relative_to(output).as_posix():{'sha256':s.digest(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()}
    s.require(set(inventory)==expected_output_paths(),'Evaluation payload inventory mismatch')
    s.require(len(reports)==135,'Incomplete reports')
    s.write_json(output/'EVALUATION_COMMIT.json',{'status':'completed','study_id':'QPATH-ROUTING-v0.4','report_count':135,
       'prediction_file_count':135,'population_count':3,'payload_count':len(inventory),'release_id':release['release_id'],
       'release_sha256':s.digest(RELEASE),'registration_sha256':s.digest(REGISTRATION),'endpoint_lock_sha256':s.digest(LOCK),
       'files':inventory,'completed_utc':s.now()},True)


def evaluate():
    reg,lock,release,watched=verify_guard();OUTPUT.mkdir(exist_ok=False);start=time.perf_counter()
    try:
        s.write_json(OUTPUT/'ACCESS_EVENT.json',{'event':'Root-released confirmation test payload loading begins',
                    'created_utc':s.now(),'release_id':release['release_id'],'registration_sha256':s.digest(REGISTRATION),
                    'endpoint_lock_sha256':s.digest(LOCK),'populations':list(s.POPULATIONS['B'])},True)
        seal=s.read_json(ROOT/'data/DATA_SEAL.json');populations={}
        for population in s.POPULATIONS['B']:
            path=ROOT/'data'/f'{population}_SEALED_test.npz';digest=s.digest(path)
            s.require(digest==seal['files'][path.name]['sha256'],'Sealed test payload changed')
            with np.load(path,allow_pickle=False) as f:populations[population]={k:f[k] for k in f.files}
            s.require(len(populations[population]['y'])==1600,'Wrong test record count');watched[path]=digest
        endpoints={(r['population'],r['seed'],r['method']):r for r in lock['endpoints']}
        summaries,reports=evaluate_payloads(populations,endpoints,OUTPUT)
        finish_commit(OUTPUT,release,reg,lock,watched,summaries,reports,time.perf_counter()-start)
        print('PASS completed all135 registered test endpoints')
    except BaseException as error:
        s.write_json(OUTPUT/'FAILURE.json',{'status':'FAIL','error':str(error),'traceback':traceback.format_exc(),'created_utc':s.now(),'recovery':'Preserve all output; no automatic retry or overwrite'},True)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evaluate',action='store_true',required=True)
    p.parse_args();evaluate()


if __name__=='__main__':main()
