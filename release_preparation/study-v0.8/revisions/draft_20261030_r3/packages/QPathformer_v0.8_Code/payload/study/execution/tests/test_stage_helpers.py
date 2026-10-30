"""Stdlib-only stage-gate fixtures. Never call build/main/launch or load model data."""
from datetime import datetime, timezone
import copy
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "governance"))
import freeze_engineering as gate
import freeze_full_stage as full

SESSION = ROOT / "execution/test_runs" / ("stage_gates_" + uuid.uuid4().hex[:12])
SESSION.mkdir(parents=True)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture():
    root = SESSION / ("fixture_" + uuid.uuid4().hex[:10])
    root.mkdir()
    matrix = gate.read(ROOT / "governance/RUN_MATRIX.json")
    plan = gate.read(ROOT / "governance/STUDY_PLAN.json")
    write(root / "governance/RUN_MATRIX.json", matrix)
    write(root / "governance/STUDY_PLAN.json", plan)
    write(root / "quantum/data/DATA_SEAL.json", {"fixture": True})
    for directory, names in (("governance", gate.HELPERS), ("execution", gate.EXECUTION), ("quantum", ["study.py"])):
        for name in names:
            path = root / directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# synthetic inert source; never imported\n", encoding="utf-8")
    dll = root / "fixture.dll"
    dll.write_bytes(b"not a library; never loaded")
    environment = {"interpreter": plan["runtime"]["scientific_python"],
                   "python": plan["runtime"]["scientific_python_version"], "numpy_version": "2.5.4",
                   "effective_blas_threads": 1, "openblas_dll": str(dll), "openblas_dll_sha256": gate.sha(dll)}
    write(root / "environment.json", environment)
    execution = {name: gate.sha(root / "execution" / name) for name in gate.EXECUTION}
    science = {"study.py": gate.sha(root / "quantum/study.py")}
    settings = {"fixture": True}
    peer_path = root / "reviews/execution_peer_review.json"
    write(peer_path, {"status": "PASS_SOURCE_REVIEW", "source_bindings": [
        gate.binding(root / "execution" / name) for name in gate.EXECUTION]})
    reviews = {
        "scientific_root_review": {"status": "PASS", "reviewed_by_root": True,
                                  "scientific_source_hashes": science, "settings": settings},
        "scientific_tests": {"status": "PASS", "source_sha256": science},
        "execution_root_review": {"status": "PASS", "reviewed_by_root": True,
                                  "execution_source_sha256": execution, "peer_review": gate.binding(peer_path)},
        "independent_data_review": {"status": "PASS", "data_seal_sha256": gate.sha(root / "quantum/data/DATA_SEAL.json")},
        "resource_review": {"status": "PASS", "reviewed_by_root": True, "selected_cap": 5,
                            "effective_blas_threads": 1, "environment": gate.binding(root / "environment.json"),
                            "execution_source_sha256": execution},
        "prior_preservation": {"status": "PASS", "phase": "before"},
    }
    for name, value in reviews.items():
        write(root / "reviews" / (name + ".json"), value)
    request = {"schema": "qpath-v08-stage-build-request-1", "review_status": "approved_by_root",
               "stage": "engineering", "study_root": str(root), "max_parallel_tasks": 5,
               "matrix": gate.binding(root / "governance/RUN_MATRIX.json"),
               "protocol": gate.binding(root / "governance/STUDY_PLAN.json"),
               "data_seal": gate.binding(root / "quantum/data/DATA_SEAL.json"),
               "environment": gate.binding(root / "environment.json"),
               "helper_source_sha256": {name: gate.sha(root / "governance" / name) for name in gate.HELPERS},
               "execution_source_sha256": execution, "scientific_source_hashes": science, "settings": settings,
               "reviews": {name: gate.binding(root / "reviews" / (name + ".json")) for name in gate.REVIEW_KEYS}}
    path = root / "governance/fixture_request.json"
    write(path, request)
    return root, path, request


