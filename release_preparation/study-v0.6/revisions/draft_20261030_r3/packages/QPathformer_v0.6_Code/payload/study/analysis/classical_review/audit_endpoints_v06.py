"""Independent all-round validation audit. No production models or test loader.

All checks use explicit exceptions, including under Python -O. Official use
requires closed full-stage execution and the separately authored endpoint lock.
This audits every saved round, not a rerun of all 15000 optimizer updates.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, csv, hashlib, json, sys, time, traceback
import numpy as np
import reference_v06 as ref

ROOT=Path(__file__).resolve().parents[2];Q=ROOT/'quantum';HERE=Path(__file__).resolve().parent
SEEDS={'A':(1101,1102),'B':(1201,1202,1203,1204,1205)}
FAMILIES=('checkerboard','spiral','annulus','disks')
POPS={stage:tuple(prefix+'_'+family for family in FAMILIES) for stage,prefix in (('A','development'),('B','confirmation'))}
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
        original=Path(read(ROOT/'governance/STUDY_PLAN.json')['working_root'])
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
    allowed=('x','y','ids','source_draw_ids','hash_route','kmeans_route')
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

def expected_initial(method,seed):
    family,routing=method.split('_');banks=1 if routing=='global' else 5
    if family.startswith('q'):
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1])))
        master=rng.uniform(-.1,.1,(5,4,2,2));core=master[:banks,:2].copy()
        if family=='q2':return core.reshape(-1),master,np.empty(0)
        head=np.zeros((banks,2 if family=='qscalar' else 6));head[:,0]=2.
        if family=='qfrozen':return head.ravel(),master,core
        return np.column_stack((core.reshape(banks,8),head)).ravel(),master,np.empty(0)
    if family=='trig':
        master=np.zeros((banks,25));return master.ravel(),master,np.empty(0)
    h=32 if routing=='global' else int(family[3:].replace('relu','').replace('tanh',''))
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,4,h])))
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
       'trig_feature_values':25*n if family=='trig' else 0,'mlp_hidden_evaluations':n*h,
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

def audit_endpoint(folder,stage,population,seed,method,seal,freeze=None,engineering=False):
    need(method in ref.METHODS,'Unregistered model method')
    commit,commit_sha=check_commit(folder);c=read(folder/'config.json');r=read(folder/'result.json');status=read(folder/'status.json')
    need(c['study_id']==r['study_id']=='QPATH-GENERALIZATION-v0.6','Study identity differs')
    for obj in (commit,c,r,status):
        for k,v in [('population',population),('seed',seed),('method',method)]:need(obj[k]==v,'Endpoint identity mismatch')
    need(c['stage']==r['stage']==stage and c['engineering']==r['engineering']==engineering,'Stage/engineering mismatch')
    need(r['status']==status['status']=='completed' and c['test_accessed'] is False and r['test_accessed'] is False,'Incomplete or test-accessed endpoint')
    rounds=int(c['rounds']);need(rounds>0 and (engineering or rounds==200),'Full horizon not completed')
    need(c['train_records']==4800 and c['validation_records']==1600 and c['batch_size']==64,'Record/batch budget differs')
    need(r['completed_rounds']==status['round']==rounds and r['optimizer_global_updates']==75*rounds,'Endpoint update count differs')
    need(c['data_seal_sha256']==r['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json'),'Data seal binding differs')
    need(c['source_hashes']==commit['source_hashes'],'Commit/source mismatch')
    for name,value in c['source_hashes'].items():need(sha(remap(name))==value,'Source changed: '+name)
    if not engineering:
        need(c['source_hashes']==freeze['source_hashes'],'Source not frozen')
        need(c['settings']==freeze['settings'],'Settings differ from freeze')
        need(c['stage_freeze_sha256']==r['stage_freeze_sha256']==sha(Q/f'STAGE_{stage}_FREEZE.json'),'Freeze binding differs')
    data=[]
    for split in ('train','validation'):
        path=Q/'data'/f'{population}_{split}.npz';need(sha(path)==seal['files'][path.name]['sha256'],'Population payload changed')
        data.append(load_primary_population(path))
    train,val=data;need(sha(Q/'data'/f'{population}_router.json')==c['router_policy_sha256']==seal['routers'][population]['sha256'],'Policy identity differs')
    identity=load(folder/'population_identity.npz');need(set(identity)=={'train_ids','validation_ids'},'Population identity keys differ')
    same(identity['train_ids'],train['ids'],'Training identities differ');same(identity['validation_ids'],val['ids'],'Validation identities differ')
    initial=load(folder/'initial_state.npz');theta,master,core=expected_initial(method,seed)
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
    need(len(ledger)==rounds,'Ledger horizon differs');sampler=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
    banks=1 if routing=='global' else 5;bank_counts=np.array([4800]) if banks==1 else np.bincount(train[routing+'_route'],minlength=5)
    need(r['parameter_count']==pc and r['bank_count']==banks and r['parameters_per_bank']==pc//banks,'Architecture counts differ')
    need(c['parameter_count']==pc and c['fixed_core_parameter_count']==r['fixed_core_parameter_count']==core.size and r['stored_model_parameter_count']==pc+core.size,'Trained/fixed/stored parameter counts differ')
    need(c['has_native_logits']==r['has_native_logits']==(not legacy),'Native model flag differs')
    need(r['train_bank_counts']==bank_counts.tolist(),'Training bank allocation differs')
    best=float('inf');chosen=None;chosen_generations=[];last_elapsed=0.;all_threshold=[];max_bce=0.;clip_total=0;wrong_total=0;max_native=0.
    for i,row in enumerate(ledger):
        number=i+1;need(row['round']==number and row['optimizer_updates']==75*number,'Ledger counters differ')
        same(orders[i],sampler.permutation(4800),'Paired sample order differs')
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
        need(row['bank_record_visits_cumulative']==(bank_counts*number).tolist(),'Cumulative bank exposure differs')
        need(row['work_cumulative']=={'training':expected_work(method,4800*number,True,cached=frozen),'validation':expected_work(method,1600*number,cached=frozen),'fixed_feature_preparation':cache_work},'Cumulative operation accounting differs')
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
    need(r['bank_training_record_visits']==(bank_counts*rounds).tolist(),'Endpoint exposure differs')
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
            if ix.any():metric_check(ref.metrics(val['y'][ix],probs[chosen-1,ix]),r['validation_by_route'][kind][str(bank)])
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
              'selected_validation_replay':expected_work(method,1600,cached=frozen),'selected_training_gradient_diagnostic':expected_work(method,4800,True,cached=frozen),'fixed_feature_preparation':cache_work}
    need(r['work']==expected,'Endpoint operation accounting differs')
    inf=r['inference'];need(inf['records']==1024 and inf['warmups']==1 and inf['timed_repeats']==3,'Inference fixture differs')
    need(inf['record_ids']==np.sort(val['ids'])[:1024].tolist(),'Inference fixture membership differs')
    need(inf['work_four_uncached_forwards']==expected_work(method,4096) and inf['work_fifth_cached_comparison']==expected_work(method,1024),'Inference operation accounting differs')
    need(inf['maximum_cached_difference']<=PTOL,'Inference cached comparison differs')
    need(len(inf['total_repeat_seconds'])==len(inf['route_repeat_seconds'])==3,'Inference timing repetitions differ')
    for total,rt in zip(inf['total_repeat_seconds'],inf['route_repeat_seconds']):need(np.isfinite(total) and 0<=rt<=total,'Invalid inference timing')
    if routing=='global':need(inf['route_repeat_seconds']==[0.,0.,0.],'Global route timing must be zero')
    near(np.mean(inf['total_repeat_seconds'])/1024,inf['mean_seconds_per_record'],CTOL,'Inference mean differs')
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
    return {'population':population,'method':method,'seed':seed,'rounds_verified':rounds,'validation_predictions_replayed':rounds*1600,
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
       'paired_sample_order_sha256':sha(folder/'record_orders.npy'),'initial_state_sha256':sha(folder/'initial_state.npz'),
       'operations_verified':True,'all_saved_rounds_independently_replayed':True}

def audit_stage(stage=None,engineering_root=None,lock_path=None):
    started=time.perf_counter();sources={p.name:sha(p) for p in (Path(__file__),HERE/'reference_v06.py')}
    protocol_sha=sha(ROOT/'governance/ANALYSIS_PROTOCOL.json');protocol=read(ROOT/'governance/ANALYSIS_PROTOCOL.json');numeric=protocol['numerical']
    need(numeric['probability_abs_tolerance']==PTOL and numeric['independent_aggregate_bce_abs_tolerance']==BTOL and numeric['canonical_saved_probability_metric_abs_tolerance']==CTOL and numeric['band']==BAND,'Registered numerical thresholds differ')
    need(numeric['independent_native_logit_abs_tolerance']==ZTOL and numeric['independent_native_aggregate_loss_abs_tolerance']==NTOL,'Registered native numerical thresholds differ')
    seal_path=Q/'data/DATA_SEAL.json';seal_sha=sha(seal_path);seal=read(seal_path);freeze=None;lock=None;lock_sha=None
    engineering=engineering_root is not None
    if engineering:
        base=Path(engineering_root);populations=tuple('engineering_'+f for f in FAMILIES);seeds=(10901,);stage='A'
        need(lock_path is not None,'Engineering author lock required')
        lock_sha=sha(lock_path);lock=read(lock_path)
        need(lock['status']=='PASS' and lock['stage']=='A' and lock['engineering'] is True and lock['endpoint_count']==24,'Engineering author audit scope differs')
        need(lock['data_seal_sha256']==seal_sha and lock['analysis_protocol_sha256']==protocol_sha,'Engineering author provenance differs')
        need(len(lock['endpoints'])==24,'Engineering author row count differs')
        for name,h in lock['source_hashes'].items():need(sha(remap(name))==h,'Engineering source changed')
        for name,h in lock['audit_source_hashes'].items():need(sha(remap(name))==h,'Engineering author source changed')
        locked={(a['population'],a['seed'],a['method']):a for a in lock['endpoints']}
        need(set(locked)=={(p,s,m) for p in populations for s in seeds for m in ref.METHODS},'Engineering author identities differ')
    else:
        need(stage in SEEDS and lock_path is not None,'Official stage/author lock required')
        base=Q/f'stage_{stage}';populations=POPS[stage];seeds=SEEDS[stage];freeze=read(Q/f'STAGE_{stage}_FREEZE.json')
        need(freeze['review_status']=='approved_by_root','Root approval required')
        need(freeze['methods']==list(ref.METHODS) and freeze['populations']==list(populations) and freeze['training_seeds']==list(seeds),'Frozen study inventory differs')
        need(freeze['data_seal_sha256']==seal_sha,'Frozen data seal differs')
        for name,h in freeze['source_hashes'].items():need(sha(remap(name))==h,'Frozen source changed')
        status=read(base/'stage_status.json');need(status['status']=='completed' and status['stage']==stage,'Stage process not completed')
        need(status['expected_endpoints']==status['committed_endpoints']==len(populations)*len(seeds)*len(ref.METHODS),'Full stage endpoints required')
        need(sorted((x['seed'],x['exit_code']) for x in status['exits'])==[(s,0) for s in seeds],'Stage workers did not all finish successfully')
        lock_sha=sha(lock_path);lock=read(lock_path)
        need(lock['status']=='PASS' and lock['stage']==stage,'Author endpoint lock failed or wrong stage')
        need(lock['engineering'] is False and lock['endpoint_count']==len(populations)*len(seeds)*len(ref.METHODS),'Author lock endpoint scope differs')
        need(lock['source_hashes']==freeze['source_hashes'] and lock['data_seal_sha256']==seal_sha,'Author lock source/data identities differ')
        need(lock['analysis_protocol_sha256']==sha(ROOT/'governance/ANALYSIS_PROTOCOL.json') and lock['stage_freeze_sha256']==sha(Q/f'STAGE_{stage}_FREEZE.json'),'Author lock protocol/freeze identities differ')
        for name,value in lock['audit_source_hashes'].items():need(sha(remap(name))==value,'Author audit source changed')
        need(len(lock['endpoints'])==len(populations)*len(seeds)*len(ref.METHODS),'Author endpoint row count differs')
        locked={(a['population'],a['seed'],a['method']):a for a in lock['endpoints']}
        need(set(locked)=={(p,s,m) for p in populations for s in seeds for m in ref.METHODS},'Author endpoint identities differ')
        for seed in seeds:
            need(read(base/f'seed_{seed}_failures.json')==[],'Recorded stage failures require review')
            ordering=read(base/f'seed_{seed}_execution_order.json');si=seeds.index(seed)
            for pi,pop in enumerate(populations):
                shift=(pi*len(seeds)+si)%len(ref.METHODS);expected=list(ref.METHODS[shift:]+ref.METHODS[:shift])
                if (pi+si)%2:expected.reverse()
                need(ordering['methods_by_population'][pop]==expected,'Execution counterbalancing differs')
    expected={base/pop/f'seed_{seed}'/method for pop in populations for seed in seeds for method in ref.METHODS}
    need({p.parent for p in base.glob('*/seed_*/*/endpoint_commit.json')}==expected,'Exact endpoint inventory differs')
    results=[]
    for pop in populations:
        for seed in seeds:
            for method in ref.METHODS:
                folder=base/pop/f'seed_{seed}'/method
                item=audit_endpoint(folder,stage,pop,seed,method,seal,freeze,engineering);results.append(item)
                if lock is not None:
                    row=locked[(pop,seed,method)]
                    need(row['endpoint_commit_sha256']==item['endpoint_commit_sha256'],'Author/independent commit identity differs')
                    nrounds=3 if engineering else 200
                    need(row['rounds']==nrounds and row['optimizer_updates']==75*nrounds and row['selected_round']==item['selected_round'],'Author horizon/selection differs')
                    need(row['validation_rounds_replayed']==nrounds and row['validation_record_predictions_replayed']==1600*nrounds,'Author replay scope differs')
                    metric_check(row['selected_validation'],item['selected_validation'])
                    need(row['files']==read(folder/'endpoint_commit.json')['files'],'Author/committed file identities differ')
                print(json.dumps({'audited':len(results),'population':pop,'seed':seed,'method':method,'rounds':item['rounds_verified']}),flush=True)
    for pop in populations:
        for seed in seeds:
            cells=[r for r in results if r['population']==pop and r['seed']==seed]
            need(len({r['paired_sample_order_sha256'] for r in cells})==1,'Across-arm sample orders differ')
    need(sha(seal_path)==seal_sha and sources=={p.name:sha(p) for p in (Path(__file__),HERE/'reference_v06.py')},'Audit/source seal changed')
    need(sha(ROOT/'governance/ANALYSIS_PROTOCOL.json')==protocol_sha,'Numerical protocol changed during audit')
    if not engineering:
        for name,h in freeze['source_hashes'].items():need(sha(remap(name))==h,'Frozen source changed during audit')
        need(sha(Q/f'STAGE_{stage}_FREEZE.json')==lock['stage_freeze_sha256'],'Stage freeze changed during audit')
    if lock_path is not None:need(sha(lock_path)==lock_sha,'Author lock changed during audit')
    return {'status':'PASS','study_id':'QPATH-GENERALIZATION-v0.6','stage':stage,'engineering':engineering,'created_utc':datetime.now(timezone.utc).isoformat(),
        'endpoint_count':len(results),'round_count':sum(r['rounds_verified'] for r in results),
        'validation_rounds_replayed':sum(r['rounds_verified'] for r in results),
        'validation_predictions_replayed':sum(r['validation_predictions_replayed'] for r in results),
        'endpoint_lock_sha256':lock_sha,'data_seal_sha256':seal_sha,'auditor_sha256':sources[Path(__file__).name],
        'independent_source_sha256':sources,'analysis_protocol_sha256':sha(ROOT/'governance/ANALYSIS_PROTOCOL.json'),
        'elapsed_seconds':time.perf_counter()-started,'endpoints':results,'model_test_outcomes_accessed':False,
        'scope':'Every saved validation parameter state and all validation probabilities independently replayed; selected/final states, all raw round digests, RNG order, operation/exposure/Adam counters and payload identities checked. Does not rerun all optimizer updates or independently recreate intermediate per-batch losses/gradients/moments. Timings are checked for arithmetic/consistency, not independently remeasured. No production model/trainer imported; no test payload/model outcomes read.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=SEEDS);p.add_argument('--engineering-root',type=Path)
    p.add_argument('--author-lock',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    try:result=audit_stage(args.stage,args.engineering_root,args.author_lock)
    except Exception:result={'status':'FAIL','created_utc':datetime.now(timezone.utc).isoformat(),'traceback':traceback.format_exc(),'model_test_outcomes_accessed':False}
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='endpoints'},indent=2));sys.exit(0 if result['status']=='PASS' else 1)
