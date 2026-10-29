import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
import numpy as np
import circuits
import reference_v03
import models
import study
import tempfile


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.Generator(np.random.PCG64(960601))
        self.x=self.rng.uniform(-.8,.8,(13,2));self.y=np.arange(13)%2
        self.route=np.arange(13)%4 # Bank4 absent.

    def test_shapes_and_paired_initial_predictions(self):
        counts=(50,70,165,125,25,129)
        self.assertEqual(len(models.METHODS),len(counts))
        for name,count in zip(models.METHODS,counts):
            model=models.Model(name,1101)
            self.assertEqual(model.parameters.size,count)
            self.assertTrue(model.native_logits)
            self.assertFalse(model.legacy or model.frozen)
        arms=[models.Model(n,1101) for n in ('qscalar_kmeans','qmulti_kmeans')]
        np.testing.assert_array_equal(arms[0].master_initial,arms[1].master_initial)
        np.testing.assert_allclose(arms[0].predict(self.x,self.route),arms[1].predict(self.x,self.route),atol=2e-16,rtol=0)
        self.assertFalse(np.array_equal(arms[0].master_initial[0],arms[0].master_initial[1]))
        for removed in ('q2_kmeans','qfrozen_kmeans','mlp4relu_kmeans','mlp8relu_kmeans'):
            with self.assertRaises(ValueError):models.Model(removed,1101)

    def test_moments_and_state_against_independent_matrices(self):
        I=np.eye(2);X=np.array([[0,1],[1,0]]);Z=np.diag([1,-1])
        ops=[np.kron(X,I),np.kron(I,X),np.kron(Z,I),np.kron(I,Z),np.kron(Z,Z)]
        for _ in range(80):
            x=self.rng.uniform(-1,1,(1,2));bank=self.rng.uniform(-np.pi,np.pi,(2,2,2))
            state=reference_v03.unitary(x[0],bank,2,beta=0)[:,0]
            np.testing.assert_allclose(circuits.core_state(x,bank)[0],state,atol=2e-12,rtol=0)
            expected=np.array([np.real(np.vdot(state,P@state)) for P in ops])
            np.testing.assert_allclose(circuits.moments(x,bank)[0],expected,atol=2e-12,rtol=0)
            np.testing.assert_array_equal(circuits.moments(x,bank,1)[0],circuits.moments(x,bank,5)[0,:1])
            self.assertLessEqual(abs(circuits.predict(x,bank,2)[0]-(1+expected[0])/2),2e-12)

    def test_native_gradients_all_arms_and_absent_bank(self):
        for name in models.METHODS:
            model=models.Model(name,1101);route=None if model.routing=='global' else self.route
            if model.family=='trig':model.parameters[:]=self.rng.uniform(-.1,.1,model.parameters.size)
            if model.family in ('qscalar','qmulti','qfrozen'):
                model.parameters[:]+=self.rng.uniform(-.04,.04,model.parameters.size)
            loss,g,prob,work=model.gradient(self.x,self.y,route);numeric=np.zeros_like(g);h=1e-6
            for j in range(len(g)):
                before=model.parameters[j];model.parameters[j]=before+h
                p,z=model.predict_with_logits(self.x,route);plus=model.loss(self.y,p,z)
                model.parameters[j]=before-h;p,z=model.predict_with_logits(self.x,route);minus=model.loss(self.y,p,z)
                model.parameters[j]=before;numeric[j]=(plus-minus)/(2*h)
            np.testing.assert_allclose(g,numeric,atol=2e-7,rtol=2e-5,err_msg=name)
            if model.banks==5:np.testing.assert_array_equal(g[-model.bank_width:],0.)

    def test_wrong_saturated_logits_keep_gradient(self):
        for name in models.METHODS:
            model=models.Model(name,1101)
            if model.legacy:continue
            x=np.zeros((4,2));route=None if model.routing=='global' else np.zeros(4,dtype=int)
            for sign in (-1,1):
                model.parameters[:]=0
                coordinate=0 if model.family=='trig' else model.bank_width-1
                model.parameters[coordinate]=sign*100
                y=np.full(4,int(sign<0));loss,g,p,_=model.gradient(x,y,route)
                self.assertAlmostEqual(loss,100.,places=12);self.assertAlmostEqual(g[coordinate],sign,places=12)
                self.assertGreater(loss,models.binary_cross_entropy(y,p)+80)

    def test_native_gradient_continuity_across_probability_clip(self):
        m=models.Model('trig_global',1101);x=np.zeros((2,2));y=np.array([0,1])
        boundary=np.log(models.CLIP/(1-models.CLIP))
        for z in (boundary-1e-6,boundary,boundary+1e-6,-boundary-1e-6,-boundary,-boundary+1e-6):
            m.parameters[:]=0;m.parameters[0]=z
            loss,g,p,_=m.gradient(x,y)
            self.assertAlmostEqual(g[0],float(np.mean(p-y)),places=14)
            h=1e-5;m.parameters[0]=z+h;plus=m.loss(y,*m.predict_with_logits(x))
            m.parameters[0]=z-h;minus=m.loss(y,*m.predict_with_logits(x));m.parameters[0]=z
            self.assertAlmostEqual(g[0],(plus-minus)/(2*h),places=9)

    def test_feature_cache_is_rejected_in_every_registered_arm(self):
        features=np.zeros((len(self.x),5))
        for name in models.METHODS:
            model=models.Model(name,1101)
            with self.assertRaises(ValueError):model.predict(self.x,None,features)

    def test_actual_forward_and_shift_accounting(self):
        for name in ('qscalar_kmeans','qmulti_kmeans'):
            m=models.Model(name,1101);calls=[];original=circuits.core_state if not m.legacy else circuits.predict
            def counted(x,*args,**kwargs):calls.append(len(x));return original(x,*args,**kwargs)
            with patch.object(circuits,'predict' if m.legacy else 'core_state',counted):
                loss,g,p,w=m.gradient(self.x,self.y,self.route)
            self.assertEqual(sum(calls),w['circuit_examples'],name)
            self.assertEqual(w['circuit_examples'],len(self.x)*(1 if m.frozen else 17))
            self.assertEqual(w['readout_ry_gates'],w['circuit_examples'] if m.legacy else 0)
        m=models.Model('trig_kmeans',1101);seen=[];original=models.trig_features
        def counted(x):seen.append(len(x));return original(x)
        with patch.object(models,'trig_features',counted):w=m.gradient(self.x,self.y,self.route)[3]
        self.assertEqual(sum(seen)*25,w['trig_feature_values']);self.assertEqual(sum(seen),len(self.x))

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):models.Model('qscalar_hash',1101)
        with self.assertRaises(ValueError):models.Model('qmulti_kmeans',1101).predict(self.x,np.full(13,5))
        with self.assertRaises(ValueError):models.Model('mlp_global',1101).predict(self.x,self.route)
        with self.assertRaises(ValueError):models.logit_cross_entropy(np.array([2]),np.array([0.]))


