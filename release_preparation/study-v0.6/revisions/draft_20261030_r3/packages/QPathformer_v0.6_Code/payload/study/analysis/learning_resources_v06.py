"""Post-audit validation learning and recorded-resource summaries. No test loader.

Both successful full-stage endpoint audits are required. This reads already
committed measurements; it neither evaluates models nor changes selection.
"""
from pathlib import Path,PureWindowsPath
from datetime import datetime,timezone
import argparse,csv,hashlib,json,statistics,traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'quantum'
STUDY_ID='QPATH-GENERALIZATION-v0.6'
METHODS=('qscalar_kmeans','qmulti_kmeans','mlp8tanh_kmeans','trig_kmeans','trig_global','mlp_global')
SEEDS={'A':(1101,1102),'B':(1201,1202,1203,1204,1205)}
POPULATIONS={stage:tuple(role+'_'+family for family in ('checkerboard','spiral','annulus','disks'))
             for stage,role in (('A','development'),('B','confirmation'))}
THRESHOLDS={'90':.90,'95':.95,'97':.97}

def need(value,message):
    if not value:raise RuntimeError(message)
def sha(path):
    path=Path(path);before=path.stat();value=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):value.update(block)
    after=path.stat();need((before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino),'File changed during hash')
    return value.hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,obj):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
def read_bound(path):
    before=sha(path);raw=Path(path).read_bytes();obj=json.loads(raw.decode('utf-8-sig'))
    need(sha(path)==before==hashlib.sha256(raw).hexdigest(),'Metadata changed while read');return obj,before

def inside(root,relative):
    need(isinstance(relative,str) and relative and '\\' not in relative,'Invalid relative path')
    p=PureWindowsPath(relative)
    need(not p.drive and not p.root and all(s not in ('','.','..') and ':' not in s for s in relative.split('/')),'Unsafe relative path')
    root=Path(root).resolve();current=root/relative
    need(current.resolve().is_relative_to(root),'Evidence escapes current root')
    for part in (current,*current.parents):
        if part==root:break
        need(not part.is_symlink() and not (hasattr(part,'is_junction') and part.is_junction()),'Evidence link/junction forbidden')
    return current

def mapped_historical_path(recorded,original_root):
    """Resolve a declared original-root artifact into this checkout without edits."""
    original_root=PureWindowsPath(str(original_root));original_path=PureWindowsPath(str(recorded))
    need(original_root.is_absolute() and original_path.is_absolute(),'Historical artifact path must be absolute')
    need(original_path.is_relative_to(original_root),'Historical artifact outside declared working root')
    relative=original_path.relative_to(original_root)
    need('..' not in relative.parts,'Unsafe historical artifact path')
    return inside(ROOT,relative.as_posix()).resolve()

def endpoint_folder(stage,row,original_root):
    need(stage in SEEDS and row['population'] in POPULATIONS[stage] and row['seed'] in SEEDS[stage] and row['method'] in METHODS,'Unregistered endpoint identity')
    current=inside(Q,f"stage_{stage}/{row['population']}/seed_{row['seed']}/{row['method']}").resolve()
    need(mapped_historical_path(row['path'],original_root)==current,'Historical endpoint path/identity mismatch')
    return current

def milestones(values,elapsed=None,threshold=.97,cadence=75,consecutive=3):
    """Keep first crossing separate from the first completed qualifying streak."""
    values=np.asarray(values,dtype=float)
    need(values.ndim==1 and len(values)>0 and np.isfinite(values).all() and np.all((values>=0)&(values<=1)),'Invalid milestone values')
    need(isinstance(cadence,int) and cadence>0 and isinstance(consecutive,int) and consecutive>0,'Invalid milestone protocol')
    need(np.isfinite(threshold) and 0<=threshold<=1,'Invalid milestone threshold')
    if elapsed is not None:
        elapsed=np.asarray(elapsed,float);need(elapsed.shape==values.shape and np.isfinite(elapsed).all() and np.all(np.diff(elapsed)>=0) and elapsed[0]>=0,'Invalid elapsed history')
    first=None;confirmed=None;sequence_start=None;streak=0
    for index,value in enumerate(values):
        if value>=threshold:
            if first is None:first=index+1
            streak+=1
            if streak==consecutive and confirmed is None:confirmed=index+1;sequence_start=confirmed-consecutive+1
        else:streak=0
    return {'threshold':threshold,'cadence_updates':cadence,'confirmation_checks':consecutive,
       'first_round':first,'first_update':None if first is None else first*cadence,
       'first_elapsed_seconds':None if first is None or elapsed is None else float(elapsed[first-1]),
       'confirmed_sequence_start_round':sequence_start,'confirmed_sequence_start_update':None if sequence_start is None else sequence_start*cadence,
       'confirmed_round':confirmed,'confirmed_update':None if confirmed is None else confirmed*cadence,
       'confirmed_elapsed_seconds':None if confirmed is None or elapsed is None else float(elapsed[confirmed-1]),
       'horizon_rounds':len(values),'horizon_updates':len(values)*cadence,
       'first_reached':first is not None,'confirmed_reached':confirmed is not None,
       'final_macro_f1':float(values[-1])}

