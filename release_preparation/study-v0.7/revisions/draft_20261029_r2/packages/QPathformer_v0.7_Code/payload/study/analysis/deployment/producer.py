"""Registered post-release circuit conversion and ideal finite-shot diagnostics."""
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

CIRCUIT_ARMS = ("ScalarK", "MultiK", "MultiHash")
TRIG_ARMS = ("TrigK", "TrigHash", "TrigG25", "TrigG121")


def confirmation_inventory(matrix):
    jobs = [j for j in matrix["runs"] if j["stage"] in ("B", "confirmation")]
    populations = [p for p in matrix["populations"] if p["stage"] in ("B", "confirmation")]
    gate.require(len(jobs) == 512 and len({j["run_id"] for j in jobs}) == 512, "512 unique B jobs required")
    gate.require(len(populations) == 32 and len({p["population_id"] for p in populations}) == 32,
                 "32 unique confirmation populations required")
    gate.require(set(Counter(p["family"] for p in populations).values()) == {8}, "Eight populations per family")
    gate.require(len(set(p["family"] for p in populations)) == 4, "Four families required")
    gate.require(set(j["population_id"] for j in jobs) == {p["population_id"] for p in populations},
                 "Run/population identities differ")
    circuits = [j for j in jobs if j["arm"] in CIRCUIT_ARMS]
    gate.require(len(circuits) == 192, "192 selected circuit predictors required")
    gate.require(Counter(j["arm"] for j in jobs) ==
                 Counter({a: 64 for a in (*CIRCUIT_ARMS, *TRIG_ARMS, "MLPG129")}),
                 "Unexpected selected arm inventory")
    return jobs, populations, circuits


