"""Fail-closed test-release verification. Never reads test arrays."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

EVALUATOR_FILES = ("gate.py", "metrics.py", "statistics_core.py", "priority_diagnostics.py",
                   "evaluate.py", "tests/test_official.py")
SCIENCE_FILES = ("models.py", "study.py", "circuits.py", "reference_v03.py",
                 "prepare_data.py", "routers.py", "sampling.py", "tests/test_v08_science.py",
                 "tests/test_routers_data.py")
EXECUTION_FILES = ("durable.py", "worker.py", "launcher.py", "process_identity.py",
                   "resource_probe.py", "bind_stage.py", "vendor/etel/core.py", "vendor/etel/__init__.py")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        import os
        os.fsync(stream.fileno())


def binding(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def verify_binding(item, root=None):
    path = Path(item["path"])
    require(path.is_absolute(), "Binding path must be absolute")
    path = path.resolve()
    if root is not None:
        require(path.is_relative_to(Path(root).resolve()), "Binding escapes study root")
    require(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
            f"Changed or missing bound file: {path}")
    return path


def current_sources(root):
    root = Path(root).resolve()
    paths = [root/"analysis/official_evaluation"/p for p in EVALUATOR_FILES]
    paths += [root/"quantum"/p for p in SCIENCE_FILES]
    paths += [root/"execution"/p for p in EXECUTION_FILES]
    return {p.relative_to(root).as_posix(): sha(p) for p in paths}


def make_freeze(root):
    """Source snapshot only. This function cannot authorize testing."""
    root = Path(root).resolve()
    return {"schema": "qpath-v08-evaluator-source-freeze-1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "test_access_authorized": False, "sources": current_sources(root),
            "analysis_protocol": binding(root/"governance/ANALYSIS_PROTOCOL.json"),
            "study_plan": binding(root/"governance/STUDY_PLAN.json"),
            "run_matrix": binding(root/"governance/RUN_MATRIX.json"),
            "status": "PREPARED_FOR_ROOT_REVIEW"}


def validate_release_header(release, matrix):
    require(release.get("schema") == "qpath-v08-test-release-1", "Unsupported or absent test release")
    require(release.get("review_status") == "approved_by_root", "Root test approval missing")
    require(release.get("stage") == "B" and release.get("test_access_authorized") is True,
            "Release is not a confirmation test release")
    require(release.get("latent_diagnostics_authorized") is True,
            "Explicit post-release latent diagnostic approval missing")
    require(release.get("all_confirmation_endpoints_independently_audited") is True,
            "Independent full confirmation audit missing")
    jobs = [j for j in matrix["runs"] if j["stage"] == "B"]
    require(len(jobs) == 640 and len({j["run_id"] for j in jobs}) == 640,
            "Exactly 640 unique registered confirmation endpoints required")
    require(release.get("run_ids") == [j["run_id"] for j in jobs], "Released IDs differ from exact registered order")
    require(all(j["rounds"] == 200 and j["updates"] == 15000 for j in jobs), "Confirmation budgets changed")
    return jobs


def verify_release(root, release_path, output, require_new_output=True):
    """Verify every prior scientific payload before caller is allowed to load tests."""
    root, release_path, output = Path(root).resolve(), Path(release_path).resolve(), Path(output).resolve()
    require(release_path.is_relative_to(root), "Root release must be retained inside study")
    release = read(release_path)
    jobs = validate_release_header(release, read(root/"governance/RUN_MATRIX.json"))
    require(Path(release.get("evaluation_output", "")).resolve() == output and output.is_relative_to(root/"analysis"),
            "Output must match the root-authorized new analysis directory")
    if require_new_output:
        require(not output.exists(), "Evaluation output already exists; preserve it and use explicit root recovery")
    for key, relative in (("analysis_protocol", "governance/ANALYSIS_PROTOCOL.json"),
                          ("study_plan", "governance/STUDY_PLAN.json"),
                          ("run_matrix", "governance/RUN_MATRIX.json"),
                          ("data_seal", "quantum/data/DATA_SEAL.json")):
        require(verify_binding(release[key], root) == root/relative, "Unexpected bound governance artifact")
    verify_binding(release["runtime_environment"], root)
    freeze_path = verify_binding(release["evaluator_freeze"], root)
    freeze = read(freeze_path)
    require(freeze.get("schema") == "qpath-v08-evaluator-source-freeze-1" and
            freeze.get("test_access_authorized") is False, "Missing pre-evaluation source freeze")
    require(freeze["sources"] == current_sources(root), "Evaluator/scientific/execution source drift")
    for key in ("analysis_protocol", "study_plan", "run_matrix"):
        require(freeze[key] == release[key], "Evaluator freeze governance differs from release")
    # Distinct retained audit files are required; root attests their author/independent roles.
    audit_paths = [verify_binding(release[k], root) for k in ("author_audit", "independent_audit")]
    require(audit_paths[0] != audit_paths[1] and release["author_audit"]["sha256"] != release["independent_audit"]["sha256"],
            "Distinct author and independent audit evidence required")
    sys.path.insert(0, str(root/"execution"))
    import durable
    audits = [read(p) for p in audit_paths]
    for audit in audits:
        require(audit.get("status") == "PASS" and audit.get("stage") == "B" and
                audit.get("verified_endpoints") == 640, "Incomplete confirmation audit")
        # This checks exact matrix identities, durable attempt bindings, full budgets,
        # and every current endpoint payload byte against the committed hashes.
        durable.verify_receipt_endpoints(root, audit, "B", 640)
    maps = [{e["job_id"]: e["commit"] for e in audit["endpoints"]} for audit in audits]
    require(maps[0] == maps[1], "Auditors did not bind the same exact selected attempts")
    science = {name: freeze["sources"]["quantum/"+name] for name in SCIENCE_FILES}
    for job in jobs:
        commit_path = Path(maps[0][job["run_id"]]["path"])
        commit = read(commit_path)
        require(commit["source_hashes"] == science, "Endpoint scientific sources differ from evaluator freeze")
        require(commit["data_seal_sha256"] == release["data_seal"]["sha256"] and
                commit["matrix_sha256"] == release["run_matrix"]["sha256"] and
                commit["protocol_sha256"] == release["study_plan"]["sha256"],
                "Endpoint and release bindings differ")
    return {"release": release, "release_binding": binding(release_path), "jobs": jobs,
            "endpoint_commits": maps[0], "source_freeze": freeze}


def validate_evaluation_commit_header(commit, verified):
    require(commit.get("schema") == "qpath-v08-evaluation-commit-1" and
            commit.get("status") == "completed" and commit.get("count") == 640,
            "Successful complete official evaluation commit required")
    require(commit.get("release") == verified["release_binding"], "Evaluation commit release differs")
    require(isinstance(commit.get("files"), dict), "Evaluation commit payload inventory missing")


def verify_evaluation_payloads(verified, output, commit_binding):
    """Read-only completed-output proof; never authorizes a different scoring directory."""
    output = Path(output).resolve()
    commit_path = verify_binding(commit_binding, output)
    require(commit_path == output/"EVALUATION_COMMIT.json", "Unexpected official evaluation commit path")
    commit = read(commit_path)
    validate_evaluation_commit_header(commit, verified)
    require(not (output/"EVALUATION_FAILURE.json").exists(), "Failed evaluation cannot authorize downstream work")
    required = {"EVALUATION_START.json", "summary.json", "endpoint_index.json", "primary_analysis.json",
                "descriptive_summary.json", "diagnostic_summary.json", "priority_summary.json"}
    for job in verified["jobs"]:
        required.update(f"endpoints/{job['run_id']}/{name}" for name in
                        ("metrics.json", "validation_predictions.npz", "test_predictions.npz",
                         "training_priority_evidence.npz"))
    require(required.issubset(commit["files"]), "Official evaluation is missing required endpoint evidence")
    for relative, expected in commit["files"].items():
        path = (output/relative).resolve()
        require(path.is_relative_to(output) and path != commit_path, "Invalid evaluation payload path")
        require(path.is_file() and path.stat().st_size == expected["bytes"] and sha(path) == expected["sha256"],
                f"Official evaluation payload changed: {relative}")
    actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    require(actual == set(commit["files"]) | {"EVALUATION_COMMIT.json"},
            "Unexpected or uncommitted official evaluation files")
    summary = read(output/"summary.json")
    require(summary.get("status") == "PASS" and summary.get("evaluated_endpoints") == 640 and
            summary.get("release") == verified["release_binding"], "Evaluation summary failed or differs")
    index = read(output/"endpoint_index.json")
    require(len(index) == 640 and [r["job_id"] for r in index] == [j["run_id"] for j in verified["jobs"]],
            "Completed evaluation endpoint index differs from registered order")
    for row in index:
        require(verify_binding(row["metrics"], output) == output/"endpoints"/row["job_id"]/"metrics.json",
                "Evaluation metric index binding differs")
    return binding(commit_path)


def verify_completed_evaluation(root, release_path, evaluation_commit_binding):
    """For downstream deployment/replay after scoring, with all original gates retained."""
    release = read(release_path)
    output = Path(release["evaluation_output"]).resolve()
    verified = verify_release(root, release_path, output, require_new_output=False)
    verified["evaluation_commit"] = verify_evaluation_payloads(verified, output, evaluation_commit_binding)
    verified["evaluation_output"] = str(output)
    return verified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a reviewable evaluator source snapshot, never a test release.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--freeze-output", required=True)
    args = parser.parse_args()
    write_new(args.freeze_output, make_freeze(args.root))
