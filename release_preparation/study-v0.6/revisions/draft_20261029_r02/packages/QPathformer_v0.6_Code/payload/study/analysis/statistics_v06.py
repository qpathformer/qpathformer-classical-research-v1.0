"""Registered official probability summaries; independent replay must not import this."""
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / 'governance/ANALYSIS_PROTOCOL.json'
CLIP = 1e-7
NAMES = ('bce', 'macro_f1', 'accuracy', 'brier')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def metric_arrays(labels, probabilities):
    """seed x method x four metrics, plus per-record BCE and Brier."""
    y = np.asarray(labels, dtype=np.int64)
    p = np.asarray(probabilities, dtype=np.float64)
    if y.ndim != 1 or p.ndim != 3 or p.shape[-1] != len(y) or not len(y):
        raise ValueError('Invalid prediction shapes')
    if not np.isin(labels, [0, 1]).all() or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Invalid labels or probabilities')
    pc = np.clip(p, CLIP, 1-CLIP)
    loss = -(y*np.log(pc)+(1-y)*np.log1p(-pc))
    brier = (p-y)**2
    pred = p >= .5
    tp = np.sum(pred & (y == 1), axis=-1)
    fp = np.sum(pred & (y == 0), axis=-1)
    fn = np.sum(~pred & (y == 1), axis=-1)
    tn = np.sum(~pred & (y == 0), axis=-1)
    f1 = _macro_f1(tp, fp, fn, tn)
    metrics = np.stack([loss.mean(axis=-1), f1, (tp+tn)/len(y), brier.mean(axis=-1)], axis=-1)
    return metrics, loss, brier

def _macro_f1(tp, fp, fn, tn):
    d1, d0 = 2*tp+fp+fn, 2*tn+fp+fn
    return (np.divide(2*tp, d1, out=np.zeros_like(tp, dtype=float), where=d1 != 0)
            + np.divide(2*tn, d0, out=np.zeros_like(tn, dtype=float), where=d0 != 0))/2

def calibration(labels, probabilities):
    y, p = np.asarray(labels), np.asarray(probabilities, dtype=float)
    if y.shape != p.shape or y.ndim != 1 or not len(y):
        raise ValueError('Calibration requires one nonempty checkpoint')
    if not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Invalid calibration values')
    bins, ece = [], 0.0
    # Searchsorted preserves the declared [lo,hi) convention at float boundaries.
    edges = np.linspace(0, 1, 11)
    ix = np.minimum(np.searchsorted(edges, p, side='right')-1, 9)
    for k in range(10):
        mask = ix == k
        n = int(mask.sum())
        meanp = float(p[mask].mean()) if n else None
        meany = float(y[mask].mean()) if n else None
        if n:
            ece += n/len(y)*abs(meanp-meany)
        bins.append({'lower': float(edges[k]), 'upper': float(edges[k+1]), 'count': n,
                     'mean_probability': meanp, 'positive_fraction': meany})
    return {'ece': float(ece), 'bins': bins}

def _interval(values, confidence):
    values = np.asarray(values, dtype=np.float64)
    mean, sd = float(values.mean()), float(values.std(ddof=1))
    half = float(t.ppf((1+confidence)/2, len(values)-1)*sd/np.sqrt(len(values)))
    return {'mean': mean, 'sample_sd': sd, 'n': len(values), 'confidence': confidence,
            'lower': mean-half, 'upper': mean+half}


def class_quality(labels, probabilities):
    """Fixed-threshold class diagnostics and grouped, noninterpolated AP."""
    y, p = np.asarray(labels), np.asarray(probabilities, dtype=np.float64)
    if y.ndim != 1 or p.shape != y.shape or not len(y):
        raise ValueError('One nonempty matching label/probability array required')
    if not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Invalid labels or probabilities')
    prediction = p >= .5
    tp = int(np.sum(prediction & (y == 1))); fp = int(np.sum(prediction & (y == 0)))
    fn = int(np.sum(~prediction & (y == 1))); tn = int(np.sum(~prediction & (y == 0)))
    positives = int(np.sum(y)); ap = None
    if positives:
        order = np.argsort(-p, kind='stable'); scores = p[order]; ranked = y[order]
        ends = np.r_[np.flatnonzero(scores[1:] != scores[:-1]), len(y)-1]
        cumulative = np.cumsum(ranked)[ends]
        group_positive = np.diff(np.r_[0, cumulative])
        ap = float(np.sum((group_positive/positives)*(cumulative/(ends+1))))
    return {'prevalence': positives/len(y), 'positive_precision': tp/(tp+fp) if tp+fp else 0.,
            'positive_recall': tp/(tp+fn) if tp+fn else None,
            'negative_recall': tn/(tn+fp) if tn+fp else None,
            'average_precision': ap, 'confusion': [[tn, fp], [fn, tp]]}

