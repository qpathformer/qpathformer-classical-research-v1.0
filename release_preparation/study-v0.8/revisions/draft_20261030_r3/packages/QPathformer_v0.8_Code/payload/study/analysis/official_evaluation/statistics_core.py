"""Registered population-unit analysis, separated from model evaluation and I/O."""
from __future__ import annotations
import math
import numpy as np
from scipy.stats import t

FAMILIES = ("checkerboard", "spiral", "annulus", "disks")
ARMS = tuple(base+"_"+policy for base in ("MultiK", "MultiHash", "TrigK", "TrigHash", "TrigG121")
             for policy in ("U", "P"))
CONTRASTS = (
    ("priority_MultiK", {"MultiK_P": 1, "MultiK_U": -1}),
    ("priority_TrigK", {"TrigK_P": 1, "TrigK_U": -1}),
    ("priority_route_interaction_Multi", {"MultiK_P": 1, "MultiK_U": -1, "MultiHash_P": -1, "MultiHash_U": 1}),
    ("priority_route_interaction_Trig", {"TrigK_P": 1, "TrigK_U": -1, "TrigHash_P": -1, "TrigHash_U": 1}),
    ("priority_MultiK_vs_TrigG121", {"MultiK_P": 1, "TrigG121_P": -1}),
)
SEEDS = (1601, 1602)


def checked_index(records):
    index = {}
    for row in records:
        key = (row["family"], row["population"], int(row["seed"]), row["arm"])
        if key in index:
            raise ValueError("Duplicate result identity")
        if row["family"] not in FAMILIES or row["arm"] not in ARMS or int(row["seed"]) not in SEEDS:
            raise ValueError("Unexpected result identity")
        index[key] = row
    if len(index) != 640:
        raise ValueError("All 640 confirmation results required; no complete-case inference")
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


def validate_protocol(protocol):
    registered = [{"name": name, "weights": weights} for name, weights in CONTRASTS]
    if protocol["primary_contrasts"] != registered or protocol["family_size"] != 20 or \
            protocol["alpha_family"] != .05 or protocol["nominal_per_contrast_confidence"] != .9975 or \
            protocol["confirmation_count"] != 640 or protocol["populations_per_family"] != 8 or \
            protocol["seeds_per_population"] != 2 or protocol["practical_reference_bce"] != .01:
        raise ValueError("Frozen analysis recipe differs from implemented registered family")


def primary(records):
    index = checked_index(records)
    confidence = 1-.05/20
    critical = float(t.ppf((1+confidence)/2, 7))
    contrasts = []
    for family in FAMILIES:
        populations = sorted({key[1] for key in index if key[0] == family})
        for name, weights in CONTRASTS:
            blocks = []
            for population in populations:
                components = [{arm: index[family, population, seed, arm]["test"]["bce"]
                               for arm in weights} for seed in SEEDS]
                diffs = [sum(weights[arm]*values[arm] for arm in weights) for values in components]
                if not np.isfinite(diffs).all():
                    raise ValueError("Nonfinite primary outcome")
                blocks.append({"population": population, "seed_ids": list(SEEDS),
                               "paired_seed_components": components, "paired_seed_differences": diffs,
                               "mean_difference": float(np.mean(diffs))})
            differences = np.asarray([b["mean_difference"] for b in blocks])
            mean, sd = float(differences.mean()), float(differences.std(ddof=1))
            se = sd/math.sqrt(8)
            low, high = mean-critical*se, mean+critical*se
            contrasts.append({"family": family, "contrast_name": name, "weights": weights,
                              "metric": "common_clipped_bce", "population_blocks": blocks,
                              "n_independent_populations": 8, "paired_seeds_per_population": 2,
                              "mean_difference": mean, "population_difference_sd": sd,
                              "standard_error": se, "degrees_of_freedom": 7,
                              "nominal_confidence": confidence, "t_critical": critical,
                              "interval": [low, high],
                              "negative_interpretation": (
                                  "More favorable priority effect under geometric routing; not by itself an absolute priority benefit."
                                  if "interaction" in name else
                                  "Lower common BCE for positive-weight arm than negative-weight arm."),
                              "supports_negative_direction": high < 0,
                              "supports_negative_practical_reference": high < -.01,
                              "supports_positive_direction": low > 0,
                              "supports_positive_practical_reference": low > .01,
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


def priority_summary(records):
    """Descriptive eight-population summaries, including the secondary global effect."""
    index = checked_index(records)
    summaries, effects = [], []
    fields = ("mean_post_warmup_effective_records", "mean_unique_records_per_round",
              "flipped_training_record_fraction", "flipped_label_draw_fraction",
              "noise_draw_fraction_minus_record_fraction", "maximum_record_total_visits")
    for family in FAMILIES:
        populations = sorted({key[1] for key in index if key[0] == family})
        for arm in ARMS:
            blocks = []
            for population in populations:
                rows = [index[family, population, seed, arm] for seed in SEEDS]
                curves = []
                for round_number in (25, 50, 100, 200):
                    selected = [row["learning_curve"][round_number-1] for row in rows]
                    if any(entry["round"] != round_number or entry["optimizer_updates"] != round_number*75
                           for entry in selected):
                        raise ValueError("Incomplete registered training/validation curve")
                    curves.append({"round": round_number, "optimizer_updates": round_number*75,
                                   "full_training": {metric: float(np.mean([r["full_training"][metric] for r in selected]))
                                                     for metric in ("bce", "macro_f1", "accuracy")},
                                   "validation": {metric: float(np.mean([r["validation"][metric] for r in selected]))
                                                  for metric in ("bce", "macro_f1", "accuracy")},
                                   "full_training_native_bce": float(np.mean([r["full_training_native"]["native_bce"] for r in selected])),
                                   "validation_native_bce": float(np.mean([r["validation_native"]["native_bce"] for r in selected]))})
                blocks.append({"population": population, "paired_seed_ids": list(SEEDS),
                               "exposure": {field: float(np.mean([r["priority"][field] for r in rows])) for field in fields},
                               "fixed_learning_milestones": curves})
            summaries.append({"family": family, "arm": arm, "population_blocks": blocks,
                              "population_mean_descriptions": {
                                  field: describe([block["exposure"][field] for block in blocks]) for field in fields}})
        for base in ("MultiK", "MultiHash", "TrigK", "TrigHash", "TrigG121"):
            blocks = [{"population": pop, "seed_ids": list(SEEDS),
                       "paired_seed_differences": [
                           index[family, pop, seed, base+"_P"]["test"]["bce"]-
                           index[family, pop, seed, base+"_U"]["test"]["bce"] for seed in SEEDS]}
                      for pop in populations]
            for block in blocks:
                block["mean_difference"] = float(np.mean(block["paired_seed_differences"]))
            effects.append({"family": family, "base_model": base, "difference": "P minus U common clipped BCE",
                            "population_blocks": blocks,
                            "description": describe([b["mean_difference"] for b in blocks]),
                            "scope": "Descriptive; no extra interval, multiplicity family, selection or independent n."})
    return {"exposure_and_learning": summaries, "all_base_priority_effects_descriptive": effects,
            "scope": "Two seeds averaged within each of eight populations separately by task. Latent flip flags accessed only after root release. All models retained; no test learning curves or retrospective reselection."}
