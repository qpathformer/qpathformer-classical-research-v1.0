"""Root-only metadata release after manual inspection of both full B audits.

This helper never loads test arrays or predicts. It records a canonical adapter
to the actual independent audit and binds the pre-reviewed replay tools. The
separate evaluator remains responsible for its own guards and access event.
"""
from pathlib import Path
import argparse
from datetime import datetime
import json
import sys
import uuid
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / 'quantum'
sys.path.insert(0, str(Q))
import qstudy as s
import evaluate_confirmation as evaluator
WATCHED = {}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def bound_file(base, relative, expected):
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()), 'Unsafe bound path')
    require(s.digest(path) == expected, f'Changed bound file: {relative}')
    WATCHED[path] = expected


def read_bound(path):
    before = s.digest(path)
    value = s.read_json(path)
    require(s.digest(path) == before, f'Metadata changed while reading: {path.name}')
    WATCHED[path] = before
    return value


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--independent-audit', required=True, type=Path)
    a = p.parse_args()
    require(np.__version__ == '2.5.4', 'Registered NumPy 2.5.4 runtime required before recording a release')
    audit_path = a.independent_audit.resolve()
    require(audit_path.is_relative_to(ROOT), 'Audit must be in this study')
    lock_path = Q / 'CONFIRMATION_ENDPOINT_LOCK.json'
    review_path = Q / 'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json'
    release_path = Q / 'EVALUATION_RELEASE.json'
    require(not review_path.exists() and not release_path.exists(), 'Release metadata already exists; preserve and inspect it')
    require(not (Q / 'confirmation_evaluation').exists(), 'Evaluation output already exists')
    lock, audit = read_bound(lock_path), read_bound(audit_path)
    for value in (lock, audit):
        require(value.get('status') == 'PASS' and value.get('stage') == 'B' and value.get('endpoint_count') == 65,
                'Both complete B audits must pass')
    require(lock.get('test_accessed') is False, 'Author lock must confirm no test access')
    require(audit.get('test_arrays_or_outcomes_read') is False and audit.get('engineering_only') is False,
            'Independent audit must cover actual endpoints without test access')
    lock_hash = WATCHED[lock_path]
    require(audit['endpoint_lock_sha256'] == lock_hash, 'Independent audit must bind actual author lock')
    stage = read_bound(Q / 'stage_B/stage_status.json')
    require(stage['status'] == 'completed' and len(stage['exits']) == 5
            and {r['seed'] for r in stage['exits']} == set(s.SEEDS['B'])
            and all(r['exit_code'] == 0 for r in stage['exits']), 'B workers must all be closed successfully')
    exits = read_bound(Q / 'stage_B/process_exits.json')
    require(exits == stage['exits'], 'Separate process exit record differs')
    require(datetime.fromisoformat(audit['created_utc']) >= datetime.fromisoformat(lock['created_utc']), 'Audit chronology differs')
    require(datetime.fromisoformat(lock['created_utc']) >= datetime.fromisoformat(stage['finished_utc']), 'Lock predates completed workers')
    reg_path = Q / 'EVALUATION_REGISTRATION.json'
    reg = read_bound(reg_path)
    require(WATCHED[reg_path] == '9a1286d0353ace64cbc0e8f958dea251322273e0c6a6baaab8a3710267bd961e', 'Evaluation registration changed')
    recovery_path = ROOT / 'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json'
    recovery = read_bound(recovery_path)
    recovery_hash = WATCHED[recovery_path]
    require(recovery_hash == '049f4a627fda5fa08c739cc53375aa104e28d223bb78d525841d0f01d7931e0e', 'Recovery protocol changed')
    for value in (lock, audit, reg):
        require(value['numerical_recovery_protocol_sha256'] == recovery_hash, 'Numerical recovery binding differs')
    freeze_path = Q / 'STAGE_B_FREEZE.json'
    seal_path = Q / 'data/DATA_SEAL.json'
    protocol_path = ROOT / 'governance/ANALYSIS_PROTOCOL.json'
    freeze, seal, protocol = read_bound(freeze_path), read_bound(seal_path), read_bound(protocol_path)
    for relative, expected in freeze['protocol_hashes'].items():
        bound_file(ROOT / 'governance', relative, expected)
    require(lock['stage_freeze_sha256'] == WATCHED[freeze_path], 'Author lock freeze link changed')
    require(audit['stage_freeze_sha256'] == WATCHED[freeze_path], 'Independent audit freeze differs')
    require(lock['data_seal_sha256'] == reg['data_seal_sha256'] == WATCHED[seal_path], 'Lock/registration data seal differs')
    require(audit['data_seal_sha256'] == WATCHED[seal_path], 'Independent audit data seal differs')
    require(reg['analysis_protocol_sha256'] == evaluator.PROTOCOL_SHA == WATCHED[protocol_path], 'Registered analysis protocol differs')
    require(reg['training_source_hashes'] == s.source_hashes() == lock['training_source_hashes'], 'Training sources changed')
    require(audit['source_sha256'] == reg['training_source_hashes'], 'Independent audit training source identities differ')
    for relative, expected in reg['source_hashes'].items():
        bound_file(Q, relative, expected)
    for relative, expected in reg['external_source_hashes'].items():
        bound_file(ROOT, relative, expected)
    require(audit['auditor_sha256'] == reg['external_source_hashes']['analysis/classical_review/audit_endpoints_v03.py'], 'Auditor source differs')
    ready_path = ROOT / 'analysis/independent_replay/ANALYSIS_READY.json'
    ready = read_bound(ready_path)
    require(WATCHED[ready_path] == 'db599c82b0a37a553cdde04ef20776b615fb1ca2c30c89e0b7534e82d33b6c3d', 'Reviewed replay READY changed')
    require(ready['numerical_recovery_protocol_sha256'] == recovery_hash, 'Replay numerical recovery binding differs')
    require(ready['status'] == 'READY_FOR_ROOT_RELEASE' and ready['test_outcomes_accessed'] is False, 'Replay not ready')
    require(ready['evaluation_registration_sha256'] == WATCHED[reg_path], 'Replay/evaluator registration mismatch')
    require(ready['analysis_protocol_sha256'] == WATCHED[protocol_path], 'Replay analysis protocol differs')
    require({p.name for p in ready_path.parent.glob('*.py')} == set(ready['source_hashes']), 'Replay Python inventory differs')
    for relative, expected in ready['source_hashes'].items():
        bound_file(ready_path.parent, relative, expected)
    for relative, expected in ready['evidence_hashes'].items():
        bound_file(ROOT, relative, expected)
    bound_file(ready_path.parent, 'TOLERANCE_PROTOCOL.json', ready['tolerance_protocol_sha256'])
    expected = {(seed, method) for seed in s.SEEDS['B'] for method in s.METHODS}
    require(len(lock['endpoints']) == 65 and {(r['seed'], r['method']) for r in lock['endpoints']} == expected, 'Wrong endpoint identities')
    for row in lock['endpoints']:
        s.verify_freeze('B', row['seed'], row['method'])
        folder = Q / 'stage_B' / f"seed_{row['seed']}" / row['method']
        require(row['path'] == folder.relative_to(Q).as_posix(), 'Wrong endpoint path')
        require(not (folder / 'failure.json').exists(), 'Endpoint failure exists')
        for key, filename in evaluator.ENDPOINT_FILES.items():
            bound_file(folder, filename, row[key])
    for path, expected in WATCHED.items():
        require(s.digest(path) == expected, f'Bound metadata or payload changed before release: {path.name}')
    review = {'status': 'PASS', 'stage': 'B', 'endpoint_count': 65,
              'created_utc': s.now(), 'endpoint_lock_sha256': lock_hash,
              'independent_audit_path': audit_path.relative_to(ROOT).as_posix(),
              'independent_audit_sha256': WATCHED[audit_path],
              'numerical_recovery_protocol_sha256': recovery_hash,
              'note': 'Root adapter to the independently executed full endpoint audit under the pre-B numerical verification amendment; no test outcomes used. PASS does not assert exact classifier agreement within the registered ambiguity band.'}
    write_new(review_path, review)
    release = {'status': 'released_by_root', 'study_id': 'QPATH-QMECH-v0.3',
               'scope': 'all_65_registered_confirmation_endpoints_once',
               'release_id': str(uuid.uuid4()), 'created_utc': s.now(),
               'registration_sha256': WATCHED[reg_path], 'endpoint_lock_sha256': lock_hash,
               'independent_endpoint_review_sha256': s.digest(review_path),
               'stage_freeze_sha256': WATCHED[freeze_path],
               'data_seal_sha256': WATCHED[seal_path],
               'analysis_protocol_sha256': WATCHED[protocol_path],
               'numerical_recovery_protocol_sha256': recovery_hash,
               'independent_replay_ready_sha256': WATCHED[ready_path],
               'decision': 'All registered confirmation endpoints completed and independently checked. Release once for registered scoring and independent verification, with no subsequent tuning or reselection.'}
    write_new(release_path, release)
    evaluator.verify_guard()  # Metadata and byte hashes only; no array loads.
    print(json.dumps({'status': 'ROOT_RELEASE_RECORDED_AND_METADATA_GUARD_PASS',
                      'review_sha256': s.digest(review_path), 'release_sha256': s.digest(release_path),
                      'test_payload_loaded': False}, indent=2))


if __name__ == '__main__':
    main()
