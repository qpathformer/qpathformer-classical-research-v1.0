"""Read-only, fail-closed bindings shared by derived deployment producers."""
from __future__ import annotations
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis/official_evaluation"))
import gate

SOURCE_FILES = ("compiler.py", "fixtures.py", "support.py", "readiness_gates.py",
                "producer.py", "timing.py", "tests/test_deployment.py")


def now():
    return datetime.now(timezone.utc).isoformat()


def process_resources(phase):
    """Reuse the frozen read-only probe with an accurate derived-process scope."""
    import resource_probe
    result = resource_probe.process_resources()
    return {**result, "scope": f"Whole {phase} process including imports, release verification, derived numerical work and file writes through sampling time"}


def sources(root):
    root = Path(root).resolve()
    return {f"analysis/deployment/{p}": gate.sha(root / "analysis/deployment" / p) for p in SOURCE_FILES}


def validate_header(release, phase, output):
    gate.require(release.get("schema") == "qpath-v08-deployment-release-1" and
                 release.get("review_status") == "approved_by_root", "Root derived-work approval missing")
    gate.require(phase in ("conversion","timing"), "Unregistered deployment phase")
    gate.require(release.get("phase") == phase, "Wrong deployment phase")
    gate.require(Path(release["output"]).resolve() == Path(output).resolve(), "Output not root bound")
    gate.require(release.get("test_access_authorized") is True, "Explicit derived test access missing")
    gate.require(release.get("max_parallel_tasks") == 1 and release.get("required_blas_threads") == 1,
                 "Derived work must be serial with one BLAS thread")


def verify(root, authorization, output, phase):
    root, output = Path(root).resolve(), Path(output).resolve()
    gate.require(output.is_relative_to(root / "analysis") and not output.exists(),
                 "New separate derived output directory required")
    release = gate.read(authorization)
    validate_header(release, phase, output)
    registration_path = gate.verify_binding(release["registration"], root)
    registration = gate.read(registration_path)
    gate.require(registration["schema"] == "qpath-v08-deployment-registration-1" and
                 registration.get("test_access_authorized") is False and
                 registration["sources"] == sources(root), "Derived source registration changed")
    for key, name in (("deployment_protocol", "DEPLOYMENT_PROTOCOL.json"),
                      ("readiness_protocol", "LOCAL_READINESS_PROTOCOL.json"),
                      ("run_matrix", "RUN_MATRIX.json")):
        gate.require(gate.verify_binding(registration[key], root) == root / "governance" / name,
                     "Wrong registered protocol path")
    evaluation_release = gate.verify_binding(release["evaluation_release"], root)
    verified = gate.verify_completed_evaluation(root, evaluation_release, release["evaluation_commit"])
    import readiness_gates
    readiness_gates.verify_score_replay(root, release, verified)
    if phase == "timing":
        readiness_gates.verify_reproduction(root, release, verified)
    expected = [j["run_id"] for j in verified["jobs"] if j["arm"] in ("MultiK_U", "MultiK_P", "MultiHash_U", "MultiHash_P")]
    gate.require(registration["circuit_run_ids"] == expected and len(expected) == 256,
                 "Registered conversion identity changed")
    gate.require(registration["all_run_ids"] == [j["run_id"] for j in verified["jobs"]] and
                 len(verified["jobs"]) == 640, "Registered full predictor inventory changed")
    # Sources and historical runtime must match before any numerical loading.
    sys.path.insert(0, str(root / "execution"))
    import resource_probe
    environment = resource_probe.inspect()
    expected_env = gate.read(verified["release"]["runtime_environment"]["path"])
    for key in ("python", "interpreter", "numpy_version", "openblas_dll_sha256",
                "openblas_config", "effective_blas_threads", "gpu_used"):
        gate.require(environment[key] == expected_env[key], f"Scientific runtime changed: {key}")
    gate.require(environment["effective_blas_threads"] == 1, "Effective BLAS thread count is not one")
    return {"derived_release": release, "authorization": gate.binding(authorization), "registration": registration,
            "registration_binding": gate.binding(registration_path), "environment": environment, **verified}


def npz_new(path, **arrays):
    import numpy as np
    with Path(path).open("xb") as stream:
        np.savez(stream, **arrays)
        stream.flush()
        os.fsync(stream.fileno())


