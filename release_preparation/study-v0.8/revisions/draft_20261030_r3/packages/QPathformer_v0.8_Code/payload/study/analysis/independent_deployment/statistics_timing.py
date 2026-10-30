"""Independent scalar timing calculations; no producer, model or outcome imports."""
from __future__ import annotations
import math
from statistics import median

CIRCUIT_ARMS = ("MultiK_U", "MultiK_P", "MultiHash_U", "MultiHash_P")
BATCHES = (1, 32, 1024)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def quantile(values, probability):
    """Linear/type-7 quantile, explicitly reconstructed without numpy.quantile."""
    values = sorted(values)
    require(bool(values) and 0 <= probability <= 1 and all(finite(v) for v in values),
            "Invalid linear quantile inputs")
    position = (len(values)-1)*probability
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi]-values[lo])*(position-lo)


def condition_statistics(values):
    require(len(values) == 15 and all(type(v) is int and v > 0 for v in values),
            "Exactly15 positive integer nanosecond observations required")
    return {"trials": 15, "median_ns": float(median(values)), "min_ns": min(values),
            "max_ns": max(values), "p10_ns": quantile(values, .1), "p90_ns": quantile(values, .9),
            "first5_median_ns": float(median(values[:5])), "last5_median_ns": float(median(values[-5:]))}


def matched_statistics(original, converted, construction):
    require(len(original) == len(converted) == 15 and
            all(finite(v) and v > 0 for v in original+converted) and
            finite(construction) and construction >= 0, "Invalid paired timing evidence")
    saving = float(median([left-right for left, right in zip(original, converted)]))
    return {"median_original_over_converted_trial_ratio":
                float(median([left/right for left, right in zip(original, converted)])),
            "ratio_of_median_latencies": float(median(original)/median(converted)),
            "median_matched_per_call_saving_ns": saving,
            "construction_ns_single_instrumented_measurement": construction,
            "construction_only_break_even_calls": float(construction/saving) if saving > 0 else None}


def same(actual, expected, name):
    if expected is None:
        require(actual is None, name+" must be null")
    else:
        require(finite(actual) and abs(actual-expected) <= max(1e-9, 2e-14*abs(expected)),
                name+" differs from independent calculation")


def ordered_jobs(jobs, populations):
    """Reconstruct registered ordering only; never import producer timing code."""
    import numpy as np
    families = sorted({p["family"] for p in populations})
    order = sorted(populations, key=lambda p: (p["population_index"], families.index(p["family"])))
    result = []
    for pop in order:
        rows = [j for j in jobs if j["population_id"] == pop["population_id"]]
        seed = int(pop["proposed_streams"]["deployment_order"]["uint128_decimal"])
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed)))
        arms = list(rng.permutation(sorted({j["arm"] for j in rows})))
        for training_seed in sorted({j["training_seed_id"] for j in rows}):
            by_arm = {j["arm"]: j for j in rows if j["training_seed_id"] == training_seed}
            require(len(by_arm) == len(arms), "Duplicate or missing model in timing block")
            result.extend(by_arm[arm] for arm in arms)
    require(len(result) == len(jobs) and len({j["run_id"] for j in result}) == len(jobs),
            "Timing order inventory differs")
    return result


def expected_trials(jobs, session):
    require(session in (1, 2, 3), "Unregistered session")
    sequence = 0
    for job in jobs:
        labels = ["original", "converted"] if job["arm"] in CIRCUIT_ARMS else ["original"]
        for batch in BATCHES:
            for trial in range(15):
                pair = list(labels)
                if len(pair) == 2 and (session+trial) % 2:
                    pair.reverse()
                for label in pair:
                    sequence += 1
                    yield sequence, job["run_id"], label, batch, trial


def distribution(values):
    require(values and all(finite(v) for v in values), "Finite nonempty distribution required")
    return {"count": len(values), "median": float(median(values)), "min": min(values),
            "max": max(values), "p10": quantile(values, .1), "p90": quantile(values, .9)}


def across_sessions(sessions, jobs):
    """Collapse technical sessions within models, seeds within independent populations."""
    require(len(sessions) == 3, "All three timing sessions required")
    by_job = {j["run_id"]: j for j in jobs}
    require(all(set(s["condition_values"]) == set(sessions[0]["condition_values"]) for s in sessions),
            "Different conditions across sessions")
    conditions, pairs, population_values, population_pairs = [], [], {}, {}
    for key in sessions[0]["condition_values"]:
        job, label, batch = key
        medians = [float(median(s["condition_values"][key])) for s in sessions]
        value = float(median(medians))
        row = {"job_id": job, "representation": label, "batch_size": batch,
               "session_median_latencies_ns": medians, "median_of_three_session_medians_ns": value,
               "session_max_over_min": max(medians)/min(medians)}
        conditions.append(row)
        meta = by_job[job]
        popkey = (meta["family"], meta["population_id"], meta["arm"], label, batch)
        population_values.setdefault(popkey, []).append(value)
    for key in sessions[0]["matched"]:
        job, batch = key
        records = [s["matched"][key] for s in sessions]
        metric_names = ("median_original_over_converted_trial_ratio", "ratio_of_median_latencies",
                        "median_matched_per_call_saving_ns")
        values = {name: float(median([r[name] for r in records])) for name in metric_names}
        pairs.append({"job_id": job, "batch_size": batch, **values,
                      "session_statistics": records,
                      "scope": "Median of three technical session summaries for this same model."})
        meta = by_job[job]
        population_pairs.setdefault((meta["family"], meta["population_id"], meta["arm"], batch), []).append(values)
    pops, grouped, pairpops, pairgroups = [], {}, [], {}
    for (family, population, arm, label, batch), values in population_values.items():
        require(len(values) == 2, "Exactly two training seeds per population required")
        value = math.fsum(values)/2
        pops.append({"family": family, "population_id": population, "arm": arm,
                     "representation": label, "batch_size": batch, "seed_mean_latency_ns": value})
        grouped.setdefault((family, arm, label, batch), []).append(value)
    for (family, population, arm, batch), records in population_pairs.items():
        require(len(records) == 2, "Exactly two paired-model seeds per population required")
        values = {name: math.fsum(r[name] for r in records)/2 for name in records[0]}
        pairpops.append({"family": family, "population_id": population, "arm": arm, "batch_size": batch, **values})
        for name, value in values.items():
            pairgroups.setdefault((family, arm, batch, name), []).append(value)
    for values in list(grouped.values())+list(pairgroups.values()):
        require(len(values) == 8, "Eight independent populations per family required")
    return {"condition_session_drift": conditions, "model_paired_session_summaries": pairs,
            "population_latency": pops, "population_pairing": pairpops,
            "family_latency_descriptive":
                [{"family": f, "arm": a, "representation": r, "batch_size": b, **distribution(v)}
                 for (f, a, r, b), v in grouped.items()],
            "family_pairing_descriptive":
                [{"family": f, "arm": a, "batch_size": b, "metric": m, **distribution(v)}
                 for (f, a, b, m), v in pairgroups.items()],
            "scope": "Technical trials collapse to condition medians; three sessions collapse within the same model; two training seeds average within each population. Descriptive distributions across eight populations per family, with no new hypothesis test or increased independent n."}
