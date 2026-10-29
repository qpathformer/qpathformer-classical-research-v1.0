"""Independent metrics and registered paired uncertainty, using NumPy only."""
import math
import numpy as np

METRICS = ('bce', 'macro_f1', 'accuracy')
CLIP = 1e-7


def metrics(labels, probabilities, weights=None):
    labels, p = np.asarray(labels), np.asarray(probabilities, dtype=np.float64)
    if labels.shape != p.shape or p.ndim != 1 or not len(p):
        raise ValueError('Nonempty aligned one-dimensional arrays required')
    if not np.isin(labels, [0, 1]).all() or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Binary labels and finite physical probabilities required')
    w = np.ones(len(p), dtype=np.int64) if weights is None else np.asarray(weights)
    if w.shape != p.shape or not np.isfinite(w).all() or np.any(w < 0) or w.sum() <= 0:
        raise ValueError('Invalid nonnegative record multiplicities')
    predicted = (p >= .5).astype(np.int64)
    confusion = np.zeros((2, 2), dtype=np.float64)
    for y in (0, 1):
        for yhat in (0, 1):
            confusion[y, yhat] = w[(labels == y) & (predicted == yhat)].sum()
    f1 = []
    for y in (0, 1):
        numerator = 2 * confusion[y, y]
        denominator = confusion[y, :].sum() + confusion[:, y].sum()
        f1.append(numerator / denominator if denominator else 0.)
    bounded = np.minimum(1 - CLIP, np.maximum(CLIP, p))
    loss = -(labels * np.log(bounded) + (1 - labels) * np.log(1 - bounded))
    return {'bce': float(np.dot(w, loss) / w.sum()), 'macro_f1': float(sum(f1) / 2),
            'accuracy': float(np.trace(confusion) / w.sum()),
            'clipped': int(w[(p < CLIP) | (p > 1 - CLIP)].sum()),
            'confusion': confusion.astype(np.int64).tolist()}


def t_cdf_df4(value):
    """Closed-form Student t CDF for df4; no SciPy/official statistics imports."""
    s = value / math.sqrt(value * value + 4)
    return .5 + .75 * s - .25 * s ** 3


def t_critical_df4(confidence):
    if not 0 < confidence < 1: raise ValueError('Invalid confidence')
    target = (1 + confidence) / 2
    low, high = 0., 1.
    while t_cdf_df4(high) < target: high *= 2
    for _ in range(100):
        middle = (low + high) / 2
        if t_cdf_df4(middle) < target: low = middle
        else: high = middle
    return (low + high) / 2


def seed_statistics(values, primary=False):
    a = np.asarray(values, dtype=np.float64)
    if a.shape != (5,) or not np.isfinite(a).all(): raise ValueError('Exactly five finite paired seeds required')
    mean, sd = float(a.mean()), float(a.std(ddof=1))
    result = {'n': 5, 'values': a.tolist(), 'mean': mean, 'sample_sd': sd,
              't95': [mean - t_critical_df4(.95) * sd / math.sqrt(5),
                      mean + t_critical_df4(.95) * sd / math.sqrt(5)]}
    if primary:
        level = 1 - .05 / 3
        half = t_critical_df4(level) * sd / math.sqrt(5)
        result['primary_bonferroni_confidence'] = level
        result['primary_bonferroni_t_interval'] = [mean - half, mean + half]
    return result


