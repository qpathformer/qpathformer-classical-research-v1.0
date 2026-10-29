"""Mutation tests use temporary copies of a completed engineering fixture only."""
import json,shutil,tempfile,unittest,subprocess,sys,itertools
from pathlib import Path
import numpy as np
import audit_endpoints_v03 as a

class EndpointAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)/'fixed1'
        shutil.copytree(a.Q/'engineering_pilot_v02/fixed1',self.folder)
        self.seal=a.read(a.Q/'data/DATA_SEAL.json')
        self.train=a.load(a.Q/'data/engineering_train.npz');self.val=a.load(a.Q/'data/engineering_validation.npz')
    def tearDown(self):self.tmp.cleanup()
    def audit(self):return a.audit_run(self.folder,'fixed1',9501,'A',self.train,self.val,self.seal,None,3,True)
    def write(self,name,obj):(self.folder/name).write_text(json.dumps(obj),encoding='utf-8')
    def rebind(self,key,file):
        result=a.read(self.folder/'result.json');result[key]=a.sha(self.folder/file);self.write('result.json',result)
        commit=a.read(self.folder/'endpoint_commit.json');commit[key]=result[key];commit['result_sha256']=a.sha(self.folder/'result.json');self.write('endpoint_commit.json',commit)
    def ledger_mutation(self,modify):
        rows=[json.loads(s) for s in (self.folder/'ledger.jsonl').read_text().splitlines()];modify(rows)
        (self.folder/'ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n');self.rebind('ledger_sha256','ledger.jsonl')
    def test_valid_engineering_fixture(self):self.assertEqual(self.audit()['selected_validation_predictions_replayed'],1600)
    def test_ledger_selection_not_only_hash(self):
        self.ledger_mutation(lambda rows:rows[0].update(selected=False))
        with self.assertRaises(AssertionError):self.audit()
    def test_work_count_not_only_hash(self):
        self.ledger_mutation(lambda rows:rows[0]['work_cumulative']['training'].update(circuit_examples=123))
        with self.assertRaises(AssertionError):self.audit()
    def test_sample_order_not_only_hash(self):
        data=a.load(self.folder/'record_orders.npz');data['orders'][0,[0,1]]=data['orders'][0,[1,0]]
        np.savez_compressed(self.folder/'record_orders.npz',**data);self.rebind('record_orders_sha256','record_orders.npz')
        with self.assertRaises(AssertionError):self.audit()
    def test_adam_step_count_not_only_hash(self):
        data=a.load(self.folder/'last_checkpoint.npz');data['adam_t']=np.array(224)
        np.savez(self.folder/'last_checkpoint.npz',**data);self.rebind('last_checkpoint_sha256','last_checkpoint.npz')
        with self.assertRaises(AssertionError):self.audit()
    def test_unauthorized_test_access_flag(self):
        result=a.read(self.folder/'result.json');result['test_accessed']=True;self.write('result.json',result)
        commit=a.read(self.folder/'endpoint_commit.json');commit['result_sha256']=a.sha(self.folder/'result.json');self.write('endpoint_commit.json',commit)
        with self.assertRaises(AssertionError):self.audit()
    def test_optimized_python_cannot_disable_checks(self):
        output=Path(self.tmp.name)/'forbidden.json'
        result=subprocess.run([sys.executable,'-B','-O',str(Path(a.__file__)),'--stage','A','--engineering-pilot','--output',str(output)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertFalse(output.exists());self.assertIn('enabled assertions',result.stderr)

class NumericalRecoveryTests(unittest.TestCase):
    def population(self,y):
        y=np.asarray(y,int);n=len(y)
        return {'y':y,'ids':np.arange(n)+900,'depth':np.arange(n)%4+1,
                'hash_route':np.arange(n)%5,'kmeans_route':np.arange(n)[::-1]%5}

    def test_in_band_differences_flagged_without_changing_canonical(self):
        saved=np.array([.5,.5-2*np.finfo(float).eps,.2,.8]);reference=np.array([.5-np.finfo(float).eps,.5,.2,.8])
        pop=self.population([0,1,0,1]);review=a.numerical_review(saved,reference,pop)
        self.assertFalse(review['exact_class_agreement']);self.assertEqual(review['disagreements'],2)
        self.assertEqual(review['outside_band_disagreements'],0)
        self.assertEqual(review['canonical_metrics'],a.metrics(pop['y'],saved))
        self.assertEqual(review['reference_metrics'],a.metrics(pop['y'],reference))
        self.assertEqual([r['record_id'] for r in review['disagreement_rows']],[900,901])
        self.assertEqual(review['canonical_band_sensitivity']['all_zero']['confusion'],[[2,0],[1,1]])
        self.assertEqual(review['canonical_band_sensitivity']['all_one']['confusion'],[[1,1],[0,2]])
        self.assertEqual(review['canonical_band_sensitivity']['all_incorrect']['confusion'],[[1,1],[1,1]])
        self.assertEqual(review['canonical_band_sensitivity']['all_correct']['confusion'],[[2,0],[0,2]])

    def test_one_probability_outside_band_rejected_even_with_probability_agreement(self):
        pop=self.population([0,1]);saved=np.array([.5,.2]);reference=np.array([np.nextafter(.5-a.BAND,-np.inf),.2])
        self.assertLess(np.max(abs(saved-reference)),2e-12)
        for left,right in [(saved,reference),(reference,saved)]:
            with self.assertRaisesRegex(AssertionError,'outside approved'):a.numerical_review(left,right,pop)

    def test_inclusive_boundary_and_canonical_only_sensitivity_mask(self):
        saved=np.array([.5-a.BAND,.5+a.BAND,.5+2*a.BAND,.8]);reference=np.array([.5,.5-np.finfo(float).eps,.5+a.BAND,.8])
        pop=self.population([0,1,1,1]);r=a.numerical_review(saved,reference,pop)
        self.assertEqual(r['canonical_near_band_count'],2);self.assertEqual(r['reference_near_band_count'],3)
        self.assertEqual(r['union_near_band_count'],3)
        expected=(saved>=.5).astype(int);expected[:2]=0
        self.assertEqual(r['canonical_band_sensitivity']['all_zero'],a.classification(pop['y'],expected))

    def test_extrema_match_exhaustive_ambiguous_class_assignments(self):
        saved=np.array([.5,.5-a.BAND,.5+a.BAND,.2,.8]);pop=self.population([0,1,0,1,0])
        r=a.numerical_review(saved,saved.copy(),pop);cases=[]
        for assignment in itertools.product((0,1),repeat=3):
            pred=(saved>=.5).astype(int);pred[:3]=assignment;cases.append(a.classification(pop['y'],pred))
        for metric in ('macro_f1','accuracy'):
            self.assertEqual(r['canonical_band_sensitivity']['all_incorrect'][metric],min(x[metric] for x in cases))
            self.assertEqual(r['canonical_band_sensitivity']['all_correct'][metric],max(x[metric] for x in cases))
        self.assertTrue(all('bce' not in x for x in r['canonical_band_sensitivity'].values()))

    def test_probability_discrepancy_and_nonfinite_rejected(self):
        pop=self.population([0,1]);saved=np.array([.2,.8])
        for reference in (np.array([.2+3e-12,.8]),np.array([np.nan,.8])):
            with self.assertRaises(AssertionError):a.numerical_review(saved,reference,pop)

    def test_canonical_metric_changes_remain_failure(self):
        metric=a.metrics(np.array([0,1]),np.array([.5,.9]));changed=dict(metric)
        changed['macro_f1']=np.nextafter(metric['macro_f1'],np.inf)
        with self.assertRaisesRegex(AssertionError,'Canonical saved-probability'):a.exact_canonical_classification(metric,changed)

if __name__=='__main__':unittest.main()