class TrainerEvidenceTests(unittest.TestCase):
    def test_calibration_decimal_boundaries_and_empty_bins(self):
        edges=np.linspace(0,1,11);p=np.r_[edges,np.nextafter(edges[1:-1],0)]
        y=np.arange(len(p))%2;result=study.metrics(y,p)
        bins=np.minimum(np.searchsorted(edges,p,side='right')-1,9)
        self.assertEqual(len(result['reliability10']),10)
        self.assertEqual([r['count'] for r in result['reliability10']],np.bincount(bins,minlength=10).tolist())
        sparse=study.metrics(np.array([0,1]),np.array([0.,1.]))
        self.assertEqual(sparse['ece10'],0.);self.assertEqual(sparse['brier'],0.)
        self.assertIsNone(sparse['reliability10'][5]['mean_probability'])

    def test_full_small_synthetic_trainer_artifacts_all_arms(self):
        # This is generated test data in a temporary fixture, never a registered population.
        import routers
        import audit_stage
        rng=np.random.Generator(np.random.PCG64(690651));x=rng.uniform(-1,1,(224,2))
        policy=routers.fit_route_policy(x[:64],690652)
        with tempfile.TemporaryDirectory(prefix='qpath_v06_synthetic_') as name:
            root=Path(name);data=root/'data';data.mkdir();(root/'tests').mkdir()
            for source in ('models.py','study.py','circuits.py','reference_v03.py','prepare_data.py','routers.py','launch_stage.py'):
                (root/source).write_text('synthetic source identity placeholder\n')
            population='engineering_checkerboard';policy_path=data/f'{population}_router.json';study.write_json(policy_path,policy,True)
            files={}
            for split,ids in (('train',np.arange(64)),('validation',np.arange(64,224))):
                f=data/f'{population}_{split}.npz';xx=x[ids]
                np.savez(f,x=xx,y=(xx[:,0]*xx[:,1]>0).astype(np.int64),ids=ids,source_draw_ids=ids,
                         hash_route=routers.route(xx,policy,'hash'),kmeans_route=routers.route(xx,policy,'kmeans'),
                         clean_y=np.full(len(ids),999,dtype=np.int64),label_flip=np.ones(len(ids),dtype=bool))
                files[f.name]={'sha256':study.digest(f)}
            seal={'files':files,'routers':{population:{'sha256':study.digest(policy_path)}},
                  'datasets':{population:{'generation_seconds':0.,'router_fit_seconds':0.,
                  'route_application_seconds_by_split':{k:{'hash':0.,'kmeans':0.} for k in ('train','validation')}}}}
            study.write_json(data/'DATA_SEAL.json',seal,True)
            with patch.object(study,'ROOT',root):
                with self.assertRaises(ValueError):study.load_population(population,'test')
                loaded=study.load_population(population,'train')
                self.assertNotIn('clean_y',loaded);self.assertNotIn('label_flip',loaded)
                with self.assertRaises(RuntimeError):study.train('trig_global',1101,'A','development_checkerboard',root/'forbidden')
                self.assertFalse((root/'forbidden').exists())
                for method in models.METHODS:
                    out=root/method;r=study.train(method,690653,'A',population,out,rounds=1,engineering=True)
                    self.assertEqual(r['study_id'],'QPATH-GENERALIZATION-v0.6');self.assertEqual(r['optimizer_global_updates'],1)
                    self.assertEqual(r['fixed_core_parameter_count'],0)
                    self.assertTrue((out/'validation_logits.npy').exists())
                    ledger=study.read_json(out/'ledger.jsonl');self.assertEqual(ledger['validation_native']['native_bce'],np.load(out/'validation_native_losses.npy')[0])
                    self.assertGreaterEqual(ledger['training_forward_extrema']['minimum_raw_probability'],0)
                    self.assertLessEqual(ledger['training_forward_extrema']['maximum_raw_probability'],1)
                    with np.load(out/'selected_checkpoint.npz') as c:
                        np.testing.assert_array_equal(c['validation_probabilities'],np.load(out/'validation_probabilities.npy')[0])
                        self.assertEqual(int(c['adam_t']),1);self.assertTrue(c['validation_evidence_present'])
                        self.assertEqual(c['core_parameters'].size,0)
                    commit=study.read_json(out/'endpoint_commit.json')
                    for f,meta in commit['files'].items():self.assertEqual(study.digest(out/f),meta['sha256'])
                    audit=audit_stage.audit_endpoint(out,'A',population,690653,method,engineering=True)
                    self.assertEqual(audit['validation_rounds_replayed'],1)
                    with self.assertRaises(FileExistsError):study.train(method,690653,'A',population,out,rounds=1,engineering=True)


if __name__=='__main__':unittest.main()
