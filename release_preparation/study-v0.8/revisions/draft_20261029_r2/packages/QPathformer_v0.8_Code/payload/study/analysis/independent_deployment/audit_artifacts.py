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
sys.path.insert(0, str(ROOT/"analysis/official_evaluation"))
import gate

SOURCES = ("reference.py", "verify_arrays.py", "audit_artifacts.py", "release_chains.py", "test_reference.py")
CIRCUIT_ARMS = ("MultiK_U", "MultiK_P", "MultiHash_U", "MultiHash_P")
TRIG_ARMS = tuple(base+"_"+policy for base in ("TrigK", "TrigHash", "TrigG121") for policy in ("U", "P"))
METHODS = {base+"_"+policy: method for base,method in
           (("MultiK", "qmulti_kmeans"),("MultiHash", "qmulti_hash"),("TrigK", "trig_kmeans"),
            ("TrigHash", "trig_hash"),("TrigG121", "trig121_global")) for policy in ("U", "P") }


def source_hashes():
    return {name: gate.sha(HERE/name) for name in SOURCES}


def source_freeze():
    """Metadata-only snapshot, never test or model loading."""
    return {"schema": "qpath-v08-independent-deployment-source-freeze-1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "test_access_authorized": False, "sources": source_hashes(),
            "protocols": {name: gate.binding(ROOT/"governance"/name)
                          for name in ("RUN_MATRIX.json", "DEPLOYMENT_PROTOCOL.json", "LOCAL_READINESS_PROTOCOL.json")}}


