"""Official author scoring after an explicit all-636-endpoint root release.

No CLI option bypasses the release barrier. Qualification imports pure numerical
functions only and uses constructed inputs, never the official sealed outcomes.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import traceback

THREAD_KEYS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
               'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')
for key in THREAD_KEYS:
    os.environ[key] = '1'
sys.dont_write_bytecode = True
import numpy as np
from scipy.special import expit, logsumexp
from metrics_v09 import metrics, losses, analyze, distribution
from release_gate_v09 import (read, sha, binding, require, inside, evaluator_sources,
                              verify_release, PROTOCOL_PATHS)


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, content):
    encoded = json.dumps(content, indent=2, allow_nan=False)+'\n'
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(encoded); stream.flush(); os.fsync(stream.fileno())


def load_split(root, verified, population, split, routers):
    # Only callers with the completed gate object reach this function.
    require(verified['release']['review_status'] == 'approved_by_root' and len(verified['endpoints']) == 636,
            'The complete release barrier must precede data loading')
    name = f'{population}_{"SEALED_test" if split == "test" else split}.npz'
    path = root/'quantum/data'/name; seal = verified['seal']
    require(sha(path) == seal['files'][name]['sha256'], 'Input payload changed')
    policy_path = root/'quantum/data'/f'{population}_router.json'
    require(sha(policy_path) == seal['routers'][population]['sha256'], 'Frozen router changed')
    policy = read(policy_path)
    with np.load(path, allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
    require({'x', 'y', 'ids', 'kmeans_route', 'margin_bin'} <= set(data), 'Missing population arrays')
    require(len(data['y']) == seal['datasets'][population]['counts'][split], 'Split count changed')
    require(np.array_equal(routers.route(data['x'], policy, 'kmeans'), data['kmeans_route']), 'Geometric route replay changed')
    require(np.array_equal(routers.margin_bins(data['x'], policy), data['margin_bin']), 'Margin-bin replay changed')
    if 'raw_x' in data:
        for dimensions, field in ((2, 'x'), (4, 'x4')):
            require(np.array_equal(routers.preprocess(data['raw_x'], policy, dimensions), data[field]),
                    'Train-fitted raw Banknote preprocessing replay changed')
    return data, policy


def diagnostic_slices(data, p, z, policy):
    return dict(
        classes=[dict(label=label, metrics=metrics(data['y'][data['y'] == label], p[data['y'] == label], z[data['y'] == label]))
                 for label in (0, 1)],
        fixed_geometric_banks=[dict(bank=b, metrics=metrics(data['y'][data['kmeans_route'] == b],
                                      p[data['kmeans_route'] == b], z[data['kmeans_route'] == b])) for b in range(5)],
        fixed_geometry_margin_bins=[dict(bin=b, metrics=metrics(data['y'][data['margin_bin'] == b],
                                         p[data['margin_bin'] == b], z[data['margin_bin'] == b]))
                                    for b in range(policy['margin_bins']['bins'])],
        margin_definition=policy['margin_bins'],
        interpretation='Slices use common training-fitted geometry for every arm; class/slice metrics are descriptive.')


def bank_diagnostics(model, x, y):
    n = len(x)
    if model.routed:
        logq, q, nearest = model.gate(x)
        if model.routing == 'H':
            q = np.eye(5)[nearest]
        expert_z = np.column_stack([model._expert(x, model.parameters[b*model.bank_width:(b+1)*model.bank_width])[0]
                                    for b in range(5)])
    else:
        q = np.ones((n, 1)); expert_z = model.predict_with_logits(x)[1][:, None]
        nearest = np.zeros(n, dtype=int)
    entropy = -np.sum(np.where(q > 0, q*np.log(np.maximum(q, np.finfo(float).tiny)), 0.), axis=1)
    native = np.maximum(expert_z, 0)-y[:, None]*expert_z+np.log1p(np.exp(-np.abs(expert_z)))
    common = -y[:, None]*np.log(np.clip(expit(expert_z), 1e-7, 1-1e-7))-(1-y[:, None])*np.log1p(-np.clip(expit(expert_z), 1e-7, 1-1e-7))
    conditional = []
    for label in (0, 1):
        chosen = y == label
        for b in range(q.shape[1]):
            mass = float(q[chosen, b].sum())
            conditional.append(dict(label=label, bank=b, record_count=int(chosen.sum()), weight_mass=mass,
                                    native_expert_bce=float(np.sum(q[chosen, b]*native[chosen, b])/mass) if mass else None,
                                    common_expert_bce=float(np.sum(q[chosen, b]*common[chosen, b])/mass) if mass else None))
    output = dict(bank_count=q.shape[1], mean_weights=q.mean(0).tolist(),
                  argmax_occupancy=np.bincount(q.argmax(1), minlength=q.shape[1]).tolist(),
                  mean_entropy=float(entropy.mean()), mean_effective_experts=float(np.exp(entropy).mean()),
                  class_conditional_weight_and_expert_loss=conditional,
                  interpretation='Selected-state descriptive weights and expert losses. These are not historical training exposure or mixture-loss decomposition.')
    if model.routing == 'L':
        zz = expert_z[np.arange(n), q.argmax(1)]
        output['postfit_argmax_gate'] = dict(metrics=metrics(y, expit(zz), zz),
                                            interpretation='Diagnostic replacement of the selected soft gate by its argmax; no retraining or reselection.')
    return output, q, expert_z


def actual_training_exposure(model, train, endpoint):
    """Replay only 12 gate coefficients; no expert training or gradient recomputation."""
    endpoint = Path(endpoint); y = train['y']; x = train['x']; banks = model.banks
    visits = np.load(endpoint/'training_record_exposure.npy', allow_pickle=False)
    require(int(visits.sum()) == 960000, 'Training exposure does not cover the full budget')
    if model.routing != 'L':
        if model.routed:
            _, q, nearest = model.gate(x)
            if model.routing == 'H':
                q = np.eye(banks)[nearest]
        else:
            q = np.ones((len(y), 1))
        exposure = np.array([(q*(visits*(y == label))[:, None]).sum(0) for label in (0, 1)])
        return dict(class_bank_weighted_visits=exposure.tolist(), total_visits=int(visits.sum()),
                    scope='Exact saved sampler counts with the fixed training gate; uniform sampling with replacement.',
                    replayed_gate_updates=0)
    order = np.load(endpoint/'record_orders.npy', mmap_mode='r', allow_pickle=False)
    gradients = np.load(endpoint/'minibatch_gradients.npy', mmap_mode='r', allow_pickle=False)
    parameters = np.load(endpoint/'round_parameters.npy', mmap_mode='r', allow_pickle=False)
    require(order.shape == (200, 4800), 'Unexpected order archive')
    score = -np.sum((x[:, None, :]-model.centres[None, :, :])**2, axis=2)/model.tau
    features = np.column_stack((x, np.ones(len(x))))
    coefficients = np.zeros(12); m = np.zeros(12); v = np.zeros(12); local_step = 0
    exposure = np.zeros((2, 5))
    for r in range(200):
        for b in range(75):
            ids = order[r, b*64:(b+1)*64]
            scores = score[ids].copy(); scores[:, :4] += features[ids]@coefficients.reshape(4, 3).T
            q = np.exp(scores-logsumexp(scores, axis=1, keepdims=True))
            for label in (0, 1):
                exposure[label] += q[y[ids] == label].sum(0)
            step = r*75+b+1
            if step > 750:
                g = gradients[step-1, model.expert_size:]
                local_step += 1; m = .9*m+.1*g; v = .999*v+.001*g**2
                coefficients -= .001*(m/(1-.9**local_step))/(np.sqrt(v/(1-.999**local_step))+1e-8)
        require(np.array_equal(coefficients, parameters[r, model.expert_size:]), 'Historical learned-gate replay changed')
    require(abs(float(exposure.sum())-960000) < 1e-5, 'Historical gate exposure lost probability mass')
    return dict(class_bank_weighted_visits=exposure.tolist(), total_visits=960000,
                replayed_gate_updates=local_step,
                scope='Actual pre-update gate weights on saved sampled batches; gate-only Adam replay verified against every saved round. No model refit.')


def milestones(endpoint):
    rounds = [json.loads(line) for line in (Path(endpoint)/'rounds.jsonl').read_text(encoding='utf-8').splitlines()]
    require(len(rounds) == 200 and rounds[-1]['optimizer_updates'] == 15000, 'Incomplete validation curve')
    result = []
    for threshold in (.90, .95, .97):
        hits = [r for r in rounds if r['validation']['macro_f1'] >= threshold]
        r = hits[0] if hits else None
        result.append(dict(threshold=threshold, reached=r is not None,
                           first_observed_round=r['round'] if r else None,
                           first_observed_updates=r['optimizer_updates'] if r else None,
                           first_observed_elapsed_seconds=r['elapsed_seconds'] if r else None))
    return result


def verified_resources(root, row, ownership):
    folder = inside(root, row['metadata_dir']); path = folder/'PROCESS_RESOURCES.json'
    if not path.exists():
        return None, dict(resource_limitation='No final resource sample retained; unobserved CPU is not treated as zero.')
    resources = read(path); terminal_path = folder/'TERMINAL.json'; request_path = folder/'REQUEST.json'
    terminal = read(terminal_path); request = read(request_path)
    identity = json.loads(row['identity_json'])
    require(identity and identity.get('creation_token') and ownership.get('process_identity') == identity,
            'Resource sample has no exact durable worker creation identity')
    require(resources['pid'] == identity['pid'], 'Resource PID differs from the exact registered worker')
    require(request['attempt_id'] == row['attempt_id'] and request['job']['run_id'] == row['job_id'] and
            Path(request['metadata_dir']).resolve() == folder, 'Resource request identity changed')
    require(terminal['attempt_id'] == row['attempt_id'] and terminal['job_id'] == row['job_id'] and
            terminal['status'] == row['status'] and terminal['details'].get('process_resources') == resources,
            'Resource file differs from the same-attempt terminal evidence')
    if 'process_identity' in terminal['details']:
        require(terminal['details']['process_identity'] == identity, 'Terminal worker creation identity differs')
    return resources, dict(resource_binding=binding(path), terminal_binding=binding(terminal_path),
                           request_binding=binding(request_path), exact_worker_identity=identity,
                           resource_limitation='Native lifetime peak and whole-process CPU through the retained resource sample, normally after endpoint verification. The final exit interval is not sampled; this is not training-only memory or an exact final-exit peak.')


def cost_inventory(root):
    path = root/'execution/state/ledger.sqlite3'
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute('SELECT a.*,j.phase FROM attempts a JOIN jobs j USING(job_id) ORDER BY a.job_id,a.started_utc')]
        owners = {}
        for r in db.execute("SELECT attempt_id,details_json FROM journal WHERE event='scientific_process_owned'"):
            require(r['attempt_id'] not in owners, 'Duplicate scientific ownership event')
            owners[r['attempt_id']] = json.loads(r['details_json'])
    output = []
    for row in rows:
        if row['phase'] not in ('engineering', 'A', 'B'):
            continue
        resources, evidence = verified_resources(root, row, owners.get(row['attempt_id'], {}))
        output.append(dict(job_id=row['job_id'], attempt_id=row['attempt_id'], stage=row['phase'], status=row['status'],
                           started_utc=row['started_utc'], finished_utc=row['finished_utc'],
                           resources=resources, **evidence))
    groups = []
    for stage in ('engineering', 'A', 'B'):
        for success in (True, False):
            subset = [r for r in output if r['stage'] == stage and (r['status'] == 'succeeded') == success]
            observed = [r['resources'] for r in subset if r['resources'] is not None]
            groups.append(dict(stage=stage, success=success, attempts=len(subset), measured_attempts=len(observed),
                               measured_process_cpu_seconds=sum(r['process_cpu_seconds'] for r in observed),
                               measured_sum_child_elapsed_seconds=sum(r['seconds_since_durable_ownership'] for r in observed),
                               max_observed_peak_working_set_bytes=max([r['peak_working_set_bytes'] for r in observed], default=None)))
    return dict(attempts=output, groups=groups,
                limitation='Sum of child elapsed times is compute occupancy, not parallel study wall time. Whole-child CPU and native lifetime peak extend through the post-verification sample, not final exit or training alone. Exact worker creation identity and terminal resource equality are checked. Reproduction, conversion, audits and timing have separate phase receipts. Missing failed-attempt resource samples remain unknown.')


def run(root, release_path, output):
    root = Path(root).resolve(); output = inside(root, output)
    require(not output.exists(), 'Evaluation output must be a new directory; preserve all previous attempts')
    sys.path.insert(0, str(root/'execution'))
    import durable
    from resource_probe import inspect
    with durable.auxiliary_lease(root, 'audit'):
        started = time.perf_counter(); cpu_start = time.process_time()
        verified = verify_release(root, release_path)  # No sealed model outcome before this completes.
        environment = inspect(); expected = verified['protocols']['study_plan']['runtime']
        require(environment['python'] == expected['python'] and environment['numpy_version'] == expected['numpy'] and
                environment['effective_blas_threads'] == 1, 'Registered numerical runtime required')
        sys.path.insert(0, str(root/'quantum'))
        from models import Model
        import routers
        output.mkdir(parents=True, exist_ok=False)
        write(output/'EVALUATION_STARTED.json', dict(utc=now(), release=verified['release_binding'],
              endpoint_payloads_rehashed=verified['endpoint_payloads_rehashed'], environment=environment))
        rows = []; population_cache = {}; consumed_diagnostics = {}
        try:
            for job in verified['jobs']:
                job_id = job['run_id']; name = job['population_id']; entry = verified['endpoints'][job_id]
                endpoint = Path(entry['endpoint']); selected = entry['selected_checkpoint']
                if name not in population_cache:
                    population_cache[name] = {split: load_split(root, verified, name, split, routers)
                                              for split in ('train', 'validation', 'test')}
                populations = population_cache[name]; policy = populations['train'][1]
                streams = {key: int(value['uint128_decimal']) for key, value in job['paired_streams'].items()}
                model = Model(job['arm'], job['training_seed_id'], streams, policy)
                with np.load(selected['path'], allow_pickle=False) as checkpoint:
                    model.parameters[:] = checkpoint['parameters']
                    require(int(checkpoint['current_round']) == entry['selected_round'], 'Selected round changed')
                    selected_vp = checkpoint['validation_probabilities'].copy()
                    selected_vz = checkpoint['validation_logits'].copy()
                record = dict(job_id=job_id, family=job['family'], population=name, seed=job['training_seed_id'],
                              arm=job['arm'], selected_round=entry['selected_round'], endpoint_commit=entry['commit'],
                              selected_checkpoint=selected, parameter_count=len(model.parameters))
                predictions = {}
                for split, (data, _) in populations.items():
                    x = model.input_for(data); p, z = model.predict_with_logits(x)
                    if split == 'validation':
                        require(np.array_equal(p, selected_vp) and np.array_equal(z, selected_vz), 'Selected validation predictions changed')
                    record[split] = metrics(data['y'], p, z)
                    record[split+'_slices'] = diagnostic_slices(data, p, z, policy)
                    bank, q, expert_z = bank_diagnostics(model, x, data['y'])
                    record[split+'_bank_diagnostics'] = bank
                    for key, value in dict(ids=data['ids'], labels=data['y'], probabilities=p, logits=z,
                                           weights=q, expert_logits=expert_z, margin_bin=data['margin_bin'],
                                           geometric_route=data['kmeans_route']).items():
                        predictions[f'{split}_{key}'] = value
                if job['family'] == 'annulus':
                    meta = verified['seal']['diagnostics'][name]; path = root/'quantum/data'/meta['file']
                    require(sha(path) == meta['sha256'], 'Sealed latent diagnostics changed')
                    consumed_diagnostics[str(path)] = binding(path)
                    with np.load(path, allow_pickle=False) as latent:
                        data = populations['test'][0]
                        require(np.array_equal(latent['test_ids'], data['ids']), 'Clean-label record alignment changed')
                        clean = latent['test_clean_y']; flipped = latent['test_label_flip'].astype(bool)
                    p = predictions['test_probabilities']; z = predictions['test_logits']
                    record['annulus_clean_label_test'] = metrics(clean, p, z)
                    record['annulus_flip_strata'] = [dict(flipped=bool(f), observed=metrics(data['y'][flipped == f], p[flipped == f], z[flipped == f]),
                                                        clean=metrics(clean[flipped == f], p[flipped == f], z[flipped == f])) for f in (False, True)]
                    predictions['test_clean_y'] = clean; predictions['test_label_flip'] = flipped
                record['actual_training_gate_exposure'] = actual_training_exposure(model, populations['train'][0], endpoint)
                record['validation_milestones'] = milestones(endpoint)
                result = read(endpoint/'result.json')
                record['costs'] = {key: result[key] for key in ('training_seconds', 'training_process_cpu_seconds',
                    'endpoint_total_seconds', 'invocation_process_cpu_seconds_through_result',
                    'diagnostic_forward_wall_seconds', 'diagnostic_forward_cpu_seconds', 'sampler_wall_seconds',
                    'sampler_cpu_seconds', 'work', 'expert_parameter_count', 'extra_parameter_count', 'full_training_record_visits')}
                record['costs']['checkpoint_bytes'] = selected['bytes']
                record['costs']['endpoint_payload_bytes'] = sum(v['bytes'] for v in read(endpoint/'endpoint_commit.json')['files'].values())
                name_out = job_id.replace('/', '__'); folder = output/'endpoints'; folder.mkdir(exist_ok=True)
                np.savez_compressed(folder/(name_out+'.npz'), **predictions)
                write(folder/(name_out+'.json'), record); rows.append(record)
            statistics = analyze(rows, verified['protocols']['analysis_protocol'])
            milestone_summary = []
            for family, arm in sorted({(r['family'], r['arm']) for r in rows}):
                chosen = [r for r in rows if r['family'] == family and r['arm'] == arm]
                for k, threshold in enumerate((.90, .95, .97)):
                    mm = [r['validation_milestones'][k] for r in chosen]
                    milestone_summary.append(dict(family=family, arm=arm, threshold=threshold, n=len(mm),
                                                   never=sum(not r['reached'] for r in mm),
                                                   reached_updates=distribution([r['first_observed_updates'] for r in mm]),
                                                   limitation='Descriptive validation observations at round boundaries; not test performance, early stopping or reselection.'))
            write(output/'STATISTICAL_ANALYSIS.json', statistics)
            write(output/'VALIDATION_MILESTONES.json', milestone_summary)
            write(output/'RESOURCE_ACCOUNTING.json', cost_inventory(root))
            write(output/'ENDPOINT_RESULTS.json', rows)
            # Recheck every bound source, protocol and consumed data file before commit.
            require(evaluator_sources(root) == verified['release']['evaluator_sources'], 'Evaluator changed during scoring')
            for name, expected_hash in verified['scientific_source_hashes'].items():
                require(sha(root/'quantum'/name) == expected_hash, 'Scientific source changed during scoring')
            for key, relpath in PROTOCOL_PATHS.items():
                require(binding(root/relpath) == verified['release']['protocols'][key], 'Protocol changed during scoring')
            for name in population_cache:
                for split in ('train', 'validation', 'SEALED_test'):
                    filename = f'{name}_{split}.npz'
                    require(sha(root/'quantum/data'/filename) == verified['seal']['files'][filename]['sha256'], 'Consumed data changed')
                require(sha(root/'quantum/data'/f'{name}_router.json') == verified['seal']['routers'][name]['sha256'], 'Router changed')
            for path, expected_binding in consumed_diagnostics.items():
                require(binding(path) == expected_binding, 'Consumed sealed latent diagnostics changed during scoring')
            require(binding(release_path) == verified['release_binding'], 'Root release changed during scoring')
            files = {str(p.relative_to(output)).replace('\\', '/'): dict(sha256=sha(p), bytes=p.stat().st_size)
                     for p in sorted(output.rglob('*')) if p.is_file()}
            commit = dict(schema='qpath-v09-author-evaluation-commit-1', status='PASS', utc=now(), scored_endpoints=len(rows),
                          release=verified['release_binding'], evaluator_sources=evaluator_sources(root),
                          files=files, wall_seconds=time.perf_counter()-started, process_cpu_seconds=time.process_time()-cpu_start,
                          environment=environment, physical_quantum_jobs=0, training_performed=False,
                          selection='Previously frozen earliest strict validation BCE minimum; no test reselection.',
                          scope='All registered B models, train/validation/test metrics and diagnostics, 12 primary synthetic BCE contrasts, separate descriptive Banknote results.')
            write(output/'EVALUATION_COMMIT.json', commit)
            return binding(output/'EVALUATION_COMMIT.json')
        except BaseException as error:
            write(output/'EVALUATION_FAILURE.json', dict(utc=now(), error_type=type(error).__name__, error=str(error),
                  traceback=traceback.format_exc(), completed_endpoints=len(rows),
                  recovery='Preserve this attempt; root-reviewed correction and a new output directory required.'))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.release, args.output)))


if __name__ == '__main__':
    main()
