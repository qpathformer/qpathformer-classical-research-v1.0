"""Input-boundary, occupancy and redraw tests; no model outcome evaluation."""
import json
import unittest
import numpy as np

from routers import (canonical_features, feature_keys, feature_hashes,
                     fit_route_policy, route, _lloyd)
from prepare_data import generate


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x = np.random.Generator(np.random.PCG64(721)).uniform(-1, 1, (140, 2))
        cls.policy = fit_route_policy(cls.x, 823)

    def test_deterministic_training_order_invariance_and_serialization(self):
        other = fit_route_policy(self.x[::-1], 823)
        expected = dict(self.policy)
        expected.pop("training_ordered_features_sha256")
        other.pop("training_ordered_features_sha256")
        self.assertEqual(expected, other)
        policy = json.loads(json.dumps(self.policy))
        for kind in ("hash", "kmeans"):
            np.testing.assert_array_equal(route(self.x, policy, kind), route(self.x, self.policy, kind))

    def test_matched_occupancy_and_exact_hash_boundary_rule(self):
        geometric = np.bincount(route(self.x, self.policy, "kmeans"), minlength=5)
        hashed = np.bincount(route(self.x, self.policy, "hash"), minlength=5)
        np.testing.assert_array_equal(geometric, hashed)
        np.testing.assert_array_equal(geometric, self.policy["kmeans_training_counts"])
        hashes = feature_hashes(self.x, self.policy["hash_salt"])
        for bank, cutoff in enumerate(self.policy["hash_cutpoints_hex"]):
            point = self.x[[hashes.index(cutoff)]]
            self.assertEqual(int(route(point, self.policy, "hash")[0]), bank)

    def test_heldout_routes_fixed_and_batch_independent(self):
        points = np.repeat(self.x[[7]], 19, axis=0)
        before = json.dumps(self.policy, sort_keys=True)
        for kind in ("hash", "kmeans"):
            expected = route(points, self.policy, kind)
            self.assertEqual(len(set(expected)), 1)
            np.testing.assert_array_equal(expected, np.concatenate([route(points[:3], self.policy, kind), route(points[3:], self.policy, kind)]))
            self.assertEqual(route(np.empty((0, 2)), self.policy, kind).shape, (0,))
        self.assertEqual(before, json.dumps(self.policy, sort_keys=True))

    def test_signed_zero_and_invalid_feature_boundary(self):
        self.assertEqual(feature_keys([[0., -0.]])[0], feature_keys([[-0., 0.]])[0])
        for value in ([[np.nan, 0]], [[0, np.inf]], [1, 2], [[1, 2, 3]]):
            with self.assertRaises(ValueError):
                canonical_features(value)
        with self.assertRaises(ValueError):
            fit_route_policy(np.repeat(self.x[:1], 20, axis=0), 823)
        with self.assertRaises(TypeError):
            fit_route_policy(self.x, 823, np.zeros(len(self.x)))
        with self.assertRaises(ValueError):
            route(self.x, self.policy, "label")

    def test_geometry_tie_and_empty_cluster_repair(self):
        policy = dict(self.policy)
        policy["centroids"] = [[-1., 0.], [-0.5, 0.], [0., 0.], [0.5, 0.], [1., 0.]]
        np.testing.assert_array_equal(route([[-.75, 0.], [.25, 0.]], policy), [0, 2])
        points = np.column_stack((np.linspace(-1, 1, 51), np.zeros(51)))
        centers, labels, iterations, converged = _lloyd(points, np.zeros((5, 2)))
        self.assertTrue(converged)
        self.assertTrue(np.all(np.bincount(labels, minlength=5) > 0))
        self.assertLessEqual(iterations, 500)
        for bank in range(5):
            np.testing.assert_allclose(centers[bank], points[labels == bank].mean(axis=0), atol=0, rtol=0)


class GenerationTests(unittest.TestCase):
    def test_forced_exclusion_consumes_same_stream_without_relabel_selection(self):
        seeds = (723, 727, 729)
        original = np.random.Generator(np.random.PCG64(seeds[0])).uniform(-1, 1, (8001, 2))
        excluded = {feature_keys(original[:1])[0]}
        splits, evidence, keys = generate(seeds, excluded)
        self.assertEqual(evidence["draws_consumed"], 8001)
        self.assertEqual(evidence["rejected"][0]["draw_index"], 0)
        self.assertEqual(excluded, {feature_keys(original[:1])[0]})
        self.assertTrue(keys.isdisjoint(excluded))
        self.assertEqual(keys, set(feature_keys(original[1:])))
        for name, n in (("train", 4800), ("validation", 1600), ("test", 1600)):
            self.assertEqual(len(splits[name]["x"]), n)
        ids = np.concatenate([part["ids"] for part in splits.values()])
        np.testing.assert_array_equal(np.sort(ids), np.arange(8000))
        draw_ids = np.concatenate([part["source_draw_ids"] for part in splits.values()])
        np.testing.assert_array_equal(np.sort(draw_ids), np.arange(1, 8001))


if __name__ == "__main__":
    unittest.main()