def _bootstrap_metrics(labels, probabilities, loss, brier, counts):
    y, p = np.asarray(labels), np.asarray(probabilities)
    n = len(y)
    s, m, _ = p.shape
    if counts.ndim != 2 or counts.shape[1] != n or not np.all(counts.sum(axis=1) == n) or np.any(counts < 0):
        raise ValueError('Invalid paired record counts')
    pred = p.reshape(s*m, n) >= .5
    tp_basis = (pred & (y == 1)).astype(np.float64).T
    fp_basis = (pred & (y == 0)).astype(np.float64).T
    result = np.empty((len(counts), m, 4), dtype=np.float64)
    for start in range(0, len(counts), 100):
        stop = min(start+100, len(counts))
        c = counts[start:stop].astype(np.float64)
        tp, fp = c@tp_basis, c@fp_basis
        pos = (c@y)[:, None]
        fn, tn = pos-tp, n-pos-fp
        result[start:stop, :, 0] = c@loss.mean(axis=0).T/n
        result[start:stop, :, 1] = _macro_f1(tp, fp, fn, tn).reshape(stop-start, s, m).mean(axis=1)
        result[start:stop, :, 2] = ((tp+tn)/n).reshape(stop-start, s, m).mean(axis=1)
        result[start:stop, :, 3] = c@brier.mean(axis=0).T/n
    return result

def analyse_population(population_name, labels, probabilities, seeds, methods, output_dir):
    """All 30 committed endpoints for one population. Caller enforces release gate."""
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding='utf-8-sig'))
    if list(seeds) != protocol['training_seeds'] or list(methods) != protocol['methods']:
        raise ValueError('Unregistered seeds or method order')
    if population_name not in protocol['population_order']:
        raise ValueError('Unregistered confirmation population')
    p, y = np.asarray(probabilities, dtype=np.float64), np.asarray(labels)
    if p.shape[:2] != (len(seeds), len(methods)):
        raise ValueError('All registered population endpoints required')
    metrics, loss, brier = metric_arrays(y, p)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    config = protocol['record_bootstrap']
    rng = np.random.Generator(np.random.PCG64(config['seeds'][population_name]))
    raw = rng.multinomial(len(y), np.full(len(y), 1.0/len(y)), size=config['replicates'])
    if raw.max() > np.iinfo(np.uint16).max:
        raise ValueError('Bootstrap count overflow')
    counts = raw.astype(np.uint16)
    count_path = output/'bootstrap_counts.npy'
    np.save(count_path, counts, allow_pickle=False)
    boot = _bootstrap_metrics(y, p, loss, brier, counts)
    aggregate = {}
    for mi, method in enumerate(methods):
        aggregate[method] = {metric: {'mean': float(metrics[:, mi, ki].mean()),
                                    'sample_sd': float(metrics[:, mi, ki].std(ddof=1)),
                                    'seed_values': metrics[:, mi, ki].tolist()}
                             for ki, metric in enumerate(NAMES)}
        cal = [calibration(y, p[si, mi]) for si in range(len(seeds))]
        aggregate[method]['calibration'] = {'seed_results': cal,
            'ece_mean': float(np.mean([row['ece'] for row in cal])),
            'ece_sample_sd': float(np.std([row['ece'] for row in cal], ddof=1))}
        quality = [class_quality(y, p[si, mi]) for si in range(len(seeds))]
        aggregate[method]['class_quality'] = {'seed_results': quality,
            'descriptive': {key: {'mean': float(np.mean([r[key] for r in quality])),
                                 'sample_sd': float(np.std([r[key] for r in quality], ddof=1))}
                            if all(r[key] is not None for r in quality) else None
                            for key in ('prevalence','positive_precision','positive_recall','negative_recall','average_precision')}}
    comparisons = []
    for primary, pairs in [(True, protocol['primary_contrasts']), (False, protocol['secondary_contrasts'])]:
        for first, second in pairs:
            ai, bi = methods.index(first), methods.index(second)
            result = {'name': first+' minus '+second, 'terms': [(first, 1), (second, -1)],
                      'primary': primary, 'metrics': {}}
            for ki, metric in enumerate(NAMES):
                scale = 100.0 if metric in ('macro_f1', 'accuracy') else 1.0
                seed_delta = (metrics[:, ai, ki]-metrics[:, bi, ki])*scale
                boot_delta = (boot[:, ai, ki]-boot[:, bi, ki])*scale
                item = {'units': ('percentage_points' if scale == 100 else
                                 'natural_log_loss' if metric == 'bce' else 'squared_probability_error'),
                        'seed_values': seed_delta.tolist(), 'seed_interval95': _interval(seed_delta, .95),
                        'record_interval95': np.quantile(boot_delta, [.025, .975], method='linear').tolist()}
                if primary and metric == 'bce':
                    alpha = .05/protocol['primary_family_size']
                    item['seed_interval_adjusted'] = _interval(seed_delta, 1-alpha)
                    item['record_interval_adjusted'] = np.quantile(boot_delta, [alpha/2, 1-alpha/2], method='linear').tolist()
                    item['practical_magnitude'] = protocol['practical_difference']
                result['metrics'][metric] = item
            comparisons.append(result)
    result = {'population': population_name, 'n': len(y), 'seeds': list(seeds), 'methods': list(methods),
              'protocol_sha256': digest(PROTOCOL_PATH), 'statistics_source_sha256': digest(__file__),
              'numpy_version': np.__version__, 'bootstrap_counts_sha256': digest(count_path),
              'bootstrap_replicates': len(counts), 'primary_family_size': protocol['primary_family_size'],
              'aggregate': aggregate, 'contrasts': comparisons,
              'limits': {'seed': protocol['seed_uncertainty']['limits'], 'record': config['limits'],
                         'secondary': protocol['secondary_units']}}
    with (output/'population_summary.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    return result

