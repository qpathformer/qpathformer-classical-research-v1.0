"""Synthetic metadata-only gate tests; no real confirmation arrays/outcomes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import replay_and_analyse as r


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


class SyntheticGate:
    def __init__(self, root):
        self.root = root; self.q = root / 'quantum'; self.here = root / 'analysis/independent_replay'
        self.here.mkdir(parents=True); self.q.mkdir()
        protocol = root / 'governance/ANALYSIS_PROTOCOL.json'; protocol.parent.mkdir()
        protocol.write_bytes((r.ROOT / 'governance/ANALYSIS_PROTOCOL.json').read_bytes())
        (root / 'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json').write_bytes((r.ROOT / 'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json').read_bytes())
        (self.here / 'TOLERANCE_PROTOCOL.json').write_bytes((r.HERE / 'TOLERANCE_PROTOCOL.json').read_bytes())
        source = self.q / 'synthetic.py'; source.write_text('# SYNTHETIC METADATA FIXTURE', encoding='utf-8')
        sources = {'synthetic.py': r.sha(source)}
        auditor = root / 'analysis/classical_review/audit_endpoints_v03.py'; auditor.parent.mkdir()
        auditor.write_text('# SYNTHETIC AUDITOR FIXTURE', encoding='utf-8')
        external = {'analysis/classical_review/audit_endpoints_v03.py': r.sha(auditor)}
        seal = self.q / 'data/DATA_SEAL.json'; put(seal, {'synthetic': True})
        freeze = self.q / 'STAGE_B_FREEZE.json'
        put(freeze, {'review_status': 'approved_by_root', 'stage': 'B', 'methods': list(r.METHODS),
             'training_seeds': list(r.TRAINING_SEEDS), 'settings': {'rounds': 200, 'optimizer_updates': 15000},
             'data_seal_sha256': r.sha(seal), 'source_hashes': sources,
             'protocol_hashes': {'ANALYSIS_PROTOCOL.json': r.ANALYSIS_SHA}})
        rows = []
        for seed in r.TRAINING_SEEDS:
            for method in r.METHODS:
                folder = self.q / 'stage_B' / f'seed_{seed}' / method; folder.mkdir(parents=True)
                for name in r.ENDPOINT_FILES.values(): (folder / name).write_text('SYNTHETIC INVALID-NPZ PAYLOAD', encoding='utf-8')
                put(folder / 'result.json', {'method': method, 'seed': seed, 'stage': 'B', 'engineering': False,
                     'status': 'completed', 'completed_rounds': 200, 'optimizer_global_updates': 15000,
                     'test_accessed': False, 'finished_utc': '2026-01-01T00:01:00+00:00'})
                put(folder / 'status.json', {'status': 'completed', 'round': 200, 'seed': seed, 'method': method})
                put(folder / 'config.json', {'source_hashes': sources, 'data_seal_sha256': r.sha(seal)})
                rows.append({'method': method, 'seed': seed, 'path': folder.relative_to(self.q).as_posix(), 'selected_round': 1,
                             **{k: r.sha(folder / name) for k, name in r.ENDPOINT_FILES.items()}})
        exits = [{'seed': seed, 'exit_code': 0} for seed in r.TRAINING_SEEDS]
        put(self.q / 'stage_B/stage_status.json', {'status': 'completed', 'exits': exits, 'finished_utc': '2026-01-01T00:02:00+00:00'})
        put(self.q / 'stage_B/process_exits.json', exits)
        lock = self.q / 'CONFIRMATION_ENDPOINT_LOCK.json'
        put(lock, {'status': 'PASS', 'stage': 'B', 'endpoint_count': 65, 'test_accessed': False, 'endpoints': rows,
             'numerical_recovery_protocol_sha256': r.RECOVERY_SHA,
             'stage_freeze_sha256': r.sha(freeze), 'data_seal_sha256': r.sha(seal), 'training_source_hashes': sources,
             'audit_sources': sources, 'created_utc': '2026-01-01T00:03:00+00:00'})
        audit = root / 'analysis/classical_review/B.json'
        put(audit, {'status': 'PASS', 'stage': 'B', 'endpoint_count': 65, 'endpoint_lock_sha256': r.sha(lock),
                    'numerical_recovery_protocol_sha256': r.RECOVERY_SHA,
                    'auditor_sha256': r.sha(auditor), 'created_utc': '2026-01-01T00:04:00+00:00'})
        review = self.q / 'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json'
        put(review, {'status': 'PASS', 'stage': 'B', 'endpoint_count': 65, 'endpoint_lock_sha256': r.sha(lock),
                     'numerical_recovery_protocol_sha256': r.RECOVERY_SHA,
                     'independent_audit_path': audit.relative_to(root).as_posix(), 'independent_audit_sha256': r.sha(audit)})
        self.expected_files = {'ACCESS_EVENT.json', 'summary.json', 'bootstrap_arrays.npz', 'readout/counts.npz', 'readout/summary.json'}
        self.expected_files.update(f'seed_{seed}/{method}/{name}' for seed in r.TRAINING_SEEDS for method in r.METHODS
                                   for name in ('report.json', 'predictions.csv'))
        registration = self.q / 'EVALUATION_REGISTRATION.json'
        put(registration, {'status': 'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS', 'analysis_protocol_sha256': r.ANALYSIS_SHA,
             'numerical_recovery_protocol_sha256': r.RECOVERY_SHA,
             'method_order': list(r.METHODS), 'training_seeds': list(r.TRAINING_SEEDS), 'data_seal_sha256': r.sha(seal),
             'source_hashes': sources, 'training_source_hashes': sources, 'external_source_hashes': external,
             'expected_output_paths': sorted(self.expected_files),
             'readout': {'methods': list(r.READOUT_METHODS), 'budgets': list(r.SHOT_BUDGETS), 'shot_seeds': list(r.MEASUREMENT_SEEDS)}})
        ready = self.here / 'ANALYSIS_READY.json'
        put(ready, {'status': 'READY_FOR_ROOT_RELEASE', 'test_outcomes_accessed': False, 'analysis_protocol_sha256': r.ANALYSIS_SHA,
             'numerical_recovery_protocol_sha256': r.RECOVERY_SHA,
             'tolerance_protocol_sha256': r.TOLERANCE_SHA, 'evaluation_registration_sha256': r.sha(registration),
             'source_hashes': {}, 'evidence_hashes': {}})
        self.release = self.q / 'EVALUATION_RELEASE.json'
        put(self.release, {'status': 'released_by_root', 'study_id': 'QPATH-QMECH-v0.3',
             'scope': 'all_65_registered_confirmation_endpoints_once', 'release_id': 'SYNTHETIC-ONLY-NOT-A-REAL-RELEASE',
             'created_utc': '2026-01-01T00:05:00+00:00', 'registration_sha256': r.sha(registration),
             'endpoint_lock_sha256': r.sha(lock), 'independent_endpoint_review_sha256': r.sha(review),
             'stage_freeze_sha256': r.sha(freeze), 'data_seal_sha256': r.sha(seal),
             'analysis_protocol_sha256': r.ANALYSIS_SHA, 'independent_replay_ready_sha256': r.sha(ready)})
        release = r.read(self.release); release['numerical_recovery_protocol_sha256'] = r.RECOVERY_SHA; put(self.release, release)
        self.official = self.q / 'confirmation_evaluation'
        for relative in self.expected_files:
            path = self.official / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('SYNTHETIC NON-OUTCOME PAYLOAD', encoding='utf-8')
        put(self.official / 'ACCESS_EVENT.json', {'event': 'ROOT_RELEASE_VERIFIED_BEFORE_CONFIRMATION_TEST_LOAD',
             'release_sha256': r.sha(self.release), 'release_id': 'SYNTHETIC-ONLY-NOT-A-REAL-RELEASE', 'created_utc': '2026-01-01T00:06:00+00:00'})
        put(self.official / 'EVALUATION_COMMIT.json', {'status': 'completed', 'study_id': 'QPATH-QMECH-v0.3',
             'report_count': 65, 'prediction_file_count': 65, 'count_array_count': 150, 'payload_count': 135,
             'release_id': 'SYNTHETIC-ONLY-NOT-A-REAL-RELEASE', 'release_sha256': r.sha(self.release),
             'registration_sha256': r.sha(registration), 'endpoint_lock_sha256': r.sha(lock), 'completed_utc': '2026-01-01T00:07:00+00:00',
             'files': {name: {'sha256': r.sha(self.official / name), 'bytes': (self.official / name).stat().st_size} for name in self.expected_files}})


class GateChecks(unittest.TestCase):
    def setUp(self):
        self.parent = r.HERE / 'synthetic_fixture_work'; self.parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='SYNTHETIC_ONLY_', dir=self.parent)
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(self.parent.resolve()))
        self.fixture = SyntheticGate(self.root)

    def tearDown(self): self.temporary.cleanup()

    def test_complete_metadata_gate_never_opens_arrays(self):
        with patch.object(r.np, 'load', side_effect=AssertionError('ARRAY LOAD IS FORBIDDEN IN METADATA GATE')) as loader:
            gate = r.verify_gate(self.fixture.release, self.root)
            self.assertEqual(gate['commit']['report_count'], 65)
            loader.assert_not_called()

    def test_mutations_fail_before_array_load_or_output_creation(self):
        q = self.fixture.q
        changes = [
            (self.fixture.release, lambda value: value.update(status='not_released')),
            (q / 'stage_B/stage_status.json', lambda value: value.update(status='running')),
            (q / 'stage_B/stage_status.json', lambda value: value.update(finished_utc='2026-01-02T00:00:00+00:00')),
            (q / 'CONFIRMATION_ENDPOINT_LOCK.json', lambda value: value.update(endpoint_count=64)),
            (q / 'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json', lambda value: value.update(status='FAIL')),
            (self.fixture.here / 'ANALYSIS_READY.json', lambda value: value.update(status='UNREVIEWED')),
            (self.fixture.official / 'EVALUATION_COMMIT.json', lambda value: value.update(status='running')),
            (self.fixture.official / 'EVALUATION_COMMIT.json', lambda value: value['files'].pop('seed_605/mlp129/report.json')),
        ]
        for index, (path, modify) in enumerate(changes):
            with self.subTest(mutation=index):
                saved = path.read_bytes(); value = json.loads(saved); modify(value); put(path, value)
                output = self.fixture.here / f'forbidden_output_{index}'
                try:
                    with patch.object(r.np, 'load', side_effect=AssertionError('PREMATURE ARRAY LOAD')) as loader:
                        with self.assertRaises(ValueError): r.run(self.fixture.release, output, self.root)
                        loader.assert_not_called()
                    self.assertFalse(output.exists())
                finally: path.write_bytes(saved)
        endpoint = q / 'stage_B/seed_605/mlp129/selected_checkpoint.npz'
        endpoint.write_text('CHANGED SYNTHETIC CHECKPOINT', encoding='utf-8')
        with patch.object(r.np, 'load', side_effect=AssertionError('PREMATURE ARRAY LOAD')) as loader:
            with self.assertRaises(ValueError): r.verify_gate(self.fixture.release, self.root)
            loader.assert_not_called()


if __name__ == '__main__': unittest.main(verbosity=2)
