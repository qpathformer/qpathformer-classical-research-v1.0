"""Synthetic-only compilation qualification; official outcomes remain sealed."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
import sys,unittest,tempfile,json
from unittest.mock import patch
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compiler import *
from models import Model
from routers import fit_route_policy,fit_preprocessing
from timing import ordered_jobs
import support
class CompilationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen=np.random.default_rng(923117);cls.policy=fit_route_policy(cls.gen.uniform(-1,1,(400,2)),8831);cls.streams={'paired_circuit_core_initialization':55321,'mlp_initialization':83901};cls.x=cls.gen.uniform(-1,1,(601,2))
    def test_all_four_complete_pipelines_and_forced_banks(self):
        for arm in CIRCUIT_ARMS:
            model=Model(arm,1,self.streams,self.policy);model.parameters[:70]=self.gen.normal(size=70)
            if model.extra_size:model.parameters[70:]=self.gen.normal(0,.4,12)
            coef,extra,grid=compile_parameters(arm,model.parameters);compiled=Compiled(arm,coef,extra,self.policy)
            self.assertEqual(coef.shape,(5,25));self.assertEqual(grid.shape,(5,25));np.testing.assert_array_equal(extra,model.parameters[70:])
            parity(*compiled.predict_with_logits(self.x),*model.predict_with_logits(self.x))
            forced=np.column_stack([model._expert(self.x,t)[0] for t in model.parameters[:70].reshape(5,14)])
            np.testing.assert_allclose(compiled.core_logits(self.x),forced,atol=3e-14,rtol=0)
            offgrid,boundary=probes(self.policy,3881);self.assertEqual(offgrid.shape,(257,2));self.assertEqual(boundary.shape,(30,2))
            parity(*compiled.predict_with_logits(boundary),*model.predict_with_logits(boundary))
    def test_preserves_learned_gate_and_residual_effect(self):
        for arm in ('C_L','C_R'):
            m=Model(arm,1,self.streams,self.policy);m.parameters[:70]=self.gen.normal(size=70);m.parameters[70:]=self.gen.normal(size=12);c,e,_=compile_parameters(arm,m.parameters);v=Compiled(arm,c,e,self.policy);zero=Compiled(arm,c,np.zeros(12),self.policy)
            self.assertGreater(float(abs(v.predict_with_logits(self.x)[0]-zero.predict_with_logits(self.x)[0]).max()),1e-3)
            parity(*v.predict_with_logits(self.x),*m.predict_with_logits(self.x))
    def test_raw_four_feature_preprocessing_included(self):
        raw=self.gen.normal(size=(91,4));policy=dict(self.policy);policy['preprocessing']=fit_preprocessing(raw[:60]);m=Model('C_L',1,self.streams,policy);m.parameters[70:]=self.gen.normal(size=12);c,e,_=compile_parameters(m.method,m.parameters);converted=Compiled(m.method,c,e,policy)
        parity(*converted.predict_raw(raw),*original_raw(m,raw,policy))
    def test_fail_closed_shapes_classes_and_altered_conversion(self):
        with self.assertRaises(ValueError):compile_parameters('T_L',np.zeros(137))
        with self.assertRaises(ValueError):compile_parameters('C_L',np.zeros(70))
        with self.assertRaises(RuntimeError):parity(np.array([.5]),np.array([0.]),np.array([.49999999999]),np.array([-1e-10]))
        with self.assertRaises(RuntimeError):parity(np.array([.2]),np.array([-1.]),np.array([.3]),np.array([-.5]))
    def test_full_timing_inventory_order_and_sessions(self):
        import json
        root=Path(__file__).resolve().parents[3];matrix=json.loads((root/'governance/RUN_MATRIX.json').read_text());jobs=[x for x in matrix['runs'] if x['stage']=='B'];seen=[]
        for session in (1,2,3):
            ordered=ordered_jobs(jobs,matrix,session);self.assertEqual(len(ordered),636);self.assertEqual({x['run_id'] for x in ordered},{x['run_id'] for x in jobs});self.assertEqual(ordered,ordered_jobs(jobs,matrix,session));seen.append([x['run_id'] for x in ordered]);representations=sum(1+(x['arm'] in CIRCUIT_ARMS) for x in ordered);self.assertEqual(representations,912);self.assertEqual(representations*3*15,41040);self.assertEqual(representations*3*2,5472)
        self.assertNotEqual(seen[0],seen[1]);self.assertNotEqual(seen[1],seen[2])
    def test_router_tampering_rejected_before_checkpoint_or_prediction(self):
        with tempfile.TemporaryDirectory(prefix='v09_router_binding_') as tmp:
            root=Path(tmp);folder=root/'quantum/data';folder.mkdir(parents=True);policy=folder/'fixture_router.json';policy.write_text(json.dumps(self.policy));expected=support.sha(policy);policy.write_text(json.dumps({**self.policy,'tau':self.policy['tau']+.1}))
            with patch.object(support,'ROOT',root),patch.object(support,'endpoint',return_value=(root,{})):
                with self.assertRaisesRegex(RuntimeError,'Frozen router policy changed'):support.load_model({'run_id':'fixture','population_id':'fixture'},{'seal':{'routers':{'fixture':{'sha256':expected}}}})
    def test_canonical_score_replay_receipt_binding(self):
        commit={'path':'fixture/EVALUATION_COMMIT.json','sha256':'a'*64,'bytes':101}
        for schema in ('qpath-v09-independent-analysis-1','qpath-v09-independent-analysis-commit-1'):
            receipt={'schema':schema,'status':'PASS','verified_endpoints':636,'author_evaluation_commit':commit}
            support.verify_score_replay(receipt,commit)
            support.verify_score_replay({**receipt,'evaluation_commit':commit},commit)
            with self.assertRaisesRegex(RuntimeError,'Conflicting legacy'):support.verify_score_replay({**receipt,'evaluation_commit':{**commit,'sha256':'b'*64}},commit)
            with self.assertRaisesRegex(RuntimeError,'exact official'):support.verify_score_replay({**receipt,'author_evaluation_commit':{**commit,'sha256':'b'*64}},commit)
            with self.assertRaisesRegex(RuntimeError,'incomplete'):support.verify_score_replay({**receipt,'verified_endpoints':635},commit)
if __name__=='__main__':unittest.main(verbosity=2)
