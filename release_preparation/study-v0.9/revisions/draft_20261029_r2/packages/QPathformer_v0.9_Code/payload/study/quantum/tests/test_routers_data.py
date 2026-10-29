"""Data qualification on small in-memory fixtures; no official data generation."""
import ast, hashlib, json, sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import prepare_data as data
import routers as rt

def stream(role):
    n='QPATH-v09-DATA-UNIT-FIXTURE|'+role
    return {'namespace':n,'uint128_decimal':str(int.from_bytes(hashlib.sha256(n.encode()).digest()[:16],'little'))}

class DataTests(unittest.TestCase):
    def test_inherited_task_formula_and_generation(self):
        old=ast.parse(Path(r'C:\Anthony Siljeg\Q2_improvement_study_v08\quantum\prepare_data.py').read_text(encoding='utf-8-sig'))
        new=ast.parse(Path(data.__file__).read_text())
        extract=lambda t,n:ast.dump(next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name==n),include_attributes=False)
        for n in ['_allocate','labels_for','generate']:self.assertEqual(extract(old,n),extract(new,n),n)

    def test_inherited_kmeans_core(self):
        old=ast.parse(data.OLD_ROUTER.read_text(encoding='utf-8-sig'));new=ast.parse(Path(rt.__file__).read_text())
        names=['_distance','_canonical_order','_initial_centers','_lloyd']
        extract=lambda t,n:ast.dump(next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name==n),include_attributes=False)
        for n in names:self.assertEqual(extract(old,n),extract(new,n),n)

    def test_geometric_temperature_and_residual(self):
        x=np.random.default_rng(33).uniform(-1,1,(160,2));policy=rt.fit_route_policy(x,91)
        centers=np.array(policy['centroids']);dist=((x[:,None]-centers)**2).sum(2)
        self.assertTrue(np.array_equal(rt.route(x,policy),np.argmin(dist,axis=1)))
        ds=np.sort(dist,axis=1);self.assertEqual(policy['tau'],max(.001,np.median(ds[:,1]-ds[:,0])))
        q=rt.soft_weights(x,policy)
        expected=np.exp(-dist/policy['tau']-np.max(-dist/policy['tau'],axis=1)[:,None]);expected/=expected.sum(1)[:,None]
        np.testing.assert_allclose(q,expected,atol=1e-15,rtol=1e-15)
        np.testing.assert_allclose(q.sum(1),1,atol=1e-15,rtol=0)
        probe=np.array([[.2,-.3]]);r=rt.residual_features(probe,policy)[0]
        np.testing.assert_allclose(r,[.04,-.06,.09,.008,-.012,.018,-.027,.0016,-.0024,.0036,-.0054,.0081],atol=1e-16)
        before=json.dumps(policy,sort_keys=True);rt.soft_weights(np.ones((3,2))*17,policy);rt.margin_bins(np.zeros((4,2)),policy)
        self.assertEqual(before,json.dumps(policy,sort_keys=True))
        # Original k-means canonicalization makes training row permutation irrelevant.
        again=rt.fit_route_policy(x[::-1],91)
        self.assertEqual(policy['centroids'],again['centroids'])

    def test_duplicate_grouping_and_conflicts(self):
        rng=np.random.default_rng(76);raw=rng.normal(size=(91,4));y=np.arange(91)%2
        raw=np.vstack([raw,raw[3],raw[3],raw[10]]);y=np.r_[y,1-y[3],y[3],y[10]]
        idx,report=data.grouped_split(raw,y,842);again,_=data.grouped_split(raw,y,842)
        sets=[]
        for name,rows in idx.items():
            np.testing.assert_array_equal(rows,again[name]);sets.append(set(data.raw4_keys(raw[rows])))
        for i in range(3):
            for j in range(i):self.assertTrue(sets[i].isdisjoint(sets[j]))
        self.assertEqual(len(report['conflicting_groups']),1)
        self.assertEqual(report['duplicate_extra_rows'],3)
        self.assertEqual(sum(map(len,idx.values())),len(raw))
        for count,target in zip(report['counts'].values(),[.6,.2,.2]):self.assertLess(abs(count/len(raw)-target),.05)

    def test_train_only_pca_and_constant_feature(self):
        rng=np.random.default_rng(18);train=rng.normal(size=(120,4));train[:,3]=4
        prep=rt.fit_preprocessing(train);before=json.dumps(prep,sort_keys=True)
        x=rt.preprocess(train,prep,2);x4=rt.preprocess(train,prep,4)
        self.assertEqual(x.shape,(120,2));self.assertEqual(x4.shape,(120,4))
        np.testing.assert_array_equal(x4[:,3],0)
        self.assertTrue(np.all(abs(x)<1));self.assertTrue(0<=prep['retained_variance']<=1)
        loadings=np.asarray(prep['components2x4'])
        for row in loadings:self.assertGreaterEqual(row[np.argmax(abs(row))],0)
        np.testing.assert_allclose(loadings@loadings.T,np.eye(2),atol=1e-14)
        rt.preprocess(rng.normal(100,20,(50,4)),prep,2)
        self.assertEqual(before,json.dumps(prep,sort_keys=True))
        # Verify full projection independently from saved coefficients.
        standardized=(train-np.array(prep['mean4']))/np.array(prep['scale4'])
        pc=(standardized-np.array(prep['pca_center4']))@loadings.T
        expected=2/np.pi*np.arctan((pc-np.array(prep['pc_mean2']))/np.array(prep['pc_scale2']))
        np.testing.assert_array_equal(x,expected)

    def test_synthetic_freshness_latent_and_replay(self):
        pop={'family':'annulus','proposed_streams':{r:stream(r) for r in ['coordinates','annulus_noise','split','record_ids']}}
        counts={'train':60,'validation':20,'test':20}
        parts,latent,meta,keys=data.generate(pop,set(),10000,n=100,counts=counts)
        again,_,_,_=data.generate(pop,set(),10000,n=100,counts=counts)
        for name,p in parts.items():
            self.assertFalse({'clean_y','label_flip'}&set(p))
            np.testing.assert_array_equal(p['x'],again[name]['x'])
            np.testing.assert_array_equal(p['y'],latent[name]['clean_y']^latent[name]['label_flip'])
        self.assertEqual(len(keys),100)
        blocked={next(iter(keys))};_,_,report,newkeys=data.generate(pop,blocked,10000,n=100,counts=counts)
        self.assertTrue(newkeys.isdisjoint(blocked));self.assertEqual(len(report['rejected']),1)

    def test_matrix_extent_and_stream_pairing(self):
        matrix=data.read_json(data.GOV/'RUN_MATRIX.json');streams=data.all_matrix_streams(matrix)
        self.assertEqual(len(streams),531)
        self.assertEqual({s:sum(r['stage']==s for r in matrix['runs']) for s in ['engineering','A','B']},{'engineering':48,'A':72,'B':636})
        groups={}
        for run in matrix['runs']:
            key=(run['stage'],run['population_id'],run['training_seed_id'])
            if key in groups:self.assertEqual(groups[key],run['paired_streams'])
            groups[key]=run['paired_streams']
        self.assertEqual(sum(r['updates'] for r in matrix['runs'])+4*15000,10752000)

    def test_generation_fails_without_approval(self):
        # Reject before any output creation; don't invoke official generation.
        with self.assertRaises(ValueError):data.validate_generation_approval({}, {}, {})

if __name__=='__main__':unittest.main()
