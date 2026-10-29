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
REGISTRATION_SHA256 = '64d4954472dd3575248f0e98aa2012f74ec64ee678473af4aa92877a4ef8942a'
EVIDENCE = (
    'analysis/classical_review/STATISTICS_AND_NUMERICAL_PEER_REVIEW.json',
    'analysis/classical_review/INDEPENDENT_REPLAY_ADAPTER_REVIEW.json',
    'analysis/independent_replay/CORE_SYNTHETIC_TESTS.log',
    'analysis/independent_replay/CORE_SYNTHETIC_TESTS_ATTEMPT02.log',
    'analysis/independent_replay/ADAPTER_SYNTHETIC_TESTS_ATTEMPT01.log',
    'analysis/independent_replay/ADAPTER_SYNTHETIC_TESTS_ATTEMPT02.log',
    'analysis/independent_replay/ADAPTER_SYNTHETIC_OPTIMIZED_TESTS.log',
    'analysis/independent_replay/ADAPTER_SYNTHETIC_OPTIMIZED_TESTS_ATTEMPT02.log',
    'analysis/independent_replay/RELOCATED_PREFLIGHT_RESULT.json',
    'analysis/independent_replay/RELOCATED_PREFLIGHT_CLI.log',
    'analysis/independent_replay/ENDPOINT_AUDITOR_SOURCE_REVIEW.json',
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
    paths = sorted(HERE.glob('*.py')) + [STUDY / 'analysis/classical_review/reference_v04.py']
    sources = {path.relative_to(STUDY).as_posix(): digest(path) for path in paths}
    evidence = {name: digest(contained(STUDY, name)) for name in EVIDENCE}
    review = read_bound(STUDY / 'analysis/classical_review/INDEPENDENT_REPLAY_ADAPTER_REVIEW.json', watched)
    require(review['status'] == 'PASS', 'Independent adapter peer review has not passed')
    require(review['source_hashes'] == sources and review['registration_sha256'] == REGISTRATION_SHA256,
            'Adapter peer review does not bind every current source and actual registry')
    preflight = read_bound(HERE / 'RELOCATED_PREFLIGHT_RESULT.json', watched)
    require(preflight['status'] == 'PASS' and preflight['synthetic_only'] is True
            and preflight['real_confirmation_outcomes_accessed'] is False and preflight['endpoint_count'] == 135
            and preflight['prediction_pairs_replayed'] == 216000 and preflight['metadata_rewritten'] is False,
            'Complete relocated synthetic preflight missing')
    require(preflight['current_source_hashes'] == {path.name: sources[path.relative_to(STUDY).as_posix()] for path in HERE.glob('*.py')},
            'Relocated preflight does not bind every current independent source')
    require(digest(HERE / 'RELOCATED_PREFLIGHT_CLI.log') == preflight['log_sha256'], 'Relocated CLI evidence changed')
    for name, expected in {**sources, **evidence}.items(): watched[str(contained(STUDY, name).resolve())] = expected
    recheck(watched)
    oracle = 'analysis/classical_review/reference_v04.py'
    result = {'status': 'READY_BEFORE_CONFIRMATION_TEST_ACCESS', 'study_id': 'QPATH-ROUTING-v0.4',
              'created_utc': datetime.now(timezone.utc).isoformat(), 'registration_sha256': REGISTRATION_SHA256,
              'analysis_protocol_sha256': digest(STUDY / 'governance/ANALYSIS_PROTOCOL.json'),
              'independent_oracle_path': oracle, 'independent_oracle_sha256': sources[oracle],
              'source_hashes': sources, 'evidence_hashes': evidence,
              'model_test_outcomes_accessed': False,
              'scope': 'After root release and actual official completion only: all135 frozen checkpoints,216000 checkpoint-record probabilities, canonical metrics, independent probabilities/BCE, numerical32eps diagnostics, all17 contrasts in each of3 populations, paired-five-seed Student intervals and5000 paired-record bootstrap with exact count hashes.',
              'portability': 'Recorded absolute identities validated beneath registry original_working_root, then remapped to current package root without metadata changes; copied actual CLI synthetic preflight blocked all file opens under original study outside copied package.',
              'first_core_failure': 'Preserved initial synthetic comparison failure concerned in-memory tuple versus persisted JSON list representation; corrected comparator uses actual persisted JSON. No real outcomes involved.',
              'generated_fixture_policy': 'synthetic_fixture_work is reproducible generated testing material, preserved in working tree and excluded from scientific deliverable findings. Durable source/log/summary evidence is retained.'}
    with ready.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, allow_nan=False); handle.write('\n')
    print(json.dumps({'status': result['status'], 'path': str(ready), 'sha256': digest(ready)}))


if __name__ == '__main__':
    main()
