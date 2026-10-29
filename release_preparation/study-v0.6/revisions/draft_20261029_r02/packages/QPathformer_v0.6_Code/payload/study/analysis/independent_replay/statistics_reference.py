"""Independent v0.6 metrics and uncertainty; imports no official study helpers.

Confusion cells are counted explicitly. Resampled nonlinear F1 is calculated
within each checkpoint before the five-checkpoint mean. Student-t quantiles
use the closed-form df4 CDF and bisection rather than SciPy's implementation.
Calibration uses direct interval membership rather than bin-index arithmetic.
"""
import hashlib
import io
import math
import numpy as np

METRICS = ("bce", "macro_f1", "accuracy", "brier")
METHODS = ("qscalar_kmeans", "qmulti_kmeans", "mlp8tanh_kmeans", "trig_kmeans", "trig_global", "mlp_global")
POPULATIONS = ("confirmation_checkerboard", "confirmation_spiral", "confirmation_annulus", "confirmation_disks")
SEEDS = (1201, 1202, 1203, 1204, 1205)
BOOTSTRAP_SEEDS = dict(zip(POPULATIONS, (298601, 298602, 298603, 298604)))
PRIMARY = (("qmulti_kmeans", "qscalar_kmeans"), ("qscalar_kmeans", "trig_kmeans"),
           ("qmulti_kmeans", "trig_kmeans"), ("trig_kmeans", "trig_global"))
SECONDARY = (("qscalar_kmeans", "mlp8tanh_kmeans"), ("qmulti_kmeans", "mlp8tanh_kmeans"),
             ("qscalar_kmeans", "mlp_global"), ("qmulti_kmeans", "mlp_global"),
             ("mlp8tanh_kmeans", "mlp_global"), ("trig_global", "mlp_global"))
QUALITY = ("prevalence", "positive_precision", "positive_recall", "negative_recall", "average_precision")
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
                  brier=math.fsum((float(q) - int(label)) ** 2 for label, q in zip(y, p)) / len(y),
                  clipped=int(np.count_nonzero((p < CLIP) | (p > 1 - CLIP))))
    return result


def calibration(y, probabilities):
    """Ten fixed float64 linspace bins, direct [lo,hi) masks; last includes 1."""
    y, p = validate(y, probabilities)
    edges = np.linspace(0, 1, 11)
    bins, contributions, total = [], [], 0
    for k in range(10):
        membership = (p >= edges[k]) & ((p < edges[k + 1]) if k < 9 else (p <= edges[k + 1]))
        count = int(membership.sum())
        meanp = math.fsum(map(float, p[membership])) / count if count else None
        meany = int(y[membership].sum()) / count if count else None
        total += count
        if count:
            contributions.append(count / len(y) * abs(meanp - meany))
        bins.append({"lower": float(edges[k]), "upper": float(edges[k + 1]), "count": count,
                     "mean_probability": meanp, "positive_fraction": meany})
    require(total == len(y), "Calibration bins are not a partition")
    return {"ece": math.fsum(contributions), "bins": bins}


def class_quality(y, probabilities):
    """Fixed threshold metrics and tie-group AP, independently accumulated by score.

    All examples with the same floating score enter together. Each group's
    positive fraction increments recall, multiplied by precision after that
    entire group; this is noninterpolated AP, not trapezoidal PR area.
    """
    y, p = validate(y, probabilities)
    cells = class_metrics(y, p >= .5)["confusion"]
    tn, fp = cells[0]; fn, tp = cells[1]
    positives, negatives = tp + fn, tn + fp
    grouped = {}
    for label, score in zip(y, p):
        key = float(score)
        if key not in grouped: grouped[key] = [0, 0]
        grouped[key][0] += 1
        grouped[key][1] += int(label)
    terms, selected, selected_positive = [], 0, 0
    for score in sorted(grouped, reverse=True):
        size, positive = grouped[score]
        selected += size; selected_positive += positive
        if positives: terms.append((positive / positives) * (selected_positive / selected))
    return {"prevalence": positives / len(y),
            "positive_precision": tp / (tp + fp) if tp + fp else 0.,
            "positive_recall": tp / positives if positives else None,
            "negative_recall": tn / negatives if negatives else None,
            "average_precision": math.fsum(terms) if positives else None,
            "confusion": cells}


