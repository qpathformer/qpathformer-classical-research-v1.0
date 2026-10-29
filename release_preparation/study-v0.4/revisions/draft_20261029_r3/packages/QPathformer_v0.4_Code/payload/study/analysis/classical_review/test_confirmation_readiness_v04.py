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

import audit_confirmation_readiness_v04 as a
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
        self.assertEqual(len(context['endpoints']), 135)

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
    home = a.HERE / 'readiness_test_work'; home.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='synthetic_capsule_', dir=home)); q = root / 'quantum'
    folder = q / 'local_readiness_confirmation'; folder.mkdir(parents=True)
    protocol = read(a.ROOT / 'governance/LOCAL_READINESS_PROTOCOL.json')
    seal = {'files': {}}; endpoints = {}; report = {'circuits': [], 'fixture_ids': {}, 'summaries': {}, 'timings_seconds': {'synthetic': 0.}, 'elapsed_seconds': 0.}
    arrays = {}; probability_arrays = {}; records = []; measured = []
    rng = np.random.default_rng(440022)
    for pi, population in enumerate(a.POPULATIONS):
        val = {'ids': pi * 100000 + rng.permutation(1600).astype(np.int64), 'x': rng.uniform(-1, 1, (1600, 2)),
               'hash_route': rng.integers(0, 5, 1600), 'kmeans_route': rng.integers(0, 5, 1600)}
        path = q / 'data' / f'{population}_validation.npz'; path.parent.mkdir(exist_ok=True)
        np.savez(path, **val); seal['files'][path.name] = {'sha256': a.digest(path)}
        idx = np.argsort(val['ids'], kind='stable')[:32]; report['fixture_ids'][population] = val['ids'][idx].tolist()
        for seed in a.SEEDS:
            for mi, method in enumerate(a.METHODS):
                theta = rng.uniform(-.2, .2, a.ref.PARAMETERS[method])
                path = q / 'stage_B' / population / f'seed_{seed}' / method / 'selected_checkpoint.npz'; path.parent.mkdir(parents=True)
                np.savez(path, parameters=theta, current_round=137, completed_rounds=137, adam_t=10275)
                ch = a.digest(path); endpoints[(population, seed, method)] = {'files': {'selected_checkpoint.npz': {'sha256': ch}}, 'selected_round': 137}
                group = []
                for fi, index in enumerate(idx):
                    x = val['x'][index]; bank = 0 if method == 'q2_global' else int(val[method.split('_')[1] + '_route'][index])
                    angles = theta[8 * bank:8 * (bank + 1)].reshape(2, 2, 2); ideal = a.ref.scalar_circuit(x, angles)
                    row = {'key': f'{population}__seed{seed}__{method}__id{int(val["ids"][index])}',
                           'population': population, 'training_seed': seed, 'method': method, 'fixture_index': fi,
                           'record_id': int(val['ids'][index]), 'x': x.tolist(), 'bank': bank,
                           'hash_route': int(val['hash_route'][index]), 'kmeans_route': int(val['kmeans_route'][index]),
                           'checkpoint_sha256': ch, 'logical_operations': {'ry': 9, 'rz': 4, 'cx': 2},
                           'compiled_operations': {'rz': 20, 'sx': 10, 'cx': 2},
                           'production_probability': ideal, 'reference_probability': ideal, 'compiled_probability': ideal,
                           'compiled_aer_probability': ideal, 'source_unitary_error': 0., 'compiled_unitary_error': 0., 'scenarios': {}}
                    for sc in protocol['noise_scenarios']:
                        p = a.engineering.density_probability(x, angles, sc['one_qubit_depolarizing'], sc['cx_depolarizing'])
                        flip = sc['symmetric_readout_flip']; observed = flip + (1 - 2 * flip) * p
                        row['scenarios'][sc['name']] = {'premeasurement_probability': p, 'observed_probability': observed,
                            'absolute_distortion_from_ideal': abs(observed - ideal), 'classification_disagreement_from_ideal': bool((observed >= .5) != (ideal >= .5))}
                    group.append(row); report['circuits'].append(row)
                for ni, sc in enumerate(protocol['noise_scenarios']):
                    p = np.array([r['scenarios'][sc['name']]['observed_probability'] for r in group])
                    for shots in protocol['finite_shot']['shots']:
                        for repeat in range(5):
                            sequence = [490101, pi, seed, mi, ni, shots, repeat]
                            n = np.random.Generator(np.random.PCG64(np.random.SeedSequence(sequence))).binomial(shots, p)
                            key = f'{population}__seed{seed}__{method}__{sc["name"]}__shots{shots}__repeat{repeat}'
                            arrays[key] = n; probability_arrays[key] = n / shots
                            records.append({'key': key, 'population': population, 'training_seed': seed, 'method': method,
                                'scenario': sc['name'], 'shots': shots, 'repeat_index': repeat, 'seed_sequence': sequence,
                                'record_ids': [r['record_id'] for r in group], 'mean_absolute_probability_error': float(np.mean(abs(n / shots - p))),
                                'classification_disagreement_from_density': float(np.mean((n / shots >= .5) != (p >= .5)))})
    rows = report['circuits']
    for sc in protocol['noise_scenarios']:
        if sc['name'] not in protocol['aer_measured_smoke']['scenarios']: continue
        for row in rows:
            if row['fixture_index'] >= 8: continue
            p = row['scenarios'][sc['name']]['observed_probability']; n1 = round(1024 * p); variance = 1024 * p * (1 - p)
            measured.append({'key': row['key'], 'scenario': sc['name'], 'shots': 1024, 'counts': {'0': 1024 - n1, '1': n1},
                             'density_expected_probability': p, 'observed_probability': n1 / 1024, 'degenerate_variance': variance == 0,
                             'standardized_count_residual': (n1 - 1024 * p) / np.sqrt(variance) if variance > 0 else None, 'seed_simulator': 490103})
    for population in a.POPULATIONS:
        report['summaries'][population] = {}
        for method in a.METHODS:
            chosen = [r for r in rows if r['population'] == population and r['method'] == method]
            report['summaries'][population][method] = {sc['name']: {
                'checkpoint_fixture_pairs': 160,
                'mean_absolute_distortion': float(np.mean([r['scenarios'][sc['name']]['absolute_distortion_from_ideal'] for r in chosen])),
                'maximum_absolute_distortion': max(r['scenarios'][sc['name']]['absolute_distortion_from_ideal'] for r in chosen),
                'classification_disagreement_fraction': float(np.mean([r['scenarios'][sc['name']]['classification_disagreement_from_ideal'] for r in chosen]))} for sc in protocol['noise_scenarios']}
    report.update(circuit_count=1440, matrix_comparisons=2880, density_scenario_circuit_evaluations=4320,
                  compiled_ideal_aer_circuit_evaluations=1440, measured_aer_circuit_experiments=720,
                  actual_simulated_measurement_shots=737280, finite_shot_array_count=1350,
                  represented_binomial_trials=sum(r['shots'] * 32 for r in records), maximum_source_unitary_error=0.,
                  maximum_compiled_unitary_error=0., maximum_compiled_aer_probability_error=0.,
                  maximum_ideal_density_probability_error=max(abs(r['scenarios']['ideal']['observed_probability'] - r['reference_probability']) for r in rows))
    np.savez(folder / 'finite_shot_counts.npz', **arrays); np.savez(folder / 'finite_shot_probabilities.npz', **probability_arrays)
    write(folder / 'finite_shot_records.json', records); write(folder / 'measured_aer_counts.json', measured)
    files = {'report.json', 'finite_shot_counts.npz', 'finite_shot_probabilities.npz', 'finite_shot_records.json', 'measured_aer_counts.json'}
    files.update(f'circuits/{r["key"]}__{kind}.qasm' for r in rows for kind in ('logical', 'compiled'))
    files.update(f'circuits/{r["key"]}__measured.qasm' for r in rows if r['fixture_index'] < 8)
    write(root / 'SYNTHETIC_ONLY.json', {'synthetic_only': True, 'scope': 'Numerical auditor schema fixture only; no real Aer execution or training claim.'})
    return {'root': root, 'q': q, 'folder': folder, 'report': report, 'protocol': protocol, 'seal': seal,
            'endpoints': endpoints, 'commit': {'files': {name: {} for name in files}}, 'watched': {}}


class NumericTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.context = numeric_fixture()

    def test_complete_45_checkpoint_scope(self):
        result = a.verify_numerics(self.context)
        self.assertEqual(result['selected_checkpoints_checked'], 45)
        self.assertEqual(result['density_scenario_circuit_evaluations'], 4320)
        self.assertEqual(result['actual_simulated_measurement_shots'], 737280)

    def test_fixture_coordinate_change_rejected(self):
        context = {**self.context, 'report': copy.deepcopy(self.context['report'])}
        context['report']['circuits'][0]['x'][0] += .001
        with self.assertRaisesRegex(ValueError, 'coordinates/IDs/routes'): a.verify_numerics(context)

    def test_wrong_logical_noise_rejected(self):
        context = {**self.context, 'report': copy.deepcopy(self.context['report'])}
        context['report']['circuits'][0]['scenarios']['illustrative_mild']['premeasurement_probability'] += .001
        with self.assertRaisesRegex(ValueError, 'density channel'): a.verify_numerics(context)

    def test_missing_group_rejected(self):
        context = {**self.context, 'report': {**self.context['report'], 'circuits': self.context['report']['circuits'][:-1]}}
        with self.assertRaisesRegex(ValueError, '1440'): a.verify_numerics(context)

    def test_binomial_array_change_rejected(self):
        path = self.context['folder'] / 'finite_shot_counts.npz'; original = path.read_bytes()
        try:
            arrays = a.load_arrays(path); key = next(iter(arrays)); arrays[key][0] += 1
            np.savez(path, **arrays)
            with self.assertRaisesRegex(ValueError, 'Exact binomial replay'): a.verify_numerics(self.context)
        finally: path.write_bytes(original)

    def test_measured_count_sum_change_rejected(self):
        path = self.context['folder'] / 'measured_aer_counts.json'; original = path.read_bytes()
        try:
            rows = read(path); rows[0]['counts']['0'] += 1; write(path, rows)
            # This unit deliberately exercises arithmetic after integrity; the
            # separate gate mutation test already exercises bound-byte failure.
            context = {**self.context, 'watched': {}}
            with self.assertRaisesRegex(ValueError, 'Measured counts differ'): a.verify_numerics(context)
        finally: path.write_bytes(original)

    def test_nonfinite_total_elapsed_rejected(self):
        context = {**self.context, 'report': {**self.context['report'], 'elapsed_seconds': float('inf')}, 'watched': {}}
        with self.assertRaisesRegex(ValueError, 'Nonfinite/negative timing'): a.verify_numerics(context)


if __name__ == '__main__': unittest.main(verbosity=2)
