"""Independent input-data replay; no model imports or sealed diagnostic reads."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,json,time,traceback
from pathlib import Path
from datetime import datetime,timezone
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
GOV=ROOT/'governance';DATA=ROOT/'quantum/data'
SPLITS=('train','validation','test')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):return {'path':str(p),'sha256':sha(p),'bytes':Path(p).stat().st_size}
def ah(a):
    a=np.ascontiguousarray(a);return hashlib.sha256(str(a.dtype).encode()+str(a.shape).encode()+a.tobytes()).hexdigest()
def keys(a):
    a=np.array(a,dtype='<f8',order='C',copy=True);a[a==0]=0.;return [row.tobytes() for row in a]
def seed(s):
    n=int.from_bytes(hashlib.sha256(s['namespace'].encode('ascii')).digest()[:16],'little');assert n==int(s['uint128_decimal']);return n
def rng(pop,role):return np.random.Generator(np.random.PCG64(seed(pop['proposed_streams'][role])))
def allocate(counts,fraction,n):
    a=np.asarray(counts)*fraction;out=np.floor(a).astype(np.int64)
    order=sorted(range(2),key=lambda i:(-(a[i]-out[i]),i))
    for i in order[:n-int(out.sum())]:out[i]+=1
    return out
def labels(x,family):
    a,b=x.T
    if family=='checkerboard':p=np.sin(3*np.pi*a+np.pi/7)*np.sin(3*np.pi*b+np.pi/5)>0
    elif family=='spiral':p=np.sin(2*np.arctan2(b,a)+4*np.pi*np.sqrt(a*a+b*b))>0
    elif family=='annulus':p=(a*a+b*b>.25)&(a*a+b*b<.85)
    else:p=np.minimum.reduce([(a+.55)**2+(b+.45)**2,(a-.5)**2+(b+.35)**2,a*a+(b-.55)**2])<.22**2
    return p.astype(np.int64)
def synthetic(pop,base,excluded):
    generator=rng(pop,'coordinates');accepted=[];draws=[];seen=set();consumed=0
    while len(accepted)<8000:
        for x in generator.uniform(-1,1,(8000-len(accepted),2)):
            k=keys(x[None,:])[0]
            if k not in excluded and k not in seen:accepted.append(x);draws.append(consumed);seen.add(k)
            consumed+=1
        assert consumed<=1000000
    x=np.array(accepted);y=labels(x,pop['family'])
    if pop['family']=='annulus':y^=(rng(pop,'annulus_noise').random(8000)<.1).astype(np.int64)
    ids=base+rng(pop,'record_ids').permutation(8000).astype(np.int64);draws=np.array(draws,dtype=np.int64)
    gen=rng(pop,'split');classes=[gen.permutation(np.flatnonzero(y==k)) for k in (0,1)];cnt=list(map(len,classes));a=allocate(cnt,.6,4800);b=allocate(cnt,.2,1600);members=[[],[],[]]
    for c,na,nb in zip(classes,a,b):members[0].extend(c[:na]);members[1].extend(c[na:na+nb]);members[2].extend(c[na+nb:])
    out={}
    for split,member in zip(SPLITS,members):
        ix=gen.permutation(np.array(member,dtype=np.int64));out[split]={'x':x[ix],'y':y[ix],'ids':ids[ix],'source_draw_ids':draws[ix]}
    return out,seen,consumed
def banknote(pop,base):
    p=ROOT/'quantum/raw/data_banknote_authentication.txt';assert sha(p)=='d0539aaed2139ba7a587b3e34fb345ce503ff7d5d33dbf9912d8e195ce425cb9'
    raw=np.loadtxt(p,delimiter=',');assert raw.shape==(1372,5);x=raw[:,:4];y=raw[:,4].astype(np.int64);groups={}
    for i,k in enumerate(keys(x)):groups.setdefault(k,[]).append(i)
    gen=rng(pop,'split');ordered=sorted(groups);ordered=[ordered[i] for i in gen.permutation(len(ordered))];ordered.sort(key=lambda k:-len(groups[k]));targets=np.array([.6,.2,.2])[:,None]*np.bincount(y,minlength=2);current=np.zeros((3,2),dtype=np.int64);members=[[],[],[]]
    for k in ordered:
        ix=groups[k];c=np.bincount(y[ix],minlength=2);cost=((2*(current-targets)*c+c*c)/targets).sum(1);j=int(cost.argmin());members[j].extend(ix);current[j]+=c
    indices={s:gen.permutation(np.array(ix,dtype=np.int64)) for s,ix in zip(SPLITS,members)};ids=base+rng(pop,'record_ids').permutation(len(x)).astype(np.int64)
    train=x[indices['train']];mean=train.mean(0);scale=train.std(0);scale=np.where(scale>0,scale,1.);z=(train-mean)/scale;center=z.mean(0);cov=(z-center).T@(z-center);ev,V=np.linalg.eigh(cov);comp=V[:,np.argsort(ev)[-2:][::-1]].T
    for row in comp:
        if row[np.argmax(abs(row))]<0:row*=-1
    pc=(z-center)@comp.T;pcmean=pc.mean(0);pcscale=pc.std(0);pcscale=np.where(pcscale>0,pcscale,1.)
    out={}
    for s,ix in indices.items():
        norm=(x[ix]-mean)/scale;pc=(norm-center)@comp.T
        out[s]={'raw_x':x[ix],'x':(2/np.pi)*np.arctan((pc-pcmean)/pcscale),'x4':(2/np.pi)*np.arctan(norm),'y':y[ix],'ids':ids[ix],'source_row_indices':ix}
    return out,{'mean4':mean,'scale4':scale,'pca_center4':center,'components2x4':comp,'pc_mean2':pcmean,'pc_scale2':pcscale,'retained_variance':ev[-2:].sum()/ev.sum()}
def dist(x,c):return ((x[:,None,:]-c[None,:,:])**2).sum(2)
def order(c):return np.lexsort((c[:,1],c[:,0]))
def kmeans(x,stream):
    x=x[np.lexsort((x[:,1],x[:,0]))];candidates=[];records=[]
    for restart in range(20):
        gen=np.random.Generator(np.random.PCG64(np.random.SeedSequence([stream,restart])));idx=[int(gen.integers(len(x)))];near=dist(x,x[idx])[:,0]
        for _ in range(4):
            j=min(int(np.searchsorted(np.cumsum(near),gen.random()*near.sum(),side='right')),len(x)-1)
            if j in idx:j=int(np.flatnonzero(near>0)[0])
            idx.append(j);near=np.minimum(near,dist(x,x[[j]])[:,0])
        c=x[idx];c=c[order(c)];converged=False
        for iteration in range(1,501):
            d=dist(x,c);assigned=d.argmin(1);counts=np.bincount(assigned,minlength=5);new=c.copy()
            for k in range(5):
                if counts[k]:new[k]=x[assigned==k].mean(0)
            candidates_empty=np.argsort(-d[np.arange(len(x)),assigned],kind='stable');used=set()
            for k in np.flatnonzero(counts==0):
                chosen=next(int(j) for j in candidates_empty if int(j) not in used);used.add(chosen);new[k]=x[chosen]
            new=new[order(new)];after=dist(x,new).argmin(1);c=new
            if np.array_equal(after,assigned) and np.all(counts>0):converged=True;break
        assigned=dist(x,c).argmin(1);counts=np.bincount(assigned,minlength=5);inertia=float(((x-c[assigned])**2).sum());eligible=bool(converged and np.all(counts>0))
        records.append({'restart':restart,'iterations':iteration,'converged':converged,'eligible':eligible,'inertia':inertia,'counts':counts.tolist()})
        if eligible:candidates.append((inertia,tuple(c.ravel()),restart,c,counts))
    winner=min(candidates,key=lambda z:z[:3]);return winner,records
def run():
    started=time.perf_counter();seal=read(DATA/'DATA_SEAL.json');matrix=read(GOV/'RUN_MATRIX.json');reg=read(GOV/'DATA_REGISTRATION.json');approved=read(GOV/'DATA_GENERATION_APPROVAL.json');pre=read(GOV/'HISTORICAL_FRESHNESS_PREFLIGHT.json');history=set();registered=set()
    assert seal['schema']=='qpath-v09-data-seal-1' and seal['outcomes_evaluated'] is False
    for name,h in seal['source_sha256'].items():assert sha(ROOT/'quantum'/name)==h
    for name,h in seal['active_input_sha256'].items():assert sha(GOV/name)==h
    assert seal['registration_sha256']==sha(GOV/'DATA_REGISTRATION.json')==approved['registration_sha256'];assert seal['generation_approval_sha256']==sha(GOV/'DATA_GENERATION_APPROVAL.json');assert seal['freshness_preflight_sha256']==sha(GOV/'HISTORICAL_FRESHNESS_PREFLIGHT.json')
    for item in pre['coordinate_sources']:
        p=Path(item['path']);assert sha(p)==item['sha256']
        with np.load(p,allow_pickle=False) as f:x=f['x']
        assert ah(x)==item['x_array_sha256'];k=set(keys(x));history.update(k)
        if item['registered_payload']:registered.update(k)
    assert len(history)==983258==reg['historical_unique_observed'];assert len(registered)==904000
    for item in pre['seed_sources']:assert sha(item['path'])==item['sha256']
    oldseeds=set(map(int,pre['declared_historical_seed_values']));streams={}
    def walk(value):
        if isinstance(value,dict):
            if 'namespace' in value and 'uint128_decimal' in value:streams[value['namespace']]=seed(value)
            else:
                for x in value.values():walk(x)
        elif isinstance(value,list):
            for x in value:walk(x)
    walk(matrix);assert len(streams)==len(set(streams.values()))==531 and set(streams.values()).isdisjoint(oldseeds)
    bankhist=read(GOV/'BANKNOTE_HISTORICAL_PRESENCE.json');assert bankhist['status']=='PASS_NO_RETAINED_PRIOR_BANKNOTE_INPUT_FOUND' and not bankhist['named_files'] and not bankhist['four_feature_input_arrays']
    for item in bankhist['excluded_non_numeric_four_column_headers']:assert sha(item['path'])==item['sha256']
    expected_files={'DATA_SEAL.json'};allids=set();records=[];new_count=0
    for ordinal,pop in enumerate(matrix['populations']):
        name=pop['population_id'];base=9000000000000000000+ordinal*1000000;policy_path=DATA/f'{name}_router.json';policy=read(policy_path);expected_files.add(policy_path.name);assert sha(policy_path)==seal['routers'][name]['sha256']
        if pop['family']=='banknote':expected,prep=banknote(pop,base)
        else:
            expected,newkeys,consumed=synthetic(pop,base,history);assert newkeys.isdisjoint(history);history.update(newkeys);new_count+=len(newkeys)
            assert consumed==seal['datasets'][name]['preparation_metadata']['draws_consumed']
        actual={};max_error=0.
        for s in SPLITS:
            filename=f"{name}_{'SEALED_test' if s=='test' else s}.npz";expected_files.add(filename);item=seal['files'][filename];p=DATA/filename;assert sha(p)==item['sha256']
            with np.load(p,allow_pickle=False) as f:part={k:f[k] for k in f.files}
            assert set(part)==set(expected[s])|{'kmeans_route','margin_bin'} and not {'clean_y','label_flip'}&set(part)
            for k,a in part.items():assert ah(a)==item['arrays'][k]
            for k,a in expected[s].items():
                if pop['family']=='banknote' and k=='x':np.testing.assert_allclose(part[k],a,atol=2e-13,rtol=0);max_error=max(max_error,float(abs(part[k]-a).max()))
                else:np.testing.assert_array_equal(part[k],a)
            ids=set(part['ids'].tolist());assert len(ids)==len(part['x']) and ids.isdisjoint(allids);allids.update(ids);assert len(ids)==seal['datasets'][name]['counts'][s];assert np.bincount(part['y'],minlength=2).tolist()==seal['datasets'][name]['label_counts'][s];actual[s]=part
        train=actual['train']['x'];winner,restarts=kmeans(train,seed(pop['proposed_streams']['kmeans_initialization']));inertia,_,which,centers,counts=winner
        np.testing.assert_array_equal(policy['centroids'],centers);assert policy['kmeans']['restart_records']==restarts and policy['kmeans']['selected_restart']==which and policy['kmeans']['selected_inertia']==inertia
        assert policy['training_ids_array_sha256']==ah(actual['train']['ids']);assert policy['training_n']==len(train)
        d=np.sort(dist(train,centers),axis=1);margin=d[:,1]-d[:,0];assert policy['tau']==max(.001,float(np.median(margin)));raw=np.column_stack([train[:,0]**(degree-k)*train[:,1]**k for degree in (2,3,4) for k in range(degree+1)]);np.testing.assert_array_equal(policy['residual_scale'],np.maximum(1,abs(raw).max(0)))
        edges=np.quantile(margin,[0,.1,.25,.5,1],method='linear');np.testing.assert_array_equal(policy['margin_bins']['raw_edges'],edges);edges=np.unique(edges);np.testing.assert_array_equal(policy['margin_bins']['unique_edges'],edges)
        for s,part in actual.items():
            d=dist(part['x'],centers);np.testing.assert_array_equal(part['kmeans_route'],d.argmin(1));d.sort(axis=1);np.testing.assert_array_equal(part['margin_bin'],np.searchsorted(edges[1:-1],d[:,1]-d[:,0],side='right'))
        if pop['family']=='banknote':
            for k,a in prep.items():np.testing.assert_allclose(policy['preprocessing'][k],a,atol=2e-13,rtol=0)
            splitkeys=[set(keys(a['raw_x'])) for a in actual.values()];assert all(splitkeys[i].isdisjoint(splitkeys[j]) for i in range(3) for j in range(i))
        else:
            item=seal['diagnostics'][name];expected_files.add(item['file']);assert sha(DATA/item['file'])==item['sha256'] # bytes only: latent members remain sealed
        records.append({'population':name,'records':sum(len(p['x']) for p in actual.values()),'independent_split_rng_labels_ids':'PASS','router_restarts_replayed':20,'train_only_policy':'PASS','max_PCA_eigh_prediction_coordinate_error':max_error})
        print(json.dumps({'audited_population':name,'count':len(records)}),flush=True)
    assert len(records)==41 and len(allids)==321372 and new_count==320000
    assert {p.name for p in DATA.iterdir() if p.is_file()}==expected_files
    return {'schema':'qpath-v09-data-independent-audit-1','status':'PASS','reviewer':'/root/v09_science','utc':datetime.now(timezone.utc).isoformat(),'data_seal_sha256':sha(DATA/'DATA_SEAL.json'),'verified_payloads':204,'verified_populations':41,'verified_split_files':123,'verified_router_policies':41,'replayed_router_restarts':820,'new_synthetic_coordinates':new_count,'unique_record_ids':len(allids),'historical_unique_coordinates':983258,'registered_historical_unique_coordinates':904000,'new_namespace_streams':len(streams),'data_seal':bind(DATA/'DATA_SEAL.json'),'source':bind(Path(__file__)),'source_receipt':bind(GOV/'DATA_SOURCE_INDEPENDENT_REVIEW_v02.json'),'execution_source_review':bind(GOV/'EXECUTION_INDEPENDENT_SOURCE_REVIEW_v01.json'),'populations':records,'wall_seconds':time.perf_counter()-started,'model_test_outcomes_read':False,'sealed_diagnostics':'SHA256 bytes checked; no NPZ members loaded','limitations':'Historical freshness uses independently rehashed and replayed coordinate/seed files from the registered complete historical inventory. Banknote identity grouping cannot establish specimen/capture-session independence.'}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    try:receipt=run()
    except BaseException as error:
        receipt={'status':'FAIL','error':repr(error),'traceback':traceback.format_exc(),'utc':datetime.now(timezone.utc).isoformat(),'source':bind(Path(__file__))}
        with args.output.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
        raise
    with args.output.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    print(json.dumps({'status':'PASS','receipt':str(args.output)}))
