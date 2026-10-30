"""Pre-freeze tests only. No official study or sealed test arrays opened."""
import json,shutil,time,unittest,uuid
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import audit_endpoints_v09 as a

SOURCE=a.ROOT/'quantum/synthetic_fixtures/trainer_20261022T083155'
SESSION=a.HERE/'test_runs'/('audit_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8])
SESSION.mkdir(parents=True)
REPORTS=[]

class EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=a.read(SOURCE/'governance/FIXTURE_MANIFEST.json')
        cls.auth_path=Path(cls.manifest['authorization']['path']);cls.auth=a.read(cls.auth_path)
        cls.seal=a.read(SOURCE/'quantum/data/DATA_SEAL.json')

    def endpoint(self,job,ep=None,paired=None,root=SOURCE):
        return a.audit_endpoint(root,job,ep or SOURCE/'endpoints'/job['run_id'],self.auth,self.auth_path,self.seal,{} if paired is None else paired,{})

    def test_all_four_full_engineering_fixture_endpoints(self):
        paired={}
        for job in self.manifest['jobs']:
            report=self.endpoint(job,paired=paired);REPORTS.append(report)
            self.assertEqual(report['completed_rounds'],20);self.assertEqual(report['independent_gradient_probes'],40)

    def copy_endpoint(self,arm='T_L'):
        job=next(j for j in self.manifest['jobs'] if j['arm']==arm)
        target=SESSION/('mutation_'+uuid.uuid4().hex)/job['run_id'];shutil.copytree(SOURCE/'endpoints'/job['run_id'],target)
        return job,target

    def test_uncommitted_and_changed_payloads_rejected(self):
        job,ep=self.copy_endpoint();(ep/'uncommitted.txt').write_text('added')
        with self.assertRaisesRegex(RuntimeError,'inventory'):self.endpoint(job,ep,root=a.ROOT)
        job,ep=self.copy_endpoint();(ep/'status.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'Payload'):self.endpoint(job,ep,root=a.ROOT)

    def test_resealed_gradient_corruption_rejected_by_reference(self):
        job,ep=self.copy_endpoint();g=np.load(ep/'minibatch_gradients.npy');g[0,0]+=.01;np.save(ep/'minibatch_gradients.npy',g)
        commit=a.read(ep/'endpoint_commit.json');b=a.binding(ep/'minibatch_gradients.npy');commit['files']['minibatch_gradients.npy']={k:b[k] for k in ('sha256','bytes')}
        (ep/'endpoint_commit.json').write_text(json.dumps(commit))
        # Data are the sealed synthetic qualification data; copy endpoint checker
        # uses a preloaded population cache because the mutated endpoint has another root.
        pop=job['population_id'];cache={pop:a.population(SOURCE,pop,self.seal)}
        with self.assertRaisesRegex(RuntimeError,'Independent gradient'):
            a.audit_endpoint(a.ROOT,job,ep,self.auth,self.auth_path,self.seal,{},cache)

    def test_incomplete_budget_and_bad_stream_are_rejected(self):
        job=dict(self.manifest['jobs'][0]);job['updates']=1499
        with self.assertRaisesRegex(RuntimeError,'budget'):self.endpoint(job)
        job,ep=self.copy_endpoint();config=a.read(ep/'config.json');job=json.loads(json.dumps(job))
        job['paired_streams']['training_order']['uint128_decimal']='1';config['paired_streams']=job['paired_streams']
        (ep/'config.json').write_text(json.dumps(config));commit=a.read(ep/'endpoint_commit.json');b=a.binding(ep/'config.json')
        commit['files']['config.json']={k:b[k] for k in ('sha256','bytes')};(ep/'endpoint_commit.json').write_text(json.dumps(commit))
        with self.assertRaisesRegex(RuntimeError,'Stream hash'):self.endpoint(job,ep,root=a.ROOT)

    def test_paired_warmup_mismatch_rejected(self):
        job=self.manifest['jobs'][0]
        paired={(job['population_id'],job['training_seed_id']):{'C_warm750_gradients':'corrupt'}}
        with self.assertRaisesRegex(RuntimeError,'warmup gradients'):self.endpoint(job,paired=paired)

    def test_fixture_cannot_enter_official_stage_audit(self):
        auth=SESSION/'not_a_release.json';a.write_new(auth,{})
        with self.assertRaisesRegex(RuntimeError,'official root'):
            a.audit(SOURCE/'governance/FIXTURE_MANIFEST.json',SOURCE/'AUTHOR_AUDIT_FIXTURE.json',auth,SESSION/'must_not_exist.json')
        self.assertFalse((SESSION/'must_not_exist.json').exists())

if __name__=='__main__':
    start=time.perf_counter();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EndpointTests))
    receipt={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
      'wall_seconds':time.perf_counter()-start,'source_fixture':str(SOURCE),'official_training_or_audits':False,
      'source_bindings':{p.name:a.binding(p) for p in (Path(__file__),a.HERE/'audit_endpoints_v09.py',a.HERE/'reference_v09.py')},
      'endpoint_reports':REPORTS,'failure_details':[{'test':str(t),'traceback':s} for t,s in result.failures+result.errors]}
    a.write_new(SESSION/'TEST_RESULT.json',receipt);print(json.dumps({'status':receipt['status'],'receipt':str(SESSION/'TEST_RESULT.json')}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
