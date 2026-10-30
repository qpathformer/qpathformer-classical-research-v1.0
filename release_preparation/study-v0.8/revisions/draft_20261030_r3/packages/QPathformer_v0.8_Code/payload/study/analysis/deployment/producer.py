"""Registered post-release circuit conversion; no finite-shot campaign."""
from __future__ import annotations
import argparse
from collections import Counter
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

CIRCUIT_ARMS = ("MultiK_U", "MultiK_P", "MultiHash_U", "MultiHash_P")
TRIG_ARMS = ("TrigK_U", "TrigK_P", "TrigHash_U", "TrigHash_P", "TrigG121_U", "TrigG121_P")


def confirmation_inventory(matrix):
    jobs = [j for j in matrix["runs"] if j["stage"] in ("B", "confirmation")]
    populations = [p for p in matrix["populations"] if p["stage"] in ("B", "confirmation")]
    gate.require(len(jobs) == 640 and len({j["run_id"] for j in jobs}) == 640, "640 unique B jobs required")
    gate.require(len(populations) == 32 and len({p["population_id"] for p in populations}) == 32,
                 "32 unique confirmation populations required")
    gate.require(set(Counter(p["family"] for p in populations).values()) == {8}, "Eight populations per family")
    gate.require(len(set(p["family"] for p in populations)) == 4, "Four families required")
    gate.require(set(j["population_id"] for j in jobs) == {p["population_id"] for p in populations},
                 "Run/population identities differ")
    circuits = [j for j in jobs if j["arm"] in CIRCUIT_ARMS]
    gate.require(len(circuits) == 256, "256 selected circuit predictors required")
    gate.require(Counter(j["arm"] for j in jobs) ==
                 Counter({a: 64 for a in (*CIRCUIT_ARMS, *TRIG_ARMS)}),
                 "Unexpected selected arm inventory")
    return jobs, populations, circuits


def registration(root):
    """Metadata only; does not inspect any data arrays or endpoint outcomes."""
    root = Path(root).resolve()
    jobs, populations, circuits = confirmation_inventory(gate.read(root / "governance/RUN_MATRIX.json"))
    return {"schema": "qpath-v08-deployment-registration-1", "created_utc": s.now(),
            "status": "PREPARED_FOR_ROOT_REVIEW", "test_access_authorized": False,
            "sources": s.sources(root),
            "deployment_protocol": gate.binding(root / "governance/DEPLOYMENT_PROTOCOL.json"),
            "readiness_protocol": gate.binding(root / "governance/LOCAL_READINESS_PROTOCOL.json"),
            "run_matrix": gate.binding(root / "governance/RUN_MATRIX.json"),
            "all_run_ids": [j["run_id"] for j in jobs],
            "circuit_run_ids": [j["run_id"] for j in circuits],
            "confirmation_populations": [p["population_id"] for p in populations],
            "fixtures": {"conversion_offgrid": "128 uniform[-1,1]^2 using population boundary_diagnostic stream",
                         "conversion_boundary": "All nonzero clipped Voronoi edge midpoints and +/-1e-10 normal offsets",
                         "forced_banks": "All five banks on every offgrid and geometric-boundary input"},
            "parity": {"probability_absolute_tolerance": 2e-12, "logit_absolute_tolerance": 1e-9,
                       "class_rule": "All differences preserved; require both probabilities within32float64eps of0.5"},
            "timing": {"sessions": [1, 2, 3], "batch_sizes": [1, 32, 1024],
                       "warmup_trials": 2, "timed_trials": 15, "forward_calls_per_trial": 1,
                       "fixture_selection": "First batch_size of ascending numeric validation IDs",
                       "blocks": "Interleave population_index then family then paired seed; arm order permuted by each population deployment_order stream",
                       "pair_order": "Original/converted alternate with session+trial parity, including warmups",
                       "baseline_representation": "Same checkpoint; shared feature kernel for learned Trig, vectorized native Model for other methods",
                       "component_probe": "Separate instrumented routing, feature/core, head and sigmoid; excluded from primary raw-input latency",
                       "latency_scope": "One complete raw-input forward call per trial; no input features or routes cached"},
            "conversion_scope": "No fit; five banks x25 real coefficients; 384 learned Trig tables repacked without fitting",
            "out_of_scope": "No new finite-shot/noise/Aer campaign, physical hardware or cloud"}


