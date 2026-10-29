"""Synthetic derived-kernel/gate tests; official arrays/outcomes are never read."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
import zipfile
from unittest.mock import patch
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[key] = "1"
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "quantum"))
import numpy as np
import compiler
import fixtures
import producer
import support
import timing
import readiness_gates
import routers
from models import Model, ARM_METHODS

STREAMS = {"paired_circuit_core_initialization": 92731}
POLICY = {"schema": "qpath-v08-input-route-1", "banks": 5,
          "centroids": [[-.8, -.7], [-.8, .7], [0., 0.], [.8, -.7], [.8, .7]],
          "hash_salt": "SYNTHETIC_DEPLOYMENT_TEST_ONLY",
          "hash_cutpoints_hex": [f"{i * (2**256 // 5):064x}" for i in range(1, 5)]}


class DeploymentTests(unittest.TestCase):
    def test_readonly_available_memory_telemetry(self):
        memory = timing.available_memory()
        self.assertEqual(memory["source"], "Win32_GlobalMemoryStatusEx")
        self.assertGreater(memory["total_physical_bytes"], 0)
        self.assertGreaterEqual(memory["available_physical_bytes"], 0)
        self.assertLessEqual(memory["available_physical_bytes"], memory["total_physical_bytes"])
        self.assertTrue(0 <= memory["memory_load_percent"] <= 100)

    def test_all_active_metadata_and_schedule(self):
        matrix = support.gate.read(ROOT / "governance/RUN_MATRIX.json")
        jobs, populations, circuits = producer.confirmation_inventory(matrix)
        self.assertEqual((len(jobs), len(populations), len(circuits)), (640, 32, 256))
        schedule = timing.ordered_jobs(jobs, populations)
        self.assertEqual(schedule, timing.ordered_jobs(jobs, populations))
        for start in range(0, 80, 20):
            self.assertEqual(len({r["family"] for r in schedule[start:start + 20]}), 1)
        broken = copy.deepcopy(matrix)
        broken["runs"] = [r for r in broken["runs"] if r["run_id"] != jobs[0]["run_id"]]
        with self.assertRaises(RuntimeError):
            producer.confirmation_inventory(broken)

    def test_registered_stream_inventory(self):
        value = producer.registration(ROOT)
        self.assertEqual(len(value["circuit_run_ids"]),256)
        self.assertEqual(len(value["all_run_ids"]),640)
        self.assertNotIn("shot_streams",value)
        self.assertFalse(value["test_access_authorized"])
        self.assertEqual(value["timing"]["forward_calls_per_trial"], 1)

    def test_conversion_forced_banks_and_affine_readout(self):
        rng = np.random.default_rng(4918)
        x = rng.uniform(-1, 1, (19, 2))
        for method in compiler.METHODS:
            model = Model(method, 0, STREAMS)
            model.parameters[:] = rng.normal(0, .8, model.parameters.shape)
            coefficients = compiler.compile_model(method, model.parameters)
            for bank in range(5):
                route = np.full(len(x), bank, dtype=np.int64)
                p, z = model.predict_with_logits(x, route)
                converted = compiler.predict_compiled(x, coefficients, route)
                fixtures.parity(*converted, p, z)

    def test_optimized_control_and_instrumented_kernel_parity(self):
        x = np.random.default_rng(591).uniform(-1, 1, (32, 2))
        for method in ARM_METHODS.values():
            model = Model(method, 0, STREAMS)
            model.parameters[:] += np.random.default_rng(82).normal(0, .2, model.parameters.shape)
            route = None if model.routing == "global" else routers.route(x, POLICY, kind=model.routing)
            reference = model.predict_with_logits(x, route)
            coefficients = compiler.learned_trig_coefficients(method, model.parameters) if model.family.startswith("trig") else None
            forward = timing.make_forward(model, POLICY, coefficients)
            fixtures.parity(*forward(x), *reference)
            p, z, costs = timing.component_probe(model, POLICY, x, coefficients)
            fixtures.parity(p, z, *reference)
            self.assertTrue(all(costs[k] >= 0 for k in ("routing_ns", "feature_or_core_ns", "head_ns", "sigmoid_ns")))
            if model.quantum:
                coefficients = compiler.compile_model(method, model.parameters)
                fixtures.parity(*timing.make_forward(model, POLICY, coefficients)(x), *reference)
                p, z, _ = timing.component_probe(model, POLICY, x, coefficients)
                fixtures.parity(p, z, *reference)

    def test_fixture_geometry_and_determinism(self):
        offgrid, boundary, metadata = fixtures.parity_inputs(POLICY, 932)
        duplicate = fixtures.parity_inputs(POLICY, 932)
        np.testing.assert_array_equal(offgrid, duplicate[0])
        np.testing.assert_array_equal(boundary, duplicate[1])
        self.assertEqual(offgrid.shape, (128, 2))
        self.assertEqual(len(boundary), len(metadata))
        centers = np.array(POLICY["centroids"])
        for x, row in zip(boundary, metadata):
            if row["side"] == 0:
                distances = ((centers - x)**2).sum(axis=1)
                a, b = row["centroid_pair"]
                self.assertAlmostEqual(distances[a], distances[b], places=12)
                self.assertLessEqual(distances[a], distances.min() + 1e-12)
        hashes = routers.route(offgrid, POLICY, kind="hash")
        np.testing.assert_array_equal(hashes, routers.route(offgrid, POLICY, kind="hash"))

    def test_decision_tie_band_is_separate_from_numeric_tolerance(self):
        p, z = np.array([.5 + 1e-15]), np.array([4e-15])
        result = fixtures.parity(p, z, np.array([.5 - 1e-15]), -z)
        self.assertEqual(result["class_disagreements"], 1)
        with self.assertRaises(RuntimeError):
            fixtures.parity(np.array([.5 + 1e-13]), np.array([4e-13]),
                            np.array([.5 - 1e-13]), np.array([-4e-13]))
        with self.assertRaises(RuntimeError):
            fixtures.parity(np.array([.7]), np.array([1.]), np.array([.6]), np.array([.5]))

    def test_phase_gate_rejects_unapproved_wrong_output_and_parallel(self):
        output = str(ROOT / "analysis/SYNTHETIC_ONLY_NOT_CREATED")
        release = {"schema": "qpath-v08-deployment-release-1", "review_status": "approved_by_root",
                   "phase": "conversion", "output": output, "test_access_authorized": True,
                   "max_parallel_tasks": 1, "required_blas_threads": 1}
        support.validate_header(release, "conversion", output)
        for key, value in (("review_status", "pending"), ("phase", "shots"),
                           ("max_parallel_tasks", 2), ("test_access_authorized", False),
                           ("required_blas_threads", 2), ("output", str(ROOT / "analysis/DIFFERENT"))):
            broken = {**release, key: value}
            with self.assertRaises(RuntimeError):
                support.validate_header(broken, "conversion", output)
        timing.validate_session({"stage": "timing", "session": 1, "previous_session_commits": []}, 1)
        with self.assertRaises(RuntimeError):
            timing.validate_session({"stage": "timing", "session": 2, "previous_session_commits": []}, 2)
        binding = {"path": "SYNTHETIC", "sha256": "SYNTHETIC", "bytes": 0}
        audit = {"status": "PASS", "phase": "conversion", "circuit_endpoints": 256,
                 "representations_replayed": 640, "learned_trig_exact_repacks": 384,
                 "conversion_commit": binding}
        timing.validate_independent_conversion(audit, binding)
        for key, value in (("circuit_endpoints", 255), ("status", "FAIL"),
                           ("representations_replayed", 192), ("conversion_commit", {})):
            with self.assertRaises(RuntimeError):
                timing.validate_independent_conversion({**audit, key: value}, binding)

    def test_completed_gate_keeps_distinct_authorizations(self):
        """Mock gate return only; genuine completed-release guard is independently tested."""
        with tempfile.TemporaryDirectory(prefix="qpath_synthetic_gate_") as temporary:
            root = Path(temporary)
            (root / "analysis").mkdir()
            (root / "governance").mkdir()
            for name in ("DEPLOYMENT_PROTOCOL.json", "LOCAL_READINESS_PROTOCOL.json", "RUN_MATRIX.json"):
                support.gate.write_new(root / "governance" / name, {})
            environment = dict.fromkeys(("python", "interpreter", "numpy_version", "openblas_dll_sha256",
                                         "openblas_config", "gpu_used"), "SYNTHETIC")
            environment["effective_blas_threads"] = 1
            support.gate.write_new(root / "environment.json", environment)
            support.gate.write_new(root / "evaluation_release.json", {"identity": "EVALUATION"})
            registration = {"schema": "qpath-v08-deployment-registration-1", "sources": {}, "test_access_authorized": False,
                "circuit_run_ids": [str(i) for i in range(256)],
                "all_run_ids": [str(i) for i in range(640)],
                **{key: support.gate.binding(root / "governance" / filename) for key, filename in
                   (("deployment_protocol", "DEPLOYMENT_PROTOCOL.json"),
                    ("readiness_protocol", "LOCAL_READINESS_PROTOCOL.json"), ("run_matrix", "RUN_MATRIX.json"))}}
            support.gate.write_new(root / "registration.json", registration)
            output = root / "analysis/new_output"
            authorization = {"schema": "qpath-v08-deployment-release-1", "review_status": "approved_by_root",
                "phase": "conversion", "output": str(output), "test_access_authorized": True,
                "max_parallel_tasks": 1, "required_blas_threads": 1,
                "registration": support.gate.binding(root / "registration.json"),
                "evaluation_release": support.gate.binding(root / "evaluation_release.json"),
                "evaluation_commit": {"identity": "MOCK_NO_OFFICIAL_IO"}}
            support.gate.write_new(root / "authorization.json", authorization)
            evaluation = {"identity": "EVALUATION", "runtime_environment": {"path": str(root / "environment.json")}}
            fake = {"release": evaluation, "jobs": [
                {"run_id":str(i),"arm":"MultiK_U" if i<256 else "TrigK_U"} for i in range(640)]}
            with patch.object(support, "sources", return_value={}), patch.object(
                    support.gate, "verify_completed_evaluation", return_value=fake), patch.object(
                    readiness_gates, "verify_score_replay", return_value=None), patch.dict(
                    sys.modules, {"resource_probe": types.SimpleNamespace(inspect=lambda: environment)}):
                result = support.verify(root, root / "authorization.json", output, "conversion")
            self.assertEqual(result["derived_release"], authorization)
            self.assertEqual(result["release"], evaluation)
            self.assertNotEqual(result["derived_release"], result["release"])

    def test_missing_peer_commits_are_fail_closed(self):
        with self.assertRaises((RuntimeError,KeyError)):
            readiness_gates.verify_score_replay(ROOT,{},{"jobs":[]})
        with self.assertRaises((RuntimeError,KeyError)):
            readiness_gates.verify_reproduction(ROOT,{},{"jobs":[]})

    def test_full_reference_inventory_and_order_gate(self):
        """Hash-only synthetic files; no real NPZ/model/data content."""
        parent=HERE/"synthetic_fixtures";parent.mkdir(exist_ok=True)
        folder=Path(tempfile.mkdtemp(prefix="NOTSTUDY_reference_gate_",dir=parent))
        ids=[f"B/NOTSTUDY_{i:04d}/seed_0/arm" for i in range(640)]
        rows=[];files={}
        for identity in ids:
            row={"job_id":identity,"splits":{}}
            for split in ("validation","test"):
                path=folder/"predictions"/identity/(split+"_reference.npz")
                path.parent.mkdir(parents=True,exist_ok=True)
                with zipfile.ZipFile(path,"x") as archive:
                    archive.writestr("SYNTHETIC_METADATA_ONLY.txt","No arrays, coordinates or model outputs.")
                item=support.gate.binding(path)
                row["splits"][split]={"prediction_binding":item}
                files[path.relative_to(folder).as_posix()]={k:item[k] for k in ("sha256","bytes")}
            rows.append(row)
        commit={"files":files}
        readiness_gates.validate_reference_inventory(folder,commit,rows,ids)
        conversion_rows=[{"job_id":r["job_id"],"splits":{"validation":{},"test":{}}} for r in rows]
        readiness_gates.validate_reference_inventory(folder,commit,conversion_rows,ids,bound_predictions=False)
        bad_rows=(rows[:-1],[rows[0],*rows[:-1]],list(reversed(rows)))
        for bad in bad_rows:
            with self.assertRaisesRegex(RuntimeError,"identities"):
                readiness_gates.validate_reference_inventory(folder,commit,bad,ids)
        missing={"files":dict(list(files.items())[1:])}
        with self.assertRaisesRegex(RuntimeError,"payload inventory"):
            readiness_gates.validate_reference_inventory(folder,missing,rows,ids)
        bad=copy.deepcopy(rows);bad[0]["splits"]["test"]["prediction_binding"]=bad[0]["splits"]["validation"]["prediction_binding"]
        with self.assertRaisesRegex(RuntimeError,"binding changed"):
            readiness_gates.validate_reference_inventory(folder,commit,bad,ids)

    def test_process_identity_uses_pid_and_creation_token(self):
        a={"pid":123,"creation_token":"456","identity_source":"one"}
        b={"pid":123,"creation_token":"456","identity_source":"two"}
        self.assertEqual(timing.process_key(a),timing.process_key(b))

    def test_all_prior_session_prerequisites_are_identical(self):
        fields=("registration","evaluation_release","evaluation_commit","independent_score_replay_commit",
                "conversion_commit","independent_conversion_commit","independent_conversion_audit",
                "reproduction_commit","independent_reproduction_commit","independent_reproduction_audit")
        current={key:{"path":"SYNTHETIC/"+key,"sha256":"fixed","bytes":1} for key in fields}
        current["previous_session_commits"]=[{"session":1},{"session":2}]
        for number in (1,2):
            prior={**current,"previous_session_commits":current["previous_session_commits"][:number-1]}
            timing.validate_prior_chain(prior,current,number)
            for key in fields:
                with self.subTest(session=number,key=key),self.assertRaisesRegex(RuntimeError,"readiness chain"):
                    timing.validate_prior_chain({**prior,key:{"path":"DIFFERENT"}},current,number)
            with self.assertRaisesRegex(RuntimeError,"readiness chain"):
                timing.validate_prior_chain({**prior,"previous_session_commits":[{"changed":True}]},current,number)


if __name__ == "__main__":
    unittest.main()
