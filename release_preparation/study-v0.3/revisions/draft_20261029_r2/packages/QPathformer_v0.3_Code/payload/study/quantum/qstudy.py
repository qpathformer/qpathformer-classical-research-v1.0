"""Internal v0.3 mechanism study. Official runs require external source/data freeze.

No network or hardware. Training loaders cannot open tests. Failures are retained;
checkpoint files do not make interrupted training resumable (no sampler RNG).
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

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
import numpy as np
from qpath import quantum
import circuits
import reference_v03

METHODS=('scheduled','min_depth2','untied_assigned','fixed1','fixed2','fixed4',
         'encoding1','readout1','hash40','kmeans40','ensemble40','mlp41','mlp129')
OFFSETS=(0,4,12,24,40)
FIVE_BANK=('hash40','kmeans40','ensemble40')
SEEDS={'A':(501,502,503),'B':(601,602,603,604,605)}
SETTINGS={'rounds':200,'batch_size':64,'training_records':4800,'optimizer_updates':15000,
          'learning_rate':.01,'selection':'minimum full validation BCE; earliest exact tie',
          'adam_betas':[.9,.999],'adam_epsilon':1e-8,'weight_decay':0.,
          'loss_clip':[1e-7,1-1e-7],'classification_threshold':.5,
          'inference_fixture':'lowest 1024 validation record IDs; one warmup, three timed repeats; uncached routes'}


def now(): return datetime.now(timezone.utc).isoformat()
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def source_hashes():
    files=[ROOT/n for n in ('qstudy.py','circuits.py','reference_v03.py','prepare_data.py','routers.py','launch_stage.py')]
    files+=sorted((ROOT/'vendor/qpath').glob('*.py'))
    files+=sorted((ROOT/'tests').glob('test*.py'))
    return {str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files}


def load_population(dataset,split):
    if split not in ('train','validation'): raise ValueError('Training can load only train/validation')
    path=ROOT/'data'/f'{dataset}_{split}.npz'
    seal=read_json(ROOT/'data/DATA_SEAL.json')
    if digest(path)!=seal['files'][path.name]['sha256']: raise ValueError('Data hash mismatch')
    if digest(ROOT/'data'/f'{dataset}_router.json')!=seal['routers'][dataset]['sha256']:raise ValueError('Router policy hash mismatch')
    with np.load(path,allow_pickle=False) as data: return {k:data[k] for k in data.files}


def metrics(y,p):
    y,p=np.asarray(y),np.asarray(p)
    if len(y)==0 or not np.isfinite(p).all(): raise ValueError('Invalid metric population/probabilities')
    pred=p>=.5; f=[]
    for label in (0,1):
        tp=np.sum((y==label)&(pred==label));fp=np.sum((y!=label)&(pred==label));fn=np.sum((y==label)&(pred!=label))
        f.append(float(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else 0.)
    return {'bce':quantum.binary_cross_entropy(y,p),'macro_f1':float(np.mean(f)),
            'accuracy':float(np.mean(pred==y)),'n':len(y),
            'clipped':int(np.sum((p<quantum.CLIP)|(p>1-quantum.CLIP))),
            'confusion':[[int(np.sum((y==a)&(pred==b))) for b in (0,1)] for a in (0,1)]}


def sigmoid(x):
    p=np.empty_like(x);pos=x>=0;p[pos]=1/(1+np.exp(-x[pos]));e=np.exp(x[~pos]);p[~pos]=e/(1+e)
    return p


def add_work(total,part):
    for k,v in part.items():total[k]=total.get(k,0)+int(v)
    return total


class Model:
    def __init__(self,method,seed):
        if method not in METHODS: raise ValueError(method)
        self.method=method;self.seed=seed;self.is_mlp=method.startswith('mlp')
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1])))
        master=rng.uniform(-.1,.1,(5,4,2,2))
        self.master_initial=master
        if self.is_mlp:
            self.inputs,self.hidden=(6,5) if method=='mlp41' else (6,16)
            h,m=self.hidden,self.inputs
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,4])))
            a,b=np.sqrt(6/(m+h)),np.sqrt(6/(h+1))
            self.parameters=np.concatenate([rng.uniform(-a,a,m*h),np.zeros(h),rng.uniform(-b,b,h),[0.]])
        elif method in FIVE_BANK:self.parameters=master[:,:2].ravel().copy()
        elif method=='untied_assigned':self.parameters=np.concatenate([master[0,:d].ravel() for d in range(1,5)])
        elif method=='readout1':self.parameters=np.r_[master[0,:1].ravel(),np.pi/2]
        else:
            d={'fixed1':1,'encoding1':1,'fixed2':2}.get(method,4)
            self.parameters=master[0,:d].ravel().copy()

    def effective_depth(self,depth):
        depth=np.asarray(depth,dtype=int)
        if self.method in ('fixed1','encoding1','readout1'):return np.ones_like(depth)
        if self.method in ('fixed2',*FIVE_BANK):return np.full_like(depth,2)
        if self.method=='fixed4':return np.full_like(depth,4)
        if self.method=='min_depth2':return np.maximum(depth,2)
        return depth

    def route_for(self,population):
        return population['hash_route'] if self.method=='hash40' else population['kmeans_route'] if self.method=='kmeans40' else None

    def components(self,x,depth,route=None):
        """(row indices, bank identity, angle bank, depths, coordinate slice)."""
        d=self.effective_depth(depth);all_ids=np.arange(len(x))
        if self.method in FIVE_BANK:
            if self.method!='ensemble40':
                raw=np.asarray(route)
                if raw.shape!=(len(x),) or np.any(raw!=raw.astype(int)) or np.any(raw<0) or np.any(raw>4):raise ValueError('Route must be integer 0..4 per record')
                route=raw.astype(int)
            for k in range(5):
                ids=all_ids if self.method=='ensemble40' else np.flatnonzero(route==k)
                if len(ids):yield ids,k,self.parameters[k*8:(k+1)*8].reshape(2,2,2),d[ids],slice(k*8,(k+1)*8)
        elif self.method=='untied_assigned':
            for k in range(1,5):
                ids=np.flatnonzero(d==k)
                if len(ids):yield ids,k-1,self.parameters[OFFSETS[k-1]:OFFSETS[k]].reshape(k,2,2),d[ids],slice(OFFSETS[k-1],OFFSETS[k])
        else:
            count=4 if self.method=='readout1' else len(self.parameters)
            yield all_ids,0,self.parameters[:count].reshape(-1,2,2),d,slice(0,len(self.parameters))

    def options(self):
        return {'encoding':self.method=='encoding1','beta':float(self.parameters[-1]) if self.method=='readout1' else np.pi/2}

    def features(self,x,depth):
        return np.asarray(x) if self.inputs==2 else np.column_stack([x,np.eye(4)[np.asarray(depth)-1]])

    def unpack(self):
        h,m,p=self.hidden,self.inputs,self.parameters;n=m*h
        return p[:n].reshape(m,h),p[n:n+h],p[n+h:n+2*h],p[-1]

    def predict(self,x,depth,route=None):
        if self.is_mlp:
            a,b,c,d=self.unpack();return sigmoid(np.maximum(self.features(x,depth)@a+b,0)@c+d)
        result=np.zeros(len(x))
        for ids,k,bank,depths,sl in self.components(x,depth,route):
            result[ids]+=circuits.predict(x[ids],bank,depths,**self.options())/(5 if self.method=='ensemble40' else 1)
        return result

    def reference_predict(self,x,depth,route=None):
        if self.is_mlp:raise ValueError('Matrix oracle is circuit-only')
        result=np.zeros(len(x))
        for ids,k,bank,depths,sl in self.components(x,depth,route):
            for i,d in zip(ids,depths):result[i]+=reference_v03.probability(x[i],bank,int(d),**self.options())/(5 if self.method=='ensemble40' else 1)
        return result

    def accounting(self,x,depth,route=None,gradient=False):
        total={k:0 for k in circuits.work(np.array([],int))}
        if not self.is_mlp:
            for ids,k,bank,depths,sl in self.components(x,depth,route):
                add_work(total,circuits.work(depths,self.method=='encoding1',self.method=='readout1',gradient))
        total['model_record_visits']=len(x)
        return total

    def gradient(self,x,y,depth,route=None):
        if self.is_mlp:
            f=self.features(x,depth);a,b,c,d=self.unpack();z=f@a+b;act=np.maximum(z,0);p=sigmoid(act@c+d)
            g=(p-y)/len(y);g[(p<quantum.CLIP)|(p>1-quantum.CLIP)]=0
            hidden=g[:,None]*c[None,:]*(z>0)
            grad=np.concatenate([(f.T@hidden).ravel(),hidden.sum(0),act.T@g,[g.sum()]])
        else:
            p=self.predict(x,depth,route);pc=np.clip(p,quantum.CLIP,1-quantum.CLIP)
            chain=(pc-y)/(pc*(1-pc));chain[(p<quantum.CLIP)|(p>1-quantum.CLIP)]=0
            grad=np.zeros_like(self.parameters)
            for ids,k,bank,depths,sl in self.components(x,depth,route):
                jac=circuits.jacobian(x[ids],bank,depths,train_readout=self.method=='readout1',**self.options())
                grad[sl]=np.sum(jac*chain[ids,None],axis=0)/len(y)/(5 if self.method=='ensemble40' else 1)
        return quantum.binary_cross_entropy(y,p),grad,p,self.accounting(x,depth,route,gradient=True)

    def predict_population(self,pop):return self.predict(pop['x'],pop['depth'],self.route_for(pop))


def verify_freeze(stage,seed,method):
    path=ROOT/f'STAGE_{stage}_FREEZE.json'
    if not path.is_file():raise RuntimeError('Official training requires root approval')
    freeze=read_json(path)
    if freeze.get('review_status')!='approved_by_root':raise RuntimeError('Missing root approval')
    if freeze.get('methods')!=list(METHODS) or freeze.get('training_seeds')!=list(SEEDS[stage]):raise RuntimeError('Arm/seed matrix differs from registration')
    if method not in METHODS or seed not in SEEDS[stage]:raise ValueError('Unregistered method/seed')
    if freeze.get('settings')!=SETTINGS:raise RuntimeError('Registered settings mismatch')
    if freeze.get('source_hashes')!=source_hashes():raise RuntimeError('Frozen source changed')
    if freeze.get('data_seal_sha256')!=digest(ROOT/'data/DATA_SEAL.json'):raise RuntimeError('Data seal changed')
    return freeze


def save_checkpoint(path,model,opt,round_number,completed_rounds):
    if Path(path).exists():raise FileExistsError(path)
    np.savez(path,parameters=model.parameters,adam_m=opt.m,adam_v=opt.v,adam_t=opt.t,
             current_round=round_number,completed_rounds=completed_rounds)


def save_predictions(path,pop,p):
    with Path(path).open('x',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['record_id','original_depth','hash_route','kmeans_route','label','probability','prediction'])
        w.writerows(zip(pop['ids'],pop['depth'],pop['hash_route'],pop['kmeans_route'],pop['y'],p,(p>=.5).astype(int)))


def selected_diagnostics(model,pop,output):
    result={'scope':'Prespecified train/validation only; local raw gradients, not causal or Adam-direction proof','train_groups':{}}
    gradients=[]
    for d in range(1,5):
        ids=np.flatnonzero(pop['depth']==d)
        route=model.route_for(pop);route=None if route is None else route[ids]
        loss,g,p,w=model.gradient(pop['x'][ids],pop['y'][ids],pop['depth'][ids],route)
        gradients.append(g)
        result['train_groups'][str(d)]={'metrics':metrics(pop['y'][ids],p),'gradient_norm':float(np.linalg.norm(g)),'work':w}
    np.savez(output/'selected_training_gradients_by_depth.npz',gradients=np.asarray(gradients),depths=np.arange(1,5))
    return result


def inference_diagnostic(model,validation,dataset,output):
    """Resource-only, label-independent validation fixture; no checkpoint tuning."""
    import routers
    ids=np.argsort(validation['ids'],kind='stable')[:min(1024,len(validation['ids']))]
    x,depth=validation['x'][ids],validation['depth'][ids]
    policy=read_json(ROOT/'data'/f'{dataset}_router.json')
    def forward():
        begin=time.perf_counter();route=None
        if model.method in ('hash40','kmeans40'):
            route=routers.route(x,policy,kind='hash' if model.method=='hash40' else 'kmeans')
        routed=time.perf_counter();p=model.predict(x,depth,route)
        return time.perf_counter()-begin,(routed-begin if route is not None else 0.),p,route
    warmup=forward();runs=[forward() for _ in range(3)]
    cached=model.predict_population({k:v[ids] for k,v in validation.items()})
    max_error=max(float(np.max(abs(t[2]-cached))) for t in [warmup,*runs])
    if max_error>1e-12:raise RuntimeError('Uncached inference disagrees with frozen route cache')
    work={}
    for t in [warmup,*runs]:add_work(work,model.accounting(x,depth,t[3]))
    np.savez(output/'inference_fixture_ids.npz',record_ids=validation['ids'][ids])
    return {'scope':'Already loaded NumPy features/depth; CPU route calculation plus full circuit/MLP forward. Excludes input generation, router fit and model load. Concurrent host timing, not isolated hardware efficiency.',
            'population':'validation only, lowest record IDs; labels not consulted','records':len(x),'warmups':1,'timed_repeats':3,
            'total_repeat_seconds':[t[0] for t in runs],'route_repeat_seconds':[t[1] for t in runs],
            'mean_seconds_per_record':float(np.mean([t[0] for t in runs])/len(x)),
            'maximum_cached_difference':max_error,'work_separate_from_training':work}


def train(method,seed,stage,output,rounds=200,limit=None,engineering=False):
    output=Path(output)
    if output.exists():raise FileExistsError('Output exists; preserve all prior results/failures')
    freeze=None if engineering else verify_freeze(stage,seed,method)
    if rounds<1 or (limit is not None and limit<64):raise ValueError('Invalid engineering budget')
    if not engineering and (rounds!=200 or limit is not None):raise ValueError('Full official horizon required')
    dataset='engineering' if engineering else ('development' if stage=='A' else 'confirmation')
    training=load_population(dataset,'train');validation=load_population(dataset,'validation')
    if not engineering and (len(training['y'])!=4800 or len(validation['y'])!=1600):raise ValueError('Official population counts must be 4800/1600')
    data_cost=read_json(ROOT/'data/DATA_SEAL.json')['datasets'][dataset]
    route_kind='hash' if method=='hash40' else 'kmeans' if method=='kmeans40' else None
    preparation={'generation_seconds_charged':data_cost['generation_seconds'],
                 'joint_router_fit_seconds_charged':data_cost['router_fit_seconds'] if route_kind else 0.,
                 'train_validation_route_cache_seconds_charged':sum(data_cost['route_application_seconds_by_split'][split][route_kind] for split in ('train','validation')) if route_kind else 0.,
                 'actual_common_population_preparation_seconds':data_cost['total_population_preparation_seconds'],
                 'scope':'Generation/splitting charged to each arm; joint train-only k-means plus matched hash-cut fit and relevant train/validation cache charged to routed arms. Costs executed once per population but repeatedly charged per arm/seed; cannot sum as project wall time. Test cache excluded from charged arm preparation.'}
    if limit is not None:
        training={k:v[:limit] for k,v in training.items()};validation={k:v[:160] for k,v in validation.items()}
    output.mkdir(parents=True,exist_ok=False)
    config={'classification':'INTERNAL','stage':stage,'engineering':engineering,'dataset':dataset,'method':method,'seed':seed,
            'rounds':rounds,'batch_size':64,'train_records':len(training['y']),'validation_records':len(validation['y']),
            'test_accessed':False,'started_utc':now(),'source_hashes':source_hashes(),'settings':SETTINGS,
            'data_seal_sha256':digest(ROOT/'data/DATA_SEAL.json'),
            'stage_freeze_sha256':digest(ROOT/f'STAGE_{stage}_FREEZE.json') if freeze else None,
            'router_policy_file':f'data/{dataset}_router.json','router_policy_sha256':digest(ROOT/'data'/f'{dataset}_router.json'),
            'preparation':preparation,
            'environment':{'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'executable':sys.executable,
                           'threads':{k:os.getenv(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}}}
    write_json(output/'config.json',config)
    model=Model(method,seed);opt=quantum.Adam(model.parameters.shape)
    np.savez(output/'initial_state.npz',parameters=model.parameters,master_bank=model.master_initial)
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
    route=model.route_for(training);orders=[];gradient_means=[]
    work={'training':{},'validation':{}};total_clips=0;bank_visits=np.zeros(5,dtype=np.int64);depth_visits=np.zeros(4,dtype=np.int64);layer_exposure=np.zeros(4,dtype=np.int64)
    best=float('inf');selected_round=None;selected_path=None;selected=None;round_number=0;completed_rounds=0
    start=time.perf_counter()
    try:
        with (output/'ledger.jsonl').open('x',encoding='utf-8') as ledger:
            for round_number in range(1,rounds+1):
                order=rng.permutation(len(training['y']));orders.append(order)
                loss_sum=0.;norm_sum=0.;norm_max=0.;gradient_sum=np.zeros_like(model.parameters);batches=0;clips=0
                for offset in range(0,len(order),64):
                    ids=order[offset:offset+64];r=None if route is None else route[ids]
                    loss,g,p,w=model.gradient(training['x'][ids],training['y'][ids],training['depth'][ids],r)
                    if not np.isfinite(loss) or not np.isfinite(g).all():raise FloatingPointError('Nonfinite loss/gradient')
                    norm=float(np.linalg.norm(g));norm_sum+=norm;norm_max=max(norm_max,norm);gradient_sum+=g;batches+=1
                    opt.step(model.parameters,g);loss_sum+=loss*len(ids);clips+=int(np.sum((p<quantum.CLIP)|(p>1-quantum.CLIP)))
                    add_work(work['training'],w)
                    if not model.is_mlp:
                        for ix,k,bank,ds,sl in model.components(training['x'][ids],training['depth'][ids],r):
                            bank_visits[k]+=len(ix)
                            depth_visits+=np.bincount(ds,minlength=5)[1:5]
                            layer_exposure+=[np.sum(ds>=d) for d in range(1,5)]
                gradient_means.append(gradient_sum/batches)
                total_clips+=clips
                p=model.predict_population(validation);vm=metrics(validation['y'],p)
                add_work(work['validation'],model.accounting(validation['x'],validation['depth'],model.route_for(validation)))
                chosen=vm['bce']<best
                if chosen:
                    best=vm['bce'];selected_round=round_number;selected=model.parameters.copy()
                    selected_path=output/f'selected_round_{round_number:04d}.npz'
                    save_checkpoint(selected_path,model,opt,round_number,round_number)
                row={'round':round_number,'optimizer_updates':opt.t,'training_loss':loss_sum/len(order),'validation':vm,'selected':chosen,
                     'mean_batch_gradient_norm':norm_sum/batches,'maximum_batch_gradient_norm':norm_max,
                     'training_clipped_probabilities':clips,'work_cumulative':work,'elapsed_seconds':time.perf_counter()-start}
                ledger.write(json.dumps(row,allow_nan=False)+'\n');ledger.flush();completed_rounds=round_number
                write_json(output/'status.json',{'status':'running','round':round_number,'seed':seed,'method':method})
        training_seconds=time.perf_counter()-start
        save_checkpoint(output/'last_checkpoint.npz',model,opt,rounds,rounds)
        shutil.copyfile(selected_path,output/'selected_checkpoint.npz')
        np.savez_compressed(output/'record_orders.npz',orders=np.asarray(orders,dtype=np.int32),record_ids=training['ids'])
        np.savez(output/'epoch_gradient_means.npz',gradients=np.asarray(gradient_means))
        model.parameters[:]=selected;p=model.predict_population(validation)
        save_predictions(output/'validation_predictions.csv',validation,p)
        work['selected_validation_replay']=model.accounting(validation['x'],validation['depth'],model.route_for(validation))
        diagnostics=selected_diagnostics(model,training,output)
        inference=inference_diagnostic(model,validation,dataset,output)
        grouped={str(d):metrics(validation['y'][validation['depth']==d],p[validation['depth']==d]) for d in range(1,5)}
        result={'status':'completed','method':method,'seed':seed,'stage':stage,'engineering':engineering,
                'completed_rounds':rounds,'optimizer_global_updates':opt.t,'selected_round':selected_round,
                'selected_validation':metrics(validation['y'],p),'validation_by_original_depth':grouped,
                'validation_route_population_counts':{k:np.bincount(validation[k+'_route'],minlength=5).tolist() for k in ('hash','kmeans')},
                'parameter_count':len(model.parameters),'training_seconds':training_seconds,'total_seconds':time.perf_counter()-start,
                'charged_training_seconds':training_seconds+sum(preparation[k] for k in ('generation_seconds_charged','joint_router_fit_seconds_charged','train_validation_route_cache_seconds_charged')),
                'preparation':preparation,
                'work':work,'training_clipped_probabilities':total_clips,'bank_training_record_visits':bank_visits.tolist(),'executed_depth_training_record_visits':depth_visits.tolist(),
                'layer_training_record_exposure':layer_exposure.tolist(),'diagnostics':diagnostics,
                'inference':inference,
                'selected_checkpoint_sha256':digest(output/'selected_checkpoint.npz'),'last_checkpoint_sha256':digest(output/'last_checkpoint.npz'),
                'ledger_sha256':digest(output/'ledger.jsonl'),'record_orders_sha256':digest(output/'record_orders.npz'),
                'data_seal_sha256':config['data_seal_sha256'],'stage_freeze_sha256':config['stage_freeze_sha256'],
                'test_accessed':False,'finished_utc':now()}
        write_json(output/'result.json',result)
        write_json(output/'endpoint_commit.json',{'result_sha256':digest(output/'result.json'),'config_sha256':digest(output/'config.json'),
                   'selected_checkpoint_sha256':result['selected_checkpoint_sha256'],'last_checkpoint_sha256':result['last_checkpoint_sha256'],
                   'ledger_sha256':result['ledger_sha256'],'record_orders_sha256':result['record_orders_sha256'],'committed_utc':now()})
        write_json(output/'status.json',{'status':'completed','round':rounds,'seed':seed,'method':method})
        return result
    except BaseException as error:
        failure={'status':'failed','method':method,'seed':seed,'utc':now(),'current_round':round_number,'completed_rounds':completed_rounds,
                 'completed_optimizer_updates':opt.t,'error':str(error),'type':type(error).__name__,'traceback':traceback.format_exc(),
                 'recovery':'No automatic resume; preserve failure and require reviewed fresh output/restart.'}
        save_checkpoint(output/'failed_checkpoint.npz',model,opt,round_number,completed_rounds)
        write_json(output/'failure.json',failure);write_json(output/'status.json',failure)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['A','B'],default='A');parser.add_argument('--method',choices=METHODS,required=True)
    parser.add_argument('--seed',type=int,required=True);parser.add_argument('--engineering',action='store_true')
    parser.add_argument('--rounds',type=int,default=200);parser.add_argument('--train-limit',type=int);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();r=train(a.method,a.seed,a.stage,a.output,a.rounds,a.train_limit,a.engineering)
    print(json.dumps({k:r[k] for k in ('status','method','seed','selected_validation','training_seconds')}))


if __name__=='__main__':main()