def canonical(verified, job, split):
    import numpy as np
    file = Path(verified["evaluation_output"]) / "endpoints" / job["run_id"] / f"{split}_predictions.npz"
    commit = gate.read(verified["evaluation_commit"]["path"])
    relative = file.relative_to(verified["evaluation_output"]).as_posix()
    gate.require(gate.sha(file) == commit["files"][relative]["sha256"], "Canonical prediction changed")
    with np.load(file, allow_pickle=False) as data:
        return {k: data[k].copy() for k in ("record_ids", "probabilities", "native_logits")}


def convert(root, output, verified):
    import numpy as np
    import compiler
    from fixtures import parity_inputs, parity
    import routers
    root, output = Path(root), Path(output)
    seal = gate.read(root / "quantum/data/DATA_SEAL.json")
    _, populations, _ = confirmation_inventory(gate.read(root / "governance/RUN_MATRIX.json"))
    pop_metadata = {p["population_id"]: p for p in populations}
    cache, records = {}, []
    for job in verified["jobs"]:
        if job["arm"] not in (*CIRCUIT_ARMS, *TRIG_ARMS):
            continue
        model, load_evidence = s.load_model(job, verified, root)
        folder = output / "endpoints" / job["run_id"]
        folder.mkdir(parents=True, exist_ok=False)
        start = time.perf_counter_ns()
        if job["arm"] in CIRCUIT_ARMS:
            coefficients, construction = compiler.compile_model(model.method, model.parameters, True)
            construction_ns = time.perf_counter_ns() - start
            arrays = {"coefficients": coefficients, "grid": compiler.GRID}
            for bank, evidence in enumerate(construction):
                arrays[f"bank{bank}_grid_moments"] = evidence["grid_moments"]
                arrays[f"bank{bank}_grid_logits"] = evidence["grid_logits"]
            transform = "exact_D2_logit_to_25_coefficient_table"
        else:
            coefficients = compiler.learned_trig_coefficients(model.method, model.parameters)
            construction_ns = time.perf_counter_ns() - start
            arrays, transform = {"coefficients": coefficients}, "same_trained_coefficients_shared_feature_kernel"
        s.npz_new(folder / "representation.npz", **arrays)
        record = {"job_id": job["run_id"], "arm": job["arm"], "family": job["family"],
                  "population": job["population_id"], "seed": job["training_seed_id"], "base_model": job["base_model"], "sampling_policy": job["sampling_policy"],
                  "transform": transform, "construction_ns": construction_ns,
                  "original_parameter_bytes": model.parameters.nbytes,
                  "coefficient_bytes": coefficients.nbytes,
                  "original_and_converted_total_parameter_bytes": model.parameters.nbytes + coefficients.nbytes,
                  "load": load_evidence, "parity": {},
                  "storage_scope": "Float64 parameter payload only; NPZ container/router/filesystem overhead reported separately",
                  "timing_scope": "Single instrumented transform, not isolated repeated latency"}
        for split in ("validation", "test"):
            key = job["population_id"], split
            if key not in cache:
                cache[key] = s.load_population(root, *key, seal)
            pop, policy, data_evidence = cache[key]
            original = canonical(verified, job, split)
            gate.require(np.array_equal(pop["ids"], original["record_ids"]), "Canonical record IDs differ")
            p, z = compiler.predict_coefficients(pop["x"], coefficients, model.route_for(pop))
            record["parity"][split] = parity(p, z, original["probabilities"], original["native_logits"], pop["ids"])
            record["parity"][split]["data_evidence"] = data_evidence
            s.npz_new(folder / f"{split}_parity.npz", record_ids=pop["ids"],
                      original_probability=original["probabilities"], original_logits=original["native_logits"],
                      transformed_probability=p, transformed_logits=z,
                      decision_disagreement=(p >= .5) != (original["probabilities"] >= .5))
        # All fixtures are population-derived and label free, independent of arm/seed outcomes.
        stream = pop_metadata[job["population_id"]]["proposed_streams"]["boundary_diagnostic"]["uint128_decimal"]
        offgrid, boundary, boundary_metadata = parity_inputs(policy, stream)
        fixture = np.concatenate((offgrid, boundary))
        r = None if model.routing == "global" else routers.route(fixture, policy, kind=model.routing)
        p, z = compiler.predict_coefficients(fixture, coefficients, r)
        rp, rz = model.predict_with_logits(fixture, r)
        record["parity"]["label_free_routed_fixtures"] = parity(p, z, rp, rz)
        record["boundary_metadata"] = boundary_metadata
        fixture_arrays = {"x": fixture, "offgrid_count": np.array(len(offgrid)), "original_probability": rp,
                          "original_logits": rz, "transformed_probability": p, "transformed_logits": z}
        if r is not None:
            fixture_arrays["route"] = r
            gate.require(np.array_equal(r, routers.route(fixture, policy, kind=model.routing)),
                         "Router nondeterminism")
            record["parity"]["forced_banks"] = []
            for bank in range(5):
                forced = np.full(len(fixture), bank, dtype=np.int64)
                p, z = compiler.predict_coefficients(fixture, coefficients, forced)
                rp, rz = model.predict_with_logits(fixture, forced)
                record["parity"]["forced_banks"].append({"bank": bank, **parity(p, z, rp, rz)})
                fixture_arrays.update({f"bank{bank}_original_probability": rp, f"bank{bank}_original_logits": rz,
                                       f"bank{bank}_transformed_probability": p, f"bank{bank}_transformed_logits": z})
        s.npz_new(folder / "fixture_parity.npz", **fixture_arrays)
        record["representation_file_bytes"] = (folder / "representation.npz").stat().st_size
        gate.write_new(folder / "conversion.json", record)
        records.append({"job_id": job["run_id"], "arm": job["arm"],
                        "record": gate.binding(folder / "conversion.json"),
                        "representation": gate.binding(folder / "representation.npz")})
    gate.require(len(records) == 640 and sum(r["arm"] in CIRCUIT_ARMS for r in records) == 256,
                 "Conversion inventory incomplete")
    gate.write_new(output / "endpoint_index.json", records)
    return {"status": "PASS", "circuit_conversions": 256, "learned_trig_same_checkpoint_transforms": 384,
            "transformed_representations": len(records), "all_validation_test_parity_retained": True,
            "independent_coefficient_replay": "REQUIRED_SEPARATE_IMPLEMENTATION",
            "no_accuracy_gain_claimed": True, "hardware_used": False}


