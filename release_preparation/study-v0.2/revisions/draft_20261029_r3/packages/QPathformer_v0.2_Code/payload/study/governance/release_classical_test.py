"""Root-only manual release after reviewing completed text training and both audits.

This helper opens training metadata/checkpoints as bytes only. It does not load
test payloads, initialize CUDA, start evaluation or authorize itself on a timer.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import uuid

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / 'classical'
R = C / 'results/stage_b'
I = ROOT / 'analysis/classical_independent'
EXPECTED = {
    'protocol_stage_b_frozen.json': '8acef77f0f1893fab6c3a8c79aa02f5219e8fe56d9094aae6bddd7d38d621d4c',
    'selection_frozen.json': 'b6d249f72c8fd274966177dc7a038cf2fdc81ae53854d7cef8641ccb8a589c17',
    'data/manifest.json': 'b4cd9800206d6380c1f8ab0c4d7a6927076560b7168df38ecf55cb694a1a014c',
    'readiness/ROOT_STAGE_B_APPROVAL.json': 'b2505eff718bac101415209d58be1cf43bd8c39b1d420d2db7c8f9e58d34d60b',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def utc(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(d.tzinfo is not None, 'Timestamp lacks timezone')
    return d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-reviewed', action='store_true', required=True)
    parser.parse_args()
    output = C / 'evaluation_release.json'
    evaluation = C / 'confirmation_evaluation'
    require(not output.exists() and not evaluation.exists(), 'Preserve existing release/evaluation')
    for name, expected in EXPECTED.items():
        require(sha(C / name) == expected, 'Frozen identity changed: ' + name)
    protocol = read(C / 'protocol_stage_b_frozen.json')
    expected_main = {(seed, method) for seed in range(401, 406) for method in ['shared', 'current_content', 'hash18']}
    expected_all = expected_main | {(seed, 'common_warmup') for seed in range(401, 406)}
    require(protocol['seeds'] == list(range(401, 406)) and protocol['methods'] == ['shared', 'current_content', 'hash18'], 'Registered matrix')
    require(protocol['schedules']['main_updates'] == 10000 and protocol['schedules']['warmup_updates'] == 1000, 'Registered horizons')
    for name, expected in protocol['code_sha256'].items():
        require(sha(C / name) == expected, 'Frozen source changed: ' + name)
    require(sha(ROOT / 'governance/ANALYSIS_PROTOCOL.json') == '9b409934d07e8eb7a6380a02fe93780cab3323401d595c846da1b2ce7ba1e414', 'Analysis protocol')
    require(sha(I / 'audit_stage_b.py') == '0ef24836ff490df2509539ef620d7e25605546bb319b352d6ec64a78a7c3ad08', 'Independent audit source')
    require(sha(I / 'replay_and_analyse.py') == 'dca77d8c05ed1c6ef53adfe7ae88d1be12aca673a08dbc91fc384eb6ed574f6d', 'Independent replay source')
    review_path = I / 'CLASSICAL_STAGE_B_INDEPENDENT_REVIEW.json'
    review_hash = sha(review_path)
    review = read(review_path)
    audit_path = C / 'readiness/stage_b_completion_audit.json'
    audit_hash = sha(audit_path)
    audit = read(audit_path)
    require(review['status'] == audit['status'] == 'PASS', 'Both completion audits must pass')
    require(review['audit_script_sha256'] == sha(I / 'audit_stage_b.py'), 'Audit source binding')
    require(review['stage_b_protocol_sha256'] == audit['protocol_sha256'] == EXPECTED['protocol_stage_b_frozen.json'], 'Audit protocol binding')
    require(review['root_approval_sha256'] == EXPECTED['readiness/ROOT_STAGE_B_APPROVAL.json'], 'Audit root approval')
    require(review['selection_sha256'] == EXPECTED['selection_frozen.json'] and review['selected_candidate'] == 'hash18', 'Audit selection')
    require(review['data_manifest_sha256'] == EXPECTED['data/manifest.json'], 'Audit data identity')
    require(review['registered_analysis_protocol_sha256'] == sha(ROOT / 'governance/ANALYSIS_PROTOCOL.json'), 'Audit analysis binding')
    require(review['independent_replay_script_sha256'] == sha(I / 'replay_and_analyse.py'), 'Audit replay binding')
    require(review['test_payload_read'] is False and review['test_outcomes_accessed'] is False and audit['test_read'] is False, 'Pre-release boundary')
    require(review['completed_main_endpoints'] == 15 and review['completed_warmups'] == 5, 'All phases required')
    require(review['verified_validation_snapshots'] == 1550 and review['verified_validation_prediction_records'] == 17360000, 'Validation audit coverage')
    require(review['registered_main_updates'] == 150000 and review['registered_warmup_updates'] == 5000 and audit['physical_optimizer_updates'] == 155000, 'Full registered budgets')
    require(review['incident_count'] == 0 and audit['incident_paths'] == [], 'Incidents require documented root review before release')
    require(not list(R.rglob('incidents.jsonl')), 'Current incident files require documented root review')
    watched = {C / name: expected for name, expected in EXPECTED.items()}
    watched.update({C / name: expected for name, expected in protocol['code_sha256'].items()})
    watched[review_path] = review_hash
    watched[audit_path] = audit_hash
    for path in [ROOT / 'governance/ANALYSIS_PROTOCOL.json', I / 'audit_stage_b.py', I / 'replay_and_analyse.py', Path(__file__)]:
        watched[path] = sha(path)
    execution = review['execution_completion']
    require(sha(C / 'execution_segments.jsonl') == execution['execution_segments_sha256'], 'Training changed since audit')
    require(sha(R / 'training_completed.json') == execution['training_completed_sha256'], 'Completion marker changed')
    watched[C / 'execution_segments.jsonl'] = execution['execution_segments_sha256']
    watched[R / 'training_completed.json'] = execution['training_completed_sha256']
    spans = execution['completed_stage_b_segments']
    require(len(spans) == 1 and spans[0]['end']['status'] == 'completed', 'Unexpected execution history requires review')
    require(utc(spans[0]['end']['utc']) <= utc(review['created_utc']) <= datetime.now(timezone.utc), 'Audit chronology')
    require(execution['training_completed']['test_accessed'] is False, 'Training accessed test')
    rows = review['per_seed'] + review['common_warmups']
    require(len(rows) == 20 and {(r['seed'], r['method']) for r in rows} == expected_all, 'Independent audit identities')
    require(len(list(R.glob('seed_*/*/status.json'))) == 20, 'Unexpected training identities')
    structural = {(r['seed'], r['method']): r for r in audit['method_endpoints']}
    require(len(audit['method_endpoints']) == 15 and set(structural) == expected_main, 'Structural audit identities')
    endpoints = []
    for row in rows:
        folder = R / f"seed_{row['seed']}" / row['method']
        state = read(folder / 'status.json')
        commit = read(folder / 'checkpoint_commit.json')
        horizon = 1000 if row['method'] == 'common_warmup' else 10000
        require(state['status'] == 'completed' and state['phase_update'] == state['horizon'] == state['latest_eligible_update'] == horizon, 'Incomplete/censored endpoint')
        require(state['protocol_sha256'] == commit['state']['protocol_sha256'] == EXPECTED['protocol_stage_b_frozen.json'], 'Endpoint protocol')
        require(state['latest_eligible_in_common_warmup'] == (row['method'] == 'common_warmup'), 'Endpoint phase')
        require(state['resumed_segments'] == row['resumed_segments'] == 0 and row['incidents'] == [], 'Recovery requires review')
        for name, field in [('status.json', 'status_sha256'), ('checkpoint_commit.json', 'commit_sha256'), ('ledger.jsonl', 'ledger_sha256')]:
            require(sha(folder / name) == row[field], 'Endpoint metadata changed: ' + name)
            watched[folder / name] = row[field]
        checkpoint = (R / state['latest_eligible_checkpoint']).resolve()
        require(checkpoint.is_relative_to(folder.resolve()) and checkpoint == (folder / commit['checkpoint']).resolve(), 'Checkpoint path containment')
        require(commit['state']['phase_update'] == horizon and sha(checkpoint) == commit['sha256'] == row['checkpoint_sha256'], 'Committed checkpoint identity')
        provenance = review['checkpoint_provenance'][f"{row['seed']}/{row['method']}"]
        require((C / provenance['checkpoint']).resolve() == checkpoint and provenance['sha256'] == row['checkpoint_sha256'], 'Checkpoint audit provenance')
        if row['method'] != 'common_warmup':
            entry = structural[(row['seed'], row['method'])]
            require(entry['checkpoint_sha256'] == row['checkpoint_sha256'] and entry['checkpoint_relative_path'] == state['latest_eligible_checkpoint'], 'Audits disagree on endpoint')
            endpoints.append({'seed': row['seed'], 'method': row['method'], 'checkpoint_relative_path': state['latest_eligible_checkpoint'], 'sha256': row['checkpoint_sha256'], 'committed_main_update': 10000})
    require(len(review['validation_prediction_sha256']) == 1550, 'Missing audited predictions')
    for name, expected in review['validation_prediction_sha256'].items():
        path = (R / name).resolve()
        require(path.is_relative_to(R.resolve()) and sha(path) == expected, 'Audited validation predictions changed')
    manifest = read(C / 'data/manifest.json')
    seal = read(C / 'data/TEST_SEAL.json')
    require(sha(C / 'data/TEST_SEAL.json') == manifest['file_sha256']['TEST_SEAL.json'], 'Frozen test seal changed')
    watched[C / 'data/TEST_SEAL.json'] = manifest['file_sha256']['TEST_SEAL.json']
    require(seal['status'] == 'SEALED_FOR_STAGE_B_CONFIRMATION' and set(seal['file_sha256']) == {'test.jsonl', 'test_encoded.npz'}, 'Frozen seal status/payload keys')
    require(seal['test_rows'] == 14000 and seal['selected_record_ids_sha256'], 'Test seal metadata')
    for name, expected in seal['file_sha256'].items():
        require(manifest['file_sha256']['sealed/' + name] == expected, 'Data manifest/test seal mismatch')
    for path, expected in watched.items():
        require(sha(path) == expected, 'Release input changed during review sweep: ' + str(path))
    require(not list(R.rglob('incidents.jsonl')), 'New incident file appeared during review sweep')
    release = {
        'authorized': True, 'release_type': 'independent_evaluation_after_all_training',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'release_id': 'qpath-v02-classical-' + str(uuid.uuid4()),
        'stage_b_protocol_sha256': EXPECTED['protocol_stage_b_frozen.json'],
        'selection_sha256': EXPECTED['selection_frozen.json'], 'data_manifest_sha256': EXPECTED['data/manifest.json'],
        'test_seal_sha256': sha(C / 'data/TEST_SEAL.json'), 'expected_test_rows': 14000,
        'output_directorynew': str(evaluation), 'endpoints': sorted(endpoints, key=lambda r: (r['seed'], protocol['methods'].index(r['method']))),
        'independent_stage_b_review_sha256': sha(review_path), 'structural_completion_audit_sha256': sha(audit_path),
        'root_release_script_sha256': sha(Path(__file__)), 'test_outcomes_accessed_before_release': False,
        'scope': 'One separate local evaluation of all15 fixed full-budget endpoints, then independent replay and registered analysis. No retraining or test selection.'
    }
    require(not evaluation.exists(), 'An evaluation directory appeared before release')
    with output.open('x', encoding='utf-8') as f:
        f.write(json.dumps(release, indent=2) + '\n')
    print(json.dumps({'status': 'RELEASED', 'path': str(output), 'release_id': release['release_id'], 'endpoints': len(endpoints)}, indent=2))


if __name__ == '__main__':
    main()
