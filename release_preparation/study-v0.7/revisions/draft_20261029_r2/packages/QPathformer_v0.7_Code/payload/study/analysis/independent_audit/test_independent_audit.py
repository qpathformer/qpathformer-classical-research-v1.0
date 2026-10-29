"""Synthetic tests; the numerical reference itself never imports a producer."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import numpy as np

HERE=Path(__file__).resolve().parent
Q=HERE.parents[1]/"quantum"
sys.path.insert(0,str(Q))
sys.path.insert(0,str(HERE))
import models
import reference_v07 as ref
import audit_endpoints_v07 as audit


class IndependentNumericalTests(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.Generator(np.random.PCG64(2026102001))
        self.x=self.rng.uniform(-.85,.85,(15,2))
        self.y=np.array([0,1,0,1,1]*3)
        self.routes=np.arange(15)%5
        self.streams={'paired_circuit_core_initialization':775887,
                      'mlp_initialization':994411}

    def test_all_eight_models_scalar_vector_forward_and_gradient(self):
        for method in ref.METHODS:
            with self.subTest(method=method):
                model=models.Model(method,123,self.streams)
                model.parameters[:]+=self.rng.normal(0,.12,len(model.parameters))
                route=None if method.endswith('_global') else self.routes
                p,z=model.predict_with_logits(self.x,route)
                vector,vz=ref.predict_with_logits(method,model.parameters,self.x,route)
                scalar,sz=ref.scalar_predict_with_logits(method,model.parameters,self.x,route)
                np.testing.assert_allclose(p,vector,atol=2e-12,rtol=0)
                np.testing.assert_allclose(z,vz,atol=1e-9,rtol=0)
                np.testing.assert_allclose(p,scalar,atol=2e-12,rtol=0)
                np.testing.assert_allclose(z,sz,atol=1e-9,rtol=0)
                loss,gradient,_,work=model.gradient(self.x,self.y,route)
                numerical=ref.central_gradient(method,model.parameters,self.x,self.y,route)
                np.testing.assert_allclose(gradient,numerical,atol=2e-8,rtol=0)
                self.assertLessEqual(abs(loss-ref.stable_logit_bce(self.y,vz)),1e-12)
                self.assertEqual(work,audit.expected_work(method,len(self.x),gradient=True))

    def test_explicit_initial_stream_reconstruction_all_methods(self):
        wrapped={k:{'uint128_decimal':str(v)} for k,v in self.streams.items()}
        for method in ref.METHODS:
            model=models.Model(method,123,self.streams)
            parameters,master,core=audit.expected_initial(method,wrapped)
            np.testing.assert_array_equal(model.parameters,parameters)
            np.testing.assert_array_equal(model.master_initial,master)
            np.testing.assert_array_equal(model.core_parameters,core)

    def test_quantum_initial_core_pairing_across_routes_and_heads(self):
        models_=[models.Model(m,123,self.streams) for m in ref.METHODS[:3]]
        cores=[m.parameters.reshape(5,-1)[:,:8] for m in models_]
        np.testing.assert_array_equal(cores[0],cores[1])
        np.testing.assert_array_equal(cores[1],cores[2])

    def test_121_feature_tensor_scalar_reference(self):
        theta=np.arange(121)/121
        x=np.array([[.1,-.9],[0,0],[-1,1.]])
        p,z=ref.predict_with_logits('trig121_global',theta,x)
        q,w=ref.scalar_predict_with_logits('trig121_global',theta,x)
        np.testing.assert_allclose(z,w,atol=1e-12,rtol=0)
        np.testing.assert_allclose(p,q,atol=1e-12,rtol=0)
        self.assertEqual(ref.trig_features(x,5).shape,(3,121))

    def test_threshold_tie_diagnostic_requires_both_inside_band(self):
        y=np.array([0,1]);ids=np.array([1,2])
        result=audit.threshold_check(y,np.array([.5,.5]),np.array([.5-1e-16,.5]),ids)
        self.assertEqual(result['class_disagreements'],1)
        with self.assertRaises(RuntimeError):
            audit.threshold_check(y,np.array([.5,.5]),np.array([.5-1e-13,.5]),ids)

    def test_native_extreme_loss_stays_finite(self):
        z=np.array([-1000.,1000.]);y=np.array([1,0])
        self.assertEqual(ref.stable_logit_bce(y,z),1000.)

    def test_invalid_method_routes_and_state_sizes_fail(self):
        for args in [('unknown',np.zeros(1),self.x,None),
                     ('qmulti_hash',np.zeros(70),self.x,None),
                     ('trig121_global',np.zeros(25),self.x,None),
                     ('mlp_global',np.zeros(129),self.x,self.routes)]:
            with self.assertRaises((ValueError,TypeError)):ref.predict_with_logits(*args)

    def test_metric_check_rejects_edited_summary(self):
        import study
        p=np.linspace(.05,.95,len(self.y))
        canonical=study.metrics(self.y,p);independent=ref.metrics(self.y,p)
        audit.metric_check(independent,canonical)
        altered=copy.deepcopy(canonical);altered['bce']+=1e-3
        with self.assertRaises(RuntimeError):audit.metric_check(independent,altered)

    def test_commit_hash_inventory_and_test_access_are_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix='v07_audit_commit_fixture_') as name:
            folder=Path(name);payload=folder/'fixture.txt';payload.write_text('synthetic only',encoding='utf-8')
            c={'status':'completed','test_accessed':False,'files':{'fixture.txt':audit.binding(payload)}}
            commit=folder/'endpoint_commit.json';commit.write_text(json.dumps(c),encoding='utf-8')
            audit.check_commit(folder)
            payload.write_text('tampered',encoding='utf-8')
            with self.assertRaises(RuntimeError):audit.check_commit(folder)
            payload.write_text('synthetic only',encoding='utf-8')
            c['test_accessed']=True;commit.write_text(json.dumps(c),encoding='utf-8')
            with self.assertRaises(RuntimeError):audit.check_commit(folder)

    def test_checkpoint_rejects_optimizer_count_and_nonfinite_moment(self):
        with tempfile.TemporaryDirectory(prefix='v07_audit_state_fixture_') as name:
            path=Path(name)/'checkpoint.npz'
            state=np.arange(25,dtype=np.float64);p=np.array([.2,.8]);z=np.log(p/(1-p))
            fields=dict(parameters=state,core_parameters=np.empty(0),adam_m=np.zeros(25),adam_v=np.ones(25),
                        adam_t=150,current_round=2,completed_rounds=2,validation_evidence_present=True,
                        validation_probabilities=p,has_native_logits=True,validation_logits=z,
                        validation_native_loss=np.array([.2]))
            np.savez(path,**fields);audit.checkpoint(path,state,2,25,np.empty(0),p,z,.2)
            fields['adam_t']=149;np.savez(path,**fields)
            with self.assertRaises(RuntimeError):audit.checkpoint(path,state,2,25,np.empty(0),p,z,.2)
            fields['adam_t']=150;fields['adam_m'][1]=np.nan;np.savez(path,**fields)
            with self.assertRaises(RuntimeError):audit.checkpoint(path,state,2,25,np.empty(0),p,z,.2)


if __name__=='__main__':
    unittest.main(verbosity=2)
