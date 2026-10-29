"""Root-released, one-time independent test replay. No official model imports.

Refuses partial evaluation, changed evidence, stale source hashes and reused
outputs. Root release must explicitly bind the final ANALYSIS_READY manifest.
"""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import traceback
import numpy as np
from matrix_reference import METHODS, PARAMETERS, predict, routes_from_policy
from statistics_reference import METRICS, metrics, summarize, seed_statistics
from readout_reference import READOUT_METHODS, TRAINING_SEEDS, SHOT_BUDGETS, MEASUREMENT_SEEDS, exact_counts, nested_summary
from comparison import require, close, compare_metrics, compare_statistics
from threshold_reference import threshold_diagnostics, RECOVERY_SHA
from threshold_comparison import compare_endpoint as compare_threshold_endpoint, compare_summary as compare_threshold_summary

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANALYSIS_SHA = '7401f1ab9f805eed0a1cd97a86e1aab9be3c27746e0a529a991efdaf9e1766f5'
TOLERANCE_SHA = '92b0a015769e1069727e0d4630a94280032b52513f57a17e80bdfdcc3fd02476'
ENDPOINT_FILES = {'result_sha256': 'result.json', 'config_sha256': 'config.json',
    'selected_checkpoint_sha256': 'selected_checkpoint.npz', 'last_checkpoint_sha256': 'last_checkpoint.npz',
    'ledger_sha256': 'ledger.jsonl', 'record_orders_sha256': 'record_orders.npz',
    'endpoint_commit_sha256': 'endpoint_commit.json', 'status_sha256': 'status.json',
    'validation_predictions_sha256': 'validation_predictions.csv'}


def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read_bound(path):
    before = sha(path); value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    require(sha(path) == before, 'JSON changed during read: ' + str(path))
    return value, before
def read(path): return read_bound(path)[0]
def read_verified(path, expected):
    value, digest = read_bound(path); require(digest == expected, 'Bound JSON changed: ' + str(path))
    return value
def timestamp(value): return datetime.fromisoformat(value.replace('Z', '+00:00'))


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as f: json.dump(value, f, indent=2, allow_nan=False); f.write('\n')


def inside(root, relative):
    part = Path(relative)
    require(not part.is_absolute() and '..' not in part.parts, 'Unsafe relative path')
    result = (root / part).resolve()
    require(result.is_relative_to(root.resolve()), 'Path escapes evidence root')
    return result