def native_logit_bce(y, logits):
    """Unbounded stable logistic loss; not the common clipped comparison loss."""
    y, z = np.asarray(y), np.asarray(logits, dtype=np.float64)
    require(y.ndim == 1 and len(y) and z.shape == y.shape and np.isin(y, (0, 1)).all()
            and np.isfinite(z).all(), "Finite aligned logits and binary labels required")
    losses = [max(float(value), 0.) - int(label) * float(value)
              + math.log1p(math.exp(-abs(float(value)))) for label, value in zip(y, z)]
    return math.fsum(losses) / len(losses)


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
    """Return [replicate,method,metric]; explicit four-cell checkpoint bases.

Each method builds its own five-checkpoint loss/Brier/confusion bases. The
F1 ratio is evaluated for each checkpoint and only then averaged. Record
multiplicities are common to every method and checkpoint in this population.
"""
    y, p, counts = np.asarray(y), np.asarray(p, dtype=np.float64), np.asarray(counts)
    require(y.ndim == 1 and len(y) > 0 and p.ndim == 3 and p.shape[0] == 5 and p.shape[2] == len(y)
            and p.shape[1] > 0, "Expected [5,method,record] probabilities")
    require(counts.ndim == 2 and len(counts) > 0 and counts.shape[1] == len(y) and counts.dtype.kind in "iu"
            and (counts >= 0).all() and np.all(counts.sum(axis=1) == len(y)), "Invalid count matrix")
    require(np.isin(y, (0, 1)).all() and np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all(), "Invalid bootstrap data")
    n, methods = len(y), p.shape[1]
    result = np.empty((len(counts), methods, len(METRICS)), dtype=np.float64)
    for method in range(methods):
        basis = []
        for seed in range(5):
            prediction = p[seed, method] >= .5
            bounded = np.minimum(1 - CLIP, np.maximum(CLIP, p[seed, method]))
            basis.extend([np.where(y == 1, -np.log(bounded), -np.log1p(-bounded)), (p[seed, method] - y) ** 2])
            for actual, predicted in ((0, 0), (0, 1), (1, 0), (1, 1)):
                basis.append(((y == actual) & (prediction == predicted)).astype(np.float64))
        basis = np.column_stack(basis)
        for start in range(0, len(counts), 256):
            stop = min(start + 256, len(counts))
            totals = (counts[start:stop].astype(np.float64) @ basis).reshape(stop - start, 5, 6)
            loss, squared_error, tn, fp, fn, tp = [totals[:, :, index] for index in range(6)]
            d0, d1 = 2 * tn + fp + fn, 2 * tp + fp + fn
            score0 = np.divide(2 * tn, d0, out=np.zeros_like(tn), where=d0 > 0)
            score1 = np.divide(2 * tp, d1, out=np.zeros_like(tp), where=d1 > 0)
            result[start:stop, method, 0] = (loss / n).mean(axis=1)
            result[start:stop, method, 1] = ((score0 + score1) / 2).mean(axis=1)
            result[start:stop, method, 2] = ((tn + tp) / n).mean(axis=1)
            result[start:stop, method, 3] = (squared_error / n).mean(axis=1)
    return result


def validate_protocol(protocol):
    require(protocol["study_id"] == "QPATH-GENERALIZATION-v0.6", "Unregistered study")
    require(tuple(protocol["methods"]) == METHODS and tuple(protocol["training_seeds"]) == SEEDS
            and tuple(protocol["population_order"]) == POPULATIONS, "Unregistered identity/order")
    require(tuple(map(tuple, protocol["primary_contrasts"])) == PRIMARY
            and tuple(map(tuple, protocol["secondary_contrasts"])) == SECONDARY, "Contrast set/order changed")
    require(protocol["primary_family_size"] == 16 and protocol["practical_difference"] == .01,
            "Primary family or practical difference changed")
    config = protocol["record_bootstrap"]
    require(config["replicates"] == 10000 and config["seeds"] == BOOTSTRAP_SEEDS
            and tuple(config["metrics"]) == METRICS, "Bootstrap contract changed")
    seed_config = protocol["seed_uncertainty"]
    require(seed_config["n"] == 5 and seed_config["df"] == 4 and seed_config["descriptive_confidence"] == .95
            and seed_config["primary_confidence"] == 1 - .05 / 16, "Seed uncertainty changed")


