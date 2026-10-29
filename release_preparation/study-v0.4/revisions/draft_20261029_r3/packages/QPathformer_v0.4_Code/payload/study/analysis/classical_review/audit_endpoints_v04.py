"""Independent all-round validation audit. No production models or test loader.

All checks use explicit exceptions, including under Python -O. Official use
requires closed full-stage execution and the separately authored endpoint lock.
This audits every saved round, not a rerun of all 15000 optimizer updates.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, csv, hashlib, json, sys, time, traceback
import numpy as np
import reference_v04 as ref

ROOT=Path(__file__).resolve().parents[2];Q=ROOT/'quantum';HERE=Path(__file__).resolve().parent
SEEDS={'A':(701,702,703),'B':(801,802,803,804,805)}
POPS={'A':('development_circle','development_ellipse'),
      'B':('confirmation_circle_1','confirmation_circle_2','confirmation_ellipse')}
PTOL=2e-12;BTOL=1e-8;CTOL=2e-12;BAND=32*np.finfo(np.float64).eps

def need(condition,message):
    if not condition:raise RuntimeError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rawsha(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def same(a,b,message):need(np.array_equal(a,b),message)
def near(a,b,tol,message):need(np.isfinite(a).all() and np.isfinite(b).all() and np.max(np.abs(np.asarray(a)-np.asarray(b)),initial=0)<=tol,message)
def metric_check(a,b):
    need(set(a)==set(b),'Metric inventory differs')
    for k in a:
        if k in ('bce','macro_f1','accuracy'):near(a[k],b[k],CTOL,'Canonical metric differs: '+k)
        else:need(a[k]==b[k],'Canonical exact metric differs: '+k)

def expected_initial(method,seed):
    family,routing=method.split('_');banks=1 if routing=='global' else 5
    if family=='q2':
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1])))
        master=rng.uniform(-.1,.1,(5,4,2,2));return master[:banks,:2].reshape(-1),master
    if family=='trig':
        master=np.zeros((banks,25));return master.ravel(),master
    h=32 if routing=='global' else 2
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,4,h])))
    master=[]
    for _ in range(banks):
        a=np.sqrt(6/(2+h));b=np.sqrt(6/(h+1))
        master.append(np.r_[rng.uniform(-a,a,2*h),np.zeros(h),rng.uniform(-b,b,h),0.])
    master=np.asarray(master);return master.ravel(),master

def expected_work(method,n,gradient=False):
    family,routing=method.split('_');q=family=='q2';forward=n if q else 0;shift=16*n if q and gradient else 0;c=forward+shift
    w={'forward_circuit_examples':forward,'shift_circuit_examples':shift,'circuit_examples':c,
       'layer_applications':2*c,'feature_ry_gates':4*c,'feature_rz_gates':0,
       'trainable_ry_gates':4*c,'trainable_rz_gates':4*c,'cx_gates':2*c,'readout_ry_gates':c,
       'bank_record_visits':n,'model_record_visits':n,'classical_forward_examples':0 if q else n,
       'classical_backward_examples':n if not q and gradient else 0,
       'trig_feature_values':25*n*(2 if gradient else 1) if family=='trig' else 0,
       'mlp_hidden_evaluations':n*(32 if routing=='global' else 2)*(2 if gradient else 1) if family=='mlp' else 0}
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

def checkpoint(path,state,round_number,pcount):
    z=load(path);need(set(z)=={'parameters','adam_m','adam_v','adam_t','current_round','completed_rounds'},'Checkpoint fields differ')
    same(z['parameters'],state,'Checkpoint parameter identity differs')
    for key in ('adam_m','adam_v'):
        need(z[key].shape==(pcount,) and z[key].dtype==np.float64 and np.isfinite(z[key]).all(),'Invalid optimizer moment')
    need(np.all(z['adam_v']>=0),'Negative second moment')
    need(int(z['adam_t'])==75*round_number and int(z['current_round'])==round_number and int(z['completed_rounds'])==round_number,'Checkpoint horizon/update counters differ')
    return z

def audit_endpoint(folder,stage,population,seed,method,seal,freeze=None,engineering=False):
    commit,commit_sha=check_commit(folder);c=read(folder/'config.json');r=read(folder/'result.json');status=read(folder/'status.json')
    for obj in (commit,c,r,status):
        for k,v in [('population',population),('seed',seed),('method',method)]:need(obj[k]==v,'Endpoint identity mismatch')
    need(c['stage']==r['stage']==stage and c['engineering']==r['engineering']==engineering,'Stage/engineering mismatch')
    need(r['status']==status['status']=='completed' and c['test_accessed'] is False and r['test_accessed'] is False,'Incomplete or test-accessed endpoint')
    rounds=int(c['rounds']);need(rounds>0 and (engineering or rounds==200),'Full horizon not completed')
    need(c['train_records']==4800 and c['validation_records']==1600 and c['batch_size']==64,'Record/batch budget differs')
    need(r['completed_rounds']==status['round']==rounds and r['optimizer_global_updates']==75*rounds,'Endpoint update count differs')
    need(c['data_seal_sha256']==r['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json'),'Data seal binding differs')
    need(c['source_hashes']==commit['source_hashes'],'Commit/source mismatch')
    for name,value in c['source_hashes'].items():need(sha(Q/name)==value,'Source changed: '+name)
    if not engineering:
        need(c['source_hashes']==freeze['source_hashes'],'Source not frozen')
        need(c['settings']==freeze['settings'],'Settings differ from freeze')
        need(c['stage_freeze_sha256']==r['stage_freeze_sha256']==sha(Q/f'STAGE_{stage}_FREEZE.json'),'Freeze binding differs')
    data=[]
    for split in ('train','validation'):
        path=Q/'data'/f'{population}_{split}.npz';need(sha(path)==seal['files'][path.name]['sha256'],'Population payload changed')
        data.append(load(path))
    train,val=data;need(sha(Q/'data'/f'{population}_router.json')==c['router_policy_sha256']==seal['routers'][population]['sha256'],'Policy identity differs')
    identity=load(folder/'population_identity.npz');need(set(identity)=={'train_ids','validation_ids'},'Population identity keys differ')
    same(identity['train_ids'],train['ids'],'Training identities differ');same(identity['validation_ids'],val['ids'],'Validation identities differ')
    initial=load(folder/'initial_state.npz');theta,master=expected_initial(method,seed)
    same(initial['parameters'],theta,'Initialization differs');same(initial['master_initial'],master,'Master initialization differs')
    states=np.load(folder/'round_parameters.npy',allow_pickle=False);probs=np.load(folder/'validation_probabilities.npy',allow_pickle=False);orders=np.load(folder/'record_orders.npy',allow_pickle=False)
    pc=ref.PARAMETERS[method];need(states.shape==(rounds,pc) and states.dtype==np.float64 and np.isfinite(states).all(),'Invalid saved parameter states')
    need(probs.shape==(rounds,1600) and probs.dtype==np.float64 and np.isfinite(probs).all() and np.all((probs>=0)&(probs<=1)),'Invalid full validation probabilities')
    need(orders.shape==(rounds,4800) and orders.dtype==np.uint16,'Invalid recorded orders')
    routing=method.split('_')[1];route=None if routing=='global' else val[routing+'_route']
    independent=ref.predict_many(method,states,val['x'],route);near(probs,independent,PTOL,'All-round probability replay differs')
    # Fixed scalar spotchecks, independent of outcomes: endpoints/middle rounds and lowest7 validation IDs.
    spots=np.argsort(val['ids'],kind='stable')[:7];spot_rounds=sorted({0,rounds//2,rounds-1});scalar_error=0.
    for index in spot_rounds:
        scalar=ref.scalar_predict(method,states[index],val['x'][spots],None if route is None else route[spots])
        scalar_error=max(scalar_error,float(np.max(abs(scalar-probs[index,spots]))));near(scalar,probs[index,spots],PTOL,'Scalar spotcheck differs')
    ledger=[json.loads(line) for line in (folder/'ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    need(len(ledger)==rounds,'Ledger horizon differs');sampler=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
    banks=1 if routing=='global' else 5;bank_counts=np.array([4800]) if banks==1 else np.bincount(train[routing+'_route'],minlength=5)
    need(r['parameter_count']==pc and r['bank_count']==banks and r['parameters_per_bank']==pc//banks,'Architecture counts differ')
    need(r['train_bank_counts']==bank_counts.tolist(),'Training bank allocation differs')
    best=float('inf');chosen=None;chosen_generations=[];last_elapsed=0.;all_threshold=[];max_bce=0.;clip_total=0
    for i,row in enumerate(ledger):
        number=i+1;need(row['round']==number and row['optimizer_updates']==75*number,'Ledger counters differ')
        same(orders[i],sampler.permutation(4800),'Paired sample order differs')
        need(row['round_parameter_sha256']==rawsha(states[i]) and row['validation_probability_sha256']==rawsha(probs[i]) and row['record_order_sha256']==rawsha(orders[i]),'Raw round-array digest differs')
        canonical=ref.metrics(val['y'],probs[i]);metric_check(canonical,row['validation'])
        error=abs(ref.bce(val['y'],independent[i])-canonical['bce']);max_bce=max(max_bce,error);need(error<=BTOL,'Independent aggregate clipped BCE differs')
        selected=canonical['bce']<best;need(row['selected']==selected,'Earliest minimum selection rule differs')
        if selected:best=canonical['bce'];chosen=number;chosen_generations.append(number)
        need(row['bank_record_visits_cumulative']==(bank_counts*number).tolist(),'Cumulative bank exposure differs')
        need(row['work_cumulative']=={'training':expected_work(method,4800*number,True),'validation':expected_work(method,1600*number)},'Cumulative operation accounting differs')
        for key in ('training_loss','mean_batch_gradient_norm','maximum_batch_gradient_norm','elapsed_seconds'):
            need(np.isfinite(row[key]) and row[key]>=0,'Invalid training diagnostic '+key)
        need(row['maximum_batch_gradient_norm']+1e-14>=row['mean_batch_gradient_norm'],'Gradient extrema inconsistent')
        need(row['elapsed_seconds']>=last_elapsed,'Nonmonotone elapsed time');last_elapsed=row['elapsed_seconds']
        need(isinstance(row['training_clipped_probabilities'],int) and 0<=row['training_clipped_probabilities']<=4800,'Clip counter invalid');clip_total+=row['training_clipped_probabilities']
        threshold=threshold_check(val['y'],probs[i],independent[i],val['ids']);threshold['round']=number;all_threshold.append(threshold)
    need(chosen==r['selected_round'],'Selected round differs');need(r['training_clipped_probabilities']==clip_total,'Cumulative clipping counter differs')
    need(r['bank_training_record_visits']==(bank_counts*rounds).tolist(),'Endpoint exposure differs')
    need({p.name for p in folder.glob('selected_round_*.npz')}=={f'selected_round_{n:04d}.npz' for n in chosen_generations},'Selected generations differ')
    for number in chosen_generations:checkpoint(folder/f'selected_round_{number:04d}.npz',states[number-1],number,pc)
    checkpoint(folder/'last_checkpoint.npz',states[-1],rounds,pc)
    selected=checkpoint(folder/'selected_checkpoint.npz',states[chosen-1],chosen,pc)
    need(sha(folder/'selected_checkpoint.npz')==sha(folder/f'selected_round_{chosen:04d}.npz'),'Selected checkpoint alias differs')
    metric_check(ref.metrics(val['y'],probs[chosen-1]),r['selected_validation'])
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
    gm=load(folder/'round_gradient_means.npz');need(gm['gradients'].shape==(rounds,pc) and np.isfinite(gm['gradients']).all(),'Gradient diagnostic shape differs')
    g=load(folder/'selected_training_gradient.npz')['gradient'];need(g.shape==(pc,) and np.isfinite(g).all(),'Selected gradient invalid');near(np.linalg.norm(g),r['selected_training_gradient_norm'],CTOL,'Selected gradient norm differs')
    expected={'training':expected_work(method,rounds*4800,True),'validation':expected_work(method,rounds*1600),
              'selected_validation_replay':expected_work(method,1600),'selected_training_gradient_diagnostic':expected_work(method,4800,True)}
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
    near(r['charged_training_seconds'],r['training_seconds']+charge,CTOL,'Charged training time differs')
    need(0<=last_elapsed<=r['training_seconds']<=r['endpoint_total_seconds'],'Timing boundary differs')
    _,after=check_commit(folder);need(after==commit_sha,'Endpoint changed during independent audit')
    disagreement=[dict(item,round=entry['round']) for entry in all_threshold for item in entry['disagreement_records']]
    return {'population':population,'method':method,'seed':seed,'rounds_verified':rounds,'validation_predictions_replayed':rounds*1600,
       'endpoint_commit_sha256':commit_sha,'selected_checkpoint_sha256':sha(folder/'selected_checkpoint.npz'),
       'selected_round':chosen,'selected_validation':r['selected_validation'],
       'maximum_probability_error':float(np.max(abs(probs-independent))),'maximum_independent_aggregate_bce_error':max_bce,
       'maximum_scalar_spotcheck_error':scalar_error,'scalar_spotcheck_records':len(spots)*len(spot_rounds),
       'all_round_canonical_band_records':sum(a['canonical_band_records'] for a in all_threshold),
       'all_round_reference_band_records':sum(a['reference_band_records'] for a in all_threshold),
       'all_round_class_disagreements':len(disagreement),'outside_band_disagreements':0,
       'disagreement_records':disagreement,'selected_threshold_diagnostic':all_threshold[chosen-1],
       'round_numeric_diagnostics':[{k:a[k] for k in ('round','canonical_band_records','reference_band_records','class_disagreements')} for a in all_threshold],
       'paired_sample_order_sha256':sha(folder/'record_orders.npy'),'initial_state_sha256':sha(folder/'initial_state.npz'),
       'operations_verified':True,'all_saved_rounds_independently_replayed':True}

def audit_stage(stage=None,engineering_root=None,lock_path=None):
    started=time.perf_counter();sources={p.name:sha(p) for p in (Path(__file__),HERE/'reference_v04.py')}
    protocol_sha=sha(ROOT/'governance/ANALYSIS_PROTOCOL.json');protocol=read(ROOT/'governance/ANALYSIS_PROTOCOL.json');numeric=protocol['numerical']
    need(numeric['probability_abs_tolerance']==PTOL and numeric['independent_aggregate_bce_abs_tolerance']==BTOL and numeric['canonical_saved_probability_metric_abs_tolerance']==CTOL and numeric['band']==BAND,'Registered numerical thresholds differ')
    seal_path=Q/'data/DATA_SEAL.json';seal_sha=sha(seal_path);seal=read(seal_path);freeze=None;lock=None;lock_sha=None
    engineering=engineering_root is not None
    if engineering:
        base=Path(engineering_root);populations=('engineering_circle','engineering_ellipse');seeds=(9701,);stage='A'
    else:
        need(stage in SEEDS and lock_path is not None,'Official stage/author lock required')
        base=Q/f'stage_{stage}';populations=POPS[stage];seeds=SEEDS[stage];freeze=read(Q/f'STAGE_{stage}_FREEZE.json')
        need(freeze['review_status']=='approved_by_root','Root approval required')
        need(freeze['methods']==list(ref.METHODS) and freeze['populations']==list(populations) and freeze['training_seeds']==list(seeds),'Frozen study inventory differs')
        need(freeze['data_seal_sha256']==seal_sha,'Frozen data seal differs')
        for name,h in freeze['source_hashes'].items():need(sha(Q/name)==h,'Frozen source changed')
        status=read(base/'stage_status.json');need(status['status']=='completed' and status['stage']==stage,'Stage process not completed')
        need(status['expected_endpoints']==status['committed_endpoints']==len(populations)*len(seeds)*9,'Full stage endpoints required')
        need(sorted((x['seed'],x['exit_code']) for x in status['exits'])==[(s,0) for s in seeds],'Stage workers did not all finish successfully')
        lock_sha=sha(lock_path);lock=read(lock_path)
        need(lock['status']=='PASS' and lock['stage']==stage,'Author endpoint lock failed or wrong stage')
        need(lock['engineering'] is False and lock['endpoint_count']==len(populations)*len(seeds)*9,'Author lock endpoint scope differs')
        need(lock['source_hashes']==freeze['source_hashes'] and lock['data_seal_sha256']==seal_sha,'Author lock source/data identities differ')
        need(lock['analysis_protocol_sha256']==sha(ROOT/'governance/ANALYSIS_PROTOCOL.json') and lock['stage_freeze_sha256']==sha(Q/f'STAGE_{stage}_FREEZE.json'),'Author lock protocol/freeze identities differ')
        for name,value in lock['audit_source_hashes'].items():need(sha(Q/name)==value,'Author audit source changed')
        need(len(lock['endpoints'])==len(populations)*len(seeds)*9,'Author endpoint row count differs')
        locked={(a['population'],a['seed'],a['method']):a for a in lock['endpoints']}
        need(set(locked)=={(p,s,m) for p in populations for s in seeds for m in ref.METHODS},'Author endpoint identities differ')
        for seed in seeds:
            need(read(base/f'seed_{seed}_failures.json')==[],'Recorded stage failures require review')
            ordering=read(base/f'seed_{seed}_execution_order.json');si=seeds.index(seed)
            for pi,pop in enumerate(populations):
                shift=(pi*len(seeds)+si)%9;expected=list(ref.METHODS[shift:]+ref.METHODS[:shift])
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
                if not engineering:
                    row=locked[(pop,seed,method)]
                    need(row['endpoint_commit_sha256']==item['endpoint_commit_sha256'],'Author/independent commit identity differs')
                    need(row['rounds']==200 and row['optimizer_updates']==15000 and row['selected_round']==item['selected_round'],'Author horizon/selection differs')
                    need(row['validation_rounds_replayed']==200 and row['validation_record_predictions_replayed']==320000,'Author replay scope differs')
                    metric_check(row['selected_validation'],item['selected_validation'])
                    need(row['files']==read(folder/'endpoint_commit.json')['files'],'Author/committed file identities differ')
                print(json.dumps({'audited':len(results),'population':pop,'seed':seed,'method':method,'rounds':item['rounds_verified']}),flush=True)
    for pop in populations:
        for seed in seeds:
            cells=[r for r in results if r['population']==pop and r['seed']==seed]
            need(len({r['paired_sample_order_sha256'] for r in cells})==1,'Across-arm sample orders differ')
    need(sha(seal_path)==seal_sha and sources=={p.name:sha(p) for p in (Path(__file__),HERE/'reference_v04.py')},'Audit/source seal changed')
    need(sha(ROOT/'governance/ANALYSIS_PROTOCOL.json')==protocol_sha,'Numerical protocol changed during audit')
    if not engineering:
        for name,h in freeze['source_hashes'].items():need(sha(Q/name)==h,'Frozen source changed during audit')
        need(sha(Q/f'STAGE_{stage}_FREEZE.json')==lock['stage_freeze_sha256'],'Stage freeze changed during audit')
    if lock_path is not None:need(sha(lock_path)==lock_sha,'Author lock changed during audit')
    return {'status':'PASS','stage':stage,'engineering':engineering,'created_utc':datetime.now(timezone.utc).isoformat(),
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