def registration(root):
    """Metadata only; does not inspect any data arrays or endpoint outcomes."""
    import joint
    root = Path(root).resolve()
    jobs, populations, circuits = confirmation_inventory(gate.read(root / "governance/RUN_MATRIX.json"))
    streams = []
    for job in circuits:
        for budget in (1024, 8192):
            for repeat in range(20):
                for setting in (("XX",) if job["arm"] == "ScalarK" else ("XX", "ZZ")):
                    streams.append({"run_id": job["run_id"], "total_budget": budget,
                                    "technical_seed_id": repeat, "setting": setting,
                                    **joint.technical_stream(job["run_id"], budget, setting, repeat)})
    gate.require(len(streams) == len({v["uint128_decimal"] for v in streams}) == 12800,
                 "Shot stream count/collision")
    return {"schema": "qpath-v07-deployment-registration-1", "created_utc": s.now(),
            "status": "PREPARED_FOR_ROOT_REVIEW", "test_access_authorized": False,
            "sources": s.sources(root),
            "deployment_protocol": gate.binding(root / "governance/DEPLOYMENT_PROTOCOL.json"),
            "readiness_protocol": gate.binding(root / "governance/LOCAL_READINESS_PROTOCOL.json"),
            "run_matrix": gate.binding(root / "governance/RUN_MATRIX.json"),
            "all_run_ids": [j["run_id"] for j in jobs],
            "circuit_run_ids": [j["run_id"] for j in circuits],
            "confirmation_populations": [p["population_id"] for p in populations],
            "shot_streams": streams,
            "fixtures": {"shot_selection": "Lowest 32 numeric validation IDs, ascending, no labels",
                         "conversion_offgrid": "128 uniform[-1,1]^2 using population boundary_diagnostic stream",
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
            "conversion_scope": "No fit; five banks x25 real coefficients; 256 learned Trig tables repacked without fitting",
            "shot_scope": "Conditional classical multinomial simulation; no hardware, no heldout F1"}


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
                  "population": job["population_id"], "seed": job["training_seed_id"],
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
    gate.require(len(records) == 448 and sum(r["arm"] in CIRCUIT_ARMS for r in records) == 192,
                 "Conversion inventory incomplete")
    gate.write_new(output / "endpoint_index.json", records)
    return {"status": "PASS", "circuit_conversions": 192, "learned_trig_same_checkpoint_transforms": 256,
            "transformed_representations": len(records), "all_validation_test_parity_retained": True,
            "independent_coefficient_replay": "REQUIRED_SEPARATE_IMPLEMENTATION",
            "no_accuracy_gain_claimed": True, "hardware_used": False}


def analytic_logit_variance(joints, heads, total_budget):
    """Variance of linear logit estimator with joint within-setting covariance."""
    import numpy as np
    import joint
    scalar = heads.shape[1] == 2
    shots = total_budget if scalar else total_budget // 2
    result = np.zeros(len(heads))
    settings = [("XX", heads[:, :1], joint.SIGNS[:1])] if scalar else [
        ("XX", heads[:, :2], joint.SIGNS[:2]), ("ZZ", heads[:, 2:5], joint.SIGNS)]
    for setting, weights, signs in settings:
        values = weights @ signs
        mean = np.sum(joints[setting] * values, axis=1)
        variance = np.sum(joints[setting] * values**2, axis=1) - mean**2
        result += np.maximum(variance, 0) / shots
    return result


def shots(root, output, verified):
    import numpy as np
    import joint
    from fixtures import parity
    root, output = Path(root), Path(output)
    seal = gate.read(root / "quantum/data/DATA_SEAL.json")
    records, cache = [], {}
    count_arrays = count_vectors = prediction_values = represented_outcomes = 0
    stream_map = {(v["run_id"], v["total_budget"], v["setting"], v["technical_seed_id"]): v
                  for v in verified["registration"]["shot_streams"]}
    for job in verified["jobs"]:
        if job["arm"] not in CIRCUIT_ARMS:
            continue
        model, load_evidence = s.load_model(job, verified, root)
        population = job["population_id"]
        if population not in cache:
            cache[population] = s.load_population(root, population, "validation", seal)
        pop, policy, data_evidence = cache[population]
        order = np.argsort(pop["ids"], kind="stable")[:32]
        x, ids = pop["x"][order], pop["ids"][order]
        route = model.route_for(pop)[order]
        joints, heads = joint.model_joint(model, x, route)
        ideal_p, ideal_z, ideal_moments = joint.predict_from_joint(joints, heads)
        canonical_values = canonical(verified, job, "validation")
        gate.require(np.array_equal(canonical_values["record_ids"], pop["ids"]), "Shot canonical record identity")
        ideal_parity = parity(ideal_p, ideal_z, canonical_values["probabilities"][order],
                              canonical_values["native_logits"][order], ids)
        folder = output / "endpoints" / job["run_id"]
        folder.mkdir(parents=True, exist_ok=False)
        s.npz_new(folder / "ideal_fixture.npz", x=x, record_ids=ids, route=route, heads=heads,
                  probabilities=ideal_p, logits=ideal_z, moments=ideal_moments,
                  **{f"joint_{k}": v for k, v in joints.items()})
        count_payload, budget_diagnostics = {}, []
        probabilities = np.empty((2, 20, 32))
        logits = np.empty_like(probabilities)
        moments = np.empty((2, 20, 32, model.moment_count))
        for b, budget in enumerate((1024, 8192)):
            for repeat in range(20):
                sampled = {}
                for setting, values in joints.items():
                    counts, setting_shots, stream = joint.draw_counts(
                        values, budget, setting, repeat, job["run_id"], model.moment_count == 1)
                    expected = stream_map[(job["run_id"], budget, setting, repeat)]
                    gate.require(stream["namespace"] == expected["namespace"] and
                                 stream["uint128_decimal"] == expected["uint128_decimal"], "Shot stream differs from registration")
                    count_payload[f"N{budget}_r{repeat:02d}_{setting}"] = counts
                    sampled[setting] = counts / setting_shots
                    count_arrays += 1
                    count_vectors += len(counts)
                    represented_outcomes += int(counts.sum())
                probabilities[b, repeat], logits[b, repeat], moments[b, repeat] = joint.predict_from_joint(sampled, heads)
            theoretical = analytic_logit_variance(joints, heads, budget)
            diagnostics = joint.conditional_diagnostics(probabilities[b], ideal_p)
            budget_diagnostics.append({"total_budget": budget, **diagnostics,
                "head_weight_l1_per_record": np.sum(abs(heads[:, :-1]), axis=1).tolist(),
                "head_weight_l2_per_record": np.linalg.norm(heads[:, :-1], axis=1).tolist(),
                "analytic_joint_logit_variance_per_record": theoretical.tolist(),
                "observed_logit_technical_variance_ddof0_per_record": logits[b].var(axis=0, ddof=0).tolist(),
                "first_order_delta_probability_variance_per_record":
                    ((ideal_p * (1 - ideal_p))**2 * theoretical).tolist(),
                "delta_method_scope": "Descriptive first-order approximation; actual probability error uses sampled sigmoid outputs"})
        prediction_values += probabilities.size
        s.npz_new(folder / "joint_counts.npz", **count_payload)
        s.npz_new(folder / "shot_predictions.npz", total_budgets=np.array([1024, 8192]),
                  technical_seed_ids=np.arange(20), record_ids=ids,
                  probabilities=probabilities, logits=logits, moments=moments)
        record = {"job_id": job["run_id"], "arm": job["arm"], "family": job["family"],
                  "population": population, "seed": job["training_seed_id"], "load": load_evidence,
                  "fixture_data": data_evidence, "fixture_selection": "Lowest32numeric validationIDs, ascending",
                  "fixture_records": 32, "ideal_parity": ideal_parity, "budgets": budget_diagnostics,
                  "hardware_used": False, "labels_used": False,
                  "scope": "Conditional finite-shot diagnostics around own ideal checkpoint; not heldout performance or hardware evidence"}
        gate.write_new(folder / "diagnostics.json", record)
        records.append({"job_id": job["run_id"], "arm": job["arm"],
                        "record": gate.binding(folder / "diagnostics.json")})
    actual = [len(records), count_arrays, count_vectors, prediction_values, represented_outcomes]
    gate.require(actual == [192, 12800, 409600, 245760, 1132462080], "Finite-shot coverage/count inventory differs")
    gate.write_new(output / "endpoint_index.json", records)
    return {"status": "PASS", "checkpoints": len(records), "checkpoint_input_pairs": 6144,
            "joint_count_arrays": count_arrays, "joint_count_vectors": count_vectors,
            "scalar_prediction_values": prediction_values, "represented_measurement_outcomes": represented_outcomes,
            "hardware_used": False, "cloud_used": False, "aer_calls": 0,
            "scope": "Classical ideal joint multinomial simulation; not physical shots",
            "independent_joint_count_replay": "REQUIRED_SEPARATE_IMPLEMENTATION"}


def run(root, authorization, output, phase):
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
            result = (convert if phase == "conversion" else shots)(root, output, verified)
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
    parser.add_argument("--phase", choices=("registration", "conversion", "shots"), required=True)
    parser.add_argument("--authorization")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.phase == "registration":
        value = registration(args.root)
        gate.write_new(args.output, value)
        print(json.dumps({"status": value["status"], "output": args.output,
                          "circuit_run_ids": len(value["circuit_run_ids"]), "shot_streams": len(value["shot_streams"])}))
    else:
        if not args.authorization:
            parser.error("--authorization is required for numerical deployment phases")
        print(json.dumps(run(args.root, args.authorization, args.output, args.phase), allow_nan=False))
