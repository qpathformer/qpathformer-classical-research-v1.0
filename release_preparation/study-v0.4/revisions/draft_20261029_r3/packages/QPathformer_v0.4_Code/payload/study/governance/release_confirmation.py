"""Root-only, metadata-only release after all 135 confirmation endpoints pass.

This does not evaluate a model or load sealed test arrays. Preserve any failure;
never edit an issued release to work around a failed guard.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / 'quantum'
sys.path.insert(0, str(Q))
import study as s
import evaluate_confirmation as evaluator


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(independent_audit):
    audit_path = (ROOT / independent_audit).resolve()
    require(audit_path.is_relative_to(ROOT), 'Independent audit must be in the study')
    for path in (evaluator.REVIEW, evaluator.RELEASE, evaluator.OUTPUT):
        require(not path.exists(), 'Prior release/review/evaluation exists; never duplicate: ' + str(path))
    lock = s.read_json(evaluator.LOCK)
    audit = s.read_json(audit_path)
    status = s.read_json(Q / 'stage_B/stage_status.json')
    freeze = s.read_json(Q / 'STAGE_B_FREEZE.json')
    ready_path = ROOT / 'analysis/independent_replay/ANALYSIS_READY.json'
    ready = s.read_json(ready_path)
    reg = s.read_json(evaluator.REGISTRATION)
    for obj in (lock, audit):
        require(obj['status'] == 'PASS' and obj['stage'] == 'B' and obj['engineering'] is False and obj['endpoint_count'] == 135, 'All 135 full endpoints must pass both audits')
    require(audit['validation_rounds_replayed'] == 27000 and audit['validation_predictions_replayed'] == 43200000, 'Independent replay must cover every validation round')
    require(audit['endpoint_lock_sha256'] == s.digest(evaluator.LOCK), 'Independent audit does not bind current author lock')
    require(status['status'] == 'completed' and status['committed_endpoints'] == 135, 'Stage B is not complete')
    require(sorted((row['seed'], row['exit_code']) for row in status['exits']) == [(seed, 0) for seed in s.SEEDS['B']], 'All five registered workers must close successfully')
    require(freeze['review_status'] == 'approved_by_root' and freeze['stage'] == 'B', 'Missing root B approval')
    require(freeze['source_hashes'] == lock['source_hashes'] == reg['training_source_hashes'] == s.source_hashes(), 'Training sources changed')
    require(ready['status'] == 'READY_BEFORE_CONFIRMATION_TEST_ACCESS' and ready['study_id'] == 'QPATH-ROUTING-v0.4', 'Independent replay is not registered ready')
    require(ready['registration_sha256'] == s.digest(evaluator.REGISTRATION), 'Replay readiness registration mismatch')
    expected = {(p, seed, m) for p in s.POPULATIONS['B'] for seed in s.SEEDS['B'] for m in s.METHODS}
    for obj in (lock, audit):
        require(len(obj['endpoints']) == 135 and {(r['population'], r['seed'], r['method']) for r in obj['endpoints']} == expected, 'Missing or duplicate endpoint identity')
    # The official metadata-only guard below repeats all payload/source bindings.
    timestamp = datetime.now(timezone.utc).isoformat()
    wrapper = {
        'status': 'PASS', 'study_id': 'QPATH-ROUTING-v0.4', 'stage': 'B',
        'endpoint_count': 135, 'created_utc': timestamp,
        'reviewer': 'root', 'endpoint_lock_sha256': s.digest(evaluator.LOCK),
        'independent_audit_path': audit_path.relative_to(ROOT).as_posix(),
        'independent_audit_sha256': s.digest(audit_path),
        'scope': 'Root accepts the independent full 27000-round validation audit; no model test outcomes used.'
    }
    s.write_json(evaluator.REVIEW, wrapper, True)
    bindings = {
        'registration_sha256': evaluator.REGISTRATION,
        'endpoint_lock_sha256': evaluator.LOCK,
        'independent_endpoint_review_sha256': evaluator.REVIEW,
        'stage_freeze_sha256': Q / 'STAGE_B_FREEZE.json',
        'data_seal_sha256': Q / 'data/DATA_SEAL.json',
        'analysis_protocol_sha256': evaluator.PROTOCOL,
        'readiness_protocol_sha256': evaluator.READINESS_PROTOCOL,
        'independent_replay_ready_sha256': ready_path,
    }
    release = {
        'status': 'released_by_root', 'study_id': 'QPATH-ROUTING-v0.4',
        'scope': 'all_135_registered_confirmation_endpoints_once',
        'release_id': str(uuid.uuid4()), 'created_utc': timestamp,
        'authorization': 'User authorized the complete internal local study; all full confirmation endpoints independently audited before this root release.',
        'release_tool_sha256': s.digest(Path(__file__)),
        **{key: s.digest(path) for key, path in bindings.items()},
    }
    s.write_json(evaluator.RELEASE, release, True)
    try:
        _, _, _, watched = evaluator.verify_guard()
        result = {'status': 'PASS', 'created_utc': datetime.now(timezone.utc).isoformat(),
                  'release_sha256': s.digest(evaluator.RELEASE), 'bound_inputs': len(watched),
                  'scope': 'Metadata-only official release guard passed. No test array loaded and no predictions evaluated.'}
        s.write_json(Q / 'ROOT_RELEASE_GUARD.json', result, True)
        print(json.dumps(result, indent=2))
    except Exception:
        s.write_json(Q / 'ROOT_RELEASE_GUARD_FAILURE.json', {'status': 'FAIL', 'created_utc': datetime.now(timezone.utc).isoformat(), 'error': traceback.format_exc()}, True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--independent-audit', type=Path, required=True)
    args = parser.parse_args()
    run(args.independent_audit)
