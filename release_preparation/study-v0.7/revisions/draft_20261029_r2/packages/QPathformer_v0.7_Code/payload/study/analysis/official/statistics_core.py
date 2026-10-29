"""Registered population-unit analysis, separated from model evaluation and I/O."""
from __future__ import annotations
import math
import numpy as np
from scipy.stats import t

FAMILIES = ("checkerboard", "spiral", "annulus", "disks")
ARMS = ("ScalarK", "MultiK", "MultiHash", "TrigK", "TrigHash", "TrigG25", "TrigG121", "MLPG129")
CONTRASTS = (("MultiK", "ScalarK"), ("MultiK", "MultiHash"), ("MultiK", "TrigK"),
             ("TrigK", "TrigHash"), ("TrigK", "TrigG121"))
SEEDS = (1401, 1402)


def checked_index(records):
    index = {}
    for row in records:
        key = (row["family"], row["population"], int(row["seed"]), row["arm"])
        if key in index:
            raise ValueError("Duplicate result identity")
        if row["family"] not in FAMILIES or row["arm"] not in ARMS or int(row["seed"]) not in SEEDS:
            raise ValueError("Unexpected result identity")
        index[key] = row
    if len(index) != 512:
        raise ValueError("All 512 confirmation results required; no complete-case inference")
    for family in FAMILIES:
        populations = sorted({key[1] for key in index if key[0] == family})
        if len(populations) != 8:
            raise ValueError("Exactly eight independent populations per family required")
        for population in populations:
            for seed in SEEDS:
                for arm in ARMS:
                    if (family, population, seed, arm) not in index:
                        raise ValueError("Incomplete paired population block")
    return index


def describe(values):
    values = np.asarray(values, dtype=np.float64)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("Finite nonempty values required")
    return {"n": len(values), "mean": float(values.mean()),
            "sample_sd": float(values.std(ddof=1)) if len(values) > 1 else None,
            "minimum": float(values.min()), "maximum": float(values.max()),
            "median": float(np.median(values)), "values": values.tolist()}


def primary(records):
    index = checked_index(records)
    confidence = 1-.05/20
    critical = float(t.ppf((1+confidence)/2, 7))
    contrasts = []
    for family in FAMILIES:
        populations = sorted({key[1] for key in index if key[0] == family})
        for first, second in CONTRASTS:
            blocks = []
            for population in populations:
                diffs = [index[family, population, seed, first]["test"]["bce"] -
                         index[family, population, seed, second]["test"]["bce"] for seed in SEEDS]
                if not np.isfinite(diffs).all():
                    raise ValueError("Nonfinite primary outcome")
                blocks.append({"population": population, "seed_ids": list(SEEDS),
                               "paired_seed_differences": diffs, "mean_difference": float(np.mean(diffs))})
            differences = np.asarray([b["mean_difference"] for b in blocks])
            mean, sd = float(differences.mean()), float(differences.std(ddof=1))
            se = sd/math.sqrt(8)
            low, high = mean-critical*se, mean+critical*se
            contrasts.append({"family": family, "first": first, "second": second,
                              "metric": "common_clipped_bce", "population_blocks": blocks,
                              "n_independent_populations": 8, "paired_seeds_per_population": 2,
                              "mean_difference": mean, "population_difference_sd": sd,
                              "standard_error": se, "degrees_of_freedom": 7,
                              "nominal_confidence": confidence, "t_critical": critical,
                              "interval": [low, high], "negative_favors": first,
                              "supports_first_direction": high < 0,
                              "supports_first_practical_reference": high < -.01,
                              "supports_second_direction": low > 0,
                              "supports_second_practical_reference": low > .01,
                              "crosses_zero_inconclusive_not_equivalence": low <= 0 <= high})
    return {"family_size": 20, "alpha_family": .05, "contrasts": contrasts,
            "scope": "Separate task families. Two paired seed differences averaged within each of eight populations. Nominal Bonferroni t intervals assume independent approximately normal population differences; small-sample assumptions unverified. No equivalence claim."}


