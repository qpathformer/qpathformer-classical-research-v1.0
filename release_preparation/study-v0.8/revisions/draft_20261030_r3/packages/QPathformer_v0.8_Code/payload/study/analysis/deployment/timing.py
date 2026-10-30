"""One root-authorized, fresh, exclusive v0.8 raw-input timing session."""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
import json
import os
from pathlib import Path
import sys
import time
import traceback
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_key] = "1"
sys.dont_write_bytecode = True
import support as s
gate = s.gate


def available_memory():
    """Read-only system availability, distinct from this process's resident set."""
    import ctypes
    from ctypes import wintypes
    gate.require(sys.platform == "win32", "Registered memory telemetry requires Windows")
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
            (key, ctypes.c_ulonglong) for key in
            ("total_physical", "available_physical", "total_pagefile", "available_pagefile",
             "total_virtual", "available_virtual", "available_extended_virtual")]
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MemoryStatus)]
    kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"sampled_utc": s.now(), "source": "Win32_GlobalMemoryStatusEx",
            "memory_load_percent": int(status.load),
            **{key + "_bytes": int(getattr(status, key)) for key in
               ("total_physical", "available_physical", "total_pagefile", "available_pagefile",
                "total_virtual", "available_virtual")},
            "scope": "System-wide instantaneous availability; not model memory or controlled OS load"}


def ordered_jobs(jobs, populations):
    """Interleaved task/population blocks with an outcome-independent arm permutation."""
    import numpy as np
    metadata = {p["population_id"]: p for p in populations}
    families = sorted({p["family"] for p in populations})
    population_order = sorted(populations, key=lambda p: (p["population_index"], families.index(p["family"])))
    result = []
    for population in population_order:
        rows = [j for j in jobs if j["population_id"] == population["population_id"]]
        stream = int(metadata[population["population_id"]]["proposed_streams"]["deployment_order"]["uint128_decimal"])
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(stream)))
        arms = list(rng.permutation(sorted({j["arm"] for j in rows})))
        for seed in sorted({j["training_seed_id"] for j in rows}):
            by_arm = {j["arm"]: j for j in rows if j["training_seed_id"] == seed}
            result.extend(by_arm[arm] for arm in arms)
    gate.require(len(result) == len(jobs) == 640 and len({j["run_id"] for j in result}) == 640,
                 "Timing block inventory mismatch")
    return result


def make_forward(model, policy, coefficients=None):
    import compiler
    import routers
    if coefficients is not None:
        def forward(x):
            route = None if model.routing == "global" else routers.route(x, policy, kind=model.routing)
            return compiler.predict_coefficients(x, coefficients, route)
    else:
        def forward(x):
            route = None if model.routing == "global" else routers.route(x, policy, kind=model.routing)
            return model.predict_with_logits(x, route)
    return forward


def component_probe(model, policy, x, coefficients=None):
    """Instrumented decomposition; never used as the primary latency measurement."""
    import numpy as np
    import circuits
    import routers
    from models import sigmoid, trig_features
    clock = time.perf_counter_ns
    start = clock()
    route = None if model.routing == "global" else routers.route(x, policy, kind=model.routing)
    costs = {"routing_ns": clock() - start, "feature_or_core_ns": 0, "head_ns": 0, "sigmoid_ns": 0}
    if coefficients is not None:
        start = clock()
        phi = trig_features(x, 5 if coefficients.shape[1] == 121 else 2)
        costs["feature_or_core_ns"] += clock() - start
        start = clock()
        r = np.zeros(len(x), dtype=np.int64) if route is None else route
        z = np.einsum("ni,ni->n", phi, coefficients[r])
        costs["head_ns"] += clock() - start
    else:
        z = np.empty(len(x))
        for ids, bank, sl in model.components(x, route):
            theta, f = model.parameters[sl], x[ids]
            start = clock()
            if model.quantum:
                features = circuits.moments(f, theta[:8].reshape(2, 2, 2), model.moment_count)
                weights, bias = theta[8:-1], theta[-1]
            else:
                raise RuntimeError("Learned Trig must use equally optimized coefficient kernel")
            costs["feature_or_core_ns"] += clock() - start
            start = clock()
            z[ids] = features @ weights + bias
            costs["head_ns"] += clock() - start
    start = clock()
    p = sigmoid(z)
    costs["sigmoid_ns"] = clock() - start
    return p, z, {**costs, "scope": "One instrumented call; counters perturb execution. Components do not sum to primary latency."}


def validate_session(authorization, session):
    gate.require(session in (1, 2, 3) and authorization.get("session") == session,
                 "Wrong registered timing session")
    gate.require(authorization.get("stage") == "timing" and
                 len(authorization.get("previous_session_commits", [])) == session - 1,
                 "Separate root timing release and all prior session bindings required")


def validate_independent_conversion(audit, conversion_binding):
    gate.require(audit.get("status") == "PASS" and audit.get("phase") == "conversion" and
                 audit.get("circuit_endpoints") == 256 and audit.get("representations_replayed") == 640 and
                 audit.get("learned_trig_exact_repacks") == 384 and audit.get("conversion_commit") == conversion_binding,
                 "Complete independently replayed conversion required before timing")


