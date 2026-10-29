"""Independent reconstruction; reads data provenance, never model outcomes."""
from pathlib import Path
import argparse, bisect, hashlib, json, sys, traceback
from datetime import datetime, timezone
import numpy as np
sys.dont_write_bytecode = True
if not __debug__:
    raise RuntimeError('Independent audit requires enabled assertions; refuse Python -O')
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'quantum/data'
SEEDS = {role+'_'+family: (base+17,base+23,base+29,base+37)
         for role,offset in [('engineering',2000000),('development',2100000),('confirmation',2200000)]
         for family,add in [('checkerboard',30000),('spiral',40000),('annulus',50000),('disks',60000)]
         for base in [offset+add]}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ah(a): return hashlib.sha256(str(a.dtype).encode()+str(a.shape).encode()+np.ascontiguousarray(a).tobytes()).hexdigest()
def canon(x):
    a=np.array(x,dtype='<f8',order='C',copy=True);a[a==0]=0.;return a
def keys(x): return [a.tobytes() for a in canon(x)]
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def exact(a,b): assert np.array_equal(a,b), 'Exact array mismatch'
def near(a,b): assert np.allclose(a,b,rtol=0,atol=2e-12), 'Numeric mismatch'
def allocate(n,numerator,total):
    q=(np.asarray(n)*numerator)//5
    priority=sorted(range(len(n)),key=lambda i:(-int(n[i]*numerator%5),i))
    q[priority[:total-int(q.sum())]]+=1
    return q

def independent_labels(x,family):
    a,b=x.T
    if family=='checkerboard':positive=np.sin(3*np.pi*a+np.pi/7)*np.sin(3*np.pi*b+np.pi/5)>0
    elif family=='spiral':positive=np.sin(2*np.arctan2(b,a)+4*np.pi*np.sqrt(a*a+b*b))>0
    elif family=='annulus':positive=((a*a+b*b)>.25)&((a*a+b*b)<.85)
    elif family=='disks':positive=np.logical_or.reduce([(a-u)**2+(b-v)**2<.22**2 for u,v in [(-.55,-.45),(.5,-.35),(0.,.55)]])
    else:raise ValueError('Unknown family')
    return positive.astype(np.int64)

def reconstruct_population(seed,excluded,family):
    rng=np.random.Generator(np.random.PCG64(seed[0]));accepted=[];draws=[];rejected=[];seen=set();consumed=0
    while len(accepted)<8000:
        for row in canon(rng.uniform(-1,1,(8000-len(accepted),2))):
            key=row.tobytes()
            if key in excluded or key in seen:
                rejected.append({'draw_index':consumed,'feature_sha256':hashlib.sha256(key).hexdigest(),'reason':'prior_population_exact_match' if key in excluded else 'within_population_duplicate'})
            else:accepted.append(row);draws.append(consumed);seen.add(key)
            consumed+=1
        assert consumed<1000000
    x=np.array(accepted);clean=independent_labels(x,family)
    flips=np.random.Generator(np.random.PCG64(seed[3])).random(8000)<.1 if family=='annulus' else np.zeros(8000,dtype=bool)
    y=clean ^ flips.astype(np.int64)
    record_ids=seed[0]*1000000+np.random.Generator(np.random.PCG64(seed[1])).permutation(8000)
    draws=np.array(draws,dtype=np.int64)
    rng=np.random.Generator(np.random.PCG64(seed[2]))
    groups=[rng.permutation(np.where(y==label)[0]) for label in range(2)]
    sizes=[len(g) for g in groups];nt=allocate(sizes,3,4800);nv=allocate(sizes,1,1600)
    membership=[[],[],[]]
    for g,n,m in zip(groups,nt,nv):
        membership[0].extend(g[:n]);membership[1].extend(g[n:n+m]);membership[2].extend(g[n+m:])
    out={}
    for split,ids in zip(('train','validation','test'),membership):
        ids=rng.permutation(np.array(ids,dtype=np.int64))
        out[split]={'x':x[ids],'y':y[ids],'clean_y':clean[ids],'label_flip':flips[ids],'ids':record_ids[ids],'source_draw_ids':draws[ids]}
    return out,seen,{'draws_consumed':consumed,'accepted':8000,'rejected':rejected,'stratum_order':[0,1],
        'stratum_counts':sizes,'train_stratum_counts':nt.tolist(),'validation_stratum_counts':nv.tolist(),
        'clean_label_counts':np.bincount(clean,minlength=2).tolist(),'label_noise_probability':.1 if family=='annulus' else 0.,'realized_flip_count':int(flips.sum())}

