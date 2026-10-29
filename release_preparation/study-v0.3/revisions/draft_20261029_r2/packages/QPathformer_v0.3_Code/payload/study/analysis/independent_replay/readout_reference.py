"""Independent registered ideal finite-shot draws and nested summaries.

Counts represent ideal Bernoulli readout trials, not executions of Aer circuits
or IBM hardware. Measurement repeats are nested within five training seeds.
"""
import numpy as np
from matrix_reference import METHODS
from statistics_reference import METRICS, metrics, seed_statistics

READOUT_METHODS = ('encoding1', 'readout1', 'kmeans40')
TRAINING_SEEDS = (601, 602, 603, 604, 605)
MEASUREMENT_SEEDS = (801, 802, 803, 804, 805)
SHOT_BUDGETS = (1024, 4096)


def exact_counts(probabilities, training_seed, measurement_seed, shots, method):
    if np.__version__ != '2.5.4':
        raise RuntimeError('Exact registered binomial replay requires NumPy2.5.4')
    if (method not in READOUT_METHODS or training_seed not in TRAINING_SEEDS or
            measurement_seed not in MEASUREMENT_SEEDS or shots not in SHOT_BUDGETS):
        raise ValueError('Unregistered ideal-readout identity')
    p = np.asarray(probabilities, dtype=np.float64)
    if p.ndim != 1 or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError('Invalid ideal readout probabilities')
    sequence = np.random.SeedSequence([training_seed, measurement_seed, shots, METHODS.index(method)])
    return np.random.Generator(np.random.PCG64(sequence)).binomial(shots, p)


def nested_summary(labels, probabilities, counts):
    """probabilities keyed (method,training_seed), counts additionally(shots,measurement_seed)."""
    required = {(m, s, b, r) for m in READOUT_METHODS for s in TRAINING_SEEDS
                for b in SHOT_BUDGETS for r in MEASUREMENT_SEEDS}
    if set(counts) != required: raise ValueError('All150 nested count arrays are required')
    output = {'training_seeds': list(TRAINING_SEEDS), 'measurement_seeds': list(MEASUREMENT_SEEDS),
              'readout_methods': list(READOUT_METHODS), 'shot_budgets': list(SHOT_BUDGETS),
              'count_arrays': len(required), 'test_records': len(labels),
              'represented_bernoulli_trials': len(READOUT_METHODS) * len(TRAINING_SEEDS) *
                  len(MEASUREMENT_SEEDS) * len(labels) * sum(SHOT_BUDGETS),
              'scope': 'Ideal independent binomial sensitivity, no physical noise model; five measurement repeats nested within each of five trained checkpoints. Counts do not establish a noise benefit.',
              'aggregates': {}}
    for method in READOUT_METHODS:
        output['aggregates'][method] = {}
        for budget in SHOT_BUDGETS:
            rows = []
            deltas = []
            for seed in TRAINING_SEEDS:
                base = metrics(labels, probabilities[(method, seed)])
                per_seed = []
                for shotseed in MEASUREMENT_SEEDS:
                    values = np.asarray(counts[(method, seed, budget, shotseed)])
                    if values.shape != (len(labels),) or not np.issubdtype(values.dtype, np.integer) or np.any((values < 0) | (values > budget)):
                        raise ValueError('Invalid integer readout counts')
                    measured = metrics(labels, values / budget)
                    per_seed.append([measured[key] for key in METRICS])
                averaged = np.asarray(per_seed).mean(axis=0)
                rows.append(averaged)
                deltas.append(averaged - np.asarray([base[key] for key in METRICS]))
            rows, deltas = np.asarray(rows), np.asarray(deltas)
            output['aggregates'][method][str(budget)] = {
                key: {'checkpoint_measurement_mean': seed_statistics(rows[:, j]),
                      'measurement_mean_minus_ideal': seed_statistics(deltas[:, j])}
                for j, key in enumerate(METRICS)}
    return output