def finite_summary(values):
    values=list(map(float,values));need(values and np.isfinite(values).all(),'Empty/nonfinite summary')
    return {'n':len(values),'mean':statistics.mean(values),'sample_sd':statistics.stdev(values) if len(values)>1 else None,
            'median':statistics.median(values),'minimum':min(values),'maximum':max(values)}
def reaching_summary(rows,prefix,threshold_key=None):
    milestones_rows=[r['milestones'] if threshold_key is None else r['milestones_by_threshold'][threshold_key] for r in rows]
    reached=[m[prefix+'_update'] for m in milestones_rows if m[prefix+'_reached']]
    return {'total_runs':len(rows),'reached':len(reached),'not_reached':len(rows)-len(reached),
       'horizon_updates':15000,'conditional_update_summary':finite_summary(reached) if reached else None,
       'scope':'Reached-only summary; nonreachers remain counted/censored at15000, never imputed as success.'}

def completed_replay_gate():
    """Metadata/bytes only; no test metric value or model/array is interpreted."""
    watched={}
    def bound(path):
        obj,h=read_bound(path);watched[path]=h;return obj,h
    release,release_sha=bound(Q/'EVALUATION_RELEASE.json')
    need(release.get('status')=='released_by_root' and release.get('study_id')==STUDY_ID
         and release.get('scope')=='all_120_registered_confirmation_endpoints_once','Root release required before learning summaries')
    registry,registry_sha=bound(Q/'EVALUATION_REGISTRATION.json')
    ready,ready_sha=bound(ROOT/'analysis/independent_replay/ANALYSIS_READY.json')
    need(registry.get('status')=='REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS' and registry.get('study_id')==STUDY_ID,
         'Current evaluation registration required')
    need(ready.get('status')=='READY_BEFORE_CONFIRMATION_TEST_ACCESS' and ready.get('study_id')==STUDY_ID
         and ready['registration_sha256']==registry_sha,'Independent readiness binding differs')
    need(release['registration_sha256']==registry_sha and release['independent_replay_ready_sha256']==ready_sha,'Release registry/readiness binding differs')
    official,official_sha=bound(Q/'confirmation_evaluation/EVALUATION_COMMIT.json')
    need(official.get('status')=='completed' and official.get('study_id')==STUDY_ID
         and official.get('report_count')==120 and official.get('prediction_file_count')==120
         and official.get('population_count')==4 and official.get('payload_count')==250,'Complete official evaluation required')
    need(official['release_sha256']==release_sha and official['registration_sha256']==registry_sha,'Official completion bindings differ')
    folder=ROOT/'analysis/independent_replay/confirmation_replay'
    replay,replay_sha=bound(folder/'REPLAY_COMMIT.json')
    need(replay.get('status')=='completed' and replay.get('study_id')==STUDY_ID
         and replay.get('endpoint_count')==120 and replay.get('population_count')==4
         and replay.get('payload_count')==138,'Complete independent scoring replay required')
    need(replay['release_sha256']==release_sha and replay['official_commit_sha256']==official_sha
         and replay['ready_sha256']==ready_sha and replay['analysis_protocol_sha256']==sha(ROOT/'governance/ANALYSIS_PROTOCOL.json'),
         'Independent replay completion bindings differ')
    expected={'ACCESS_EVENT.json','summary.json'}
    for population in POPULATIONS['B']:
        expected.update(f'{population}/{name}' for name in ('population_summary.json','probabilities_replayed.npz','bootstrap_counts.npy','bootstrap_values.npy'))
        expected.update(f'{population}/seed_{seed}/{method}/report.json' for seed in SEEDS['B'] for method in METHODS)
    need(set(replay['files'])==expected,'Replay declared inventory differs')
    actual=set()
    for path in folder.rglob('*'):
        need(not path.is_symlink() and not (hasattr(path,'is_junction') and path.is_junction()),'Replay evidence link forbidden')
        if path.is_file() and path.relative_to(folder).as_posix()!='REPLAY_COMMIT.json':actual.add(path.relative_to(folder).as_posix())
    need(actual==expected,'Replay physical inventory differs')
    for name,item in replay['files'].items():
        path=inside(folder,name)
        need(type(item['bytes']) is int and item['bytes']>=0 and path.stat().st_size==item['bytes']
             and sha(path)==item['sha256'],'Completed replay payload changed')
        watched[path]=item['sha256']
    return watched,{'release_sha256':release_sha,'official_commit_sha256':official_sha,
        'independent_replay_commit_sha256':replay_sha,'scope':'Completion gate hashes committed test-replay evidence without parsing test metric values. All reported learning metrics derive from observed-label training/validation records only.'}