def verify_gate(release_path, root=ROOT):
    """Only metadata, source and checkpoint hashes. Never load test/NPZ/outcomes."""
    q = root / 'quantum'; here = root / 'analysis/independent_replay'
    require(release_path.resolve() == (q / 'EVALUATION_RELEASE.json').resolve(), 'Use the canonical root-issued release')
    release, release_hash = read_bound(release_path)
    require(release.get('status') == 'released_by_root' and release.get('study_id') == 'QPATH-QMECH-v0.3', 'Root release missing')
    require(release.get('scope') == 'all_65_registered_confirmation_endpoints_once', 'Wrong release scope')
    require(bool(release.get('release_id')), 'Missing release identity')
    require(np.__version__ == '2.5.4', 'Exact NumPy2.5.4 replay environment required')
    paths = {'registration_sha256': q / 'EVALUATION_REGISTRATION.json',
             'endpoint_lock_sha256': q / 'CONFIRMATION_ENDPOINT_LOCK.json',
             'independent_endpoint_review_sha256': q / 'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json',
             'stage_freeze_sha256': q / 'STAGE_B_FREEZE.json',
             'data_seal_sha256': q / 'data/DATA_SEAL.json',
             'analysis_protocol_sha256': root / 'governance/ANALYSIS_PROTOCOL.json',
             'numerical_recovery_protocol_sha256': root / 'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json',
             'independent_replay_ready_sha256': here / 'ANALYSIS_READY.json'}
    watched = {release_path.resolve(): release_hash}
    for key, path in paths.items():
        require(release.get(key) == sha(path), 'Release binding mismatch: ' + key)
        watched[path.resolve()] = sha(path)
    require(sha(paths['analysis_protocol_sha256']) == ANALYSIS_SHA, 'Registered analysis changed')
    require(sha(paths['numerical_recovery_protocol_sha256']) == RECOVERY_SHA, 'Numerical recovery protocol changed')
    require(sha(here / 'TOLERANCE_PROTOCOL.json') == TOLERANCE_SHA, 'Registered tolerances changed')
    watched[(here / 'TOLERANCE_PROTOCOL.json').resolve()] = TOLERANCE_SHA
    ready = read_verified(paths['independent_replay_ready_sha256'], release['independent_replay_ready_sha256'])
    require(ready.get('status') == 'READY_FOR_ROOT_RELEASE' and ready.get('test_outcomes_accessed') is False, 'Replay readiness missing')
    require(ready['analysis_protocol_sha256'] == ANALYSIS_SHA and ready['tolerance_protocol_sha256'] == TOLERANCE_SHA, 'Stale replay protocol')
    require(ready['numerical_recovery_protocol_sha256'] == RECOVERY_SHA, 'Stale recovery readiness')
    require(ready['evaluation_registration_sha256'] == sha(paths['registration_sha256']), 'Stale evaluator adapter')
    require(set(ready['source_hashes']) == {p.name for p in here.glob('*.py')}, 'Independent source inventory changed')
    for name, digest in ready['source_hashes'].items():
        path = inside(here, name); require(sha(path) == digest, 'Independent source changed: ' + name); watched[path] = digest
    for relative, digest in ready['evidence_hashes'].items():
        path = inside(root, relative); require(sha(path) == digest, 'Readiness evidence changed: ' + relative); watched[path] = digest
    registration = read_verified(paths['registration_sha256'], release['registration_sha256'])
    require(registration['status'] == 'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS', 'Evaluator registration status')
    require(registration['numerical_recovery_protocol_sha256'] == RECOVERY_SHA, 'Unamended evaluator registration')
    require(registration['analysis_protocol_sha256'] == ANALYSIS_SHA and registration['method_order'] == list(METHODS)
            and registration['training_seeds'] == list(TRAINING_SEEDS), 'Registered evaluator identities differ')
    require(registration['readout']['methods'] == list(READOUT_METHODS) and registration['readout']['budgets'] == list(SHOT_BUDGETS)
            and registration['readout']['shot_seeds'] == list(MEASUREMENT_SEEDS), 'Registered readout scope differs')
    freeze = read_verified(paths['stage_freeze_sha256'], release['stage_freeze_sha256'])
    lock = read_verified(paths['endpoint_lock_sha256'], release['endpoint_lock_sha256'])
    review = read_verified(paths['independent_endpoint_review_sha256'], release['independent_endpoint_review_sha256'])
    require(registration['data_seal_sha256'] == sha(paths['data_seal_sha256'])
            and registration['training_source_hashes'] == freeze['source_hashes'], 'Evaluator registration training/data mismatch')
    require(freeze['review_status'] == 'approved_by_root' and freeze['stage'] == 'B'
            and freeze['methods'] == list(METHODS) and freeze['training_seeds'] == list(TRAINING_SEEDS), 'B freeze scope mismatch')
    require(freeze['settings']['rounds'] == 200 and freeze['settings']['optimizer_updates'] == 15000, 'B budget mismatch')
    require(freeze['data_seal_sha256'] == sha(paths['data_seal_sha256']), 'B data seal changed')
    for name, digest in freeze['protocol_hashes'].items():
        path = inside(root / 'governance', name); require(sha(path) == digest, 'Frozen protocol changed'); watched[path] = digest
    require(lock['status'] == 'PASS' and lock['stage'] == 'B' and lock['endpoint_count'] == 65 and lock['test_accessed'] is False, 'Endpoint lock incomplete')
    require(lock['stage_freeze_sha256'] == sha(paths['stage_freeze_sha256']) and lock['data_seal_sha256'] == sha(paths['data_seal_sha256']), 'Stale endpoint lock')
    require(lock['training_source_hashes'] == freeze['source_hashes'], 'Training source identity mismatch')
    for mapping in (registration['source_hashes'], freeze['source_hashes'], lock['audit_sources']):
        for name, digest in mapping.items():
            path = inside(q, name); require(sha(path) == digest, 'Frozen source changed: ' + name); watched[path] = digest
    require(review['status'] == 'PASS' and review['stage'] == 'B' and review['endpoint_count'] == 65
            and review['endpoint_lock_sha256'] == sha(paths['endpoint_lock_sha256']), 'Independent B review is stale/incomplete')
    path = inside(root, review['independent_audit_path'])
    require(sha(path) == review['independent_audit_sha256'], 'Independent audit changed')
    watched[path] = review['independent_audit_sha256']
    audit = read_verified(path, review['independent_audit_sha256'])
    for label, document in [('endpoint lock', lock), ('independent review', review), ('independent audit', audit)]:
        require(document['numerical_recovery_protocol_sha256'] == RECOVERY_SHA, 'Stale recovery binding: ' + label)
    require(audit['status'] == 'PASS' and audit['stage'] == 'B' and audit['endpoint_count'] == 65
            and audit['endpoint_lock_sha256'] == sha(paths['endpoint_lock_sha256']), 'Underlying independent audit failed/stale')
    auditor_name = 'analysis/classical_review/audit_endpoints_v03.py'
    require(audit['auditor_sha256'] == registration['external_source_hashes'][auditor_name], 'Independent auditor source mismatch')
    for name, digest in registration['external_source_hashes'].items():
        path = inside(root, name); require(sha(path) == digest, 'External registered source changed'); watched[path] = digest
    require(timestamp(lock['created_utc']) <= timestamp(release['created_utc'])
            and timestamp(audit['created_utc']) <= timestamp(release['created_utc']), 'Release predates endpoint reviews')
    stage_path = q / 'stage_B/stage_status.json'; stage, stage_hash = read_bound(stage_path); watched[stage_path] = stage_hash
    require(stage['status'] == 'completed' and sorted((r['seed'], r['exit_code']) for r in stage['exits']) == [(s, 0) for s in TRAINING_SEEDS], 'B processes incomplete')
    require(timestamp(stage['finished_utc']) <= timestamp(release['created_utc']), 'Release predates B completion')
    exit_path = q / 'stage_B/process_exits.json'
    exits, exit_hash = read_bound(exit_path)
    require(exits == stage['exits'], 'Process exit records mismatch'); watched[exit_path] = exit_hash
    expected = {(s, m) for s in TRAINING_SEEDS for m in METHODS}
    require(len(lock['endpoints']) == 65 and {(r['seed'], r['method']) for r in lock['endpoints']} == expected, 'Exact65 endpoint identity set required')
    for row in lock['endpoints']:
        method, seed = row['method'], row['seed']; folder = q / 'stage_B' / f'seed_{seed}' / method
        require(row['path'] == folder.relative_to(q).as_posix() and not (folder / 'failure.json').exists(), 'Unexpected endpoint/failure')
        for key, name in ENDPOINT_FILES.items():
            path = folder / name; require(sha(path) == row[key], 'Endpoint payload changed'); watched[path] = row[key]
        result = read_verified(folder / 'result.json', row['result_sha256'])
        config = read_verified(folder / 'config.json', row['config_sha256'])
        status = read_verified(folder / 'status.json', row['status_sha256'])
        require((result['method'], result['seed'], result['stage'], result['engineering']) == (method, seed, 'B', False), 'Endpoint identity mismatch')
        require(result['status'] == 'completed' and result['completed_rounds'] == 200 and result['optimizer_global_updates'] == 15000
                and result['test_accessed'] is False, 'Endpoint incomplete')
        require(status == {'status': 'completed', 'round': 200, 'seed': seed, 'method': method}, 'Endpoint status mismatch')
        require(config['source_hashes'] == freeze['source_hashes'] and config['data_seal_sha256'] == sha(paths['data_seal_sha256']), 'Endpoint source/data identity mismatch')
        require(timestamp(result['finished_utc']) <= timestamp(release['created_utc']), 'Release predates endpoint completion')
    official = q / 'confirmation_evaluation'; commit_path = official / 'EVALUATION_COMMIT.json'
    require(not (official / 'FAILURE.json').exists(), 'Official evaluation failure is unresolved')
    commit, commit_hash = read_bound(commit_path); watched[commit_path] = commit_hash
    require(commit['status'] == 'completed' and commit['study_id'] == 'QPATH-QMECH-v0.3'
            and commit['report_count'] == 65 and commit['prediction_file_count'] == 65
            and commit['count_array_count'] == 150 and commit['payload_count'] == 135, 'Official evaluation incomplete')
    for key in ('release_id', 'registration_sha256', 'endpoint_lock_sha256'):
        expected_value = release['release_id'] if key == 'release_id' else release[key]
        require(commit[key] == expected_value, 'Evaluation commit binding mismatch: ' + key)
    require(commit['release_sha256'] == sha(release_path), 'Evaluation used another release')
    expected_files = {'ACCESS_EVENT.json', 'summary.json', 'bootstrap_arrays.npz', 'readout/counts.npz', 'readout/summary.json'}
    expected_files.update(f'seed_{s}/{m}/{n}' for s in TRAINING_SEEDS for m in METHODS for n in ('report.json', 'predictions.csv'))
    require(registration['expected_output_paths'] == sorted(expected_files), 'Registered output schema mismatch')
    require(set(commit['files']) == expected_files, 'Exact official output inventory required')
    found = {p.relative_to(official).as_posix() for p in official.rglob('*') if p.is_file()}
    require(found == expected_files | {'EVALUATION_COMMIT.json'}, 'Unexpected or missing official payload')
    canonical = set()
    for name, entry in commit['files'].items():
        path = inside(official, name); identity = str(path).casefold()
        require(identity not in canonical, 'Duplicate normalized output path'); canonical.add(identity)
        require(sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes'], 'Official payload changed: ' + name)
        watched[path] = entry['sha256']
    event = read_verified(official / 'ACCESS_EVENT.json', commit['files']['ACCESS_EVENT.json']['sha256'])
    require(event['event'] == 'ROOT_RELEASE_VERIFIED_BEFORE_CONFIRMATION_TEST_LOAD'
            and event['release_sha256'] == sha(release_path) and event['release_id'] == release['release_id'], 'Official access event mismatch')
    require(timestamp(release['created_utc']) <= timestamp(event['created_utc']) <= timestamp(commit['completed_utc']), 'Official access chronology invalid')
    for path, digest in watched.items(): require(sha(path) == digest, 'Evidence changed during gate: ' + str(path))
    return {'root': root, 'quantum': q, 'official': official, 'release': release, 'lock': lock,
            'commit': commit, 'watched': watched, 'protocol': read_verified(paths['analysis_protocol_sha256'], ANALYSIS_SHA),
            'seal': read_verified(paths['data_seal_sha256'], release['data_seal_sha256']), 'official_access': event}


def load_test(gate):
    path = gate['quantum'] / 'data/confirmation_SEALED_test.npz'; entry = gate['seal']['files'][path.name]
    require(sha(path) == entry['sha256'], 'Confirmation test hash mismatch')
    with np.load(path, allow_pickle=False) as f: pop = {k: f[k] for k in f.files}
    require(set(pop) == set(entry['arrays']), 'Test array inventory mismatch')
    for name, value in pop.items():
        a = np.ascontiguousarray(value)
        digest = hashlib.sha256(str(a.dtype).encode() + str(a.shape).encode() + a.tobytes()).hexdigest()
        require(digest == entry['arrays'][name], 'Test array changed: ' + name)
    require(len(pop['y']) == 1600 and len(set(pop['ids'].tolist())) == 1600 and pop['x'].shape == (1600, 2), 'Test shape/IDs invalid')
    require(np.array_equal(pop['y'], (np.sum(pop['x'] ** 2, axis=1) < 2 / np.pi).astype(np.int64)), 'Declared circle-label mechanism mismatch')
    require(np.array_equal(pop['depth'], 5 - (pop['classes'] + 1) // 2), 'Declared random-class depth mapping mismatch')
    policy_path = gate['quantum'] / 'data/confirmation_router.json'
    require(sha(policy_path) == gate['seal']['routers']['confirmation']['sha256'] == entry['router_policy_sha256'], 'Router policy hash mismatch')
    calculated = routes_from_policy(pop['x'], read(policy_path))
    for key in calculated: require(np.array_equal(calculated[key], pop[key]), 'Independent route disagreement: ' + key)
    gate['watched'][path] = entry['sha256']; gate['watched'][policy_path] = sha(policy_path)
    return pop


def saved_predictions(path, population):
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames == ['record_id', 'original_depth', 'hash_route', 'kmeans_route', 'label', 'probability', 'prediction'], 'CSV header mismatch')
        rows = list(reader)
    require(len(rows) == 1600, 'Incomplete prediction file')
    for column, key in [('record_id', 'ids'), ('original_depth', 'depth'), ('hash_route', 'hash_route'), ('kmeans_route', 'kmeans_route'), ('label', 'y')]:
        require(np.array_equal(np.asarray([int(r[column]) for r in rows]), population[key]), 'CSV identity mismatch: ' + key)
    p = np.asarray([float(r['probability']) for r in rows])
    require(np.isfinite(p).all() and np.all((p >= 0) & (p <= 1)), 'Invalid saved probabilities')
    require(np.array_equal([int(r['prediction']) for r in rows], p >= .5), 'CSV threshold decisions mismatch')
    return p


def verify_readout(gate, pop, probabilities):
    official = read(gate['official'] / 'readout/summary.json')
    require(official['status'] == 'completed' and official['numpy'] == '2.5.4' and official['count_array_count'] == 150, 'Readout summary incomplete')
    require(official['method_order'] == list(READOUT_METHODS) and official['budgets'] == list(SHOT_BUDGETS)
            and official['shot_seeds'] == list(MEASUREMENT_SEEDS) and official['training_seeds'] == list(TRAINING_SEEDS)
            and official['records_per_array'] == 1600, 'Readout metadata identities mismatch')
    with np.load(gate['official'] / 'readout/counts.npz', allow_pickle=False) as f: stored = {k: f[k] for k in f.files}
    require(sha(gate['official'] / 'readout/counts.npz') == official['counts_sha256'], 'Readout count file identity mismatch')
    rows = {(r['method'], r['training_seed'], r['budget']): r for r in official['rows']}
    require(len(rows) == len(official['rows']) == 30, 'Readout checkpoint/budget row count mismatch')
    count_map, expected_names, ideal = {}, set(), {}
    for method in READOUT_METHODS:
        for seed in TRAINING_SEEDS:
            p = probabilities[METHODS.index(method), TRAINING_SEEDS.index(seed)]; ideal[(method, seed)] = p
            for budget in SHOT_BUDGETS:
                row = rows[method, seed, budget]
                compare_metrics(metrics(pop['y'], p), row['ideal_metrics'], 1600, 'Readout ideal metric')
                measurements = {r['shot_seed']: r for r in row['measurements']}
                require(len(measurements) == len(row['measurements']) == 5 and set(measurements) == set(MEASUREMENT_SEEDS), 'Readout measurement identities mismatch')
                recalculated = []; flips = []
                for measurement_seed in MEASUREMENT_SEEDS:
                    name = f'{method}_seed{seed}_shots{budget}_measurement{measurement_seed}'; expected_names.add(name)
                    observed = stored[name]
                    expected = exact_counts(p, seed, measurement_seed, budget, method)
                    require(np.issubdtype(observed.dtype, np.integer) and np.array_equal(observed, expected), 'Exact binomial replay mismatch: ' + name)
                    count_map[(method, seed, budget, measurement_seed)] = observed
                    measurement = measurements[measurement_seed]
                    require(measurement['array_key'] == name and measurement['seed_sequence'] == [seed, measurement_seed, budget, METHODS.index(method)], 'Readout RNG identity mismatch')
                    measured = metrics(pop['y'], observed / budget); recalculated.append([measured[k] for k in METRICS])
                    compare_metrics(measured, measurement['metrics'], 1600, name)
                    flip = float(np.mean((observed / budget >= .5) != (p >= .5))); flips.append(flip)
                    close(flip, measurement['prediction_flip_fraction'], name + '/flip', 0.)
                    close(np.mean(np.abs(observed / budget - p)), measurement['probability_mean_absolute_error'], name + '/mae')
                for j, key in enumerate(METRICS): close(np.asarray(recalculated)[:, j].mean(), row['nested_mean_metrics'][key], 'Nested readout metric')
                close(np.mean(flips), row['nested_mean_flip_fraction'], 'Nested flip mean')
    require(set(stored) == expected_names, 'Readout count array set mismatch')
    summary = nested_summary(pop['y'], ideal, count_map)
    require(summary['represented_bernoulli_trials'] == official['represented_bernoulli_trials'], 'Represented Bernoulli count mismatch')
    for method in READOUT_METHODS:
        for budget in SHOT_BUDGETS:
            for key in METRICS:
                ours = summary['aggregates'][method][str(budget)][key]['checkpoint_measurement_mean']
                peer = official['aggregates'][method][str(budget)][key]
                require(peer['n_training_seeds'] == 5 and peer['degrees_of_freedom'] == 4, 'Readout pseudo-replication')
                require(peer['confidence'] == .95, 'Readout confidence mismatch')
                for field in ('values', 'mean', 'sample_sd'): close(ours[field], peer[field], 'Readout seed aggregate/' + field)
                close(ours['t95'], peer['t_interval'], 'Readout t95 interval')
            flip_stats = seed_statistics([rows[method, seed, budget]['nested_mean_flip_fraction'] for seed in TRAINING_SEEDS])
            peer = official['aggregates'][method][str(budget)]['prediction_flip_fraction']
            require(peer['n_training_seeds'] == 5 and peer['degrees_of_freedom'] == 4 and peer['confidence'] == .95, 'Flip replication/interval mismatch')
            for field in ('values', 'mean', 'sample_sd'): close(flip_stats[field], peer[field], 'Readout flip aggregate/' + field)
            close(flip_stats['t95'], peer['t_interval'], 'Readout flip t95')
    summary['exact_integer_count_replay'] = 'PASS: all150 arrays/240000 record-count values'
    summary['draw_probability_source'] = 'Hash-bound official float probabilities, separately validated by independent matrix/MLP replay.'
    return summary


def run(release_path, output, root=ROOT):
    require(output.resolve().is_relative_to((root / 'analysis/independent_replay').resolve()), 'Replay output must remain inside owned analysis folder')
    require(not output.exists(), 'Output exists; preserve attempts and do not overwrite')
    gate = verify_gate(release_path, root)
    output.mkdir(parents=True, exist_ok=False); started = time.perf_counter()
    try:
        write_new(output / 'ACCESS_EVENT.json', {'event': 'ROOT_RELEASE_AND_OFFICIAL_COMPLETION_VERIFIED_BEFORE_TEST_READ',
            'created_utc': now(), 'release_sha256': sha(release_path), 'release_id': gate['release']['release_id'],
            'official_commit_sha256': sha(gate['official'] / 'EVALUATION_COMMIT.json'),
            'official_access_utc': gate['official_access']['created_utc'], 'official_completed_utc': gate['commit']['completed_utc']})
        pop = load_test(gate)
        p_saved = np.empty((len(METHODS), 5, 1600)); p_replayed = np.empty_like(p_saved)
        endpoint_reports, result_data = [], {}
        locked = {(r['seed'], r['method']): r for r in gate['lock']['endpoints']}
        with (output / 'endpoint_progress.jsonl').open('x', encoding='utf-8') as progress:
            for mi, method in enumerate(METHODS):
                for si, seed in enumerate(TRAINING_SEEDS):
                    row = locked[seed, method]; folder = gate['quantum'] / row['path']; official = gate['official'] / f'seed_{seed}' / method
                    report = read(official / 'report.json')
                    require(report['status'] == 'completed' and (report['method'], report['seed'], report['stage']) == (method, seed, 'B'), 'Official report identity mismatch')
                    for field, expected in [('selected_checkpoint_sha256', row['selected_checkpoint_sha256']), ('training_result_sha256', row['result_sha256']),
                                            ('config_sha256', row['config_sha256']), ('test_payload_sha256', gate['seal']['files']['confirmation_SEALED_test.npz']['sha256']),
                                            ('predictions_sha256', sha(official / 'predictions.csv'))]:
                        require(report[field] == expected, 'Official report provenance mismatch: ' + field)
                    require(report['selected_round'] == row['selected_round'], 'Selected round mismatch')
                    with np.load(folder / 'selected_checkpoint.npz', allow_pickle=False) as checkpoint:
                        require(checkpoint['parameters'].shape == (PARAMETERS[method],), 'Checkpoint parameter shape mismatch')
                        require(int(checkpoint['completed_rounds']) == row['selected_round'] and int(checkpoint['adam_t']) == 75 * row['selected_round'], 'Selected checkpoint round mismatch')
                        parameters = checkpoint['parameters'].copy()
                    saved = saved_predictions(official / 'predictions.csv', pop)
                    replayed = predict(method, parameters, pop['x'], pop['depth'], pop)
                    error = close(replayed, saved, f'{seed}/{method}/probabilities', 2e-12)
                    diagnostic = threshold_diagnostics(pop['y'], saved, replayed, pop['ids'], pop['depth'],
                        {kind: pop[kind + '_route'] for kind in ('hash', 'kmeans')})
                    numerical_comparison = compare_threshold_endpoint(diagnostic, report['numerical_verification'], pop, saved)
                    disagreements = diagnostic['counts']['classification_disagreements']
                    saved_metrics, replay_metrics = metrics(pop['y'], saved), metrics(pop['y'], replayed)
                    compare_metrics(saved_metrics, report['metrics'], 1600, f'{seed}/{method}/saved_metrics')
                    close(replay_metrics['bce'], report['metrics']['bce'], f'{seed}/{method}/independent_bce', 1e-9)
                    for d in range(1, 5):
                        ix = pop['depth'] == d
                        compare_metrics(metrics(pop['y'][ix], saved[ix]), report['by_original_depth'][str(d)], int(ix.sum()), f'{seed}/{method}/depth{d}')
                        close(metrics(pop['y'][ix], replayed[ix])['bce'], report['by_original_depth'][str(d)]['bce'], f'{seed}/{method}/depth{d}/independent_bce', 1e-9)
                    for kind in ('hash', 'kmeans'):
                        expected_routes = {str(k) for k in range(5) if np.any(pop[kind + '_route'] == k)}
                        require(set(report['by_route'][kind]) == expected_routes, 'Route metric group inventory mismatch')
                        for k in expected_routes:
                            ix = pop[kind + '_route'] == int(k)
                            compare_metrics(metrics(pop['y'][ix], saved[ix]), report['by_route'][kind][k], int(ix.sum()), f'{seed}/{method}/{kind}{k}')
                            close(metrics(pop['y'][ix], replayed[ix])['bce'], report['by_route'][kind][k]['bce'], f'{seed}/{method}/{kind}{k}/independent_bce', 1e-9)
                    p_saved[mi, si], p_replayed[mi, si] = saved, replayed
                    item = {'method': method, 'seed': seed, 'records': 1600, 'selected_round': row['selected_round'],
                            'checkpoint_sha256': row['selected_checkpoint_sha256'], 'maximum_probability_error': error,
                            'bce_absolute_error': abs(saved_metrics['bce'] - replay_metrics['bce']),
                            'classification_disagreements': disagreements, 'metrics': saved_metrics, 'reference_metrics': replay_metrics,
                            'exact_classifier_agreement': diagnostic['counts']['exact_classifier_agreement'],
                            'numerical_verification': diagnostic, 'official_numerical_verification': report['numerical_verification'],
                            'numerical_comparison': numerical_comparison, 'status': 'PASS'}
                    endpoint_reports.append(item); progress.write(json.dumps(item, allow_nan=False) + '\n'); progress.flush()
                    result_data[(method, seed)] = read(folder / 'result.json')
                    print(f'REPLAY PASS {seed} {method} max_error={error:.3g}', flush=True)
        np.savez_compressed(output / 'independent_probabilities.npz', probabilities=p_replayed, record_ids=pop['ids'],
                            method_order=np.asarray(METHODS), training_seeds=np.asarray(TRAINING_SEEDS))
        # Statistics use identical saved float inputs after independently validating every value.
        # This makes the statistic-implementation check distinct from floating-point gate replay.
        summary, boot = summarize(pop['y'], p_saved, list(METHODS), gate['protocol'])
        official_summary = read(gate['official'] / 'summary.json')
        require(official_summary['status'] == 'completed' and official_summary['report_count'] == 65, 'Official summary incomplete')
        require(official_summary['numerical_recovery_protocol_sha256'] == RECOVERY_SHA, 'Official summary recovery binding mismatch')
        numerical_summary_comparison = compare_threshold_summary(official_summary['numerical_verification'], endpoint_reports, METHODS, TRAINING_SEEDS)
        require(official_summary['release_id'] == gate['release']['release_id']
                and official_summary['analysis_protocol_sha256'] == ANALYSIS_SHA
                and official_summary['endpoint_lock_sha256'] == gate['release']['endpoint_lock_sha256']
                and official_summary['registration_sha256'] == gate['release']['registration_sha256']
                and official_summary['test_payload_sha256'] == gate['seal']['files']['confirmation_SEALED_test.npz']['sha256'], 'Official summary provenance mismatch')
        require(official_summary['bootstrap_sha256'] == sha(gate['official'] / 'bootstrap_arrays.npz')
                and official_summary['readout_summary_sha256'] == sha(gate['official'] / 'readout/summary.json'), 'Official summary payload binding mismatch')
        with np.load(gate['official'] / 'bootstrap_arrays.npz', allow_pickle=False) as f:
            require(f['method_order'].tolist() == list(METHODS) and f['metric_order'].tolist() == list(METRICS), 'Official bootstrap axis identities mismatch')
            statistic_comparison = compare_statistics(summary, official_summary, boot, f['metric_means'])
        np.savez_compressed(output / 'independent_bootstrap.npz', metric_means=boot, method_order=np.asarray(METHODS), metric_order=np.asarray(METRICS))
        readout = verify_readout(gate, pop, p_saved); write_new(output / 'readout_summary.json', readout)
        resources = {'scope': 'Recorded concurrent local CPU measurements; preparation repeatedly charged per arm, not summed project wall time. Independent replay is additional verification work.',
                     'extra_cached_verification_scope': 'One additional1024-record cached forward per endpoint, outside the one warmup plus three timed forwards; see root RESOURCE_ACCOUNTING_NOTE_01.json.', 'methods': {}}
        for method in METHODS:
            rows = [result_data[method, s] for s in TRAINING_SEEDS]
            resources['methods'][method] = {
                'parameter_count': PARAMETERS[method], 'selected_rounds': [r['selected_round'] for r in rows],
                'charged_training_seconds': seed_statistics([r['charged_training_seconds'] for r in rows]),
                'training_seconds': seed_statistics([r['training_seconds'] for r in rows]),
                'uncached_validation_inference_seconds_per_record': seed_statistics([r['inference']['mean_seconds_per_record'] for r in rows]),
                'recorded_work_by_seed': [r['work'] for r in rows],
                'training_gradient_diagnostic_work_by_seed': [{d: v['work'] for d, v in r['diagnostics']['train_groups'].items()} for r in rows],
                'extra_cached_verification_work_by_seed': [{k: v // 4 for k, v in r['inference']['work_separate_from_training'].items()} for r in rows]}
        write_new(output / 'resource_summary.json', resources)
        for path, digest in gate['watched'].items(): require(sha(path) == digest, 'Bound evidence changed during replay: ' + str(path))
        summary.update({'status': 'PASS', 'created_utc': now(), 'test_outcomes_accessed': True,
            'release_id': gate['release']['release_id'], 'release_sha256': sha(release_path),
            'analysis_protocol_sha256': ANALYSIS_SHA, 'tolerance_protocol_sha256': TOLERANCE_SHA,
            'numerical_recovery_protocol_sha256': RECOVERY_SHA,
            'official_commit_sha256': sha(gate['official'] / 'EVALUATION_COMMIT.json'), 'endpoint_count': 65,
            'prediction_records_replayed': 104000, 'maximum_probability_error': max(r['maximum_probability_error'] for r in endpoint_reports),
            'maximum_bce_absolute_error': max(r['bce_absolute_error'] for r in endpoint_reports),
            'classification_disagreements': sum(r['classification_disagreements'] for r in endpoint_reports),
            'exact_classifier_agreement': all(r['exact_classifier_agreement'] for r in endpoint_reports),
            'outside_band_disagreements': sum(r['numerical_verification']['counts']['outside_band_disagreements'] for r in endpoint_reports),
            'canonical_near_band_count': sum(r['numerical_verification']['counts']['canonical_near_band_count'] for r in endpoint_reports),
            'reference_near_band_count': sum(r['numerical_verification']['counts']['reference_near_band_count'] for r in endpoint_reports),
            'union_near_band_count': sum(r['numerical_verification']['counts']['union_near_band_count'] for r in endpoint_reports),
            'verification_scope': 'PASS under recovery01 means canonical saved-metric reconstruction and independent probability/BCE agreement, with every hard-threshold discrepancy inside the fixed32eps band for BOTH probabilities. It does not assert exact classifier agreement. All canonical ambiguity sensitivity scenarios are retained per endpoint; these are not statistical intervals.',
            'statistics_comparison': statistic_comparison, 'endpoints': endpoint_reports,
            'numerical_summary_comparison': numerical_summary_comparison,
            'route_counts': {k: np.bincount(pop[k + '_route'], minlength=5).tolist() for k in ('hash', 'kmeans')},
            'environment': {'numpy': np.__version__, 'python': sys.version, 'executable': sys.executable, 'platform': platform.platform()},
            'elapsed_seconds': time.perf_counter() - started})
        write_new(output / 'summary.json', summary)
        inventory = {p.relative_to(output).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in output.rglob('*') if p.is_file()}
        write_new(output / 'REPLAY_COMMIT.json', {'status': 'PASS', 'completed_utc': now(), 'files': inventory,
            'release_sha256': sha(release_path), 'official_commit_sha256': sha(gate['official'] / 'EVALUATION_COMMIT.json')})
        print(json.dumps({'status': 'PASS', 'endpoint_count': 65, 'maximum_probability_error': summary['maximum_probability_error'],
                          'classification_disagreements': summary['classification_disagreements'], 'output': str(output)}), flush=True)
    except BaseException as error:
        write_new(output / 'FAILURE.json', {'status': 'FAIL', 'created_utc': now(), 'error': str(error), 'traceback': traceback.format_exc(),
            'policy': 'Preserve this attempt. No tuning, reselection, overwriting or automatic retry.'})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); run(args.release, args.output)
