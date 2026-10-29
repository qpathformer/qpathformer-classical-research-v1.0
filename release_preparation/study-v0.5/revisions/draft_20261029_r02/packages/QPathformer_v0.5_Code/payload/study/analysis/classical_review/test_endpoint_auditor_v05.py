"""Semantic mutations of a real reduced engineering endpoint; never official data."""
from pathlib import Path
import json,shutil,tempfile,unittest
from unittest.mock import patch
import numpy as np
import audit_endpoints_v05 as a

HERE=Path(__file__).resolve().parent
ORIGINAL=a.Q/'engineering_pilot_01/engineering_circle/seed_8901/qmulti_kmeans'

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
    def audit(self):return a.audit_endpoint(self.folder,'A','engineering_circle',8901,'qmulti_kmeans',a.read(a.Q/'data/DATA_SEAL.json'),engineering=True)
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

    def test_resealed_native_logits_cannot_hide_behind_probabilities(self):
        z=np.load(self.folder/'validation_logits.npy');z[0,0]+=.01;np.save(self.folder/'validation_logits.npy',z)
        rows=self.rows();rows[0]['validation_logit_sha256']=a.rawsha(z[0]);self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'native logits differ'):self.audit()

    def test_resealed_native_aggregate_loss_fails(self):
        loss=np.load(self.folder/'validation_native_losses.npy');loss[0]+=.001;np.save(self.folder/'validation_native_losses.npy',loss)
        rows=self.rows();rows[0]['validation_native_loss_sha256']=a.rawsha(loss[:1]);rows[0]['validation_native']['native_bce']=float(loss[0]);self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'Native aggregate loss'):self.audit()

    def test_resealed_validation_probability_extrema_fails(self):
        rows=self.rows();rows[0]['validation_native']['minimum_raw_probability']+=.01;self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'Validation p minimum'):self.audit()

    def test_resealed_group_gradient_empty_head_contract_fails(self):
        rows=self.rows();rows[0]['mean_batch_gradient_group_norms']['core']=-1.;self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'Group gradient'):self.audit()

    def test_resealed_calibration_count_fails(self):
        rows=self.rows();rows[0]['validation']['reliability10'][0]['count']+=1;self.ledger(rows);self.seal()
        with self.assertRaisesRegex(RuntimeError,'Calibration bin membership'):self.audit()

class FrozenCacheMutationTests(EndpointMutationTests):
    # Only specialized tests are used; avoid inheriting qmulti-specific tests.
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='frozen_audit_fixture_',dir=HERE)
        self.folder=Path(self.tmp.name)/'endpoint';shutil.copytree(ORIGINAL.parent/'qfrozen_kmeans',self.folder)
    def audit(self):return a.audit_endpoint(self.folder,'A','engineering_circle',8901,'qfrozen_kmeans',a.read(a.Q/'data/DATA_SEAL.json'),engineering=True)
    def test_resealed_cache_cannot_substitute_another_core(self):
        path=self.folder/'frozen_validation_moments.npy';cache=np.load(path);cache[0,0]+=.001;np.save(path,cache)
        meta=a.read(self.folder/'frozen_cache.json');meta['records']['validation']['file_sha256']=a.sha(path);meta['records']['validation']['array_sha256']=a.rawsha(cache)
        self.write('frozen_cache.json',meta);result=a.read(self.folder/'result.json');result['frozen_cache']=meta;self.write('result.json',result);self.seal()
        with self.assertRaisesRegex(RuntimeError,'independent fixed core'):self.audit()
    def test_resealed_core_identity_fails(self):
        path=self.folder/'initial_state.npz';state=a.load(path);state['core_parameters'].ravel()[0]+=.1;np.savez(path,**state);self.seal()
        with self.assertRaisesRegex(RuntimeError,'Frozen initial core'):self.audit()
    # Inherited mutations also apply to the six-head-coefficient frozen model.

class PathMappingTests(unittest.TestCase):
    def test_declared_original_absolute_identity_remaps_to_current_copy(self):
        original=a.ROOT
        with tempfile.TemporaryDirectory(prefix='relocated_audit_',dir=HERE) as tmp:
            root=Path(tmp);(root/'governance').mkdir();(root/'quantum').mkdir()
            (root/'governance/STUDY_PLAN.json').write_text(json.dumps({'working_root':str(original)}))
            (root/'quantum/check.py').write_text('copied source')
            with patch.object(a,'ROOT',root),patch.object(a,'Q',root/'quantum'):
                p=a.remap(original/'quantum/check.py');self.assertEqual(p,(root/'quantum/check.py').resolve())
                self.assertEqual(p.read_text(),'copied source')
                with self.assertRaisesRegex(RuntimeError,'outside declared'):a.remap(original.parent/'elsewhere.py')
                with self.assertRaisesRegex(RuntimeError,'escapes'):a.remap('../../escape.py')

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