def input_gate(stage,author_path,independent_path):
    need(stage in SEEDS,'Unregistered stage');author_path=Path(author_path).resolve();independent_path=Path(independent_path).resolve()
    expected_lock=Q/('STAGE_A_ENDPOINT_LOCK.json' if stage=='A' else 'CONFIRMATION_ENDPOINT_LOCK.json')
    need(author_path==expected_lock.resolve(),'Canonical author lock required')
    need(independent_path.is_relative_to(ROOT.resolve()),'Independent audit must be inside study root')
    completion_watched,completion_proof=completed_replay_gate()
    author,ah=read_bound(author_path);independent,ih=read_bound(independent_path)
    freeze_path=Q/f'STAGE_{stage}_FREEZE.json';freeze,fh=read_bound(freeze_path)
    protocol_path=ROOT/'governance/ANALYSIS_PROTOCOL.json';protocol,ph=read_bound(protocol_path)
    plan_path=ROOT/'governance/STUDY_PLAN.json';plan,plan_sha=read_bound(plan_path);original_root=Path(plan['working_root'])
    seal_path=Q/'data/DATA_SEAL.json';seal,dh=read_bound(seal_path)
    count=len(SEEDS[stage])*len(POPULATIONS[stage])*len(METHODS)
    for obj in (author,independent):need(obj['status']=='PASS' and obj['stage']==stage and obj['engineering'] is False and obj['endpoint_count']==count,'Successful full official audits required')
    need(independent['endpoint_lock_sha256']==ah and independent['data_seal_sha256']==author['data_seal_sha256']==dh,'Audit lock/data mismatch')
    need(author['stage_freeze_sha256']==fh and freeze['review_status']=='approved_by_root','Stage freeze mismatch')
    need(author['analysis_protocol_sha256']==independent['analysis_protocol_sha256']==ph,'Analysis protocol binding mismatch')
    need(independent['validation_rounds_replayed']==count*200,'Every validation round must be independently verified')
    need(independent['validation_predictions_replayed']==count*200*1600,'Every validation record prediction must be independently verified')
    need(author['test_accessed'] is False and independent['model_test_outcomes_accessed'] is False,'Audits must exclude test model outcomes')
    need(plan['study_id']==protocol['study_id']==STUDY_ID and tuple(protocol['methods'])==METHODS and tuple(protocol['training_seeds'])==SEEDS['B'],'Study/analysis inventory differs')
    need(freeze['methods']==list(METHODS) and freeze['populations']==list(POPULATIONS[stage]) and freeze['training_seeds']==list(SEEDS[stage]),'Frozen stage inventory differs')
    need(freeze['data_seal_sha256']==dh,'Frozen data seal differs')
    need(protocol['milestones']['thresholds']==list(THRESHOLDS.values()) and protocol['milestones']['threshold']==.97 and protocol['milestones']['cadence_updates']==75 and protocol['milestones']['confirmation_checks']==3,'Milestone protocol differs')
    auditor=ROOT/'analysis/classical_review/audit_endpoints_v06.py';need(independent['auditor_sha256']==sha(auditor),'Independent auditor changed')
    watched={author_path:ah,independent_path:ih,freeze_path:fh,protocol_path:ph,plan_path:plan_sha,seal_path:dh,auditor:sha(auditor),Path(__file__):sha(__file__)}
    watched.update(completion_watched)
    for name,h in independent['independent_source_sha256'].items():
        path=inside(auditor.parent,name);need(sha(path)==h,'Independent oracle changed');watched[path]=h
    need(author['source_hashes']==freeze['source_hashes'],'Frozen source identity differs')
    for name,h in freeze['source_hashes'].items():
        path=inside(Q,name);need(sha(path)==h,'Frozen training source changed');watched[path]=h
    for name,h in author['audit_source_hashes'].items():
        path=mapped_historical_path(name,original_root);need(sha(path)==h,'Author audit changed');watched[path]=h
    expected={(p,s,m) for p in POPULATIONS[stage] for s in SEEDS[stage] for m in METHODS}
    ar={(r['population'],r['seed'],r['method']):r for r in author['endpoints']}
    ir={(r['population'],r['seed'],r['method']):r for r in independent['endpoints']}
    need(len(author['endpoints'])==len(independent['endpoints'])==count and set(ar)==set(ir)==expected,'Endpoint inventory differs')
    status_path=Q/f'stage_{stage}/stage_status.json';status,sh=read_bound(status_path);watched[status_path]=sh
    need(status['status']=='completed' and status['stage']==stage and status['expected_endpoints']==status['committed_endpoints']==count and sorted((r['seed'],r['exit_code']) for r in status['exits'])==[(s,0) for s in SEEDS[stage]],'Stage workers not complete')
    expected_folders={endpoint_folder(stage,row,original_root) for row in ar.values()}
    need({p.parent.resolve() for p in (Q/f'stage_{stage}').glob('*/seed_*/*/endpoint_commit.json')}==expected_folders,'Physical stage endpoint inventory differs')
    for key,row in ar.items():
        pop,seed,method=key;folder=endpoint_folder(stage,row,original_root)
        commit_path=folder/'endpoint_commit.json';commit,ch=read_bound(commit_path);watched[commit_path]=ch
        need(ch==row['endpoint_commit_sha256']==ir[key]['endpoint_commit_sha256'],'Audited endpoint commit differs')
        need(commit['status']=='completed' and commit['test_accessed'] is False and commit['source_hashes']==freeze['source_hashes'],'Endpoint completion/source differs')
        need((commit['population'],commit['seed'],commit['method'])==key,'Endpoint commit identity differs')
        need(ir[key]['rounds_verified']==200 and ir[key]['validation_predictions_replayed']==200*1600,'Independent endpoint replay horizon differs')
        need(commit['files']==row['files'] and row['rounds']==200 and row['optimizer_updates']==15000,'Author endpoint evidence differs')
        need({p.name for p in folder.iterdir() if p.is_file() and p.name!='endpoint_commit.json'}==set(commit['files']),'Endpoint inventory changed')
        need(not any(p.is_dir() for p in folder.iterdir()),'Unexpected endpoint subdirectory')
        for name,item in commit['files'].items():
            need(Path(name).name==name,'Unsafe endpoint payload name');path=inside(folder,name)
            need(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'Endpoint payload changed');watched[path]=item['sha256']
    return author,independent,seal,status,watched,original_root,completion_proof

