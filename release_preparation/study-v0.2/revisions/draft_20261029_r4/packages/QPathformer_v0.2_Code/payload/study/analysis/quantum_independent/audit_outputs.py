"""Independently recompute released quantum statistics; never run a model.

Reads the completed evaluator's raw probabilities and the released test IDs,
labels and depth. No study Python modules are imported, no GPU or network is
used, and no training/evaluation source or result is modified.
"""
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
Q = ROOT / "quantum"
E = Q / "confirmation_evaluation"
OWN = Path(__file__).resolve().parent
SEEDS = list(range(401, 406))
METHODS = ["scheduled", "fixed4", "untied_assigned", "untied_balanced", "untied_all_records", "mlp129", "mlp17", "mlp41"]
KEYS = ["bce", "macro_f1", "accuracy"]
CONTRASTS = {"selected_minus_scheduled": ("untied_assigned", "scheduled"),
             "selected_minus_fixed4": ("untied_assigned", "fixed4"),
             "selected_minus_mlp129": ("untied_assigned", "mlp129"),
             "balanced_minus_assigned": ("untied_balanced", "untied_assigned"),
             "all_records_minus_balanced": ("untied_all_records", "untied_balanced")}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def equal(actual, expected, where, tolerance=2e-11):
    if isinstance(expected, dict):
        for key, value in expected.items():
            equal(actual[key], value, where+"/"+key, tolerance)
    elif isinstance(expected, (list, tuple)):
        check(len(actual) == len(expected), where+" length")
        for i, (a, b) in enumerate(zip(actual, expected)):
            equal(a, b, where+f"/{i}", tolerance)
    elif isinstance(expected, (float, np.floating)):
        check(math.isfinite(actual) and math.isfinite(expected)
              and abs(actual-expected) <= tolerance*max(1, abs(expected)), where+f": {actual} != {expected}")
    else:
        check(actual == expected, where+f": {actual} != {expected}")


