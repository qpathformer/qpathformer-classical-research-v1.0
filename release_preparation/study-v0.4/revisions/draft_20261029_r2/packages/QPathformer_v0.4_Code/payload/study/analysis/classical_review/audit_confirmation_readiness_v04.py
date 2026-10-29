"""Independent audit of the complete, root-released local confirmation capsule.

The public CLI reads no test arrays or official test metrics. It requires the
completed readiness commit, full Stage B audits and the root release first.
Density channels are reconstructed with NumPy; actual Aer measurement draws
are checked as recorded, never rerandomized or treated as hardware results.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path, PureWindowsPath
import sys
import traceback

import numpy as np
import reference_v04 as ref
import audit_engineering_readiness_v04 as engineering

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'analysis/independent_replay'))
from evidence_io import contained, digest, inventory, map_original_absolute, read_bound, recheck, require

REGISTRY = '64d4954472dd3575248f0e98aa2012f74ec64ee678473af4aa92877a4ef8942a'
POPULATIONS = ('confirmation_circle_1', 'confirmation_circle_2', 'confirmation_ellipse')
SEEDS = (801, 802, 803, 804, 805)
METHODS = ('q2_global', 'q2_hash', 'q2_kmeans')
ALL_METHODS = tuple(f'{family}_{route}' for family in ('q2', 'mlp', 'trig') for route in ('global', 'hash', 'kmeans'))


def now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(text):
    result = datetime.fromisoformat(text)
    require(result.tzinfo is not None, 'Timezone-aware evidence required')
    return result.astimezone(timezone.utc)


def bound_file(path, expected, watched):
    path = Path(path).resolve()
    require(str(path) not in watched or watched[str(path)] == expected,
            'Previously bound input identity differs: ' + str(path))
    require(digest(path) == expected, 'Bound input changed: ' + str(path))
    watched[str(path)] = expected


def gate(root, *, expected_registry=REGISTRY):
    """Metadata and hashes only. No np.load, test arrays or test reports."""
    require(np.__version__ == '2.5.4', 'Registered NumPy2.5.4 required for exact binomial replay')
    root = Path(root).resolve(); q = root / 'quantum'
    folder = q / 'local_readiness_confirmation'
    watched = {}
    release_path = q / 'EVALUATION_RELEASE.json'
    release = read_bound(release_path, watched)
    require(release.get('status') == 'released_by_root'
            and release.get('study_id') == 'QPATH-ROUTING-v0.4'
            and release.get('scope') == 'all_135_registered_confirmation_endpoints_once'
            and isinstance(release.get('release_id'), str) and release['release_id'], 'Root release required')
    paths = {
        'registration_sha256': q / 'EVALUATION_REGISTRATION.json',
        'endpoint_lock_sha256': q / 'CONFIRMATION_ENDPOINT_LOCK.json',
        'independent_endpoint_review_sha256': q / 'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json',
        'stage_freeze_sha256': q / 'STAGE_B_FREEZE.json',
        'data_seal_sha256': q / 'data/DATA_SEAL.json',
        'analysis_protocol_sha256': root / 'governance/ANALYSIS_PROTOCOL.json',
        'readiness_protocol_sha256': root / 'governance/LOCAL_READINESS_PROTOCOL.json',
        'independent_replay_ready_sha256': root / 'analysis/independent_replay/ANALYSIS_READY.json',
    }
    objects = {}
    for key, path in paths.items():
        objects[key] = read_bound(path, watched)
        require(release.get(key) == watched[str(path.resolve())], 'Root release binding differs: ' + key)
    reg = objects['registration_sha256']; lock = objects['endpoint_lock_sha256']
    review = objects['independent_endpoint_review_sha256']; ready = objects['independent_replay_ready_sha256']
    freeze = objects['stage_freeze_sha256']; protocol = objects['readiness_protocol_sha256']
    seal = objects['data_seal_sha256']; rh = watched[str(paths['registration_sha256'].resolve())]
    require(rh == expected_registry and reg['status'] == 'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS', 'Registered evaluator changed')
    require(reg['methods'] == list(ALL_METHODS) and reg['training_seeds'] == list(SEEDS)
            and reg['populations'] == list(POPULATIONS), 'Registered scope differs')
    original = reg['original_working_root']
    for key in ('data_seal_sha256', 'analysis_protocol_sha256', 'readiness_protocol_sha256'):
        require(reg[key] == release[key], 'Registered data/protocol differs')
    require(ready['status'] == 'READY_BEFORE_CONFIRMATION_TEST_ACCESS'
            and ready['registration_sha256'] == rh
            and ready['analysis_protocol_sha256'] == release['analysis_protocol_sha256'], 'Independent replay readiness differs')
    for hashes in (reg['source_hashes'], ready['source_hashes'], ready['evidence_hashes']):
        require(bool(hashes), 'Empty registered hash inventory')
        for name, expected in hashes.items():
            bound_file(contained(root, name), expected, watched)
    require(freeze['review_status'] == 'approved_by_root'
            and freeze['methods'] == list(ALL_METHODS) and freeze['populations'] == list(POPULATIONS)
            and freeze['training_seeds'] == list(SEEDS), 'Root full Stage B freeze missing')
    require(lock['status'] == 'PASS' and lock['stage'] == 'B' and lock['endpoint_count'] == 135
            and lock['engineering'] is False, 'Completed author audit required')
    for key in ('data_seal_sha256', 'analysis_protocol_sha256', 'stage_freeze_sha256'):
        require(lock[key] == release[key], 'Author lock binding differs')
    require(lock['source_hashes'] == freeze['source_hashes'] == reg['training_source_hashes'], 'Training sources differ')
    for name, expected in lock['source_hashes'].items():
        bound_file(contained(q, name), expected, watched)
    for name, expected in lock['audit_source_hashes'].items():
        bound_file(map_original_absolute(name, original, root), expected, watched)
    require(review['status'] == 'PASS' and review['stage'] == 'B' and review['endpoint_count'] == 135
            and review['endpoint_lock_sha256'] == release['endpoint_lock_sha256'], 'Independent review required')
    audit_path = contained(root, review['independent_audit_path'])
    audit = read_bound(audit_path, watched)
    require(watched[str(audit_path.resolve())] == review['independent_audit_sha256'], 'Independent audit changed')
    require(audit['status'] == 'PASS' and audit['stage'] == 'B' and audit['endpoint_count'] == 135
            and audit['engineering'] is False and audit['validation_rounds_replayed'] == 27000
            and audit['model_test_outcomes_accessed'] is False, 'Full independent audit required')
    for key in ('endpoint_lock_sha256', 'analysis_protocol_sha256', 'data_seal_sha256'):
        require(audit[key] == release[key], 'Independent audit binding differs')
    auditor = contained(root, reg['independent_auditor_path'])
    require(digest(auditor) == audit['auditor_sha256'] == reg['source_hashes'][reg['independent_auditor_path']], 'Independent auditor differs')
    for name, expected in audit['independent_source_sha256'].items():
        require(Path(name).name == name, 'Unsafe independent source name')
        p = auditor.parent / name
        require(expected == reg['source_hashes'][p.relative_to(root).as_posix()], 'Independent source registry differs')
        bound_file(p, expected, watched)
    identities = {(pop, seed, method) for pop in POPULATIONS for seed in SEEDS for method in ALL_METHODS}
    require(len(lock['endpoints']) == len(audit['endpoints']) == 135
            and {(r['population'], r['seed'], r['method']) for r in lock['endpoints']} == identities
            and {(r['population'], r['seed'], r['method']) for r in audit['endpoints']} == identities, 'Exact135 endpoint identities required')
    checked = {(r['population'], r['seed'], r['method']): r for r in audit['endpoints']}
    endpoints = {}
    for row in lock['endpoints']:
        identity = row['population'], row['seed'], row['method']
        pop, seed, method = identity; ar = checked[identity]
        endpoint = q / 'stage_B' / pop / f'seed_{seed}' / method
        require(map_original_absolute(row['path'], original, root).resolve() == endpoint.resolve(), 'Endpoint original identity differs')
        require(ar['endpoint_commit_sha256'] == row['endpoint_commit_sha256']
                and ar['rounds_verified'] == 200 and ar['validation_predictions_replayed'] == 320000
                and ar['selected_round'] == row['selected_round']
                and ar['selected_checkpoint_sha256'] == row['files']['selected_checkpoint.npz']['sha256'], 'Full endpoint audit differs')
        endpoint_commit = read_bound(endpoint / 'endpoint_commit.json', watched)
        require(watched[str((endpoint / 'endpoint_commit.json').resolve())] == row['endpoint_commit_sha256']
                and endpoint_commit['status'] == 'completed' and endpoint_commit['test_accessed'] is False
                and endpoint_commit['files'] == row['files'] and not (endpoint / 'failure.json').exists(), 'Endpoint commit differs')
        inventory(endpoint, row['files'], exclude=('endpoint_commit.json',))
        for name, metadata in row['files'].items():
            bound_file(contained(endpoint, name), metadata['sha256'], watched)
        endpoints[identity] = row
    stage = read_bound(q / 'stage_B/stage_status.json', watched)
    require(stage['status'] == 'completed' and stage['stage'] == 'B'
            and stage['committed_endpoints'] == stage['expected_endpoints'] == 135
            and sorted((r['seed'], r['exit_code']) for r in stage['exits']) == [(s, 0) for s in SEEDS], 'All five workers must have closed')
    require(timestamp(release['created_utc']) >= max(timestamp(lock['created_utc']), timestamp(audit['created_utc'])), 'Release predates audits')
    require(protocol['populations'] == list(POPULATIONS) and protocol['training_seeds'] == list(SEEDS)
            and protocol['methods'] == list(METHODS), 'Readiness protocol scope differs')
    commit_path = folder / 'READINESS_COMMIT.json'
    commit = read_bound(commit_path, watched)
    require(commit['status'] == 'completed' and commit['engineering'] is False
            and commit['test_accessed'] is False and not (folder / 'FAILURE.json').exists(), 'Actual complete confirmation capsule required')
    inventory(folder, commit['files'], exclude=('READINESS_COMMIT.json',))
    for name, metadata in commit['files'].items():
        bound_file(contained(folder, name), metadata['sha256'], watched)
    report = read_bound(folder / 'report.json', watched)
    require(report['status'] == 'PASS' and report['engineering'] is False and report['test_accessed'] is False
            and report['populations'] == list(POPULATIONS) and report['training_seeds'] == list(SEEDS)
            and report['methods'] == list(METHODS) and report['protocol_sha256'] == release['readiness_protocol_sha256'], 'Readiness report identity differs')
    require(timestamp(release['created_utc']) <= timestamp(report['created_utc']) <= timestamp(commit['created_utc']), 'Readiness chronology differs')
    # The producer records every pre-capsule bound input. Remap provenance, never
    # dereference original-tree paths or a sealed test/outcome payload.
    recorded_watched = {}
    for name, expected in report['watched_input_hashes'].items():
        path = map_original_absolute(name, original, root) if PureWindowsPath(name).is_absolute() else contained(q, name.replace('\\', '/'))
        relative = path.relative_to(root).as_posix()
        require('_SEALED_test' not in relative and not relative.startswith('quantum/confirmation_evaluation/'), 'Readiness must not watch test outcomes')
        bound_file(path, expected, watched); recorded_watched[str(path.resolve())] = expected
    # All root-approved evidence and selected endpoint inventories must have
    # been watched by the original capsule, not merely by this later audit.
    own_prefix = str(folder.resolve()) + '\\'
    for name, expected in watched.items():
        if not name.startswith(own_prefix):
            require(recorded_watched.get(name) == expected, 'Capsule omitted bound pre-execution evidence: ' + name)
    recheck(watched)
    return {'root': root, 'q': q, 'folder': folder, 'release': release, 'report': report,
            'commit': commit, 'seal': seal, 'protocol': protocol, 'endpoints': endpoints,
            'watched': watched, 'registry_sha256': rh, 'original_root': original}


def load_arrays(path):
    require('_SEALED_test' not in str(path), 'Test arrays are outside this audit')
    with np.load(path, allow_pickle=False) as z:
        return {key: z[key] for key in z.files}


def close(actual, expected, label, tol=2e-12):
    require(math.isfinite(float(actual)) and abs(float(actual) - float(expected)) <= tol, label)


def verify_numerics(context):
    report, protocol, q = context['report'], context['protocol'], context['q']
    rows = report['circuits']; require(len(rows) == 1440, 'Exact1440 fixture rows required')
    expected_groups = [(p, s, m) for p in POPULATIONS for s in SEEDS for m in METHODS]
    expected_rows = [(p, s, m, i) for p, s, m in expected_groups for i in range(32)]
    require([(r['population'], r['training_seed'], r['method'], r['fixture_index']) for r in rows] == expected_rows, 'Fixture group/order differs')
    require(len({r['key'] for r in rows}) == 1440, 'Duplicate fixture keys')
    validations, checkpoints, row_by_key = {}, {}, {}
    max_pre = max_observed = max_ideal = 0.; channel_error = engineering.channel_fixtures()
    maximum_unitary_source = maximum_unitary_compiled = maximum_compiled_aer = maximum_ideal_density = 0.
    for population in POPULATIONS:
        path = q / 'data' / f'{population}_validation.npz'
        bound_file(path, context['seal']['files'][path.name]['sha256'], context['watched'])
        val = load_arrays(path); indices = np.argsort(val['ids'], kind='stable')[:32]
        require(len(val['ids']) == 1600 and len(indices) == 32, 'Validation fixture scope differs')
        validations[population] = {key: a[indices] for key, a in val.items() if key in ('ids', 'x', 'hash_route', 'kmeans_route')}
        require(report['fixture_ids'][population] == val['ids'][indices].tolist(), 'Fixtures are not32 smallest label-independent IDs')
    for row in rows:
        group = row['population'], row['training_seed'], row['method']; pop, seed, method = group
        val = validations[pop]; i = row['fixture_index']
        expected_key = f'{pop}__seed{seed}__{method}__id{int(val["ids"][i])}'
        require(row['key'] == expected_key and row['record_id'] == int(val['ids'][i])
                and np.array_equal(row['x'], val['x'][i])
                and row['hash_route'] == int(val['hash_route'][i])
                and row['kmeans_route'] == int(val['kmeans_route'][i]), 'Fixture coordinates/IDs/routes differ')
        bank = 0 if method == 'q2_global' else int(val[method.split('_')[1] + '_route'][i])
        require(row['bank'] == bank and 0 <= bank < (1 if method == 'q2_global' else 5), 'Selected bank differs')
        if group not in checkpoints:
            endpoint = context['endpoints'][group]
            path = q / 'stage_B' / pop / f'seed_{seed}' / method / 'selected_checkpoint.npz'
            require(digest(path) == row['checkpoint_sha256'] == endpoint['files']['selected_checkpoint.npz']['sha256'], 'Selected checkpoint hash differs')
            checkpoint = load_arrays(path); theta = checkpoint['parameters']
            require(theta.dtype == np.float64 and theta.shape == (ref.PARAMETERS[method],) and np.isfinite(theta).all(), 'Selected parameter schema differs')
            require(int(checkpoint['current_round']) == int(checkpoint['completed_rounds']) == endpoint['selected_round']
                    and int(checkpoint['adam_t']) == 75 * endpoint['selected_round'], 'Selected checkpoint horizon differs')
            checkpoints[group] = theta
        require(row['checkpoint_sha256'] == context['endpoints'][group]['files']['selected_checkpoint.npz']['sha256'], 'Per-row checkpoint differs')
        theta = checkpoints[group][8 * bank:8 * (bank + 1)].reshape(2, 2, 2)
        require(row['logical_operations'] == {'ry': 9, 'rz': 4, 'cx': 2}, 'Logical per-gate noise work differs')
        ideal = ref.scalar_circuit(row['x'], theta)
        for name in ('production_probability', 'reference_probability', 'compiled_probability', 'compiled_aer_probability'):
            close(row[name], ideal, 'Independent ideal probability differs: ' + name)
            max_ideal = max(max_ideal, abs(row[name] - ideal))
        for name in ('source_unitary_error', 'compiled_unitary_error'):
            require(0 <= row[name] <= 2e-12, 'Recorded matrix comparison failed')
        require(set(row['compiled_operations']) <= {'rz', 'sx', 'x', 'cx'}
                and all(type(n) is int and n >= 0 for n in row['compiled_operations'].values()), 'Compiled basis/work differs')
        require(set(row['scenarios']) == {s['name'] for s in protocol['noise_scenarios']}, 'Scenario inventory differs')
        for scenario in protocol['noise_scenarios']:
            p = engineering.density_probability(row['x'], theta, scenario['one_qubit_depolarizing'], scenario['cx_depolarizing'])
            saved = row['scenarios'][scenario['name']]; flip = scenario['symmetric_readout_flip']; observed = flip + (1 - 2 * flip) * p
            close(saved['premeasurement_probability'], p, 'Independent density channel differs')
            close(saved['observed_probability'], observed, 'Independent analytic readout differs')
            close(saved['absolute_distortion_from_ideal'], abs(saved['observed_probability'] - row['reference_probability']), 'Distortion arithmetic differs')
            require(saved['classification_disagreement_from_ideal'] == bool((saved['observed_probability'] >= .5) != (row['reference_probability'] >= .5)), 'Raw class-difference flag differs')
            max_pre = max(max_pre, abs(saved['premeasurement_probability'] - p)); max_observed = max(max_observed, abs(saved['observed_probability'] - observed))
        maximum_unitary_source = max(maximum_unitary_source, row['source_unitary_error'])
        maximum_unitary_compiled = max(maximum_unitary_compiled, row['compiled_unitary_error'])
        maximum_compiled_aer = max(maximum_compiled_aer, abs(row['compiled_aer_probability'] - row['reference_probability']))
        maximum_ideal_density = max(maximum_ideal_density, abs(row['scenarios']['ideal']['observed_probability'] - row['reference_probability']))
        row_by_key[row['key']] = row
    folder = context['folder']; counts = load_arrays(folder / 'finite_shot_counts.npz')
    probabilities = load_arrays(folder / 'finite_shot_probabilities.npz')
    records = read_bound(folder / 'finite_shot_records.json', context['watched'])
    expected_shot_keys = [f'{p}__seed{s}__{m}__{sc["name"]}__shots{shots}__repeat{repeat}'
        for p, s, m in expected_groups for sc in protocol['noise_scenarios']
        for shots in protocol['finite_shot']['shots'] for repeat in range(protocol['finite_shot']['replicates'])]
    require(len(records) == len(counts) == len(probabilities) == 1350
            and [r['key'] for r in records] == expected_shot_keys
            and set(counts) == set(probabilities) == set(expected_shot_keys), 'Exact1350 binomial arrays/order required')
    represented = 0
    for row in records:
        group = [r for r in rows if (r['population'], r['training_seed'], r['method']) == (row['population'], row['training_seed'], row['method'])]
        sequence = [490101, POPULATIONS.index(row['population']), row['training_seed'], METHODS.index(row['method']),
                    [s['name'] for s in protocol['noise_scenarios']].index(row['scenario']), row['shots'], row['repeat_index']]
        require(row['seed_sequence'] == sequence and row['record_ids'] == [r['record_id'] for r in group], 'Binomial RNG/record identity differs')
        p = np.array([r['scenarios'][row['scenario']]['observed_probability'] for r in group])
        expected = np.random.Generator(np.random.PCG64(np.random.SeedSequence(sequence))).binomial(row['shots'], p)
        n = counts[row['key']]; sample = probabilities[row['key']]
        require(n.dtype == np.int64 and n.shape == (32,) and sample.dtype == np.float64
                and np.array_equal(n, expected) and np.array_equal(sample, expected / row['shots']), 'Exact binomial replay differs')
        close(row['mean_absolute_probability_error'], np.mean(abs(sample - p)), 'Finite-shot error summary differs')
        close(row['classification_disagreement_from_density'], np.mean((sample >= .5) != (p >= .5)), 'Finite-shot class summary differs')
        represented += row['shots'] * 32
    measured = read_bound(folder / 'measured_aer_counts.json', context['watched'])
    expected_measured = [(r['key'], scenario['name']) for scenario in protocol['noise_scenarios']
                         if scenario['name'] in protocol['aer_measured_smoke']['scenarios'] for r in rows if r['fixture_index'] < 8]
    require(len(measured) == 720 and [(r['key'], r['scenario']) for r in measured] == expected_measured, 'Exact720 measured experiments required')
    for row in measured:
        n0, n1 = row['counts']['0'], row['counts']['1']
        require(set(row['counts']) == {'0', '1'} and type(n0) is int and type(n1) is int
                and min(n0, n1) >= 0 and n0 + n1 == row['shots'] == 1024, 'Measured counts differ')
        require(row['seed_simulator'] == protocol['aer_measured_smoke']['seed_simulator'], 'Measured Aer seed differs')
        p = row_by_key[row['key']]['scenarios'][row['scenario']]['observed_probability']
        close(row['density_expected_probability'], p, 'Measured expected probability differs')
        close(row['observed_probability'], n1 / 1024, 'Measured frequency differs')
        variance = 1024 * p * (1 - p)
        require(row['degenerate_variance'] == (variance == 0), 'Variance flag differs')
        if variance > 0:
            close(row['standardized_count_residual'], (n1 - 1024 * p) / math.sqrt(variance), 'Measured residual differs')
        else:
            require(row['standardized_count_residual'] is None, 'Degenerate residual must be absent')
    for population in POPULATIONS:
        for method in METHODS:
            chosen = [r for r in rows if r['population'] == population and r['method'] == method]
            for scenario in protocol['noise_scenarios']:
                name = scenario['name']; summary = report['summaries'][population][method][name]
                require(summary['checkpoint_fixture_pairs'] == len(chosen) == 160, 'Noise-summary denominator differs')
                values = [r['scenarios'][name]['absolute_distortion_from_ideal'] for r in chosen]
                close(summary['mean_absolute_distortion'], np.mean(values), 'Mean noise distortion differs')
                close(summary['maximum_absolute_distortion'], max(values), 'Maximum noise distortion differs')
                close(summary['classification_disagreement_fraction'], np.mean([r['scenarios'][name]['classification_disagreement_from_ideal'] for r in chosen]), 'Noise class summary differs')
    totals = {'circuit_count': 1440, 'matrix_comparisons': 2880, 'density_scenario_circuit_evaluations': 4320,
              'compiled_ideal_aer_circuit_evaluations': 1440, 'measured_aer_circuit_experiments': 720,
              'actual_simulated_measurement_shots': 737280, 'finite_shot_array_count': 1350, 'represented_binomial_trials': represented}
    for key, value in totals.items(): require(report[key] == value, 'Capsule work total differs: ' + key)
    for key, value in (('maximum_source_unitary_error', maximum_unitary_source), ('maximum_compiled_unitary_error', maximum_unitary_compiled),
                       ('maximum_ideal_density_probability_error', maximum_ideal_density), ('maximum_compiled_aer_probability_error', maximum_compiled_aer)):
        close(report[key], value, 'Maximum summary differs: ' + key)
    expected_files = {'report.json', 'finite_shot_counts.npz', 'finite_shot_probabilities.npz', 'finite_shot_records.json', 'measured_aer_counts.json'}
    expected_files.update(f'circuits/{r["key"]}__{kind}.qasm' for r in rows for kind in ('logical', 'compiled'))
    expected_files.update(f'circuits/{r["key"]}__measured.qasm' for r in rows if r['fixture_index'] < 8)
    require(set(context['commit']['files']) == expected_files, 'Readiness QASM/payload coverage differs')
    require(all(math.isfinite(v) and v >= 0 for v in report['timings_seconds'].values())
            and math.isfinite(report['elapsed_seconds']) and report['elapsed_seconds'] >= 0, 'Nonfinite/negative timing')
    return {'selected_checkpoints_checked': len(checkpoints), **totals,
            'pauli_vs_partial_trace_channel_fixture_maximum_error': channel_error,
            'maximum_independent_ideal_probability_error': max_ideal,
            'maximum_independent_premeasurement_probability_error': max_pre,
            'maximum_independent_observed_probability_error': max_observed,
            'all_exact_binomial_arrays_reproduced': True,
            'measured_count_residuals_checked': len(measured), 'qasm_payload_count': len(expected_files) - 5}


def run(root, output):
    output = Path(output).resolve(); require(not output.exists(), 'Preserve prior audit output')
    context = gate(root)
    for path in (Path(__file__), Path(engineering.__file__), Path(ref.__file__)):
        bound_file(path, digest(path), context['watched'])
    output.mkdir(parents=True, exist_ok=False)
    def write(name, value):
        with (output / name).open('x', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, allow_nan=False); handle.write('\n')
    write('ACCESS_EVENT.json', {'created_utc': now(), 'scope': 'Root-released completed local validation-only readiness capsule audit; no test arrays.',
          'release_id': context['release']['release_id'], 'readiness_commit_sha256': digest(context['folder'] / 'READINESS_COMMIT.json')})
    try:
        checks = verify_numerics(context); recheck(context['watched'])
        result = {'status': 'PASS', 'created_utc': now(), 'study_id': 'QPATH-ROUTING-v0.4', 'engineering': False,
                  'test_arrays_accessed': False, 'model_test_outcomes_accessed': False, 'checks': checks,
                  'release_id': context['release']['release_id'], 'release_sha256': digest(context['q'] / 'EVALUATION_RELEASE.json'),
                  'readiness_commit_sha256': digest(context['folder'] / 'READINESS_COMMIT.json'),
                  'registration_sha256': context['registry_sha256'],
                  'auditor_sources': {str(p.relative_to(ROOT).as_posix()): digest(p) for p in (Path(__file__), Path(engineering.__file__), Path(ref.__file__))},
                  'watched_input_hashes': context['watched'],
                  'scope': 'Independent per-logical-gate density/noise/readout reconstruction and exact binomial replay; recorded actual Aer count arithmetic checked without rerandomization. 45 selected quantum checkpoints, label-independent validation fixtures only.',
                  'limits': 'QASM payload identities and completeness, recorded matrix residuals and independently reconstructed probabilities are checked; this auditor does not independently compile or parse QASM unitaries. No hardware/calibration, test accuracy, seed independence from repeated shots, or stochastic pass/fail inference.'}
        write('summary.json', result)
        recheck(context['watched'])
        write('AUDIT_COMMIT.json', {'status': 'completed', 'created_utc': now(), 'files': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in output.iterdir() if p.is_file()},
              'readiness_commit_sha256': result['readiness_commit_sha256']})
        return result
    except BaseException as error:
        write('FAILURE.json', {'status': 'FAIL', 'created_utc': now(), 'error': str(error), 'traceback': traceback.format_exc(), 'recovery': 'Preserve all outputs; root review before any separate retry.'})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    require(args.output.resolve().parent == HERE, 'Output must be a new child of classical_review')
    result = run(ROOT, args.output)
    print(json.dumps({'status': result['status'], 'output': str(args.output), 'checks': result['checks']}))


if __name__ == '__main__':
    main()
