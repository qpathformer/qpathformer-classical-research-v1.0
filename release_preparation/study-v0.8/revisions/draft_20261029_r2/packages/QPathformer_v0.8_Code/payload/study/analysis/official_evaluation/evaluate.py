"""Official v0.8 scoring. Requires root release and all 640 audited B endpoints."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import traceback

# Set before importing NumPy/SciPy/model code; never silently permit oversubscription.
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_key] = "1"
sys.dont_write_bytecode = True
from gate import read, sha, require, write_new, binding, current_sources, verify_release


def load_released_population(root, population, split, seal):
    """Only called after successful verify_release; no fallback to unsealed files."""
    import numpy as np
    import routers
    require(split in ("validation", "test"), "Only registered heldout splits")
    folder = Path(root)/"quantum/data"
    filename = f"{population}_{'SEALED_test' if split == 'test' else split}.npz"
    entry = seal["files"][filename]
    path = folder/filename
    require(sha(path) == entry["sha256"] and entry["dataset"] == population and entry["split"] == split,
            "Released population payload changed")
    policy_path = folder/f"{population}_router.json"
    require(sha(policy_path) == entry["router_policy_sha256"] == seal["routers"][population]["sha256"],
            "Released router changed")
    policy = read(policy_path)
    with np.load(path, allow_pickle=False) as data:
        pop = {name: data[name].copy() for name in
               ("x", "y", "ids", "source_draw_ids", "hash_route", "kmeans_route", "margin_bin")}
    require(pop["x"].shape == (1600, 2) and np.isfinite(pop["x"]).all(), "Heldout feature shape/finite check")
    require(pop["y"].shape == (1600,) and np.isin(pop["y"], [0, 1]).all(), "Heldout label shape check")
    require(len(set(pop["ids"].tolist())) == 1600, "Heldout IDs must be unique")
    route_seconds = {}
    for kind in ("hash", "kmeans"):
        start = time.perf_counter()
        routed = routers.route(pop["x"], policy, kind=kind)
        route_seconds[kind] = time.perf_counter()-start
        require(np.array_equal(routed, pop[kind+"_route"]), "Cached route differs from immutable policy")
    margin = routers.margin_bins(pop["x"], policy, policy["margin_bins"])
    require(np.array_equal(margin, pop["margin_bin"]), "Cached margin slices differ from frozen policy")
    return pop, policy, {"file": binding(path), "router": binding(policy_path),
                         "route_recompute_seconds": route_seconds,
                         "timing_scope": "One audit call per population/split, not a deployment latency benchmark."}


def evaluate(root, release_path, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    sys.path.insert(0, str(root/"execution"))
    import durable
    # Official scoring is numerical audit work and cannot overlap isolated timing.
    with durable.auxiliary_lease(root, "audit"):
        verified = verify_release(root, release_path, output)
        import numpy as np
        import scipy
        import resource_probe
        environment = resource_probe.inspect()
        expected_environment = read(verified["release"]["runtime_environment"]["path"])
        for key in ("python", "interpreter", "numpy_version", "openblas_dll_sha256",
                    "openblas_config", "effective_blas_threads", "gpu_used"):
            require(environment[key] == expected_environment[key], f"Numerical environment differs: {key}")
        require(environment["numpy_version"] == "2.5.4" and environment["effective_blas_threads"] == 1
                and scipy.__version__ == "1.18.1", "Registered numerical versions/thread count required")
        sys.path.insert(0, str(root/"quantum"))
        from models import Model, ARM_METHODS
        from metrics import score, slices, milestones
        from statistics_core import primary, descriptive, diagnostic_summary, priority_summary, validate_protocol
        from priority_diagnostics import load_released_training_diagnostics, endpoint_diagnostics
        validate_protocol(read(verified["release"]["analysis_protocol"]["path"]))
        seal = read(root/"quantum/data/DATA_SEAL.json")
        sources = current_sources(root)
        output.mkdir(parents=True, exist_ok=False)
        write_new(output/"EVALUATION_START.json", {
            "status": "RUNNING", "started_utc": datetime.now(timezone.utc).isoformat(),
            "release": verified["release_binding"], "environment": environment,
            "scipy": scipy.__version__, "sources": sources,
            "expected_endpoint_count": 640, "test_access_now_authorized": True})
        records, cache, training_cache = [], {}, {}
        start, cpu = time.perf_counter(), time.process_time()
        try:
            for job in verified["jobs"]:
                identity, population = job["run_id"], job["population_id"]
                commit_binding = verified["endpoint_commits"][identity]
                endpoint = Path(commit_binding["path"]).parent
                commit = read(commit_binding["path"])
                for filename in ("selected_checkpoint.npz", "result.json", "ledger.jsonl"):
                    require(sha(endpoint/filename) == commit["files"][filename]["sha256"],
                            "Consumed selected endpoint changed after release gate")
                result = read(endpoint/"result.json")
                require(result["job_id"] == identity and result["completed_rounds"] == 200
                        and result["optimizer_global_updates"] == 15000, "Invalid full selected endpoint")
                streams = {k: int(v["uint128_decimal"]) for k, v in job["paired_streams"].items()}
                model = Model(ARM_METHODS[job["arm"]], job["training_seed_id"], streams)
                with np.load(endpoint/"selected_checkpoint.npz", allow_pickle=False) as checkpoint:
                    parameters = checkpoint["parameters"].copy()
                    require(parameters.shape == model.parameters.shape and np.isfinite(parameters).all(),
                            "Invalid selected parameters")
                    require(int(checkpoint["current_round"]) == result["selected_round"], "Selected round mismatch")
                    model.parameters[:] = parameters
                    require(np.array_equal(checkpoint["core_parameters"], model.core_parameters),
                            "Unexpected frozen core payload")
                folder = output/"endpoints"/identity
                folder.mkdir(parents=True, exist_ok=False)
                row = {"job_id": identity, "family": job["family"], "population": population,
                       "seed": job["training_seed_id"], "arm": job["arm"],
                       "base_model": job["base_model"], "sampling_policy": job["sampling_policy"],
                       "selected_round": result["selected_round"], "endpoint_commit": commit_binding,
                       "selection_scope": "Prior full-validation BCE choice, never test selection",
                       "splits": {}, "diagnostics": {}}
                for split in ("validation", "test"):
                    if (population, split) not in cache:
                        cache[population, split] = load_released_population(root, population, split, seal)
                    pop, policy, data_evidence = cache[population, split]
                    p, z = model.predict_with_logits(pop["x"], model.route_for(pop))
                    require(z is not None and p.shape == z.shape == pop["y"].shape, "Native predictions missing")
                    if split == "validation":
                        with np.load(endpoint/"selected_checkpoint.npz", allow_pickle=False) as checkpoint:
                            require(np.array_equal(p, checkpoint["validation_probabilities"]) and
                                    np.array_equal(z, checkpoint["validation_logits"]),
                                    "Official selected validation replay differs")
                    with (folder/f"{split}_predictions.npz").open("xb") as stream:
                        np.savez(stream, record_ids=pop["ids"], source_draw_ids=pop["source_draw_ids"],
                                 labels=pop["y"], probabilities=p, native_logits=z,
                                 predictions=(p >= .5).astype(np.int8), hash_route=pop["hash_route"],
                                 kmeans_route=pop["kmeans_route"], margin_bin=pop["margin_bin"])
                    row[split] = score(pop["y"], p, z)
                    row["splits"][split] = data_evidence
                    row["diagnostics"][split] = slices(pop["y"], p, z,
                        {kind: pop[kind+"_route"] for kind in ("hash", "kmeans")},
                        pop["margin_bin"], policy["margin_bins"]["bins"])
                    row["diagnostics"][split]["geometric_margin_policy"] = policy["margin_bins"]
                ledger = [json.loads(line) for line in (endpoint/"ledger.jsonl").read_text(encoding="utf-8").splitlines()]
                require(len(ledger) == 200, "Complete 200-round milestone evidence required")
                row["validation_milestones"] = milestones(ledger)
                row["learning_curve"] = [{"round": entry["round"], "optimizer_updates": entry["optimizer_updates"],
                    "full_training": entry["full_training"], "full_training_native": entry["full_training_native"],
                    "validation": entry["validation"], "validation_native": entry["validation_native"]}
                    for entry in ledger]
                if population not in training_cache:
                    training_cache[population] = load_released_training_diagnostics(root, population, seal)
                row["priority"], priority_evidence = endpoint_diagnostics(
                    endpoint, commit, training_cache[population], ledger)
                with (folder/"training_priority_evidence.npz").open("xb") as stream:
                    np.savez(stream, **priority_evidence)
                mechanism_fields = ("bank_count", "parameters_per_bank", "parameter_count", "train_bank_counts",
                    "bank_training_record_visits", "bank_minibatch_appearances", "bank_absent_updates",
                    "bank_absent_parameter_movement_l2_sum", "bank_gradient_l2_sum",
                    "selected_coefficients_or_heads_by_bank", "selected_parameter_l2_norm_by_bank",
                    "training_seconds", "training_process_cpu_seconds",
                    "invocation_process_cpu_seconds_through_result", "work", "preparation", "sampling_diagnostics")
                row["training_mechanism_and_costs"] = {key: result[key] for key in mechanism_fields}
                row["training_mechanism_and_costs"]["scope"] = (
                    "Exposure/costs cover full horizon; coefficients describe validation-selected checkpoint. "
                    "Bank indices across policies do not denote matched semantic groups. Concurrent fit timers are not isolated latency.")
                write_new(folder/"metrics.json", row)
                records.append(row)
                with (output/"progress.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"completed": len(records), "job_id": identity,
                                             "metrics_sha256": sha(folder/"metrics.json")})+"\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            write_new(output/"primary_analysis.json", primary(records))
            write_new(output/"descriptive_summary.json", descriptive(records))
            write_new(output/"diagnostic_summary.json", diagnostic_summary(records))
            write_new(output/"priority_summary.json", priority_summary(records))
            # Compact index retains full metrics separately; never pools historical populations.
            write_new(output/"endpoint_index.json", [{"job_id": r["job_id"], "arm": r["arm"],
                "family": r["family"], "population": r["population"], "seed": r["seed"],
                "metrics": binding(output/"endpoints"/r["job_id"]/"metrics.json")} for r in records])
            require(current_sources(root) == sources, "Source drift during evaluation")
            require(sha(release_path) == verified["release_binding"]["sha256"], "Root release changed during evaluation")
            require(sha(root/"quantum/data/DATA_SEAL.json") == verified["release"]["data_seal"]["sha256"],
                    "Data seal changed during evaluation")
            summary = {"status": "PASS", "evaluated_endpoints": len(records),
                       "evaluated_test_records_with_model_multiplicity": 640*1600,
                       "unique_test_populations": 32, "independent_populations_per_family": 8,
                       "paired_seeds_per_population": 2, "primary_contrasts": 20,
                       "comparison_scope": {
                           "warmup": "Both U and P use ten uniform-with-replacement rounds before any priority updates.",
                           "uniform_control": "Current U samples uniformly with replacement for all rounds and pays the same full-training priority-refresh computation after warmup.",
                           "historical_v07": "v0.7 used shuffled passes. Current U is a fresh-task control with a changed sampling law; raw cross-version results cannot isolate a priority effect.",
                           "endpoint_audit_limit": "All saved gradients are applied by the separate Adam replay. Only twelve predeclared minibatch gradients per full endpoint, plus the selected full-data gradient, are independently recomputed.",
                           "inference_unit": "Eight independent populations per task; paired seeds, records and diagnostic bins add no independent n."},
                       "classification": "INTERNAL", "hardware_used": False,
                       "release": verified["release_binding"], "elapsed_seconds": time.perf_counter()-start,
                       "process_cpu_seconds": time.process_time()-cpu,
                       "process_resources": resource_probe.process_resources(),
                       "finished_utc": datetime.now(timezone.utc).isoformat(),
                       "independent_replay_status": "REQUIRED_SEPARATE_IMPLEMENTATION_NOT_YET_PERFORMED"}
            write_new(output/"summary.json", summary)
            files = {p.relative_to(output).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
                     for p in sorted(output.rglob("*")) if p.is_file()}
            write_new(output/"EVALUATION_COMMIT.json", {"schema": "qpath-v08-evaluation-commit-1",
                "status": "completed", "count": len(records), "release": verified["release_binding"], "files": files})
            return summary
        except BaseException as error:
            write_new(output/"EVALUATION_FAILURE.json", {
                "status": "FAILED_PRESERVED", "completed_endpoints": len(records),
                "error": repr(error), "traceback": traceback.format_exc(),
                "recovery": "Root must document a fresh full same-recipe evaluation attempt; no overwrites or selective exclusion.",
                "utc": datetime.now(timezone.utc).isoformat()})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.root, args.release, args.output), allow_nan=False))
