"""Synthetic JSON-only checks for report diagnostics; no real B outcomes."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'report_work'))
import prepare_diagnostic_sections as d


def training_fixture():
    populations = {}; reports = {}
    counters = ('circuit_examples', 'feature_ry_gates', 'feature_rz_gates', 'trainable_ry_gates', 'trainable_rz_gates',
                'readout_ry_gates', 'cx_gates', 'mlp_hidden_evaluations', 'trig_feature_values')
    for pop in d.POPS:
        rows = []
        for si, seed in enumerate(d.SEEDS):
            for method in d.METHODS:
                banks = 1 if method.endswith('_global') else 5
                bce = .1 + .01 * si
                metric = lambda loss, n: {'bce': loss, 'n': n, 'clipped': 0, 'macro_f1': .9, 'accuracy': .9}
                work = {k: 0 for k in counters}
                if method.startswith('q2'):
                    work.update(circuit_examples=16320000, feature_ry_gates=65280000, trainable_ry_gates=65280000,
                                trainable_rz_gates=65280000, readout_ry_gates=16320000, cx_gates=32640000)
                elif method.startswith('mlp'):
                    work['mlp_hidden_evaluations'] = 61440000 if banks == 1 else 3840000
                else: work['trig_feature_values'] = 48000000
                row = {'stage': 'B', 'population': pop, 'seed': seed, 'method': method, 'test_accessed': False,
                    'selected_round': 25 + si, 'selected_checkpoint_sha256': f'{pop}-{seed}-{method}-synthetic',
                    'selected_training': metric(bce, 4800), 'selected_validation': metric(bce + .02, 1600),
                    'training_records_seen': 960000, 'validation_records_seen': 320000, 'optimizer_updates': 15000,
                    'training_clipped_probability_visits': 96, 'training_clipped_probability_fraction': .0001,
                    'gradients': {point: {'round': round_, 'mean_batch_gradient_norm': .2,
                        'maximum_batch_gradient_norm': .5, 'norm_of_mean_batch_gradient_vector': .1}
                        for point, round_ in (('first', 1), ('selected', 25 + si), ('last', 200))},
                    'bank_count': banks, 'parameter_count': 8 if banks == 1 else 40, 'parameters_per_bank': 8,
                    'train_bank_counts': [4800 // banks] * banks, 'bank_training_record_visits': [960000 // banks] * banks,
                    'validation_route_counts': {'hash': [320] * 5, 'kmeans': [320] * 5}, 'work_by_phase': {'training': work}}
                row['gradients']['selected_full_training_gradient_norm'] = .03
                rows.append(row)
                reports[(pop, seed, method)] = {'population': pop, 'seed': seed, 'method': method,
                    'selected_round': row['selected_round'], 'checkpoint_sha256': row['selected_checkpoint_sha256'],
                    'metrics': metric(bce + .05, 1600)}
        populations[pop] = {'population': pop, 'stage': 'B', 'endpoint_count': 45, 'endpoints': rows}
    return populations, reports


def readiness_fixture():
    report = {'engineering': False, 'test_accessed': False, 'populations': list(d.POPS), 'training_seeds': list(d.SEEDS),
              'methods': list(d.QMETHODS), 'circuits': [], 'summaries': {}}
    shots = []
    for pi, pop in enumerate(d.POPS):
        report['summaries'][pop] = {}
        for si, seed in enumerate(d.SEEDS):
            for mi, method in enumerate(d.QMETHODS):
                records = [pi * 10000 + i for i in range(32)]
                for i, record in enumerate(records):
                    ideal = .49 if i % 2 else .7
                    row = {'key': f'{pop}/{seed}/{method}/{record}', 'population': pop, 'training_seed': seed, 'method': method,
                           'record_id': record, 'fixture_index': i, 'bank': 0, 'checkpoint_sha256': 'synthetic', 'reference_probability': ideal, 'scenarios': {}}
                    for scenario, delta in zip(d.SCENARIOS, (0, .02, .06)):
                        observed = ideal + delta
                        row['scenarios'][scenario] = {'premeasurement_probability': observed, 'observed_probability': observed,
                            'absolute_distortion_from_ideal': abs(observed - ideal),
                            'classification_disagreement_from_ideal': bool((observed >= .5) != (ideal >= .5))}
                    report['circuits'].append(row)
                for ni, scenario in enumerate(d.SCENARIOS):
                    for budget in (1024, 8192):
                        for repeat in range(5):
                            shots.append({'key': f'{pop}-{seed}-{method}-{scenario}-{budget}-{repeat}', 'population': pop,
                                'training_seed': seed, 'method': method, 'scenario': scenario, 'shots': budget, 'repeat_index': repeat,
                                'seed_sequence': [490101, pi, seed, mi, ni, budget, repeat], 'record_ids': records,
                                'mean_absolute_probability_error': .01 * (si + 1) + .001 * (repeat - 2),
                                'classification_disagreement_from_density': si / 32})
        for method in d.QMETHODS:
            report['summaries'][pop][method] = {sc: {'checkpoint_fixture_pairs': 160,
                'mean_absolute_distortion': statistics.fmean(r['scenarios'][sc]['absolute_distortion_from_ideal'] for r in report['circuits'] if r['population'] == pop and r['method'] == method),
                'maximum_absolute_distortion': max(r['scenarios'][sc]['absolute_distortion_from_ideal'] for r in report['circuits'] if r['population'] == pop and r['method'] == method),
                'classification_disagreement_fraction': statistics.fmean(r['scenarios'][sc]['classification_disagreement_from_ideal'] for r in report['circuits'] if r['population'] == pop and r['method'] == method)} for sc in d.SCENARIOS}
    return report, shots


class DerivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.populations, cls.reports = training_fixture()
        cls.readiness, cls.shots = readiness_fixture()

    def test_same_checkpoint_gaps_and_exposure(self):
        result = d.derive_training(self.populations, self.reports)
        self.assertEqual(len(result['loss_rows']), 135)
        self.assertEqual(len(result['gradient_rows']), 405)
        self.assertEqual(len(result['bank_exposure_rows']), 495)
        row = result['loss_rows'][0]
        self.assertAlmostEqual(row['validation_minus_train_bce'], .02)
        self.assertAlmostEqual(row['test_minus_validation_bce'], .03)
        self.assertAlmostEqual(row['test_minus_train_bce'], .05)

    def test_mismatched_test_checkpoint_rejected(self):
        reports = copy.deepcopy(self.reports)
        reports[next(iter(reports))]['checkpoint_sha256'] = 'different'
        with self.assertRaisesRegex(RuntimeError, 'checkpoint pairing'): d.derive_training(self.populations, reports)

    def test_probability_clip_denominator_rejected(self):
        populations = copy.deepcopy(self.populations)
        populations[d.POPS[0]]['endpoints'][0]['training_clipped_probability_fraction'] = .01
        with self.assertRaisesRegex(RuntimeError, 'clip fraction'): d.derive_training(populations, self.reports)

    def test_shot_replicates_nested_before_seed_dispersion(self):
        result = d.derive_readiness(self.readiness, self.shots)
        self.assertEqual(len(result['noise_record_rows']), 4320)
        self.assertEqual(len(result['noise_checkpoint_rows']), 135)
        self.assertEqual(len(result['shot_checkpoint_rows']), 270)
        cell = result['aggregate_shots'][d.POPS[0]][d.QMETHODS[0]]['ideal']['1024']['mean_absolute_probability_error']
        self.assertEqual(cell['n_training_seeds'], 5)
        self.assertAlmostEqual(cell['mean'], .03)
        self.assertAlmostEqual(cell['sample_sd'], statistics.stdev([.01, .02, .03, .04, .05]))

    def test_wrong_shot_rng_identity_rejected(self):
        shots = copy.deepcopy(self.shots); shots[0]['seed_sequence'][1] += 1
        with self.assertRaisesRegex(RuntimeError, 'RNG identity'): d.derive_readiness(self.readiness, shots)

    def test_word_sections_and_common_work_require_equality(self):
        result = {**d.derive_training(self.populations, self.reports), **d.derive_readiness(self.readiness, self.shots)}
        sections, counts, common = d.blocks(result)
        self.assertEqual(set(sections), {'mechanisms', 'work', 'readiness'})
        self.assertEqual(len(counts), 135); self.assertTrue(common)
        changed = copy.deepcopy(result)
        changed['endpoints'][0]['learning_endpoint']['work_by_phase']['training']['circuit_examples'] += 1
        self.assertFalse(d.blocks(changed)[2])


class BindingTests(unittest.TestCase):
    def setUp(self):
        home = ROOT / 'analysis/classical_review/readiness_test_work'; home.mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='synthetic_diagnostics_', dir=home))
        (self.root / 'report_work').mkdir(); (self.root / 'learning').mkdir()
        self.payload = self.root / 'learning/population.json'; self.payload.write_text('{"synthetic_only":true}', encoding='utf-8')
        commit = {'status': 'PASS', 'files': {'population.json': {'sha256': d.sha(self.payload), 'bytes': self.payload.stat().st_size}}}
        path = self.root / 'learning/ANALYSIS_COMMIT.json'; path.write_text(json.dumps(commit), encoding='utf-8')
        proof = self.root / 'report_work/REPORT_INPUT_VERIFICATION.json'; proof.write_text('{}', encoding='utf-8')
        manifest = {'verification_sha256': d.sha(proof), 'inputs': {'learning_B_commit': {'relative_path': 'learning/ANALYSIS_COMMIT.json', 'sha256': d.sha(path)}}}
        (self.root / 'report_work/ROOT_REPORT_INPUTS.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.inputs = d.Inputs(self.root, {'learning_B_commit': commit}, manifest)

    def test_committed_json_and_mutation(self):
        self.assertTrue(self.inputs.committed_json('learning_B_commit', 'population.json')['synthetic_only'])
        self.payload.write_text('{"synthetic_only":false}', encoding='utf-8')
        with self.assertRaises(RuntimeError): self.inputs.committed_json('learning_B_commit', 'population.json')

    def test_uncommitted_and_escape_paths_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'not committed'): self.inputs.committed_json('learning_B_commit', 'other.json')
        with self.assertRaisesRegex(RuntimeError, 'Unsafe'): d.safe_file(self.root, '../outside.json')

    def test_missing_root_approval_stops_before_diagnostic_read(self):
        with patch.object(d, 'load', side_effect=RuntimeError('approval missing')):
            with patch.object(d.Inputs, 'committed_json', side_effect=AssertionError('Must not read supplemental data')):
                with self.assertRaisesRegex(RuntimeError, 'approval missing'): d.main()


class OutputTests(unittest.TestCase):
    def test_full_synthetic_write_commits_every_supplement(self):
        home = ROOT / 'analysis/classical_review/readiness_test_work'
        home.mkdir(exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix='synthetic_diagnostic_output_', dir=home))
        report_work = root / 'report_work'; report_work.mkdir()
        (root / 'SYNTHETIC_ONLY.txt').write_text('Synthetic report JSON workflow; no scientific outputs or real B evidence.', encoding='utf-8')
        for name in ('prepare_diagnostic_sections.py', 'prepare_measured_sections.py', 'load_report_inputs.py'):
            shutil.copyfile(ROOT / 'report_work' / name, report_work / name)
        populations, reports = training_fixture(); readiness, shots = readiness_fixture()
        data = {'evaluation': {'method_order': list(d.METHODS), 'population_order': list(d.POPS), 'training_seeds': list(d.SEEDS)},
                'readiness': readiness}
        manifest = {'inputs': {}}
        def save(path, value):
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value), encoding='utf-8')
        def add_input(key, relative, value):
            path = root / relative; save(path, value)
            manifest['inputs'][key] = {'relative_path': relative, 'sha256': d.sha(path)}
        for key, folder, values in (
            ('learning_B_commit', 'learning', {p + '.json': obj for p, obj in populations.items()}),
            ('evaluation_commit', 'evaluation', {f'{p}/seed_{s}/{m}/report.json': obj for (p, s, m), obj in reports.items()}),
            ('readiness_commit', 'readiness', {'report.json': readiness, 'finite_shot_records.json': shots})):
            files = {}
            for name, value in values.items():
                path = root / folder / name; save(path, value)
                files[name] = {'sha256': d.sha(path), 'bytes': path.stat().st_size}
            data[key] = {'status': 'completed', 'files': files}
            add_input(key, folder + '/COMMIT.json', data[key])
        add_input('evaluation', 'evaluation/summary.json', data['evaluation'])
        add_input('readiness', 'readiness/report.json', readiness)
        proof = report_work / 'REPORT_INPUT_VERIFICATION.json'; save(proof, {'status': 'SYNTHETIC_ONLY'})
        manifest['verification_sha256'] = d.sha(proof); save(report_work / 'ROOT_REPORT_INPUTS.json', manifest)
        spec = importlib.util.spec_from_file_location('synthetic_diagnostic_output_module', report_work / 'prepare_diagnostic_sections.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with patch.object(module, 'load', return_value=(data, manifest)):
            module.main()
        output = report_work / 'diagnostic_tables'
        commit = json.loads((output / 'DIAGNOSTIC_COMMIT.json').read_text())
        self.assertEqual(commit['status'], 'completed'); self.assertEqual(len(commit['files']), 9)
        self.assertEqual(commit['report_block_sha256'], d.sha(report_work / 'report_diagnostic_sections.json'))
        for name, metadata in commit['files'].items():
            self.assertEqual(metadata['sha256'], d.sha(output / name))
            self.assertEqual(metadata['bytes'], (output / name).stat().st_size)
        blocks = json.loads((report_work / 'report_diagnostic_sections.json').read_text())
        self.assertEqual(set(blocks['sections']), {'mechanisms', 'work', 'readiness'})


if __name__ == '__main__': unittest.main(verbosity=2)
