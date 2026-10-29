"""Whole-adapter preflight using ONLY engineering data/checkpoints and fake metadata.

All fake release, stage and evaluation files live under SYNTHETIC_ADAPTER_*.
They are never written into the real quantum workspace. Failure fixtures remain.
"""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import numpy as np
import replay_and_analyse as r
from test_gate import SyntheticGate, put

sys.path.insert(0, str(r.ROOT / 'quantum'))
import qstudy
import evaluation_stats
import evaluate_confirmation
import numerical_verification
import replay as official_replay


def engineering_fixture(fixture):
    q, root, here, official = fixture.q, fixture.root, fixture.here, fixture.official
    real_q = r.ROOT / 'quantum'
    data_path = q / 'data/confirmation_SEALED_test.npz'
    data_path.write_bytes((real_q / 'data/engineering_validation.npz').read_bytes())
    policy = q / 'data/confirmation_router.json'; policy.write_bytes((real_q / 'data/engineering_router.json').read_bytes())
    with np.load(data_path, allow_pickle=False) as f: pop = {k: f[k] for k in f.files}
    arrays = {k: r.hashlib.sha256(str(v.dtype).encode() + str(v.shape).encode() + np.ascontiguousarray(v).tobytes()).hexdigest() for k, v in pop.items()}
    seal_path = q / 'data/DATA_SEAL.json'
    put(seal_path, {'files': {data_path.name: {'sha256': r.sha(data_path), 'arrays': arrays,
                'router_policy_sha256': r.sha(policy)}}, 'routers': {'confirmation': {'sha256': r.sha(policy)}}})
    freeze_path = q / 'STAGE_B_FREEZE.json'; freeze = r.read(freeze_path)
    freeze['data_seal_sha256'] = r.sha(seal_path); put(freeze_path, freeze)
    lock_path = q / 'CONFIRMATION_ENDPOINT_LOCK.json'; lock = r.read(lock_path)
    lock['data_seal_sha256'] = r.sha(seal_path); lock['stage_freeze_sha256'] = r.sha(freeze_path)
    probabilities = np.empty((13, 5, 1600))
    reports = []
    for row in lock['endpoints']:
        seed, method = row['seed'], row['method']; folder = q / row['path']; destination = official / f'seed_{seed}' / method
        engineering = real_q / 'engineering_pilot_v01' / method
        with np.load(engineering / 'selected_checkpoint.npz', allow_pickle=False) as f: parameters = f['parameters'].copy()
        if method == 'fixed1' and seed == 601:
            # Synthetic near-half fixture exercises the amended path end to end.
            # This modifies only this generated fixture's parameters, never a real checkpoint.
            parameters = np.array([0., np.pi / 2, 0., np.pi / 2])
        np.savez(folder / 'selected_checkpoint.npz', parameters=parameters, adam_m=np.zeros_like(parameters),
                 adam_v=np.zeros_like(parameters), adam_t=np.asarray(75), current_round=np.asarray(1), completed_rounds=np.asarray(1))
        result = r.read(engineering / 'result.json')
        result.update({'method': method, 'seed': seed, 'stage': 'B', 'engineering': False, 'status': 'completed',
                       'completed_rounds': 200, 'optimizer_global_updates': 15000, 'test_accessed': False,
                       'selected_round': 1, 'finished_utc': '2026-01-01T00:01:00+00:00'})
        put(folder / 'result.json', result)
        config = r.read(folder / 'config.json'); config['data_seal_sha256'] = r.sha(seal_path); put(folder / 'config.json', config)
        row.update({k: r.sha(folder / name) for k, name in r.ENDPOINT_FILES.items()})
        model = qstudy.Model(method, seed); model.parameters[:] = parameters
        probability = model.predict_population(pop)
        probabilities[r.METHODS.index(method), r.TRAINING_SEEDS.index(seed)] = probability
        (destination / 'predictions.csv').unlink()  # Remove only this fixture's dummy payload.
        qstudy.save_predictions(destination / 'predictions.csv', pop, probability)
        report = {'status': 'completed', 'method': method, 'seed': seed, 'stage': 'B', 'selected_round': 1,
                  'selected_checkpoint_sha256': row['selected_checkpoint_sha256'], 'training_result_sha256': row['result_sha256'],
                  'config_sha256': row['config_sha256'], 'test_payload_sha256': r.sha(data_path),
                  'predictions_sha256': r.sha(destination / 'predictions.csv'), 'metrics': qstudy.metrics(pop['y'], probability),
                  'by_original_depth': {str(d): qstudy.metrics(pop['y'][pop['depth'] == d], probability[pop['depth'] == d]) for d in range(1, 5)},
                  'by_route': {kind: {str(k): qstudy.metrics(pop['y'][pop[kind + '_route'] == k], probability[pop[kind + '_route'] == k])
                                      for k in range(5) if np.any(pop[kind + '_route'] == k)} for kind in ('hash', 'kmeans')}}
        report['numerical_verification'] = numerical_verification.verify_pair(pop, probability,
            official_replay.predict(method, parameters, pop['x'], pop['depth'], pop['hash_route'], pop['kmeans_route']))
        put(destination / 'report.json', report); reports.append(report)
    put(lock_path, lock)
    audit_path = root / 'analysis/classical_review/B.json'; audit = r.read(audit_path)
    audit['endpoint_lock_sha256'] = r.sha(lock_path); put(audit_path, audit)
    review_path = q / 'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json'; review = r.read(review_path)
    review.update(endpoint_lock_sha256=r.sha(lock_path), independent_audit_sha256=r.sha(audit_path)); put(review_path, review)
    registration_path = q / 'EVALUATION_REGISTRATION.json'; registration = r.read(registration_path)
    registration['data_seal_sha256'] = r.sha(seal_path); put(registration_path, registration)
    ready_path = here / 'ANALYSIS_READY.json'; ready = r.read(ready_path)
    ready['evaluation_registration_sha256'] = r.sha(registration_path); put(ready_path, ready)
    release = r.read(fixture.release)
    release.update(registration_sha256=r.sha(registration_path), endpoint_lock_sha256=r.sha(lock_path),
                   independent_endpoint_review_sha256=r.sha(review_path), stage_freeze_sha256=r.sha(freeze_path),
                   data_seal_sha256=r.sha(seal_path), independent_replay_ready_sha256=r.sha(ready_path))
    put(fixture.release, release)
    protocol = r.read(root / 'governance/ANALYSIS_PROTOCOL.json')
    summary, bootstrap = evaluation_stats.summarize(pop['y'], probabilities, list(r.METHODS), protocol)
    np.savez_compressed(official / 'bootstrap_arrays.npz', metric_means=bootstrap, method_order=np.asarray(r.METHODS), metric_order=np.asarray(r.METRICS))
    # Remove only the two explicitly created dummy readout files in this fixture.
    readout_dir = (official / 'readout').resolve()
    if not readout_dir.is_relative_to(root.resolve()): raise ValueError('Unsafe synthetic fixture path')
    for name in ('counts.npz', 'summary.json'): (readout_dir / name).unlink()
    readout_dir.rmdir()
    evaluate_confirmation.finite_shots(pop, probabilities, readout_dir)
    summary.update(status='completed', report_count=65, release_id=release['release_id'],
                   numerical_recovery_protocol_sha256=r.RECOVERY_SHA,
                   numerical_verification=evaluate_confirmation.summarize_numerical(reports),
                   analysis_protocol_sha256=r.ANALYSIS_SHA, endpoint_lock_sha256=r.sha(lock_path),
                   registration_sha256=r.sha(registration_path), test_payload_sha256=r.sha(data_path),
                   bootstrap_sha256=r.sha(official / 'bootstrap_arrays.npz'), readout_summary_sha256=r.sha(readout_dir / 'summary.json'))
    put(official / 'summary.json', summary)
    event = r.read(official / 'ACCESS_EVENT.json'); event['release_sha256'] = r.sha(fixture.release); put(official / 'ACCESS_EVENT.json', event)
    commit = r.read(official / 'EVALUATION_COMMIT.json')
    commit.update(release_sha256=r.sha(fixture.release), registration_sha256=r.sha(registration_path), endpoint_lock_sha256=r.sha(lock_path),
                  files={name: {'sha256': r.sha(official / name), 'bytes': (official / name).stat().st_size} for name in fixture.expected_files})
    put(official / 'EVALUATION_COMMIT.json', commit)


