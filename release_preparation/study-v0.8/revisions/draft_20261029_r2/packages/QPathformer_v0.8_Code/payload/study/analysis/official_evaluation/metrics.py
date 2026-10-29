"""Pure array metrics. No filesystem access, model fitting, or selection."""
from __future__ import annotations
import math
import numpy as np

CLIP = 1e-7


def checked(y, p, logits=None):
    y, p = np.asarray(y), np.asarray(p, dtype=np.float64)
    if y.ndim != 1 or y.shape != p.shape or not np.isin(y, [0, 1]).all():
        raise ValueError("Matching one-dimensional binary labels/probabilities required")
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Probabilities must be finite in [0,1]")
    if logits is not None:
        logits = np.asarray(logits, dtype=np.float64)
        if logits.shape != y.shape or not np.isfinite(logits).all():
            raise ValueError("Matching finite native logits required")
    return y, p, logits


def grouped_average_precision(y, p):
    """Threshold-at-group-end AP; ties form one threshold, never arbitrary order."""
    y, p, _ = checked(y, p)
    positives = int(y.sum())
    if not positives:
        return None
    order = np.argsort(-p, kind="stable")
    labels, scores = y[order], p[order]
    ends = np.r_[np.flatnonzero(scores[:-1] != scores[1:]), len(scores)-1]
    tp = np.cumsum(labels)[ends].astype(np.float64)
    increments = np.diff(np.r_[0., tp])
    return float(np.sum((increments/positives) * (tp/(ends+1))))


def wilson(successes, n, z=1.959963984540054):
    if not n:
        return None
    center = (successes/n + z*z/(2*n))/(1+z*z/n)
    radius = z*math.sqrt((successes/n)*(1-successes/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0., center-radius), min(1., center+radius)]


def score(y, p, logits=None):
    y, p, logits = checked(y, p, logits)
    n = len(y)
    if not n:
        return None
    q, predicted = np.clip(p, CLIP, 1-CLIP), p >= .5
    loss = -(y*np.log(q)+(1-y)*np.log1p(-q))
    tn = int(np.sum((y == 0) & ~predicted))
    fp = int(np.sum((y == 0) & predicted))
    fn = int(np.sum((y == 1) & ~predicted))
    tp = int(np.sum((y == 1) & predicted))
    f0 = 2*tn/(2*tn+fp+fn) if 2*tn+fp+fn else 0.
    f1 = 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.
    binned = np.minimum(np.searchsorted(np.linspace(0., 1., 11), p, side="right")-1, 9)
    reliability, ece = [], 0.
    for k in range(10):
        use = binned == k
        size = int(use.sum())
        mean_p, mean_y = (float(p[use].mean()), float(y[use].mean())) if size else (None, None)
        if size:
            ece += size/n*abs(mean_p-mean_y)
        reliability.append({"bin": k, "lower": k/10, "upper": (k+1)/10,
                            "upper_inclusive": k == 9, "n": size,
                            "mean_probability": mean_p, "positive_fraction": mean_y})
    sd = float(loss.std(ddof=1)) if n > 1 else None
    clipped = (p < CLIP) | (p > 1-CLIP)
    result = {"n": n, "negative_count": tn+fp, "positive_count": tp+fn,
              "positive_prevalence": (tp+fn)/n, "bce": float(loss.mean()),
              "bce_record_sd": sd, "bce_record_se": sd/math.sqrt(n) if sd is not None else None,
              "macro_f1": (f0+f1)/2, "accuracy": (tp+tn)/n,
              "class_f1": [f0, f1], "brier": float(np.mean((p-y)**2)),
              "ece10": float(ece), "reliability_bins": reliability,
              "positive_precision": tp/(tp+fp) if tp+fp else None,
              "positive_recall": tp/(tp+fn) if tp+fn else None,
              "grouped_tie_average_precision": grouped_average_precision(y, p),
              "confusion_tn_fp_fn_tp": [tn, fp, fn, tp],
              "positive_prevalence_wilson95": wilson(tp+fn, n),
              "probability_min": float(p.min()), "probability_max": float(p.max()),
              "clipped_count": int(clipped.sum()),
              "clipped_wrong_count": int(np.sum(clipped & (predicted != y))),
              "exact_zero_count": int(np.sum(p == 0)), "exact_one_count": int(np.sum(p == 1)),
              "descriptive_uncertainty_scope": "Record SD/SE and Wilson prevalence only; conditional on fitted model and fixed slice. No seed/population replication or primary inference."}
    if logits is not None:
        native = np.maximum(logits, 0)-y*logits+np.log1p(np.exp(-np.abs(logits)))
        result.update(native_bce=float(native.mean()), native_minus_clipped_bce=float(native.mean()-loss.mean()),
                      native_logit_min=float(logits.min()), native_logit_max=float(logits.max()),
                      absolute_logit_over20_count=int(np.sum(abs(logits) > 20)),
                      absolute_logit_over40_count=int(np.sum(abs(logits) > 40)))
    return result


def slices(y, p, logits, routes, margin, margin_count):
    """All five banks for both policies and all frozen geometric margin bins."""
    y, p, logits = checked(y, p, logits)
    result = {}
    for name, assignment, count in [("hash", routes["hash"], 5), ("kmeans", routes["kmeans"], 5),
                                    ("geometric_margin", margin, margin_count)]:
        assignment = np.asarray(assignment)
        if assignment.shape != y.shape or not np.isin(assignment, np.arange(count)).all():
            raise ValueError("Invalid diagnostic slice")
        result[name] = []
        for k in range(count):
            use = assignment == k
            result[name].append({"bin": k, "n": int(use.sum()),
                                 "metrics": score(y[use], p[use], None if logits is None else logits[use])})
    return result


def milestones(ledger, thresholds=(.90, .95, .97), horizon_updates=15000):
    """First observed validation crossing; never truncates training or reselects."""
    rounds = [int(row["round"]) for row in ledger]
    if rounds != list(range(1, len(ledger)+1)) or not ledger:
        raise ValueError("Complete contiguous validation ledger required")
    updates = [int(row["optimizer_updates"]) for row in ledger]
    if any(b <= a for a, b in zip(updates, updates[1:])) or updates[-1] != horizon_updates:
        raise ValueError("Invalid update horizon")
    out = {}
    for threshold in thresholds:
        hits = [row for row in ledger if row["validation"]["macro_f1"] >= threshold]
        first = hits[0] if hits else None
        out[str(threshold)] = {"reached": first is not None,
                              "first_observed_round": first["round"] if first else None,
                              "first_observed_updates": first["optimizer_updates"] if first else None,
                              "right_censored": first is None, "censor_updates": horizon_updates,
                              "resolution_updates": updates[0],
                              "scope": "Descriptive validation-only first crossing; no early stopping/reselection; nonreachers excluded only from reached-only median."}
    return out