def endpoint_summary(stage,row,original_root):
    folder=endpoint_folder(stage,row,original_root);result=read(folder/'result.json');config=read(folder/'config.json')
    ledger=[json.loads(line) for line in (folder/'ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    need(len(ledger)==200 and [r['round'] for r in ledger]==list(range(1,201)) and [r['optimizer_updates'] for r in ledger]==list(range(75,15001,75)),'Incomplete validation history')
    milestone_set={key:milestones([r['validation']['macro_f1'] for r in ledger],[r['elapsed_seconds'] for r in ledger],threshold=threshold) for key,threshold in THRESHOLDS.items()}
    milestone=milestone_set['97']
    selected=int(result['selected_round']);need(1<=selected<=200,'Invalid selection')
    need(result['test_accessed'] is False and config['test_accessed'] is False,'Unexpected test access in training result')
    need(result['completed_rounds']==200 and result['optimizer_global_updates']==15000,'Endpoint full horizon required')
    need(selected==min(range(200),key=lambda i:ledger[i]['validation']['bce'])+1,'Saved validation selection differs')
    need(result['selected_validation']==ledger[selected-1]['validation'],'Selected validation ledger/result differs')
    need(result['parameter_count']+result['fixed_core_parameter_count']==result['stored_model_parameter_count'],'Stored parameter accounting differs')
    with np.load(folder/'round_gradient_means.npz',allow_pickle=False) as f:mean_vectors=np.asarray(f['gradients'])
    need(mean_vectors.shape==(200,result['parameter_count']) and np.isfinite(mean_vectors).all(),'Invalid gradient diagnostic history')
    norms=np.linalg.norm(mean_vectors,axis=1);indices={'first':0,'selected':selected-1,'last':199}
    gradients={name:{'round':index+1,'mean_batch_gradient_norm':ledger[index]['mean_batch_gradient_norm'],
                    'maximum_batch_gradient_norm':ledger[index]['maximum_batch_gradient_norm'],
                    'norm_of_mean_batch_gradient_vector':float(norms[index])} for name,index in indices.items()}
    gradients['selected_full_training_gradient_norm']=result['selected_training_gradient_norm']
    gradients['selected_full_training_group_norms']=result['selected_training_gradient_group_norms']
    for name,index in indices.items():
        gradients[name]['mean_batch_group_norms']=ledger[index]['mean_batch_gradient_group_norms']
        gradients[name]['maximum_batch_group_norms']=ledger[index]['maximum_batch_gradient_group_norms']
    gradients['scope']='Stored diagnostics from training batches/selected checkpoint; gradient cancellation can make norm(mean vector) smaller than mean(norm). No independent optimizer rerun.'
    fullwork={**result['work'],'inference_four_uncached':result['inference']['work_four_uncached_forwards'],
              'inference_fifth_cached':result['inference']['work_fifth_cached_comparison']}
    cache=result['frozen_cache'];prep=result['preparation'];frozen=row['method']=='qfrozen_kmeans'
    need(not frozen and cache['enabled'] is False and result['fixed_core_parameter_count']==0 and result['has_native_logits'] is True,'v0.6 native/trainable model contract differs')
    need(fullwork['fixed_feature_preparation']==cache['work'],'Cache work differs from result work')
    need(np.isfinite(cache['seconds']) and cache['seconds']>=0 and type(cache['bytes']) is int and cache['bytes']>=0,'Invalid cache resource values')
    charged=result['training_seconds']+cache['seconds']+sum(prep[k] for k in ('generation_seconds_charged','joint_router_fit_seconds_charged','train_validation_cache_seconds_charged'))
    need(abs(charged-result['charged_training_seconds'])<=1e-9,'Charged time arithmetic differs')
    if frozen:
        need(set(cache['records'])=={'train','validation'} and cache['bytes']==sum(r['bytes'] for r in cache['records'].values()),'Cache byte accounting differs')
    else:need(cache['bytes']==0 and cache['seconds']==0 and cache['work']=={},'Nonfrozen cache charge')
    need(result['training_clipped_probabilities']==sum(r['training_clipped_probabilities'] for r in ledger),'Training clip total differs')
    need(result['training_clipped_wrong_probabilities']==sum(r['training_clipped_wrong_probabilities'] for r in ledger),'Wrong clipped total differs')
    need(result['legacy_outside_clip_zero_derivative_visits']==sum(r['legacy_outside_clip_zero_derivative_visits'] for r in ledger),'Legacy derivative count differs')
    loss_curve=[{'round':r['round'],'optimizer_updates':r['optimizer_updates'],
        'training_native_bce':r['training_loss'],'training_common_clipped_bce':r['training_common_clipped_bce'],
        'validation_native_bce':r['validation_native']['native_bce'],
        **{'validation_'+k:r['validation'][k] for k in ('bce','macro_f1','accuracy','brier','ece10','clipped')},
        'training_clipped_probability_visits':r['training_clipped_probabilities'],
        'training_wrong_clipped_probability_visits':r['training_clipped_wrong_probabilities'],
        'training_forward_extrema':r['training_forward_extrema'],'validation_native_diagnostics':r['validation_native'],
        'elapsed_seconds':r['elapsed_seconds']} for r in ledger]
    return {'stage':stage,'population':row['population'],'seed':row['seed'],'method':row['method'],
       'endpoint_commit_sha256':row['endpoint_commit_sha256'],'selected_checkpoint_sha256':row['files']['selected_checkpoint.npz']['sha256'],
       'ledger_sha256':row['files']['ledger.jsonl']['sha256'],'selected_round':selected,'selected_update':75*selected,
       'selected_validation':result['selected_validation'],'selected_training':result['selected_training'],
       'selected_validation_native':result['selected_validation_native'],
       'selected_training_native_bce':result['selected_training_native_bce'],
       'selected_training_forward_extrema':result['selected_training_forward_extrema'],
       'training_objective':result['training_objective'],'has_native_logits':result['has_native_logits'],
       'first_validation_native':ledger[0]['validation_native'],'final_validation_native':ledger[-1]['validation_native'],
       'loss_curve':loss_curve,
       'first_validation':ledger[0]['validation'],'final_validation':ledger[-1]['validation'],'milestones':milestone,
       'milestones_by_threshold':milestone_set,
       'annulus_milestone_caution':row['population'].endswith('_annulus'),
       'gradients':gradients,'parameter_count':result['parameter_count'],'bank_count':result['bank_count'],
       'trainable_parameter_count':result['parameter_count'],'fixed_core_parameter_count':result['fixed_core_parameter_count'],
       'stored_model_parameter_count':result['stored_model_parameter_count'],
       'parameters_per_bank':result['parameters_per_bank'],'train_bank_counts':result['train_bank_counts'],
       'bank_training_record_visits':result['bank_training_record_visits'],'validation_route_counts':result['validation_route_counts'],
       'training_records_seen':200*4800,'validation_records_seen':200*1600,'optimizer_updates':15000,
       'training_clipped_probability_visits':result['training_clipped_probabilities'],
       'training_clipped_probability_fraction':result['training_clipped_probabilities']/(200*4800),
       'training_wrong_clipped_probability_visits':result['training_clipped_wrong_probabilities'],
       'legacy_outside_clip_zero_derivative_visits':result['legacy_outside_clip_zero_derivative_visits'],
       'validation_clipped_probability_visits':sum(r['validation']['clipped'] for r in ledger),
       'work_by_phase':fullwork,'preparation':result['preparation'],'frozen_cache':cache,
       'timing':{'training_loop_seconds':result['training_seconds'],'charged_training_loop_seconds':result['charged_training_seconds'],
                 'endpoint_timer_seconds':result['endpoint_total_seconds'],'frozen_cache_creation_seconds':cache['seconds'],
                 'inference_seconds_per_record':result['inference']['mean_seconds_per_record'],
                 'inference_total_repeat_seconds':result['inference']['total_repeat_seconds'],'inference_route_repeat_seconds':result['inference']['route_repeat_seconds']},
       'source_hashes':config['source_hashes'],'test_accessed':False}

def add_counters(destination,source):
    """Preserve nested cache train/validation counters; never count moments as states."""
    need(isinstance(source,dict),'Work counter mapping required')
    for key,value in source.items():
        if isinstance(value,dict):
            need(key not in destination or isinstance(destination[key],dict),'Work counter shape changed')
            add_counters(destination.setdefault(key,{}),value)
        else:
            need(type(value) is int and value>=0,'Nonnegative integer work counter required')
            need(key not in destination or type(destination[key]) is int,'Work counter shape changed')
            destination[key]=destination.get(key,0)+value

def aggregate(rows):
    result={}
    for method in METHODS:
        cells=sorted((r for r in rows if r['method']==method),key=lambda r:r['seed']);work={}
        for row in cells:
            add_counters(work,row['work_by_phase'])
        result[method]={'n':len(cells),'seeds':[r['seed'] for r in cells],
          'selected_round':finite_summary(r['selected_round'] for r in cells),
          'selected_validation':{k:finite_summary(r['selected_validation'][k] for r in cells) for k in ('bce','macro_f1','accuracy','brier','ece10')},
          'final_validation':{k:finite_summary(r['final_validation'][k] for r in cells) for k in ('bce','macro_f1','accuracy','brier','ece10')},
          'native_bce':{'selected_validation':finite_summary(r['selected_validation_native']['native_bce'] for r in cells),
                        'selected_training':finite_summary(r['selected_training_native_bce'] for r in cells),
                        'final_validation':finite_summary(r['final_validation_native']['native_bce'] for r in cells)},
          'parameter_counts':{k:sorted({r[k] for r in cells}) for k in ('trainable_parameter_count','fixed_core_parameter_count','stored_model_parameter_count')},
          **{prefix+key:reaching_summary(cells,prefix,key) for key in THRESHOLDS for prefix in ('first','confirmed')},
          'timing':{k:finite_summary(r['timing'][k] for r in cells) for k in ('training_loop_seconds','charged_training_loop_seconds','endpoint_timer_seconds','frozen_cache_creation_seconds','inference_seconds_per_record')},
          'cache_array_bytes':finite_summary(r['frozen_cache']['bytes'] for r in cells),
          'sum_actual_endpoint_cache_creation_seconds':sum(r['frozen_cache']['seconds'] for r in cells),
          'sum_recorded_work_by_phase':work,
          'sum_training_record_visits':sum(r['training_records_seen'] for r in cells),
          'sum_validation_record_visits':sum(r['validation_records_seen'] for r in cells),
          'sum_training_clipped_probability_visits':sum(r['training_clipped_probability_visits'] for r in cells),
          'sum_training_wrong_clipped_probability_visits':sum(r['training_wrong_clipped_probability_visits'] for r in cells),
          'sum_validation_clipped_probability_visits':sum(r['validation_clipped_probability_visits'] for r in cells),
          'sum_legacy_outside_clip_zero_derivative_visits':sum(r['legacy_outside_clip_zero_derivative_visits'] for r in cells)}
    return result

def write_csv(path,rows):
    names=('population','seed','method','selected_round','selected_update','first97_update','confirmed97_sequence_start_update',
       'confirmed97_update','not_first97_reached','not_confirmed97_reached','selected_validation_bce','selected_validation_macro_f1',
       'final_validation_bce','final_validation_macro_f1','training_loop_seconds','charged_training_loop_seconds',
       'endpoint_timer_seconds','inference_seconds_per_record','parameter_count','bank_count','training_record_visits',
       'validation_record_visits','training_clipped_probability_visits','bank_training_record_visits','endpoint_commit_sha256','selected_checkpoint_sha256',
       'selected_validation_brier','selected_validation_ece10','selected_validation_native_bce','selected_training_native_bce',
       'final_validation_native_bce','training_wrong_clipped_probability_visits','validation_clipped_probability_visits',
       'legacy_outside_clip_zero_derivative_visits','trainable_parameter_count','fixed_core_parameter_count',
       'stored_model_parameter_count','frozen_cache_creation_seconds','frozen_cache_array_bytes')
    names+=tuple(prefix+key+suffix for key in ('90','95') for prefix,suffix in (('first','_update'),('confirmed','_sequence_start_update'),('confirmed','_update'),('not_first','_reached'),('not_confirmed','_reached')))
    with Path(path).open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=names);writer.writeheader()
        for r in rows:
            m=r['milestones'];writer.writerow({**{k:r[k] for k in ('population','seed','method','selected_round','selected_update','parameter_count','bank_count','training_clipped_probability_visits','endpoint_commit_sha256','selected_checkpoint_sha256')},
             'first97_update':m['first_update'],'confirmed97_sequence_start_update':m['confirmed_sequence_start_update'],'confirmed97_update':m['confirmed_update'],
             'not_first97_reached':not m['first_reached'],'not_confirmed97_reached':not m['confirmed_reached'],
             'selected_validation_bce':r['selected_validation']['bce'],'selected_validation_macro_f1':r['selected_validation']['macro_f1'],
             'final_validation_bce':r['final_validation']['bce'],'final_validation_macro_f1':r['final_validation']['macro_f1'],
             'selected_validation_brier':r['selected_validation']['brier'],'selected_validation_ece10':r['selected_validation']['ece10'],
             'selected_validation_native_bce':r['selected_validation_native']['native_bce'],
             'selected_training_native_bce':r['selected_training_native_bce'],'final_validation_native_bce':r['final_validation_native']['native_bce'],
             **{k:r[k] for k in ('training_wrong_clipped_probability_visits','validation_clipped_probability_visits',
                 'legacy_outside_clip_zero_derivative_visits','trainable_parameter_count','fixed_core_parameter_count','stored_model_parameter_count')},
             'frozen_cache_creation_seconds':r['timing']['frozen_cache_creation_seconds'],'frozen_cache_array_bytes':r['frozen_cache']['bytes'],
             **{k:r['timing'][k] for k in ('training_loop_seconds','charged_training_loop_seconds','endpoint_timer_seconds','inference_seconds_per_record')},
             'training_record_visits':r['training_records_seen'],'validation_record_visits':r['validation_records_seen'],
             'bank_training_record_visits':json.dumps(r['bank_training_record_visits']),
             **{prefix+key+suffix: (not r['milestones_by_threshold'][key][field] if prefix.startswith('not_') else r['milestones_by_threshold'][key][field])
                for key in ('90','95') for prefix,suffix,field in (('first','_update','first_update'),('confirmed','_sequence_start_update','confirmed_sequence_start_update'),('confirmed','_update','confirmed_update'),('not_first','_reached','first_reached'),('not_confirmed','_reached','confirmed_reached'))}})

def run(stage,author_path,independent_path,output):
    output=Path(output);need(not output.exists(),'Preserve prior analysis; output must be absent')
    need(output.resolve().is_relative_to((ROOT/'analysis').resolve()),'Output must remain inside the current analysis folder')
    author,independent,seal,status,watched,original_root,completion_proof=input_gate(stage,author_path,independent_path)
    output.mkdir(parents=True,exist_ok=False)
    try:
        rows=[endpoint_summary(stage,row,original_root) for row in author['endpoints']]
        populations={}
        for pop in POPULATIONS[stage]:
            cells=[r for r in rows if r['population']==pop];value={'population':pop,'stage':stage,'endpoint_count':len(cells),'methods':aggregate(cells),'endpoints':cells}
            write(output/(pop+'.json'),value);write_csv(output/(pop+'.csv'),cells);populations[pop]=value['methods']
        write_csv(output/'endpoint_metrics.csv',rows)
        result={'status':'PASS','study_id':STUDY_ID,'stage':stage,'created_utc':datetime.now(timezone.utc).isoformat(),'endpoint_count':len(rows),
          'source_sha256':sha(__file__),'author_audit_sha256':sha(author_path),'independent_audit_sha256':sha(independent_path),
          'post_release_completion_gate':completion_proof,
          'analysis_protocol_sha256':sha(ROOT/'governance/ANALYSIS_PROTOCOL.json'),'data_seal_sha256':sha(Q/'data/DATA_SEAL.json'),
          'path_handling':{'declared_original_working_root':str(original_root),'current_analysis_root':str(ROOT),'rule':'Historical absolute endpoint/source paths validated against original STUDY_PLAN working_root and remapped by study-relative identity; metadata bytes unchanged.'},
          'stage_execution_observed_wall_seconds':status['observed_wall_seconds'],
          'sum_endpoint_training_loop_seconds':sum(r['timing']['training_loop_seconds'] for r in rows),
          'sum_endpoint_charged_training_loop_seconds':sum(r['timing']['charged_training_loop_seconds'] for r in rows),
          'sum_endpoint_timer_seconds':sum(r['timing']['endpoint_timer_seconds'] for r in rows),
          'sum_actual_endpoint_frozen_cache_creation_seconds':sum(r['frozen_cache']['seconds'] for r in rows),
          'sum_actual_endpoint_frozen_cache_array_bytes':sum(r['frozen_cache']['bytes'] for r in rows),
          'populations':populations,'preparation_actual_recorded_by_population':{p:seal['datasets'][p] for p in POPULATIONS[stage]},
          'scope':['Validation learning only; all200rounds/15000updates actually completed. No model test outcomes or early-checkpoint test evaluation.',
          'Registered90/95/97 thresholds are descriptive only. First threshold crossing and first completed three-check streak are different. Confirmation is150updates after its own qualifying sequence start, not necessarily150after first-ever crossing.',
          'Annulus labels include independent10percent flips;97percent observed-label validationF1 is not a sensible expected generalization requirement. Latent labels never enter milestones.',
          'Nonreachers counted and censored; reached-only medians are conditional and not estimates for allruns. No earlystopping savings are claimed.',
          'Selected checkpoint minimizes validationBCE; its validationF1 is not a separate best-F1 selection.',
          'Training loop timer covers batchtraining,allvalidation,and within-loop checkpoint/evidence work. Initial data/model setup and frozenfeaturecachecreation excluded; endpointtimer includes cachecreation and posttrainingdiagnostics but stops before finalresult/commitwrites.',
          'Logged milestone elapsed ends at that round ledger construction; later ledger/status writes are outside that recorded instant.',
          'Chargedtraining is trainingloop plus actual endpoint frozen-featurecachecreation plus reused applicablegeneration/routerfit/train-validation-route-cache charges. Population preparation charges repeated acrossarms/seeds are accounting, not extra actualprojectwalltime.',
          'Native logistic BCE is unbounded for all six arms; common clipped BCE is the registered selection/comparison metric. Training batch-average native/clipped curves use changing parameters and are not fixed-checkpoint training loss.',
          'No v0.6 arm has a separately frozen core or cached moment features; recorded frozen-cache creation and bytes must be zero. General cache byte fields denote feature-array bytes, excluding container/file overhead. No fitted router parameter is counted as a trained model weight.',
          'Nested fixed_feature_preparation train/validation counters are separate from cached head-training work. Five moments from one state are not five independent circuit evolutions; measurement-setting equivalents are logical counters, not executed hardware shots.',
          'Parallel workers overlap: summed endpoint seconds must not be labelled elapsedprojecttime. Stage observedwalltime is a separate launchermeasurement.',
          'Inference timers use loaded rawcoordinates, uncachedrouter+model, three repeats afteronewarmup; excludedIO/model-loading/fit. A fifthcached check is separatelycounted. Hostconcurrenttimings descriptive. These training-run reference timers are separate from the later deployment/compiler experiment, whose results are reported in its own artifact.',
          'Operation counts are logicalcircuits/gates and feature/activation/examples, not measuredFLOPs,MACs,hardwarelatency or energy.',
          'Gradientcurves and clipping/exposure diagnostics are recordedtrainingmeasurements, not an independent replay of everyoptimizerstep.']}
        for path,h in watched.items():need(sha(path)==h,'Bound input changed during analysis')
        write(output/'summary.json',result)
        files={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in output.iterdir() if p.is_file()}
        write(output/'ANALYSIS_COMMIT.json',{'status':'PASS','study_id':STUDY_ID,'stage':stage,'endpoint_count':len(rows),'files':files,
             'source_sha256':sha(__file__),'created_utc':datetime.now(timezone.utc).isoformat(),'test_accessed':False})
        print(json.dumps({'status':'PASS','stage':stage,'endpoints':len(rows),'summary_sha256':sha(output/'summary.json')}))
    except BaseException:
        write(output/'FAILURE.json',{'status':'FAIL','traceback':traceback.format_exc(),'test_accessed':False});raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=SEEDS,required=True);p.add_argument('--author-lock',type=Path,required=True)
    p.add_argument('--independent-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(args.stage,args.author_lock,args.independent_audit,args.output)
