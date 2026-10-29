"""Internal v0.4 trainer. Official full runs require external root freeze.

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
SEEDS={'A':(701,702,703),'B':(801,802,803,804,805)}
POPULATIONS={'A':('development_circle','development_ellipse'),
             'B':('confirmation_circle_1','confirmation_circle_2','confirmation_ellipse')}
ENGINEERING=('engineering_circle','engineering_ellipse')
SETTINGS={'rounds':200,'batch_size':64,'training_records':4800,'validation_records':1600,
          'optimizer_updates':15000,'learning_rate':.01,'adam_betas':[.9,.999],'adam_epsilon':1e-8,
          'weight_decay':0.,'loss_clip':[1e-7,1-1e-7],'classification_threshold':.5,
          'selection':'minimum full validation BCE; earliest exact tie',
          'shuffle':'PCG64 SeedSequence([seed,2]); one permutation of training row positions per round',
          'inference_fixture':'lowest 1024 validation IDs; one warmup plus three uncached timed repeats, and separate fifth cached check',
          'round_evidence':'float64 round_parameters.npy and validation_probabilities.npy, uint16 record_orders.npy, flushed before ledger'}


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
    return {'bce':loss,'macro_f1':float(np.mean(f)),'accuracy':float(np.mean(y==pred)),
            'confusion':confusion,'n':len(y),'clipped':int(np.sum((p<CLIP)|(p>1-CLIP)))}


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


def save_checkpoint(path,model,opt,current_round,completed_rounds):
    if Path(path).exists():raise FileExistsError(path)
    np.savez(path,parameters=model.parameters,adam_m=opt.m,adam_v=opt.v,adam_t=opt.t,
             current_round=current_round,completed_rounds=completed_rounds)


def save_predictions(path,pop,p):
    with Path(path).open('x',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['record_id','hash_route','kmeans_route','label','probability','prediction'])
        w.writerows(zip(pop['ids'],pop['hash_route'],pop['kmeans_route'],pop['y'],p,(p>=.5).astype(int)))


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
          'scope':'Population preparation executed once; repeats are accounting charges, not extra project wall time. Both routed arms charge the common joint fit. Test route application excluded.'}
    output.mkdir(parents=True,exist_ok=False)
    config={'study_id':'QPATH-ROUTING-v0.4','classification':'INTERNAL','stage':stage,'population':population,'method':method,
            'seed':seed,'engineering':engineering,'rounds':rounds,'train_records':len(training['y']),
            'validation_records':len(validation['y']),'batch_size':64,'settings':SETTINGS,'source_hashes':source,
            'data_seal_sha256':digest(ROOT/'data/DATA_SEAL.json'),'router_policy_sha256':digest(ROOT/'data'/f'{population}_router.json'),
            'stage_freeze_sha256':None if engineering else digest(ROOT/f'STAGE_{stage}_FREEZE.json'),
            'initialization':model.initialization,'preparation':prep,'test_accessed':False,'started_utc':now(),
            'environment':{'python':sys.version,'executable':sys.executable,'numpy':np.__version__,'platform':platform.platform(),
                           'threads':{key:os.getenv(key) for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}}}
    write_json(output/'config.json',config,True)
    np.savez(output/'initial_state.npz',parameters=model.parameters,master_initial=model.master_initial)
    shape=(rounds,len(model.parameters));states=np.lib.format.open_memmap(output/'round_parameters.npy',mode='w+',dtype=np.float64,shape=shape)
    probabilities=np.lib.format.open_memmap(output/'validation_probabilities.npy',mode='w+',dtype=np.float64,shape=(rounds,len(validation['y'])))
    orders=np.lib.format.open_memmap(output/'record_orders.npy',mode='w+',dtype=np.uint16,shape=(rounds,len(training['y'])))
    states[:]=np.nan;probabilities[:]=np.nan;orders[:]=np.iinfo(np.uint16).max
    for arr in (states,probabilities,orders):arr.flush()
    np.savez(output/'population_identity.npz',train_ids=training['ids'],validation_ids=validation['ids'])
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
    route=model.route_for(training);work={'training':{},'validation':{}};visits=np.zeros(model.banks,dtype=np.int64)
    total_clips=0;gradient_means=[];best=float('inf');chosen_round=None;chosen_path=None
    current_round=0;completed_rounds=0;start=time.perf_counter()
    try:
        with (output/'ledger.jsonl').open('x',encoding='utf-8') as ledger:
            for current_round in range(1,rounds+1):
                order=rng.permutation(len(training['y']));orders[current_round-1]=order
                loss_sum=0.;norm_sum=0.;norm_max=0.;g_sum=np.zeros_like(model.parameters);batches=0;clips=0
                for offset in range(0,len(order),64):
                    ids=order[offset:offset+64];batch_route=None if route is None else route[ids]
                    loss,g,p,w=model.gradient(training['x'][ids],training['y'][ids],batch_route)
                    require(np.isfinite(loss) and np.isfinite(g).all(),'Nonfinite training loss/gradient')
                    norm=float(np.linalg.norm(g));norm_sum+=norm;norm_max=max(norm_max,norm);g_sum+=g;batches+=1
                    opt.step(model.parameters,g);loss_sum+=len(ids)*loss;clips+=int(np.sum((p<CLIP)|(p>1-CLIP)))
                    add_work(work['training'],w)
                    for ix,bank,sl in model.components(training['x'][ids],batch_route):visits[bank]+=len(ix)
                total_clips+=clips;gradient_means.append(g_sum/batches)
                p=model.predict_population(validation);vm=metrics(validation['y'],p)
                add_work(work['validation'],model.accounting(validation['x'],model.route_for(validation)))
                states[current_round-1]=model.parameters;probabilities[current_round-1]=p
                for arr in (states,probabilities,orders):arr.flush()
                chosen=vm['bce']<best
                if chosen:
                    best=vm['bce'];chosen_round=current_round;chosen_path=output/f'selected_round_{current_round:04d}.npz'
                    save_checkpoint(chosen_path,model,opt,current_round,current_round)
                row={'round':current_round,'optimizer_updates':opt.t,'training_loss':loss_sum/len(order),'validation':vm,'selected':chosen,
                     'round_parameter_sha256':array_digest(states[current_round-1]),
                     'validation_probability_sha256':array_digest(probabilities[current_round-1]),
                     'record_order_sha256':array_digest(orders[current_round-1]),'mean_batch_gradient_norm':norm_sum/batches,
                     'maximum_batch_gradient_norm':norm_max,'training_clipped_probabilities':clips,
                     'bank_record_visits_cumulative':visits.tolist(),'work_cumulative':work,'elapsed_seconds':time.perf_counter()-start}
                ledger.write(json.dumps(row,allow_nan=False)+'\n');ledger.flush();completed_rounds=current_round
                write_json(output/'status.json',{'status':'running','round':current_round,'seed':seed,'method':method,'population':population})
        training_seconds=time.perf_counter()-start
        save_checkpoint(output/'last_checkpoint.npz',model,opt,rounds,rounds)
        shutil.copyfile(chosen_path,output/'selected_checkpoint.npz')
        np.savez(output/'round_gradient_means.npz',gradients=np.asarray(gradient_means))
        model.parameters[:]=states[chosen_round-1];p=model.predict_population(validation)
        require(np.array_equal(p,np.asarray(probabilities[chosen_round-1])),'Selected checkpoint replay changed probabilities')
        save_predictions(output/'validation_predictions.csv',validation,p)
        work['selected_validation_replay']=model.accounting(validation['x'],model.route_for(validation))
        inference=inference_diagnostic(model,validation,population)
        # Fixed, training-only local gradient diagnostic. It never changes selection.
        loss,g,p_train,dwork=model.gradient(training['x'],training['y'],route)
        np.savez(output/'selected_training_gradient.npz',gradient=g)
        work['selected_training_gradient_diagnostic']=dwork
        train_bank_counts=np.bincount(route,minlength=5).tolist() if route is not None else [len(training['y'])]
        validation_by_route={kind:{str(k):metrics(validation['y'][validation[kind+'_route']==k],p[validation[kind+'_route']==k])
                                  for k in range(5) if np.any(validation[kind+'_route']==k)} for kind in ('hash','kmeans')}
        require(source_hashes()==source,'Training sources changed during run')
        require(digest(ROOT/'data/DATA_SEAL.json')==config['data_seal_sha256'],'Data seal changed during run')
        result={'status':'completed','study_id':config['study_id'],'method':method,'seed':seed,'stage':stage,'population':population,
                'engineering':engineering,'completed_rounds':rounds,'optimizer_global_updates':opt.t,'selected_round':chosen_round,
                'selected_validation':metrics(validation['y'],p),'selected_training':metrics(training['y'],p_train),
                'selected_training_gradient_norm':float(np.linalg.norm(g)),'parameter_count':len(model.parameters),
                'bank_count':model.banks,'parameters_per_bank':model.bank_width,'validation_by_route':validation_by_route,
                'train_bank_counts':train_bank_counts,'bank_training_record_visits':visits.tolist(),
                'validation_route_counts':{k:np.bincount(validation[k+'_route'],minlength=5).tolist() for k in ('hash','kmeans')},
                'training_seconds':training_seconds,'endpoint_total_seconds':time.perf_counter()-start,
                'charged_training_seconds':training_seconds+sum(prep[k] for k in ('generation_seconds_charged','joint_router_fit_seconds_charged','train_validation_cache_seconds_charged')),
                'preparation':prep,'work':work,'inference':inference,'training_clipped_probabilities':total_clips,
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
