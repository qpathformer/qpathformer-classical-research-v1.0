"""Released-only independent derived-artifact audit; no producer model imports."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import traceback
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[key] = "1"
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/"analysis/official"))
import gate

SOURCES = ("reference.py", "verify_arrays.py", "audit_artifacts.py", "test_reference.py")
CIRCUIT_ARMS = ("ScalarK", "MultiK", "MultiHash")
TRIG_ARMS = ("TrigK", "TrigHash", "TrigG25", "TrigG121")
METHODS = {"ScalarK": "qscalar_kmeans", "MultiK": "qmulti_kmeans", "MultiHash": "qmulti_hash",
           "TrigK": "trig_kmeans", "TrigHash": "trig_hash", "TrigG25": "trig_global", "TrigG121": "trig121_global"}


def source_hashes():
    return {name: gate.sha(HERE/name) for name in SOURCES}


def source_freeze():
    """Metadata-only snapshot, never test or model loading."""
    return {"schema": "qpath-v07-independent-deployment-source-freeze-1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "test_access_authorized": False, "sources": source_hashes(),
            "protocols": {name: gate.binding(ROOT/"governance"/name)
                          for name in ("RUN_MATRIX.json", "DEPLOYMENT_PROTOCOL.json", "LOCAL_READINESS_PROTOCOL.json")}}


def verify_header(release, output, phase):
    gate.require(release.get("schema") == "qpath-v07-independent-deployment-release-1" and
                 release.get("review_status") == "approved_by_root", "Independent deployment root release missing")
    gate.require(release.get("phase") == phase and phase in ("conversion", "shots"),
                 "Independent deployment phase differs")
    gate.require(release.get("test_access_authorized") is True and
                 release.get("max_parallel_tasks") == 1 and release.get("required_blas_threads") == 1,
                 "Independent deployment access/resources not authorized")
    gate.require(Path(release["output"]).resolve() == Path(output).resolve(),
                 "Independent output differs from root authorization")


def verify_committed_folder(commit_binding, phase):
    commit_path = gate.verify_binding(commit_binding, ROOT)
    folder, commit = commit_path.parent, gate.read(commit_path)
    gate.require(commit_path.name == phase.upper()+"_COMMIT.json" and
                 commit.get("schema") == f"qpath-v07-{phase}-commit-1" and commit.get("status") == "completed",
                 "Successful registered producer commit required")
    gate.require(not (folder/"FAILURE.json").exists(), "Producer failure evidence prohibits completed audit")
    for relative, info in commit["files"].items():
        file = (folder/relative).resolve()
        gate.require(file.is_relative_to(folder) and file != commit_path, "Producer payload path escapes output")
        gate.require(file.is_file() and file.stat().st_size == info["bytes"] and gate.sha(file) == info["sha256"],
                     "Producer payload changed")
    inventory = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    gate.require(inventory == set(commit["files"]) | {commit_path.name}, "Producer inventory differs")
    summary = gate.read(folder/"summary.json")
    gate.require(summary.get("status") == "PASS", "Producer summary unsuccessful")
    return folder, commit


def verify_release(authorization, output, phase):
    release = gate.read(authorization)
    verify_header(release, output, phase)
    gate.require(Path(authorization).resolve().is_relative_to(ROOT), "Root authorization outside study")
    output = Path(output).resolve()
    gate.require(output.is_relative_to(ROOT/"analysis") and not output.exists(), "New independent output required")
    freeze = gate.read(gate.verify_binding(release["source_freeze"], ROOT))
    gate.require(freeze.get("schema") == "qpath-v07-independent-deployment-source-freeze-1" and
                 freeze.get("test_access_authorized") is False and freeze["sources"] == source_hashes(),
                 "Independent deployment sources changed")
    for name, item in freeze["protocols"].items():
        gate.require(gate.verify_binding(item, ROOT) == ROOT/"governance"/name, "Independent protocol path differs")
    original_release = gate.verify_binding(release["evaluation_release"], ROOT)
    verified = gate.verify_completed_evaluation(ROOT, original_release, release["evaluation_commit"])
    producer_folder, producer_commit = verify_committed_folder(release["producer_commit"], phase)
    gate.require(producer_commit["evaluation_commit"] == verified["evaluation_commit"],
                 "Producer derived from another evaluation")
    producer_authorization = gate.read(gate.verify_binding(producer_commit["authorization"], ROOT))
    gate.require(producer_authorization.get("schema") == "qpath-v07-deployment-release-1" and
                 producer_authorization.get("review_status") == "approved_by_root" and
                 producer_authorization.get("phase") == phase and producer_authorization.get("test_access_authorized") is True,
                 "Producer authorization incomplete")
    gate.require(Path(producer_authorization["output"]).resolve() == producer_folder,
                 "Producer output not root authorized")
    registration = gate.read(gate.verify_binding(producer_commit["registration"], ROOT))
    gate.require(registration["schema"] == "qpath-v07-deployment-registration-1" and
                 registration["test_access_authorized"] is False, "Producer registration missing")
    gate.require(producer_commit["registration"] == producer_authorization["registration"],
                 "Producer authorization registration differs")
    for relative, digest in registration["sources"].items():
        path = (ROOT/relative).resolve()
        gate.require(path.is_relative_to(ROOT) and gate.sha(path) == digest, "Producer source changed")
    gate.require(producer_authorization["evaluation_release"] == release["evaluation_release"] and
                 producer_authorization["evaluation_commit"] == release["evaluation_commit"],
                 "Derived evaluation authorization differs")
    for key, name in (("deployment_protocol", "DEPLOYMENT_PROTOCOL.json"),
                      ("readiness_protocol", "LOCAL_READINESS_PROTOCOL.json"), ("run_matrix", "RUN_MATRIX.json")):
        gate.require(gate.verify_binding(registration[key], ROOT) == ROOT/"governance"/name,
                     "Producer protocol differs")
    arms = CIRCUIT_ARMS+TRIG_ARMS if phase == "conversion" else CIRCUIT_ARMS
    jobs = [job for job in verified["jobs"] if job["arm"] in arms]
    index = gate.read(producer_folder/"endpoint_index.json")
    gate.require([row["job_id"] for row in index] == [job["run_id"] for job in jobs],
                 "Producer endpoint inventory/order differs")
    gate.require(len(jobs) == (448 if phase == "conversion" else 192), "Incomplete producer scope")
    for row in index:
        expected = producer_folder/"endpoints"/row["job_id"]/("conversion.json" if phase == "conversion" else "diagnostics.json")
        gate.require(gate.verify_binding(row["record"], ROOT) == expected, "Producer record index differs")
    return {"root_release": release, "authorization": gate.binding(authorization), "verified": verified,
            "source_freeze": freeze, "producer_folder": producer_folder,
            "producer_commit": producer_commit, "registration": registration, "jobs": jobs}


def load_npz(path):
    import numpy as np
    with np.load(path, allow_pickle=False) as arrays:
        return {key: arrays[key].copy() for key in arrays.files}


def inputs(population, split, seal):
    """After release, read coordinates/identity only; labels remain unnecessary here."""
    import numpy as np
    import reference
    name = f"{population}_{'SEALED_test' if split == 'test' else 'validation'}.npz"
    file, policy_file = ROOT/"quantum/data"/name, ROOT/"quantum/data"/f"{population}_router.json"
    gate.require(gate.sha(file) == seal["files"][name]["sha256"] and
                 gate.sha(policy_file) == seal["routers"][population]["sha256"], "Consumed data/router changed")
    policy = gate.read(policy_file)
    with np.load(file, allow_pickle=False) as stored:
        pop = {key: stored[key].copy() for key in ("x", "ids", "kmeans_route", "hash_route")}
    gate.require(pop["x"].shape == (1600, 2) and len(set(pop["ids"].tolist())) == 1600, "Released input inventory differs")
    for kind in ("hash", "kmeans"):
        gate.require(np.array_equal(reference.route(pop["x"], policy, kind), pop[kind+"_route"]),
                     "Independent immutable routing differs")
    return pop, policy


def selected(job, verified):
    commit_path = gate.verify_binding(verified["endpoint_commits"][job["run_id"]], ROOT)
    commit = gate.read(commit_path)
    path = commit_path.parent/"selected_checkpoint.npz"
    gate.require(gate.sha(path) == commit["files"][path.name]["sha256"], "Selected checkpoint changed")
    return load_npz(path)["parameters"]


def feature_predict(arm, theta, x, route):
    """Independent learned Trig feature expansion; no producer/Model calls."""
    import numpy as np
    import reference
    frequency = 5 if arm == "TrigG121" else 2
    axes = []
    for q in range(2):
        values = [np.ones(len(x))]
        for k in range(1, frequency+1):
            values.extend((np.cos(k*np.pi*x[:, q]), np.sin(k*np.pi*x[:, q])))
        axes.append(np.column_stack(values))
    phi = np.einsum("ni,nj->nij", *axes).reshape(len(x), (2*frequency+1)**2)
    coefficients = theta.reshape(1 if arm in ("TrigG25", "TrigG121") else 5, -1)
    table = coefficients[0] if route is None else coefficients[route]
    z = np.sum(phi*table, axis=1)
    return reference.sigmoid(z), z


def assert_prediction_arrays(artifact, ids, original, p, z):
    import numpy as np
    from verify_arrays import near, threshold_parity
    gate.require(np.array_equal(artifact["record_ids"], ids) and np.array_equal(original["record_ids"], ids),
                 "Parity record order differs")
    gate.require(np.array_equal(artifact["original_probability"], original["probabilities"]) and
                 np.array_equal(artifact["original_logits"], original["native_logits"]), "Original parity arrays altered")
    pe = near(artifact["transformed_probability"], p, 2e-12, "Transformed probability replay differs")
    ze = near(artifact["transformed_logits"], z, 1e-9, "Transformed logit replay differs")
    disagreement = (artifact["transformed_probability"] >= .5) != (artifact["original_probability"] >= .5)
    gate.require(np.array_equal(artifact["decision_disagreement"], disagreement), "Parity disagreement flags differ")
    original_transformed = threshold_parity(artifact["original_probability"], artifact["transformed_probability"],
                                           "Original versus transformed threshold disagreement")
    transformed_reference = threshold_parity(artifact["transformed_probability"], p,
                                            "Transformed versus reference threshold disagreement")
    return {"maximum_probability_error": pe, "maximum_native_logit_error": ze,
            "retained_disagreement_indices": np.flatnonzero(disagreement).tolist(),
            "original_vs_transformed_threshold_parity": original_transformed,
            "transformed_vs_reference_threshold_parity": transformed_reference}


def audit_conversion(checked, output):
    import numpy as np
    import reference
    import verify_arrays as v
    seal = gate.read(ROOT/"quantum/data/DATA_SEAL.json")
    populations = {pop["population_id"]: pop for pop in gate.read(ROOT/"governance/RUN_MATRIX.json")["populations"]}
    cache, reports = {}, []
    for job in checked["jobs"]:
        identity, method = job["run_id"], METHODS[job["arm"]]
        theta = selected(job, checked["verified"])
        folder = checked["producer_folder"]/"endpoints"/identity
        representation = load_npz(folder/"representation.npz")["coefficients"]
        circuit = job["arm"] in CIRCUIT_ARMS
        report = {"job_id": identity, "arm": job["arm"], "splits": {}}
        if not circuit:
            expected = theta.reshape(1 if job["arm"] in ("TrigG25", "TrigG121") else 5, -1)
            v.near(representation, expected, 0., "Learned Trig repack changed coefficients")
        for split in ("validation", "test"):
            key = job["population_id"], split
            if key not in cache:
                cache[key] = inputs(*key, seal)
            pop, policy = cache[key]
            route = None if method.endswith("_global") else pop[method.split("_")[1]+"_route"]
            artifact = load_npz(folder/f"{split}_parity.npz")
            original = load_npz(Path(checked["verified"]["evaluation_output"])/"endpoints"/identity/f"{split}_predictions.npz")
            if circuit:
                record, coefficients, p, z = v.verify_conversion(method, theta, representation, pop["x"], route,
                                                               artifact["transformed_probability"], artifact["transformed_logits"])
                report.setdefault("coefficient_verification", record)
            else:
                p, z = feature_predict(job["arm"], theta, pop["x"], route)
            report["splits"][split] = assert_prediction_arrays(artifact, pop["ids"], original, p, z)
            destination = output/"predictions"/identity
            destination.mkdir(parents=True, exist_ok=True)
            with (destination/f"{split}_reference.npz").open("xb") as stream:
                np.savez(stream, record_ids=pop["ids"], probabilities=p, native_logits=z)
        fixture = load_npz(folder/"fixture_parity.npz")
        x = fixture["x"]
        stream = populations[job["population_id"]]["proposed_streams"]["boundary_diagnostic"]["uint128_decimal"]
        offgrid, boundary, metadata = reference.registered_parity_inputs(policy, stream)
        v.near(x, np.concatenate((offgrid, boundary)), 2e-11, "Preregistered independent offgrid/boundary fixtures differ")
        gate.require(int(fixture["offgrid_count"]) == 128 and
                     gate.read(folder/"conversion.json")["boundary_metadata"] == metadata,
                     "Fixture boundary metadata differs")
        route = None if method.endswith("_global") else reference.route(x, policy, method.split("_")[1])
        if route is not None:
            gate.require(np.array_equal(route, fixture["route"]), "Fixture raw-coordinate route differs")
        if circuit:
            fixture_report, _, fp, fz = v.verify_conversion(method, theta, representation, x, route,
                                                 fixture["transformed_probability"], fixture["transformed_logits"])
            v.near(fixture["original_probability"], fp, 2e-12, "Original routed fixture probability differs")
            v.near(fixture["original_logits"], fz, 1e-9, "Original routed fixture logits differ")
            forced = []
            for bank in range(5):
                report_bank, _, fp, fz = v.verify_conversion(method, theta, representation, x, np.full(len(x), bank),
                    fixture[f"bank{bank}_transformed_probability"], fixture[f"bank{bank}_transformed_logits"])
                v.near(fixture[f"bank{bank}_original_probability"], fp, 2e-12, "Original forced-bank probability differs")
                v.near(fixture[f"bank{bank}_original_logits"], fz, 1e-9, "Original forced-bank logits differ")
                report_bank["original_vs_transformed_threshold_parity"] = v.threshold_parity(
                    fixture[f"bank{bank}_original_probability"], fixture[f"bank{bank}_transformed_probability"],
                    f"Original versus transformed circuit bank{bank} threshold disagreement")
                forced.append(report_bank)
            report["forced_bank_fixtures"] = forced
        else:
            p, z = feature_predict(job["arm"], theta, x, route)
            fixture_report = {"probability_error": v.near(fixture["transformed_probability"], p, 2e-12, "Trig fixture differs"),
                              "native_logit_error": v.near(fixture["transformed_logits"], z, 1e-9, "Trig fixture logits differ")}
            v.near(fixture["original_probability"], p, 2e-12, "Original Trig fixture probability differs")
            v.near(fixture["original_logits"], z, 1e-9, "Original Trig fixture logits differ")
            fixture_report["transformed_vs_reference_threshold_parity"] = v.threshold_parity(
                fixture["transformed_probability"], p, "Transformed versus reference Trig fixture threshold disagreement")
            if route is not None:
                forced = []
                for bank in range(5):
                    p, z = feature_predict(job["arm"], theta, x, np.full(len(x), bank))
                    for prefix in ("original", "transformed"):
                        v.near(fixture[f"bank{bank}_{prefix}_probability"], p, 2e-12, "Forced Trig probability differs")
                        v.near(fixture[f"bank{bank}_{prefix}_logits"], z, 1e-9, "Forced Trig logits differ")
                    forced.append({
                        "bank": bank,
                        "original_vs_transformed_threshold_parity": v.threshold_parity(
                            fixture[f"bank{bank}_original_probability"], fixture[f"bank{bank}_transformed_probability"],
                            f"Original versus transformed Trig bank{bank} threshold disagreement"),
                        "transformed_vs_reference_threshold_parity": v.threshold_parity(
                            fixture[f"bank{bank}_transformed_probability"], p,
                            f"Transformed versus reference Trig bank{bank} threshold disagreement")})
                report["forced_bank_fixtures"] = forced
        fixture_report["original_vs_transformed_threshold_parity"] = v.threshold_parity(
            fixture["original_probability"], fixture["transformed_probability"],
            "Original versus transformed routed/offgrid fixture threshold disagreement")
        report["label_free_fixtures"] = fixture_report
        reports.append(report)
    gate.write_new(output/"conversion_replay.json", reports)
    return {"status": "PASS", "representations_replayed": len(reports), "independent_circuit_coefficients": 192,
            "circuit_endpoints": 192, "conversion_commit": checked["root_release"]["producer_commit"],
            "learned_trig_exact_repacks": 256, "validation_and_test_probability_rows": 448*3200,
            "scope": "Separate Laurent algebra, explicit dense matrices, feature expansion and immutable routes; all five circuit banks checked on retained label-free fixtures."}


def audit_shots(checked, output):
    import numpy as np
    import reference
    import verify_arrays as v
    seal = gate.read(ROOT/"quantum/data/DATA_SEAL.json")
    cache, reports = {}, []
    arrays = vectors = values = outcomes = 0
    for job in checked["jobs"]:
        identity, population, method = job["run_id"], job["population_id"], METHODS[job["arm"]]
        theta = selected(job, checked["verified"])
        if population not in cache:
            cache[population] = inputs(population, "validation", seal)
        pop, policy = cache[population]
        order = np.argsort(pop["ids"], kind="stable")[:32]
        x, ids = pop["x"][order], pop["ids"][order]
        route = reference.route(x, policy, method.split("_")[1])
        folder = checked["producer_folder"]/"endpoints"/identity
        fixture = load_npz(folder/"ideal_fixture.npz")
        gate.require(np.array_equal(fixture["x"], x) and np.array_equal(fixture["record_ids"], ids)
                     and np.array_equal(fixture["route"], route), "Shot fixture selection/route changed")
        settings = ("XX",) if job["arm"] == "ScalarK" else ("XX", "ZZ")
        joints = {setting: fixture["joint_"+setting] for setting in settings}
        joint_report, independent_joints = v.verify_joint_inputs(method, theta, x, route, joints,
                                                                fixture["heads"], fixture["probabilities"])
        expected_x = independent_joints["XX"] @ reference.SIGNS[:2].T
        ideal_moments = (expected_x[:, :1] if len(settings) == 1 else
                         np.column_stack((expected_x, independent_joints["ZZ"] @ reference.SIGNS.T)))
        ideal_logits = np.sum(ideal_moments*fixture["heads"][:, :-1], axis=1)+fixture["heads"][:, -1]
        v.near(fixture["moments"], ideal_moments, 2e-12, "Saved ideal moments differ")
        v.near(fixture["logits"], ideal_logits, 1e-9, "Saved ideal native logits differ")
        counts, prediction = load_npz(folder/"joint_counts.npz"), load_npz(folder/"shot_predictions.npz")
        expected_keys = {f"N{total}_r{repeat:02d}_{setting}" for total in (1024, 8192)
                         for repeat in range(20) for setting in settings}
        gate.require(set(counts) == expected_keys and prediction["probabilities"].shape == (2, 20, 32),
                     "Shot array inventory/shape differs")
        gate.require(np.array_equal(prediction["record_ids"], ids) and
                     np.array_equal(prediction["total_budgets"], [1024, 8192]) and
                     np.array_equal(prediction["technical_seed_ids"], np.arange(20)), "Shot prediction metadata differs")
        diagnostics = gate.read(folder/"diagnostics.json")
        gate.require(diagnostics["job_id"] == identity and diagnostics["arm"] == job["arm"] and
                     diagnostics["population"] == population and diagnostics["seed"] == job["training_seed_id"] and
                     diagnostics["hardware_used"] is False and diagnostics["labels_used"] is False,
                     "Shot identity or scope differs")
        reconstructed = np.empty((2, 20, 32))
        budget_reports = []
        for b, total in enumerate((1024, 8192)):
            for repeat in range(20):
                selected_counts = {setting: counts[f"N{total}_r{repeat:02d}_{setting}"] for setting in settings}
                draw_report, reconstructed[b, repeat] = v.verify_shot_draw(identity, total, repeat, fixture["heads"],
                    joints, selected_counts, prediction["probabilities"][b, repeat])
                moments = reference.moments_from_counts(selected_counts["XX"], selected_counts.get("ZZ"))
                z = np.sum(moments*fixture["heads"][:, :-1], axis=1)+fixture["heads"][:, -1]
                v.near(prediction["moments"][b, repeat], moments, 2e-15, "Saved count moments differ")
                v.near(prediction["logits"][b, repeat], z, 1e-9, "Saved count logits differ")
                arrays += len(settings)
                vectors += draw_report["joint_count_vectors"]
                outcomes += draw_report["represented_measurement_outcomes"]
                values += 32
            stats = v.conditional_statistics(prediction["probabilities"][b], fixture["probabilities"])
            saved = diagnostics["budgets"][b]
            gate.require(saved["total_budget"] == total, "Budget diagnostic order differs")
            for name, value in stats.items():
                v.near(saved[name], value, 2e-12, "Conditional shot statistic differs: "+name)
            analytic = v.head_logit_variance(joints, fixture["heads"], total)
            v.near(saved["analytic_joint_logit_variance_per_record"], analytic, 2e-12, "Analytic joint-head variance differs")
            v.near(saved["head_weight_l1_per_record"], np.sum(abs(fixture["heads"][:, :-1]), axis=1), 2e-12, "Head L1 differs")
            v.near(saved["head_weight_l2_per_record"], np.sqrt(np.sum(fixture["heads"][:, :-1]**2, axis=1)), 2e-12, "Head L2 differs")
            v.near(saved["observed_logit_technical_variance_ddof0_per_record"], prediction["logits"][b].var(axis=0, ddof=0),
                   2e-12, "Observed logit variance differs")
            v.near(saved["first_order_delta_probability_variance_per_record"],
                   (fixture["probabilities"]*(1-fixture["probabilities"]))**2*analytic, 2e-12, "Delta variance differs")
            budget_reports.append({"total_budget": total, "statistics": stats, "analytic_logit_variance": analytic.tolist()})
        destination = output/"predictions"/identity
        destination.mkdir(parents=True, exist_ok=False)
        with (destination/"reference_shot_predictions.npz").open("xb") as stream:
            np.savez(stream, record_ids=ids, probabilities=reconstructed)
        reports.append({"job_id": identity, "joint_state": joint_report, "budgets": budget_reports})
    gate.require([len(reports), arrays, vectors, values, outcomes] == [192, 12800, 409600, 245760, 1132462080],
                 "Independent complete shot accounting differs")
    gate.write_new(output/"shot_replay.json", reports)
    return {"status": "PASS", "checkpoints": len(reports), "count_arrays": arrays, "count_vectors": vectors,
            "prediction_values": values, "represented_measurement_outcomes": outcomes,
            "scope": "Separate dense-state probabilities, exact stream replay using retained normalized probabilities, shared-count moments and scalar predictions; no physical quantum evidence."}


def run(authorization, output, phase):
    sys.path.insert(0, str(ROOT/"execution"))
    import durable
    import resource_probe
    with durable.auxiliary_lease(ROOT, "audit"):
        checked = verify_release(authorization, output, phase)
        environment = resource_probe.inspect()
        expected_environment = gate.read(checked["verified"]["release"]["runtime_environment"]["path"])
        for key in ("python", "interpreter", "numpy_version", "openblas_dll_sha256", "effective_blas_threads"):
            gate.require(environment[key] == expected_environment[key], "Independent deployment environment differs")
        output = Path(output).resolve()
        output.mkdir(parents=True, exist_ok=False)
        started, wall, cpu = datetime.now(timezone.utc).isoformat(), time.perf_counter(), time.process_time()
        gate.write_new(output/"START.json", {"status": "RUNNING", "phase": phase, "started_utc": started,
                       "authorization": checked["authorization"], "environment": environment})
        try:
            result = (audit_conversion if phase == "conversion" else audit_shots)(checked, output)
            result.update(phase=phase, elapsed_seconds=time.perf_counter()-wall,
                          process_cpu_seconds=time.process_time()-cpu,
                          finished_utc=datetime.now(timezone.utc).isoformat(),
                          authorization=checked["authorization"],
                          producer_commit=checked["root_release"]["producer_commit"])
            gate.require(checked["source_freeze"]["sources"] == source_hashes(), "Independent sources changed during audit")
            gate.verify_binding(checked["authorization"], ROOT)
            verify_committed_folder(checked["root_release"]["producer_commit"], phase)
            gate.write_new(output/"summary.json", result)
            files = {p.relative_to(output).as_posix(): {"sha256": gate.sha(p), "bytes": p.stat().st_size}
                     for p in sorted(output.rglob("*")) if p.is_file()}
            gate.write_new(output/"INDEPENDENT_DEPLOYMENT_COMMIT.json",
                           {"schema": "qpath-v07-independent-deployment-commit-1",
                            "status": "completed", "phase": phase, "files": files,
                            "authorization": checked["authorization"]})
            return result
        except BaseException as error:
            gate.write_new(output/"FAILURE.json", {"status": "FAILED_PRESERVED", "error": repr(error),
                "traceback": traceback.format_exc(), "recovery": "Root-authorized fresh identical audit attempt; no overwrite."})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "conversion", "shots"), required=True)
    parser.add_argument("--authorization")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.phase == "freeze":
        gate.require(args.authorization is None, "Source freeze never authorizes numerical access")
        gate.write_new(args.output, source_freeze())
    else:
        gate.require(args.authorization is not None, "Root independent audit release required")
        print(json.dumps(run(args.authorization, args.output, args.phase), allow_nan=False))
