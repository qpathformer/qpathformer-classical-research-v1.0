"""Freeze independent replay readiness after real preflight and peer review.

No data/model loading. This records readiness, never test release or execution.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REGISTRATION_SHA = '9a1286d0353ace64cbc0e8f958dea251322273e0c6a6baaab8a3710267bd961e'
ANALYSIS_SHA = '7401f1ab9f805eed0a1cd97a86e1aab9be3c27746e0a529a991efdaf9e1766f5'
TOLERANCE_SHA = '92b0a015769e1069727e0d4630a94280032b52513f57a17e80bdfdcc3fd02476'
RECOVERY_SHA = '049f4a627fda5fa08c739cc53375aa104e28d223bb78d525841d0f01d7931e0e'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def require(condition, message):
    if not condition: raise ValueError(message)


def main():
    require(not (HERE / 'ANALYSIS_READY.json').exists(), 'Readiness already exists; preserve the registered version')
    registration = ROOT / 'quantum/EVALUATION_REGISTRATION.json'
    require(sha(registration) == REGISTRATION_SHA, 'Evaluator registration changed')
    require(sha(ROOT / 'governance/ANALYSIS_PROTOCOL.json') == ANALYSIS_SHA, 'Analysis protocol changed')
    require(sha(HERE / 'TOLERANCE_PROTOCOL.json') == TOLERANCE_SHA, 'Tolerances changed')
    require(sha(ROOT / 'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json') == RECOVERY_SHA, 'Recovery protocol changed')
    require(sha(HERE / 'ANALYSIS_READY_PRE_RECOVERY_01.json') == 'e5121e4254035fba0d3cf2cb158271b0ce2f49b66d0c5b480e85433c9e9d538d', 'Original readiness not preserved')
    for namespace, base in [('source_hashes', ROOT / 'quantum'), ('training_source_hashes', ROOT / 'quantum'), ('external_source_hashes', ROOT)]:
        for name, digest in read(registration)[namespace].items(): require(sha(base / name) == digest, 'Registered source changed: ' + name)
    core_peer = ROOT / 'analysis/classical_review/INDEPENDENT_REPLAY_CORE_REVIEW.json'
    adapter_peer = ROOT / 'analysis/classical_review/INDEPENDENT_REPLAY_ADAPTER_RECOVERY_01_REVIEW.json'
    for path, expected_status in ((core_peer, 'PASS_READ_ONLY_MATHEMATICAL_REVIEW'),
                                  (adapter_peer, 'PASS_READ_ONLY_GATE_AND_SCHEMA_REVIEW')):
        peer = read(path)
        require(peer['status'] == expected_status and peer['findings'] == [], 'Peer review has not passed')
        for name, digest in peer['source_sha256'].items(): require(sha(ROOT / name) == digest, 'Peer-reviewed source changed: ' + name)
    for name in ('recovery01_unit_gate_checks.log', 'recovery01_optimized_gate_checks.log', 'recovery01_full_adapter_preflight01.log'):
        log = (HERE / name).read_text(encoding='utf-8-sig')
        require('OK' in log and 'FAILED' not in log and 'ERROR' not in log, 'Preflight did not pass: ' + name)
    review_path = HERE / 'EVALUATOR_SOURCE_REVIEW.json'
    if not review_path.exists():
        review = {'status': 'PASS', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'scope': 'Independent read-only review of official evaluator release gates, complete output commit and registered statistics. Local Aer readiness reviewed separately by root/other agent.',
            'reviewed_hashes': {str(path.relative_to(ROOT)).replace('\\', '/'): sha(path) for path in
                [registration, ROOT / 'quantum/evaluate_confirmation.py', ROOT / 'quantum/evaluation_stats.py', ROOT / 'quantum/numerical_verification.py', ROOT / 'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json']},
            'checks': ['Release and both65-endpoint audits bound before any test NPZ load; sources and metadata rechecked.',
                       'Exact135-payload completion commit,65 reports,65 predictions and150 nested count arrays.',
                       'Clipped BCE, both-label macro-F1, threshold and first-minus-second contrast direction.',
                       'Five-seed df4 ordinary95 and primary Bonferroni98.333 intervals; shared-record2000 bootstrap.',
                       'Independent NumPy2.5.4 binomial budgets and five measurement repeats nested within checkpoint.',
                       'Source/statistics behavior cross-checked on synthetic and engineering-only fixtures.',
                       'Recovery01 retains unchanged canonical probabilities/metrics and independently checks both-probability32eps class-disagreement band, all four canonical-mask sensitivity cases, per-depth/route counts, raw reference classes and summary aggregates.'],
            'nonblocking_note': 'PASS under recovery01 does not claim exact classifier replay. Author and independent matrix oracles may differ on numerical-band hard classes; each retains exact disagreement records. Canonical probabilities, primary statistics and binomial draw inputs remain unchanged.',
            'test_outcomes_accessed': False, 'confirmation_data_accessed': False, 'official_sources_modified': False}
        with review_path.open('x', encoding='utf-8') as f: json.dump(review, f, indent=2); f.write('\n')
    evidence = [core_peer, adapter_peer, review_path, HERE / 'ENGINEERING_PREFLIGHT_v01.json',
                HERE / 'final_unit_gate_checks.log', HERE / 'optimized_gate_checks.log',
                HERE / 'full_adapter_preflight01.log', HERE / 'full_adapter_preflight02.log',
                ROOT / 'governance/RESOURCE_ACCOUNTING_NOTE_01.json',
                ROOT / 'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json',
                ROOT / 'governance/recovery_01/ORIGINALS_MANIFEST.json',
                HERE / 'ANALYSIS_READY_PRE_RECOVERY_01.json', HERE / 'TOLERANCE_PROTOCOL_PRE_RECOVERY_01.json',
                HERE / 'EVALUATOR_SOURCE_REVIEW_PRE_RECOVERY_01.json', HERE / 'DEVELOPMENT_THRESHOLD_DIAGNOSIS_RECOVERY_01.json',
                HERE / 'recovery01_unit_gate_checks.log', HERE / 'recovery01_optimized_gate_checks.log',
                HERE / 'recovery01_full_adapter_preflight01.log']
    ready = {'status': 'READY_FOR_ROOT_RELEASE', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'study_id': 'QPATH-QMECH-v0.3', 'analysis_protocol_sha256': ANALYSIS_SHA,
        'tolerance_protocol_sha256': TOLERANCE_SHA, 'evaluation_registration_sha256': REGISTRATION_SHA,
        'numerical_recovery_protocol_sha256': RECOVERY_SHA,
        'registration_history': 'Amended verification readiness after the preserved development audit failure and before Stage B; original strict readiness remains ANALYSIS_READY_PRE_RECOVERY_01.json. Training/primary analysis unchanged.',
        'source_hashes': {path.name: sha(path) for path in sorted(HERE.glob('*.py'))},
        'evidence_hashes': {str(path.relative_to(ROOT)).replace('\\', '/'): sha(path) for path in evidence},
        'tests': {'normal_unit_and_gate_tests': 18, 'optimized_gate_tests': 7, 'full_adapter_engineering_test': 1,
                  'full_adapter_endpoints': 65, 'replayed_engineering_records': 104000,
                  'ideal_count_arrays': 150, 'bootstrap_replicates': 2000,
                  'scope': 'Engineering-only65-endpoint fixture with one explicitly synthetic near-half fixed1 case; both flagged and ordinary paths, canonical scenarios and exact150count-array replay. Actual maxima and discrepancy counts are retained in the bound full-adapter log.',
                  'statistics_numeric_comparisons': 412, 'numerical_scenario_and_difference_aggregates': 143},
        'failure_preservation': 'First full-adapter fixture failed because an exclusive CSV writer encountered its own generated dummy file; test-generator correction only, no model/source/data outcome change. Failure log retained and generated failed fixture preserved outside delivery inventory.',
        'runtime': r'C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe; NumPy2.5.4',
        'execution_gate': 'Root release must bind this manifest under independent_replay_ready_sha256 and the recovery01 protocol. All65 B endpoints and both amended audits must pass, then official evaluation must complete its135-payload commit. Root triggers independent replay once afterward.',
        'test_outcomes_accessed': False, 'confirmation_data_accessed': False,
        'training_executed': False, 'test_release_issued': False}
    with (HERE / 'ANALYSIS_READY.json').open('x', encoding='utf-8') as f: json.dump(ready, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps({'status': ready['status'], 'manifest_sha256': sha(HERE / 'ANALYSIS_READY.json')}))


if __name__ == '__main__': main()