def process_key(identity):
    return int(identity["pid"]), identity["creation_token"]


def validate_prior_chain(prior_release,release,number):
    """Every fresh session must use the same full prerequisite evidence chain."""
    shared=("registration","evaluation_release","evaluation_commit","independent_score_replay_commit",
            "conversion_commit","independent_conversion_commit","independent_conversion_audit",
            "reproduction_commit","independent_reproduction_commit","independent_reproduction_audit")
    gate.require(all(prior_release[key]==release[key] for key in shared) and
                 prior_release["previous_session_commits"]==release["previous_session_commits"][:number-1],
                 "Prior timing readiness chain differs")


def run(root, authorization, output, session):
    root, output = Path(root).resolve(), Path(output).resolve()
    sys.path.insert(0, str(root / "execution"))
    sys.path.insert(0, str(root / "quantum"))
    import durable
    import resource_probe
    import process_identity
    with durable.timing_lease(root, authorization):
        verified = s.verify(root, authorization, output, "timing")
        release = verified["derived_release"]
        validate_session(release, session)
        import readiness_gates
        conversion_commit, conversion = readiness_gates.verify_conversion(root, release, verified)
        prior_records = []
        for number, item in enumerate(release["previous_session_commits"], 1):
            prior_commit, prior_output = s.committed_output(item, root, "qpath-v08-timing-commit-1")
            prior = gate.read(prior_output / "summary.json")
            gate.require(prior["session"] == number and prior["status"] == "PASS" and
                         prior_commit["registration"] == verified["registration_binding"] and
                         prior_commit["evaluation_commit"] == verified["evaluation_commit"],
                         "Prior timing session identity mismatch")
            prior_release = gate.read(gate.verify_binding(prior_commit["authorization"], root))
            s.validate_header(prior_release, "timing", prior_output)
            validate_session(prior_release, number)
            validate_prior_chain(prior_release,release,number)
            prior_records.append(prior)
        import numpy as np
        import compiler
        from fixtures import parity
        from producer import confirmation_inventory
        jobs, populations, _ = confirmation_inventory(gate.read(root / "governance/RUN_MATRIX.json"))
        jobs = ordered_jobs(jobs, populations)
        identity = process_identity.identity()
        gate.require(identity is not None, "Cannot record timing process creation identity")
        gate.require(all(process_key(p["process_identity"]) != process_key(identity) for p in prior_records), "Fresh timing process required")
        output.mkdir(parents=True, exist_ok=False)
        gate.write_new(output / "START.json", {"status": "RUNNING", "session": session, "started_utc": s.now(),
            "authorization": verified["authorization"], "registration": verified["registration_binding"],
            "conversion_commit": release["conversion_commit"], "environment": verified["environment"],
            "independent_conversion_audit": release["independent_conversion_audit"],
            "independent_conversion_commit": release["independent_conversion_commit"],
            "process_identity": identity, "clock": vars(time.get_clock_info("perf_counter")),
            "process_resources": s.process_resources("timing"),
            "available_memory": available_memory(),
            "isolation_scope": "Exclusive ETEL study lease plus managed scientific child checks; external OS scheduling remains uncontrolled"})
        wall, cpu = time.perf_counter(), time.process_time()
        try:
            seal = gate.read(root / "quantum/data/DATA_SEAL.json")
            cache, component_records, model_records, summaries, matched = {}, [], [], [], []
            memory_blocks = []
            timed_count = warmup_count = 0
            condition_values = defaultdict(list)
            with (output / "trials.csv").open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["sequence", "job_id", "representation", "batch_size",
                    "trial", "elapsed_ns", "probability_sum", "logit_sum", "measured_utc"])
                writer.writeheader()
                for job in jobs:
                    model, loading = s.load_model(job, verified, root)
                    if job["population_id"] not in cache:
                        memory_blocks.append({"population": job["population_id"], "next_job_id": job["run_id"],
                                              "available_memory": available_memory()})
                        pop, policy, data_binding = s.load_population(root, job["population_id"], "validation", seal)
                        order = np.argsort(pop["ids"], kind="stable")
                        cache[job["population_id"]] = pop["x"][order], pop["ids"][order], policy, data_binding
                    x, ids, policy, data_binding = cache[job["population_id"]]
                    transforms = {}
                    start = time.perf_counter_ns()
                    # Every selected v0.8 predictor has an exact table representation.
                    file = conversion / "endpoints" / job["run_id"] / "representation.npz"
                    expected = conversion_commit["files"][file.relative_to(conversion).as_posix()]
                    gate.require(gate.sha(file) == expected["sha256"], "Converted representation changed")
                    with np.load(file, allow_pickle=False) as data:
                        coefficients = data["coefficients"].copy()
                    transforms["converted" if model.quantum else "original"] = coefficients
                    representation_load_ns = time.perf_counter_ns() - start
                    labels = ["original", "converted"] if model.quantum else ["original"]
                    kernels = {label: make_forward(model, policy, transforms.get(label)) for label in labels}
                    model_records.append({"job_id": job["run_id"], "arm": job["arm"], "family": job["family"],
                        "population": job["population_id"], "seed": job["training_seed_id"], "load": loading,
                        "representation_file_hash_check_and_load_ns": representation_load_ns,
                        "data": data_binding, "representation_labels": labels,
                        "original_semantics": "Equally optimized same-checkpoint Trig table kernel" if model.family.startswith("trig") else "Native vectorized Model"})
                    for batch_size in (1, 32, 1024):
                        batch = x[:batch_size]
                        reference = model.predict_with_logits(
                            batch, None if model.routing == "global" else __import__("routers").route(batch, policy, kind=model.routing))
                        for label in labels:
                            pp, zz, costs = component_probe(model, policy, batch, transforms.get(label))
                            component_records.append({"job_id": job["run_id"], "representation": label,
                                "batch_size": batch_size, "costs": costs, "parity": parity(pp, zz, *reference)})
                        for trial in range(-2, 15):
                            pair = list(labels)
                            if len(pair) == 2 and (session + trial) % 2:
                                pair.reverse()
                            for label in pair:
                                start = time.perf_counter_ns()
                                p, z = kernels[label](batch)
                                elapsed = time.perf_counter_ns() - start
                                parity(p, z, *reference, ids[:batch_size])
                                if trial < 0:
                                    warmup_count += 1
                                    continue
                                timed_count += 1
                                condition_values[(job["run_id"], label, batch_size)].append(elapsed)
                                writer.writerow({"sequence": timed_count, "job_id": job["run_id"],
                                    "representation": label, "batch_size": batch_size, "trial": trial,
                                    "elapsed_ns": elapsed, "probability_sum": float(p.sum()),
                                    "logit_sum": float(z.sum()), "measured_utc": s.now()})
                    stream.flush()
                    os.fsync(stream.fileno())
            for (job_id, label, batch), values in condition_values.items():
                gate.require(len(values) == 15, "Missing timing trials")
                summaries.append({"job_id": job_id, "representation": label, "batch_size": batch,
                    "trials": 15, "median_ns": float(np.median(values)),
                    "min_ns": min(values), "max_ns": max(values), "p10_ns": float(np.quantile(values, .1)),
                    "p90_ns": float(np.quantile(values, .9)), "first5_median_ns": float(np.median(values[:5])),
                    "last5_median_ns": float(np.median(values[-5:]))})
            for job in jobs:
                if job["arm"] not in ("MultiK_U", "MultiK_P", "MultiHash_U", "MultiHash_P"):
                    continue
                construction = gate.read(conversion / "endpoints" / job["run_id"] / "conversion.json")["construction_ns"]
                for batch in (1, 32, 1024):
                    original = np.array(condition_values[(job["run_id"], "original", batch)], dtype=np.float64)
                    converted = np.array(condition_values[(job["run_id"], "converted", batch)], dtype=np.float64)
                    saving = float(np.median(original - converted))
                    matched.append({"job_id": job["run_id"], "batch_size": batch,
                        "median_original_over_converted_trial_ratio": float(np.median(original / converted)),
                        "ratio_of_median_latencies": float(np.median(original) / np.median(converted)),
                        "median_matched_per_call_saving_ns": saving,
                        "construction_ns_single_instrumented_measurement": construction,
                        "construction_only_break_even_calls": float(construction / saving) if saving > 0 else None,
                        "break_even_scope": "Construction only, warm resident parameters; not loading/route policy/storage or hardware cost"})
            gate.require([len(condition_values), timed_count, warmup_count, len(matched)] ==
                         [2688, 40320, 5376, 768], "Timing session coverage mismatch")
            gate.write_new(output / "conditions.json", summaries)
            gate.write_new(output / "components.json", component_records)
            gate.write_new(output / "models_and_loading.json", model_records)
            gate.write_new(output / "matched_ratios.json", matched)
            gate.write_new(output / "population_memory_snapshots.json", memory_blocks)
            after = resource_probe.inspect()
            gate.require(after == verified["environment"], "BLAS/runtime changed during timing")
            summary = {"status": "PASS", "session": session, "process_identity": identity,
                "conditions": 2688, "representations": 896, "selected_models": 640,
                "timed_trials": timed_count, "warmup_trials": warmup_count, "forward_calls_per_trial": 1,
                "finished_utc": s.now(), "elapsed_seconds": time.perf_counter() - wall,
                "process_cpu_seconds": time.process_time() - cpu, "environment_after": after,
                "process_resources": s.process_resources("timing"),
                "available_memory_after": available_memory(),
                "independent_n_scope": "Technical timing repeats and sessions do not increase model/population n",
                "cold_loading_scope": "Single instrumented loading samples; primary forward timings use resident model data",
                "hardware_used": False, "external_os_scheduling_controlled": False}
            s.finish(output, "timing", verified, summary)
            return summary
        except BaseException as error:
            gate.write_new(output / "FAILURE.json", {"status": "FAILED_PRESERVED", "session": session,
                "error": repr(error), "traceback": traceback.format_exc(), "utc": s.now(),
                "recovery": "Root must authorize a fresh isolated session attempt; preserve all partial timings"})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--session", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.authorization, args.output, args.session), allow_nan=False))