def run(root, authorization, output, phase):
    gate.require(phase == "conversion", "Only conversion is registered in this producer")
    root, output = Path(root).resolve(), Path(output).resolve()
    sys.path.insert(0, str(root / "execution"))
    sys.path.insert(0, str(root / "quantum"))
    import durable
    import resource_probe
    with durable.auxiliary_lease(root, phase):
        verified = s.verify(root, authorization, output, phase)
        output.mkdir(parents=True, exist_ok=False)
        gate.write_new(output / "START.json", {"status": "RUNNING", "phase": phase,
                       "started_utc": s.now(), "authorization": verified["authorization"],
                       "registration": verified["registration_binding"], "environment": verified["environment"]})
        wall, cpu = time.perf_counter(), time.process_time()
        try:
            result = convert(root, output, verified)
            result.update(finished_utc=s.now(), elapsed_seconds=time.perf_counter() - wall,
                          process_cpu_seconds=time.process_time() - cpu,
                          process_resources=s.process_resources(phase))
            s.finish(output, phase, verified, result)
            return result
        except BaseException as error:
            gate.write_new(output / "FAILURE.json", {"status": "FAILED_PRESERVED", "phase": phase,
                "error": repr(error), "traceback": traceback.format_exc(), "utc": s.now(),
                "recovery": "Root must authorize a fresh output with the identical frozen recipe; preserve this attempt"})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--phase", choices=("registration", "conversion"), required=True)
    parser.add_argument("--authorization")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.phase == "registration":
        value = registration(args.root)
        gate.write_new(args.output, value)
        print(json.dumps({"status": value["status"], "output": args.output,
                          "circuit_run_ids": len(value["circuit_run_ids"])}))
    else:
        if not args.authorization:
            parser.error("--authorization is required for numerical deployment phases")
        print(json.dumps(run(args.root, args.authorization, args.output, args.phase), allow_nan=False))
