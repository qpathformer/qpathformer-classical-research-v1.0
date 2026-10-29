"""Independent v0.4 metrics and uncertainty; no official statistics imports.

Binary confusion cells are counted explicitly. Bootstrap metrics are computed
for every checkpoint before averaging. Student-t df4 quantiles use a closed-form
CDF and bisection, independently of the official SciPy implementation.
"""
import hashlib
import io
import math
import numpy as np

METRICS = ("bce", "macro_f1", "accuracy")
CLIP = 1e-7


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(y, p):
    y, p = np.asarray(y), np.asarray(p, dtype=np.float64)
    require(y.ndim == 1 and len(y) > 0 and p.shape == y.shape, "Aligned nonempty vectors required")
    require(np.isin(y, [0, 1]).all() and np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all(),
            "Binary labels and finite physical probabilities required")
    return y.astype(np.int64), p


def class_metrics(y, predicted):
    y, predicted = np.asarray(y), np.asarray(predicted)
    require(y.ndim == 1 and len(y) > 0 and predicted.shape == y.shape
            and np.isin(y, (0, 1)).all() and np.isin(predicted, (0, 1)).all(), "Invalid class vectors")
    cells = np.array([[np.count_nonzero((y == row) & (predicted == col)) for col in (0, 1)]
                      for row in (0, 1)], dtype=np.int64)
    f1 = []
    for label in (0, 1):
        denominator = int(cells[label, :].sum() + cells[:, label].sum())
        f1.append(2 * int(cells[label, label]) / denominator if denominator else 0.)
    return {"n": len(y), "confusion": cells.tolist(), "macro_f1": sum(f1) / 2,
            "accuracy": float(np.trace(cells) / len(y))}


def metrics(y, probabilities):
    y, p = validate(y, probabilities)
    result = class_metrics(y, p >= .5)
    bounded = np.minimum(1 - CLIP, np.maximum(CLIP, p))
    losses = [-math.log(float(q)) if label else -math.log1p(-float(q)) for label, q in zip(y, bounded)]
    result.update(bce=math.fsum(losses) / len(losses),
                  clipped=int(np.count_nonzero((p < CLIP) | (p > 1 - CLIP))))
    return result


def t_cdf_df4(value):
    z = float(value) / math.sqrt(float(value) ** 2 + 4)
    return .5 + .75 * z - .25 * z ** 3


def t_critical_df4(confidence):
    require(0 < confidence < 1, "Invalid confidence")
    target = (1 + confidence) / 2
    left, right = 0., 1.
    while t_cdf_df4(right) < target:
        right *= 2
    for _ in range(100):
        midpoint = (left + right) / 2
        if t_cdf_df4(midpoint) < target:
            left = midpoint
        else:
            right = midpoint
    return (left + right) / 2


def interval(values, confidence=.95):
    values = np.asarray(values, dtype=np.float64)
    require(values.shape == (5,) and np.isfinite(values).all(), "Exactly five finite paired values required")
    mean = math.fsum(values) / 5
    sd = math.sqrt(math.fsum((float(v) - mean) ** 2 for v in values) / 4)
    half = t_critical_df4(confidence) * sd / math.sqrt(5)
    return {"mean": mean, "sample_sd": sd, "n": 5, "confidence": confidence,
            "lower": mean - half, "upper": mean + half}


def regenerate_counts(records, replicates, seed):
    require(isinstance(records, int) and records > 0 and isinstance(replicates, int) and replicates > 0,
            "Positive integer resampling sizes required")
    require(np.__version__ == "2.5.4", "Exact bootstrap identity requires registered NumPy2.5.4")
    rng = np.random.Generator(np.random.PCG64(seed))
    raw = rng.multinomial(records, np.full(records, 1.0 / records), size=replicates)
    require(raw.max() <= np.iinfo(np.uint16).max, "Bootstrap count overflow")
    counts = raw.astype(np.uint16)
    require(np.all(counts.sum(axis=1) == records), "Bootstrap multiplicities do not sum to n")
    return counts


def npy_bytes(array):
    output = io.BytesIO()
    np.save(output, np.asarray(array), allow_pickle=False)
    return output.getvalue()


def count_identity(counts):
    return {"dtype": str(counts.dtype), "shape": list(counts.shape),
            "array_bytes_sha256": hashlib.sha256(counts.tobytes(order="C")).hexdigest(),
            "npy_sha256": hashlib.sha256(npy_bytes(counts)).hexdigest()}


