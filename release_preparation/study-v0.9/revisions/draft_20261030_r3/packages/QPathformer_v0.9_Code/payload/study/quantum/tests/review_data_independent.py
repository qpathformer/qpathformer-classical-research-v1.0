"""Independent source and mathematical fixture review of v09 data, not official generation."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import prepare_data as data
import routers

def bind(path):
    p=Path(path);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}

def main():
    root=Path(__file__).resolve().parents[2];parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=root/'governance/DATA_SOURCE_INDEPENDENT_REVIEW_v01.json');args=parser.parse_args();out=args.output
    if out.exists():raise FileExistsError(out)
    records=[]
    def stream(role):
        n='QPATH-v09-independent-data-fixture|'+role
        return {'namespace':n,'uint128_decimal':str(int.from_bytes(hashlib.sha256(n.encode()).digest()[:16],'little'))}
    streams={r:stream(r) for r in ('coordinates','annulus_noise','record_ids','split')}
    rng=np.random.Generator(np.random.PCG64(int(streams['coordinates']['uint128_decimal'])))
    draws=rng.uniform(-1,1,(603,2));excluded={row.astype('<f8').tobytes() for row in draws[:3]}
    for family in ('checkerboard','spiral','annulus','disks'):
        parts,latent,meta,keys=data.generate({'family':family,'proposed_streams':streams},excluded,700000,n=600,counts={'train':360,'validation':120,'test':120})
        allx=np.vstack([p['x'] for p in parts.values()]);allsrc=np.concatenate([p['source_draw_ids'] for p in parts.values()]);ally=np.concatenate([p['y'] for p in parts.values()]);sort=np.argsort(allsrc)
        np.testing.assert_array_equal(allsrc[sort],np.arange(3,603));np.testing.assert_array_equal(allx[sort],draws[3:]);assert keys.isdisjoint(excluded)
        a,b=draws[3:].T
        if family=='checkerboard':expected=(np.sin(3*np.pi*a+np.pi/7)*np.sin(3*np.pi*b+np.pi/5)>0).astype(int)
        elif family=='spiral':expected=(np.sin(2*np.arctan2(b,a)+4*np.pi*np.hypot(a,b))>0).astype(int)
        elif family=='annulus':expected=((a*a+b*b>.25)&(a*a+b*b<.85)).astype(int)
        else:
            distances=[(a+.55)**2+(b+.45)**2,(a-.5)**2+(b+.35)**2,a*a+(b-.55)**2]
            expected=(np.minimum.reduce(distances)<.22**2).astype(int)
        if family=='annulus':expected^=(np.random.Generator(np.random.PCG64(int(streams['annulus_noise']['uint128_decimal']))).random(600)<.1).astype(int)
        np.testing.assert_array_equal(ally[sort],expected)
        ids=[set(p['ids'].tolist()) for p in parts.values()];assert all(ids[i].isdisjoint(ids[j]) for i in range(3) for j in range(i))
        assert all(not ({'clean_y','label_flip'}&set(p)) for p in parts.values())
        records.append({'fixture':'synthetic_'+family,'records':600,'rejected_first_draws':3,'independent_labels_and_rng_match':True,'latent_fields_absent':True})
    rng=np.random.default_rng(5321);raw=rng.normal(size=(303,4));raw=np.vstack((raw,raw[7],raw[7],raw[21]));labels=np.arange(len(raw))%2
    idx,meta=data.grouped_split(raw,labels,4901);again,_=data.grouped_split(raw,labels,4901)
    owner={}
    for split,rows in idx.items():
        np.testing.assert_array_equal(rows,again[split])
        for i in rows:
            key=tuple(raw[i]);assert key not in owner or owner[key]==split;owner[key]=split
    assert sorted(np.concatenate(list(idx.values())).tolist())==list(range(len(raw)))
    prep=routers.fit_preprocessing(raw[idx['train']]);train=raw[idx['train']]
    mean=train.mean(0);scale=train.std(0);z=(train-mean)/scale;z-=z.mean(0)
    values,vectors=np.linalg.eigh(z.T@z);independent_components=vectors[:,np.argsort(values)[::-1][:2]].T
    for row in independent_components:
        if row[np.argmax(abs(row))]<0:row*=-1
    np.testing.assert_allclose(prep['components2x4'],independent_components,atol=2e-13,rtol=0)
    before=json.dumps(prep,sort_keys=True);changed=raw[idx['test']]+1e5
    transformed=routers.preprocess(changed,prep,2);assert np.isfinite(transformed).all() and json.dumps(prep,sort_keys=True)==before
    expected2=(2/np.pi)*np.arctan((((raw-np.array(prep['mean4']))/np.array(prep['scale4'])-np.array(prep['pca_center4']))@independent_components.T-np.array(prep['pc_mean2']))/np.array(prep['pc_scale2']))
    np.testing.assert_allclose(routers.preprocess(raw,prep,2),expected2,rtol=0,atol=2e-13)
    records.append({'fixture':'duplicate_groups_and_PCA','records':len(raw),'group_disjointness':True,'SVD_vs_independent_eigh_agrees':True,'heldout_transform_does_not_refit':True})
    x=rng.uniform(-1,1,(301,2));policy=routers.fit_route_policy(x,7681);centers=np.array(policy['centroids']);d=((x[:,None,:]-centers)**2).sum(2);nearest=d.argmin(1)
    for b in range(5):np.testing.assert_allclose(centers[b],x[nearest==b].mean(0),rtol=0,atol=3e-16)
    ds=np.sort(d,axis=1);assert policy['tau']==max(.001,np.median(ds[:,1]-ds[:,0]))
    probes=np.array([[-2.,3.],[0.,0.],[1.,-1.]])
    expectedphi=np.array([[a**(degree-k)*b**k for degree in (2,3,4) for k in range(degree+1)] for a,b in probes])/np.array(policy['residual_scale'])
    np.testing.assert_array_equal(routers.residual_features(probes,policy),expectedphi)
    records.append({'fixture':'geometric_policy','centroid_means_verified':True,'tau_train_margin_verified':True,'residual_monomial_order_verified':True})
    matrix=data.read_json(root/'governance/RUN_MATRIX.json');runs=matrix['runs'];assert len({r['run_id'] for r in runs})==756
    assert {s:sum(r['stage']==s for r in runs) for s in ('engineering','A','B')}=={'engineering':48,'A':72,'B':636}
    grouped={}
    for row in runs:
        key=(row['population_id'],row['training_seed_id']);streams2=row['paired_streams']
        if key in grouped:assert streams2==grouped[key]
        grouped[key]=streams2
        assert row['updates']==row['rounds']*75 and row['batch_size']==64
    assert sum(r['updates'] for r in runs)+60000==10752000
    records.append({'fixture':'full_matrix_inventory','unique_jobs':756,'full_budget_and_pairing_verified':True})
    receipt={'schema':'qpath-v09-data-independent-source-review-1','status':'PASS_SOURCE_AND_SYNTHETIC_FIXTURES','created_utc':datetime.now(timezone.utc).isoformat(),
      'reviewer':'v09_science (not data author)','sources':[bind(data.__file__),bind(routers.__file__),bind(root/'governance/RUN_MATRIX.json'),bind(root/'governance/STUDY_PLAN.json'),bind(__file__)],
      'checks':records,'official_data_generated':False,'test_model_outcomes_read':False,'limitations':'Source and synthetic qualification only. Exact official data hashes, history exclusion and split payloads require generated-data independent audit before training.'}
    with out.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    print(json.dumps({'status':receipt['status'],'checks':len(records),'receipt':str(out)}))
if __name__=='__main__':main()
