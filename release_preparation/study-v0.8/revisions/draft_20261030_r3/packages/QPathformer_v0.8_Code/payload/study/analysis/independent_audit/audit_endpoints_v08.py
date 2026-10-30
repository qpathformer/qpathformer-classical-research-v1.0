"""Independent all-round validation audit. No production models or test loader.

All checks use explicit exceptions, including under Python -O. Official use
requires closed full-stage execution and the separately authored endpoint lock.
Every retained raw gradient drives a separately implemented Adam replay;
predeclared gradient probes are independently recomputed, not every gradient.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, csv, hashlib, json, sqlite3, sys, time, traceback
import numpy as np
import reference_v08 as ref
from audit_sampling_trace import audit_trace,GRADIENT_ATOL,GRADIENT_RTOL,STATE_ATOL,PRIORITY_ATOL,SPOT_ROUNDS,SPOT_BATCHES

ROOT=Path(__file__).resolve().parents[2];Q=ROOT/'quantum';HERE=Path(__file__).resolve().parent
ARM_METHODS={base+'_'+mode:method for base,method in zip(('MultiK','MultiHash','TrigK','TrigHash','TrigG121'),ref.METHODS) for mode in ('U','P')}
STAGE_COUNTS={'engineering':40,'A':80,'B':640}
PTOL=2e-12;BTOL=1e-8;CTOL=2e-12;ZTOL=1e-9;NTOL=1e-8;BAND=32*np.finfo(np.float64).eps

def need(condition,message):
    if not condition:raise RuntimeError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rawsha(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def remap(name,relative_base=None):
    """Resolve preserved original-root identities into the current copy, never the old tree."""
    p=Path(name)
    if p.is_absolute():
        original=ROOT.resolve()
        try:rel=p.relative_to(original)
        except ValueError:raise RuntimeError('Absolute identity outside declared original root: '+str(p))
        result=ROOT/rel
    else:result=(Q if relative_base is None else relative_base)/p
    result=result.resolve()
    need(result.is_relative_to(ROOT.resolve()),'Identity escapes current study root')
    return result
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def load_primary_population(p):
    """Read only primary observed-label evidence; never expose clean/noise arrays."""
    allowed=('x','y','ids','source_draw_ids','hash_route','kmeans_route','margin_bin')
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in allowed}
def same(a,b,message):need(np.array_equal(a,b),message)
def near(a,b,tol,message):need(np.isfinite(a).all() and np.isfinite(b).all() and np.max(np.abs(np.asarray(a)-np.asarray(b)),initial=0)<=tol,message)
def metric_check(a,b):
    need(set(a)==set(b),'Metric inventory differs')
    for k in a:
        if k in ('bce','macro_f1','accuracy','brier','ece10'):near(a[k],b[k],CTOL,'Canonical metric differs: '+k)
        elif k=='reliability10':
            need(len(a[k])==len(b[k])==10,'Calibration bin count differs')
            edges=np.linspace(0.,1.,11)
            for i,(left,right) in enumerate(zip(a[k],b[k])):
                # The independent oracle intentionally uses its own field naming.
                nn=left.get('n',left.get('count'));pm=left.get('mean_probability');rate=left.get('positive_fraction',left.get('fraction_positive'))
                need(right['bin']==i and right['count']==nn,'Calibration bin membership differs')
                near(right['lower'],edges[i],0.,'Calibration lower boundary differs');near(right['upper'],edges[i+1],0.,'Calibration upper boundary differs')
                if nn:
                    near(right['mean_probability'],pm,CTOL,'Calibration mean p differs');near(right['fraction_positive'],rate,CTOL,'Calibration mean label differs')
                else:need(right['mean_probability'] is None and right['fraction_positive'] is None,'Empty calibration means must be null')
        else:need(a[k]==b[k],'Canonical exact metric differs: '+k)

def expected_initial(method,streams):
    family,routing=method.split('_');banks=1 if routing=='global' else 5
    if family.startswith('q'):
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(int(streams['paired_circuit_core_initialization']['uint128_decimal']))))
        master=rng.uniform(-.1,.1,(5,4,2,2));core=master[:banks,:2].copy()
        if family=='q2':return core.reshape(-1),master,np.empty(0)
        head=np.zeros((banks,2 if family=='qscalar' else 6));head[:,0]=2.
        if family=='qfrozen':return head.ravel(),master,core
        return np.column_stack((core.reshape(banks,8),head)).ravel(),master,np.empty(0)
    if family.startswith('trig'):
        master=np.zeros((banks,121 if family=='trig121' else 25));return master.ravel(),master,np.empty(0)
    h=32 if routing=='global' else int(family[3:].replace('relu','').replace('tanh',''))
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(int(streams['mlp_initialization']['uint128_decimal']))))
    master=[]
    for _ in range(banks):
        a=np.sqrt(6/(2+h));b=np.sqrt(6/(h+1))
        master.append(np.r_[rng.uniform(-a,a,2*h),np.zeros(h),rng.uniform(-b,b,h),0.])
    master=np.asarray(master);return master.ravel(),master,np.empty(0)

def expected_work(method,n,gradient=False,cached=False,preparation=False):
    family,routing=method.split('_');q=family.startswith('q');legacy=family=='q2';frozen=family=='qfrozen';moments=0 if legacy or not q else (1 if family=='qscalar' else 5)
    forward=n if q and not cached else 0;shift=16*n if q and not frozen and gradient else 0;c=forward+shift
    h=0 if not family.startswith('mlp') else (32 if family=='mlp' else int(family[3:].replace('relu','').replace('tanh','')))
    w={'forward_circuit_examples':forward,'shift_circuit_examples':shift,'circuit_examples':c,
       'layer_applications':2*c,'feature_ry_gates':4*c,'feature_rz_gates':0,
       'trainable_ry_gates':0 if frozen else 4*c,'trainable_rz_gates':0 if frozen else 4*c,'cx_gates':2*c,'readout_ry_gates':c if legacy else 0,
       'fixed_core_ry_gates':4*c if frozen else 0,'fixed_core_rz_gates':4*c if frozen else 0,
       'bank_record_visits':n,'model_record_visits':n,'classical_forward_examples':0 if legacy else n,
       'classical_backward_examples':n if not legacy and gradient else 0,
       'trig_feature_values':(121 if family=='trig121' else 25)*n if family.startswith('trig') else 0,'mlp_hidden_evaluations':n*h,
       'core_statevector_examples':c,'moment_values_computed':c*moments,
       'frozen_cached_feature_rows':n if cached else 0,'head_feature_values':n*moments,
       'measurement_settings_equivalent':c*(2 if moments==5 else 1)}
    if preparation:
        need(frozen and not cached and not gradient,'Invalid independent preparation scope')
        w.update(model_record_visits=0,bank_record_visits=0,classical_forward_examples=0,head_feature_values=0,feature_preparation_records=n)
    return w

def classes(y,pred):
    cm=np.array([[np.sum((y==a)&(pred==b)) for b in (0,1)] for a in (0,1)],int)
    f=[2*cm[k,k]/(cm[k].sum()+cm[:,k].sum()) if cm[k].sum()+cm[:,k].sum() else 0. for k in (0,1)]
    return {'macro_f1':float(np.mean(f)),'accuracy':float(np.mean(y==pred)),'confusion':cm.tolist()}

def threshold_check(y,p,r,ids):
    near(p,r,PTOL,'Independent probabilities differ')
    a=np.abs(p-.5)<=BAND;b=np.abs(r-.5)<=BAND;different=(p>=.5)!=(r>=.5)
    need(np.all(~different|(a&b)),'Independent class disagreement outside both-probabilities numeric band')
    sensitivity={}
    for key,assign in [('all0',np.zeros(len(y),int)),('all1',np.ones(len(y),int)),('allincorrect',1-y),('allcorrect',y)]:
        value=(p>=.5).astype(int);value[a]=assign[a];sensitivity[key]=classes(y,value)
    rows=[{'record_id':int(ids[i]),'canonical_probability':float(p[i]),'reference_probability':float(r[i]),
           'canonical_prediction':int(p[i]>=.5),'reference_prediction':int(r[i]>=.5)} for i in np.flatnonzero(different)]
    return {'canonical_band_records':int(a.sum()),'reference_band_records':int(b.sum()),
            'class_disagreements':int(different.sum()),'outside_band_disagreements':0,
            'disagreement_records':rows,'canonical_mask_sensitivity':sensitivity,'reference_classes':classes(y,r>=.5)}

def check_commit(folder):
    need(not folder.is_symlink() and not any(p.is_symlink() for p in folder.iterdir()),'Symlink endpoint unsupported')
    path=folder/'endpoint_commit.json';before=sha(path);c=read(path)
    need(c['status']=='completed' and c['test_accessed'] is False,'Endpoint not completed without test access')
    actual={p.name for p in folder.iterdir() if p.is_file() and p.name!='endpoint_commit.json'}
    need(actual==set(c['files']),'Committed payload inventory differs')
    need(not any(p.is_dir() for p in folder.iterdir()),'Unexpected endpoint subdirectory')
    for name,info in c['files'].items():
        need(Path(name).name==name,'Unsafe payload name');p=folder/name
        need(p.stat().st_size==info['bytes'] and sha(p)==info['sha256'],'Committed payload changed: '+name)
    need(before==sha(path),'Endpoint commit changed while reading')
    return c,before

def checkpoint(path,state,round_number,pcount,core,p,z,native):
    saved=load(path);need(set(saved)=={'parameters','core_parameters','adam_m','adam_v','adam_t','current_round','completed_rounds','validation_evidence_present','validation_probabilities','has_native_logits','validation_logits','validation_native_loss'},'Checkpoint fields differ')
    same(saved['core_parameters'],core,'Checkpoint frozen core differs')
    need(bool(saved['validation_evidence_present']) and bool(saved['has_native_logits'])==(z is not None),'Checkpoint validation/native flag differs')
    same(saved['validation_probabilities'],p,'Checkpoint validation p differs')
    same(saved['validation_logits'],np.array([]) if z is None else z,'Checkpoint native logits differ')
    same(saved['validation_native_loss'],np.array([native]),'Checkpoint native loss differs')
    z=saved
    same(z['parameters'],state,'Checkpoint parameter identity differs')
    for key in ('adam_m','adam_v'):
        need(z[key].shape==(pcount,) and z[key].dtype==np.float64 and np.isfinite(z[key]).all(),'Invalid optimizer moment')
    need(np.all(z['adam_v']>=0),'Negative second moment')
    need(int(z['adam_t'])==75*round_number and int(z['current_round'])==round_number and int(z['completed_rounds'])==round_number,'Checkpoint horizon/update counters differ')
    return z

def native_check(y,p,z,native,recorded):
    expected=ref.bce(y,p) if z is None else ref.stable_logit_bce(y,z)
    near(native,expected,NTOL,'Native aggregate loss differs')
    near(recorded['native_bce'],native,0.,'Recorded native loss differs from saved value')
    need(recorded['has_native_logits']==(z is not None),'Native-logit flag differs')
    near(recorded['minimum_raw_probability'],np.min(p),0.,'Validation p minimum differs')
    near(recorded['maximum_raw_probability'],np.max(p),0.,'Validation p maximum differs')
    for key,value in (('minimum_native_logit',None if z is None else np.min(z)),('maximum_native_logit',None if z is None else np.max(z))):
        if value is None:need(recorded[key] is None,'Legacy native logit must be null')
        else:near(recorded[key],value,0.,'Native logit extremum differs')
    wrong=int(np.sum(((p<ref.CLIP)|(p>1-ref.CLIP))&((p>=.5)!=y)))
    need(recorded['clipped_wrong_prediction_count']==wrong,'Wrong clipped count differs')
    if z is not None:
        linked=np.exp(-np.logaddexp(0.,-z))
        near(p,linked,PTOL,'Saved native logits do not yield saved probabilities')

def inspect_cache(folder,method,core,train,val,recorded):
    if method!='qfrozen_kmeans':
        need(recorded=={'enabled':False,'seconds':0.,'bytes':0,'work':{}},'Unexpected cache for trainable-core/classical model')
        need(not (folder/'frozen_cache.json').exists(),'Unexpected fixed feature cache')
        return {}
    meta=read(folder/'frozen_cache.json');need(meta==recorded and meta['enabled'] is True,'Frozen cache metadata differs')
    need(meta['core_sha256']==rawsha(core),'Frozen cache core identity differs')
    need(set(meta['records'])==set(meta['work'])=={'train','validation'},'Frozen cache split inventory differs')
    total=0;secs=0.
    for name,pop in (('train',train),('validation',val)):
        info=meta['records'][name];filename=f'frozen_{name}_moments.npy';need(info['file']==filename,'Frozen cache name differs')
        path=folder/filename;a=np.load(path,allow_pickle=False)
        need(a.shape==(len(pop['y']),5) and a.dtype==np.float64 and np.isfinite(a).all(),'Frozen cache invalid shape/type/value')
        near(a,ref.frozen_features(pop['x'],pop['kmeans_route'],core),PTOL,'Frozen cache does not match independent fixed core')
        need(info['file_sha256']==sha(path) and info['array_sha256']==rawsha(a),'Frozen cache digest differs')
        need(info['shape']==list(a.shape) and info['bytes']==a.nbytes and info['file_bytes']==path.stat().st_size,'Frozen cache storage differs')
        for key,array in (('ids_sha256',pop['ids']),('route_sha256',pop['kmeans_route']),('input_sha256',pop['x'])):need(info[key]==rawsha(array),'Frozen cache record/input identity differs')
        need(meta['work'][name]==expected_work(method,len(pop['y']),preparation=True),'Frozen preparation work differs')
        need(np.isfinite(info['compute_seconds']) and info['compute_seconds']>=0,'Invalid cache compute time')
        total+=a.nbytes;secs+=info['compute_seconds']
    need(meta['bytes']==total and np.isfinite(meta['seconds']) and meta['seconds']>=secs,'Frozen cache charge/storage differs')
    return meta['work']

def audit_endpoint(folder,job,seal,authorization):
    stage=job['stage'];population=job['population_id'];seed=job['training_seed_id']
    method=ARM_METHODS[job['arm']];engineering=stage=='engineering';freeze=read(authorization)
    need(freeze['review_status']=='approved_by_root' and freeze['schema']=='qpath-v08-stage-authorization-1','Root authority missing')
    need(freeze['stage']==stage and freeze['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json'),'Authority stage/data differs')
    need(freeze['matrix_sha256']==sha(ROOT/'governance/RUN_MATRIX.json') and freeze['protocol_sha256']==sha(ROOT/'governance/STUDY_PLAN.json'),'Authority protocol/matrix differs')
    expected_ids=[row['run_id'] for row in read(ROOT/'governance/RUN_MATRIX.json')['runs'] if row['stage']==stage]
    need(freeze['run_ids']==expected_ids,'Authority does not bind complete matrix stage')
    need(method in ref.METHODS,'Unregistered model method')
    commit,commit_sha=check_commit(folder);c=read(folder/'config.json');r=read(folder/'result.json');status=read(folder/'status.json')
    need(c['study_id']==r['study_id']=='QPATH-PRIORITY-ROUTING-v0.8','Study identity differs')
    for obj in (commit,c,r,status):
        for k,v in [('population',population),('seed',seed),('method',method)]:need(obj[k]==v,'Endpoint identity mismatch')
    need(c['stage']==r['stage']==stage and c['engineering']==r['engineering']==engineering,'Stage/engineering mismatch')
    need(r['status']==status['status']=='completed' and c['test_accessed'] is False and r['test_accessed'] is False,'Incomplete or test-accessed endpoint')
    rounds=int(c['rounds']);need(rounds==job['rounds']==(12 if engineering else 200),'Full horizon not completed')
    need(c['train_records']==4800 and c['validation_records']==1600 and c['batch_size']==64,'Record/batch budget differs')
    need(r['completed_rounds']==status['round']==commit['completed_rounds']==rounds and r['optimizer_global_updates']==commit['optimizer_global_updates']==job['updates']==75*rounds,'Endpoint update count differs')
    need(c['data_seal_sha256']==r['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json'),'Data seal binding differs')
    need(c['source_hashes']==commit['source_hashes'],'Commit/source mismatch')
    for name,value in c['source_hashes'].items():need(sha(remap(name))==value,'Source changed: '+name)
    need(c['source_hashes']==freeze['scientific_source_hashes'],'Source not frozen')
    need(c['settings']==freeze['settings'],'Settings differ from freeze')
    for obj in (c,r,commit):
        need(obj['job_id']==job['run_id'] and obj['arm']==job['arm'],'Exact matrix job/arm identity differs')
        need(obj['base_model']==job['base_model'] and obj['sampling_policy']==job['sampling_policy'],'Exact base model/sampling policy differs')
        need(obj['authorization_sha256']==sha(authorization),'Authorization binding differs')
        need(obj['matrix_sha256']==sha(ROOT/'governance/RUN_MATRIX.json') and obj['protocol_sha256']==sha(ROOT/'governance/STUDY_PLAN.json'),'Active protocol binding differs')
    need(c['paired_streams']==job['paired_streams'],'Paired RNG stream identity differs')
    for stream in job['paired_streams'].values():
        need(int.from_bytes(hashlib.sha256(stream['namespace'].encode('ascii')).digest()[:16],'little')==int(stream['uint128_decimal']),'RNG derivation differs')
    data=[]
    for split in ('train','validation'):
        path=Q/'data'/f'{population}_{split}.npz';need(sha(path)==seal['files'][path.name]['sha256'],'Population payload changed')
        data.append(load_primary_population(path))
    train,val=data;need(sha(Q/'data'/f'{population}_router.json')==c['router_policy_sha256']==seal['routers'][population]['sha256'],'Policy identity differs')
    identity=load(folder/'population_identity.npz');need(set(identity)=={'train_ids','validation_ids'},'Population identity keys differ')
    same(identity['train_ids'],train['ids'],'Training identities differ');same(identity['validation_ids'],val['ids'],'Validation identities differ')
    initial=load(folder/'initial_state.npz');theta,master,core=expected_initial(method,job['paired_streams'])
    need(set(initial)=={'parameters','master_initial','core_parameters'},'Initial state field inventory differs')
    same(initial['parameters'],theta,'Initialization differs');same(initial['master_initial'],master,'Master initialization differs')
    same(initial['core_parameters'],core,'Frozen initial core differs')
    frozen=method=='qfrozen_kmeans';legacy=method=='q2_kmeans';oracle_core=core if frozen else None
    cache_work=inspect_cache(folder,method,core,train,val,r['frozen_cache'])
    need(r['fixed_core_sha256']==rawsha(core),'Fixed core identity differs')
    states=np.load(folder/'round_parameters.npy',allow_pickle=False);probs=np.load(folder/'validation_probabilities.npy',allow_pickle=False);orders=np.load(folder/'record_orders.npy',allow_pickle=False)
    pc=ref.PARAMETERS[method];need(states.shape==(rounds,pc) and states.dtype==np.float64 and np.isfinite(states).all(),'Invalid saved parameter states')
    need(probs.shape==(rounds,1600) and probs.dtype==np.float64 and np.isfinite(probs).all() and np.all((probs>=0)&(probs<=1)),'Invalid full validation probabilities')
    need(orders.shape==(rounds,4800) and orders.dtype==np.uint16,'Invalid recorded orders')
    native=np.load(folder/'validation_native_losses.npy',allow_pickle=False)
    need(native.shape==(rounds,) and native.dtype==np.float64 and np.isfinite(native).all() and np.all(native>=0),'Native losses invalid')
    logits=None
    if not legacy:
        logits=np.load(folder/'validation_logits.npy',allow_pickle=False)
        need(logits.shape==(rounds,1600) and logits.dtype==np.float64 and np.isfinite(logits).all(),'All-round logits invalid')
    else:need(not (folder/'validation_logits.npy').exists(),'Legacy arm must not invent native logits')
    routing=method.split('_')[1];route=None if routing=='global' else val[routing+'_route']
    independent,independent_logits=ref.predict_many_with_logits(method,states,val['x'],route,oracle_core);near(probs,independent,PTOL,'All-round probability replay differs')
    max_logit=0.
    if logits is not None:
        near(logits,independent_logits,ZTOL,'All-round native logits differ');max_logit=float(abs(logits-independent_logits).max())
    # Fixed scalar spotchecks, independent of outcomes: endpoints/middle rounds and lowest7 validation IDs.
    spots=np.argsort(val['ids'],kind='stable')[:7];spot_rounds=sorted({0,rounds//2,rounds-1});scalar_error=0.
    for index in spot_rounds:
        scalar,sz=ref.scalar_predict_with_logits(method,states[index],val['x'][spots],None if route is None else route[spots],oracle_core)
        if sz is not None:near(sz,logits[index,spots],ZTOL,'Scalar native logit differs')
        scalar_error=max(scalar_error,float(np.max(abs(scalar-probs[index,spots]))));near(scalar,probs[index,spots],PTOL,'Scalar spotcheck differs')
    ledger=[json.loads(line) for line in (folder/'ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    need(len(ledger)==rounds,'Ledger horizon differs')
    sampling_audit=audit_trace(folder,job,method,train,states,orders,theta,ledger,metric_check,native_check)
    banks=1 if routing=='global' else 5;bank_counts=np.array([4800]) if banks==1 else np.bincount(train[routing+'_route'],minlength=5)
    need(r['parameter_count']==pc and r['bank_count']==banks and r['parameters_per_bank']==pc//banks,'Architecture counts differ')
    need(c['parameter_count']==pc and c['fixed_core_parameter_count']==r['fixed_core_parameter_count']==core.size and r['stored_model_parameter_count']==pc+core.size,'Trained/fixed/stored parameter counts differ')
    need(c['has_native_logits']==r['has_native_logits']==(not legacy),'Native model flag differs')
    need(r['train_bank_counts']==bank_counts.tolist(),'Training bank allocation differs')
    appearances=np.zeros(banks,dtype=np.int64)
    best=float('inf');chosen=None;chosen_generations=[];last_elapsed=0.;all_threshold=[];max_bce=0.;clip_total=0;wrong_total=0;max_native=0.
    for i,row in enumerate(ledger):
        number=i+1;need(row['round']==number and row['optimizer_updates']==75*number,'Ledger counters differ')
        for batch in orders[i].reshape(75,64):
            counts=np.array([64]) if banks==1 else np.bincount(train[routing+'_route'][batch],minlength=5)
            appearances+=(counts>0)
        need(row['bank_minibatch_appearances_cumulative']==appearances.tolist(),'Per-bank minibatch appearances differ')
        need(row['bank_absent_updates_cumulative']==(75*number-appearances).tolist(),'Absent bank update count differs')
        for key in ('bank_absent_parameter_movement_l2_sum_cumulative','bank_gradient_l2_sum_cumulative'):
            values=np.asarray(row[key],float)
            need(values.shape==(banks,) and np.isfinite(values).all() and np.all(values>=0),'Invalid bank diagnostic '+key)
            if i:need(np.all(values+1e-12>=np.asarray(ledger[i-1][key])),'Nonmonotone bank diagnostic '+key)
        need(np.all(np.asarray(row['bank_absent_parameter_movement_l2_sum_cumulative'])[75*number-appearances==0]==0),'Absent movement without absence')
        need(row['round_parameter_sha256']==rawsha(states[i]) and row['validation_probability_sha256']==rawsha(probs[i]) and row['record_order_sha256']==rawsha(orders[i]),'Raw round-array digest differs')
        need(row['validation_native_loss_sha256']==rawsha(native[i:i+1]),'Raw native loss digest differs')
        need(row['validation_logit_sha256']==(None if logits is None else rawsha(logits[i])),'Raw native logit digest differs')
        native_check(val['y'],probs[i],None if logits is None else logits[i],native[i],row['validation_native'])
        independent_loss=ref.bce(val['y'],independent[i]) if independent_logits is None else ref.stable_logit_bce(val['y'],independent_logits[i])
        ne=abs(native[i]-independent_loss);max_native=max(max_native,ne);need(ne<=NTOL,'Independent native loss differs')
        canonical=ref.metrics(val['y'],probs[i]);metric_check(canonical,row['validation'])
        error=abs(ref.bce(val['y'],independent[i])-canonical['bce']);max_bce=max(max_bce,error);need(error<=BTOL,'Independent aggregate clipped BCE differs')
        selected=canonical['bce']<best;need(row['selected']==selected,'Earliest minimum selection rule differs')
        if selected:best=canonical['bce'];chosen=number;chosen_generations.append(number)
        need(row['bank_record_visits_cumulative']==sampling_audit['visits_by_round'][i].tolist(),'Cumulative bank exposure differs')
        refresh_work={} if number<=10 else expected_work(method,4800*(number-10),cached=frozen)
        need(row['work_cumulative']=={'training':expected_work(method,4800*number,True,cached=frozen),'validation':expected_work(method,1600*number,cached=frozen),
            'full_training_diagnostics':expected_work(method,4800*number,cached=frozen),'priority_refresh':refresh_work,
            'fixed_feature_preparation':cache_work},'Cumulative operation accounting differs')
        for key in ('training_loss','training_common_clipped_bce','mean_batch_gradient_norm','maximum_batch_gradient_norm','elapsed_seconds'):
            need(np.isfinite(row[key]) and row[key]>=0,'Invalid training diagnostic '+key)
        need(row['maximum_batch_gradient_norm']+1e-14>=row['mean_batch_gradient_norm'],'Gradient extrema inconsistent')
        need(row['elapsed_seconds']>=last_elapsed,'Nonmonotone elapsed time');last_elapsed=row['elapsed_seconds']
        need(isinstance(row['training_clipped_probabilities'],int) and 0<=row['training_clipped_probabilities']<=4800,'Clip counter invalid');clip_total+=row['training_clipped_probabilities']
        need(isinstance(row['training_clipped_wrong_probabilities'],int) and 0<=row['training_clipped_wrong_probabilities']<=row['training_clipped_probabilities'],'Wrong clip counter invalid');wrong_total+=row['training_clipped_wrong_probabilities']
        need(row['legacy_outside_clip_zero_derivative_visits']==(row['training_clipped_probabilities'] if legacy else 0),'Legacy derivative-zero visits differ')
        ext=row['training_forward_extrema'];need(0<=ext['minimum_raw_probability']<=ext['maximum_raw_probability']<=1,'Training probability extrema invalid')
        if legacy:need(ext['minimum_native_logit'] is None and ext['maximum_native_logit'] is None,'Legacy native extrema must be null')
        else:need(np.isfinite([ext['minimum_native_logit'],ext['maximum_native_logit']]).all() and ext['minimum_native_logit']<=ext['maximum_native_logit'],'Training logit extrema invalid')
        for group in ('core','head'):
            low=row['mean_batch_gradient_group_norms'][group];high=row['maximum_batch_gradient_group_norms'][group]
            need(np.isfinite([low,high]).all() and 0<=low<=high+1e-14,'Group gradient diagnostic invalid')
            if (group=='core' and (frozen or not method.startswith('q'))) or (group=='head' and legacy):need(low==high==0,'Empty parameter-group norm not zero')
        threshold=threshold_check(val['y'],probs[i],independent[i],val['ids']);threshold['round']=number;all_threshold.append(threshold)
    need(chosen==r['selected_round'],'Selected round differs');need(r['training_clipped_probabilities']==clip_total,'Cumulative clipping counter differs')
    need(r['training_clipped_wrong_probabilities']==wrong_total and r['legacy_outside_clip_zero_derivative_visits']==(clip_total if legacy else 0),'Endpoint wrongclip/legacy counters differ')
    need(r['bank_training_record_visits']==sampling_audit['visits_by_round'][-1].tolist(),'Endpoint exposure differs')
    for final_key,row_key in (('bank_minibatch_appearances','bank_minibatch_appearances_cumulative'),
                             ('bank_absent_updates','bank_absent_updates_cumulative'),
                             ('bank_absent_parameter_movement_l2_sum','bank_absent_parameter_movement_l2_sum_cumulative'),
                             ('bank_gradient_l2_sum','bank_gradient_l2_sum_cumulative')):
        need(r[final_key]==ledger[-1][row_key],'Final bank diagnostics differ')
    selected_banks=states[chosen-1].reshape(banks,-1)
    same(np.asarray(r['selected_coefficients_or_heads_by_bank']),selected_banks[:,8:] if method.startswith('q') else selected_banks,'Selected coefficients differ')
    near(r['selected_parameter_l2_norm_by_bank'],np.linalg.norm(selected_banks,axis=1),CTOL,'Selected bank parameter norm differs')
    need({p.name for p in folder.glob('selected_round_*.npz')}=={f'selected_round_{n:04d}.npz' for n in chosen_generations},'Selected generations differ')
    for number in chosen_generations:checkpoint(folder/f'selected_round_{number:04d}.npz',states[number-1],number,pc,core,probs[number-1],None if logits is None else logits[number-1],native[number-1])
    checkpoint(folder/'last_checkpoint.npz',states[-1],rounds,pc,core,probs[-1],None if logits is None else logits[-1],native[-1])
    selected=checkpoint(folder/'selected_checkpoint.npz',states[chosen-1],chosen,pc,core,probs[chosen-1],None if logits is None else logits[chosen-1],native[chosen-1])
    need(sha(folder/'selected_checkpoint.npz')==sha(folder/f'selected_round_{chosen:04d}.npz'),'Selected checkpoint alias differs')
    metric_check(ref.metrics(val['y'],probs[chosen-1]),r['selected_validation'])
    native_check(val['y'],probs[chosen-1],None if logits is None else logits[chosen-1],native[chosen-1],r['selected_validation_native'])
    for kind in ('hash','kmeans'):
        need(r['validation_route_counts'][kind]==np.bincount(val[kind+'_route'],minlength=5).tolist(),'Validation occupancy differs')
        for bank in range(5):
            ix=val[kind+'_route']==bank
            subgroup=r['validation_by_route'][kind][str(bank)]
            need(subgroup['n']==int(ix.sum()) and subgroup['positive_count']==int(val['y'][ix].sum()),'Route subgroup membership differs')
            if ix.any():metric_check(ref.metrics(val['y'][ix],probs[chosen-1,ix]),subgroup['metrics'])
            else:need(subgroup['metrics'] is None,'Empty route metrics must be null')
    margin_count=read(Q/'data'/f'{population}_router.json')['margin_bins']['bins']
    need(set(r['validation_by_margin_bin'])=={str(k) for k in range(margin_count)},'Margin bin inventory differs')
    for k in range(margin_count):
        ix=val['margin_bin']==k;subgroup=r['validation_by_margin_bin'][str(k)]
        need(subgroup['n']==int(ix.sum()),'Margin membership differs')
        if ix.any():metric_check(ref.metrics(val['y'][ix],probs[chosen-1,ix]),subgroup['metrics'])
        else:need(subgroup['metrics'] is None,'Empty margin metrics must be null')
    with (folder/'validation_predictions.csv').open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    need(len(rows)==1600,'Selected validation CSV count differs')
    for j,row in enumerate(rows):
        need(int(row['record_id'])==val['ids'][j] and int(row['label'])==val['y'][j] and int(row['hash_route'])==val['hash_route'][j] and int(row['kmeans_route'])==val['kmeans_route'][j],'Prediction CSV identity differs')
        need(float(row['probability'])==probs[chosen-1,j] and int(row['prediction'])==int(probs[chosen-1,j]>=.5),'Prediction CSV canonical outcome differs')
        need(row['native_logit']=='' if legacy else float(row['native_logit'])==logits[chosen-1,j],'Prediction CSV native logit differs')
    gm=load(folder/'round_gradient_means.npz');need(gm['gradients'].shape==(rounds,pc) and np.isfinite(gm['gradients']).all(),'Gradient diagnostic shape differs')
    g=load(folder/'selected_training_gradient.npz')['gradient'];need(g.shape==(pc,) and np.isfinite(g).all(),'Selected gradient invalid');near(np.linalg.norm(g),r['selected_training_gradient_norm'],CTOL,'Selected gradient norm differs')
    mask=np.zeros(pc,bool)
    if method.startswith('q') and not frozen:
        for bank in range(banks):mask[bank*(pc//banks):bank*(pc//banks)+8]=True
    for group,m in (('core',mask),('head',~mask)):near(np.linalg.norm(g[m]),r['selected_training_gradient_group_norms'][group],CTOL,'Selected group gradient norm differs')
    expected={'training':expected_work(method,rounds*4800,True,cached=frozen),'validation':expected_work(method,rounds*1600,cached=frozen),
              'full_training_diagnostics':expected_work(method,rounds*4800,cached=frozen),'priority_refresh':expected_work(method,(rounds-10)*4800,cached=frozen),
              'selected_validation_replay':expected_work(method,1600,cached=frozen),'selected_training_gradient_diagnostic':expected_work(method,4800,True,cached=frozen),'fixed_feature_preparation':cache_work}
    need(r['work']==expected,'Endpoint operation accounting differs')
    need(r['inference']=={'performed':False,'scope':'Timing deferred to isolated post-training deployment sessions.'},'Training must not perform inference timing')
    train_prediction,train_logits=ref.predict_with_logits(method,states[chosen-1],train['x'],None if banks==1 else train[routing+'_route'])
    metric_check(ref.metrics(train['y'],train_prediction),r['selected_training'])
    near(ref.stable_logit_bce(train['y'],train_logits),r['selected_training_native_bce'],NTOL,'Selected training native loss differs')
    selected_g=ref.weighted_gradient(method,states[chosen-1],train['x'],train['y'],None if banks==1 else train[routing+'_route'])
    need(np.all(abs(g-selected_g)<=1e-10+1e-8*abs(selected_g)),'Independent selected full-training gradient differs')
    sd=r['sampling_diagnostics'];ss=sampling_audit['summary']
    for key,expected_value in [('refresh_count',rounds-10),('replacement_draws',rounds*4800),
        ('unique_records_exposed',ss['unique_records_exposed']),('class_draws',ss['class_draws']),('trace_bytes',ss['trace_bytes'])]:
        need(sd[key]==expected_value,'Endpoint sampling summary differs '+key)
    need(sd['sampling_diagnostics_stream_consumed'] is False,'Unused diagnostic stream was consumed')
    for key in ('refresh_wall_seconds','refresh_cpu_seconds','sampling_wall_seconds','sampling_cpu_seconds',
        'full_training_diagnostic_wall_seconds','full_training_diagnostic_cpu_seconds'):
        need(np.isfinite(sd[key]) and sd[key]>=0,'Invalid sampling cost '+key)
    for key in ('training_process_cpu_seconds','invocation_process_cpu_seconds_through_result','invocation_wall_seconds_through_result'):
        need(np.isfinite(r[key]) and r[key]>=0,'Invalid process resource diagnostic')
    need(r['training_process_cpu_seconds']<=r['invocation_process_cpu_seconds_through_result'],'Process CPU scopes inconsistent')
    cost=seal['datasets'][population];prep=r['preparation'];need(prep==c['preparation'],'Preparation metadata differs')
    near(prep['generation_seconds_charged'],cost['generation_seconds'],CTOL,'Generation charge differs')
    near(prep['joint_router_fit_seconds_charged'],cost['router_fit_seconds'] if banks==5 else 0.,CTOL,'Router fit charge differs')
    cache=sum(cost['route_application_seconds_by_split'][part][routing] for part in ('train','validation')) if banks==5 else 0.
    near(prep['train_validation_cache_seconds_charged'],cache,CTOL,'Route cache charge differs')
    charge=sum(prep[k] for k in ('generation_seconds_charged','joint_router_fit_seconds_charged','train_validation_cache_seconds_charged'))
    near(r['charged_training_seconds'],r['training_seconds']+r['frozen_cache']['seconds']+charge,CTOL,'Charged training time differs')
    need(0<=last_elapsed<=r['training_seconds']<=r['endpoint_total_seconds'],'Timing boundary differs')
    _,after=check_commit(folder);need(after==commit_sha,'Endpoint changed during independent audit')
    disagreement=[dict(item,round=entry['round']) for entry in all_threshold for item in entry['disagreement_records']]
    return {'job_id':job['run_id'],'arm':job['arm'],'stage':stage,'population':population,'method':method,'seed':seed,'rounds_verified':rounds,'validation_predictions_replayed':rounds*1600,
       'endpoint_commit_sha256':commit_sha,'selected_checkpoint_sha256':sha(folder/'selected_checkpoint.npz'),
       'selected_round':chosen,'selected_validation':r['selected_validation'],
       'maximum_probability_error':float(np.max(abs(probs-independent))),'maximum_independent_aggregate_bce_error':max_bce,
       'maximum_native_logit_error':max_logit,'maximum_independent_native_loss_error':max_native,
       'maximum_scalar_spotcheck_error':scalar_error,'scalar_spotcheck_records':len(spots)*len(spot_rounds),
       'all_round_canonical_band_records':sum(a['canonical_band_records'] for a in all_threshold),
       'all_round_reference_band_records':sum(a['reference_band_records'] for a in all_threshold),
       'all_round_class_disagreements':len(disagreement),'outside_band_disagreements':0,
       'disagreement_records':disagreement,'selected_threshold_diagnostic':all_threshold[chosen-1],
       'round_numeric_diagnostics':[{k:a[k] for k in ('round','canonical_band_records','reference_band_records','class_disagreements')} for a in all_threshold],
       'sample_order_sha256':sha(folder/'record_orders.npy'),'initial_state_sha256':sha(folder/'initial_state.npz'),
       'initial_parameters_array_sha256':rawsha(initial['parameters']),'first_ten_round_parameters_sha256':rawsha(states[:10]),
       'sampling_and_optimizer_replay':sampling_audit['summary'],
       'operations_verified':True,'all_saved_rounds_independently_replayed':True}

def binding(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size}


def verify_binding(item):
    path=Path(item['path']).resolve()
    need(path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'Artifact binding differs: '+str(path))
    return path


def ledger_snapshot():
    """Open SQLite in read-only mode; never import or mutate scheduler state."""
    path=ROOT/'execution/state/ledger.sqlite3'
    need(path.is_file(),'Official execution ledger absent')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        current=[dict(row) for row in db.execute(
            'SELECT a.*,j.phase,j.recipe_sha,j.manifest_sha FROM attempts a JOIN jobs j '
            'ON j.current_attempt=a.attempt_id ORDER BY j.job_id')]
        all_attempts=[dict(row) for row in db.execute('SELECT * FROM attempts ORDER BY attempt_id')]
        journal=[dict(row) for row in db.execute("SELECT * FROM journal WHERE event='stage_supervision_finished' ORDER BY sequence")]
    return {'current':current,'all_attempts':all_attempts,'closed_events':journal}


def audit_stage(stage):
    began=time.perf_counter()
    need(stage in STAGE_COUNTS,'Unknown registered stage')
    numeric_path=HERE/'AUDIT_NUMERICAL_PROTOCOL.json';numeric=read(numeric_path)
    need(numeric['status']=='registered_before_official_endpoint_audits','Numerical protocol not registered')
    need(numeric['probability_abs_tolerance']==PTOL and numeric['aggregate_bce_abs_tolerance']==BTOL
         and numeric['saved_metric_abs_tolerance']==CTOL and numeric['native_logit_abs_tolerance']==ZTOL
         and numeric['native_loss_abs_tolerance']==NTOL and numeric['threshold_band']==BAND,'Numerical tolerances differ')
    need(numeric['gradient_absolute_tolerance']==GRADIENT_ATOL and numeric['gradient_relative_tolerance']==GRADIENT_RTOL
         and numeric['adam_state_absolute_tolerance']==STATE_ATOL and numeric['priority_probability_absolute_tolerance']==PRIORITY_ATOL
         and numeric['gradient_probe_rounds']==list(SPOT_ROUNDS) and numeric['gradient_probe_minibatch_indices_zero_based']==list(SPOT_BATCHES),'Sampler/Adam audit registration differs')
    matrix_path=ROOT/'governance/RUN_MATRIX.json';matrix=read(matrix_path)
    jobs=[row for row in matrix['runs'] if row['stage']==stage]
    need(len(jobs)==STAGE_COUNTS[stage] and len({j['run_id'] for j in jobs})==len(jobs),'Registered matrix stage cardinality differs')
    snapshot=ledger_snapshot()
    terminal={'succeeded','failed','orphaned','timed_out','invalid_commit','interrupted'}
    need(all(row['status'] in terminal for row in snapshot['all_attempts']),'A numerical training attempt remains nonterminal; close before audit')
    rows=[row for row in snapshot['current'] if row['phase']==stage]
    need({r['job_id'] for r in rows}=={j['run_id'] for j in jobs} and len(rows)==len(jobs),'Exact ledger/matrix job inventory differs')
    need(all(row['status']=='succeeded' for row in rows),'Current stage endpoints not all successful')
    manifests={row['manifest_sha'] for row in rows};need(len(manifests)==1,'Stage has mixed execution manifests')
    closed=[]
    for path in sorted((ROOT/'execution/stage_reports').glob(stage+'_*.json')):
        report=read(path)
        if report.get('status')=='completed' and report.get('manifest_sha256') in manifests:
            need(report.get('stage')==stage,'Stage close report differs')
            closed.append(binding(path))
    need(closed,'Successful closed supervision receipt required')
    events=[r for r in snapshot['closed_events'] if (lambda d:d.get('stage')==stage and d.get('succeeded') is True and d.get('total')==len(jobs))(json.loads(r['details_json']))]
    need(events,'No corresponding closed-stage journal event')
    seal_path=Q/'data/DATA_SEAL.json';seal=read(seal_path)
    stable_inputs=[binding(matrix_path),binding(ROOT/'governance/STUDY_PLAN.json'),binding(ROOT/'governance/ANALYSIS_PROTOCOL.json'),binding(seal_path),binding(numeric_path)]
    audit_source_paths=(Path(__file__),HERE/'reference_v08.py',HERE/'sampler_reference.py',HERE/'audit_sampling_trace.py')
    audit_sources={p.name:sha(p) for p in audit_source_paths}
    results=[];by_id={row['job_id']:row for row in rows}
    for job in jobs:
        row=by_id[job['run_id']];metadata=Path(row['metadata_dir']).resolve();folder=Path(row['endpoint']).resolve()
        need(metadata.is_relative_to((ROOT/'execution/attempts').resolve()) and folder==metadata/'endpoint','Endpoint outside canonical execution tree')
        request_path=metadata/'REQUEST.json';request=read(request_path)
        need(request['attempt_id']==row['attempt_id'] and request['job']==job,'Attempt recipe differs from exact registered row')
        need(request['metadata_dir']==str(metadata) and Path(request['endpoint']).resolve()==folder,'Attempt location differs')
        recipe=hashlib.sha256(json.dumps(job,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
        need(recipe==request['recipe_sha256']==row['recipe_sha'],'Canonical job recipe digest differs')
        manifest_path=Path(request['manifest_path']);need(sha(manifest_path)==request['manifest_sha256']==row['manifest_sha'],'Manifest identity differs')
        manifest=read(manifest_path)
        need(manifest['mode']=='OFFICIAL_STUDY' and manifest['stage']==stage and manifest['jobs']==jobs,'Manifest scientific inventory differs')
        authorization=verify_binding(manifest['authorization'])
        verify_binding(manifest['matrix']);verify_binding(manifest['protocol'])
        release_path=Path(request['release_path']);need(sha(release_path)==request['release_sha256'],'Execution root release changed')
        release=read(release_path);need(release['review_status']=='approved_by_root' and release['stage']==stage and release['manifest_sha256']==row['manifest_sha'],'Execution not authorized')
        endpoint_commit=folder/'endpoint_commit.json'
        need(sha(endpoint_commit)==row['commit_sha'],'Ledger committed endpoint hash differs')
        result=audit_endpoint(folder,job,seal,authorization)
        result['commit']=binding(endpoint_commit)
        result['attempt_id']=row['attempt_id'];result['request']=binding(request_path)
        result['authorization']=binding(authorization)
        results.append(result)
        print(json.dumps({'audited':len(results),'required':len(jobs),'job_id':job['run_id'],'status':'PASS'}),flush=True)
    need(ledger_snapshot()==snapshot,'Execution ledger changed during independent audit')
    for item in stable_inputs:verify_binding(item)
    need(audit_sources=={p.name:sha(p) for p in audit_source_paths},'Audit sources changed')
    paired={};warmup={}
    for result in results:
        key=(result['population'],result['seed']);u=result['sampling_and_optimizer_replay']['sampler_uniform_sha256']
        need(key not in paired or paired[key]==u,'Common random sampling uniforms differ within population/seed')
        paired[key]=u
        base=result['arm'].rsplit('_',1)[0];mode=result['arm'].rsplit('_',1)[1]
        wkey=(result['population'],result['seed'],base)
        warmup.setdefault(wkey,{})[mode]=(result['initial_parameters_array_sha256'],result['first_ten_round_parameters_sha256'])
    need(all(set(values)=={'U','P'} and values['U']==values['P'] for values in warmup.values()),'Matched U/P initialization or first ten uniform trajectories differ')
    return {'schema':'qpath-v08-independent-stage-audit-1','status':'PASS','stage':stage,
            'created_utc':datetime.now(timezone.utc).isoformat(),'verified_endpoints':len(results),
            'endpoints':results,'input_bindings':stable_inputs,'audit_source_sha256':audit_sources,
            'stage_close_observations':closed,'stage_close_journal_sequences':[e['sequence'] for e in events],
            'all_round_validation_predictions_replayed':sum(r['validation_predictions_replayed'] for r in results),
            'test_model_outcomes_accessed':False,'full_optimizer_training_repeated':False,
            'optimizer_scope':'Every retained raw gradient drives independent full packed Adam replay including all saved moments and round states. First/last batches in predeclared rounds1,10,11,12,100,200 have independently recomputed gradients. No claim of independent recomputation of every gradient.',
            'all_adam_updates_replayed':sum(r['sampling_and_optimizer_replay']['all_adam_updates_replayed'] for r in results),
            'paired_uniform_groups_verified':len(paired),
            'matched_up_initialization_and_warmup_pairs_verified':len(warmup),
            'seconds':time.perf_counter()-began}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=tuple(STAGE_COUNTS),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    need(not args.output.exists(),'Audit receipt already exists; preserve it')
    try:
        receipt=audit_stage(args.stage)
    except BaseException as error:
        receipt={'status':'FAIL','stage':args.stage,'created_utc':datetime.now(timezone.utc).isoformat(),
                 'error':repr(error),'traceback':traceback.format_exc(),'test_model_outcomes_accessed':False}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as handle:json.dump(receipt,handle,indent=2,allow_nan=False)
        raise
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as handle:json.dump(receipt,handle,indent=2,allow_nan=False)
    print(json.dumps({'status':receipt['status'],'stage':receipt['stage'],'verified_endpoints':receipt['verified_endpoints'],'receipt':str(args.output)}))


if __name__=='__main__':
    main()
