"""Independent recovery01 threshold diagnostics; never changes probabilities.

The 32-epsilon band is an engineering convention, not an error bound or CI.
Only saved-production near-band records enter sensitivity scenarios. Labels
enter the two explicitly labelled diagnostic extrema, never predictions.
"""
import numpy as np
from statistics_reference import metrics

BAND = 32 * np.finfo(np.float64).eps
RECOVERY_SHA = '049f4a627fda5fa08c739cc53375aa104e28d223bb78d525841d0f01d7931e0e'


def require(condition, message):
    if not condition: raise ValueError(message)


def class_metrics(y, prediction):
    """Binary macro-F1, accuracy and confusion only; no synthetic BCE."""
    y, predicted = np.asarray(y), np.asarray(prediction)
    require(y.ndim == 1 and len(y) and y.shape == predicted.shape
            and np.isin(y, (0, 1)).all() and np.isin(predicted, (0, 1)).all(), 'Invalid class arrays')
    c = np.array([[np.count_nonzero((y == a) & (predicted == b)) for b in (0, 1)] for a in (0, 1)])
    f = []
    for k in (0, 1):
        den = int(c[k, :].sum() + c[:, k].sum())
        f.append(2 * int(c[k, k]) / den if den else 0.)
    return {'confusion': c.tolist(), 'macro_f1': float(sum(f) / 2),
            'accuracy': float(np.trace(c) / len(y))}


def threshold_diagnostics(y, canonical, reference, ids, depth, routes):
    y, p, q = np.asarray(y), np.asarray(canonical, dtype=np.float64), np.asarray(reference, dtype=np.float64)
    n = len(y)
    require(p.shape == q.shape == y.shape == (n,) and n > 0, 'Aligned nonempty arrays required')
    require(np.isfinite(p).all() and np.isfinite(q).all() and ((p >= 0) & (p <= 1)).all()
            and ((q >= 0) & (q <= 1)).all(), 'Invalid physical probabilities')
    ids, depth = np.asarray(ids), np.asarray(depth)
    require(ids.shape == depth.shape == (n,) and len(set(ids.tolist())) == n, 'Invalid record identities')
    require(set(routes) == {'hash', 'kmeans'} and all(np.asarray(v).shape == (n,) for v in routes.values()), 'Invalid route arrays')
    saved_class, ref_class = p >= .5, q >= .5
    saved_near, ref_near = np.abs(p - .5) <= BAND, np.abs(q - .5) <= BAND
    disagree = saved_class != ref_class
    outside = disagree & ~(saved_near & ref_near)
    require(np.max(np.abs(p - q)) <= 2e-12, 'Independent probability tolerance exceeded')
    require(not outside.any(), 'Threshold disagreement outside the BOTH-probabilities32eps band')
    canonical_metrics, reference_metrics = metrics(y, p), metrics(y, q)
    require(abs(canonical_metrics['bce'] - reference_metrics['bce']) <= 1e-9, 'Independent BCE tolerance exceeded')

    def counts(ix):
        return {'n': int(np.count_nonzero(ix)), 'canonical_near_band_count': int(np.count_nonzero(ix & saved_near)),
                'reference_near_band_count': int(np.count_nonzero(ix & ref_near)),
                'union_near_band_count': int(np.count_nonzero(ix & (saved_near | ref_near))),
                'classification_disagreements': int(np.count_nonzero(ix & disagree)),
                'outside_band_disagreements': int(np.count_nonzero(ix & outside)),
                'exact_classifier_agreement': not bool(np.any(ix & disagree))}

    scenarios = {}
    for name, values in [('all_class0', np.zeros(n, dtype=np.int64)), ('all_class1', np.ones(n, dtype=np.int64)),
                         ('all_incorrect_label_assisted', 1 - y), ('all_correct_label_assisted', y)]:
        changed = saved_class.astype(np.int64).copy(); changed[saved_near] = values[saved_near]
        scenarios[name] = class_metrics(y, changed)
    rows = []
    for i in np.flatnonzero(disagree):
        rows.append({'record_id': int(ids[i]), 'allocation_depth': int(depth[i]), 'label': int(y[i]),
                     'canonical_probability': float(p[i]), 'reference_probability': float(q[i]),
                     'canonical_prediction': int(saved_class[i]), 'reference_prediction': int(ref_class[i]),
                     'hash_route': int(routes['hash'][i]), 'kmeans_route': int(routes['kmeans'][i])})
    return {'status': 'PASS_UNDER_RECOVERY_01', 'numerical_recovery_protocol_sha256': RECOVERY_SHA,
            'band_half_width': float(BAND), 'counts': counts(np.ones(n, dtype=bool)),
            'counts_by_depth': {str(int(d)): counts(depth == d) for d in sorted(set(depth.tolist()))},
            'counts_by_route': {kind: {str(int(k)): counts(np.asarray(values) == k) for k in sorted(set(np.asarray(values).tolist()))}
                                for kind, values in routes.items()},
            'counts_by_label': {str(k): counts(y == k) for k in (0, 1)},
            'canonical_metrics': canonical_metrics, 'reference_metrics': reference_metrics,
            'reference_minus_canonical': {k: reference_metrics[k] - canonical_metrics[k] for k in ('bce', 'macro_f1', 'accuracy')},
            'canonical_band_sensitivity': scenarios, 'disagreements': rows,
            'sensitivity_scope': 'Canonical saved-probability band only; conventions are not extrema. Label-assisted extrema are possible class-flip sensitivity, not trained models or statistical confidence intervals. No probabilities or BCE changed.',
            'verification_scope': 'Canonical metric reconstruction and independent probability/BCE verification; exact classifier agreement is reported separately.'}
