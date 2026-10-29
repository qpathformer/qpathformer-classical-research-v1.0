"""Register immutable independent replay readiness after synthetic peer review.

This checks metadata/source evidence only. It cannot read a sealed population
or an official result, and cannot release a test or execute a checkpoint.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from evidence_io import contained, digest, read_bound, recheck, require

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
REGISTRATION_SHA256 = '401e8ebed00499a82bdd4e392a33f97269d0ee4078f5bb7c8653b11287b4cbf0'
EVIDENCE = (
    'analysis/classical_review/STATISTICS_AND_REPLAY_CORES_INDEPENDENT_REVIEW.json',
    'analysis/classical_review/INDEPENDENT_REPLAY_ADAPTER_REVIEW.json',
    'analysis/independent_replay/CORE_TESTS_NORMAL_ATTEMPT01.log',
    'analysis/independent_replay/CORE_TESTS_OPTIMIZED_ATTEMPT01.log',
    'analysis/independent_replay/PREDICTION_TESTS_NORMAL_ATTEMPT01.log',
    'analysis/independent_replay/PREDICTION_TESTS_OPTIMIZED_ATTEMPT01.log',
    'analysis/independent_replay/ADAPTER_TESTS_NORMAL_ATTEMPT01.log',
    'analysis/independent_replay/ADAPTER_TESTS_NORMAL_ATTEMPT02.log',
    'analysis/independent_replay/ADAPTER_TESTS_OPTIMIZED_ATTEMPT01.log',
    'analysis/independent_replay/RELOCATED_PREFLIGHT_RESULT.json',
    'analysis/independent_replay/RELOCATED_PREFLIGHT_CLI.log',
)


def main():
    ready = HERE / 'ANALYSIS_READY.json'
    require(not ready.exists(), 'Preserve prior READY; registration is exclusive')
    require(not (STUDY / 'quantum/EVALUATION_RELEASE.json').exists()
            and not (STUDY / 'quantum/confirmation_evaluation').exists(), 'Must register before actual test release/access')
    watched = {}
    registry_path = STUDY / 'quantum/EVALUATION_REGISTRATION.json'
    registry = read_bound(registry_path, watched)
    require(digest(registry_path) == REGISTRATION_SHA256 and registry['status'] == 'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS',
            'Unexpected final official registration')
    for name, expected in registry['source_hashes'].items():
        require(digest(contained(STUDY, name)) == expected, 'Official registered source changed: ' + name)
    paths = sorted(HERE.glob('*.py')) + [STUDY / 'analysis/classical_review/reference_v05.py']
    sources = {path.relative_to(STUDY).as_posix(): digest(path) for path in paths}
    evidence = {name: digest(contained(STUDY, name)) for name in EVIDENCE}
    review = read_bound(STUDY / 'analysis/classical_review/INDEPENDENT_REPLAY_ADAPTER_REVIEW.json', watched)
    require(review['status'] == 'PASS', 'Independent adapter peer review has not passed')
    require(review['source_hashes'] == sources and review['registration_sha256'] == REGISTRATION_SHA256,
            'Adapter peer review does not bind every current source and actual registry')
    preflight = read_bound(HERE / 'RELOCATED_PREFLIGHT_RESULT.json', watched)
    require(preflight['status'] == 'PASS' and preflight['synthetic_only'] is True
            and preflight['real_confirmation_outcomes_accessed'] is False and preflight['endpoint_count'] == 165
            and preflight['prediction_pairs_replayed'] == 264000 and preflight['metadata_rewritten'] is False,
            'Complete relocated synthetic preflight missing')
    require(preflight['current_source_hashes'] == {path.name: sources[path.relative_to(STUDY).as_posix()] for path in HERE.glob('*.py')},
            'Relocated preflight does not bind every current independent source')
    require(digest(HERE / 'RELOCATED_PREFLIGHT_CLI.log') == preflight['log_sha256'], 'Relocated CLI evidence changed')
    for name, expected in {**sources, **evidence}.items(): watched[str(contained(STUDY, name).resolve())] = expected
    recheck(watched)
    oracle = 'analysis/classical_review/reference_v05.py'
    result = {'status': 'READY_BEFORE_CONFIRMATION_TEST_ACCESS', 'study_id': 'QPATH-READOUT-v0.5',
              'created_utc': datetime.now(timezone.utc).isoformat(), 'registration_sha256': REGISTRATION_SHA256,
              'analysis_protocol_sha256': digest(STUDY / 'governance/ANALYSIS_PROTOCOL.json'),
              'independent_oracle_path': oracle, 'independent_oracle_sha256': sources[oracle],
              'source_hashes': sources, 'evidence_hashes': evidence,
              'model_test_outcomes_accessed': False,
              'scope': 'After root release and actual official completion only: all165 frozen checkpoints,264000 checkpoint-record probabilities, frozen cores, native logits/loss, canonical BCE/F1/accuracy/Brier/calibration, numerical32eps diagnostics, all17 contrasts in each of3 populations, paired-five-seed Student intervals (ordinary95% and primary12-family adjusted) and10000 paired-record bootstrap replicates with exact count hashes.',
              'portability': 'Recorded absolute identities validated beneath registry original_working_root, then remapped to current package root without metadata changes; copied actual CLI synthetic preflight blocked all file opens under original study outside copied package.',
              'synthetic_scope': 'I/O fixtures use scalar versus vector independent oracle variants and independent statistics; they test complete schema, integrity and relocation. A separate peer core comparison checked the official statistics on synthetic populations. No official statistics module is imported by this implementation.',
              'generated_fixture_policy': 'synthetic_fixture_work is reproducible generated testing material, preserved in working tree and excluded from scientific deliverable findings. Durable source/log/summary evidence is retained.'}
    with ready.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, allow_nan=False); handle.write('\n')
    print(json.dumps({'status': result['status'], 'path': str(ready), 'sha256': digest(ready)}))


if __name__ == '__main__':
    main()
