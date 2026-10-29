"""Independent checks of official recovery diagnostics; no official imports."""
import numpy as np
from comparison import require, close, compare_metrics
from statistics_reference import seed_statistics
from threshold_reference import BAND, RECOVERY_SHA, class_metrics

CASES = {'all_class0': 'all_ambiguous_to0', 'all_class1': 'all_ambiguous_to1',
         'all_incorrect_label_assisted': 'label_assisted_all_incorrect',
         'all_correct_label_assisted': 'label_assisted_all_correct'}


def compare_endpoint(ours, peer, pop, saved):
    """Canonical diagnostics agree exactly; reference implementations may differ."""
    require(peer['protocol_sha256'] == RECOVERY_SHA and peer['band_half_width'] == BAND, 'Official numerical protocol mismatch')
    require(peer['probability_tolerance'] == 2e-12 and peer['bce_tolerance'] == 1e-10, 'Official tolerance mismatch')
    require(0 <= peer['maximum_probability_error'] <= 2e-12 and 0 <= peer['independent_bce_error'] <= 1e-10, 'Official probability/BCE verification failed')
    compare_metrics(ours['canonical_metrics'], peer['canonical_metrics'], len(saved), 'Official canonical numerical metrics')
    require(set(peer['sensitivity']) == set(CASES.values()), 'Official sensitivity case set differs')
    for own_key, peer_key in CASES.items():
        scenario = peer['sensitivity'][peer_key]
        require(set(scenario) == {'n', 'confusion', 'macro_f1', 'accuracy'} and scenario['n'] == len(saved), 'Invalid sensitivity metric scope')
        for key, value in ours['canonical_band_sensitivity'][own_key].items():
            require(scenario[key] == value, 'Official canonical sensitivity differs: ' + peer_key + '/' + key)
    id_index = {int(v): i for i, v in enumerate(pop['ids'])}
    reference_class = saved >= .5
    reference_class = reference_class.copy()
    records = peer['disagreements']; seen = set()
    for row in records:
        rid = row['record_id']; require(rid in id_index and rid not in seen, 'Official discrepancy record identity invalid'); seen.add(rid); i = id_index[rid]
        for field, key in [('original_depth', 'depth'), ('hash_route', 'hash_route'), ('kmeans_route', 'kmeans_route'), ('label', 'y')]:
            require(row[field] == int(pop[key][i]), 'Official discrepancy record metadata differs')
        p, q = row['canonical_probability'], row['reference_probability']
        require(p == float(saved[i]) and np.isfinite(q) and abs(p - .5) <= BAND and abs(q - .5) <= BAND, 'Official disagreement outside BOTH32eps band')
        require(row['canonical_class'] == int(p >= .5) and row['reference_class'] == int(q >= .5)
                and row['canonical_class'] != row['reference_class'], 'Official discrepancy class values invalid')
        require(abs(p - q) <= peer['maximum_probability_error'], 'Official maximum error understates listed discrepancy')
        reference_class[i] = q >= .5
    reconstructed = class_metrics(pop['y'], reference_class)
    for key, value in reconstructed.items(): require(peer['raw_reference_metrics'][key] == value, 'Official raw reference classification mismatch')
    close(abs(peer['raw_reference_metrics']['bce'] - peer['canonical_metrics']['bce']), peer['independent_bce_error'], 'Official BCE error identity', 1e-15)
    for key in ('bce', 'macro_f1', 'accuracy'):
        close(peer['raw_reference_minus_canonical'][key], peer['raw_reference_metrics'][key] - peer['canonical_metrics'][key], 'Official raw difference', 1e-15)

    def count_check(counts, mask):
        n = int(mask.sum()); canonical_near = int(np.sum(mask & (abs(saved - .5) <= BAND)))
        disagreements = int(np.sum(mask & ((saved >= .5) != reference_class)))
        require(counts['n'] == n and counts['canonical_near_band'] == canonical_near, 'Official canonical near-band count mismatch')
        require(counts['class_disagreements'] == disagreements and counts['outside_band_class_disagreements'] == 0
                and counts['exact_class_agreement'] == (disagreements == 0), 'Official discrepancy count mismatch')
        a, b, union = canonical_near, counts['reference_near_band'], counts['union_near_band']
        require(all(type(v) is int for v in (b, union)) and 0 <= b <= n and max(a, b) <= union <= min(n, a + b)
                and disagreements <= a + b - union, 'Official band count inclusion bounds fail')
    count_check(peer['counts'], np.ones(len(saved), dtype=bool))
    require(set(peer['by_original_depth']) == {'1', '2', '3', '4'}, 'Official numerical depth inventory mismatch')
    for d in range(1, 5): count_check(peer['by_original_depth'][str(d)], pop['depth'] == d)
    for kind in ('hash', 'kmeans'):
        require(set(peer['by_route'][kind]) == {'0', '1', '2', '3', '4'}, 'Official numerical route inventory mismatch')
        for k in range(5): count_check(peer['by_route'][kind][str(k)], pop[kind + '_route'] == k)
    for slice_rows in [peer['by_original_depth'], *peer['by_route'].values()]:
        for key in ('n', 'canonical_near_band', 'reference_near_band', 'union_near_band', 'class_disagreements', 'outside_band_class_disagreements'):
            require(sum(r[key] for r in slice_rows.values()) == peer['counts'][key], 'Official slice totals mismatch')
    require(len(records) == peer['counts']['class_disagreements'], 'Official discrepancy row count mismatch')
    return {'status': 'PASS', 'canonical_sensitivities_exact': True,
            'official_reference_class_disagreements': len(records),
            'independent_reference_class_disagreements': ours['counts']['classification_disagreements'],
            'scope': 'Different matrix implementations can have different near-threshold classes. Canonical diagnostics are exact; author raw classification reconstructed from its disclosed disagreement records.'}