def summarise_population(population, y, p, protocol):
    """Return independent summary, deterministic counts and bootstrap values.

This mathematical helper has no file/data loader. Production callers must
verify the root release and completed official output commit before calling.
"""
    validate_protocol(protocol)
    methods, seeds = list(METHODS), list(SEEDS)
    p = np.asarray(p, dtype=np.float64)
    require(population in POPULATIONS and p.shape == (5, len(METHODS), len(y)), "Complete registered population required")
    observations = np.empty((5, len(METHODS), 4), dtype=np.float64)
    for seed in range(5):
        for method in range(len(METHODS)):
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
        calibration_rows = [calibration(y, p[index, method_index]) for index in range(5)]
        ece_stats = interval([row["ece"] for row in calibration_rows])
        aggregate[method]["calibration"] = {"seed_results": calibration_rows,
            "ece_mean": ece_stats["mean"], "ece_sample_sd": ece_stats["sample_sd"]}
        quality_rows = [class_quality(y, p[index, method_index]) for index in range(5)]
        descriptive = {}
        for key in QUALITY:
            values = [row[key] for row in quality_rows]
            stats = interval(values) if all(value is not None for value in values) else None
            descriptive[key] = None if stats is None else {"mean": stats["mean"], "sample_sd": stats["sample_sd"]}
        aggregate[method]["class_quality"] = {"seed_results": quality_rows, "descriptive": descriptive}
    comparisons = []
    for primary, pairs in ((True, PRIMARY), (False, SECONDARY)):
        for first, second in pairs:
            terms = [[first, 1], [second, -1]]
            item = {"name": first + " minus " + second, "terms": terms, "primary": primary, "metrics": {}}
            for index, metric in enumerate(METRICS):
                scale = 100. if metric in ("macro_f1", "accuracy") else 1.
                seed_values = np.stack([observations[:, methods.index(method), index] * weight
                                        for method, weight in terms]).sum(axis=0) * scale
                boot_values = np.stack([boot[:, methods.index(method), index] * weight
                                        for method, weight in terms]).sum(axis=0) * scale
                units = ("percentage_points" if scale == 100 else
                         "natural_log_loss" if metric == "bce" else "squared_probability_error")
                measure = {"units": units, "seed_values": seed_values.tolist(), "seed_interval95": interval(seed_values),
                           "record_interval95": np.quantile(boot_values, [.025, .975], method="linear").tolist()}
                if primary and metric == "bce":
                    alpha = .05 / 16
                    measure["seed_interval_adjusted"] = interval(seed_values, 1 - alpha)
                    measure["record_interval_adjusted"] = np.quantile(boot_values, [alpha / 2, 1 - alpha / 2], method="linear").tolist()
                    measure["practical_magnitude"] = .01
                item["metrics"][metric] = measure
            comparisons.append(item)
    identity = count_identity(counts)
    result = {"population": population, "n": len(y), "seeds": seeds, "methods": methods,
              "bootstrap_replicates": len(counts), "bootstrap_counts_sha256": identity["npy_sha256"],
              "bootstrap_count_identity": identity, "primary_family_size": 16,
              "aggregate": aggregate, "contrasts": comparisons,
              "t95_critical_df4": t_critical_df4(.95), "t_adjusted_critical_df4": t_critical_df4(1 - .05 / 16),
              "limits": {"seed": protocol["seed_uncertainty"]["limits"], "record": config["limits"],
                         "secondary": protocol["secondary_units"]}}
    return result, counts, boot
