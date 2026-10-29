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

import audit_confirmation_readiness_v05 as a
import synthetic_fixture


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


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
        self.assertEqual(len(context['endpoints']), 165)

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
            sealed = self.root / 'quantum/data/confirmation_circle_1_SEALED_test.npz'
            report['watched_input_hashes'][str(sealed)] = '0' * 64
            write(path, report)
            changed = copy.deepcopy(self.commit)
            changed['files']['report.json'] = {'sha256': a.digest(path), 'bytes': path.stat().st_size}
            write(self.folder / 'READINESS_COMMIT.json', changed)
            with self.assertRaisesRegex(ValueError, 'must not watch test outcomes'):
                a.gate(self.root, expected_registry=self.registry_hash)
        finally:
            path.write_bytes(original); write(self.folder / 'READINESS_COMMIT.json', self.commit)


def numeric_fixture():
    pointer=read(a.HERE/'READINESS_AUDITOR_SYNTHETIC_FIXTURE.json')
    if pointer['synthetic_only'] is not True:raise RuntimeError('Only generated untrained synthetic fixture allowed')
    root=Path(pointer['root']);q=root/'quantum';folder=root/'capsule'
    if a.digest(folder/'READINESS_COMMIT.json')!=pointer['readiness_commit_sha256']:raise RuntimeError('Synthetic producer capsule changed')
    commit=read(folder/'READINESS_COMMIT.json');a.inventory(folder,commit['files'],exclude=('READINESS_COMMIT.json',))
    protocol=read(a.ROOT/'governance/LOCAL_READINESS_PROTOCOL.json')
    protocol.update(populations=[pointer['population']],training_seeds=[pointer['seed']])
    endpoints={}
    for method in a.METHODS:
        ep=q/'untrained_initial_states'/pointer['population']/f'seed_{pointer["seed"]}'/method
        ec=read(ep/'endpoint_commit.json')
        if ec['synthetic_untrained'] is not True:raise RuntimeError('No trained checkpoint in test')
        endpoints[(pointer['population'],pointer['seed'],method)]={'path':str(ep),'files':ec['files']}
    return {'root':root,'q':q,'folder':folder,'report':read(folder/'report.json'),'protocol':protocol,
            'seal':read(q/'data/DATA_SEAL.json'),'endpoints':endpoints,'original_root':str(root),'commit':commit,'watched':{}}


class NumericTests(unittest.TestCase):
    def setUp(self):self.context=numeric_fixture()

    def test_complete_four_untrained_checkpoint_producer_capsule(self):
        checks=a.verify_numerics(self.context)
        self.assertEqual(checks['selected_checkpoints_checked'],4)
        self.assertEqual(checks['checkpoint_fixture_pairs'],128)
        self.assertEqual(checks['logical_density_evaluations'],672)
        self.assertEqual(checks['finite_shot_count_array_count'],180)
        self.assertEqual(checks['finite_shot_predictor_array_count'],120)
        self.assertEqual(checks['actual_simulated_measurement_shots'],98304)

    def test_independent_threshold_band_is_separate(self):
        self.assertTrue(a.classification(.5,np.nextafter(.5,0.))['class_disagreement'])
        with self.assertRaisesRegex(ValueError,'outside numerical band'):a.classification(.5,.5-1e-12)

    def test_missing_producer_validation_watch_rejected_before_array_load(self):
        path=self.context['q']/'data'/f'{self.context["protocol"]["populations"][0]}_validation.npz'
        del self.context['report']['watched_input_hashes'][str(path)]
        with patch.object(np,'load',side_effect=AssertionError('No array load before producer binding')):
            with self.assertRaisesRegex(ValueError,'omitted sealed validation/router'):a.verify_numerics(self.context)

    def test_joint_record_tuple_must_match_key(self):
        original=a.read_bound
        def changed(path,watched):
            value=original(path,watched)
            if Path(path).name=='finite_shot_records.json':value[0]['repeat_index']=1
            return value
        with patch.object(a,'read_bound',side_effect=changed),self.assertRaisesRegex(ValueError,'semantic tuple order'):a.verify_numerics(self.context)

    def test_fixture_coordinate_change_rejected(self):
        self.context['report']['circuits'][0]['x'][0]+=.1
        with self.assertRaisesRegex(ValueError,'Fixture raw input'):a.verify_numerics(self.context)

    def test_full_moment_change_rejected(self):
        self.context['report']['circuits'][0]['production_moments']['Z0']+=.01
        with self.assertRaisesRegex(ValueError,'full moments'):a.verify_numerics(self.context)

    def test_head_change_rejected(self):
        self.context['report']['circuits'][32]['head'][0]+=.1
        with self.assertRaisesRegex(ValueError,'Stored head'):a.verify_numerics(self.context)

    def test_joint_correlation_change_rejected(self):
        row=self.context['report']['circuits'][64]['scenarios']['illustrative_mild']['settings']['ZZ']
        delta=np.array([1.,-1.,-1.,1.])*.001
        row['observed_joint']=(np.array(row['observed_joint'])+delta).tolist()
        with self.assertRaisesRegex(ValueError,'observed joint'):a.verify_numerics(self.context)

    def test_missing_group_rejected(self):
        self.context['report']['circuits']=self.context['report']['circuits'][:-32]
        with self.assertRaisesRegex(ValueError,'Every checkpoint'):a.verify_numerics(self.context)

    def test_nonfinite_elapsed_rejected(self):
        self.context['report']['elapsed_seconds']=float('inf')
        with self.assertRaisesRegex(ValueError,'Nonfinite/negative timing'):a.verify_numerics(self.context)

    def test_extra_statevector_cost_required(self):
        self.context['report']['additional_full_moment_statevector_examples']=0
        with self.assertRaisesRegex(ValueError,'work total'):a.verify_numerics(self.context)

    def test_wrong_joint_rng_array_rejected(self):
        original=a.load_arrays
        def changed(path):
            values=original(path)
            if Path(path).name=='finite_shot_counts.npz':
                item=values[next(iter(values))].copy();j=int(item[0].argmax());k=(j+1)%4;item[0,j]-=1;item[0,k]+=1;values[next(iter(values))]=item
            return values
        with patch.object(a,'load_arrays',side_effect=changed),self.assertRaisesRegex(ValueError,'Exact joint multinomial'):a.verify_numerics(self.context)

    def test_wrong_bias_variance_summary_rejected(self):
        original=a.read_bound
        def changed(path,watched):
            value=original(path,watched)
            if Path(path).name=='finite_shot_summary.json':value[0]['mean_sample_variance']+=.01
            return value
        with patch.object(a,'read_bound',side_effect=changed),self.assertRaisesRegex(ValueError,'bias/variance aggregate'):a.verify_numerics(self.context)

    def test_measured_wire_moment_rejected(self):
        original=a.read_bound
        def changed(path,watched):
            value=original(path,watched)
            if Path(path).name=='measured_aer_counts.json':value[0]['observed_moments'][0]+=.1
            return value
        with patch.object(a,'read_bound',side_effect=changed),self.assertRaisesRegex(ValueError,'Measured moment'):a.verify_numerics(self.context)


if __name__=='__main__':unittest.main(verbosity=2)