def descriptive(records):
    index = checked_index(records)
    output = []
    metrics = ("bce", "native_bce", "macro_f1", "accuracy", "brier", "ece10",
               "positive_precision", "positive_recall", "grouped_tie_average_precision")
    for family in FAMILIES:
        populations = sorted({key[1] for key in index if key[0] == family})
        for arm in ARMS:
            rows = [index[family, pop, seed, arm] for pop in populations for seed in SEEDS]
            summary = {"family": family, "arm": arm, "metrics": {}, "validation_milestones": {}}
            for metric in metrics:
                means, undefined = [], []
                for pop in populations:
                    vals = [index[family, pop, seed, arm]["test"].get(metric) for seed in SEEDS]
                    if any(value is None for value in vals):
                        undefined.append(pop)
                    else:
                        means.append(float(np.mean(vals)))
                summary["metrics"][metric] = {"population_means": describe(means) if means else None,
                                               "undefined_population_ids": undefined,
                                               "scope": "Descriptive seed averages; undefined ratios retained and never converted to zero."}
            for threshold in (".90", ".95", ".97"):
                key = str(float(threshold))
                reached = [r["validation_milestones"][key]["first_observed_updates"]
                           for r in rows if r["validation_milestones"][key]["reached"]]
                summary["validation_milestones"][key] = {
                    "total_endpoints": len(rows), "reached": len(reached), "right_censored": len(rows)-len(reached),
                    "censor_updates": 15000, "reached_only_median_updates": float(np.median(reached)) if reached else None,
                    "reached_updates": reached, "scope": "Descriptive across nested seeds; 97% is not an annulus expectation."}
            output.append(summary)
    return output


def diagnostic_summary(records):
    """Population variability of descriptive test slices; no added significance tests."""
    index = checked_index(records)
    output = []
    for family in FAMILIES:
        populations = sorted({key[1] for key in index if key[0] == family})
        for arm in ARMS:
            for kind in ("hash", "kmeans", "geometric_margin"):
                count = max(len(index[family, pop, seed, arm]["diagnostics"]["test"][kind])
                            for pop in populations for seed in SEEDS)
                for bin_id in range(count):
                    blocks = []
                    for pop in populations:
                        entries = [index[family, pop, seed, arm]["diagnostics"]["test"][kind] for seed in SEEDS]
                        if any(bin_id >= len(entry) for entry in entries):
                            blocks.append({"population": pop, "status": "BIN_ABSENT_AFTER_TRAIN_EDGE_COLLAPSE"})
                            continue
                        selected = [entry[bin_id] for entry in entries]
                        counts = [entry["n"] for entry in selected]
                        if counts[0] != counts[1]:
                            raise ValueError("Paired seeds have inconsistent diagnostic record slices")
                        if not counts[0]:
                            blocks.append({"population": pop, "status": "EMPTY_BIN", "n": 0})
                            continue
                        values = {metric: float(np.mean([entry["metrics"][metric] for entry in selected]))
                                  for metric in ("bce", "macro_f1", "positive_prevalence")}
                        blocks.append({"population": pop, "status": "OBSERVED", "n": counts[0], **values})
                    observed = [block for block in blocks if block["status"] == "OBSERVED"]
                    output.append({"family": family, "arm": arm, "slice_policy": kind, "bin": bin_id,
                                   "population_blocks": blocks,
                                   "population_mean_descriptions": {
                                       metric: describe([b[metric] for b in observed]) if observed else None
                                       for metric in ("bce", "macro_f1", "positive_prevalence")},
                                   "scope": "Descriptive population SD/range of paired seed means, not a primary interval or causal bank contrast. Router-specific banks and train-fitted quantile boundaries differ across populations; all missing/empty bins retained."})
    return output
