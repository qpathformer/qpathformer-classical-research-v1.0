"""Synthetic gates and independent numeric/timing-assembly replay; no real results."""
from pathlib import Path
import copy,inspect,json,sys,unittest
from unittest.mock import patch
import numpy as np
import audit_confirmation_deployment_v06 as a
sys.path.insert(0,str(a.ROOT/'quantum/deployment_checks'))
import test_integrity as producer_fixture
from synthetic_fixture import make_fixture

def read(p):return json.loads(Path(p).read_text())

class NumericTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root,q,pop,seed,arrays,fake=producer_fixture.fixture();b=producer_fixture.b;s=producer_fixture.s
        cls.root=root;cls.q=q;cls.pop=pop;cls.seed=seed;cls.output=q/'independent_synthetic_deployment';cache={}
        def mock_clock_measure(forward,batches):
            variables=inspect.getclosurevars(forward).nonlocals
            key=(variables['key'],variables['representation'],len(batches[0]))
            if key not in cache:
                results=[forward(x) for x in batches]
                cache[key]=(np.concatenate([x[0] for x in results]),np.concatenate([x[1] for x in results]))
            p,z=cache[key]
            return 1000,p,z
        env={k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
        with patch.object(s,'ROOT',q),patch.object(s,'POPULATIONS',{'B':(pop,)}),patch.object(s,'SEEDS',{'B':(seed,)}),\
             patch.object(s,'load_population',side_effect=lambda p,split:arrays[split]),\
             patch.object(b,'PROTOCOL',root/'governance/DEPLOYMENT_PROTOCOL.json'),\
             patch.object(b,'IMPLEMENTATION_NOTES',root/'governance/DEPLOYMENT_IMPLEMENTATION_NOTES.json'),\
             patch.object(b,'assert_quiescent',return_value={'relevant_other_process_count':0,'pid':12345,'synthetic_mock':True}),\
             patch.object(b,'measure_trial',side_effect=mock_clock_measure),patch.dict(sys.modules,{'evaluate_confirmation':fake}),patch.dict('os.environ',env):
            b.run(cls.output)
        cls.context={'study':root,'quantum':q,'folder':cls.output,'watched':{},'summary':read(cls.output/'summary.json'),
                     'deployment_commit':read(cls.output/'DEPLOYMENT_COMMIT.json'),'endpoints':{}}
        for method in a.d.METHODS:
            ep=q/'stage_B'/pop/f'seed_{seed}'/method
            cls.context['endpoints'][(pop,seed,method)]={'files':read(ep/'endpoint_commit.json')['files']}
        with (root/'INDEPENDENT_TEST_SCOPE.json').open('x') as f:json.dump({'scope':'Generated untrained model/data; actual prediction outputs, mock clock1000ns, fake release gate. No performance measurement.','auditor_sha256':a.digest(a.__file__)},f)
    def setUp(self):self.context=copy.deepcopy(self.__class__.context)
    def verify(self):
        with patch.object(a.d,'POPULATIONS',(self.pop,)),patch.object(a.d,'SEEDS',(self.seed,)):return a.verify(self.context)
    def test_complete_six_arm_numeric_assembly(self):
        result=self.verify();self.assertEqual(result['selected_checkpoints'],6);self.assertEqual(result['compiled_checkpoints'],2)
        self.assertEqual(result['total_representations'],10);self.assertEqual(result['timing_conditions'],30);self.assertEqual(result['payload_count'],18)
    def mutate_json(self,name,change,pattern):
        original=a.read_bound
        def modified(path,watched):
            value=original(path,watched)
            if Path(path).name==name:change(value)
            return value
        with patch.object(a,'read_bound',side_effect=modified),self.assertRaisesRegex(ValueError,pattern):self.verify()
    def test_representation_order_mutation(self):
        self.mutate_json('timing_trials.json',lambda rows:rows.__setitem__(slice(0,2),rows[0:2][::-1]),'trial order')
    def test_timing_work_mutation(self):
        self.mutate_json('timing_trials.json',lambda rows:rows[0].update(prediction_records=127),'input work')
    def test_parity_class_metadata_mutation(self):
        self.mutate_json('conversion.json',lambda rows:rows[0]['checks']['validation'].update(class_disagreements=1),'parity summary')
    def test_offgrid_disclosed_count_mutation(self):
        self.mutate_json('conversion.json',lambda rows:rows[0]['checks']['offgrid'].update(records=127),'disclosure record count')
    def test_forced_disclosed_tolerance_mutation(self):
        self.mutate_json('conversion.json',lambda rows:rows[0]['checks']['forced_offgrid_banks'][0].update(maximum_logit_error=1e-8),'disclosure tolerance')
    def test_forced_disclosed_inventory_mutation(self):
        self.mutate_json('conversion.json',lambda rows:rows[0]['checks']['forced_offgrid_banks'].pop(),'Forced-bank parity inventory')
    def test_load_checkpoint_bytes_mutation(self):
        self.mutate_json('load_measurements.json',lambda rows:rows[0].update(checkpoint_file_bytes=1),'representation/file bytes')
    def test_load_representation_mutation(self):
        self.mutate_json('load_measurements.json',lambda rows:rows[0].update(representation='classical'),'representation/file bytes')
    def test_compiled_array_inventory_mutation(self):
        original=a.arrays
        def altered(path,keys=None):
            value=original(path,keys)
            if Path(path).name.endswith('qmulti_kmeans__compiled.npz'):value['unexpected']=np.array([1.])
            return value
        with patch.object(a,'arrays',side_effect=altered),self.assertRaisesRegex(ValueError,'Compiled NPZ inventory'):self.verify()
    def test_coefficient_bank_mutation(self):
        original=a.arrays
        def altered(path,keys=None):
            value=original(path,keys)
            if Path(path).name.endswith('qmulti_kmeans__compiled.npz'):value['coefficients'][0,0]+=.01
            return value
        with patch.object(a,'arrays',side_effect=altered),self.assertRaisesRegex(ValueError,'Coefficient tolerance'):self.verify()
    def test_optimized_summary_mutation(self):
        self.context['summary']['summaries'][0]['median_ns_per_record']+=1
        with self.assertRaisesRegex(ValueError,'timing summary'):self.verify()
    def test_no_label_array_decoding(self):
        original=a.arrays;calls=[]
        def checked(path,keys=None):
            if '_SEALED_test.npz' in str(path):
                calls.append(path);self.assertEqual(keys,('x','ids','kmeans_route'))
            return original(path,keys)
        with patch.object(a,'arrays',side_effect=checked):self.verify()
        self.assertEqual(len(calls),1)

class GateTests(unittest.TestCase):
    def test_chronology_compares_aware_instants(self):
        self.assertEqual(a.timestamp('2026-10-19T13:00:00+11:00'),a.timestamp('2026-10-19T02:00:00+00:00'))
        self.assertLess(a.timestamp('2026-10-19T13:00:00+11:00'),a.timestamp('2026-10-19T03:00:00+00:00'))
        with self.assertRaisesRegex(ValueError,'Timezone-aware'):a.timestamp('2026-10-19T02:00:00')
    def test_parity_disclosure_band_and_identity_guards(self):
        row={'maximum_probability_error':1e-13,'maximum_logit_error':1e-13,'records':3,'class_disagreements':1,'canonical_near_band':1,'compiled_near_band':1,'disagreements':[{'record_id':0,'canonical_probability':.5,'compiled_probability':.5-1e-13}]}
        a.disclosed_parity(row,3)
        bad=copy.deepcopy(row);bad['disagreements'][0]['record_id']=3
        with self.assertRaisesRegex(ValueError,'record identity'):a.disclosed_parity(bad,3)
        bad=copy.deepcopy(row);bad['disagreements'][0]['compiled_probability']=.5-3e-12
        with self.assertRaisesRegex(ValueError,'class band'):a.disclosed_parity(bad,3)
    def test_missing_actual_deployment_or_release_blocks_arrays(self):
        fixture=make_fixture(12);root=fixture['root']
        with patch.object(np,'load',side_effect=AssertionError('No array read')):
            with self.assertRaises((FileNotFoundError,ValueError)):a.gate(root)
    def test_public_run_requires_metadata_gate(self):
        with patch.object(a,'gate',side_effect=ValueError('Synthetic gate rejection')),patch.object(np,'load',side_effect=AssertionError('No arrays')):
            with self.assertRaisesRegex(ValueError,'Synthetic gate'):a.run(a.ROOT,a.HERE/'ABSENT_SYNTHETIC_GATE_OUTPUT')
    def test_prior_hash_cannot_be_rebound(self):
        path=a.HERE/'deployment_reference_v06.py';watched={str(path.resolve()):'0'*64}
        with self.assertRaisesRegex(ValueError,'Conflicting prior'):a.bind(path,a.digest(path),watched)

if __name__=='__main__':unittest.main()
