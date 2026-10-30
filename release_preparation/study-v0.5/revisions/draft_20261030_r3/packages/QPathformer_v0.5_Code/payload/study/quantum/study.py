"""Internal v0.5 trainer. Official full runs require external root freeze.

Training cannot load a test payload. All round parameters and validation
probabilities are flushed before that round's ledger entry. Failed runs retain
partial arrays and current state; sampler state is not resumable automatically.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time
import traceback
import numpy as np
from models import Model,METHODS,Adam,CLIP,binary_cross_entropy,add_work

ROOT=Path(__file__).resolve().parent
SEEDS={'A':(901,902,903),'B':(1001,1002,1003,1004,1005)}
POPULATIONS={'A':('development_circle','development_ellipse'),
             'B':('confirmation_circle_1','confirmation_circle_2','confirmation_ellipse')}
ENGINEERING=('engineering_circle','engineering_ellipse')
SETTINGS={'rounds':200,'batch_size':64,'training_records':4800,'validation_records':1600,
          'optimizer_updates':15000,'learning_rate':.01,'adam_betas':[.9,.999],'adam_epsilon':1e-8,
          'weight_decay':0.,'loss_clip':[1e-7,1-1e-7],'classification_threshold':.5,
          'selection':'minimum full validation common clipped BCE; earliest exact tie',
          'native_objectives':'legacyq2 retains clippedBornBCE/outsideclipzero; allotherarmsstablelogitBCE/nooutsideclipzero',
          'frozen_cache':'train/validation moments once withfixedrandomcore; serializedfeatures,identity,corehash,cost; uncachedtimedinference',
          'calibration':'rawBrier; binaryprobabilityECE10fixedequalwidthbins,lastincludes1; labelsunusedinprediction',
          'shuffle':'PCG64 SeedSequence([seed,2]); one permutation of training row positions per round',
          'inference_fixture':'lowest 1024 validation IDs; one warmup plus three uncached timed repeats, and separate fifth cached check',
          'round_evidence':'float64 round_parameters,validation_probabilities,validation_native_losses; validation_logits onlynative-logitmodels; uint16 record_orders; flushbeforeledger'}


def now():return datetime.now(timezone.utc).isoformat()
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def array_digest(array):return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()
def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write_json(path,value,exclusive=False):
    with Path(path).open('x' if exclusive else 'w',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def require(condition,message):
    if not condition:raise RuntimeError(message)


def source_hashes():
    names=['models.py','study.py','circuits.py','reference_v03.py','prepare_data.py','routers.py','launch_stage.py']
    files=[ROOT/n for n in names]+sorted((ROOT/'tests').glob('test*.py'))
    return {p.relative_to(ROOT).as_posix():digest(p) for p in files}


def load_population(population,split):
    if split not in ('train','validation'):raise ValueError('Training loader allows train/validation only')
    if population not in (*ENGINEERING,*POPULATIONS['A'],*POPULATIONS['B']):raise ValueError('Unregistered population')
    seal=read_json(ROOT/'data/DATA_SEAL.json'); path=ROOT/'data'/f'{population}_{split}.npz'
    require(digest(path)==seal['files'][path.name]['sha256'],'Data payload changed')
    require(digest(ROOT/'data'/f'{population}_router.json')==seal['routers'][population]['sha256'],'Router changed')
    with np.load(path,allow_pickle=False) as f:pop={k:f[k] for k in f.files}
    n=len(pop['y']);require(pop['x'].shape==(n,2),'Bad coordinate shape')
    require(np.isin(pop['y'],[0,1]).all(),'Nonbinary labels')
    return pop


def metrics(y,p):
    y=np.asarray(y);p=np.asarray(p);loss=binary_cross_entropy(y,p);pred=p>=.5
    confusion=[[int(np.sum((y==a)&(pred==b))) for b in (0,1)] for a in (0,1)]
    f=[]
    for k in (0,1):
        tp=confusion[k][k];fp=confusion[1-k][k];fn=confusion[k][1-k];den=2*tp+fp+fn
        f.append(2*tp/den if den else 0.)
    edges=np.linspace(0,1,11);bins=np.minimum(np.searchsorted(edges,p,side='right')-1,9);reliability=[];ece=0.
    for k in range(10):
        chosen=bins==k;n=int(np.sum(chosen));mp=float(np.mean(p[chosen])) if n else None;my=float(np.mean(y[chosen])) if n else None
        if n:ece+=n/len(y)*abs(mp-my)
        reliability.append({'bin':k,'lower':float(edges[k]),'upper':float(edges[k+1]),'count':n,'mean_probability':mp,'fraction_positive':my})
    return {'bce':loss,'macro_f1':float(np.mean(f)),'accuracy':float(np.mean(y==pred)),
            'brier':float(np.mean((p-y)**2)),'ece10':float(ece),'reliability10':reliability,
            'confusion':confusion,'n':len(y),'clipped':int(np.sum((p<CLIP)|(p>1-CLIP)))}


def native_diagnostics(model,y,p,z):
    return {'native_bce':model.loss(y,p,z),'has_native_logits':z is not None,
            'minimum_raw_probability':float(np.min(p)),'maximum_raw_probability':float(np.max(p)),
            'minimum_native_logit':None if z is None else float(np.min(z)),
            'maximum_native_logit':None if z is None else float(np.max(z)),
            'clipped_wrong_prediction_count':int(np.sum(((p<CLIP)|(p>1-CLIP))&((p>=.5)!=y)))}


def verify_freeze(stage,population,seed,method):
    require(stage in SEEDS and population in POPULATIONS[stage],'Unregistered stage/population')
    require(seed in SEEDS[stage] and method in METHODS,'Unregistered seed/method')
    path=ROOT/f'STAGE_{stage}_FREEZE.json';require(path.is_file(),'Root approval required before official training')
    f=read_json(path);require(f.get('review_status')=='approved_by_root','Root approval missing')
    require(f.get('methods')==list(METHODS) and f.get('populations')==list(POPULATIONS[stage]),'Freeze arm/population mismatch')
    require(f.get('training_seeds')==list(SEEDS[stage]) and f.get('settings')==SETTINGS,'Freeze settings/seeds mismatch')
    require(f.get('source_hashes')==source_hashes(),'Frozen training source changed')
    require(f.get('data_seal_sha256')==digest(ROOT/'data/DATA_SEAL.json'),'Data seal changed')
    return f


def save_checkpoint(path,model,opt,current_round,completed_rounds,validation_p=None,validation_z=None,native_loss=None):
    if Path(path).exists():raise FileExistsError(path)
    np.savez(path,parameters=model.parameters,core_parameters=model.core_parameters,
             adam_m=opt.m,adam_v=opt.v,adam_t=opt.t,current_round=current_round,completed_rounds=completed_rounds,
             validation_evidence_present=validation_p is not None,
             validation_probabilities=np.array([]) if validation_p is None else validation_p,
             has_native_logits=model.native_logits,
             validation_logits=np.array([]) if validation_z is None else validation_z,
             validation_native_loss=np.array([]) if native_loss is None else np.array([native_loss]))


def save_predictions(path,pop,p,z=None):
    with Path(path).open('x',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['record_id','hash_route','kmeans_route','label','probability','prediction','native_logit'])
        w.writerows(zip(pop['ids'],pop['hash_route'],pop['kmeans_route'],pop['y'],p,(p>=.5).astype(int),['']*len(p) if z is None else z))


def prepare_frozen_cache(model,training,validation,output):
    if not model.frozen:return None,None,{'enabled':False,'seconds':0.,'bytes':0,'work':{}}
    arrays=[];records={};work={};start=time.perf_counter()
    for name,pop in (('train',training),('validation',validation)):
        t=time.perf_counter();a=model.cache_features(pop['x'],model.route_for(pop));elapsed=time.perf_counter()-t
        path=output/f'frozen_{name}_moments.npy';np.save(path,a,allow_pickle=False)
        records[name]={'file':path.name,'file_sha256':digest(path),'array_sha256':array_digest(a),
                       'shape':list(a.shape),'bytes':a.nbytes,'file_bytes':path.stat().st_size,'compute_seconds':elapsed,
                       'ids_sha256':array_digest(pop['ids']),'route_sha256':array_digest(model.route_for(pop)),
                       'input_sha256':array_digest(pop['x'])}
        work[name]=model.cache_accounting(pop['x'],model.route_for(pop));a.setflags(write=False);arrays.append(a)
    meta={'enabled':True,'seconds':time.perf_counter()-start,'bytes':sum(a.nbytes for a in arrays),
          'core_sha256':array_digest(model.core_parameters),'records':records,'work':work,
          'scope':'Fixedrandomcore andfrozenrouter; labelindependent features computedonce. CachecreationandI/Ocharged. Timedinference doesnotusethiscache.'}
    write_json(output/'frozen_cache.json',meta,True)
    return arrays[0],arrays[1],meta


def inference_diagnostic(model,validation,population):
    import routers
    indices=np.argsort(validation['ids'],kind='stable')[:1024]
    pop={k:v[indices] for k,v in validation.items()};policy=read_json(ROOT/'data'/f'{population}_router.json')
    def forward():
        start=time.perf_counter();route=None if model.routing=='global' else routers.route(pop['x'],policy,kind=model.routing)
        middle=time.perf_counter();p=model.predict(pop['x'],route)
        return time.perf_counter()-start,middle-start if route is not None else 0.,p
    warmup=forward();runs=[forward() for _ in range(3)];cached=model.predict_population(pop)
    difference=max(float(np.max(abs(v[2]-cached))) for v in (warmup,*runs))
    require(difference<=2e-12,'Uncached route forward differs from cached route')
    work={}
    for _ in range(4):add_work(work,model.accounting(pop['x'],model.route_for(pop)))
    return {'population':'validation only; smallest IDs; labels unused','records':len(indices),
            'record_ids':pop['ids'].tolist(),'warmups':1,'timed_repeats':3,
            'total_repeat_seconds':[v[0] for v in runs],'route_repeat_seconds':[v[1] for v in runs],
            'mean_seconds_per_record':float(np.mean([v[0] for v in runs])/len(indices)),
            'maximum_cached_difference':difference,'work_four_uncached_forwards':work,
            'work_fifth_cached_comparison':model.accounting(pop['x'],model.route_for(pop)),
            'scope':'Loaded raw coordinates; uncached route plus forward. Excludes I/O, fit, model loading. Concurrent CPU timing, not isolated hardware efficiency. Fifth comparison is charged separately; its time not isolated.'}


def train(method,seed,stage,population,output,rounds=200,limit=None,engineering=False):
    output=Path(output)
    if output.exists():raise FileExistsError('Preserve previous output; no in-place restart')
    if engineering:
        require(population in ENGINEERING,'Engineering may only use engineering populations')
    else:
        verify_freeze(stage,population,seed,method)
        require(rounds==200 and limit is None,'Official full horizon required')
    require(rounds>=1 and (limit is None or limit>=64),'Invalid budget')
    training=load_population(population,'train');validation=load_population(population,'validation')
    if not engineering:require(len(training['y'])==4800 and len(validation['y'])==1600,'Official split counts changed')
    if limit is not None:
        training={k:v[:limit] for k,v in training.items()};validation={k:v[:160] for k,v in validation.items()}
    model=Model(method,seed);opt=Adam(model.parameters.shape);source=source_hashes()
    seal=read_json(ROOT/'data/DATA_SEAL.json');cost=seal['datasets'][population];kind=model.routing
    prep={'generation_seconds_charged':cost['generation_seconds'],
          'joint_router_fit_seconds_charged':cost['router_fit_seconds'] if kind!='global' else 0.,
          'train_validation_cache_seconds_charged':sum(cost['route_application_seconds_by_split'][part][kind] for part in ('train','validation')) if kind!='global' else 0.,
          'scope':'Population preparation executed once; repeats are accounting charges, not extra project wall time. All routed arms charge the common joint fit. Test route application excluded.'}
    output.mkdir(parents=True,exist_ok=False)
    config={'study_id':'QPATH-READOUT-v0.5','classification':'INTERNAL','stage':stage,'population':population,'method':method,
            'seed':seed,'engineering':engineering,'rounds':rounds,'train_records':len(training['y']),
            'validation_records':len(validation['y']),'batch_size':64,'settings':SETTINGS,'source_hashes':source,
            'data_seal_sha256':digest(ROOT/'data/DATA_SEAL.json'),'router_policy_sha256':digest(ROOT/'data'/f'{population}_router.json'),
            'stage_freeze_sha256':None if engineering else digest(ROOT/f'STAGE_{stage}_FREEZE.json'),
            'initialization':model.initialization,'training_objective':model.training_objective,
            'parameter_count':len(model.parameters),'fixed_core_parameter_count':model.core_parameters.size,
            'has_native_logits':model.native_logits,'preparation':prep,'test_accessed':False,'started_utc':now(),
            'environment':{'python':sys.version,'executable':sys.executable,'numpy':np.__version__,'platform':platform.platform(),
                           'threads':{key:os.getenv(key) for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}}}
    write_json(output/'config.json',config,True)
    np.savez(output/'initial_state.npz',parameters=model.parameters,master_initial=model.master_initial,core_parameters=model.core_parameters)
    shape=(rounds,len(model.parameters));states=np.lib.format.open_memmap(output/'round_parameters.npy',mode='w+',dtype=np.float64,shape=shape)
    probabilities=np.lib.format.open_memmap(output/'validation_probabilities.npy',mode='w+',dtype=np.float64,shape=(rounds,len(validation['y'])))
    native_losses=np.lib.format.open_memmap(output/'validation_native_losses.npy',mode='w+',dtype=np.float64,shape=(rounds,))
    logits=(np.lib.format.open_memmap(output/'validation_logits.npy',mode='w+',dtype=np.float64,shape=probabilities.shape)
            if model.native_logits else None)
    orders=np.lib.format.open_memmap(output/'record_orders.npy',mode='w+',dtype=np.uint16,shape=(rounds,len(training['y'])))
    states[:]=np.nan;probabilities[:]=np.nan;native_losses[:]=np.nan;orders[:]=np.iinfo(np.uint16).max
    arrays=[states,probabilities,native_losses,orders]
    if logits is not None:logits[:]=np.nan;arrays.append(logits)
    for arr in arrays:arr.flush()
    np.savez(output/'population_identity.npz',train_ids=training['ids'],validation_ids=validation['ids'])
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
    route=model.route_for(training);work={'training':{},'validation':{}};visits=np.zeros(model.banks,dtype=np.int64)
    total_clips=0;total_wrong_clips=0;gradient_means=[];best=float('inf');chosen_round=None;chosen_path=None
    fixed_core_hash=array_digest(model.core_parameters)
    current_round=0;completed_rounds=0;endpoint_start=time.perf_counter()
    try:
        train_features,validation_features,cache=prepare_frozen_cache(model,training,validation,output)
        work['fixed_feature_preparation']=cache['work'];start=time.perf_counter()
        with (output/'ledger.jsonl').open('x',encoding='utf-8') as ledger:
            for current_round in range(1,rounds+1):
                order=rng.permutation(len(training['y']));orders[current_round-1]=order
                loss_sum=0.;common_loss_sum=0.;norm_sum=0.;norm_max=0.;g_sum=np.zeros_like(model.parameters);batches=0;clips=0;wrong_clips=0
                group_sum={'core':0.,'head':0.};group_max={'core':0.,'head':0.}
                extrema={'minimum_raw_probability':None,'maximum_raw_probability':None,
                         'minimum_native_logit':None,'maximum_native_logit':None}
                for offset in range(0,len(order),64):
                    ids=order[offset:offset+64];batch_route=None if route is None else route[ids]
                    loss,g,p,w=model.gradient(training['x'][ids],training['y'][ids],batch_route,
                                              None if train_features is None else train_features[ids])
                    require(np.isfinite(loss) and np.isfinite(g).all(),'Nonfinite training loss/gradient')
                    for key,value in model.last_gradient_diagnostics.items():
                        if value is not None:extrema[key]=value if extrema[key] is None else (min(extrema[key],value) if key.startswith('minimum') else max(extrema[key],value))
                    norm=float(np.linalg.norm(g));norm_sum+=norm;norm_max=max(norm_max,norm);g_sum+=g;batches+=1
                    for group,mask in (('core',model.core_mask),('head',model.head_mask)):
                        value=float(np.linalg.norm(g[mask]));group_sum[group]+=value;group_max[group]=max(group_max[group],value)
                    opt.step(model.parameters,g);loss_sum+=len(ids)*loss
                    common_loss_sum+=len(ids)*binary_cross_entropy(training['y'][ids],p)
                    clipped=(p<CLIP)|(p>1-CLIP);clips+=int(np.sum(clipped))
                    wrong_clips+=int(np.sum(clipped&((p>=.5)!=training['y'][ids])))
                    add_work(work['training'],w)
                    for ix,bank,sl in model.components(training['x'][ids],batch_route):visits[bank]+=len(ix)
                total_clips+=clips;total_wrong_clips+=wrong_clips;gradient_means.append(g_sum/batches)
                p,z=model.predict_with_logits(validation['x'],model.route_for(validation),validation_features)
                vm=metrics(validation['y'],p);nd=native_diagnostics(model,validation['y'],p,z)
                add_work(work['validation'],model.accounting(validation['x'],model.route_for(validation),cached_features=model.frozen))
                states[current_round-1]=model.parameters;probabilities[current_round-1]=p;native_losses[current_round-1]=nd['native_bce']
                if logits is not None:logits[current_round-1]=z
                for arr in arrays:arr.flush()
                chosen=vm['bce']<best
                if chosen:
                    best=vm['bce'];chosen_round=current_round;chosen_path=output/f'selected_round_{current_round:04d}.npz'
                    save_checkpoint(chosen_path,model,opt,current_round,current_round,p,z,nd['native_bce'])
                row={'round':current_round,'optimizer_updates':opt.t,'training_loss':loss_sum/len(order),
                     'training_common_clipped_bce':common_loss_sum/len(order),'validation':vm,'validation_native':nd,'selected':chosen,
                     'training_forward_extrema':extrema,
                     'round_parameter_sha256':array_digest(states[current_round-1]),
                     'validation_probability_sha256':array_digest(probabilities[current_round-1]),
                     'validation_native_loss_sha256':array_digest(native_losses[current_round-1:current_round]),
                     'validation_logit_sha256':None if logits is None else array_digest(logits[current_round-1]),
                     'record_order_sha256':array_digest(orders[current_round-1]),'mean_batch_gradient_norm':norm_sum/batches,
                     'maximum_batch_gradient_norm':norm_max,'mean_batch_gradient_group_norms':{k:v/batches for k,v in group_sum.items()},
                     'maximum_batch_gradient_group_norms':group_max,'training_clipped_probabilities':clips,
                     'training_clipped_wrong_probabilities':wrong_clips,
                     'legacy_outside_clip_zero_derivative_visits':clips if model.legacy else 0,
                     'bank_record_visits_cumulative':visits.tolist(),'work_cumulative':work,'elapsed_seconds':time.perf_counter()-start}
                ledger.write(json.dumps(row,allow_nan=False)+'\n');ledger.flush();completed_rounds=current_round
                write_json(output/'status.json',{'status':'running','round':current_round,'seed':seed,'method':method,'population':population})
        training_seconds=time.perf_counter()-start
        save_checkpoint(output/'last_checkpoint.npz',model,opt,rounds,rounds,p,z,nd['native_bce'])
        shutil.copyfile(chosen_path,output/'selected_checkpoint.npz')
        np.savez(output/'round_gradient_means.npz',gradients=np.asarray(gradient_means))
        model.parameters[:]=states[chosen_round-1];p,z=model.predict_with_logits(validation['x'],model.route_for(validation),validation_features)
        require(np.array_equal(p,np.asarray(probabilities[chosen_round-1])),'Selected checkpoint replay changed probabilities')
        if logits is not None:require(np.array_equal(z,np.asarray(logits[chosen_round-1])),'Selected checkpoint replay changed logits')
        require(model.loss(validation['y'],p,z)==native_losses[chosen_round-1],'Selected native loss changed')
        save_predictions(output/'validation_predictions.csv',validation,p,z)
        work['selected_validation_replay']=model.accounting(validation['x'],model.route_for(validation),cached_features=model.frozen)
        inference=inference_diagnostic(model,validation,population)
        # Fixed, training-only local gradient diagnostic. It never changes selection.
        loss,g,p_train,dwork=model.gradient(training['x'],training['y'],route,train_features)
        np.savez(output/'selected_training_gradient.npz',gradient=g)
        work['selected_training_gradient_diagnostic']=dwork
        train_bank_counts=np.bincount(route,minlength=5).tolist() if route is not None else [len(training['y'])]
        validation_by_route={kind:{str(k):metrics(validation['y'][validation[kind+'_route']==k],p[validation[kind+'_route']==k])
                                  for k in range(5) if np.any(validation[kind+'_route']==k)} for kind in ('hash','kmeans')}
        require(source_hashes()==source,'Training sources changed during run')
        require(digest(ROOT/'data/DATA_SEAL.json')==config['data_seal_sha256'],'Data seal changed during run')
        require(array_digest(model.core_parameters)==fixed_core_hash,'Frozen core changed')
        if model.frozen:
            for record in cache['records'].values():require(digest(output/record['file'])==record['file_sha256'],'Frozen feature cache changed')
        result={'status':'completed','study_id':config['study_id'],'method':method,'seed':seed,'stage':stage,'population':population,
                'engineering':engineering,'completed_rounds':rounds,'optimizer_global_updates':opt.t,'selected_round':chosen_round,
                'selected_validation':metrics(validation['y'],p),'selected_training':metrics(training['y'],p_train),
                'selected_validation_native':native_diagnostics(model,validation['y'],p,z),
                'selected_training_native_bce':loss,'training_objective':model.training_objective,
                'selected_training_forward_extrema':model.last_gradient_diagnostics,
                'selected_training_gradient_norm':float(np.linalg.norm(g)),'parameter_count':len(model.parameters),
                'selected_training_gradient_group_norms':{'core':float(np.linalg.norm(g[model.core_mask])),'head':float(np.linalg.norm(g[model.head_mask]))},
                'fixed_core_parameter_count':model.core_parameters.size,'stored_model_parameter_count':len(model.parameters)+model.core_parameters.size,
                'has_native_logits':model.native_logits,'frozen_cache':cache,'fixed_core_sha256':fixed_core_hash,
                'bank_count':model.banks,'parameters_per_bank':model.bank_width,'validation_by_route':validation_by_route,
                'train_bank_counts':train_bank_counts,'bank_training_record_visits':visits.tolist(),
                'validation_route_counts':{k:np.bincount(validation[k+'_route'],minlength=5).tolist() for k in ('hash','kmeans')},
                'training_seconds':training_seconds,'endpoint_total_seconds':time.perf_counter()-endpoint_start,
                'charged_training_seconds':training_seconds+cache['seconds']+sum(prep[k] for k in ('generation_seconds_charged','joint_router_fit_seconds_charged','train_validation_cache_seconds_charged')),
                'preparation':prep,'work':work,'inference':inference,'training_clipped_probabilities':total_clips,
                'training_clipped_wrong_probabilities':total_wrong_clips,'legacy_outside_clip_zero_derivative_visits':total_clips if model.legacy else 0,
                'data_seal_sha256':config['data_seal_sha256'],'stage_freeze_sha256':config['stage_freeze_sha256'],
                'test_accessed':False,'finished_utc':now()}
        write_json(output/'result.json',result,True)
        write_json(output/'status.json',{'status':'completed','round':rounds,'seed':seed,'method':method,'population':population})
        payloads={p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}
        write_json(output/'endpoint_commit.json',{'status':'completed','population':population,'method':method,'seed':seed,
                    'files':payloads,'committed_utc':now(),'source_hashes':source,'test_accessed':False},True)
        return result
    except BaseException as error:
        failure={'status':'failed','method':method,'seed':seed,'population':population,'utc':now(),
                 'current_round':current_round,'completed_rounds':completed_rounds,'completed_optimizer_updates':opt.t,
                 'error':str(error),'type':type(error).__name__,'traceback':traceback.format_exc(),
                 'recovery':'No automatic resume; preserve partial arrays/checkpoint and require reviewed fresh-output restart.'}
        save_checkpoint(output/'failed_checkpoint.npz',model,opt,current_round,completed_rounds)
        write_json(output/'failure.json',failure,True);write_json(output/'status.json',failure);raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=SEEDS,default='A');parser.add_argument('--population',required=True)
    parser.add_argument('--method',choices=METHODS,required=True);parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--engineering',action='store_true');parser.add_argument('--rounds',type=int,default=200)
    parser.add_argument('--train-limit',type=int);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();r=train(a.method,a.seed,a.stage,a.population,a.output,a.rounds,a.train_limit,a.engineering)
    print(json.dumps({k:r[k] for k in ('status','method','population','seed','training_seconds')}))


if __name__=='__main__':main()