def distances(a,b):
    # Explicit coordinate arithmetic, independent of production distance helper.
    return (a[:,0,None]-b[None,:,0])**2+(a[:,1,None]-b[None,:,1])**2
def ordered(a): return a[np.lexsort((a[:,1],a[:,0]))]
def reference_fit(x,seed):
    x=ordered(canon(x));runs=[];eligible=[]
    for restart in range(20):
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,restart])))
        chosen=[int(rng.integers(len(x)))];nearest=distances(x,x[chosen])[:,0]
        while len(chosen)<5:
            v=float(rng.random())*float(nearest.sum())
            index=min(int(np.searchsorted(np.cumsum(nearest),v,side='right')),len(x)-1)
            if index in chosen:index=int(np.where(nearest>0)[0][0])
            chosen.append(index);nearest=np.minimum(nearest,distances(x,x[[index]])[:,0])
        centers=ordered(x[chosen].copy());converged=False
        for iteration in range(1,501):
            dist=distances(x,centers);assignment=dist.argmin(1);counts=np.bincount(assignment,minlength=5)
            updated=centers.copy()
            for bank in range(5):
                if counts[bank]:updated[bank]=np.mean(x[assignment==bank],axis=0)
            candidates=np.argsort(-dist[np.arange(len(x)),assignment],kind='stable');used=set()
            for bank in np.where(counts==0)[0]:
                i=next(int(j) for j in candidates if int(j) not in used);used.add(i);updated[bank]=x[i]
            centers=ordered(updated);new=distances(x,centers).argmin(1)
            if np.array_equal(new,assignment) and np.all(counts>0):converged=True;break
        labels=distances(x,centers).argmin(1);counts=np.bincount(labels,minlength=5)
        inertia=float(np.sum((x-centers[labels])**2));ok=bool(converged and np.all(counts>0))
        runs.append({'restart':restart,'iterations':iteration,'converged':converged,'eligible':ok,'inertia':inertia,'counts':counts.tolist()})
        if ok:eligible.append((inertia,tuple(centers.flat),restart,centers,counts))
    return min(eligible,key=lambda z:z[:3]),runs

def reference_hashes(x,salt):
    prefix=b'QPATH-V03-HASH5\0'+salt.encode('ascii')+b'\0'
    return [hashlib.sha256(prefix+k).hexdigest() for k in keys(x)]

