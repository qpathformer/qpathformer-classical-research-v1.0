"""Independent comparisons with the official public output schema; no loading."""
import numpy as np
from statistics_reference import METRICS


def require(condition, message):
    if not condition: raise ValueError(message)


def close(actual, expected, label, tolerance=1e-10):
    a, b = np.asarray(actual, dtype=np.float64), np.asarray(expected, dtype=np.float64)
    require(a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all(), f'{label}: invalid comparison arrays')
    error = float(np.max(np.abs(a - b))) if a.size else 0.
    require(error <= tolerance, f'{label}: maximum error {error:.17g} exceeds {tolerance}')
    return error


def compare_metrics(independent, official, records, label):
    errors = [close(independent[k], official[k], f'{label}/{k}', 1e-9 if k == 'bce' else 0.) for k in METRICS]
    require(independent['confusion'] == official['confusion'], label + ': confusion mismatch')
    require(independent['clipped'] == official['clipped'], label + ': clipped count mismatch')
    if 'n' in official: require(official['n'] == records, label + ': count mismatch')
    return max(errors)


def compare_statistics(independent, official, independent_bootstrap, official_bootstrap):
    """All registered aggregate, contrast, seed and record intervals must match."""
    errors = []
    checks = 0

    def compare_seed(ours, theirs, label, adjusted=False):
        nonlocal checks
        require(theirs['n_training_seeds'] == 5 and theirs['degrees_of_freedom'] == 4, label + ': replication unit mismatch')
        for key in ('values', 'mean', 'sample_sd'):
            errors.append(close(ours[key], theirs[key], label + '/' + key)); checks += 1
        interval = ours['primary_bonferroni_t_interval'] if adjusted else ours['t95']
        errors.append(close(interval, theirs['t_interval'], label + '/t_interval')); checks += 1
        require(abs(theirs['confidence'] - (1 - .05 / 3 if adjusted else .95)) < 1e-15,
                label + ': confidence mismatch')

    require(official['metric_order'] == list(METRICS), 'Metric order mismatch')
    require(official['training_seeds'] == independent['training_seeds'], 'Training seed identities mismatch')
    require(official['n_test_records'] == independent['test_records'], 'Test record count mismatch')
    require(set(official['aggregates']) == set(independent['aggregates']), 'Aggregate method set mismatch')
    for method, values in independent['aggregates'].items():
        for metric in METRICS: compare_seed(values[metric], official['aggregates'][method][metric], method + '/' + metric)
    theirs = {(row['first'], row['second']): row for row in official['contrasts']}
    require(len(theirs) == len(official['contrasts']) == len(independent['contrasts']), 'Contrast count/duplicates mismatch')
    for label, row in independent['contrasts'].items():
        peer = theirs[(row['first'], row['second'])]
        require(peer['family'] == ('primary' if row['primary_bce'] else 'secondary'), label + ': family mismatch')
        for metric in METRICS:
            ours, other = row['metrics'][metric], peer['metrics'][metric]
            compare_seed(ours, other['seed'], label + '/' + metric)
            errors.append(close(ours['paired_record_bootstrap95'], other['conditional_record_bootstrap95'], label + '/' + metric + '/record95')); checks += 1
            if row['primary_bce'] and metric == 'bce':
                compare_seed(ours, other['seed_bonferroni'], label + '/adjusted_bce', adjusted=True)
                errors.append(close(ours['primary_bonferroni_record_percentile_interval'],
                                    other['conditional_record_bootstrap_bonferroni'], label + '/adjusted_record')); checks += 1
                require(other['practical_improvement_threshold'] == -.01, label + ': practical threshold mismatch')
                require(other['mean_reaches_practical_magnitude'] == (ours['mean'] <= -.01), label + ': practical magnitude flag mismatch')
            if metric == 'macro_f1':
                errors.append(close(ours['percentage_point_mean'], other['percentage_point_mean'], label + '/f1_pp')); checks += 1
    errors.append(close(independent_bootstrap, official_bootstrap, 'All registered bootstrap draws')); checks += 1
    return {'status': 'PASS', 'numeric_comparisons': checks, 'maximum_numeric_error': max(errors)}
