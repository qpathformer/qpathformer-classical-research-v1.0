"""Metadata-only candidate evidence. Does not authorize or launch study work."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "execution"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def binding(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-name", default="EXECUTION_READINESS_v01.json")
    args = parser.parse_args()
    assert Path(args.output_name).name == args.output_name and args.output_name.endswith(".json")
    started, cpu = time.perf_counter(), time.process_time()
    imported = read(HERE / "V07_EXECUTION_IMPORT_v02.json")
    unchanged = []
    for entry in imported["files"]:
        current = binding(entry["source_path"])
        assert current["sha256"] == entry["source_sha256"]
        assert current["bytes"] == entry["source_bytes"]
        unchanged.append(current)
    vendor = read(HERE / "VENDOR_PROVENANCE.json")
    for entry in vendor["vendored_files"]:
        assert binding(HERE / entry["path"])["sha256"] == entry["sha256"]
    test_path = HERE / "test_runs/session_20261020T182339_b87e9851/TEST_RESULT.json"
    test = read(test_path)
    assert test["status"] == "PASS" and test["tests_run"] == 20 and test["skipped"] == 0
    for name, digest in test["source_hashes"].items():
        assert binding(HERE / name)["sha256"] == digest
    matrix_path, plan_path = ROOT / "governance/RUN_MATRIX.json", ROOT / "governance/STUDY_PLAN.json"
    matrix, plan = read(matrix_path), read(plan_path)
    groups = {stage: [x for x in matrix["runs"] if x["stage"] == stage]
              for stage in ("engineering", "A", "B")}
    assert {stage: len(rows) for stage, rows in groups.items()} == {"engineering": 40, "A": 80, "B": 640}
    for stage, rows in groups.items():
        assert len({j["arm"] for j in rows}) == 10
        assert {j["rounds"] for j in rows} == {12 if stage == "engineering" else 200}
        assert {j["updates"] for j in rows} == {900 if stage == "engineering" else 15000}
        assert {j["batch_size"] for j in rows} == {64}
        assert {j["sampling_policy"] for j in rows} == {"uniform", "priority"}
        assert len({j["base_model"] for j in rows}) == 5
    assert plan["execution_layer"]["resource_ceiling"] == 5
    assert plan["execution_layer"]["deadline_per_fit_seconds"] == 3600
    assert plan["runtime"]["scientific_python"] == r"C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe"
    assert plan["runtime"]["numpy_version"] == "2.5.4" and plan["runtime"]["blas_threads"] == 1
    fixture_inventory = []
    for database in Path(test["session_root"]).glob("execution_test_*/execution/state/ledger.sqlite3"):
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        try:
            rows = list(connection.execute("SELECT status,COUNT(*) FROM attempts GROUP BY status"))
            assert all(status in {"succeeded", "failed", "timed_out", "interrupted", "invalid_commit", "orphaned"}
                       for status, _ in rows)
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            fixture_inventory.append({"path": str(database), "terminal_counts": dict(rows), "integrity_check": "ok"})
        finally:
            connection.close()
    assert not (HERE / "state").exists() and not (HERE / "attempts").exists()
    assert not list(HERE.rglob("__pycache__"))
    source_names = [entry["relative_path"] for entry in imported["files"]] + ["prepare_readiness.py"]
    result = {
        "schema": "qpath-v08-execution-candidate-readiness-1",
        "status": "PASS_SYNTHETIC_AND_METADATA_ONLY_PENDING_ROOT_REVIEW",
        "utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Reviewed adaptation only. No scientific fits, official data generation, data reads, stage freeze or release.",
        "official_launch_authorized": False,
        "source_bindings": {name: binding(HERE / name) for name in source_names},
        "active_matrix": binding(matrix_path), "active_plan": binding(plan_path),
        "test_receipt": binding(test_path), "test_count": 20,
        "synthetic_cap_qualification": binding(Path(test["session_root"]) / "SYNTHETIC_CAP_QUALIFICATION.json"),
        "tested_caps": [1, 2, 5],
        "scientific_runtime_or_throughput_qualified_by_synthetic_suite": False,
        "changes": [
            "v0.8 execution manifest, attempt and stage-observation schemas; v0.8 scientific authorization and endpoint schema.",
            "Exact engineering/A/B inventories 40/80/640; same root-authorized predecessor and complete payload gates.",
            "Official execution root, active plan and active matrix must belong to this execution copy.",
            "Retained whole-fit subprocesses, SQLite claims/journal, PID plus creation identity, watchdog, no overwrite or automatic failed retry.",
            "Retained vendor bytes. Shared lease accepts audit/conversion/reproduction; finite-shot purpose is rejected.",
            "Four clean-directory reproduction fits require a separate future root workflow and are not launched by this layer.",
        ],
        "interfaces": {
            "manifest_schema": "qpath.v08.etel.bound-stage.v1",
            "authorization_schema": "qpath-v08-stage-authorization-1",
            "endpoint_schema": "qpath-v08-endpoint-1",
            "trainer_cli": "python -B -X utf8 quantum/study.py --job-id RUN_ID --output ABS_ABSENT --authorization ABS_ROOT_FREEZE",
            "release_fields": ["review_status=approved_by_root", "stage", "manifest_sha256", "predecessor_audit for A/B"],
            "audit_receipt": "PASS, stage, verified_endpoints, endpoints[{job_id,commit:{path,sha256,bytes}}]",
            "ledger": "jobs.current_attempt -> attempts metadata_dir/REQUEST.json and endpoint/endpoint_commit.json",
            "stage_counts": {"engineering": 40, "A": 80, "B": 640},
            "phase_budgets": {"engineering": {"rounds": 12, "updates": 900}, "A": {"rounds": 200, "updates": 15000},
                              "B": {"rounds": 200, "updates": 15000}},
        },
        "remaining_before_official_launch": [
            "Root and independent source review, final scientific source list/SETTINGS and source freeze.",
            "Fresh data, routers and DATA_SEAL authorized and independently audited.",
            "Historical environment snapshot with exact loaded DLL hash and effective BLAS threads one.",
            "Root scientific authorization, bound execution manifest and distinct root execution release.",
            "Scientific engineering/resource qualification before A; synthetic process-cap tests do not establish scientific speed or numerical equivalence.",
        ],
        "retained_preparation_failure": {
            "record": binding(HERE / "V07_EXECUTION_IMPORT_v01.json"),
            "recovery": binding(HERE / "V07_EXECUTION_IMPORT_v02.json"),
            "description": "PowerShell directory creation parameter-set error in initial explicit copy; v01 receipt superseded. Verified missing-file-only recovery; no source or scientific attempt lost.",
        },
        "read_only_v07_source_reverification": {"count": len(unchanged), "all_unchanged": True, "bindings": unchanged},
        "full_v07_payload_preservation": "Owned separately by root; this candidate verifies only the twelve reused source files.",
        "fixture_ledgers": fixture_inventory,
        "no_official_execution_state_created": True,
        "wall_seconds": time.perf_counter() - started,
        "coordinator_cpu_seconds": time.process_time() - cpu,
    }
    output = HERE / args.output_name
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(binding(output), indent=2))


if __name__ == "__main__":
    main()
