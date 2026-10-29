"""Bounded synthetic independent deployment checks; no data/checkpoint loads."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import reference as ref
import verify_arrays as verify
sys.path.insert(0, str(ROOT/"analysis/deployment"))
import compiler
import joint
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
            for count in (1, 5):
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
        for method in ("qscalar_kmeans", "qmulti_kmeans", "qmulti_hash"):
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


class JointTests(unittest.TestCase):
    def test_dense_joint_probabilities_all_moments(self):
        for bank in range(3):
            core = (np.arange(8)*.2+bank*.7).reshape(2, 2, 2)
            expected = ref.joint_probabilities(POINTS, core)
            actual = joint.joint_probabilities(POINTS, core)
            for setting in ("XX", "ZZ"):
                np.testing.assert_allclose(actual[setting], expected[setting], rtol=0, atol=1.5e-15)
            np.testing.assert_allclose(joint.moments_from_joint(actual, 5), ref.dense_moments(POINTS, core),
                                       rtol=0, atol=2e-15)

    def test_joint_covariance_signs_are_not_independent_marginals(self):
        xx = np.array([[512, 0, 0, 512], [0, 512, 512, 0]])
        zz = xx.copy()
        expected = ref.moments_from_counts(xx, zz)
        np.testing.assert_array_equal(expected, [[0, 0, 0, 0, 1], [0, 0, 0, 0, -1]])
        np.testing.assert_array_equal(joint.moments_from_joint({"XX": xx/1024, "ZZ": zz/1024}, 5), expected)
        with self.assertRaises(ValueError):
            ref.moments_from_counts([[.5, .5, 0, 0]])

    def test_registered_seed_streams_and_counts(self):
        probabilities = ref.joint_probabilities(POINTS, np.arange(8).reshape(2, 2, 2)/7)
        seeds = set()
        for total in (1024, 8192):
            for repeat in range(20):
                for setting in ("XX", "ZZ"):
                    value = ref.stream_seed("SYNTHETIC_ONLY/run", total, setting, repeat)
                    self.assertNotIn(value, seeds)
                    seeds.add(value)
                    self.assertEqual(int(joint.technical_stream("SYNTHETIC_ONLY/run", total, setting, repeat)["uint128_decimal"]), value)
                    actual, shots, _ = joint.draw_counts(probabilities[setting], total, setting, repeat,
                                                         "SYNTHETIC_ONLY/run", False)
                    expected = ref.replay_counts(probabilities[setting], "SYNTHETIC_ONLY/run", total, setting, repeat, True)
                    np.testing.assert_array_equal(actual, expected)
                    np.testing.assert_array_equal(actual.sum(axis=1), np.full(len(POINTS), total//2))
                    self.assertEqual(shots, total//2)
                scalar, shots, _ = joint.draw_counts(probabilities["XX"], total, "XX", repeat, "SYNTHETIC_ONLY/run", True)
                np.testing.assert_array_equal(scalar, ref.replay_counts(probabilities["XX"], "SYNTHETIC_ONLY/run", total, "XX", repeat, False))
                self.assertEqual(shots, total)
        self.assertEqual(len(seeds), 80)

    def test_prediction_aggregation_and_technical_mse_decomposition(self):
        probabilities = ref.joint_probabilities(POINTS, np.arange(8).reshape(2, 2, 2)/7)
        heads = np.tile([1.1, -.6, .7, 1.2, -.9, .3], (len(POINTS), 1))
        ideal, ideal_z, _ = joint.predict_from_joint(probabilities, heads)
        dense_moments = ref.dense_moments(POINTS, np.arange(8).reshape(2, 2, 2)/7)
        np.testing.assert_allclose(ideal_z, (dense_moments*heads[:, :-1]).sum(axis=1)+heads[:, -1], atol=2e-15, rtol=0)
        predictions = []
        for repeat in range(20):
            counts = {s: ref.replay_counts(probabilities[s], "SYNTHETIC_ONLY/predict", 1024, s, repeat, True)
                      for s in ("XX", "ZZ")}
            expected_moments = ref.moments_from_counts(counts["XX"], counts["ZZ"])
            expected = ref.sigmoid((expected_moments*heads[:, :-1]).sum(axis=1)+heads[:, -1])
            actual = joint.predict_from_joint({s: counts[s]/512 for s in counts}, heads)[0]
            np.testing.assert_allclose(actual, expected, atol=2e-16, rtol=0)
            predictions.append(actual)
        result = joint.conditional_diagnostics(predictions, ideal)
        error = np.asarray(predictions)-ideal
        self.assertAlmostEqual(result["mean_probability_squared_error"], np.mean(error**2), places=16)
        self.assertAlmostEqual(result["mean_probability_squared_error"],
                               result["mean_per_record_squared_bias"]+result["mean_per_record_technical_variance_population_ddof0"], places=16)


class RoutingTests(unittest.TestCase):
    def test_signedzero_hashdomain_cutpoint_equality_and_centroid_boundaries(self):
        points = np.vstack((POINTS, [0., -0.], [-0., 0.]))
        salt = "synthetic-immutable-salt"
        prefix = b"QPATH-V07-HASH5\0"+salt.encode("ascii")+b"\0"
        digests = sorted(set(hashlib.sha256(prefix+np.asarray(row, dtype="<f8").tobytes()).hexdigest()
                             for row in POINTS))
        policy = {"schema": "qpath-v07-input-route-1", "banks": 5,
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

    def test_analytic_head_variance_includes_joint_covariance(self):
        # Perfectly correlated XX signs: Var(2X0+3X1)=25, not independence's13.
        joints = {"XX": np.array([[.5, 0, 0, .5]]), "ZZ": np.array([[1., 0, 0, 0]])}
        heads = np.array([[2., 3., 0, 0, 0, 0]])
        np.testing.assert_allclose(verify.head_logit_variance(joints, heads, 1024), [25/512], atol=0, rtol=0)
        np.testing.assert_allclose(verify.head_logit_variance({"XX": joints["XX"]}, [[2., 0]], 1024),
                                   [4/1024], atol=0, rtol=0)

    def test_conversion_joint_and_shot_artifact_arrays(self):
        method = "qmulti_hash"
        model = Model(method, 2, {"paired_circuit_core_initialization": 17, "mlp_initialization": 19})
        model.parameters[:] = np.cos(np.arange(70)*.27)
        route = np.arange(len(POINTS)) % 5
        coefficients = compiler.compile_model(method, model.parameters)
        p, z = model.predict_with_logits(POINTS, route)
        report, expected_coefficients, reference_p, reference_z = verify.verify_conversion(
            method, model.parameters, coefficients, POINTS, route, p, z)
        self.assertLess(report["coefficient_max_abs_error"], 2e-14)
        saved_joint, saved_heads = joint.model_joint(model, POINTS, route)
        ideal = joint.predict_from_joint(saved_joint, saved_heads)[0]
        verify.verify_joint_inputs(method, model.parameters, POINTS, route, saved_joint, saved_heads, ideal)
        draws = []
        for repeat in range(20):
            counts = {setting: joint.draw_counts(probabilities, 8192, setting, repeat,
                      "SYNTHETIC_ONLY/artifact", False)[0] for setting, probabilities in saved_joint.items()}
            probabilities = joint.predict_from_joint({s: c/4096 for s, c in counts.items()}, saved_heads)[0]
            report, reconstructed = verify.verify_shot_draw("SYNTHETIC_ONLY/artifact", 8192, repeat,
                saved_heads, saved_joint, counts, probabilities)
            self.assertEqual(report["represented_measurement_outcomes"], len(POINTS)*8192)
            draws.append(probabilities)
        expected = verify.conditional_statistics(draws, ideal)
        actual = joint.conditional_diagnostics(draws, ideal)
        for key, value in expected.items():
            np.testing.assert_allclose(actual[key], value, rtol=0, atol=3e-16)
        corrupted = coefficients.copy()
        corrupted[0, 0] += 1e-4
        with self.assertRaisesRegex(RuntimeError, "Laurent coefficients"):
            verify.verify_conversion(method, model.parameters, corrupted, POINTS, route)


class ArtifactGateTests(unittest.TestCase):
    def test_root_release_header_denies_partial_wrong_phase_and_parallel(self):
        import audit_artifacts as artifact
        output = HERE/"synthetic-not-created"
        release = {"schema": "qpath-v07-independent-deployment-release-1",
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
            commit = {"schema": "qpath-v07-conversion-commit-1", "status": "completed",
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
