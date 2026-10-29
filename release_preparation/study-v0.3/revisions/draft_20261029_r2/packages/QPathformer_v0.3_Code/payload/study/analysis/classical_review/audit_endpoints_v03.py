"""Independent, read-only completion gate. Never loads a test population.

--engineering-pilot validates auditor behavior on the preserved preflight only.
Official mode requires the whole registered stage completed without failures.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,json,sys,traceback
import numpy as np
if not __debug__ or sys.flags.optimize:
    raise RuntimeError('Audit requires enabled assertions; Python -O/-OO is forbidden')
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];Q=ROOT/'quantum'
RECOVERY=ROOT/'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json'
RECOVERY_SHA='049f4a627fda5fa08c739cc53375aa104e28d223bb78d525841d0f01d7931e0e'
BAND=32*np.finfo(np.float64).eps
METHODS=('scheduled','min_depth2','untied_assigned','fixed1','fixed2','fixed4','encoding1','readout1','hash40','kmeans40','ensemble40','mlp41','mlp129')
SEEDS={'A':(501,502,503),'B':(601,602,603,604,605)}
COUNTS=dict(zip(METHODS,(16,16,40,4,8,16,4,5,40,40,40,41,129)))
WORK_KEYS=('forward_circuit_examples','shift_circuit_examples','circuit_examples','layer_applications','feature_ry_gates','feature_rz_gates','trainable_ry_gates','trainable_rz_gates','cx_gates','readout_ry_gates','bank_record_visits','model_record_visits')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def same(a,b):assert np.array_equal(a,b),'Exact mismatch'
def near(a,b,tol=2e-11):assert np.allclose(a,b,rtol=0,atol=tol),'Numerical mismatch'
def sources():
    files=[Q/n for n in ('qstudy.py','circuits.py','reference_v03.py','prepare_data.py','routers.py','launch_stage.py')]
    files+=sorted((Q/'vendor/qpath').glob('*.py'))+sorted((Q/'tests').glob('test*.py'))
    return {str(p.relative_to(Q)).replace('\\','/'):sha(p) for p in files}

def effective(method,d):
    if method in ('fixed1','encoding1','readout1'):return np.ones_like(d)
    if method in ('fixed2','hash40','kmeans40','ensemble40'):return np.full_like(d,2)
    if method=='fixed4':return np.full_like(d,4)
    return np.maximum(d,2) if method=='min_depth2' else d

def work(method,depth,gradient=False):
    w={k:0 for k in WORK_KEYS};w['model_record_visits']=len(depth)
    if method.startswith('mlp'):return w
    d=effective(method,np.asarray(depth));copies=5 if method=='ensemble40' else 1
    mult=1+8*d+2*(method=='readout1') if gradient else np.ones_like(d)
    n=int(len(d)*copies);executions=int(mult.sum()*copies);layers=int((d*mult).sum()*copies)
    w.update(forward_circuit_examples=n,shift_circuit_examples=executions-n,circuit_examples=executions,
             layer_applications=layers,feature_ry_gates=layers*2,feature_rz_gates=layers*2*(method=='encoding1'),
             trainable_ry_gates=layers*2,trainable_rz_gates=layers*2,cx_gates=layers,readout_ry_gates=executions,bank_record_visits=n)
    return w
def scaled(w,m):return {k:int(v*m) for k,v in w.items()}

def initial(method,seed):
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1])))
    master=rng.uniform(-.1,.1,(5,4,2,2))
    if method.startswith('mlp'):
        h=5 if method=='mlp41' else 16;rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,4])))
        p=np.r_[rng.uniform(-np.sqrt(6/(6+h)),np.sqrt(6/(6+h)),6*h),np.zeros(h),rng.uniform(-np.sqrt(6/(h+1)),np.sqrt(6/(h+1)),h),0.]
    elif method in ('hash40','kmeans40','ensemble40'):p=master[:,:2].ravel().copy()
    elif method=='untied_assigned':p=np.concatenate([master[0,:d].ravel() for d in range(1,5)])
    elif method=='readout1':p=np.r_[master[0,:1].ravel(),np.pi/2]
    else:p=master[0,:{'fixed1':1,'encoding1':1,'fixed2':2}.get(method,4)].ravel().copy()
    return p,master

def ry(theta):
    c,s=np.cos(theta/2),np.sin(theta/2)
    return np.array([[c,-s],[s,c]],complex)
def rz(theta):return np.diag(np.exp(np.array([-1j,1j])*theta/2))
def dense_batch(x,bank,depth,encoding=False,beta=np.pi/2):
    """Independent dense 4x4 matrix application, no production circuit import."""
    n=len(x);state=np.zeros((n,4),complex);state[:,0]=1;eye=np.eye(2,dtype=complex)
    for layer in range(len(bank)):
        ids=np.where(depth>layer)[0]
        if not len(ids):continue
        v=state[ids]
        for qubit in range(2):
            matrices=np.stack([np.kron(ry(np.pi*t),eye) if qubit==0 else np.kron(eye,ry(np.pi*t)) for t in x[ids,qubit]])
            v=np.einsum('nij,nj->ni',matrices,v)
            if encoding:
                matrices=np.stack([np.kron(rz(np.pi*t/2),eye) if qubit==0 else np.kron(eye,rz(np.pi*t/2)) for t in x[ids,qubit]])
                v=np.einsum('nij,nj->ni',matrices,v)
            for gate in (ry(bank[layer,qubit,0]),rz(bank[layer,qubit,1])):
                matrix=np.kron(gate,eye) if qubit==0 else np.kron(eye,gate)
                v=v@matrix.T
        state[ids]=v[:,[0,1,3,2]]
    state=state@np.kron(ry(beta),eye).T
    return np.sum(np.abs(state[:,2:])**2,axis=1)

def predictions(method,p,pop):
    x,depth=pop['x'],pop['depth'];d=effective(method,depth);out=np.zeros(len(x))
    if method.startswith('mlp'):
        h=5 if method=='mlp41' else 16;f=np.c_[x,np.eye(4)[depth-1]];n=6*h
        logits=np.maximum(f@p[:n].reshape(6,h)+p[n:n+h],0)@p[n+h:n+2*h]+p[-1]
        # Stable independent sigmoid.
        return np.exp(-np.logaddexp(0.,-logits))
    if method in ('hash40','kmeans40','ensemble40'):
        route=pop.get('hash_route') if method=='hash40' else pop.get('kmeans_route')
        for bank in range(5):
            ids=np.arange(len(x)) if method=='ensemble40' else np.where(route==bank)[0]
            if len(ids):out[ids]+=dense_batch(x[ids],p[bank*8:bank*8+8].reshape(2,2,2),d[ids])/(5 if method=='ensemble40' else 1)
    elif method=='untied_assigned':
        for depth_value in range(1,5):
            ids=np.where(d==depth_value)[0];offset=2*depth_value*(depth_value-1)
            out[ids]=dense_batch(x[ids],p[offset:offset+depth_value*4].reshape(depth_value,2,2),d[ids])
    else:out=dense_batch(x,p[:4] .reshape(1,2,2) if method=='readout1' else p.reshape(-1,2,2),d,method=='encoding1',p[-1] if method=='readout1' else np.pi/2)
    return out

def metrics(y,p):
    pred=(p>=.5).astype(int);cm=np.array([[np.sum((y==a)&(pred==b)) for b in range(2)] for a in range(2)],int)
    f=[2*cm[k,k]/(2*cm[k,k]+cm[k,1-k]+cm[1-k,k]) if cm[k].sum()+cm[:,k].sum() else 0 for k in range(2)]
    pc=np.clip(p,1e-7,1-1e-7)
    return {'n':len(y),'bce':float(np.mean(-y*np.log(pc)-(1-y)*np.log1p(-pc))), 'macro_f1':float(np.mean(f)),
            'accuracy':float(np.mean(pred==y)),'confusion':cm.tolist(),'clipped':int(np.sum((p<1e-7)|(p>1-1e-7)))}

def classification(y,pred):
    """Classification-only diagnostic; never invent probabilities or a BCE."""
    cm=np.array([[np.sum((y==a)&(pred==b)) for b in range(2)] for a in range(2)],int)
    f=[2*cm[k,k]/(2*cm[k,k]+cm[k,1-k]+cm[1-k,k]) if cm[k].sum()+cm[:,k].sum() else 0 for k in range(2)]
    return {'macro_f1':float(np.mean(f)),'accuracy':float(np.mean(pred==y)),'confusion':cm.tolist()}

def numerical_review(saved,reference,pop):
    """Independent implementation of the explicit pre-B recovery convention."""
    saved,reference=np.asarray(saved),np.asarray(reference);y=pop['y']
    assert saved.shape==reference.shape==y.shape and len(y)>0
    assert np.isfinite(saved).all() and np.isfinite(reference).all()
    error=float(np.max(np.abs(saved-reference)));assert error<=2e-12,'Independent probability discrepancy'
    canonical=saved>=.5;other=reference>=.5
    band=np.abs(saved-.5)<=BAND;reference_band=np.abs(reference-.5)<=BAND
    disagreement=canonical!=other;outside=disagreement&~(band&reference_band)
    assert not outside.any(),'Classification disagreement outside approved numerical band'
    canon_metric=metrics(y,saved);ref_metric=metrics(y,reference)
    assert abs(canon_metric['bce']-ref_metric['bce'])<=1e-9,'Independent BCE discrepancy'
    def counts(mask):
        return {'records':int(mask.sum()),'canonical_near_band_count':int(np.sum(mask&band)),
                'reference_near_band_count':int(np.sum(mask&reference_band)),
                'union_near_band_count':int(np.sum(mask&(band|reference_band))),
                'exact_class_agreement':not bool(np.any(mask&disagreement)),
                'disagreements':int(np.sum(mask&disagreement)),'outside_band_disagreements':int(np.sum(mask&outside))}
    scenarios={}
    for name,assignment in [('all_zero',np.zeros(len(y),int)),('all_one',np.ones(len(y),int)),
                            ('all_incorrect',1-y),('all_correct',y)]:
        hypothetical=canonical.astype(int).copy();hypothetical[band]=assignment[band]
        scenarios[name]=classification(y,hypothetical)
    rows=[]
    for i in np.flatnonzero(disagreement):
        rows.append({'record_id':int(pop['ids'][i]),'original_depth':int(pop['depth'][i]),'label':int(y[i]),
                     'hash_route':int(pop['hash_route'][i]),'kmeans_route':int(pop['kmeans_route'][i]),
                     'canonical_probability':float(saved[i]),'reference_probability':float(reference[i]),
                     'canonical_prediction':int(canonical[i]),'reference_prediction':int(other[i])})
    return {'protocol_sha256':RECOVERY_SHA,'absolute_half_width':float(BAND),'maximum_probability_error':error,
            **counts(np.ones(len(y),bool)),
            'slices':{key:{str(int(v)):counts(pop[key]==v) for v in np.unique(pop[key])} for key in ('depth','hash_route','kmeans_route')},
            'canonical_metrics':canon_metric,'reference_metrics':ref_metric,
            'reference_minus_canonical':{key:ref_metric[key]-canon_metric[key] for key in ('bce','macro_f1','accuracy')},
            'disagreement_rows':rows,'canonical_band_sensitivity':scenarios,
            'interpretation':'PASS means canonical metrics reproduced plus independent probability/BCE agreement and only explicitly flagged numerical-band class differences. Sensitivity uses the canonical mask only; all_incorrect/all_correct are label-assisted numerical extrema, not model performance or statistical intervals.'}

def exact_canonical_classification(computed,recorded):
    for key in ('macro_f1','accuracy','confusion','n','clipped'):
        assert computed[key]==recorded[key],f'Canonical saved-probability metric mismatch: {key}'

def checkmetrics(a,b):
    assert a.keys()==b.keys()
    for k in a:
        if k in ('bce','macro_f1','accuracy'):near(a[k],b[k])
        else:assert a[k]==b[k],k

def checkpoint(path,rounds,nparams):
    a=load(path);assert set(a)=={'parameters','adam_m','adam_v','adam_t','current_round','completed_rounds'}
    assert int(a['adam_t'])==rounds*75 and int(a['current_round'])==rounds and int(a['completed_rounds'])==rounds
    for k in ('parameters','adam_m','adam_v'):assert a[k].shape==(nparams,) and np.isfinite(a[k]).all()
    assert np.all(a['adam_v']>=0)
    return a

def audit_run(folder,method,seed,stage,training,validation,seal,freeze,rounds,engineering):
    config=read(folder/'config.json');result=read(folder/'result.json');commit=read(folder/'endpoint_commit.json');status=read(folder/'status.json')
    assert not (folder/'failure.json').exists()
    assert status=={'status':'completed','round':rounds,'seed':seed,'method':method}
    for obj in (config,result):
        assert obj['method']==method and obj['seed']==seed and obj['stage']==stage and obj['engineering']==engineering
        assert obj['test_accessed'] is False and obj['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json')
        assert obj['stage_freeze_sha256']==(None if engineering else sha(Q/f'STAGE_{stage}_FREEZE.json'))
    assert config['source_hashes']==sources()
    assert config['rounds']==rounds and config['batch_size']==64 and config['train_records']==4800 and config['validation_records']==1600
    if not engineering:assert config['settings']==freeze['settings']
    assert config['dataset']==('engineering' if engineering else 'development' if stage=='A' else 'confirmation')
    assert config['router_policy_file']==f"data/{config['dataset']}_router.json"
    assert config['router_policy_sha256']==sha(Q/config['router_policy_file'])
    for key,file in [('result_sha256','result.json'),('config_sha256','config.json'),('selected_checkpoint_sha256','selected_checkpoint.npz'),('last_checkpoint_sha256','last_checkpoint.npz'),('ledger_sha256','ledger.jsonl'),('record_orders_sha256','record_orders.npz')]:
        assert commit[key]==sha(folder/file)
        if key in result:assert result[key]==commit[key]
    assert result['status']=='completed' and result['completed_rounds']==rounds and result['optimizer_global_updates']==75*rounds and result['parameter_count']==COUNTS[method]
    p,master=initial(method,seed);init=load(folder/'initial_state.npz');same(init['parameters'],p);same(init['master_bank'],master)
    order_data=load(folder/'record_orders.npz');same(order_data['record_ids'],training['ids']);assert order_data['orders'].shape==(rounds,4800)
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
    for order in order_data['orders']:same(order,rng.permutation(4800))
    rows=[json.loads(s) for s in (folder/'ledger.jsonl').read_text(encoding='utf-8').splitlines()];assert len(rows)==rounds
    tw,vw=work(method,training['depth'],True),work(method,validation['depth']);best=float('inf');selected=[];elapsed=0.
    for i,row in enumerate(rows,1):
        assert row['round']==i and row['optimizer_updates']==75*i
        assert row['work_cumulative']=={'training':scaled(tw,i),'validation':scaled(vw,i)}
        assert row['elapsed_seconds']>=elapsed;elapsed=row['elapsed_seconds']
        assert row['validation']['n']==1600 and np.isfinite(list(row['validation'][k] for k in ('bce','macro_f1','accuracy'))).all()
        cm=np.asarray(row['validation']['confusion']);assert cm.shape==(2,2) and cm.sum()==1600 and np.all(cm>=0)
        f1=[2*cm[k,k]/(cm[k].sum()+cm[:,k].sum()) if cm[k].sum()+cm[:,k].sum() else 0. for k in range(2)]
        near(row['validation']['macro_f1'],np.mean(f1));near(row['validation']['accuracy'],np.trace(cm)/1600)
        assert 0<=row['validation']['clipped']<=1600 and 0<=row['training_clipped_probabilities']<=4800
        assert row['mean_batch_gradient_norm']>=0 and row['maximum_batch_gradient_norm']>=row['mean_batch_gradient_norm']-1e-12
        choose=row['validation']['bce']<best;assert row['selected']==choose
        if choose:best=row['validation']['bce'];selected.append(i)
    assert result['selected_round']==selected[-1]
    assert {p.name for p in folder.glob('selected_round_*.npz')}=={f'selected_round_{i:04d}.npz' for i in selected}
    for i in selected:checkpoint(folder/f'selected_round_{i:04d}.npz',i,COUNTS[method])
    selected_path=folder/f'selected_round_{selected[-1]:04d}.npz'
    assert sha(selected_path)==sha(folder/'selected_checkpoint.npz')
    cp=checkpoint(selected_path,selected[-1],COUNTS[method]);checkpoint(folder/'last_checkpoint.npz',rounds,COUNTS[method])
    with (folder/'validation_predictions.csv').open(newline='',encoding='utf-8') as f:csvrows=list(csv.DictReader(f))
    assert len(csvrows)==1600
    for name,key in [('record_id','ids'),('original_depth','depth'),('hash_route','hash_route'),('kmeans_route','kmeans_route'),('label','y')]:same(np.array([int(r[name]) for r in csvrows]),validation[key])
    savedp=np.array([float(r['probability']) for r in csvrows]);assert np.isfinite(savedp).all();same(np.array([int(r['prediction']) for r in csvrows]),savedp>=.5)
    replay=predictions(method,cp['parameters'],validation);review=numerical_review(savedp,replay,validation);error=review['maximum_probability_error']
    exact_canonical_classification(metrics(validation['y'],savedp),result['selected_validation'])
    exact_canonical_classification(metrics(validation['y'],savedp),rows[selected[-1]-1]['validation'])
    checkmetrics(metrics(validation['y'],savedp),result['selected_validation']);checkmetrics(result['selected_validation'],rows[selected[-1]-1]['validation'])
    for d in range(1,5):
        ix=validation['depth']==d;checkmetrics(metrics(validation['y'][ix],savedp[ix]),result['validation_by_original_depth'][str(d)])
        exact_canonical_classification(metrics(validation['y'][ix],savedp[ix]),result['validation_by_original_depth'][str(d)])
    assert result['work']=={'training':scaled(tw,rounds),'validation':scaled(vw,rounds),'selected_validation_replay':vw}
    assert result['training_clipped_probabilities']==sum(r['training_clipped_probabilities'] for r in rows)
    d=effective(method,training['depth']);bank=np.zeros(5,dtype=np.int64)
    if method.startswith('mlp'):depth_counts=np.zeros(4,dtype=np.int64);layers=depth_counts.copy()
    else:
        copies=5 if method=='ensemble40' else 1;depth_counts=np.bincount(d,minlength=5)[1:5]*rounds*copies
        layers=np.array([np.sum(d>=i) for i in range(1,5)])*rounds*copies
        if method=='ensemble40':bank[:]=4800*rounds
        elif method in ('hash40','kmeans40'):bank=np.bincount(training['hash_route' if method=='hash40' else 'kmeans_route'],minlength=5)*rounds
        elif method=='untied_assigned':bank[:4]=np.bincount(d,minlength=5)[1:5]*rounds
        else:bank[0]=4800*rounds
    same(bank,result['bank_training_record_visits']);same(depth_counts,result['executed_depth_training_record_visits']);same(layers,result['layer_training_record_exposure'])
    grads=load(folder/'epoch_gradient_means.npz')['gradients'];assert grads.shape==(rounds,COUNTS[method]) and np.isfinite(grads).all()
    raw=load(folder/'selected_training_gradients_by_depth.npz');same(raw['depths'],np.arange(1,5));assert raw['gradients'].shape==(4,COUNTS[method]) and np.isfinite(raw['gradients']).all()
    for d in range(1,5):
        diag=result['diagnostics']['train_groups'][str(d)];near(np.linalg.norm(raw['gradients'][d-1]),diag['gradient_norm'])
        assert diag['work']==work(method,training['depth'][training['depth']==d],True)
    fixture=np.argsort(validation['ids'],kind='stable')[:1024];same(load(folder/'inference_fixture_ids.npz')['record_ids'],validation['ids'][fixture])
    inference=result['inference'];assert inference['records']==1024 and inference['warmups']==1 and inference['timed_repeats']==3
    assert inference['maximum_cached_difference']<=1e-12 and inference['work_separate_from_training']==scaled(work(method,validation['depth'][fixture]),4)
    if method not in ('hash40','kmeans40'):assert inference['route_repeat_seconds']==[0.,0.,0.]
    assert len(inference['total_repeat_seconds'])==3 and min(inference['total_repeat_seconds'])>0
    near(inference['mean_seconds_per_record'],np.mean(inference['total_repeat_seconds'])/1024)
    ds=seal['datasets'][config['dataset']];prep=result['preparation'];assert prep==config['preparation']
    kind='hash' if method=='hash40' else 'kmeans' if method=='kmeans40' else None
    near(prep['generation_seconds_charged'],ds['generation_seconds']);near(prep['joint_router_fit_seconds_charged'],ds['router_fit_seconds'] if kind else 0)
    near(prep['train_validation_route_cache_seconds_charged'],sum(ds['route_application_seconds_by_split'][split][kind] for split in ('train','validation')) if kind else 0)
    near(result['charged_training_seconds'],result['training_seconds']+sum(prep[k] for k in ('generation_seconds_charged','joint_router_fit_seconds_charged','train_validation_route_cache_seconds_charged')))
    assert result['total_seconds']>=result['training_seconds']>=elapsed
    assert result['validation_route_population_counts']=={k:np.bincount(validation[k+'_route'],minlength=5).tolist() for k in ('hash','kmeans')}
    artifacts={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
    return {'seed':seed,'method':method,'rounds':rounds,'optimizer_updates':rounds*75,'selected_round':selected[-1],
            'selected_validation':result['selected_validation'],
            'numerical_verification':review,
            'all_validation_rows_checked':rounds,'selected_validation_predictions_replayed':1600,'maximum_independent_probability_difference':error,
            'sample_orders_reconstructed':rounds,'retained_selected_checkpoints_checked':len(selected),'all_artifact_sha256':artifacts,
            'additional_cached_inference_comparison_work':work(method,validation['depth'][fixture]),
            'inference_accounting_scope':'Four measured forwards plus one additional cached comparison forward; latter separately reconstructed here, as frozen original result counts only four.'}

def main(stage,engineering_pilot,endpoint_lock=None):
    assert sha(RECOVERY)==RECOVERY_SHA,'Recovery protocol binding changed'
    before=sources();seal=read(Q/'data/DATA_SEAL.json');freeze=None if engineering_pilot else read(Q/f'STAGE_{stage}_FREEZE.json')
    if freeze:
        assert freeze['review_status']=='approved_by_root' and freeze['methods']==list(METHODS) and freeze['training_seeds']==list(SEEDS[stage])
        assert freeze['source_hashes']==before and freeze['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json')
        assert freeze['settings']['rounds']==200 and freeze['settings']['optimizer_updates']==15000
        for name,h in freeze['protocol_hashes'].items():assert sha(ROOT/'governance'/name)==h
        stagefolder=Q/f'stage_{stage}';stage_status=read(stagefolder/'stage_status.json');assert stage_status['status']=='completed'
        assert sorted((x['seed'],x['exit_code']) for x in stage_status['exits'])==[(s,0) for s in SEEDS[stage]]
        assert read(stagefolder/'process_exits.json')==stage_status['exits']
        launch=read(stagefolder/'launch.json');assert launch['source_hashes']==before and launch['stage_freeze_sha256']==sha(Q/f'STAGE_{stage}_FREEZE.json')
    dataset='engineering' if engineering_pilot else 'development' if stage=='A' else 'confirmation'
    arrays=[]
    for split in ('train','validation'):
        p=Q/'data'/f'{dataset}_{split}.npz';assert sha(p)==seal['files'][p.name]['sha256'];arrays.append(load(p))
    train,validation=arrays;assert len(train['y'])==4800 and len(validation['y'])==1600
    rows=[];rounds=3 if engineering_pilot else 200;seeds=(9501,) if engineering_pilot else SEEDS[stage]
    for seed in seeds:
        folder=Q/'engineering_pilot_v02' if engineering_pilot else Q/f'stage_{stage}'/f'seed_{seed}'
        if not engineering_pilot:
            assert read(folder/'failures.json')==[]
            shift=SEEDS[stage].index(seed)%len(METHODS);assert read(folder/'execution_order.json')['methods']==list(METHODS[shift:]+METHODS[:shift])
        for method in METHODS:
            rows.append(audit_run(folder/method,method,seed,stage,train,validation,seal,freeze,rounds,bool(engineering_pilot)))
            print(f"VERIFIED {stage} {seed} {method}",flush=True)
    lock_hash=None
    if not engineering_pilot:
        assert endpoint_lock is not None
        lock=read(endpoint_lock);lock_hash=sha(endpoint_lock)
        assert lock['status']=='PASS' and lock['stage']==stage and lock['endpoint_count']==len(rows) and lock['test_accessed'] is False
        assert lock['numerical_recovery_protocol_sha256']==RECOVERY_SHA
        assert lock['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json') and lock['stage_freeze_sha256']==sha(Q/f'STAGE_{stage}_FREEZE.json') and lock['training_source_hashes']==before
        for name,h in lock['audit_sources'].items():assert sha(Q/name)==h
        bound={(r['seed'],r['method']):r for r in lock['endpoints']}
        assert len(bound)==len(rows)==len(lock['endpoints']) and set(bound)=={(r['seed'],r['method']) for r in rows}
        field_files={'result_sha256':'result.json','config_sha256':'config.json','selected_checkpoint_sha256':'selected_checkpoint.npz','last_checkpoint_sha256':'last_checkpoint.npz',
                     'ledger_sha256':'ledger.jsonl','record_orders_sha256':'record_orders.npz','endpoint_commit_sha256':'endpoint_commit.json','status_sha256':'status.json','validation_predictions_sha256':'validation_predictions.csv'}
        for row in rows:
            item=bound[(row['seed'],row['method'])]
            assert item['path']==f"stage_{stage}/seed_{row['seed']}/{row['method']}" and item['selected_round']==row['selected_round']
            for field,file in field_files.items():assert item[field]==row['all_artifact_sha256'][file]
            for key in ('bce','macro_f1','accuracy'):near(item['selected_validation'][key],row['selected_validation'][key])
            assert item['reconstructed_cached_comparison_work']==row['additional_cached_inference_comparison_work']
    assert before==sources() and sha(RECOVERY)==RECOVERY_SHA
    return {'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'stage':stage,'engineering_only':bool(engineering_pilot),
            'source_sha256':before,'auditor_sha256':sha(__file__),'stage_freeze_sha256':sha(Q/f'STAGE_{stage}_FREEZE.json') if freeze else None,
            'data_seal_sha256':sha(Q/'data/DATA_SEAL.json'),'runs_verified':len(rows),'endpoint_count':len(rows),'endpoint_lock_sha256':lock_hash,
            'numerical_recovery_protocol_sha256':RECOVERY_SHA,
            'numerical_verification_summary':{'endpoints_with_class_disagreements':sum(not r['numerical_verification']['exact_class_agreement'] for r in rows),
                'canonical_near_band_records':sum(r['numerical_verification']['canonical_near_band_count'] for r in rows),
                'disagreements':sum(r['numerical_verification']['disagreements'] for r in rows),
                'outside_band_disagreements':sum(r['numerical_verification']['outside_band_disagreements'] for r in rows)},
            'endpoint_lock_path':str(endpoint_lock) if endpoint_lock else None,'optimizer_updates_checked':sum(r['optimizer_updates'] for r in rows),
            'validation_ledger_rows_checked':sum(r['all_validation_rows_checked'] for r in rows),'selected_validation_predictions_replayed':sum(r['selected_validation_predictions_replayed'] for r in rows),
            'runs':rows,'test_arrays_or_outcomes_read':False,'training_executed':False,'test_release_issued':False,
            'scope_limit':'Structural full-horizon evidence and exact sample/work reconstruction, with independent dense-matrix selected-validation replay. Not a full rerun of every optimizer step; no per-round probability files exist, so intermediate validation BCE values are structurally checked and selection reconstructed, not independently regenerated.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['A','B'],required=True);p.add_argument('--engineering-pilot',action='store_true');p.add_argument('--endpoint-lock',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    if not a.engineering_pilot and a.endpoint_lock is None:p.error('Official audit requires the author endpoint lock path')
    try:report=main(a.stage,a.engineering_pilot,a.endpoint_lock)
    except Exception:report={'status':'FAIL','created_utc':datetime.now(timezone.utc).isoformat(),'auditor_sha256':sha(__file__),'traceback':traceback.format_exc()}
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('runs','source_sha256')},indent=2),flush=True)
    sys.exit(0 if report['status']=='PASS' else 1)
