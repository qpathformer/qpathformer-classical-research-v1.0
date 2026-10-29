"""Synthetic-only capsule audit tests; no actual confirmation capsule access."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

import audit_confirmation_readiness_v06 as a
import synthetic_fixture


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def numeric_fixture(full=False):
    pointer=read(a.HERE/('READINESS_FULL40_SYNTHETIC_FIXTURE.json' if full else 'READINESS_SMALL2_SYNTHETIC_FIXTURE.json'))
    if pointer['synthetic_only'] is not True:raise RuntimeError('Synthetic fixture required')
    root=Path(pointer['root']);q=root/'quantum';folder=root/'capsule';commit=read(folder/'READINESS_COMMIT.json')
    if a.digest(folder/'READINESS_COMMIT.json')!=pointer['readiness_commit_sha256']:raise RuntimeError('Fixture commit changed')
    a.inventory(folder,commit['files'],exclude=('READINESS_COMMIT.json',))
    protocol=read(a.ROOT/'governance/LOCAL_READINESS_PROTOCOL.json');protocol.update(populations=pointer['populations'],training_seeds=pointer['seeds'])
    endpoints={}
    for pop in pointer['populations']:
        for seed in pointer['seeds']:
            for method in a.METHODS:
                path=q/'stage_B'/pop/f'seed_{seed}'/method;ec=read(path/'endpoint_commit.json')
                if ec['synthetic_untrained'] is not True:raise RuntimeError('Untrained fixture required')
                endpoints[(pop,seed,method)]={'path':str(path),'files':ec['files']}
    return {'root':root,'q':q,'folder':folder,'report':read(folder/'report.json'),'protocol':protocol,
            'seal':read(q/'data/DATA_SEAL.json'),'endpoints':endpoints,'original_root':str(root),'commit':commit,'watched':{}}


class NumericTests(unittest.TestCase):
    def setUp(self):self.context=numeric_fixture()
    def test_complete_two_checkpoint_actual_synthetic_producer(self):
        checks=a.verify_numerics(self.context)
        self.assertEqual(checks['checkpoint_count'],2);self.assertEqual(checks['checkpoint_fixture_pairs'],64)
        self.assertEqual(checks['density_evaluations'],288);self.assertEqual(checks['finite_shot_count_array_count'],90)
        self.assertEqual(checks['actual_simulated_measurement_shots'],49152)
    def test_missing_validation_watch_fails_before_arrays(self):
        pop=self.context['protocol']['populations'][0];path=self.context['q']/'data'/f'{pop}_validation.npz'
        del self.context['report']['watched_input_hashes'][str(path)]
        with patch.object(np,'load',side_effect=AssertionError('No array read')):
            with self.assertRaisesRegex(ValueError,'Missing original'):a.verify_numerics(self.context)
    def test_wrong_input(self):
        self.context['report']['circuits'][0]['x'][0]+=.01
        with self.assertRaisesRegex(ValueError,'input_identity'):a.verify_numerics(self.context)
    def test_wrong_bank(self):
        self.context['report']['circuits'][0]['bank']=(self.context['report']['circuits'][0]['bank']+1)%5
        with self.assertRaisesRegex(ValueError,'record/bank'):a.verify_numerics(self.context)
    def test_changed_moment(self):
        self.context['report']['circuits'][0]['production_moments']['Z0']+=.01
        with self.assertRaisesRegex(ValueError,'production_moments'):a.verify_numerics(self.context)
    def test_changed_mapping(self):
        self.context['report']['circuits'][0]['settings']['XX']['physical_mapping']['logical_q0_physical']=0
        with self.assertRaisesRegex(ValueError,'Physical/wire'):a.verify_numerics(self.context)
    def test_changed_noise_joint(self):
        self.context['report']['circuits'][0]['scenarios']['archived_manila']['settings']['XX']['observed_joint'][0]+=.01
        with self.assertRaisesRegex(ValueError,'archived_manila_observed'):a.verify_numerics(self.context)
    def changed_metadata(self,name,change,expected):
        original=a.read_bound
        def read_changed(path,watched):
            obj=original(path,watched)
            if Path(path).name==name:change(obj)
            return obj
        with patch.object(a,'read_bound',side_effect=read_changed),self.assertRaisesRegex(ValueError,expected):a.verify_numerics(self.context)
    def test_changed_sampling_tuple(self):
        self.changed_metadata('finite_shot_records.json',lambda r:r[0].update(repeat_index=1),'semantic tuple/order')
    def test_changed_rng_sequence(self):
        self.changed_metadata('finite_shot_records.json',lambda r:r[0]['seed_sequences']['XX'].__setitem__(0,123),'RNG identity')
    def test_changed_nested_variance(self):
        self.changed_metadata('finite_shot_summary.json',lambda r:r[0].update(mean_sample_variance=1),'Nested aggregate')
    def test_changed_measured_counts(self):
        self.changed_metadata('measured_aer_counts.json',lambda r:r[0]['counts'].__setitem__(0,1025),'Measured counts')
    def test_nonfinite_elapsed(self):
        self.context['report']['elapsed_seconds']=float('inf')
        with self.assertRaisesRegex(ValueError,'Timing must'):a.verify_numerics(self.context)
    def test_changed_resource_identity(self):
        self.context['report']['checkpoint_resources'][0]['trainable_parameters']+=1
        with self.assertRaisesRegex(ValueError,'resource evidence'):a.verify_numerics(self.context)
    def test_changed_recorded_maximum(self):
        self.context['report']['maximum_compiled_unitary_error']+=.01
        with self.assertRaisesRegex(ValueError,'aggregate residual'):a.verify_numerics(self.context)
    def test_threshold_band_stays_strict(self):
        self.assertTrue(a.classification(.5,np.nextafter(.5,0.))['class_disagreement'])
        with self.assertRaisesRegex(ValueError,'outside numerical'):a.classification(.5,.5-1e-12)


if __name__=='__main__':unittest.main()


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = synthetic_fixture.make_fixture(12)
        cls.root = cls.fixture['root']; q = cls.root / 'quantum'
        protocol_path = cls.root / 'governance/LOCAL_READINESS_PROTOCOL.json'
        write(protocol_path, read(a.ROOT / 'governance/LOCAL_READINESS_PROTOCOL.json'))
        regpath = q / 'EVALUATION_REGISTRATION.json'; registry = read(regpath)
        registry['readiness_protocol_sha256'] = a.digest(protocol_path); write(regpath, registry)
        readypath = cls.root / 'analysis/independent_replay/ANALYSIS_READY.json'; ready = read(readypath)
        ready['registration_sha256'] = a.digest(regpath); write(readypath, ready)
        releasepath = q / 'EVALUATION_RELEASE.json'; release = read(releasepath)
        release.update(registration_sha256=a.digest(regpath), readiness_protocol_sha256=a.digest(protocol_path),
                       independent_replay_ready_sha256=a.digest(readypath)); write(releasepath, release)
        official_path=q/'confirmation_evaluation/EVALUATION_COMMIT.json';official=read(official_path)
        official.update(release_sha256=a.digest(releasepath),registration_sha256=a.digest(regpath));write(official_path,official)
        cls.registry_hash = a.digest(regpath)
        watched = {}
        for p in cls.root.rglob('*'):
            if not p.is_file(): continue
            relative = p.relative_to(cls.root).as_posix()
            if '_SEALED_test' in relative or relative.startswith('quantum/confirmation_evaluation/'):
                continue
            watched[str(p)] = a.digest(p)
        cls.folder = q / 'local_readiness_confirmation'; cls.folder.mkdir()
        report = {'status': 'PASS', 'engineering': False, 'test_accessed': False,
                  'populations': list(a.POPULATIONS), 'training_seeds': list(a.SEEDS), 'methods': list(a.METHODS),
                  'protocol_sha256': a.digest(protocol_path), 'created_utc': a.now(), 'watched_input_hashes': watched,
                  'synthetic_only': True}
        write(cls.folder / 'report.json', report)
        cls.commit = {'status': 'completed', 'engineering': False, 'test_accessed': False, 'created_utc': a.now(),
                      'files': {'report.json': {'sha256': a.digest(cls.folder / 'report.json'), 'bytes': (cls.folder / 'report.json').stat().st_size}}}
        write(cls.folder / 'READINESS_COMMIT.json', cls.commit)

    def test_complete_metadata_gate_never_loads_arrays(self):
        with patch.object(np, 'load', side_effect=AssertionError('Gate must not load arrays')):
            context = a.gate(self.root, expected_registry=self.registry_hash)
        self.assertEqual(len(context['endpoints']), 120)

    def test_conflicting_later_hash_cannot_rebind_input(self):
        path = self.fixture['attempt'] / 'synthetic_rebinding.txt'
        path.write_text('original synthetic evidence', encoding='utf-8')
        original = a.digest(path); watched = {str(path.resolve()): original}
        path.write_text('changed synthetic evidence', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Previously bound input identity'):
            a.bound_file(path, a.digest(path), watched)
        self.assertEqual(watched[str(path.resolve())], original)

    def test_missing_release_fails_before_capsule(self):
        releasepath = self.root / 'quantum/EVALUATION_RELEASE.json'
        original = releasepath.read_bytes()
        try:
            releasepath.unlink()
            with patch.object(np, 'load', side_effect=AssertionError('No array access')):
                with self.assertRaises(FileNotFoundError): a.gate(self.root, expected_registry=self.registry_hash)
        finally: releasepath.write_bytes(original)

    def test_incomplete_official_completion_rejected_without_array_read(self):
        path=self.root/'quantum/confirmation_evaluation/EVALUATION_COMMIT.json';original=path.read_bytes()
        try:
            obj=read(path);obj['report_count']=119;write(path,obj)
            with patch.object(np,'load',side_effect=AssertionError('No array access')):
                with self.assertRaisesRegex(ValueError,'Complete official evaluation'):a.gate(self.root,expected_registry=self.registry_hash)
        finally:path.write_bytes(original)

    def test_relocated_gate_uses_copied_evidence(self):
        relocated = self.fixture['attempt'] / 'readiness_relocated_package'
        shutil.copytree(self.root, relocated)
        blocked = []
        # The hook is process-persistent but inert outside this bounded context.
        enabled = [True]
        def guard(event, args):
            if not enabled[0] or event != 'open' or not args or not isinstance(args[0], (str, bytes)):
                return
            path = Path(args[0]).resolve()
            if path.is_relative_to(self.root.resolve()):
                blocked.append(str(path)); raise AssertionError('Original package read: ' + str(path))
        sys.addaudithook(guard)
        try:
            context = a.gate(relocated, expected_registry=self.registry_hash)
            self.assertEqual(context['root'], relocated.resolve())
            self.assertEqual(blocked, [])
        finally: enabled[0] = False

    def test_failed_commit_rejected(self):
        path = self.folder / 'READINESS_COMMIT.json'
        try:
            write(path, {**self.commit, 'status': 'failed'})
            with self.assertRaisesRegex(ValueError, 'complete confirmation capsule'):
                a.gate(self.root, expected_registry=self.registry_hash)
        finally: write(path, self.commit)

    def test_commit_payload_mutation_rejected(self):
        path = self.folder / 'report.json'; original = path.read_bytes()
        try:
            path.write_bytes(original + b' ')
            with self.assertRaises(ValueError): a.gate(self.root, expected_registry=self.registry_hash)
        finally: path.write_bytes(original)

    def test_no_sealed_payload_allowed_in_watched_inputs(self):
        path = self.folder / 'report.json'; original = path.read_bytes()
        try:
            report = read(path)
            sealed = self.root / 'quantum/data/confirmation_checkerboard_SEALED_test.npz'
            report['watched_input_hashes'][str(sealed)] = '0' * 64
            write(path, report)
            changed = copy.deepcopy(self.commit)
            changed['files']['report.json'] = {'sha256': a.digest(path), 'bytes': path.stat().st_size}
            write(self.folder / 'READINESS_COMMIT.json', changed)
            with self.assertRaisesRegex(ValueError, 'must not watch test outcomes'):
                a.gate(self.root, expected_registry=self.registry_hash)
        finally:
            path.write_bytes(original); write(self.folder / 'READINESS_COMMIT.json', self.commit)