def compare_summary(peer, endpoints, methods, seeds):
    require(peer['protocol_sha256'] == RECOVERY_SHA and peer['band_half_width'] == BAND, 'Numerical summary protocol mismatch')
    for key, value in peer['totals_over_checkpoint_record_pairs'].items():
        require(value == sum(r['official_numerical_verification']['counts'][key] for r in endpoints), 'Official numerical totals differ')
    exact = all(r['official_numerical_verification']['counts']['exact_class_agreement'] for r in endpoints)
    require(peer['exact_class_agreement'] == exact, 'Official summary exact-class flag mismatch')
    for key, count_key in [('endpoints_with_disagreements', 'class_disagreements'), ('endpoints_with_canonical_ambiguity', 'canonical_near_band')]:
        expected = {(r['seed'], r['method']) for r in endpoints if r['official_numerical_verification']['counts'][count_key]}
        require(len(peer[key]) == len(expected) and {(r['seed'], r['method']) for r in peer[key]} == expected, 'Official flagged endpoint set mismatch')
    require(set(peer['methods']) == set(methods), 'Official numerical method inventory mismatch')
    checks = 0
    for method in methods:
        rows = [next(r for r in endpoints if r['method'] == method and r['seed'] == s) for s in seeds]
        entry = peer['methods'][method]
        require(entry['per_seed_counts'] == [{'seed': r['seed'], **r['official_numerical_verification']['counts']} for r in rows], 'Official per-seed counts mismatch')
        for own_case, official_case in CASES.items():
            for metric in ('macro_f1', 'accuracy'):
                own = seed_statistics([r['numerical_verification']['canonical_band_sensitivity'][own_case][metric] for r in rows])
                other = entry['sensitivity'][official_case][metric]
                require(other['n_training_seeds'] == 5 and other['degrees_of_freedom'] == 4 and other['confidence'] == .95, 'Sensitivity seed unit mismatch')
                for key in ('values', 'mean', 'sample_sd'): close(own[key], other[key], 'Numerical sensitivity aggregate/' + key)
                close(own['t95'], other['t_interval'], 'Numerical sensitivity descriptive t interval'); checks += 1
        for metric in ('bce', 'macro_f1', 'accuracy'):
            own = seed_statistics([r['official_numerical_verification']['raw_reference_minus_canonical'][metric] for r in rows])
            other = entry['raw_reference_minus_canonical'][metric]
            require(other['n_training_seeds'] == 5 and other['degrees_of_freedom'] == 4 and other['confidence'] == .95, 'Raw difference seed unit mismatch')
            for key in ('values', 'mean', 'sample_sd'): close(own[key], other[key], 'Official raw difference aggregate/' + key)
            close(own['t95'], other['t_interval'], 'Official raw difference descriptive interval'); checks += 1
    return {'status': 'PASS', 'method_scenario_or_difference_aggregates_checked': checks,
            'scope': 'Sensitivity scenarios remain numerical diagnostics, not alternative model performance or the registered uncertainty analysis.'}