class FullAdapterCheck(unittest.TestCase):
    def test_engineering_full_adapter_65_reports_150_readouts_2000_bootstraps(self):
        parent = r.HERE / 'synthetic_fixture_work'; parent.mkdir(exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix='SYNTHETIC_ADAPTER_', dir=parent)).resolve()
        self.assertTrue(root.is_relative_to(parent.resolve()))
        success = False
        try:
            fixture = SyntheticGate(root); engineering_fixture(fixture)
            output = fixture.here / 'SYNTHETIC_REPLAY_RESULTS'
            # Keep routine65 progress lines in memory; the completion evidence is below.
            with redirect_stdout(io.StringIO()): r.run(fixture.release, output, root)
            summary = r.read(output / 'summary.json'); readout = r.read(output / 'readout_summary.json')
            self.assertEqual(summary['status'], 'PASS'); self.assertEqual(summary['endpoint_count'], 65)
            self.assertEqual(summary['prediction_records_replayed'], 104000)
            self.assertGreater(summary['classification_disagreements'], 0)
            self.assertFalse(summary['exact_classifier_agreement'])
            self.assertEqual(summary['outside_band_disagreements'], 0)
            self.assertEqual(summary['canonical_near_band_count'], 1600)
            self.assertEqual(summary['numerical_summary_comparison']['status'], 'PASS')
            self.assertEqual(readout['count_arrays'], 150)
            self.assertEqual(r.read(output / 'REPLAY_COMMIT.json')['status'], 'PASS')
            print(json.dumps({'fixture_scope': 'ENGINEERING_ONLY_WITH_SYNTHETIC_METADATA',
                'endpoints': 65, 'prediction_records': 104000, 'readout_arrays': 150, 'bootstrap_replicates': 2000,
                'maximum_probability_error': summary['maximum_probability_error'],
                'maximum_bce_error': summary['maximum_bce_absolute_error'],
                'classification_disagreements': summary['classification_disagreements'],
                'canonical_near_band_count': summary['canonical_near_band_count'],
                'outside_band_disagreements': summary['outside_band_disagreements'],
                'numerical_summary_comparison': summary['numerical_summary_comparison'],
                'statistics_comparison': summary['statistics_comparison']}), flush=True)
            success = True
        finally:
            if success:
                if not root.is_relative_to(parent.resolve()): raise ValueError('Unsafe synthetic cleanup path')
                shutil.rmtree(root)
            else: print('Preserved failed SYNTHETIC fixture: ' + str(root), flush=True)


if __name__ == '__main__': unittest.main(verbosity=2)