def bootstrap_metrics(y, p, counts):
    """Return [replicate,method,metric], using all four confusion cells directly.

    Unlike the official all-method batch calculation, each method constructs
    five checkpoint-specific loss/confusion bases and evaluates them together.
    Counts are common to every checkpoint and method; F1 averages only after
    its nonlinear class calculation.
    """
    y, p, counts = np.asarray(y), np.asarray(p, dtype=np.float64), np.asarray(counts)
    require(y.ndim == 1 and len(y) > 0 and p.ndim == 3 and p.shape[0] == 5 and p.shape[2] == len(y), "Expected [5,method,record] probabilities")
    require(counts.ndim == 2 and len(counts) > 0 and counts.shape[1] == len(y) and counts.dtype.kind in "iu" and (counts >= 0).all()
            and np.all(counts.sum(axis=1) == len(y)), "Invalid count matrix")
    require(np.isin(y, (0, 1)).all() and np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all(), "Invalid bootstrap data")
    n, methods = len(y), p.shape[1]
    result = np.empty((len(counts), methods, 3), dtype=np.float64)
    multiplicities = counts.astype(np.float64)
    for method in range(methods):
        basis = []
        for seed in range(5):
            prediction = p[seed, method] >= .5
            bounded = np.minimum(1 - CLIP, np.maximum(CLIP, p[seed, method]))
            loss = np.where(y == 1, -np.log(bounded), -np.log1p(-bounded))
            basis.append(loss)
            for actual, predicted in ((0, 0), (0, 1), (1, 0), (1, 1)):
                basis.append(((y == actual) & (prediction == predicted)).astype(np.float64))
        totals = (multiplicities @ np.column_stack(basis)).reshape(len(counts), 5, 5)
        loss, tn, fp, fn, tp = [totals[:, :, index] for index in range(5)]
        d0, d1 = 2 * tn + fp + fn, 2 * tp + fp + fn
        score0 = np.divide(2 * tn, d0, out=np.zeros_like(tn), where=d0 > 0)
        score1 = np.divide(2 * tp, d1, out=np.zeros_like(tp), where=d1 > 0)
        result[:, method, 0] = (loss / n).mean(axis=1)
        result[:, method, 1] = ((score0 + score1) / 2).mean(axis=1)
        result[:, method, 2] = ((tn + tp) / n).mean(axis=1)
    return result


def summarise_population(population, y, p, protocol):
    """Return independent summary, deterministic counts and bootstrap values."""
    methods, seeds = protocol["methods"], protocol["training_seeds"]
    p = np.asarray(p, dtype=np.float64)
    require(population in protocol["population_order"] and len(methods) == 9
            and seeds == [801, 802, 803, 804, 805], "Unregistered identity/order")
    require(p.shape == (5, 9, len(y)), "Complete five-seed nine-method population required")
    require(protocol["primary_family_size"] == 9, "Primary family must include all nine comparisons")
    observations = np.empty((5, 9, 3), dtype=np.float64)
    for seed in range(5):
        for method in range(9):
            measurement = metrics(y, p[seed, method])
            observations[seed, method] = [measurement[name] for name in METRICS]
    config = protocol["record_bootstrap"]
    counts = regenerate_counts(len(y), config["replicates"], config["seeds"][population])
    boot = bootstrap_metrics(y, p, counts)
    aggregate = {}
    for method_index, method in enumerate(methods):
        aggregate[method] = {}
        for metric_index, metric in enumerate(METRICS):
            values = observations[:, method_index, metric_index]
            stats = interval(values)
            aggregate[method][metric] = {"mean": stats["mean"], "sample_sd": stats["sample_sd"],
                                          "seed_values": values.tolist()}
    specifications = []
    for first, second in protocol["primary_contrasts"]:
        specifications.append((first + " minus " + second, [[first, 1], [second, -1]], True))
    for first, second in protocol["secondary_contrasts"]:
        specifications.append((first + " minus " + second, [[first, 1], [second, -1]], False))
    for specification in protocol["secondary_interactions"]:
        specifications.append((specification["name"], specification["terms"], False))
    require(len(specifications) == 17 and len({name for name, _, _ in specifications}) == 17,
            "Expected17 unique registered contrasts/interactions")
    comparisons = []
    for name, terms, primary in specifications:
        item = {"name": name, "terms": terms, "primary": primary, "metrics": {}}
        for index, metric in enumerate(METRICS):
            scale = 1. if metric == "bce" else 100.
            # Stack and sum terms rather than sharing official contrast code.
            seed_values = np.stack([observations[:, methods.index(method), index] * weight
                                    for method, weight in terms]).sum(axis=0) * scale
            boot_values = np.stack([boot[:, methods.index(method), index] * weight
                                    for method, weight in terms]).sum(axis=0) * scale
            measure = {"units": "natural_log_loss" if metric == "bce" else "percentage_points",
                       "seed_values": seed_values.tolist(), "seed_interval95": interval(seed_values),
                       "record_interval95": np.quantile(boot_values, [.025, .975], method="linear").tolist()}
            if primary and metric == "bce":
                alpha = .05 / 9
                measure["seed_interval_adjusted"] = interval(seed_values, 1 - alpha)
                measure["record_interval_adjusted"] = np.quantile(boot_values, [alpha / 2, 1 - alpha / 2], method="linear").tolist()
                measure["practical_magnitude"] = .01
            item["metrics"][metric] = measure
        comparisons.append(item)
    result = {"population": population, "n": len(y), "seeds": seeds, "methods": methods,
              "bootstrap_replicates": len(counts), "bootstrap_counts_sha256": count_identity(counts)["npy_sha256"],
              "bootstrap_count_identity": count_identity(counts), "primary_family_size": 9,
              "aggregate": aggregate, "contrasts": comparisons,
              "t95_critical_df4": t_critical_df4(.95),
              "t_adjusted_critical_df4": t_critical_df4(1 - .05 / 9),
              "limits": {"seed": protocol["seed_uncertainty"]["limits"],
                         "record": protocol["record_bootstrap"]["limits"], "secondary": protocol["secondary_limits"]}}
    return result, counts, boot