def load_model(job, verified, root):
    import numpy as np
    sys.path.insert(0, str(Path(root) / "quantum"))
    from models import Model, ARM_METHODS
    commit_binding = verified["endpoint_commits"][job["run_id"]]
    endpoint = gate.verify_binding(commit_binding, root).parent
    commit = gate.read(commit_binding["path"])
    file = endpoint / "selected_checkpoint.npz"
    gate.require(gate.sha(file) == commit["files"]["selected_checkpoint.npz"]["sha256"],
                 "Checkpoint changed after gate")
    start = time.perf_counter_ns()
    streams = {k: int(v["uint128_decimal"]) for k, v in job["paired_streams"].items()}
    model = Model(ARM_METHODS[job["arm"]], job["training_seed_id"], streams)
    with np.load(file, allow_pickle=False) as data:
        parameters = data["parameters"].copy()
    gate.require(parameters.shape == model.parameters.shape and np.isfinite(parameters).all(),
                 "Selected parameter payload invalid")
    model.parameters[:] = parameters
    return model, {"checkpoint": gate.binding(file), "endpoint_commit": commit_binding,
                   "model_construction_and_checkpoint_loading_ns": time.perf_counter_ns() - start,
                   "parameter_bytes": parameters.nbytes,
                   "scope": "Single instrumented load; not a repeated isolated latency estimate"}


def load_population(root, population, split, seal):
    """Post-release coordinate/routes only; no labels or latent diagnostics."""
    import numpy as np
    import routers
    gate.require(split in ("validation", "test"), "Unregistered parity split")
    folder = Path(root) / "quantum/data"
    name = f"{population}_{'SEALED_test' if split == 'test' else 'validation'}.npz"
    file, policy_file = folder / name, folder / f"{population}_router.json"
    entry = seal["files"][name]
    gate.require(gate.sha(file) == entry["sha256"] and entry["dataset"] == population and
                 entry["split"] == split, "Changed data split")
    gate.require(gate.sha(policy_file) == entry["router_policy_sha256"] ==
                 seal["routers"][population]["sha256"], "Changed router policy")
    policy = gate.read(policy_file)
    with np.load(file, allow_pickle=False) as data:
        pop = {k: data[k].copy() for k in ("x", "ids", "hash_route", "kmeans_route")}
    gate.require(pop["x"].shape == (1600, 2) and np.isfinite(pop["x"]).all(), "Coordinate shape")
    for kind in ("hash", "kmeans"):
        gate.require(np.array_equal(routers.route(pop["x"], policy, kind=kind), pop[kind + "_route"]),
                     "Cached routes differ from frozen policy")
    return pop, policy, {"data": gate.binding(file), "router": gate.binding(policy_file)}


def committed_output(commit_binding, root, schema):
    path = gate.verify_binding(commit_binding, root)
    commit, folder = gate.read(path), path.parent
    gate.require(commit.get("schema") == schema and commit.get("status") == "completed", "Invalid derived commit")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    gate.require(actual == set(commit["files"]) | {path.name}, "Derived output inventory differs")
    for relative, expected in commit["files"].items():
        file = (folder / relative).resolve()
        gate.require(file.is_relative_to(folder) and file != path and file.is_file() and
                     file.stat().st_size == expected["bytes"] and gate.sha(file) == expected["sha256"],
                     "Derived committed payload changed")
    return commit, folder


def finish(output, phase, verified, summary):
    output = Path(output)
    gate.require(sources(ROOT) == verified["registration"]["sources"], "Derived source drift")
    gate.verify_binding(verified["authorization"], ROOT)
    gate.verify_binding(verified["registration_binding"], ROOT)
    gate.verify_binding(verified["evaluation_commit"], ROOT)
    for key in ("deployment_protocol", "readiness_protocol", "run_matrix"):
        gate.verify_binding(verified["registration"][key], ROOT)
    gate.write_new(output / "summary.json", summary)
    files = {p.relative_to(output).as_posix(): {"sha256": gate.sha(p), "bytes": p.stat().st_size}
             for p in sorted(output.rglob("*")) if p.is_file()}
    gate.write_new(output / f"{phase.upper()}_COMMIT.json",
                   {"schema": f"qpath-v08-{phase}-commit-1", "status": "completed",
                    "authorization": verified["authorization"], "registration": verified["registration_binding"],
                    "evaluation_commit": verified["evaluation_commit"], "files": files})
