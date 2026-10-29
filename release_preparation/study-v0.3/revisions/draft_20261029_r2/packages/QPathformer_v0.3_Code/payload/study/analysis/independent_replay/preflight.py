"""Engineering-only oracle comparisons; never loads confirmation/test data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from matrix_reference import METHODS, predict, routes_from_policy
from statistics_reference import metrics

HERE = Path(__file__).resolve().parent
QUANTUM = HERE.parents[1] / 'quantum'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(output):
    if output.exists(): raise FileExistsError(output)
    if np.__version__ != '2.5.4': raise RuntimeError('Use the recorded NumPy2.5.4 runtime')
    sys.path.insert(0, str(QUANTUM))
    import qstudy  # Engineering preflight ONLY; production replay does not import this.
    data_path = QUANTUM / 'data/engineering_validation.npz'
    seal_path = QUANTUM / 'data/DATA_SEAL.json'
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    if sha(data_path) != seal['files'][data_path.name]['sha256']: raise ValueError('Engineering data hash mismatch')
    with np.load(data_path, allow_pickle=False) as f: data = {k: f[k] for k in f.files}
    policy_path = QUANTUM / 'data/engineering_router.json'
    if sha(policy_path) != seal['routers']['engineering']['sha256']: raise ValueError('Engineering policy hash mismatch')
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    routes = routes_from_policy(data['x'], policy)
    for key in routes: np.testing.assert_array_equal(routes[key], data[key])
    # Every depth/bank occurs; choose deterministic label-independent rows.
    positions = np.random.Generator(np.random.PCG64(610019)).choice(len(data['x']), size=64, replace=False)
    subset = {k: v[positions] for k, v in data.items()}
    reports = []
    for method in METHODS:
        model = qstudy.Model(method, 7301)
        checkpoint = QUANTUM / f'engineering_pilot_v01/{method}/selected_checkpoint.npz'
        with np.load(checkpoint, allow_pickle=False) as f: model.parameters[:] = f['parameters']
        for variant in ('engineering_checkpoint', 'synthetic_perturbation'):
            if variant == 'synthetic_perturbation':
                model.parameters[:] = np.random.Generator(np.random.PCG64(71301)).normal(0, 1, len(model.parameters))
            official = model.predict_population(subset)
            independent = predict(method, model.parameters, subset['x'], subset['depth'], subset)
            error = float(np.max(np.abs(official - independent)))
            disagreements = int(np.sum((official >= .5) != (independent >= .5)))
            if error > 2e-12: raise ValueError(f'{method} probability error {error}')
            a, b = qstudy.metrics(subset['y'], official), metrics(subset['y'], independent)
            for key in ('bce', 'macro_f1', 'accuracy'):
                if abs(a[key] - b[key]) > 1e-10: raise ValueError(f'{method} metric error {key}')
            reports.append({'method': method, 'fixture': variant, 'records': len(positions),
                            'maximum_probability_error': error, 'classification_disagreements': disagreements,
                            'checkpoint_sha256': sha(checkpoint) if variant == 'engineering_checkpoint' else None})
    result = {'status': 'PASS', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'test_outcomes_accessed': False, 'confirmation_data_accessed': False,
              'scope': 'Engineering validation and deterministic synthetic parameter perturbations only; not an official confirmation result.',
              'numpy': np.__version__, 'python': sys.version, 'executable': sys.executable,
              'data_sha256': sha(data_path), 'policy_sha256': sha(policy_path),
              'data_seal_sha256': sha(seal_path), 'production_sources': qstudy.source_hashes(),
              'independent_sources': {p.name: sha(p) for p in HERE.glob('*.py')},
              'route_records_checked': len(data['x']), 'reports': reports}
    with output.open('x', encoding='utf-8') as f: json.dump(result, f, indent=2, allow_nan=False)
    print(json.dumps({'status': 'PASS', 'comparison_cases': len(reports),
                      'maximum_probability_error': max(r['maximum_probability_error'] for r in reports),
                      'classification_disagreements': sum(r['classification_disagreements'] for r in reports)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
