"""Synthetic-only mutation and whole-adapter checks; no scientific results."""
import builtins
import copy
import csv
from contextlib import contextmanager
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np

from evidence_io import digest, inventory, map_original_absolute, read_bound, safe_relative
from release_gate import validate_gate
from replay_and_analyse import run_replay, read_predictions
from synthetic_fixture import make_fixture, module, REAL_STUDY
from official_comparison import check_official_numerical, metric_shape, check_native, native_shape
from threshold_reference import diagnostics


@contextmanager
def forbid_outcome_reads(root):
    """A gate must not open either data or official result contents."""
    original_io, original_builtin = io.open, builtins.open
    def check(file):
        if isinstance(file, (str, bytes, Path)):
            path = Path(file).resolve()
            if path.is_relative_to(root):
                rel = path.relative_to(root).as_posix()
                if '_SEALED_test.npz' in rel or ('/confirmation_evaluation/' in '/' + rel and path.name != 'EVALUATION_COMMIT.json'):
                    raise AssertionError('Forbidden outcome read before release gate: ' + rel)
    def io_open(file, *args, **kwargs):
        check(file)
        return original_io(file, *args, **kwargs)
    def builtin_open(file, *args, **kwargs):
        check(file)
        return original_builtin(file, *args, **kwargs)
    with patch('io.open', io_open), patch('builtins.open', builtin_open):
        yield


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = make_fixture(12)
        cls.root = cls.fixture['root']
        print('SYNTHETIC FIXTURE: ' + str(cls.root), flush=True)

    def gate(self):
        with forbid_outcome_reads(self.root):
            return validate_gate(self.root, self.fixture['release'], self.fixture['ready'])

    @contextmanager
    def mutation(self, relative, transform, rebind=False):
        """Mutate only generated synthetic metadata, then restore exact bytes."""
        path = self.root / relative
        release = self.fixture['release']
        commit = self.root / 'quantum/confirmation_evaluation/EVALUATION_COMMIT.json'
        backups = {p: p.read_bytes() for p in {path, release, commit}}
        try:
            value = json.loads(path.read_text())
            transform(value)
            path.write_text(json.dumps(value))
            if rebind:
                release_obj = json.loads(release.read_text())
                key = {'quantum/CONFIRMATION_ENDPOINT_LOCK.json': 'endpoint_lock_sha256',
                       'quantum/CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json': 'independent_endpoint_review_sha256'}[relative]
                release_obj[key] = digest(path)
                release.write_text(json.dumps(release_obj))
                commit_obj = json.loads(commit.read_text()); commit_obj['release_sha256'] = digest(release)
                if key == 'endpoint_lock_sha256': commit_obj[key] = digest(path)
                commit.write_text(json.dumps(commit_obj))
            yield
        finally:
            for target, data in backups.items(): target.write_bytes(data)

    def test_gate_passes_without_outcome_reads(self):
        self.assertEqual(len(self.gate()['endpoints']), 165)

    def test_root_release_required(self):
        with self.mutation('quantum/EVALUATION_RELEASE.json', lambda v: v.update(status='not_released')):
            with self.assertRaisesRegex(ValueError, 'Explicit root release'): self.gate()

    def test_official_completion_required(self):
        path = self.root / 'quantum/confirmation_evaluation/EVALUATION_COMMIT.json'
        saved = path.read_bytes(); backup = path.with_suffix('.preserved_for_test')
        path.rename(backup)
        try:
            with self.assertRaisesRegex(ValueError, 'Actual official'): self.gate()
        finally:
            backup.rename(path)
        self.assertEqual(path.read_bytes(), saved)

    def test_incomplete_commit_rejected(self):
        with self.mutation('quantum/confirmation_evaluation/EVALUATION_COMMIT.json', lambda v: v.update(report_count=134)):
            with self.assertRaisesRegex(ValueError, 'completion incomplete'): self.gate()

    def test_open_worker_rejected(self):
        with self.mutation('quantum/stage_B/stage_status.json', lambda v: v.update(status='running')):
            with self.assertRaisesRegex(ValueError, 'processes not completed'): self.gate()

    def test_audit_binding_changed_rejected(self):
        with self.mutation('analysis/classical_review/SYNTHETIC_AUDIT.json', lambda v: v.update(validation_rounds_replayed=26999)):
            with self.assertRaisesRegex(ValueError, 'Independent audit changed'): self.gate()

    def test_failed_canonical_review_rejected(self):
        with self.mutation('quantum/CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json', lambda v: v.update(status='FAIL'), rebind=True):
            with self.assertRaisesRegex(ValueError, 'independent review incomplete'): self.gate()

    def test_endpoint_payload_mutation_rejected(self):
        path = self.root / 'quantum/stage_B/confirmation_circle_1/seed_1001/q2_kmeans/selected_checkpoint.npz'
        saved = path.read_bytes()
        try:
            path.write_bytes(saved + b'SYNTHETIC_TAMPER')
            with self.assertRaisesRegex(ValueError, 'payload size differs'): self.gate()
        finally: path.write_bytes(saved)

    def test_source_mutation_rejected(self):
        path = self.root / 'analysis/classical_review/reference_v05.py'; saved = path.read_bytes()
        try:
            path.write_bytes(saved + b'\n# synthetic tamper\n')
            with self.assertRaisesRegex(ValueError, 'sources changed'): self.gate()
        finally: path.write_bytes(saved)

    def test_unsafe_paths_duplicate_json_and_inventory(self):
        for name in ('../x', 'a/../../x', '/x', 'C:/x', 'a\\b', 'a//b', 'a./b', 'x:stream'):
            with self.subTest(name=name), self.assertRaises(ValueError): safe_relative(name)
        with self.assertRaises(ValueError): map_original_absolute(r'C:\other\x', r'C:\registered', self.root)
        with self.assertRaises(ValueError): map_original_absolute(r'C:\registered\..\x', r'C:\registered', self.root)
        home = self.fixture['attempt'] / 'io_negative'; home.mkdir(exist_ok=True)
        dup = home / 'duplicate.json'; dup.write_text('{"x":1,"x":2}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'): read_bound(dup, {})
        info = {'bytes': dup.stat().st_size, 'sha256': digest(dup)}
        with self.assertRaisesRegex(ValueError, 'Duplicate normalized'): inventory(home, {'duplicate.json': info, 'DUPLICATE.JSON': info})
        with self.assertRaisesRegex(ValueError, 'inventories differ'): inventory(home, {'omitted.json': info})

    def test_disclosed_author_threshold_changes(self):
        p = np.array([.5, np.nextafter(.5, 0.), .1, .9])
        q = np.array([np.nextafter(.5, 0.), .5, .1, .9])
        pop = {'y': np.array([0, 1, 0, 1]), 'ids': np.arange(4),
               'hash_route': np.array([0, 1, 2, 3]), 'kmeans_route': np.array([4, 3, 2, 1])}
        protocol = json.loads((self.root / 'governance/ANALYSIS_PROTOCOL.json').read_text())['numerical']
        routes = {kind: pop[kind + '_route'] for kind in ('hash', 'kmeans')}
        independent = diagnostics(pop['y'], p, q, pop['ids'], routes, protocol)
        import copy
        recorded=copy.deepcopy(independent)
        recorded['canonical_metrics']=metric_shape(pop['y'],p)
        recorded['raw_reference_metrics']=metric_shape(pop['y'],q)
        result = check_official_numerical(pop['y'], p, pop['ids'], routes, recorded, independent, protocol)
        self.assertEqual(result['author_disagreements'], 2)
        self.assertEqual(result['independent_disagreements'], 2)
        self.assertFalse(recorded['counts']['exact_class_agreement'])
        recorded['disagreements'][0]['reference_prediction'] = 1
        with self.assertRaisesRegex(ValueError, 'classes inconsistent'):
            check_official_numerical(pop['y'], p, pop['ids'], routes, recorded, independent, protocol)

    def test_post_gate_failure_is_preserved_without_commit(self):
        def corrupt(value):
            value['populations']['confirmation_circle_1']['statistics']['aggregate']['q2_kmeans']['bce']['mean'] += .1
        with self.mutation('quantum/confirmation_evaluation/summary.json', corrupt):
            official = self.root / 'quantum/confirmation_evaluation'
            commit = json.loads((official / 'EVALUATION_COMMIT.json').read_text())
            commit['files']['summary.json'] = {'sha256': digest(official / 'summary.json'), 'bytes': (official / 'summary.json').stat().st_size}
            (official / 'EVALUATION_COMMIT.json').write_text(json.dumps(commit))
            output = self.root / 'analysis/independent_replay/synthetic_expected_failure'
            with self.assertRaisesRegex(ValueError, 'Numeric mismatch'):
                run_replay(self.root, self.fixture['release'], self.fixture['ready'], output, expected_records=12)
            self.assertTrue((output / 'ACCESS_EVENT.json').is_file())
            self.assertTrue((output / 'FAILURE.json').is_file())
            self.assertFalse((output / 'REPLAY_COMMIT.json').exists())

    def test_whole_adapter_small_synthetic(self):
        output = self.root / 'analysis/independent_replay/synthetic_replay'
        summary = run_replay(self.root, self.fixture['release'], self.fixture['ready'], output, expected_records=12)
        self.assertEqual(summary['status'], 'PASS')
        self.assertEqual(summary['prediction_pairs_replayed'], 165 * 12)
        commit = json.loads((output / 'REPLAY_COMMIT.json').read_text())
        self.assertEqual(commit['payload_count'], 179)
        self.assertEqual(inventory(output, commit['files'], exclude=('REPLAY_COMMIT.json',))['files'], 179)
        with self.assertRaisesRegex(ValueError, 'no retry in place'):
            run_replay(self.root, self.fixture['release'], self.fixture['ready'], output, expected_records=12)

    def test_native_csv_schema_and_nonfinite_rejected(self):
        home=self.fixture['attempt']/'native_csv';home.mkdir()
        pop={'ids':np.array([1,2]),'hash_route':np.array([0,1]),'kmeans_route':np.array([1,0]),'y':np.array([0,1])}
        path=home/'predictions.csv'
        def save(z):
            with path.open('w',newline='',encoding='utf-8') as handle:
                writer=csv.writer(handle);writer.writerow(['record_id','hash_route','kmeans_route','label','probability','prediction','native_logit'])
                writer.writerows(zip(pop['ids'],pop['hash_route'],pop['kmeans_route'],pop['y'],[.25,.75],[0,1],z))
        save(['','']);p,z=read_predictions(path,pop,'q2_kmeans');self.assertIsNone(z)
        with self.assertRaises(ValueError):read_predictions(path,pop,'qscalar_kmeans')
        save([-1.,1.]);p,z=read_predictions(path,pop,'qscalar_kmeans');self.assertEqual(z.tolist(),[-1.,1.])
        with self.assertRaisesRegex(ValueError,'must be blank'):read_predictions(path,pop,'q2_kmeans')
        save(['NaN',1.])
        with self.assertRaisesRegex(ValueError,'Finite native'):read_predictions(path,pop,'qscalar_kmeans')

    def test_author_native_loss_and_error_checks(self):
        y=np.array([0,1]);z=np.array([-1.,1.]);p=1/(1+np.exp(-z))
        protocol=json.loads((self.root/'governance/ANALYSIS_PROTOCOL.json').read_text())['numerical']
        recorded=native_shape(y,p,z)
        author={'has_native_logits':True,'maximum_logit_error':0.,'independent_native_loss':recorded['native_bce'],'native_loss_error':0.}
        self.assertEqual(check_native(y,p,z,recorded,author,protocol)['status'],'PASS')
        for key,value in [('maximum_logit_error',1e-5),('native_loss_error',1e-5),('independent_native_loss',2.)]:
            changed={**author,key:value}
            with self.subTest(key=key),self.assertRaises(ValueError):check_native(y,p,z,recorded,changed,protocol)
        changed={**recorded,'native_bce':recorded['native_bce']+.01}
        with self.assertRaisesRegex(ValueError,'Numeric mismatch'):check_native(y,p,z,changed,author,protocol)

    def test_raw_author_calibration_inconsistency_rejected(self):
        y=np.array([0,1,0,1]);p=np.array([.1,.9,.2,.8]);ids=np.arange(4);routes={'hash':ids,'kmeans':ids}
        protocol=json.loads((self.root/'governance/ANALYSIS_PROTOCOL.json').read_text())['numerical']
        independent=diagnostics(y,p,p,ids,routes,protocol)
        recorded=copy.deepcopy(independent)
        recorded['canonical_metrics']=metric_shape(y,p);recorded['raw_reference_metrics']=metric_shape(y,p)
        recorded['raw_reference_metrics']['ece10']+=.01
        with self.assertRaisesRegex(ValueError,'calibration aggregate'):check_official_numerical(y,p,ids,routes,recorded,independent,protocol)


if __name__ == '__main__':
    unittest.main(verbosity=2)
