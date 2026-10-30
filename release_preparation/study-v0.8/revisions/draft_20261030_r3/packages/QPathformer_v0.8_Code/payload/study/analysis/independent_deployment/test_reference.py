"""Bounded synthetic independent deployment checks; no data/checkpoint loads."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import reference as ref
import verify_arrays as verify
sys.path.insert(0, str(ROOT/"analysis/deployment"))
import compiler
sys.path.insert(0, str(ROOT/"quantum"))
import routers
from models import Model

POINTS = np.array([[-.913, .217], [.123, -.789], [.998, -.004], [0., 0.],
                   [-1., 1.], [.333, .555], [-.002, -.999], [.51, -.49]], dtype=np.float64)


class LaurentTests(unittest.TestCase):
    def test_zero_core_state_at_origin(self):
        state = ref.dense_states([[0, 0]], np.zeros((2, 2, 2)))
        np.testing.assert_array_equal(state, [[1, 0, 0, 0]])
        np.testing.assert_allclose(ref.dense_moments([[0, 0]], np.zeros((2, 2, 2))), [[0, 0, 1, 1, 1]], atol=0.)

    def test_amplitude_polynomial_vs_dense_matrices(self):
        core = np.linspace(-1.7, 2.3, 8).reshape(2, 2, 2)
        polynomial = ref.amplitude_laurent(core)
        states = []
        for x in POINTS:
            states.append(sum(value*np.exp(.5j*np.pi*np.dot(key, x)) for key, value in polynomial.items()))
        np.testing.assert_allclose(states, ref.dense_states(POINTS, core), rtol=0, atol=8e-16)

    def test_laurent_coefficients_vs_projection_and_offgrid(self):
        for bank in range(5):
            core = (np.arange(8)*.37-1.1+bank*.19).reshape(2, 2, 2)
            for count in (5,):
                head = np.linspace(-2.7, 1.8, count+1)+bank*.13
                expected = ref.real_coefficients(core, head)
                actual = compiler.compile_bank(core, head, count)
                np.testing.assert_allclose(actual, expected, rtol=0, atol=1.5e-14)
                direct = ref.dense_moments(POINTS, core)[:, :count] @ head[:-1]+head[-1]
                np.testing.assert_allclose(ref.feature_matrix(POINTS) @ expected, direct, rtol=0, atol=8e-15)
                fourier = ref.laurent_logits(core, head)
                np.testing.assert_allclose(fourier, fourier[::-1, ::-1].conj(), rtol=0, atol=2e-15)

    def test_constant_head_and_supported_basis(self):
        coefficient = ref.real_coefficients(np.ones((2, 2, 2))*.4, [0, 0, 0, 0, 0, 3.75])
        np.testing.assert_array_equal(coefficient, np.r_[3.75, np.zeros(24)])
        with self.assertRaises(ValueError):
            ref.real_coefficients(np.ones((3, 2, 2)), [1, 0])
        with self.assertRaises(ValueError):
            ref.real_coefficients(np.ones((2, 2, 2)), [1, 2, 3])

    def test_forced_allbanks_model_compilation_and_native_logits(self):
        for method in ("qmulti_kmeans", "qmulti_hash"):
            model = Model(method, 17, {"paired_circuit_core_initialization": 31, "mlp_initialization": 41})
            model.parameters[:] = np.sin(np.arange(len(model.parameters))*.71)*1.7
            actual = compiler.compile_model(method, model.parameters)
            for bank, theta in enumerate(model.parameters.reshape(5, model.bank_width)):
                expected = ref.real_coefficients(theta[:8].reshape(2, 2, 2), theta[8:])
                np.testing.assert_allclose(actual[bank], expected, rtol=0, atol=1e-14)
                route = np.full(len(POINTS), bank)
                p, z = compiler.predict_compiled(POINTS, actual, route)
                dense_z = ref.dense_moments(POINTS, theta[:8].reshape(2, 2, 2))[:, :model.moment_count] @ theta[8:-1]+theta[-1]
                np.testing.assert_allclose(z, dense_z, rtol=0, atol=1e-14)
                np.testing.assert_allclose(p, ref.sigmoid(dense_z), rtol=0, atol=2e-15)




class RoutingTests(unittest.TestCase):
    def test_signedzero_hashdomain_cutpoint_equality_and_centroid_boundaries(self):
        points = np.vstack((POINTS, [0., -0.], [-0., 0.]))
        salt = "synthetic-immutable-salt"
        prefix = b"QPATH-V08-HASH5\0"+salt.encode("ascii")+b"\0"
        digests = sorted(set(hashlib.sha256(prefix+np.asarray(row, dtype="<f8").tobytes()).hexdigest()
                             for row in POINTS))
        policy = {"schema": "qpath-v08-input-route-1", "banks": 5,
                  "centroids": [[-.8, 0], [-.4, 0], [0, 0], [.4, 0], [.8, 0]],
                  "hash_salt": salt, "hash_cutpoints_hex": [digests[k] for k in (0, 2, 4, 6)]}
        for kind in ("hash", "kmeans"):
            np.testing.assert_array_equal(ref.route(points, policy, kind), routers.route(points, policy, kind))
        self.assertEqual(ref.route(points[-2:], policy, "hash")[0], ref.route(points[-2:], policy, "hash")[1])
        boundaries = np.array([[-.6, 0], [-.2, 0], [.2, 0], [.6, 0]])
        offsets = np.array([[0., 0.], [-1e-12, 0.], [1e-12, 0.]])
        fixtures = np.vstack([boundaries+offset for offset in offsets])
        np.testing.assert_array_equal(ref.route(fixtures, policy, "kmeans"), routers.route(fixtures, policy, "kmeans"))

    def test_independent_voronoi_vertex_fixture_reconstruction(self):
        from fixtures import parity_inputs
        for centers in ([[-.8, -.4], [-.4, .5], [0., -.3], [.4, .4], [.8, -.4]],
                        [[-.8, 0], [-.4, 0], [0, 0], [.4, 0], [.8, 0]]):
            policy = {"centroids": centers}
            actual = parity_inputs(policy, 123456)
            expected = ref.registered_parity_inputs(policy, 123456)
            np.testing.assert_array_equal(actual[0], expected[0])
            np.testing.assert_allclose(actual[1], expected[1], rtol=0, atol=2e-14)
            self.assertEqual(actual[2], expected[2])


class ArrayVerificationTests(unittest.TestCase):
    def test_multi_artifact_conversion_and_coefficient_corruption(self):
        parameters = np.cos(np.arange(70)*.27)
        coefficients = compiler.compile_model("qmulti_hash", parameters)
        route = np.arange(len(POINTS)) % 5
        p, z = compiler.predict_compiled(POINTS, coefficients, route)
        record, _, _, _ = verify.verify_conversion("qmulti_hash", parameters, coefficients, POINTS, route, p, z)
        self.assertLess(record["coefficient_max_abs_error"], 2e-14)
        broken = coefficients.copy()
        broken[0, 0] += 1e-4
        with self.assertRaisesRegex(RuntimeError, "Laurent coefficients"):
            verify.verify_conversion("qmulti_hash", parameters, broken, POINTS, route)
        with self.assertRaises(RuntimeError):
            verify.parameter_blocks("qscalar_kmeans", np.zeros(50))

    def test_independent_learned_repacks_all_v08_bases(self):
        import audit_artifacts as artifact
        for arm, banks, width in (("TrigK_U", 5, 25), ("TrigHash_P", 5, 25), ("TrigG121_P", 1, 121)):
            parameters = np.sin(np.arange(banks*width)*.17)
            route = np.arange(len(POINTS)) % 5 if banks == 5 else None
            independent_p, independent_z = artifact.feature_predict(arm, parameters, POINTS, route)
            p, z = compiler.predict_coefficients(POINTS, parameters.reshape(banks, width), route)
            np.testing.assert_allclose(p, independent_p, rtol=0, atol=2e-15)
            np.testing.assert_allclose(z, independent_z, rtol=0, atol=2e-14)

    def test_threshold_crossing_both_near_band_accepted_and_retained(self):
        delta = verify.THRESHOLD_BAND/2
        left = np.array([.1, .5-delta, .5+delta, .8])
        right = np.array([.1, .5+delta, .5-delta, .8])
        result = verify.threshold_parity(left, right, "Synthetic parity")
        self.assertEqual(result["disagreement_flat_indices"], [1, 2])
        self.assertEqual(result["disagreement_probability_pairs"],
                         [[left[1], right[1]], [left[2], right[2]]])
        self.assertEqual(result["threshold_band"], verify.THRESHOLD_BAND)

    def test_threshold_crossing_outside_band_or_one_sided_near_rejected(self):
        band = verify.THRESHOLD_BAND
        for left, right in ((.5-2*band, .5+2*band), (.5-band/2, .5+2*band),
                            (.5-2*band, .5+band/2)):
            with self.assertRaisesRegex(RuntimeError, "outside registered roundoff band"):
                verify.threshold_parity([left], [right], "Synthetic parity")
        for left, right in (([.5], [.5, .5]), ([np.nan], [.5]), ([.5], [np.inf])):
            with self.assertRaisesRegex(RuntimeError, "shape/finite"):
                verify.threshold_parity(left, right, "Synthetic parity")

    def test_retained_split_arrays_reject_numerically_small_material_crossing(self):
        import audit_artifacts as artifact
        delta = 2*verify.THRESHOLD_BAND
        original = {"record_ids": np.array([7]), "probabilities": np.array([.5-delta]),
                    "native_logits": np.array([-4*delta])}
        saved = {"record_ids": original["record_ids"], "original_probability": original["probabilities"],
                 "original_logits": original["native_logits"], "transformed_probability": np.array([.5+delta]),
                 "transformed_logits": np.array([4*delta]), "decision_disagreement": np.array([True])}
        with self.assertRaisesRegex(RuntimeError, "Original versus transformed threshold disagreement"):
            artifact.assert_prediction_arrays(saved, original["record_ids"], original,
                                               saved["transformed_probability"], saved["transformed_logits"])
        saved["transformed_probability"][:] = .5+verify.THRESHOLD_BAND/2
        saved["original_probability"][:] = .5-verify.THRESHOLD_BAND/2
        result = artifact.assert_prediction_arrays(saved, original["record_ids"], original,
                                                   saved["transformed_probability"], saved["transformed_logits"])
        self.assertEqual(result["retained_disagreement_indices"], [0])




class ArtifactGateTests(unittest.TestCase):
    def test_current_peer_score_source_inventory_matches_gate(self):
        import ast
        import release_chains as chain
        peer = ROOT/"analysis/independent_audit/replay_evaluation_v08.py"
        tree = ast.parse(peer.read_text(encoding="utf-8-sig"))
        inventories = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(name, ast.Name) and name.id == "SOURCES" for name in node.targets)]
        self.assertEqual(len(inventories), 1)
        self.assertEqual(set(inventories[0]), chain.SCORE_SOURCES)
        self.assertEqual(len(chain.SCORE_SOURCES), 16)

    def test_actual_registered_conversion_inventory(self):
        import audit_artifacts as artifact
        matrix = artifact.gate.read(ROOT/"governance/RUN_MATRIX.json")
        jobs = [row for row in matrix["runs"] if row["stage"] == "B"]
        self.assertEqual(len(jobs), 640)
        self.assertEqual(sum(row["arm"] in artifact.CIRCUIT_ARMS for row in jobs), 256)
        self.assertEqual(sum(row["arm"] in artifact.TRIG_ARMS for row in jobs), 384)
        self.assertEqual(set(artifact.METHODS), {row["arm"] for row in jobs})

    def test_exact_score_replay_chain_inventory_and_authority(self):
        import release_chains as chain
        ids = [f"synthetic-{i:04d}" for i in range(640)]
        evaluated, frozen = {"hash": "evaluated"}, {"hash": "frozen"}
        record = {"count": 640, "run_ids": ids, "official_evaluation_commit": evaluated,
                  "independent_replay_freeze": frozen, "files": {
                      f"predictions/{identity}/{split}_reference.npz": {}
                      for identity in ids for split in ("validation", "test")}}
        summary = {"ordered_run_ids": ids, "official_evaluation_commit": evaluated, "independent_replay_freeze": frozen,
                   "replayed_endpoints": 640, "primary_comparisons_replayed": 20,
                   "reference_prediction_files": 1280, "priority_endpoint_diagnostics_replayed": 640,
                   "priority_round_diagnostics_replayed": 128000, "priority_training_draws_reconstructed": 614400000,
                   "priority_family_arm_summaries_replayed": 40, "descriptive_priority_effects_replayed": 20}
        reports = [{"job_id": identity, "splits": {"validation": {}, "test": {}}} for identity in ids]
        chain.validate_score_coverage(record, summary, reports, ids, evaluated, frozen)
        for target, mutate in (
                (0, lambda x: x["files"].pop(next(iter(x["files"])))),
                (0, lambda x: x.update(official_evaluation_commit={"hash": "other"})),
                (1, lambda x: x.update(priority_round_diagnostics_replayed=127999)),
                (1, lambda x: x.update(ordered_run_ids=ids[::-1])),
                (2, lambda x: x[0].update(job_id=ids[1])),
                (2, lambda x: x[0]["splits"].pop("test"))):
            args = [deepcopy(record), deepcopy(summary), deepcopy(reports), ids, evaluated, frozen]
            mutate(args[target])
            with self.assertRaises(RuntimeError):
                chain.validate_score_coverage(*args)

    def test_root_release_header_denies_partial_wrong_phase_and_parallel(self):
        import audit_artifacts as artifact
        output = HERE/"synthetic-not-created"
        release = {"schema": "qpath-v08-independent-deployment-release-1",
                   "review_status": "approved_by_root", "phase": "conversion",
                   "test_access_authorized": True, "max_parallel_tasks": 1,
                   "required_blas_threads": 1, "output": str(output)}
        artifact.verify_header(release, output, "conversion")
        for field, value in (("phase", "shots"), ("review_status", "pending"),
                             ("test_access_authorized", False), ("max_parallel_tasks", 5),
                             ("required_blas_threads", 2)):
            altered = dict(release)
            altered[field] = value
            with self.assertRaises(RuntimeError):
                artifact.verify_header(altered, output, "conversion")

    def test_committed_artifact_rejects_tamper_extra_and_failure(self):
        import audit_artifacts as artifact
        with tempfile.TemporaryDirectory(prefix="qpath-independent-deployment-synthetic-") as temp:
            folder = Path(temp)
            (folder/"summary.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            commit = {"schema": "qpath-v08-conversion-commit-1", "status": "completed",
                      "files": {"summary.json": {"sha256": artifact.gate.sha(folder/"summary.json"),
                                               "bytes": (folder/"summary.json").stat().st_size}}}
            artifact.gate.write_new(folder/"CONVERSION_COMMIT.json", commit)
            item = artifact.gate.binding(folder/"CONVERSION_COMMIT.json")
            with patch.object(artifact, "ROOT", folder):
                artifact.verify_committed_folder(item, "conversion")
                extra = folder/"unexpected.txt"
                extra.write_text("synthetic", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "inventory"):
                    artifact.verify_committed_folder(item, "conversion")
                extra.unlink()
                (folder/"FAILURE.json").write_text("{}", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "failure"):
                    artifact.verify_committed_folder(item, "conversion")
                (folder/"FAILURE.json").unlink()
                (folder/"summary.json").write_text('{"status":"FAIL"}', encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "changed"):
                    artifact.verify_committed_folder(item, "conversion")


if __name__ == "__main__":
    unittest.main(verbosity=2)
