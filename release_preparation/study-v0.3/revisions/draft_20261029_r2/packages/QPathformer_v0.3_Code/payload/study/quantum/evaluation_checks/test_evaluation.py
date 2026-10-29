"""Synthetic/engineering-only checks, outside immutable training test glob."""
import contextlib
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import qstudy as s
import replay
import audit_stage
import evaluation_stats as stats
import evaluate_confirmation as e
import numerical_verification as numerical


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')


class GateFixture:
    def __init__(self,base):
        self.root=base/'quantum';self.root.mkdir();self.protocol=base/'governance/ANALYSIS_PROTOCOL.json'
        put(self.protocol,{'synthetic':True});self.protocol_sha=s.digest(self.protocol)
        self.numerical_protocol=base/'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json'
        self.numerical_protocol.write_bytes(numerical.PROTOCOL_PATH.read_bytes())
        self.sentinel=self.root/'sentinel.py';self.sentinel.write_text('# synthetic source',encoding='utf-8')
        self.sources={'sentinel.py':s.digest(self.sentinel)}
        self.auditor=base/'analysis/classical_review/audit_endpoints_v03.py';self.auditor.parent.mkdir(parents=True)
        self.auditor.write_text('# synthetic auditor',encoding='utf-8')
        put(self.root/'STAGE_B_FREEZE.json',{'synthetic':True});put(self.root/'data/DATA_SEAL.json',{'synthetic':True})
        self.reg=self.root/'EVALUATION_REGISTRATION.json';self.lock=self.root/'CONFIRMATION_ENDPOINT_LOCK.json'
        self.review=self.root/'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json';self.release=self.root/'EVALUATION_RELEASE.json'
        self.output=self.root/'confirmation_evaluation';self.audit=base/'analysis/classical_review/B.json'
        rows=[]
        for seed in s.SEEDS['B']:
            for method in s.METHODS:
                folder=self.root/'stage_B'/f'seed_{seed}'/method;folder.mkdir(parents=True)
                for filename in e.ENDPOINT_FILES.values():(folder/filename).write_text('synthetic payload',encoding='utf-8')
                put(folder/'result.json',{'status':'completed','completed_rounds':200,'optimizer_global_updates':15000,
                                        'method':method,'seed':seed,'stage':'B','engineering':False})
                put(folder/'status.json',{'status':'completed','round':200})
                rows.append({'seed':seed,'method':method,'path':folder.relative_to(self.root).as_posix(),
                             **{k:s.digest(folder/v) for k,v in e.ENDPOINT_FILES.items()}})
        put(self.lock,{'status':'PASS','stage':'B','endpoint_count':65,'test_accessed':False,
             'numerical_recovery_protocol_sha256':numerical.PROTOCOL_SHA,
             'stage_freeze_sha256':s.digest(self.root/'STAGE_B_FREEZE.json'),'data_seal_sha256':s.digest(self.root/'data/DATA_SEAL.json'),
             'training_source_hashes':self.sources,'audit_sources':self.sources,'endpoints':rows,'created_utc':'2026-01-01T00:00:00+00:00'})
        put(self.audit,{'status':'PASS','stage':'B','endpoint_count':65,'endpoint_lock_sha256':s.digest(self.lock),
                       'numerical_recovery_protocol_sha256':numerical.PROTOCOL_SHA,
                       'auditor_sha256':s.digest(self.auditor),'created_utc':'2026-01-01T00:01:00+00:00'})
        put(self.review,{'status':'PASS','stage':'B','endpoint_count':65,'endpoint_lock_sha256':s.digest(self.lock),
                         'independent_audit_path':self.audit.relative_to(base).as_posix(),'independent_audit_sha256':s.digest(self.audit)})
        put(self.reg,{'status':'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS','analysis_protocol_sha256':self.protocol_sha,
                     'numerical_recovery_protocol_sha256':numerical.PROTOCOL_SHA,
                     'data_seal_sha256':s.digest(self.root/'data/DATA_SEAL.json'),
                     'method_order':list(s.METHODS),'training_seeds':list(s.SEEDS['B']),
                     'readout':{'methods':list(e.READOUT_METHODS),'budgets':list(e.BUDGETS),'shot_seeds':list(e.SHOT_SEEDS)},
                     'source_hashes':self.sources,'training_source_hashes':self.sources,
                     'external_source_hashes':{'analysis/classical_review/audit_endpoints_v03.py':s.digest(self.auditor)},
                     'expected_output_paths':sorted(e.expected_output_paths())})
        self.rebind_release()

    def rebind_release(self):
        put(self.release,{'status':'released_by_root','study_id':'QPATH-QMECH-v0.3','scope':'all_65_registered_confirmation_endpoints_once',
             'release_id':'synthetic-release','created_utc':'2026-01-01T00:02:00+00:00','registration_sha256':s.digest(self.reg),
             'endpoint_lock_sha256':s.digest(self.lock),'independent_endpoint_review_sha256':s.digest(self.review),
             'stage_freeze_sha256':s.digest(self.root/'STAGE_B_FREEZE.json'),'data_seal_sha256':s.digest(self.root/'data/DATA_SEAL.json'),
             'analysis_protocol_sha256':self.protocol_sha})
        release=s.read_json(self.release);release['numerical_recovery_protocol_sha256']=numerical.PROTOCOL_SHA;put(self.release,release)

    def patch(self):
        stack=contextlib.ExitStack()
        for name,value in [('ROOT',self.root),('PROTOCOL',self.protocol),('PROTOCOL_SHA',self.protocol_sha),('REGISTRATION',self.reg),
                           ('LOCK',self.lock),('REVIEW',self.review),('RELEASE',self.release),('OUTPUT',self.output)]:stack.enter_context(patch.object(e,name,value))
        stack.enter_context(patch.object(s,'source_hashes',return_value=self.sources));stack.enter_context(patch.object(s,'verify_freeze',return_value={}))
        stack.enter_context(patch.object(numerical,'PROTOCOL_PATH',self.numerical_protocol))
        return stack