def verify_header(release, output, phase):
    gate.require(release.get("schema") == "qpath-v08-independent-deployment-release-1" and
                 release.get("review_status") == "approved_by_root", "Independent deployment root release missing")
    gate.require(release.get("phase") == phase and phase == "conversion",
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
                 commit.get("schema") == f"qpath-v08-{phase}-commit-1" and commit.get("status") == "completed",
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
    gate.require(freeze.get("schema") == "qpath-v08-independent-deployment-source-freeze-1" and
                 freeze.get("test_access_authorized") is False and freeze["sources"] == source_hashes() and
                 set(freeze["protocols"]) == {"RUN_MATRIX.json", "DEPLOYMENT_PROTOCOL.json", "LOCAL_READINESS_PROTOCOL.json"},
                 "Independent deployment sources changed")
    for name, item in freeze["protocols"].items():
        gate.require(gate.verify_binding(item, ROOT) == ROOT/"governance"/name, "Independent protocol path differs")
    original_release = gate.verify_binding(release["evaluation_release"], ROOT)
    verified = gate.verify_completed_evaluation(ROOT, original_release, release["evaluation_commit"])
    from release_chains import verify_score_replay
    verify_score_replay(release, verified)
    producer_folder, producer_commit = verify_committed_folder(release["producer_commit"], phase)
    gate.require(producer_commit["evaluation_commit"] == verified["evaluation_commit"],
                 "Producer derived from another evaluation")
    producer_authorization = gate.read(gate.verify_binding(producer_commit["authorization"], ROOT))
    gate.require(producer_authorization.get("schema") == "qpath-v08-deployment-release-1" and
                 producer_authorization.get("review_status") == "approved_by_root" and
                 producer_authorization.get("phase") == phase and producer_authorization.get("test_access_authorized") is True,
                 "Producer authorization incomplete")
    gate.require(Path(producer_authorization["output"]).resolve() == producer_folder,
                 "Producer output not root authorized")
    registration = gate.read(gate.verify_binding(producer_commit["registration"], ROOT))
    gate.require(registration["schema"] == "qpath-v08-deployment-registration-1" and
                 registration["test_access_authorized"] is False, "Producer registration missing")
    gate.require(producer_commit["registration"] == producer_authorization["registration"],
                 "Producer authorization registration differs")
    for relative, digest in registration["sources"].items():
        path = (ROOT/relative).resolve()
        gate.require(path.is_relative_to(ROOT) and gate.sha(path) == digest, "Producer source changed")
    gate.require(producer_authorization["evaluation_release"] == release["evaluation_release"] and
                 producer_authorization["evaluation_commit"] == release["evaluation_commit"] and
                 producer_authorization["independent_score_replay_commit"] == release["independent_score_replay_commit"],
                 "Derived evaluation authorization differs")
    for key, name in (("deployment_protocol", "DEPLOYMENT_PROTOCOL.json"),
                      ("readiness_protocol", "LOCAL_READINESS_PROTOCOL.json"), ("run_matrix", "RUN_MATRIX.json")):
        gate.require(gate.verify_binding(registration[key], ROOT) == ROOT/"governance"/name,
                     "Producer protocol differs")
    arms = CIRCUIT_ARMS+TRIG_ARMS
    jobs = [job for job in verified["jobs"] if job["arm"] in arms]
    index = gate.read(producer_folder/"endpoint_index.json")
    gate.require([row["job_id"] for row in index] == [job["run_id"] for job in jobs],
                 "Producer endpoint inventory/order differs")
    gate.require(len(jobs) == 640, "Incomplete producer scope")
    for row in index:
        expected = producer_folder/"endpoints"/row["job_id"]/"conversion.json"
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
    frequency = 5 if arm.startswith("TrigG121_") else 2
    axes = []
    for q in range(2):
        values = [np.ones(len(x))]
        for k in range(1, frequency+1):
            values.extend((np.cos(k*np.pi*x[:, q]), np.sin(k*np.pi*x[:, q])))
        axes.append(np.column_stack(values))
    phi = np.einsum("ni,nj->nij", *axes).reshape(len(x), (2*frequency+1)**2)
    coefficients = theta.reshape(1 if arm.startswith("TrigG121_") else 5, -1)
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
            expected = theta.reshape(1 if job["arm"].startswith("TrigG121_") else 5, -1)
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
    return {"status": "PASS", "representations_replayed": len(reports), "independent_circuit_coefficients": 256,
            "circuit_endpoints": 256, "conversion_commit": checked["root_release"]["producer_commit"],
            "learned_trig_exact_repacks": 384, "validation_and_test_probability_rows": 640*3200,
            "scope": "Separate Laurent algebra, explicit dense matrices, feature expansion and immutable routes; all five circuit banks checked on retained label-free fixtures."}




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
            result = audit_conversion(checked, output)
            result.update(phase=phase, elapsed_seconds=time.perf_counter()-wall,
                          process_cpu_seconds=time.process_time()-cpu,
                          finished_utc=datetime.now(timezone.utc).isoformat(),
                          authorization=checked["authorization"],
                          producer_commit=checked["root_release"]["producer_commit"])
            result["process_resources"] = {**resource_probe.process_resources(),
                "scope": "Whole independent conversion process through sample; reported phase wall/CPU counters start after release verification."}
            gate.require(checked["source_freeze"]["sources"] == source_hashes(), "Independent sources changed during audit")
            gate.verify_binding(checked["authorization"], ROOT)
            verify_committed_folder(checked["root_release"]["producer_commit"], phase)
            gate.write_new(output/"summary.json", result)
            files = {p.relative_to(output).as_posix(): {"sha256": gate.sha(p), "bytes": p.stat().st_size}
                     for p in sorted(output.rglob("*")) if p.is_file()}
            gate.write_new(output/"INDEPENDENT_DEPLOYMENT_COMMIT.json",
                           {"schema": "qpath-v08-independent-deployment-commit-1",
                            "status": "completed", "phase": phase, "files": files,
                            "authorization": checked["authorization"]})
            return result
        except BaseException as error:
            gate.write_new(output/"FAILURE.json", {"status": "FAILED_PRESERVED", "error": repr(error),
                "traceback": traceback.format_exc(), "recovery": "Root-authorized fresh identical audit attempt; no overwrite."})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "conversion"), required=True)
    parser.add_argument("--authorization")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.phase == "freeze":
        gate.require(args.authorization is None, "Source freeze never authorizes numerical access")
        gate.write_new(args.output, source_freeze())
    else:
        gate.require(args.authorization is not None, "Root independent audit release required")
        print(json.dumps(run(args.authorization, args.output, args.phase), allow_nan=False))
