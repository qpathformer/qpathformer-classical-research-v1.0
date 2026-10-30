"""Synthetic author-evaluator qualification. No official population is loaded."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scipy.special import expit
from scipy.stats import t
from metrics_v09 import metrics, average_precision, analyze, SCALARS
from evaluate_v09 import bank_diagnostics, actual_training_exposure, verified_resources
from release_gate_v09 import (binding, sha, verify_release, verify_completed_evaluation, evaluator_sources,
                              PROTOCOL_PATHS, EVALUATOR_FILES)

HERE = Path(__file__).resolve().parent
RUNS = HERE/'qualification_runs'
RUNS.mkdir(exist_ok=True)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')


class MetricsTests(unittest.TestCase):
    def test_manual_confusion_calibration_native(self):
        y = np.array([0, 1, 1, 0]); p = np.array([.1, .5, .8, .8]); z = np.log(p/(1-p))
        result = metrics(y, p, z)
        self.assertEqual(result['confusion'], [[1, 1], [0, 2]])
        self.assertAlmostEqual(result['macro_f1'], (2/3+4/5)/2)
        self.assertAlmostEqual(result['brier'], (.01+.25+.04+.64)/4)
        self.assertAlmostEqual(result['bce'], -np.log([.9, .5, .8, .2]).mean())
        self.assertAlmostEqual(result['native_bce'], result['bce'])
        self.assertAlmostEqual(result['positive_precision'], 2/3)
        self.assertEqual(result['positive_recall'], 1.)
        self.assertAlmostEqual(result['average_precision'], 7/12)
        self.assertAlmostEqual(result['ece10'], (.1+.5+2*.3)/4)

    def test_ties_empty_single_class_and_tails(self):
        y = np.array([0, 1, 0, 1]); p = np.full(4, .5)
        self.assertEqual(average_precision(y, p), .5)
        self.assertEqual(average_precision(y[::-1], p), .5)
        self.assertIsNone(average_precision(np.zeros(4), p))
        self.assertEqual(metrics([], [], [])['n'], 0)
        self.assertEqual(metrics(np.zeros(2), np.zeros(2), np.full(2, -1000.))['macro_f1'], .5)
        result = metrics(np.array([1, 0]), np.array([0., 1.]), np.array([-1000., 1000.]))
        self.assertEqual(result['native_bce'], 1000.)
        self.assertEqual(result['clipped_wrong_prediction_count'], 2)
        self.assertAlmostEqual(result['bce'], (-np.log(1e-7)-np.log1p(-(1-1e-7)))/2)

    def test_fixed_bin_boundaries(self):
        edges = np.linspace(0, 1, 11)
        p = np.r_[edges, np.nextafter(edges[1:-1], 0), np.nextafter(edges[1:-1], 1)]
        y = np.arange(len(p)) % 2; result = metrics(y, p, np.zeros(len(p)))
        counts = [0]*10
        for value in p:
            k = next((k for k in range(10) if edges[k] <= value < edges[k+1]), 9)
            counts[k] += 1
        self.assertEqual([b['count'] for b in result['reliability10']], counts)

    def test_population_not_seed_inference(self):
        families = ['checkerboard', 'spiral', 'annulus', 'disks']
        arms = ['C_H', 'C_S', 'C_L', 'C_R', 'T_H', 'T_S', 'T_L', 'T_R', 'G121']
        rows = []
        for family in families:
            for population in range(8):
                for seed in (1801, 1802):
                    for arm in arms:
                        value = .5 + (population+1)*.01*(arm == 'C_L') + .01*(seed == 1802)
                        rows.append(dict(job_id=f'{family}/{population}/{seed}/{arm}', family=family,
                                         population=f'{family}{population}', seed=seed, arm=arm,
                                         test={k: value for k in SCALARS}))
        for seed in range(1901, 1906):
            for arm in arms+['MLP2', 'MLP4', 'LR2']:
                rows.append(dict(job_id=f'banknote/{seed}/{arm}', family='banknote', population='banknote_01',
                                 seed=seed, arm=arm, test={k: .2 for k in SCALARS}))
        protocol = dict(family_size=12, populations_per_family=8, seeds_per_population=2,
                        nominal_per_contrast_confidence=1-.05/12,
                        primary_contrasts=[dict(family=f, first='C_L', second=a) for f in families for a in ('C_S', 'C_R', 'G121')],
                        secondary_contrasts=[dict(first='C_L', second='C_H'), dict(first='T_L', second='T_S'), dict(first='C_S', second='C_H')])
        result = analyze(rows, protocol); c = result['primary_contrasts'][0]
        expected = np.arange(1, 9)*.01
        self.assertAlmostEqual(c['mean_difference'], expected.mean())
        self.assertAlmostEqual(c['standard_error'], expected.std(ddof=1)/np.sqrt(8))
        self.assertAlmostEqual(c['interval'][1], expected.mean()+t.ppf(1-.05/24, 7)*expected.std(ddof=1)/np.sqrt(8))
        self.assertEqual(len(result['banknote_descriptive']), 12)
        self.assertEqual(len(c['populations']), 8)
        with self.assertRaises(ValueError):
            analyze(rows[:-1], protocol)


class DiagnosticTests(unittest.TestCase):
    def test_resource_identity_terminal_and_creation_binding(self):
        root = Path(tempfile.mkdtemp(prefix='resources_', dir=RUNS)); folder = root/'metadata'; folder.mkdir()
        identity = dict(pid=7134, creation_token='10101010', identity_source='synthetic_fixture')
        row = dict(metadata_dir=str(folder), identity_json=json.dumps(identity), attempt_id='attempt1', job_id='job1', status='succeeded')
        resources = dict(pid=7134, process_cpu_seconds=1.5, peak_working_set_bytes=12000, seconds_since_durable_ownership=2.)
        save(folder/'PROCESS_RESOURCES.json', resources)
        save(folder/'REQUEST.json', dict(attempt_id='attempt1', job={'run_id': 'job1'}, metadata_dir=str(folder)))
        terminal = dict(attempt_id='attempt1', job_id='job1', status='succeeded', details=dict(process_identity=identity, process_resources=resources))
        save(folder/'TERMINAL.json', terminal)
        result, evidence = verified_resources(root, row, {'process_identity': identity})
        self.assertEqual(result, resources); self.assertEqual(evidence['exact_worker_identity'], identity)
        with self.assertRaises(RuntimeError):
            verified_resources(root, row, {'process_identity': {**identity, 'creation_token': 'wrong'}})
        terminal['details']['process_resources'] = {**resources, 'peak_working_set_bytes': 12001}; save(folder/'TERMINAL.json', terminal)
        with self.assertRaises(RuntimeError):
            verified_resources(root, row, {'process_identity': identity})

    def test_actual_gate_exposure_replays_activation(self):
        folder = Path(tempfile.mkdtemp(prefix='gate_', dir=RUNS))
        rng = np.random.default_rng(910032)
        x = rng.normal(0, .2, (7, 2)); y = np.arange(7) % 2
        centres = rng.normal(0, .4, (5, 2)); tau = .3
        orders = np.tile(np.arange(4800) % 7, (200, 1)).astype(np.uint32)
        grads = np.zeros((15000, 14)); grads[:, 2:] = rng.normal(0, .01, (15000, 12))
        parameters = np.zeros((200, 14)); coeff = np.zeros(12); m = np.zeros(12); v = np.zeros(12); local_step = 0
        for i in range(15000):
            if i >= 750:
                local_step += 1; g = grads[i, 2:]
                m = .9*m+.1*g; v = .999*v+.001*g**2
                coeff -= .001*(m/(1-.9**local_step))/(np.sqrt(v/(1-.999**local_step))+1e-8)
            if (i+1) % 75 == 0:
                parameters[i//75, 2:] = coeff
        np.save(folder/'record_orders.npy', orders); np.save(folder/'minibatch_gradients.npy', grads)
        np.save(folder/'round_parameters.npy', parameters)
        np.save(folder/'training_record_exposure.npy', np.bincount(orders.ravel(), minlength=7))
        class MockModel:
            routing='L'; banks=5; expert_size=2
        model = MockModel(); model.centres = centres; model.tau = tau
        result = actual_training_exposure(model, dict(x=x, y=y), folder)
        exposure = np.array(result['class_bank_weighted_visits'])
        self.assertEqual(result['replayed_gate_updates'], 14250)
        np.testing.assert_allclose(exposure.sum(1), [(y[orders.ravel()] == k).sum() for k in (0, 1)], atol=1e-6)

    def test_all_arm_author_predictions_against_independent_oracle(self):
        import sys
        sys.path.insert(0, str(HERE.parents[1]/'quantum'))
        sys.path.insert(0, str(HERE.parent/'independent_audit'))
        from models import Model, METHODS
        import reference_v09 as oracle
        rng = np.random.default_rng(81132)
        policy = dict(centroids=[[-.7, -.6], [-.5, .6], [0., 0.], [.5, -.6], [.6, .6]],
                      tau=.23, residual_scale=np.ones(12).tolist())
        streams = dict(paired_circuit_core_initialization=713, mlp_initialization=919)
        for arm in METHODS:
            model = Model(arm, 0, streams, policy)
            model.parameters[:] = rng.normal(0, .4, len(model.parameters))
            x = rng.uniform(-1, 1, (13, model.input_dim)); y = np.arange(13) % 2
            p, z = model.predict_with_logits(x)
            op, oz = oracle.predict(arm, model.parameters, x, policy)
            np.testing.assert_allclose(p, op, atol=3e-13, rtol=0)
            np.testing.assert_allclose(z, oz, atol=3e-12, rtol=0)
            diag, q, ez = bank_diagnostics(model, x, y)
            np.testing.assert_allclose(q.sum(1), 1, atol=1e-14)
            self.assertEqual(ez.shape, (13, model.banks))
            if model.routing == 'L':
                az = ez[np.arange(13), np.argmax(q, axis=1)]
                self.assertAlmostEqual(diag['postfit_argmax_gate']['metrics']['native_bce'], metrics(y, expit(az), az)['native_bce'])


class ReleaseTests(unittest.TestCase):
    def fixture(self):
        root = Path(tempfile.mkdtemp(prefix='release_', dir=RUNS))
        for name in EVALUATOR_FILES:
            path = root/'analysis/author'/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('synthetic source fixture')
        sources = {}
        for name in ('models.py', 'study.py', 'circuits.py', 'reference_v03.py', 'prepare_data.py', 'routers.py', 'tests/test_v09_science.py'):
            p = root/'quantum'/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('synthetic source fixture'); sources[name] = sha(p)
        jobs = [dict(run_id=f'B/fixture_{i}/1801/G121', stage='B', population_id=f'fixture_{i}',
                     arm='G121', training_seed_id=1801, rounds=200, updates=15000) for i in range(636)]
        data = dict(study_plan={}, run_matrix={'runs': jobs}, analysis_protocol={'confirmation_count': 636}, data_seal={})
        for key, relative in PROTOCOL_PATHS.items():
            save(root/relative, data[key])
        protocols = {key: binding(root/relative) for key, relative in PROTOCOL_PATHS.items()}
        hashes = dict(data_seal_sha256=protocols['data_seal']['sha256'], matrix_sha256=protocols['run_matrix']['sha256'],
                      protocol_sha256=protocols['study_plan']['sha256'])
        auth = dict(schema='qpath-v09-stage-authorization-1', review_status='approved_by_root', stage='B',
                    scientific_source_hashes=sources, run_ids=[j['run_id'] for j in jobs], **hashes)
        authpath = root/'governance/auth.json'; save(authpath, auth)
        manifest_path = root/'governance/manifest.json'; save(manifest_path, dict(stage='B', jobs=jobs, authorization=binding(authpath)))
        endpoints = []
        for i, job in enumerate(jobs):
            folder = root/'attempts'/str(i); folder.mkdir(parents=True)
            checkpoint = folder/'selected_checkpoint.npz'; checkpoint.write_bytes(b'INERT FIXTURE; NEVER AN ARRAY')
            checkpoint_binding = binding(checkpoint)
            base = dict(job_id=job['run_id'], arm=job['arm'], population=job['population_id'], seed=1801,
                        completed_rounds=200, optimizer_global_updates=15000)
            commit = dict(schema='qpath-v09-endpoint-1', status='completed', stage='B', test_accessed=False,
                          source_hashes=sources, authorization_sha256=sha(authpath), **hashes, **base,
                          files={'selected_checkpoint.npz': {k: checkpoint_binding[k] for k in ('sha256', 'bytes')}})
            path = folder/'endpoint_commit.json'; save(path, commit)
            endpoints.append(dict(**base, selected_round=1, endpoint=str(folder), commit=binding(path), selected_checkpoint=checkpoint_binding))
        author = dict(schema='qpath-v09-author-stage-audit-1', status='PASS', stage='B', verified_endpoints=636,
                      endpoints=endpoints, test_model_outcomes_accessed=False, authorization=binding(authpath), manifest=binding(manifest_path))
        authorpath = root/'governance/author.json'; save(authorpath, author)
        independent = dict(schema='qpath-v09-independent-endpoint-audit-1', status='PASS', stage='B',
                           verified_endpoints=636, endpoints=endpoints, author_audit=binding(authorpath),
                           test_model_outcomes_accessed=False, manifest=binding(manifest_path))
        independentpath = root/'governance/independent.json'; save(independentpath, independent)
        release = dict(schema='qpath-v09-evaluation-release-1', review_status='approved_by_root', stage='B',
                       protocols=protocols, evaluator_sources=evaluator_sources(root), scientific_source_hashes=sources,
                       author_audit=binding(authorpath), independent_audit=binding(independentpath), endpoints=endpoints)
        path = root/'governance/release.json'; save(path, release)
        return root, path, release

    def test_gate_requires_all_exact_audited_endpoints(self):
        root, path, release = self.fixture()
        verified = verify_release(root, path)
        self.assertEqual(len(verified['jobs']), 636)
        folder = root/'evaluation'; folder.mkdir()
        payload = folder/'summary.json'; save(payload, {'synthetic_inert_fixture': True})
        commit = dict(schema='qpath-v09-author-evaluation-commit-1', status='PASS', scored_endpoints=636,
                      release=binding(path), evaluator_sources=evaluator_sources(root),
                      files={'summary.json': {k: binding(payload)[k] for k in ('sha256', 'bytes')}})
        commit_path = folder/'EVALUATION_COMMIT.json'; save(commit_path, commit)
        complete = verify_completed_evaluation(root, path, binding(commit_path))
        self.assertEqual(complete['evaluation_commit']['scored_endpoints'], 636)
        (folder/'unbound_extra.txt').write_text('Unbound extra evidence must be rejected')
        with self.assertRaises(RuntimeError):
            verify_completed_evaluation(root, path, binding(commit_path))
        # A 635-endpoint release must fail even though producer training exists.
        release['endpoints'] = release['endpoints'][:-1]; save(path, release)
        with self.assertRaises(RuntimeError):
            verify_release(root, path)

    def test_checkpoint_tamper_rejected_before_any_outcome_load(self):
        root, path, release = self.fixture()
        p = Path(release['endpoints'][0]['selected_checkpoint']['path']); p.write_bytes(b'TAMPER')
        with self.assertRaises(RuntimeError):
            verify_release(root, path)

    def test_independent_audit_test_access_and_manifest_disagreement(self):
        root, path, release = self.fixture()
        ipath = Path(release['independent_audit']['path']); independent = json.loads(ipath.read_text())
        independent['test_model_outcomes_accessed'] = True; save(ipath, independent)
        release['independent_audit'] = binding(ipath); save(path, release)
        with self.assertRaisesRegex(RuntimeError, 'Independent audit accessed'):
            verify_release(root, path)
        independent['test_model_outcomes_accessed'] = False
        independent['manifest'] = {**independent['manifest'], 'sha256': '0'*64}; save(ipath, independent)
        release['independent_audit'] = binding(ipath); save(path, release)
        with self.assertRaisesRegex(RuntimeError, 'same confirmation manifest'):
            verify_release(root, path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
