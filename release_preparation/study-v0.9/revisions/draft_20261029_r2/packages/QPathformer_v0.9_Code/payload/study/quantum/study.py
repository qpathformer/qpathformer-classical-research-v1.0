"""Internal v0.9 Plan B trainer. Full fits only after a root hash-bound release.

No test loader, no outcome-dependent stopping, no in-place resume. Interrupted
attempts remain evidence; reviewed same-recipe recovery uses a fresh directory.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,os,platform,shutil,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
THREAD_KEYS=('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')
for _key in THREAD_KEYS:os.environ[_key]='1'
import numpy as np
from models import Model,METHODS,ARM_METHODS,Adam,CLIP,binary_cross_entropy,native_losses,add_work

ROOT=Path(__file__).resolve().parent
GOVERNANCE=ROOT.parent/'governance';MATRIX_PATH=GOVERNANCE/'RUN_MATRIX.json';PROTOCOL_PATH=GOVERNANCE/'STUDY_PLAN.json'
STAGE_MAP={'engineering':'engineering','development':'A','confirmation':'B','A':'A','B':'B'}
SETTINGS={'rounds':200,'updates_per_round':75,'batch_size':64,'optimizer_updates':15000,
 'engineering_rounds':20,'engineering_optimizer_updates':1500,'expert_learning_rate':.01,'extra_learning_rate':.001,
 'adam_betas':[.9,.999],'adam_epsilon':1e-8,'extra_warmup_updates':750,'extra_adam_local_step_at_update751':1,
 'expert_state_at_update751':'retain moments and global step','classification_threshold':.5,'loss_clip':[1e-7,1-1e-7],
 'selection':'minimum full validation common clipped BCE; earliest exact tie','sampling':'PCG64 registered training_order,4800 float64 uniform draws per round,index=floor(N*u),replacement',
 'sampling_budget':'75 minibatches of64 per round for both synthetic and Banknote; a round is not an epoch',
 'training_objective':'stable native Bernoulli mixture or logit BCE; LR2 additionally0.0005*squared2weight_norm,intercept exempt',
 'frozen_cache':'none; train,validation and inference compute input features as used',
 'round_evidence':'float64 parameters,validation p/logits/native BCE,fulltrain p/logits,raw minibatch gradients,uniform RNG draws;uint32 sampledindices; flushbeforeledger',
 'inference':'no timings inside training; exclusive posttraining sessions','test_access':'forbidden'}

def now():return datetime.now(timezone.utc).isoformat()
def require(c,message):
    if not c:raise RuntimeError(message)
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def array_digest(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write_json(path,v,exclusive=False):
    with Path(path).open('x' if exclusive else 'w',encoding='utf-8') as f:
        json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def source_hashes():
    names=['models.py','study.py','circuits.py','reference_v03.py','prepare_data.py','routers.py','tests/test_v09_science.py']
    return {n:digest(ROOT/n) for n in names}

def registered_job(job_id):
    rows=[r for r in read_json(MATRIX_PATH)['runs'] if r['run_id']==job_id]
    require(len(rows)==1,'Unregistered/duplicate job identity');job=rows[0];stage=STAGE_MAP[job['stage']]
    require(job['arm'] in METHODS,'Unregistered arm');rounds=20 if stage=='engineering' else 200
    require(job['rounds']==rounds and job['updates_per_round']==75 and job['updates']==75*rounds and job['batch_size']==64,'Registered budget mismatch')
    require(set(job['paired_streams'])=={'training_order','paired_circuit_core_initialization','mlp_initialization'},'Random stream inventory mismatch')
    for name,s in job['paired_streams'].items():
        require(int.from_bytes(hashlib.sha256(s['namespace'].encode('ascii')).digest()[:16],'little')==int(s['uint128_decimal']),f'Stream mapping changed: {name}')
    return job

def verify_freeze(job,authorization):
    f=read_json(authorization);stage=STAGE_MAP[job['stage']]
    require(f.get('schema')=='qpath-v09-stage-authorization-1' and f.get('review_status')=='approved_by_root' and f.get('stage')==stage,'Wrong root stage approval')
    expected=[r['run_id'] for r in read_json(MATRIX_PATH)['runs'] if STAGE_MAP[r['stage']]==stage]
    require(f.get('run_ids')==expected and job['run_id'] in expected,'Freeze must bind complete stage')
    require(f.get('settings')==SETTINGS,'Frozen training settings changed')
    require(f.get('scientific_source_hashes')==source_hashes(),'Frozen training source changed')
    for key,path in [('data_seal_sha256',ROOT/'data/DATA_SEAL.json'),('matrix_sha256',MATRIX_PATH),('protocol_sha256',PROTOCOL_PATH)]:require(f.get(key)==digest(path),f'Frozen {key} changed')
    return f

def load_population(population,split):
    if split not in ('train','validation'):raise ValueError('Trainer permits train/validation only')
    require(population in {p['population_id'] for p in read_json(MATRIX_PATH)['populations']},'Unregistered population')
    seal=read_json(ROOT/'data/DATA_SEAL.json');path=ROOT/'data'/f'{population}_{split}.npz'
    require(digest(path)==seal['files'][path.name]['sha256'],'Data hash changed')
    policy_path=ROOT/'data'/f'{population}_router.json'
    require(digest(policy_path)==seal['routers'][population]['sha256'],'Policy changed')
    common={'x','y','ids','kmeans_route','margin_bin'}
    with np.load(path,allow_pickle=False) as f:
        fields=set(f.files);require(common.issubset(fields) and fields<=common|{'source_draw_ids','source_row_indices','raw_x','x4'},'Unexpected training fields (latent/test evidence forbidden)')
        pop={k:f[k] for k in f.files}
    n=len(pop['y']);require(n>0 and pop['x'].shape==(n,2) and np.isfinite(pop['x']).all() and np.isin(pop['y'],[0,1]).all(),'Invalid inputs/labels')
    require(len(np.unique(pop['ids']))==n,'Duplicate record IDs')
    import routers
    policy=read_json(policy_path)
    require(np.array_equal(pop['kmeans_route'],routers.route(pop['x'],policy,'kmeans')),'Cached route changed')
    require(np.array_equal(pop['margin_bin'],routers.margin_bins(pop['x'],policy)),'Cached margin bins changed')
    require(n==seal['files'][path.name]['n']==seal['datasets'][population]['counts'][split],'Recorded split count changed')
    if 'raw_x' in pop:
        require(pop['raw_x'].shape==(n,4) and pop['x4'].shape==(n,4),'Invalid real-data dimensions')
        require(np.array_equal(pop['x'],routers.preprocess(pop['raw_x'],policy,dimensions=2)),'PCA pipeline replay changed')
        require(np.array_equal(pop['x4'],routers.preprocess(pop['raw_x'],policy,dimensions=4)),'Four-feature pipeline replay changed')
    return pop

def metrics(y,p):
    y=np.asarray(y);p=np.asarray(p);loss=binary_cross_entropy(y,p);pred=p>=.5
    confusion=[[int(np.sum((y==a)&(pred==b))) for b in (0,1)] for a in (0,1)]
    f=[]
    for k in (0,1):
        tp=confusion[k][k];fp=confusion[1-k][k];fn=confusion[k][1-k];den=2*tp+fp+fn;f.append(2*tp/den if den else 0.)
    edges=np.linspace(0,1,11);bins=np.minimum(np.searchsorted(edges,p,side='right')-1,9);reliability=[];ece=0.
    for k in range(10):
        chosen=bins==k;n=int(chosen.sum());mp=float(p[chosen].mean()) if n else None;my=float(y[chosen].mean()) if n else None
        if n:ece+=n/len(y)*abs(mp-my)
        reliability.append({'bin':k,'lower':float(edges[k]),'upper':float(edges[k+1]),'count':n,'mean_probability':mp,'fraction_positive':my})
    return {'bce':loss,'macro_f1':float(np.mean(f)),'accuracy':float(np.mean(y==pred)),'brier':float(np.mean((p-y)**2)),
            'ece10':float(ece),'reliability10':reliability,'confusion':confusion,'n':len(y),'clipped':int(np.sum((p<CLIP)|(p>1-CLIP)))}

def native_diagnostics(model,y,p,z):
    return {'native_bce':model.loss(y,p,z),'minimum_raw_probability':float(np.min(p)),'maximum_raw_probability':float(np.max(p)),
            'minimum_native_logit':float(np.min(z)),'maximum_native_logit':float(np.max(z)),
            'clipped_wrong_prediction_count':int(np.sum(((p<CLIP)|(p>1-CLIP))&((p>=.5)!=y)))}

def save_checkpoint(path,model,opt,extra_opt,current_round,completed_rounds,p=None,z=None):
    if Path(path).exists():raise FileExistsError(path)
    np.savez(path,parameters=model.parameters,core_parameters=model.core_parameters,adam_m=opt.m,adam_v=opt.v,adam_t=opt.t,
             extra_adam_m=extra_opt.m,extra_adam_v=extra_opt.v,extra_adam_t=extra_opt.t,
             current_round=current_round,completed_rounds=completed_rounds,validation_evidence_present=p is not None,
             validation_probabilities=np.array([]) if p is None else p,validation_logits=np.array([]) if z is None else z)

def train(job_id,output,authorization):
    wall0=time.perf_counter();cpu0=time.process_time();job=registered_job(job_id);stage=STAGE_MAP[job['stage']]
    population=job['population_id'];arm=job['arm'];seed=job['training_seed_id'];rounds=job['rounds'];freeze=verify_freeze(job,authorization)
    output=Path(output)
    if output.exists():raise FileExistsError('Preserve prior attempt; new output required')
    train_pop=load_population(population,'train');valid_pop=load_population(population,'validation')
    policy=read_json(ROOT/'data'/f'{population}_router.json');streams={k:int(v['uint128_decimal']) for k,v in job['paired_streams'].items()}
    model=Model(arm,seed,streams,policy);x=model.input_for(train_pop);vx=model.input_for(valid_pop);y=train_pop['y'];vy=valid_pop['y']
    opt=Adam((model.expert_size,),.01);extra_opt=Adam((model.extra_size,),.001)
    source=source_hashes();data_hash=digest(ROOT/'data/DATA_SEAL.json');auth_hash=digest(authorization);matrix_hash=digest(MATRIX_PATH);protocol_hash=digest(PROTOCOL_PATH)
    output.mkdir(parents=True,exist_ok=False)
    config={'study_id':read_json(PROTOCOL_PATH)['study_id'],'classification':'INTERNAL','job_id':job_id,'arm':arm,'method':arm,'stage':stage,
       'population':population,'seed':seed,'rounds':rounds,'train_records':len(y),'validation_records':len(vy),'batch_size':64,'settings':SETTINGS,
       'source_hashes':source,'data_seal_sha256':data_hash,'authorization_sha256':auth_hash,'stage_freeze_sha256':auth_hash,
       'matrix_sha256':matrix_hash,'protocol_sha256':protocol_hash,'router_policy_sha256':digest(ROOT/'data'/f'{population}_router.json'),
       'paired_streams':job['paired_streams'],'initialization':model.initialization,'parameter_count':len(model.parameters),'test_accessed':False,
       'environment':{'python':sys.version,'executable':sys.executable,'numpy':np.__version__,'platform':platform.platform(),'threads':{k:os.getenv(k) for k in THREAD_KEYS}},'started_utc':now()}
    write_json(output/'config.json',config,True)
    np.savez(output/'initial_state.npz',parameters=model.parameters,master_initial=model.master_initial,core_parameters=model.core_parameters)
    shapes={'round_parameters':((rounds,len(model.parameters)),np.float64),'validation_probabilities':((rounds,len(vy)),np.float64),
      'validation_logits':((rounds,len(vy)),np.float64),'validation_native_losses':((rounds,),np.float64),
      'training_probabilities':((rounds,len(y)),np.float64),'training_logits':((rounds,len(y)),np.float64),
      'sampler_uniforms':((rounds,4800),np.float64),'record_orders':((rounds,4800),np.uint32),
      'minibatch_gradients':((rounds*75,len(model.parameters)),np.float64)}
    arrays={name:np.lib.format.open_memmap(output/(name+'.npy'),mode='w+',dtype=dtype,shape=shape) for name,(shape,dtype) in shapes.items()}
    for a in arrays.values():a[:]=np.nan if a.dtype.kind=='f' else np.iinfo(a.dtype).max;a.flush()
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(streams['training_order'])))
    exposure=np.zeros(len(y),dtype=np.int64);work={};best=float('inf');chosen_round=0;completed_rounds=0;current_round=0
    training0=time.perf_counter();train_cpu0=time.process_time();forward_seconds=0.;forward_cpu=0.;sampler_seconds=0.;sampler_cpu=0.
    try:
        with (output/'rounds.jsonl').open('x',encoding='utf-8') as ledger:
            for r in range(rounds):
                current_round=r+1;ts=time.perf_counter();cs=time.process_time()
                uniforms=rng.random(4800);order=np.floor(len(y)*uniforms).astype(np.uint32)
                arrays['sampler_uniforms'][r]=uniforms;arrays['record_orders'][r]=order;exposure+=np.bincount(order,minlength=len(y))
                sampler_seconds+=time.perf_counter()-ts;sampler_cpu+=time.process_time()-cs
                losses=[];norms=[]
                for b in range(75):
                    ids=order[b*64:(b+1)*64];loss,g,p,w=model.gradient(x[ids],y[ids])
                    require(np.isfinite(loss) and np.isfinite(g).all(),'Nonfinite native objective/gradient')
                    arrays['minibatch_gradients'][opt.t]=g
                    opt.step(model.parameters[:model.expert_size],g[:model.expert_size])
                    if opt.t>750 and model.extra_size:extra_opt.step(model.parameters[model.expert_size:],g[model.expert_size:])
                    losses.append(loss);norms.append(float(np.linalg.norm(g)));add_work(work.setdefault('training',{}),w)
                ts=time.perf_counter();cs=time.process_time();tp,tz=model.predict_with_logits(x);vp,vz=model.predict_with_logits(vx)
                forward_seconds+=time.perf_counter()-ts;forward_cpu+=time.process_time()-cs
                add_work(work.setdefault('full_training_diagnostics',{}),model.accounting(x));add_work(work.setdefault('validation',{}),model.accounting(vx))
                tm=metrics(y,tp);vm=metrics(vy,vp);vnd=native_diagnostics(model,vy,vp,vz)
                arrays['round_parameters'][r]=model.parameters;arrays['validation_probabilities'][r]=vp;arrays['validation_logits'][r]=vz
                arrays['validation_native_losses'][r]=vnd['native_bce'];arrays['training_probabilities'][r]=tp;arrays['training_logits'][r]=tz
                for a in arrays.values():a.flush()
                selected=vm['bce']<best
                if selected:
                    best=vm['bce'];chosen_round=current_round;chosen_path=output/f'selected_round_{current_round:04d}.npz'
                    save_checkpoint(chosen_path,model,opt,extra_opt,current_round,current_round,vp,vz)
                row={'round':current_round,'optimizer_updates':opt.t,'extra_optimizer_updates':extra_opt.t,
                     'training_objective_mean':float(np.mean(losses)),'mean_batch_gradient_norm':float(np.mean(norms)),'maximum_batch_gradient_norm':max(norms),
                     'training_objective_scope':'75 uniformly sampled batches, before each update; LR2 includes penalty',
                     'full_training':tm,'full_training_native':native_diagnostics(model,y,tp,tz),'validation':vm,'validation_native':vnd,'selected':selected,
                     'round_parameter_sha256':array_digest(model.parameters),'validation_probability_sha256':array_digest(vp),'validation_logit_sha256':array_digest(vz),
                     'record_order_sha256':array_digest(order),'uniform_sha256':array_digest(uniforms),
                     'gradient_sha256':array_digest(arrays['minibatch_gradients'][r*75:(r+1)*75]),'training_exposure_sha256':array_digest(exposure),
                     'routing_validation':model.routing_diagnostics(vx),'elapsed_seconds':time.perf_counter()-training0}
                ledger.write(json.dumps(row,allow_nan=False)+'\n');ledger.flush();os.fsync(ledger.fileno());completed_rounds=current_round
                write_json(output/'status.json',{'status':'running','round':current_round,'optimizer_updates':opt.t,'job_id':job_id})
        training_seconds=time.perf_counter()-training0;training_cpu=time.process_time()-train_cpu0
        save_checkpoint(output/'last_checkpoint.npz',model,opt,extra_opt,rounds,rounds,vp,vz)
        shutil.copyfile(chosen_path,output/'selected_checkpoint.npz');np.save(output/'training_record_exposure.npy',exposure,allow_pickle=False)
        model.parameters[:]=arrays['round_parameters'][chosen_round-1];vp,vz=model.predict_with_logits(vx);tp,tz=model.predict_with_logits(x)
        require(np.array_equal(vp,arrays['validation_probabilities'][chosen_round-1]) and np.array_equal(vz,arrays['validation_logits'][chosen_round-1]),'Selected validation replay changed')
        require(opt.t==rounds*75 and extra_opt.t==(max(0,rounds*75-750) if model.extra_size else 0),'Incomplete update horizon')
        require(source_hashes()==source and digest(authorization)==auth_hash and digest(MATRIX_PATH)==matrix_hash and digest(PROTOCOL_PATH)==protocol_hash and digest(ROOT/'data/DATA_SEAL.json')==data_hash,'Bound inputs changed during fit')
        seal=read_json(ROOT/'data/DATA_SEAL.json')
        for split in ('train','validation'):
            pth=ROOT/'data'/f'{population}_{split}.npz';require(digest(pth)==seal['files'][pth.name]['sha256'],'Consumed data changed')
        require(digest(ROOT/'data'/f'{population}_router.json')==config['router_policy_sha256'],'Policy changed during fit')
        with (output/'validation_predictions.csv').open('x',newline='',encoding='utf-8') as f:
            writer=csv.writer(f);writer.writerow(['record_id','label','probability','prediction','native_logit','kmeans_route','margin_bin'])
            writer.writerows(zip(valid_pop['ids'],vy,vp,(vp>=.5).astype(int),vz,valid_pop['kmeans_route'],valid_pop['margin_bin']))
        result={'status':'completed','study_id':config['study_id'],'job_id':job_id,'stage':stage,'population':population,'arm':arm,'method':arm,'seed':seed,
          'completed_rounds':rounds,'optimizer_global_updates':opt.t,'extra_optimizer_updates':extra_opt.t,'selected_round':chosen_round,
          'selected_validation':metrics(vy,vp),'selected_validation_native':native_diagnostics(model,vy,vp,vz),
          'selected_training':metrics(y,tp),'selected_training_native':native_diagnostics(model,y,tp,tz),
          'routing_training':model.routing_diagnostics(x),'routing_validation':model.routing_diagnostics(vx),
          'parameter_count':len(model.parameters),'expert_parameter_count':model.expert_size,'extra_parameter_count':model.extra_size,
          'training_objective':model.training_objective,'full_training_record_visits':rounds*4800,'unique_train_records_exposed':int(np.count_nonzero(exposure)),
          'training_seconds':training_seconds,'training_process_cpu_seconds':training_cpu,'endpoint_total_seconds':time.perf_counter()-wall0,
          'invocation_process_cpu_seconds_through_result':time.process_time()-cpu0,'diagnostic_forward_wall_seconds':forward_seconds,'diagnostic_forward_cpu_seconds':forward_cpu,
          'sampler_wall_seconds':sampler_seconds,'sampler_cpu_seconds':sampler_cpu,'work':work,'timing_performed':False,
          'source_hashes':source,'data_seal_sha256':data_hash,'authorization_sha256':auth_hash,'stage_freeze_sha256':auth_hash,
          'matrix_sha256':matrix_hash,'protocol_sha256':protocol_hash,'test_accessed':False,'finished_utc':now()}
        write_json(output/'result.json',result,True);write_json(output/'status.json',{'status':'completed','round':rounds,'job_id':job_id})
        files={p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}
        commit={'schema':'qpath-v09-endpoint-1','status':'completed','job_id':job_id,'stage':stage,'population':population,'arm':arm,'method':arm,'seed':seed,
          'authorization_sha256':auth_hash,'data_seal_sha256':data_hash,'matrix_sha256':matrix_hash,'protocol_sha256':protocol_hash,
          'completed_rounds':rounds,'optimizer_global_updates':opt.t,'files':files,'committed_utc':now(),'source_hashes':source,'test_accessed':False}
        write_json(output/'endpoint_commit.json',commit,True);return result
    except BaseException as error:
        failure={'status':'failed','job_id':job_id,'current_round':current_round,'completed_rounds':completed_rounds,'completed_optimizer_updates':opt.t,
                 'utc':now(),'error':str(error),'type':type(error).__name__,'traceback':traceback.format_exc(),'recovery':'Preserve; no automatic resume; root-reviewed same-recipe fresh-attempt restart.'}
        save_checkpoint(output/'failed_checkpoint.npz',model,opt,extra_opt,current_round,completed_rounds)
        write_json(output/'failure.json',failure,True);write_json(output/'status.json',failure);raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job-id',required=True);p.add_argument('--authorization',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=train(a.job_id,a.output,a.authorization);print(json.dumps({k:r[k] for k in ('status','method','population','seed','training_seconds')}))
if __name__=='__main__':main()
