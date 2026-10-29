"""Synthetic execution tests; official training cannot be invoked by this suite."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import durable as d
from process_identity import alive

SESSION = HERE/"test_runs"/("session_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8])
SESSION.mkdir(parents=True)


def fixture(action="success", count=1, deadline=10, sleep=1.5, row_stage="engineering", max_parallel=None):
    root = SESSION/("execution_test_"+uuid.uuid4().hex)
    root.mkdir()
    trainer = root/"synthetic_trainer.py"
    shutil.copyfile(HERE/"tests/synthetic_trainer.py", trainer)
    matrix_path, protocol_path = root/"matrix.json", root/"protocol.json"
    phase = d.physical_stage(row_stage)
    jobs = [{"run_id": f"{row_stage}/fixture/seed_1/arm_{i}", "stage": row_stage, "arm": f"arm_{i}",
             "population_id": "fixture", "training_seed_id": 1, "rounds": 2, "updates": 150,
             "fixture_action": action, "fixture_sleep_seconds": sleep} for i in range(count)]
    d.write_new(matrix_path, {"runs": jobs})
    d.write_new(protocol_path, {"scope": "SYNTHETIC_ONLY"})
    auth = root/"authorization.json"
    d.write_new(auth, {"schema": d.AUTHORIZATION_SCHEMA, "review_status": "approved_by_root",
        "stage": phase, "run_ids": [j["run_id"] for j in jobs],
        "matrix_sha256": d.sha(matrix_path), "protocol_sha256": d.sha(protocol_path)})
    manifest_path = root/"manifest.json"
    manifest = {"schema": d.MANIFEST_SCHEMA, "mode": "EXECUTION_TEST_FIXTURE_ONLY",
        "study_root": str(root), "stage": phase, "max_parallel_tasks": min(count,2) if max_parallel is None else max_parallel,
        "deadline_seconds": deadline, "interpreter": d.binding(sys.executable), "trainer": d.binding(trainer),
        "authorization": d.binding(auth), "matrix": d.binding(matrix_path), "protocol": d.binding(protocol_path),
        "bindings": [], "jobs": jobs}
    d.write_new(manifest_path, manifest)
    release = root/"release.json"
    d.write_new(release, {"review_status": "approved_by_root", "stage": phase,
                          "manifest_sha256": d.sha(manifest_path)})
    return root, manifest_path, release, jobs


def start(root, manifest, release):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    out = (root/f"coordinator_{uuid.uuid4().hex}.log").open("x")
    command = [sys.executable, "-B", str(HERE/"launcher.py"), "run", "--manifest", str(manifest), "--release", str(release)]
    child = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT, env=env,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    out.close()
    return child


def await_running(root, timeout=5):
    start_time = time.monotonic()
    while time.monotonic()-start_time < timeout:
        rows = d.current_attempts(root)
        if any(x["status"] == "running" for x in rows):
            return rows
        time.sleep(0.03)
    raise AssertionError("No running scientific child fixture observed")


def invocations(root):
    path = root/"invocations.jsonl"
    return [] if not path.exists() else [json.loads(x) for x in path.read_text().splitlines()]


class ExecutionTests(unittest.TestCase):
    def test_v07_manifest_and_authorization_are_rejected_without_launch(self):
        for field in ("manifest", "authorization"):
            root, manifest, release, _ = fixture()
            item = d.read(manifest)
            if field == "manifest":
                item["schema"] = "qpath.etel.bound-stage.v1"
            else:
                auth = root/"authorization.json"
                authorization = d.read(auth)
                authorization["schema"] = "qpath-v07-stage-authorization-1"
                auth.write_text(json.dumps(authorization))
                item["authorization"] = d.binding(auth)
            manifest.write_text(json.dumps(item))
            gate = d.read(release)
            gate["manifest_sha256"] = d.sha(manifest)
            release.write_text(json.dumps(gate))
            with self.assertRaises(RuntimeError):
                d.run_stage(manifest, release)
            self.assertEqual(invocations(root), [])

    def test_official_foreign_root_is_rejected_without_ledger_or_launch(self):
        root, manifest, release, _ = fixture()
        item = d.read(manifest)
        item["mode"] = "OFFICIAL_STUDY"
        manifest.write_text(json.dumps(item))
        gate = d.read(release)
        gate["manifest_sha256"] = d.sha(manifest)
        release.write_text(json.dumps(gate))
        with self.assertRaisesRegex(RuntimeError, "Official execution root differs"):
            d.run_stage(manifest, release)
        self.assertFalse((root/"execution/state").exists())
        self.assertEqual(invocations(root), [])

    def test_process_caps_one_two_five_use_identical_recipes_and_outputs(self):
        observations = []
        for cap in (1, 2, 5):
            root, manifest, release, jobs = fixture("sleep", count=6, sleep=0.15, max_parallel=cap)
            result = d.run_stage(manifest, release)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(len(invocations(root)), 6)
            db = d.connect(root)
            events = list(db.execute("SELECT event FROM journal ORDER BY sequence"))
            db.close()
            live, peak = 0, 0
            for event in events:
                if event["event"] == "scientific_process_owned":
                    live += 1
                    peak = max(peak, live)
                elif event["event"] in d.TERMINAL:
                    live -= 1
            self.assertEqual(live, 0)
            self.assertLessEqual(peak, cap)
            predictions = {r["job_id"]: (Path(r["endpoint"])/"prediction.txt").read_text()
                           for r in d.current_attempts(root)}
            observations.append({"cap": cap, "peak_owned_children": peak, "root": str(root),
                                 "recipes_sha256": d.value_sha(jobs), "predictions": predictions})
        self.assertEqual(len({x["recipes_sha256"] for x in observations}), 1)
        self.assertTrue(all(x["predictions"] == observations[0]["predictions"] for x in observations))
        d.write_new(SESSION/"SYNTHETIC_CAP_QUALIFICATION.json", {
            "status": "PASS", "scope": "File-writing fixtures only; no scientific throughput or numerical equivalence claim",
            "observations": observations})

    def test_cap_above_five_is_rejected_without_launch(self):
        root, manifest, release, _ = fixture(max_parallel=6)
        with self.assertRaisesRegex(RuntimeError, "concurrency"):
            d.run_stage(manifest, release)
        self.assertEqual(invocations(root), [])

    def test_auxiliary_leases_exclude_other_work_and_reject_shots(self):
        root, _, _, _ = fixture()
        with d.auxiliary_lease(root, "audit"):
            for purpose in ("audit", "conversion", "reproduction"):
                with self.assertRaises(RuntimeError):
                    with d.auxiliary_lease(root, purpose):
                        self.fail("A second numerical phase acquired the lease")
        with self.assertRaises(RuntimeError):
            with d.auxiliary_lease(root, "shots"):
                self.fail("v0.8 has no finite-shot phase")

    @unittest.skipUnless((HERE.parent/"governance/RUN_MATRIX.json").is_file(), "Root is still preparing the v0.8 matrix")
    def test_actual_matrix_stage_binding_is_40_80_640_without_execution(self):
        matrix = d.read(HERE.parent/"governance/RUN_MATRIX.json")
        groups = {stage: d.stage_jobs(matrix, stage) for stage in ("engineering", "A", "B")}
        self.assertEqual({k: len(v) for k, v in groups.items()}, {"engineering": 40, "A": 80, "B": 640})
        self.assertEqual(len({j["run_id"] for group in groups.values() for j in group}), 760)
        for stage, jobs in groups.items():
            self.assertEqual({j["rounds"] for j in jobs}, {12 if stage == "engineering" else 200})
            self.assertEqual({j["updates"] for j in jobs}, {900 if stage == "engineering" else 15000})
            self.assertEqual(len({j["arm"] for j in jobs}), 10)
        self.assertEqual({d.physical_stage(j["stage"]) for j in groups["A"]}, {"A"})
        self.assertEqual({d.physical_stage(j["stage"]) for j in groups["B"]}, {"B"})

    def test_alias_commit_and_strict_audit_identity_payloads(self):
        root, manifest, release, jobs = fixture(row_stage="development")
        self.assertEqual(d.run_stage(manifest, release)["status"], "completed")
        (root/"governance").mkdir()
        shutil.copyfile(root/"matrix.json", root/"governance/RUN_MATRIX.json")
        row = d.current_attempts(root)[0]
        commit = Path(row["endpoint"])/"endpoint_commit.json"
        receipt = {"endpoints": [{"job_id": jobs[0]["run_id"], "commit": d.binding(commit)}]}
        d.verify_receipt_endpoints(root, receipt, "A", 1)
        wrong = json.loads(json.dumps(receipt))
        wrong["endpoints"][0]["job_id"] = "wrong-registered-identity"
        with self.assertRaises(RuntimeError):
            d.verify_receipt_endpoints(root, wrong, "A", 1)
        (Path(row["endpoint"])/"prediction.txt").write_text("mutated")
        with self.assertRaises(RuntimeError):
            d.verify_receipt_endpoints(root, receipt, "A", 1)

    def test_success_reconciliation_never_repeats(self):
        root, manifest, release, _ = fixture(count=3)
        self.assertEqual(d.run_stage(manifest, release)["status"], "completed")
        self.assertEqual(d.run_stage(manifest, release)["status"], "completed")
        self.assertEqual(len(invocations(root)), 3)
        self.assertTrue(all(x["status"] == "succeeded" for x in d.current_attempts(root)))

    def test_pending_claim_before_launch_is_safely_reused(self):
        root, manifest, release, jobs = fixture()
        row = d.new_attempt(root, manifest, release, jobs[0])
        self.assertEqual(row["status"], "launch_pending")
        self.assertEqual(d.run_stage(manifest, release)["status"], "completed")
        self.assertEqual(len(invocations(root)), 1)
        self.assertEqual(d.current_attempts(root)[0]["attempt_id"], row["attempt_id"])

    def test_restarted_orchestrator_adopts_live_child(self):
        root, manifest, release, jobs = fixture("sleep", count=3, sleep=1.5)
        parent = start(root, manifest, release)
        before = await_running(root)
        identities = [json.loads(x["identity_json"]) for x in before if x["status"] == "running"]
        parent.kill()
        parent.wait(timeout=5)
        self.assertTrue(any(alive(x) for x in identities))
        replacement = start(root, manifest, release)
        self.assertEqual(replacement.wait(timeout=10), 0)
        self.assertEqual(len(invocations(root)), 3)
        self.assertEqual(len({x["job_id"] for x in invocations(root)}), 3)
        self.assertTrue(all(x["status"] == "succeeded" for x in d.current_attempts(root)))

    def test_concurrent_coordinator_refused(self):
        root, manifest, release, _ = fixture("sleep", sleep=1)
        first = start(root, manifest, release)
        await_running(root)
        second = start(root, manifest, release)
        self.assertNotEqual(second.wait(timeout=5), 0)
        self.assertEqual(first.wait(timeout=8), 0)
        self.assertEqual(len(invocations(root)), 1)

    def test_nonzero_preserves_failure_and_blocks_retry(self):
        root, manifest, release, _ = fixture("nonzero")
        self.assertEqual(d.run_stage(manifest, release)["status"], "failures_present")
        row = d.current_attempts(root)[0]
        self.assertEqual(row["status"], "failed")
        self.assertEqual((Path(row["endpoint"])/"partial.txt").read_text(), "preserved")
        with self.assertRaises(RuntimeError):
            d.run_stage(manifest, release)
        self.assertEqual(len(invocations(root)), 1)

    def test_deadline_survives_parent_loss(self):
        root, manifest, release, _ = fixture("sleep", deadline=0.6, sleep=3)
        parent = start(root, manifest, release)
        rows = await_running(root)
        parent.kill()
        parent.wait(timeout=5)
        time.sleep(0.9)
        row = d.current_attempts(root)[0]
        self.assertEqual(row["status"], "timed_out")
        self.assertFalse(alive(json.loads(row["identity_json"])))
        self.assertEqual(len(invocations(root)), 1)

    def test_cancel_preserves_interrupted_attempt(self):
        root, manifest, release, _ = fixture("sleep", sleep=3)
        parent = start(root, manifest, release)
        row = await_running(root)[0]
        d.request_cancel(root, row["attempt_id"], "synthetic_interrupt_test")
        self.assertNotEqual(parent.wait(timeout=5), 0)
        row = d.current_attempts(root)[0]
        self.assertEqual(row["status"], "interrupted")
        self.assertFalse(alive(json.loads(row["identity_json"])))

    def test_root_recovery_uses_fresh_attempt_same_recipe(self):
        root, manifest, release, jobs = fixture("fail_once")
        self.assertEqual(d.run_stage(manifest, release)["status"], "failures_present")
        old = d.current_attempts(root)[0]
        approval = root/"recovery.json"
        d.write_new(approval, {"review_status": "approved_by_root", "job_id": jobs[0]["run_id"],
            "previous_attempt_id": old["attempt_id"], "manifest_sha256": d.sha(manifest),
            "recipe_sha256": d.value_sha(jobs[0]), "recovery_action": "fresh_same_recipe_attempt"})
        new = d.new_attempt(root, manifest, release, jobs[0], approval)
        self.assertNotEqual(new["attempt_id"], old["attempt_id"])
        self.assertEqual(d.run_stage(manifest, release)["status"], "completed")
        self.assertTrue((Path(old["endpoint"])/"partial.txt").exists())
        self.assertEqual(len(invocations(root)), 2)

    def test_mismatched_manifest_has_no_launch(self):
        root, manifest, release, _ = fixture()
        data = d.read(manifest)
        data["jobs"][0]["updates"] = 999
        manifest.write_text(json.dumps(data))
        with self.assertRaises(RuntimeError):
            d.run_stage(manifest, release)
        self.assertEqual(invocations(root), [])

    def test_mutated_bound_source_has_no_launch(self):
        root, manifest, release, _ = fixture()
        (root/"synthetic_trainer.py").write_text("raise RuntimeError('unapproved source')")
        with self.assertRaises(RuntimeError):
            d.run_stage(manifest, release)
        self.assertEqual(invocations(root), [])

    def test_changed_completed_payload_is_not_retrained(self):
        root, manifest, release, _ = fixture()
        self.assertEqual(d.run_stage(manifest, release)["status"], "completed")
        row = d.current_attempts(root)[0]
        (Path(row["endpoint"])/"prediction.txt").write_text("changed")
        with self.assertRaises(RuntimeError):
            d.run_stage(manifest, release)
        self.assertEqual(len(invocations(root)), 1)

    def test_timing_refuses_live_training(self):
        root, manifest, release, _ = fixture("sleep", sleep=1.2)
        parent = start(root, manifest, release)
        await_running(root)
        timing = root/"timing_release.json"
        d.write_new(timing, {"review_status": "approved_by_root", "stage": "timing"})
        with self.assertRaises(RuntimeError):
            with d.timing_lease(root, timing):
                self.fail("Timing entered with active study")
        self.assertEqual(parent.wait(timeout=5), 0)

    def test_audit_gate_requires_enumerated_matching_endpoints(self):
        with self.assertRaises(RuntimeError):
            d.verify_receipt_endpoints(SESSION, {"endpoints": []}, "B", 640)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ExecutionTests)
    started_utc, wall, cpu = d.now(), time.perf_counter(), time.process_time()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    evidence = {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "session_root": str(SESSION),
        "skipped": len(result.skipped), "started_utc": started_utc, "finished_utc": d.now(),
        "wall_seconds": time.perf_counter()-wall, "coordinator_cpu_seconds": time.process_time()-cpu,
        "scope": "Synthetic children only; no scientific models, official data or full study",
        "official_fits": 0, "source_hashes": {p.relative_to(HERE).as_posix(): d.sha(p)
            for p in [HERE/"durable.py", HERE/"worker.py", HERE/"launcher.py", HERE/"process_identity.py",
                      HERE/"resource_probe.py", HERE/"bind_stage.py", Path(__file__), HERE/"tests/synthetic_trainer.py"]}}
    d.write_new(SESSION/"TEST_RESULT.json", evidence)
    print(json.dumps(evidence, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
