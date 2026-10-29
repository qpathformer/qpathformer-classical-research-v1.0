"""Synthetic-only oracle integration; never imports a production model."""
import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np

from prediction_reference import native_diagnostics, replay_checkpoint, stable_sigmoid
from statistics_reference import METHODS

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
PROTOCOL = json.loads((STUDY / "governance/ANALYSIS_PROTOCOL.json").read_text(encoding="utf-8-sig"))
SPEC = importlib.util.spec_from_file_location("independent_v06_oracle_fixture", HERE.parent / "classical_review/reference_v06.py")
ORACLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ORACLE)


class PredictionTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.Generator(np.random.PCG64(5891))
        self.x = rng.uniform(-1, 1, (20, 2))
        self.y = rng.integers(0, 2, 20)
        self.ids = np.arange(20, dtype=np.int64)
        self.routes = {"hash": np.arange(20, dtype=np.int64) % 5,
                       "kmeans": np.repeat(np.arange(5, dtype=np.int64), 4)}
        self.rng = rng

    def test_all_six_methods_scalar_canonical_vector_replay(self):
        for method in METHODS:
            parameters = self.rng.uniform(-.2, .2, ORACLE.PARAMETERS[method])
            core = None
            route = None if method.endswith("_global") else self.routes["kmeans"]
            p, z = ORACLE.scalar_predict_with_logits(method, parameters, self.x, route, core)
            q, w, report = replay_checkpoint(ORACLE, method, parameters, core, self.x, self.y, self.ids,
                                             self.routes, p, z, PROTOCOL["numerical"])
            self.assertEqual(report["status"], "PASS")
            np.testing.assert_allclose(p, q, atol=2e-12, rtol=0)
            if z is not None:
                np.testing.assert_allclose(z, w, atol=1e-9, rtol=0)
            self.assertEqual(report["native_verification"]["has_native_logits"], True)
            self.assertEqual(sum(row["count"] for row in report["canonical_calibration"]["bins"]), 20)

    def test_native_logits_detect_saturated_probability_masking(self):
        # Both sigmoid values round to 1: probability agreement alone is insufficient.
        with self.assertRaisesRegex(ValueError, "native logit tolerance"):
            native_diagnostics("qmulti_kmeans", [0], [1.], [100.], [1.], [100. + 1e-6], PROTOCOL["numerical"])
        okay = native_diagnostics("qmulti_kmeans", [0], [1.], [100.], [1.], [100.], PROTOCOL["numerical"])
        self.assertEqual(okay["canonical_native_bce"], 100.)
        self.assertEqual(okay["clipped_wrong_prediction_count"], 1)

    def test_contradictory_or_missing_logits_fail(self):
        for args in (("q2_kmeans", [0], [.1], [1.], [.1], None),
                     ("qmulti_kmeans", [0], [.1], None, [.1], None),
                     ("qmulti_kmeans", [0], [.1], [0.], [.1], [0.])):
            with self.assertRaises(ValueError):
                native_diagnostics(*args, PROTOCOL["numerical"])

    def test_unregistered_frozen_core_and_route_contract_fail(self):
        for method in METHODS:
            theta = np.zeros(ORACLE.PARAMETERS[method])
            for core in (np.zeros(40), np.full((5,2,2,2), np.nan)):
                with self.assertRaises(ValueError):
                    replay_checkpoint(ORACLE, method, theta, core, self.x, self.y, self.ids, self.routes,
                                      np.full(20,.5),np.zeros(20),PROTOCOL["numerical"])
        with self.assertRaises(ValueError):
            replay_checkpoint(ORACLE,"trig_global",np.zeros(25),None,self.x,self.y,self.ids,
                              {"kmeans":self.routes["kmeans"]},np.full(20,.5),np.zeros(20),PROTOCOL["numerical"])

    def test_large_finite_sigmoid_and_wrong_extreme_loss(self):
        np.testing.assert_array_equal(stable_sigmoid([-1000., 0., 1000.]), [0., .5, 1.])
        result = native_diagnostics("mlp_global", [1, 0], [0., 1.], [-1000., 1000.],
                                    [0., 1.], [-1000., 1000.], PROTOCOL["numerical"])
        self.assertEqual(result["canonical_native_bce"], 1000.)
        self.assertEqual(result["clipped_wrong_prediction_count"], 2)


if __name__ == "__main__":
    unittest.main()