class EvaluationChecks(unittest.TestCase):
    def test_closed_form_work_and_replay_all_engineering_methods(self):
        population=s.load_population('engineering','validation');tiny={k:v[:13] for k,v in population.items()}
        for method in s.METHODS:
            model=s.Model(method,9501)
            with np.load(s.ROOT/'engineering_pilot_v02'/method/'selected_checkpoint.npz') as cp:model.parameters[:]=cp['parameters']
            for gradient in (False,True):self.assertEqual(audit_stage.expected_work(method,tiny,gradient),model.accounting(tiny['x'],tiny['depth'],model.route_for(tiny),gradient))
            self.assertLess(float(np.max(abs(model.predict_population(tiny)-replay.predict(method,model.parameters,tiny['x'],tiny['depth'],tiny['hash_route'],tiny['kmeans_route'])))),1e-12)

    def test_metrics_edge_cases(self):
        for y,p in [(np.zeros(8,int),np.zeros(8)),(np.ones(8,int),np.ones(8)),(np.arange(8)%2,np.full(8,.5))]:
            actual=stats.metrics_array(y,p);expected=replay.metrics(y,p)
            np.testing.assert_allclose(actual,[expected[k] for k in stats.METRICS],atol=1e-12)

    def test_paired_bootstrap_identity(self):
        y=np.array([0,1,1,0]);base=np.array([.1,.8,.6,.4]);p=np.broadcast_to(base,(2,5,4)).copy()
        boot=stats.paired_bootstrap(y,p,31,98003)
        self.assertEqual(boot.shape,(31,2,3));np.testing.assert_array_equal(boot[:,0],boot[:,1])
        self.assertEqual(stats.describe(np.zeros(5))['t_interval'],[0.,0.])

    def test_gate_no_test_payload_needed(self):
        with tempfile.TemporaryDirectory(prefix='qpath_v03_guard_synthetic_') as tmp:
            f=GateFixture(Path(tmp))
            with f.patch():reg,lock,release,watched=e.verify_guard()
            self.assertEqual(len(lock['endpoints']),65);self.assertFalse((f.root/'data/confirmation_SEALED_test.npz').exists())

    def test_gate_rejects_mutations_before_data_access(self):
        for mutation in ('missing_release','changed_endpoint','adapter_missing_audit','changed_auditor','duplicate_identity','premature_release','existing_output','missing_recovery_release_binding','changed_recovery_protocol'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory(prefix='qpath_v03_guard_synthetic_') as tmp:
                f=GateFixture(Path(tmp))
                if mutation=='missing_release':f.release.unlink()
                elif mutation=='changed_endpoint':(f.root/'stage_B/seed_601/scheduled/ledger.jsonl').write_text('changed')
                elif mutation=='adapter_missing_audit':
                    r=s.read_json(f.review);del r['independent_audit_path'];put(f.review,r);f.rebind_release()
                elif mutation=='changed_auditor':f.auditor.write_text('# changed')
                elif mutation=='duplicate_identity':
                    lock=s.read_json(f.lock);lock['endpoints'][-1]=lock['endpoints'][0];put(f.lock,lock);f.rebind_release()
                elif mutation=='premature_release':
                    release=s.read_json(f.release);release['created_utc']='2025-01-01T00:00:00+00:00';put(f.release,release)
                elif mutation=='missing_recovery_release_binding':
                    release=s.read_json(f.release);del release['numerical_recovery_protocol_sha256'];put(f.release,release)
                elif mutation=='changed_recovery_protocol':f.numerical_protocol.write_text('changed')
                else:f.output.mkdir()
                with f.patch(),self.assertRaises((RuntimeError,FileNotFoundError,KeyError)):e.verify_guard()
                self.assertFalse((f.root/'data/confirmation_SEALED_test.npz').exists())

    def test_numerical_ambiguity_and_all_four_sensitivities(self):
        pop={'y':np.array([0,1,1,0]),'ids':np.arange(4),'depth':np.arange(1,5),'hash_route':np.arange(4),'kmeans_route':np.arange(4)}
        p=np.array([.5,.5,.9,.1]);r=p.copy();r[0]-=numerical.BAND/2;r[1]+=numerical.BAND/2
        result=numerical.verify_pair(pop,p,r)
        self.assertEqual(result['counts']['class_disagreements'],1);self.assertFalse(result['counts']['exact_class_agreement'])
        self.assertEqual(result['counts']['canonical_near_band'],2);self.assertEqual(len(result['disagreements']),1)
        self.assertEqual(result['sensitivity']['all_ambiguous_to0']['accuracy'],.75)
        self.assertEqual(result['sensitivity']['all_ambiguous_to1']['accuracy'],.75)
        self.assertEqual(result['sensitivity']['label_assisted_all_incorrect']['accuracy'],.5)
        self.assertEqual(result['sensitivity']['label_assisted_all_correct']['accuracy'],1.)
        for values in result['sensitivity'].values():self.assertNotIn('bce',values)
        numerical.check_canonical_metrics(result['canonical_metrics'],replay.metrics(pop['y'],p))
        changed=dict(result['canonical_metrics']);changed['macro_f1']+=1e-14
        with self.assertRaises(RuntimeError):numerical.check_canonical_metrics(result['canonical_metrics'],changed)

    def test_outside_band_disagreement_rejected_even_inside_probability_tolerance(self):
        pop={'y':np.array([0]),'ids':np.array([0]),'depth':np.array([1]),'hash_route':np.array([0]),'kmeans_route':np.array([0])}
        for p,r in [(.5-2*numerical.BAND,.5+numerical.BAND/2),(.5-numerical.BAND/2,.5+2*numerical.BAND)]:
            self.assertLess(abs(p-r),numerical.PROBABILITY_TOLERANCE)
            with self.assertRaises(RuntimeError):numerical.verify_pair(pop,np.array([p]),np.array([r]))

    def test_synthetic_end_to_end_exclusive_commit(self):
        class SyntheticModel:
            def __init__(self,method,seed):self.parameters=np.zeros(1)
            def predict_population(self,pop):return .1+.8/(1+np.exp(-pop['x'][:,0]-self.parameters[0]))
            def route_for(self,pop):return None
            def accounting(self,*args):return {'model_record_visits':1600,'circuit_examples':0}
        def synthetic_oracle(method,parameters,x,*args):return .1+.8/(1+np.exp(-x[:,0]-parameters[0]))
        with tempfile.TemporaryDirectory(prefix='qpath_v03_e2e_synthetic_') as tmp:
            root=Path(tmp);output=root/'confirmation_evaluation';(root/'data').mkdir()
            x=np.column_stack([np.linspace(-1,1,1600),np.zeros(1600)])
            pop={'x':x,'y':(np.arange(1600)%2).astype(int),'depth':1+np.arange(1600)%4,'hash_route':np.arange(1600)%5,
                 'kmeans_route':np.arange(1600)%5,'ids':np.arange(1600)}
            np.savez(root/'data/confirmation_SEALED_test.npz',**pop)
            put(root/'data/DATA_SEAL.json',{'files':{'confirmation_SEALED_test.npz':{'sha256':s.digest(root/'data/confirmation_SEALED_test.npz')}}})
            for name in ('REGISTRATION.json','LOCK.json','RELEASE.json'):put(root/name,{'synthetic':True})
            rows=[]
            for seed in s.SEEDS['B']:
                for method in s.METHODS:
                    folder=root/f'stage_B/seed_{seed}/{method}';folder.mkdir(parents=True)
                    np.savez(folder/'selected_checkpoint.npz',parameters=np.array([(seed-603)*.01]))
                    rows.append({'seed':seed,'method':method,'path':folder.relative_to(root).as_posix(),'selected_round':3,
                                 'selected_checkpoint_sha256':s.digest(folder/'selected_checkpoint.npz'),'result_sha256':'synthetic','config_sha256':'synthetic'})
            with patch.object(e,'ROOT',root),patch.object(e,'OUTPUT',output),patch.object(e,'REGISTRATION',root/'REGISTRATION.json'),patch.object(e,'LOCK',root/'LOCK.json'),patch.object(e,'RELEASE',root/'RELEASE.json'),patch.object(e,'verify_guard',return_value=({}, {'endpoints':rows},{'release_id':'synthetic'},{})),patch.object(s,'Model',SyntheticModel),patch.object(replay,'predict',side_effect=synthetic_oracle),contextlib.redirect_stdout(io.StringIO()):
                e.evaluate()
                commit=s.read_json(output/'EVALUATION_COMMIT.json')
                self.assertEqual(set(commit['files']),e.expected_output_paths());self.assertEqual(len(commit['files']),135)
                self.assertEqual(commit['count_array_count'],150)
                for name,info in commit['files'].items():self.assertEqual(s.digest(output/name),info['sha256'])
                with np.load(output/'readout/counts.npz') as counts:
                    self.assertEqual(len(counts.files),150)
                    for name in counts.files:self.assertEqual(counts[name].shape,(1600,));self.assertTrue(np.issubdtype(counts[name].dtype,np.integer))
                with self.assertRaises(FileExistsError):e.evaluate()


if __name__=='__main__':unittest.main(verbosity=2)
