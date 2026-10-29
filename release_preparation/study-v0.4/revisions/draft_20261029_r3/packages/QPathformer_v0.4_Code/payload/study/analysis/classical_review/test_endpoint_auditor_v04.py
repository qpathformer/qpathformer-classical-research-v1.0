"""Semantic mutations of a real reduced engineering endpoint; never official data."""
from pathlib import Path
import json,shutil,tempfile,unittest
import numpy as np
import audit_endpoints_v04 as a

HERE=Path(__file__).resolve().parent
ORIGINAL=a.Q/'engineering_pilot_v01/engineering_circle/seed_9701/q2_kmeans'

class EndpointMutationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='audit_fixture_',dir=HERE)
        self.folder=Path(self.tmp.name)/'endpoint';shutil.copytree(ORIGINAL,self.folder)
    def tearDown(self):self.tmp.cleanup()
    def write(self,name,value):
        (self.folder/name).write_text(json.dumps(value,allow_nan=False)+'\n',encoding='utf-8')
    def rows(self):return [json.loads(line) for line in (self.folder/'ledger.jsonl').read_text().splitlines()]
    def ledger(self,rows):(self.folder/'ledger.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    def seal(self):
        c=a.read(self.folder/'endpoint_commit.json')
        c['files']={p.name:{'sha256':a.sha(p),'bytes':p.stat().st_size} for p in self.folder.iterdir() if p.name!='endpoint_commit.json'}
        self.write('endpoint_commit.json',c)
    def audit(self):return a.audit_endpoint(self.folder,'A','engineering_circle',9701,'q2_kmeans',a.read(a.Q/'data/DATA_SEAL.json'),engineering=True)
    def test_unmodified_full_round_engineering_endpoint(self):self.assertEqual(self.audit()['rounds_verified'],3)
    def test_resealed_intermediate_parameter_mutation_fails_oracle(self):
        p=np.load(self.folder/'round_parameters.npy');p[0,0]+=.1;np.save(self.folder/'round_parameters.npy',p)
        rows=self.rows();rows[0]['round_parameter_sha256']=a.rawsha(p[0]);self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'probability replay'):self.audit()
    def test_resealed_intermediate_probability_mutation_fails_oracle(self):
        p=np.load(self.folder/'validation_probabilities.npy');p[0,0]=.123456;np.save(self.folder/'validation_probabilities.npy',p)
        rows=self.rows();rows[0]['validation_probability_sha256']=a.rawsha(p[0]);self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'probability replay'):self.audit()
    def test_resealed_sampler_order_fails_reconstruction(self):
        p=np.load(self.folder/'record_orders.npy');p[0,[0,1]]=p[0,[1,0]];np.save(self.folder/'record_orders.npy',p)
        rows=self.rows();rows[0]['record_order_sha256']=a.rawsha(p[0]);self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'sample order'):self.audit()
    def test_resealed_work_counter_fails(self):
        rows=self.rows();rows[0]['work_cumulative']['training']['shift_circuit_examples']-=1;self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'operation accounting'):self.audit()
    def test_resealed_canonical_metric_fails(self):
        rows=self.rows();rows[0]['validation']['bce']+=.0001;self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'Canonical metric'):self.audit()
    def test_resealed_selection_flag_fails(self):
        rows=self.rows();rows[0]['selected']=False;self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'minimum selection'):self.audit()
    def test_resealed_adam_counter_fails(self):
        path=self.folder/'last_checkpoint.npz';z=a.load(path);z['adam_t']=np.asarray(224);np.savez(path,**z);self.seal()
        with self.assertRaisesRegex(RuntimeError,'horizon/update'):self.audit()
    def test_uncommitted_extra_payload_fails(self):
        (self.folder/'unexpected.txt').write_text('uncommitted',encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError,'payload inventory'):self.audit()

class NumericalBoundaryTests(unittest.TestCase):
    def test_both_probabilities_required_in_band(self):
        y=np.array([0,1]);ids=np.array([8,9]);p=np.array([.5,.5]);r=np.array([.5-np.finfo(float).eps,.5])
        result=a.threshold_check(y,p,r,ids);self.assertEqual(result['class_disagreements'],1)
        self.assertEqual(result['canonical_mask_sensitivity']['allincorrect']['accuracy'],0.)
        self.assertEqual(result['canonical_mask_sensitivity']['allcorrect']['accuracy'],1.)
        r[0]=.5-a.BAND*2
        with self.assertRaisesRegex(RuntimeError,'outside both'):a.threshold_check(y,p,r,ids)
    def test_reference_only_band_does_not_expand_canonical_mask(self):
        y=np.array([0]);p=np.array([.5-2*a.BAND]);r=np.array([.5-a.BAND/2])
        result=a.threshold_check(y,p,r,np.array([7]));self.assertEqual(result['canonical_band_records'],0)
        self.assertEqual(result['reference_band_records'],1)
        for value in result['canonical_mask_sensitivity'].values():self.assertEqual(value['accuracy'],1.)

if __name__=='__main__':unittest.main()