def paired_record_bootstrap(labels, probabilities, replicates=2000, seed=98003):
    """Return [replicate,method,metric] seed means from shared resampled records.

    probabilities has [method,5,n] layout. A single vector of n sampled record
    positions is shared by every method/checkpoint in each bootstrap replicate.
    Count multiplication computes the same resample without copying records.
    """
    y, p = np.asarray(labels), np.asarray(probabilities, dtype=np.float64)
    if p.ndim != 3 or p.shape[1] != 5 or p.shape[2] != len(y):
        raise ValueError('Expected [method,5,record] probabilities')
    if not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Invalid bootstrap input')
    n, methods = len(y), len(p)
    flat = p.reshape(-1, n)
    bounded = np.minimum(1 - CLIP, np.maximum(CLIP, flat))
    loss = -(y[None] * np.log(bounded) + (1 - y[None]) * np.log(1 - bounded))
    prediction = flat >= .5
    cells = [((y[None] == a) & (prediction == b)).astype(np.float64)
             for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))]
    rng = np.random.Generator(np.random.PCG64(seed))
    output = np.empty((replicates, methods, 3), dtype=np.float64)
    for iteration in range(replicates):
        sampled = rng.integers(0, n, size=n)
        counts = np.bincount(sampled, minlength=n)
        tn, fp, fn, tp = [cell @ counts for cell in cells]
        f1 = np.divide(2 * tn, 2 * tn + fp + fn, out=np.zeros_like(tn), where=(2 * tn + fp + fn) != 0)
        f1 += np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros_like(tp), where=(2 * tp + fp + fn) != 0)
        measures = np.stack([loss @ counts / n, f1 / 2, (tn + tp) / n], axis=-1)
        output[iteration] = measures.reshape(methods, 5, 3).mean(axis=1)
    return output


def summarize(labels, probabilities, methods, protocol):
    p = np.asarray(probabilities)
    if p.shape != (len(methods), 5, len(labels)): raise ValueError('Five ordered seeds per method required')
    per = np.asarray([[[metrics(labels, row)[key] for key in METRICS] for row in arm] for arm in p])
    boot = paired_record_bootstrap(labels, p, protocol['record_bootstrap']['replicates'],
                                   protocol['record_bootstrap']['seed'])
    result = {'metric_order': list(METRICS), 'training_seeds': [601, 602, 603, 604, 605],
              'test_records': len(labels), 'aggregates': {}, 'contrasts': {},
              't95_critical_df4': t_critical_df4(.95),
              'primary_bonferroni_t_critical_df4': t_critical_df4(1 - .05 / 3),
              'units': {'bce': 'natural-log units per record', 'macro_f1': 'fraction', 'accuracy': 'fraction'},
              'bootstrap_scope': 'Conditional on fixed trained checkpoints and one test population; excludes training-seed, task, router-fit and selection uncertainty.',
              'seed_interval_scope': 'Paired five-seed t intervals with df4 assumptions; descriptive 95% and three-primary-family Bonferroni intervals; no equivalence inference.'}
    for index, method in enumerate(methods):
        result['aggregates'][method] = {key: seed_statistics(per[index, :, j]) for j, key in enumerate(METRICS)}
    primary = [tuple(c) for c in protocol['primary_contrasts']]
    for a, b in primary + [tuple(c) for c in protocol['secondary_contrasts']]:
        i, j = methods.index(a), methods.index(b)
        contrast = {'first': a, 'second': b, 'primary_bce': (a, b) in primary, 'metrics': {}}
        for k, key in enumerate(METRICS):
            adjusted = (a, b) in primary and key == 'bce'
            item = seed_statistics(per[i, :, k] - per[j, :, k], adjusted)
            draws = boot[:, i, k] - boot[:, j, k]
            item['paired_record_bootstrap95'] = np.percentile(draws, [2.5, 97.5], method='linear').tolist()
            if adjusted:
                item['primary_bonferroni_record_percentile_interval'] = np.percentile(
                    draws, [100 * (.05 / 3) / 2, 100 * (1 - (.05 / 3) / 2)], method='linear').tolist()
                item['practical_threshold'] = -.01
            if key in ('macro_f1', 'accuracy'):
                item['percentage_point_mean'] = 100 * item['mean']
                item['percentage_point_t95'] = (100 * np.asarray(item['t95'])).tolist()
            contrast['metrics'][key] = item
        result['contrasts'][a + '_minus_' + b] = contrast
    return result, boot