def audit():
    source_paths=[ROOT/'quantum'/n for n in ('prepare_data.py','routers.py','tests/test_routers_data.py')]+[Path(__file__),ROOT/'governance/DATA_REGISTRATION.json',ROOT/'governance/DATA_GENERATION_APPROVAL.json',ROOT/'analysis/classical_review/DATA_SOURCE_PREGENERATION_REVIEW.json']
    sources={str(p.relative_to(ROOT)):sha(p) for p in source_paths}
    seal=read(DATA/'DATA_SEAL.json');seal_sha=sha(DATA/'DATA_SEAL.json')
    registration=read(ROOT/'governance/DATA_REGISTRATION.json');approval=read(ROOT/'governance/DATA_GENERATION_APPROVAL.json')
    assert registration['populations']=={k:list(v) for k,v in SEEDS.items()}
    assert approval['status']=='approved_by_root' and approval['study_id']==seal['study_id']=='QPATH-GENERALIZATION-v0.6'
    assert approval['registration_sha256']==sha(ROOT/'governance/DATA_REGISTRATION.json')
    assert approval['independent_review_sha256']==sha(ROOT/'analysis/classical_review/DATA_SOURCE_PREGENERATION_REVIEW.json')
    assert approval['source_sha256']==seal['source_sha256']
    assert seal['population_order']==list(SEEDS)
    for n,h in seal['source_sha256'].items():assert sha(ROOT/'quantum'/n)==h
    excluded=set()
    for old in seal['historical_sources']:
        p=Path(old['path']);assert sha(p)==old['sha256'];assert sha(old['manifest_path'])==old['manifest_sha256']
        with np.load(p,allow_pickle=False) as z:x=z['x']
        assert ah(x)==old['feature_array_sha256'];excluded.update(keys(x))
    assert len(excluded)==168000==seal['historical_unique_features']
    assert len(seal['historical_sources'])==65
    results={};file_count=0;array_count=0;all_ids=set()
    for name,seed in SEEDS.items():
        pop,new,redraw=reconstruct_population(seed,excluded,name.split('_',1)[1]);assert not(excluded&new);excluded.update(new)
        assert redraw==seal['datasets'][name]['redraw']
        policy_path=DATA/f'{name}_router.json';policy=read(policy_path)
        assert sha(policy_path)==seal['routers'][name]['sha256']
        train=pop['train'];x=train['x'];rs=seed[0]+70000
        assert policy['seed']==rs and policy['training_n']==4800 and policy['population']==name
        assert policy['training_ids_array_sha256']==ah(train['ids'])
        assert policy['training_ordered_features_sha256']==hashlib.sha256(canon(x).tobytes()).hexdigest()
        assert policy['training_feature_set_sha256']==hashlib.sha256(ordered(canon(x)).tobytes()).hexdigest()
        fit,runs=reference_fit(x,rs);inertia,_,restart,centers,counts=fit
        near(centers,policy['centroids']);assert restart==policy['kmeans']['selected_restart'];near(inertia,policy['kmeans']['selected_inertia'])
        for a,b in zip(runs,policy['kmeans']['restart_records']):
            near(a['inertia'],b['inertia']);assert {k:v for k,v in a.items() if k!='inertia'}=={k:v for k,v in b.items() if k!='inertia'}
        assert counts.tolist()==policy['kmeans_training_counts']
        salt=f'qpath-v03-population-router-{rs+900000}'
        assert policy['hash_salt']==salt
        hashes=sorted(reference_hashes(x,salt));cuts=[hashes[int(i)-1] for i in np.cumsum(counts)[:-1]]
        assert cuts==policy['hash_cutpoints_hex']
        split_counts={}
        for split,a in pop.items():
            assert not(all_ids&set(a['ids']));all_ids.update(a['ids'].tolist())
            a['kmeans_route']=distances(a['x'],centers).argmin(1).astype(np.int64)
            a['hash_route']=np.array([bisect.bisect_left(cuts,h) for h in reference_hashes(a['x'],salt)],dtype=np.int64)
            filename=f"{name}_{'SEALED_test' if split=='test' else split}.npz";path=DATA/filename;info=seal['files'][filename]
            assert sha(path)==info['sha256'];saved=load(path);assert set(saved)==set(a)
            for k in a:exact(a[k],saved[k]);assert ah(saved[k])==info['arrays'][k];array_count+=1
            assert info['router_policy_sha256']==sha(policy_path);file_count+=1
            split_counts[split]={k:np.bincount(a[k+'_route'],minlength=5).tolist() for k in ('kmeans','hash')}
        assert split_counts==seal['datasets'][name]['route_counts']
        for split,a in pop.items():
            assert np.bincount(a['y'],minlength=2).tolist()==seal['datasets'][name]['label_counts'][split]
            assert np.bincount(a['clean_y'],minlength=2).tolist()==seal['datasets'][name]['clean_label_counts'][split]
            assert int(a['label_flip'].sum())==seal['datasets'][name]['label_flip_counts'][split]
        assert split_counts['train']['kmeans']==split_counts['train']['hash']
        results[name]={'records':8000,'all_arrays_exact':True,'kmeans_restarts_reconstructed':20,'selected_restart':restart,'selected_inertia':inertia,'train_route_counts':counts.tolist(),'split_route_counts':split_counts,'rejected_draws':len(redraw['rejected'])}
    assert len(excluded)==264000==seal['post_generation_total_unique_features']
    assert len(all_ids)==96000==seal['new_unique_record_ids']
    assert file_count==36 and len(seal['files'])==36 and len(seal['routers'])==12
    assert seal_sha==sha(DATA/'DATA_SEAL.json')
    assert sources=={str(p.relative_to(ROOT)):sha(p) for p in source_paths}
    return {'status':'PASS','study_id':'QPATH-GENERALIZATION-v0.6','created_utc':datetime.now(timezone.utc).isoformat(),'scope':'Independent exact data and policy reconstruction including observed/latent labels and independent annulus Bernoulli flips. Test arrays read only for provenance, no model probabilities, checkpoints or outcomes. No production generation/fitting helper imported.','source_sha256':sources,'data_seal_sha256':seal_sha,'historical_feature_records_unique':168000,'new_feature_records_unique':96000,'unique_record_ids':len(all_ids),'payloads_checked':file_count,'arrays_checked':array_count,'populations':results,'official_training_executed':False,'model_test_outcomes_accessed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    try:r=audit()
    except Exception:r={'status':'FAIL','traceback':traceback.format_exc()}
    args.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8');print(json.dumps(r,indent=2));sys.exit(0 if r['status']=='PASS' else 1)
