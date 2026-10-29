"""Fail-closed test release gate. This module never loads an NPZ/model outcome."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

PROTOCOL_PATHS = {
    'study_plan': 'governance/STUDY_PLAN.json',
    'run_matrix': 'governance/RUN_MATRIX.json',
    'analysis_protocol': 'governance/ANALYSIS_PROTOCOL.json',
    'data_seal': 'quantum/data/DATA_SEAL.json',
}
EVALUATOR_FILES = ('metrics_v09.py', 'release_gate_v09.py', 'evaluate_v09.py', 'test_author_v09.py')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def binding(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)


def inside(root, path):
    p = Path(path).resolve()
    require(p.is_relative_to(Path(root).resolve()), 'Binding escapes the current study root')
    return p


def verify_binding(root, item):
    require(isinstance(item, dict) and {'path', 'sha256', 'bytes'} <= set(item), 'Incomplete binding')
    path = inside(root, item['path'])
    require(path.is_file(), f'Bound file is absent: {path}')
    require(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], f'Bound file changed: {path}')
    return path


def evaluator_sources(root):
    return {f'analysis/author/{name}': sha(Path(root)/'analysis/author'/name) for name in EVALUATOR_FILES}


def endpoint_map(receipt, expected):
    require(receipt.get('status') == 'PASS' and receipt.get('stage') == 'B' and
            receipt.get('verified_endpoints') == 636, 'All 636 confirmation endpoints must pass the audit')
    entries = receipt.get('endpoints', [])
    require(len(entries) == 636 and {r['job_id'] for r in entries} == expected, 'Audit identities differ from the complete confirmation matrix')
    return {r['job_id']: r for r in entries}


def same_endpoint(a, b):
    for key in ('job_id', 'arm', 'population', 'seed', 'completed_rounds',
                'optimizer_global_updates', 'selected_round', 'commit', 'selected_checkpoint'):
        require(a.get(key) == b.get(key), f'Author/independent/root endpoint mismatch: {a.get("job_id")} {key}')


def verify_release(root, release_path):
    root = Path(root).resolve(); release_path = inside(root, release_path)
    release_binding = binding(release_path); release = read(release_path)
    require(release.get('schema') == 'qpath-v09-evaluation-release-1' and
            release.get('review_status') == 'approved_by_root' and release.get('stage') == 'B',
            'An explicit root-approved hash-bound evaluation release is required')
    protocols = {}
    require(set(release.get('protocols', {})) == set(PROTOCOL_PATHS), 'Exact evaluator protocol bindings required')
    for name, relpath in PROTOCOL_PATHS.items():
        p = verify_binding(root, release['protocols'][name])
        require(p == (root/relpath).resolve(), 'Wrong registered protocol path')
        protocols[name] = read(p)
    require(release.get('evaluator_sources') == evaluator_sources(root), 'Evaluator source changed since release')
    scientific_sources = release.get('scientific_source_hashes', {})
    require(set(scientific_sources) == {'models.py', 'study.py', 'circuits.py', 'reference_v03.py',
            'prepare_data.py', 'routers.py', 'tests/test_v09_science.py'}, 'Incomplete scientific source freeze')
    for name, expected_hash in scientific_sources.items():
        require(sha(root/'quantum'/name) == expected_hash, 'Scientific source changed')
    jobs = [r for r in protocols['run_matrix']['runs'] if r['stage'] == 'B']
    expected = {r['run_id'] for r in jobs}
    require(len(jobs) == len(expected) == 636, 'The complete 636-run confirmation stage is required')
    require(protocols['analysis_protocol']['confirmation_count'] == 636, 'Analysis count changed')
    author_path = verify_binding(root, release['author_audit'])
    independent_path = verify_binding(root, release['independent_audit'])
    author = read(author_path); independent = read(independent_path)
    require(author.get('schema') == 'qpath-v09-author-stage-audit-1', 'Wrong author audit schema')
    require(independent.get('schema') == 'qpath-v09-independent-endpoint-audit-1', 'Wrong independent audit schema')
    require(independent.get('author_audit') == release['author_audit'], 'Independent audit does not bind this author audit')
    require(author.get('test_model_outcomes_accessed') is False, 'Author audit accessed confirmation outcomes')
    require(independent.get('test_model_outcomes_accessed') is False, 'Independent audit accessed confirmation outcomes')
    require(author.get('manifest') == independent.get('manifest'), 'Audits do not bind the same confirmation manifest')
    manifest = read(verify_binding(root, author['manifest']))
    require(manifest.get('stage') == 'B' and manifest.get('jobs') == jobs, 'Audit manifest differs from the complete registered B recipes')
    am = endpoint_map(author, expected); im = endpoint_map(independent, expected)
    endpoints = release.get('endpoints', [])
    require(len(endpoints) == 636 and {e['job_id'] for e in endpoints} == expected, 'Release must enumerate every exact endpoint')
    rm = {e['job_id']: e for e in endpoints}
    source = release['scientific_source_hashes']
    auth_path = verify_binding(root, author['authorization'])
    require(manifest.get('authorization') == author['authorization'], 'Audit manifest uses a different stage authorization')
    auth = read(auth_path)
    require(auth.get('review_status') == 'approved_by_root' and auth.get('stage') == 'B' and
            auth.get('schema') == 'qpath-v09-stage-authorization-1' and auth.get('scientific_source_hashes') == source,
            'Author audit stage authorization is invalid')
    require(auth.get('run_ids') == [r['run_id'] for r in jobs], 'Stage authorization is not the complete ordered B matrix')
    hashes = dict(data_seal_sha256=release['protocols']['data_seal']['sha256'],
                  matrix_sha256=release['protocols']['run_matrix']['sha256'],
                  protocol_sha256=release['protocols']['study_plan']['sha256'])
    for key, value in hashes.items():
        require(auth.get(key) == value, 'Stage authorization protocol binding changed')
    files_rehashed = 0
    for job in jobs:
        job_id = job['run_id']; entry = am[job_id]
        same_endpoint(entry, im[job_id]); same_endpoint(entry, rm[job_id])
        require(entry['arm'] == job['arm'] and entry['population'] == job['population_id'] and
                entry['seed'] == job['training_seed_id'], 'Endpoint/matrix recipe mismatch')
        require(entry['completed_rounds'] == job['rounds'] == 200 and
                entry['optimizer_global_updates'] == job['updates'] == 15000, 'Incomplete endpoint budget')
        commit_path = verify_binding(root, entry['commit']); commit = read(commit_path)
        require(commit_path.name == 'endpoint_commit.json', 'Unexpected commit file')
        require(Path(entry['endpoint']).resolve() == commit_path.parent, 'Endpoint directory mismatch')
        checkpoint_path = verify_binding(root, entry['selected_checkpoint'])
        require(checkpoint_path == commit_path.parent/'selected_checkpoint.npz', 'Selected checkpoint is not the committed endpoint checkpoint')
        require(commit.get('schema') == 'qpath-v09-endpoint-1' and commit.get('status') == 'completed' and
                commit.get('test_accessed') is False and commit.get('stage') == 'B', 'Invalid confirmation endpoint')
        for key, value in dict(job_id=job_id, arm=job['arm'], population=job['population_id'],
                               seed=job['training_seed_id'], completed_rounds=200, optimizer_global_updates=15000,
                               source_hashes=source, authorization_sha256=sha(auth_path), **hashes).items():
            require(commit.get(key) == value, f'Commit recipe changed: {key}')
        payloads = commit['files']
        require(set(payloads) == {p.name for p in commit_path.parent.iterdir() if p.is_file()}-{'endpoint_commit.json'}, 'Endpoint inventory changed')
        for name, meta in payloads.items():
            require(Path(name).name == name, 'Unsafe endpoint payload name')
            p = commit_path.parent/name
            require(p.stat().st_size == meta['bytes'] and sha(p) == meta['sha256'], f'Endpoint payload changed: {p}')
            files_rehashed += 1
        require(payloads['selected_checkpoint.npz'] == {k: entry['selected_checkpoint'][k] for k in ('sha256', 'bytes')}, 'Checkpoint binding mismatch')
    require(binding(release_path) == release_binding, 'Evaluation release changed during verification')
    return dict(release=release, release_binding=release_binding, jobs=jobs, endpoints=am,
                protocols=protocols, seal=protocols['data_seal'], scientific_source_hashes=source,
                endpoint_payloads_rehashed=files_rehashed)


def verify_completed_evaluation(root, release_path, commit_binding):
    verified = verify_release(root, release_path)
    commit_path = verify_binding(root, commit_binding); commit = read(commit_path)
    require(commit.get('schema') == 'qpath-v09-author-evaluation-commit-1' and commit.get('status') == 'PASS' and
            commit.get('scored_endpoints') == 636 and commit.get('release') == verified['release_binding'],
            'A completed evaluation for the same root release is required')
    require(commit.get('evaluator_sources') == verified['release']['evaluator_sources'], 'Completed evaluator source binding mismatch')
    actual = {str(p.relative_to(commit_path.parent)).replace('\\', '/')
              for p in commit_path.parent.rglob('*') if p.is_file() and p != commit_path}
    require(set(commit['files']) == actual, 'Completed evaluation inventory changed')
    for name, meta in commit['files'].items():
        p = (commit_path.parent/name).resolve()
        require(p.is_relative_to(commit_path.parent), 'Unsafe evaluation payload path')
        require(p.is_file() and p.stat().st_size == meta['bytes'] and sha(p) == meta['sha256'], 'Evaluation payload changed')
    verified['evaluation_commit'] = commit
    verified['evaluation_commit_binding'] = commit_binding
    return verified