def stamp(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def t4_critical():
    # Independent inversion of exact df4 CDF: F(t)=1/2+3u/4-u^3/4,
    # where u=t/sqrt(t^2+4). Avoid copying the evaluator's t constant.
    lo, hi = 0., 1.
    for _ in range(70):
        u = (lo+hi)/2
        if .5+.75*u-.25*u**3 < .975:
            lo = u
        else:
            hi = u
    u = (lo+hi)/2
    return 2*u/math.sqrt(1-u*u)


def describe(values):
    a = np.array(values, dtype=np.float64)
    check(a.shape == (5,) and np.isfinite(a).all(), "Five finite training-seed values required")
    mean, sd = float(a.mean()), float(a.std(ddof=1))
    half = t4_critical()*sd/math.sqrt(5)
    return {"n_training_seeds": 5, "mean": mean, "sample_sd": sd,
            "descriptive_t95_interval": [mean-half, mean+half], "values_seed_401_to_405": a.tolist()}


def moments(values):
    a = np.array(values, dtype=np.float64)
    return {"n": len(a), "mean": float(a.mean()), "sample_sd": float(a.std(ddof=1)),
            "minimum": float(a.min()), "maximum": float(a.max()), "sum": float(a.sum())}


def measured(y, probabilities):
    p = np.asarray(probabilities, dtype=np.float64)
    check(p.shape == y.shape and np.isfinite(p).all() and np.all((p >= 0) & (p <= 1)), "Invalid probabilities")
    prediction = (p >= .5).astype(np.int64)
    confusion = np.bincount(2*y+prediction, minlength=4).reshape(2, 2)
    denominator = confusion.sum(0)+confusion.sum(1)
    f1 = np.divide(2*confusion.diagonal(), denominator, out=np.zeros(2), where=denominator != 0)
    q = np.clip(p, 1e-7, 1-1e-7)
    return {"bce": float(np.where(y == 1, -np.log(q), -np.log1p(-q)).mean()),
            "macro_f1": float(f1.mean()), "accuracy": float(np.mean(prediction == y)),
            "confusion": confusion.tolist(), "n": len(y)}


def weighted_scores(y, predictions, weights):
    # Distinct implementation: weighted confusion matrices, one for each seed.
    matrices = np.stack([np.bincount(2*y+p, weights=weights, minlength=4).reshape(2, 2) for p in predictions])
    denominator = matrices.sum(1)+matrices.sum(2)
    diagonal = np.diagonal(matrices, axis1=1, axis2=2)
    scores = np.divide(2*diagonal, denominator, out=np.zeros_like(diagonal), where=denominator != 0)
    return float(scores.mean()), float(diagonal.sum(axis=1).mean()/weights.sum())


def manifest_check(folder):
    entries = read(folder / "manifest.json")["files"]
    for name, expected in entries.items():
        path = (folder / name).resolve()
        check(path.is_relative_to(folder.resolve()), "Manifest containment")
        check(sha(path) == expected, "Manifest hash: "+str(path))
    return entries


def main():
    started = time.perf_counter()
    out = OWN / "QUANTUM_OUTPUTS_INDEPENDENT_REVIEW.json"
    check(not out.exists() and not (OWN / "ACCESS_EVENT.json").exists(), "Preserve earlier audit attempt")
    release, lock, freeze = [read(Q/name) for name in ["EVALUATION_RELEASE.json", "CONFIRMATION_ENDPOINT_LOCK.json", "STAGE_B_FREEZE.json"]]
    access, summary = read(E / "TEST_ACCESS_EVENT.json"), read(E / "summary.json")
    report_path = Q / "report_data" / "quantum_report_data.json"
    report = read(report_path)
    stage = read(Q / "stage_B" / "stage_status.json")
    original_numpy = read(Q / "local_readiness_results" / "configuration.json")["versions"]["numpy"]
    check(np.__version__ == original_numpy, "Exact binomial replay requires the recorded quantum NumPy version; use its existing environment")
    check(release["review_status"] == "approved_by_root" and release["registered_endpoints"] == 40, "Root release")
    check(sha(Q / "EVALUATION_RELEASE.json") == "628d77666b01717bdcbf61d8cff2052aa4862d0721169be60ee30ef2726dcce1", "Root-authorized release identity")
    check(sha(Q / "STAGE_B_FREEZE.json") == release["stage_b_freeze_sha256"] == "edcdb0b04f3c7676277ad9fd5f20695ca4792cc1b527530161ca42b95ca0b4c5", "Freeze binding")
    check(sha(ROOT / "governance" / "ANALYSIS_PROTOCOL.json") == summary["root_analysis_protocol_sha256"]
          == "9b409934d07e8eb7a6380a02fe93780cab3323401d595c846da1b2ce7ba1e414", "Registered analysis")
    check(sha(Q / "evaluate_confirmation.py") == release["evaluator_sha256"] == summary["evaluator_sha256"]
          == "e9d40495cacc5b1196c8c83cd86729a2279c5c68fb0ed0ec40b50a2ef4c69cd2", "Frozen evaluator source")
    check(sha(Q / "summarize_quantum.py") == report["report_source_sha256"]
          == freeze["additional_reporting_sources_sha256"]["summarize_quantum.py"], "Frozen summarizer source")
    check(lock["status"] == "pass" and sha(Q / "CONFIRMATION_ENDPOINT_LOCK.json") == release["endpoint_lock_sha256"]
          == access["endpoint_lock_sha256"] == summary["endpoint_lock_sha256"], "Endpoint lock binding")
    check(summary["status"] == "complete" and summary["training_seeds"] == SEEDS and summary["methods"] == METHODS, "Completed all-model evaluation")
    check(summary["release_sha256"] == access["release_sha256"] == sha(Q / "EVALUATION_RELEASE.json")
          and access["release_id"] == release["release_id"], "Release/access binding")
    check(report["confirmation_summary_sha256"] == sha(E / "summary.json"), "Report summary binding")
    chronology = {"freeze_approved": freeze["approved_utc"], "training_completed": stage["finished_utc"],
                  "endpoint_lock": lock["created_utc"], "release": release["created_utc"], "test_access": access["utc"],
                  "evaluation_completed": summary["created_utc"], "report_created": report["created_utc"]}
    dates = [stamp(v) for v in chronology.values()]
    check(all(a <= b for a, b in zip(dates, dates[1:])), "Release/access chronology")
    check(stage["status"] == "completed" and len(stage["exits"]) == 5
          and {r["seed"] for r in stage["exits"]} == set(SEEDS) and all(r["exit_code"] == 0 for r in stage["exits"]), "Completed process set")
    check(not (E / "failure.json").exists(), "Evaluation failure artifact exists")
    identities = {(seed, method) for seed in SEEDS for method in METHODS}
    check(len(summary["per_seed"]) == 40 and {(r["seed"], r["method"]) for r in summary["per_seed"]} == identities, "Exact40 predictions")
    check(len(lock["endpoints"]) == 40 and {(r["seed"], r["method"]) for r in lock["endpoints"]} == identities, "Exact40 locked endpoints")
    manifest_files = manifest_check(E)
    manifest_check(Q / "report_data")
    required = {f"seed_{seed}_{method}_predictions.csv" for seed, method in identities}
    required |= {f"seed_{seed}_selected_probability_level_shots.npz" for seed in SEEDS}
    required |= {"summary.json", "TEST_ACCESS_EVENT.json", "conditional_primary_record_bootstrap.npz"}
    check(required <= set(manifest_files), "All evaluator artifacts covered")
    with (OWN / "ACCESS_EVENT.json").open("x", encoding="utf-8") as handle:
        json.dump({"utc": datetime.now(timezone.utc).isoformat(), "release_sha256": sha(Q / "EVALUATION_RELEASE.json"),
                   "event": "Independent released-output metric audit begins; no model evaluation or training", "script_sha256": sha(__file__)}, handle, indent=2)
    seal = read(Q / "data" / "DATA_SEAL.json")
    test_path = Q / "data" / "confirmation_SEALED_test.npz"
    check(sha(Q / "data" / "DATA_SEAL.json") == summary["data_seal_sha256"] == freeze["data_seal_sha256"], "Test seal identity")
    check(sha(test_path) == seal["files"][test_path.name]["sha256"], "Released test bytes")
    with np.load(test_path, allow_pickle=False) as archive:
        ids, y, depths = archive["ids"].copy(), archive["y"].copy(), archive["depth"].copy()
    check(len(ids) == len(set(ids)) == len(y) == summary["test_records"] == 1600, "Unique fixed1600 test identities")
    check(set(y) <= {0, 1} and set(depths) <= {1, 2, 3, 4}, "Label/depth domains")
    probabilities, recalculated, runs = {}, {}, {}
    max_probability_replay_error = 0.
    for seed, method in sorted(identities):
        with (E / f"seed_{seed}_{method}_predictions.csv").open(newline="", encoding="utf-8") as handle:
            saved = list(csv.DictReader(handle))
        np.testing.assert_array_equal([int(r["record_id"]) for r in saved], ids)
        np.testing.assert_array_equal([int(r["label"]) for r in saved], y)
        np.testing.assert_array_equal([int(r["original_depth"]) for r in saved], depths)
        p = np.array([float(r["probability"]) for r in saved])
        np.testing.assert_array_equal([int(r["prediction"]) for r in saved], (p >= .5).astype(int))
        probabilities[(seed, method)] = p
        recalculated[(seed, method)] = measured(y, p)
        record = next(r for r in summary["per_seed"] if (r["seed"], r["method"]) == (seed, method))
        equal(record["metrics"], recalculated[(seed, method)], f"metrics/{seed}/{method}")
        audit = next(r for r in lock["endpoints"] if (r["seed"], r["method"]) == (seed, method))
        folder = Q / "stage_B" / f"seed_{seed}" / method
        run = read(folder / "result.json")
        runs[(seed, method)] = run
        check(sha(folder / "result.json") == audit["result_sha256"] and sha(folder / "ledger.jsonl") == audit["ledger_sha256"], "Locked result/ledger identity")
        check(sha(folder / "selected_checkpoint.npz") == record["selected_checkpoint_sha256"] == audit["checkpoint_sha256"], "Prediction checkpoint provenance")
        check(0 <= record["probability_replay_max_error"] <= 1e-10, "Pre-reviewed evaluator scalar replay bound")
        max_probability_replay_error = max(max_probability_replay_error, record["probability_replay_max_error"])
        equal(record["training_work"], run["work"], "Training work reporting")
        equal(record["training_seconds"], run["training_seconds"], "Training time reporting")
        visits = 3840000 if method in ["untied_balanced", "untied_all_records"] else 960000
        check(run["work"]["training_record_visits"] == visits and run["optimizer_global_updates"] == 15000, "Registered exposure/global optimizer count")
        if method.startswith("mlp"):
            check(run["work"]["training_circuit_examples"] == run["work"]["training_layer_applications"] == 0, "MLP circuit accounting")
        else:
            exposure = run["executed_depth_training_record_visits"]
            check(sum(exposure) == visits, "Executed-depth record visits")
            check(run["work"]["training_circuit_examples"] == sum(n*(1+8*d) for d, n in enumerate(exposure, 1)), "Parameter-shift circuit-example count")
            check(run["work"]["training_layer_applications"] == sum(n*d*(1+8*d) for d, n in enumerate(exposure, 1)), "Parameter-shift layer count")
            equal(run["layer_training_record_exposure"], [sum(exposure[i:]) for i in range(4)], "Per-layer exposure")
    aggregates = {m: {key: describe([recalculated[(seed, m)][key] for seed in SEEDS]) for key in KEYS} for m in METHODS}
    equal(summary["aggregate"], aggregates, "All aggregate means/SD/t95")
    contrasts = {name: {key: describe([recalculated[(seed, a)][key]-recalculated[(seed, b)][key] for seed in SEEDS])
                        for key in KEYS} for name, (a, b) in CONTRASTS.items()}
    equal(summary["paired_contrasts"], contrasts, "All paired contrasts")
    check(summary["practical_BCE_reduction_0_01_met"] == (contrasts["selected_minus_scheduled"]["bce"]["mean"] <= -.01), "Practical threshold")
    candidate = np.stack([probabilities[(seed, "untied_assigned")] for seed in SEEDS])
    baseline = np.stack([probabilities[(seed, "scheduled")] for seed in SEEDS])
    loss = lambda p: np.where(y[None, :] == 1, -np.log(np.clip(p, 1e-7, 1-1e-7)), -np.log1p(-np.clip(p, 1e-7, 1-1e-7)))
    record_loss_difference = (loss(candidate)-loss(baseline)).mean(axis=0)
    rng = np.random.Generator(np.random.PCG64(88003))
    bootstrap = np.zeros((2000, 3))
    for i in range(2000):
        sample = rng.integers(0, 1600, size=1600)
        weights = np.bincount(sample, minlength=1600)
        cf, ca = weighted_scores(y, (candidate >= .5).astype(int), weights)
        bf, ba = weighted_scores(y, (baseline >= .5).astype(int), weights)
        bootstrap[i] = [float(weights @ record_loss_difference / 1600), cf-bf, ca-ba]
    with np.load(E / "conditional_primary_record_bootstrap.npz", allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive["record_ids"], ids)
        for index, key in enumerate(KEYS):
            np.testing.assert_allclose(archive[key], bootstrap[:, index], rtol=0, atol=2e-12)
    interval = np.quantile(bootstrap, [.025, .975], axis=0)
    equal(summary["primary_conditional_record_bootstrap"], {"seed": 88003, "replicates": 2000,
          "percentile95_interval": interval[:, 0].tolist(), "secondary_macro_f1_interval": interval[:, 1].tolist(),
          "secondary_accuracy_interval": interval[:, 2].tolist()}, "Conditional paired record bootstrap")
    shot_metrics = {}
    check(len(summary["raw_nested_readouts"]) == 50, "All50 nested readout replicates")
    for seed in SEEDS:
        with np.load(E / f"seed_{seed}_selected_probability_level_shots.npz", allow_pickle=False) as archive:
            np.testing.assert_array_equal(archive["record_ids"], ids)
            for budget in [1024, 4096]:
                for measurement_seed in range(701, 706):
                    counts = archive[f"shots_{budget}_seed_{measurement_seed}"]
                    nested_rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, measurement_seed, budget])))
                    np.testing.assert_array_equal(counts, nested_rng.binomial(budget, probabilities[(seed, "untied_assigned")]))
                    value = measured(y, counts/budget)
                    shot_metrics[(seed, budget, measurement_seed)] = value
                    row = next(r for r in summary["raw_nested_readouts"] if (r["training_seed"], r["shots_per_record"], r["shot_seed"]) == (seed, budget, measurement_seed))
                    equal(row["metrics"], value, "Raw nested measurement metrics")
    nested = {str(budget): {key: describe([float(np.mean([shot_metrics[(seed, budget, m)][key] for m in range(701, 706)]))
                                         for seed in SEEDS]) for key in KEYS} for budget in [1024, 4096]}
    equal(summary["nested_probability_level_readouts"], nested, "Nested means retain n5 training seeds")
    check(summary["represented_bernoulli_trials"] == 204800000 and summary["physical_shots"] == summary["hardware_jobs"] == 0, "Readout/hardware accounting")
    equal(report["primary_paired_contrast"], contrasts["selected_minus_scheduled"], "Report primary")
    equal(report["all_paired_contrasts"], contrasts, "Report contrasts")
    equal(report["conditional_bootstrap"], summary["primary_conditional_record_bootstrap"], "Report bootstrap")
    equal(report["nested_ideal_probability_readouts"], nested, "Report nested readouts")
    check(len(report["confirmation_methods"]) == 8 and [r["method"] for r in report["confirmation_methods"]] == METHODS, "Report methods")
    for method in METHODS:
        values = [runs[(seed, method)] for seed in SEEDS]
        row = next(r for r in report["confirmation_methods"] if r["method"] == method)
        check(row["parameter_count"] == values[0]["parameter_count"] == {"scheduled": 16, "fixed4": 16, "untied_assigned": 40,
              "untied_balanced": 40, "untied_all_records": 40, "mlp129": 129, "mlp17": 17, "mlp41": 41}[method], "Allocated parameter count")
        equal(row["test_metrics"], aggregates[method], "Report metrics")
        for field, source in [("selected_validation_bce", lambda r: r["selected_validation"]["bce"]),
                              ("selected_round", lambda r: r["selected_round"]),
                              ("charged_training_loop_seconds", lambda r: r["training_seconds"]),
                              ("total_run_seconds", lambda r: r["total_seconds"])]:
            equal(row[field], moments([source(r) for r in values]), "Report "+field)
        for key in values[0]["work"]:
            equal(row["work_per_run"][key], moments([r["work"][key] for r in values]), "Report work "+key)
        for field, source in [("layer_record_exposure_per_seed", "layer_training_record_exposure"), ("executed_depth_record_visits_per_seed", "executed_depth_training_record_visits")]:
            equal(row[field], [r[source] for r in values], "Report exposure")
        diagnostics = row["diagnostics"]
        for field, source in [("loss_by_original_depth", "losses"), ("raw_gradient_norm_by_original_depth", "gradient_norms")]:
            equal(diagnostics[field], [moments([r["diagnostics"][source][d] for r in values]) for d in range(4)], "Report gradient diagnostic moments")
        equal(diagnostics["clipped_probabilities_by_original_depth"], [[r["diagnostics"]["clipped_probabilities"][d] for r in values] for d in range(4)], "Report clipping counts")
        for i, item in enumerate(diagnostics["common_prefix_cosines"]):
            cosines = [r["diagnostics"]["common_prefix_cosines"][i]["cosine"] for r in values]
            defined = [c for c in cosines if c is not None]
            equal(item, {"values": cosines, "nonzero_gradient_seed_count": len(defined),
                         "mean_when_defined": float(np.mean(defined)) if defined else None,
                         "negative_count": sum(c < 0 for c in defined)}, "Report raw-gradient cosine summary")
        ledgers = [json.loads(line) for seed in SEEDS for line in (Q / "stage_B" / f"seed_{seed}" / method / "ledger.jsonl").read_text().splitlines()]
        equal(row["maximum_raw_batch_gradient_norm"], max(r["maximum_batch_gradient_norm"] for r in ledgers), "Report batch-gradient maximum")
        equal(row["mean_raw_batch_gradient_norm_across_all_rounds_seeds"], float(np.mean([r["mean_batch_gradient_norm"] for r in ledgers])), "Report batch-gradient mean")
    for stage_name in ["A", "B"]:
        status = read(Q / f"stage_{stage_name}" / "stage_status.json")
        results = [read(p) for p in sorted((Q / f"stage_{stage_name}").glob("seed_*/*/result.json"))]
        check(status["status"] == "completed", "Reported stage must be complete")
        equal(report["stage_training_wall_seconds"][stage_name], status["observed_wall_seconds"], "Stage wall time")
        equal(report["summed_charged_training_loop_seconds"][stage_name], float(np.sum([r["training_seconds"] for r in results])), "Summed loop time")
        check(report["registered_endpoint_counts"][stage_name] == len(results) == (27 if stage_name == "A" else 40), "Report endpoint counts")
    launch = read(Q / "stage_A" / "launch.json")
    equal(report["elapsed_A_launch_to_B_process_completion_seconds"], (stamp(stage["finished_utc"])-stamp(launch["started_utc"])).total_seconds(), "Total observed elapsed")
    check(report["preserved_training_failure_artifacts"] == [] and report["physical_shots"] == report["hardware_jobs"] == 0, "Report failure/hardware accounting")
    np.savez(OWN / "recomputed_primary_bootstrap.npz", values=bootstrap, metric_order=np.array(KEYS), record_ids=ids)
    result = {"status": "PASS", "review_kind": "Independent released-output statistics and provenance recomputation",
              "created_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": sha(__file__),
              "numpy_version": np.__version__, "python_executable": sys.executable,
              "release_sha256": sha(Q / "EVALUATION_RELEASE.json"), "endpoint_lock_sha256": sha(Q / "CONFIRMATION_ENDPOINT_LOCK.json"),
              "confirmation_summary_sha256": sha(E / "summary.json"), "report_data_sha256": sha(report_path),
              "evaluation_manifest_sha256": sha(E / "manifest.json"), "test_file_sha256": sha(test_path), "chronology": chronology,
              "registered_endpoint_count": 40, "verified_prediction_records": 64000, "unique_test_records": 1600,
              "registered_training_seeds": SEEDS, "test_label_counts": np.bincount(y, minlength=2).tolist(),
              "independently_inverted_df4_t975": t4_critical(), "aggregate": aggregates, "paired_contrasts": contrasts,
              "conditional_bootstrap": {"replicates": 2000, "seed": 88003, "metric_order": KEYS, "percentile95_intervals": interval.T.tolist()},
              "verified_nested_readout_replicates": 50, "nested_readout_rng_exact_match": True,
              "verified_report_resources_and_diagnostics": True,
              "evaluator_reported_scalar_prediction_replay_max_error": max_probability_replay_error,
              "duplicate_model_evaluation_performed": False, "gpu_used": False, "test_outcomes_accessed": True,
              "test_access_authorized_by_root_release": True, "hardware_jobs": 0, "seconds": time.perf_counter()-started,
              "limitations": ["No new model predictions were computed; the already reviewed evaluator's scalar/matrix checkpoint replay was checked through its bound results",
                              "The paired t interval describes variation across five training seeds on one fixed1600-record synthetic test set",
                              "The paired record bootstrap conditions on the trained checkpoints and does not include training/selection/new-dataset uncertainty",
                              "Five measurement repeats per budget are nested within each training checkpoint; they do not create25 independent training seeds",
                              "Resource counters and report arithmetic were checked; local concurrent wall times do not establish hardware-independent efficiency",
                              "Figure visual and caption review is recorded separately"]}
    with out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps({"status": "PASS", "output": str(out), "primary": contrasts["selected_minus_scheduled"],
                      "methods": {m: {k: aggregates[m][k]["mean"] for k in KEYS} for m in METHODS}}, indent=2))


if __name__ == "__main__":
    main()