class StageHelperTests(unittest.TestCase):
    def test_active_matrix_exact_inventory_and_budgets(self):
        matrix = gate.read(ROOT / "governance/RUN_MATRIX.json")
        self.assertEqual({stage: len(gate.validate_jobs(matrix, stage)) for stage in gate.COUNTS},
                         {"engineering": 40, "A": 80, "B": 640})
        mutated = copy.deepcopy(matrix)
        mutated["runs"][0]["updates"] = 150
        with self.assertRaisesRegex(RuntimeError, "budgets"):
            gate.validate_jobs(mutated, "engineering")
        duplicate = copy.deepcopy(matrix)
        duplicate["runs"][1] = duplicate["runs"][0]
        with self.assertRaisesRegex(RuntimeError, "inventory"):
            gate.validate_jobs(duplicate, "engineering")

    def test_valid_request_is_metadata_only(self):
        root, path, expected = fixture()
        request, jobs = gate.validate_request(root, path, "engineering")
        self.assertEqual(request, expected)
        self.assertEqual(len(jobs), 40)
        self.assertFalse((root / "quantum/ENGINEERING_FREEZE.json").exists())
        self.assertFalse((root / "execution/state").exists())

    def test_request_cannot_approve_itself_or_change_stage(self):
        for field, value in (("review_status", "candidate"), ("stage", "A"), ("schema", "qpath-v07-stage-build-request-1")):
            root, path, request = fixture()
            request[field] = value
            write(path, request)
            with self.assertRaises(RuntimeError):
                gate.validate_request(root, path, "engineering")

    def test_stale_scientific_execution_helper_or_environment_binding(self):
        for relative in ("quantum/study.py", "execution/worker.py", "governance/launch_stage.ps1", "fixture.dll"):
            root, path, _ = fixture()
            (root / relative).write_bytes(b"changed fixture")
            with self.assertRaises(RuntimeError):
                gate.validate_request(root, path, "engineering")

    def test_rehashed_review_cannot_change_sources_data_or_cap(self):
        for name, field, value in (
            ("scientific_tests", "source_sha256", {}),
            ("scientific_root_review", "settings", {"changed": True}),
            ("execution_root_review", "execution_source_sha256", {}),
            ("independent_data_review", "data_seal_sha256", "0" * 64),
            ("resource_review", "selected_cap", 4),
        ):
            root, path, request = fixture()
            review_path = Path(request["reviews"][name]["path"])
            changed = gate.read(review_path)
            changed[field] = value
            write(review_path, changed)
            request["reviews"][name] = gate.binding(review_path)
            write(path, request)
            with self.assertRaises(RuntimeError):
                gate.validate_request(root, path, "engineering")

    def test_both_audits_require_exact_ids_hashes_bytes(self):
        rows = [{"job_id": "fixture-" + str(i), "commit": {"path": f"fixture/{i}/commit.json",
                 "sha256": f"{i:064x}", "bytes": i + 1}} for i in range(40)]
        first = {"endpoints": rows}
        full.compare_audit_commits(first, copy.deepcopy(first), 40)
        for field in ("job_id", "sha256", "bytes", "path"):
            second = copy.deepcopy(first)
            if field == "job_id":
                second["endpoints"][0]["job_id"] = "different"
            else:
                second["endpoints"][0]["commit"][field] = "different"
            with self.assertRaises(RuntimeError):
                full.compare_audit_commits(first, second, 40)
        with self.assertRaises(RuntimeError):
            full.compare_audit_commits(first, {"endpoints": rows[:-1]}, 40)

    def test_sealed_payload_hash_inventory_without_loading_arrays(self):
        root = SESSION / ("payload_" + uuid.uuid4().hex[:10])
        data = root / "quantum/data"
        data.mkdir(parents=True)
        seal = {"datasets": {}, "files": {}, "routers": {}, "diagnostics": {}}
        for i in range(40):
            pop = f"fixture_{i}"
            seal["datasets"][pop] = {}
            for split in ("train", "validation", "SEALED_test"):
                name = f"{pop}_{split}.npz"
                (data / name).write_bytes(b"inert fixture; not an array")
                seal["files"][name] = {"sha256": gate.sha(data / name)}
            for group, suffix in (("routers", "_router.json"), ("diagnostics", "_SEALED_diagnostics.npz")):
                name = pop + suffix
                (data / name).write_bytes(b"inert fixture")
                seal[group][pop] = {"file": name, "sha256": gate.sha(data / name)}
        gate.verify_data_payloads(root, seal)
        (data / "fixture_1_SEALED_test.npz").write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "Data payload differs"):
            gate.verify_data_payloads(root, seal)

    def test_source_paths_cannot_escape_source_directory(self):
        root, _, _ = fixture()
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            gate.source_hashes(root, "quantum", {"../fixture.dll": gate.sha(root / "fixture.dll")})


if __name__ == "__main__":
    wall, cpu = time.perf_counter(), time.process_time()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StageHelperTests))
    receipt = {"schema": "qpath-v08-stage-helper-synthetic-1", "status": "PASS" if result.wasSuccessful() else "FAIL",
               "utc": datetime.now(timezone.utc).isoformat(), "tests_run": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors),
               "wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
               "scope": "Synthetic metadata and inert byte fixtures only; no build, release, trainer import, official payload or model access.",
               "official_releases_created": 0, "official_fits": 0, "session": str(SESSION),
               "sources": {name: gate.binding(ROOT / "governance" / name) for name in gate.HELPERS},
               "test_source": gate.binding(__file__), "active_matrix": gate.binding(ROOT / "governance/RUN_MATRIX.json"),
               "active_protocol": gate.binding(ROOT / "governance/STUDY_PLAN.json")}
    write(SESSION / "TEST_RESULT.json", receipt)
    print(json.dumps(gate.binding(SESSION / "TEST_RESULT.json"), indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
