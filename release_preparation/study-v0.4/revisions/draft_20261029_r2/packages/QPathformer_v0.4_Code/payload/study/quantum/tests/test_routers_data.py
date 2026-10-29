"""Meaningful coordinate/router integrity tests; no model outcome evaluation."""
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np

from routers import (canonical_features, feature_keys, feature_hashes,
                     fit_route_policy, route, _lloyd)
from prepare_data import (DATASETS, generate, labels_for, task_for,
                          _allocate, ROUTER_SOURCE, ROUTER_SOURCE_SHA256)


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x = np.random.Generator(np.random.PCG64(721)).uniform(-1, 1, (140, 2))
        cls.policy = fit_route_policy(cls.x, 823)

    def test_original_reviewed_router_bytes_reused(self):
        current = Path(__file__).resolve().parent.parent / "routers.py"
        self.assertEqual(hashlib.sha256(current.read_bytes()).hexdigest(), ROUTER_SOURCE_SHA256)
        self.assertEqual(current.read_bytes(), ROUTER_SOURCE.read_bytes())

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

    def test_fixed_heldout_routes_are_batch_independent_and_do_not_refit(self):
        points = np.repeat(self.x[[7]], 19, axis=0)
        before = json.dumps(self.policy, sort_keys=True)
        for kind in ("hash", "kmeans"):
            expected = route(points, self.policy, kind)
            self.assertEqual(len(set(expected)), 1)
            np.testing.assert_array_equal(expected, np.concatenate([route(points[:3], self.policy, kind), route(points[3:], self.policy, kind)]))
            self.assertEqual(route(np.empty((0, 2)), self.policy, kind).shape, (0,))
        self.assertEqual(before, json.dumps(self.policy, sort_keys=True))

    def test_signed_zero_invalid_features_and_no_label_fit_argument(self):
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
    def test_known_labels_axis_orientation_and_population_registration(self):
        points = [[0., 0.], [.9, 0.], [.6, .6], [.6, -.6], [-.6, .6]]
        np.testing.assert_array_equal(labels_for(points, "circle"), [1, 0, 0, 0, 0])
        np.testing.assert_array_equal(labels_for(points, "ellipse"), [1, 0, 1, 0, 0])
        self.assertEqual(sum(task_for(name) == "circle" for name in DATASETS), 4)
        self.assertEqual(sum(task_for(name) == "ellipse" for name in DATASETS), 3)
        with self.assertRaises(ValueError):
            labels_for(points, "unregistered")
        with self.assertRaises(ValueError):
            task_for("unregistered")
        # Closed ellipse geometry: area pi*a*b=2; maximum |x_j|<1 after rotation.
        a, b = np.sqrt(2 / np.pi) * np.sqrt(1.5), np.sqrt(2 / np.pi) / np.sqrt(1.5)
        self.assertAlmostEqual(np.pi * a * b, 2.)
        self.assertLess(np.sqrt((a*a+b*b)/2), 1.)

    def test_largest_remainder_tie_and_small_class_allocation(self):
        np.testing.assert_array_equal(_allocate([4001, 3999], .6, 4800), [2401, 2399])
        np.testing.assert_array_equal(_allocate([4001, 3999], .2, 1600), [800, 800])
        np.testing.assert_array_equal(_allocate([1, 7999], .6, 4800), [1, 4799])
        np.testing.assert_array_equal(_allocate([1, 7999], .2, 1600), [0, 1600])
        with self.assertRaises(ValueError):
            _allocate([10, 10], .2, 10)

    def test_forced_exclusion_consumes_same_stream_and_does_not_mutate_exclusions(self):
        seeds = (723, 727, 729)
        original = np.random.Generator(np.random.PCG64(seeds[0])).uniform(-1, 1, (8001, 2))
        excluded = {feature_keys(original[:1])[0]}
        splits, evidence, keys = generate(seeds, excluded, "ellipse")
        self.assertEqual(evidence["draws_consumed"], 8001)
        self.assertEqual(evidence["rejected"][0]["draw_index"], 0)
        self.assertEqual(excluded, {feature_keys(original[:1])[0]})
        self.assertTrue(keys.isdisjoint(excluded))
        self.assertEqual(keys, set(feature_keys(original[1:])))
        for name, n in (("train", 4800), ("validation", 1600), ("test", 1600)):
            self.assertEqual(len(splits[name]["x"]), n)
            self.assertEqual(set(splits[name]), {"x", "y", "ids", "source_draw_ids"})
        ids = np.concatenate([part["ids"] for part in splits.values()])
        np.testing.assert_array_equal(np.sort(ids), 723000000 + np.arange(8000))
        draw_ids = np.concatenate([part["source_draw_ids"] for part in splits.values()])
        np.testing.assert_array_equal(np.sort(draw_ids), np.arange(1, 8001))

    def test_record_metadata_cannot_change_coordinates_labels_or_split_membership(self):
        a, info_a, keys_a = generate((1723, 1727, 1729), set(), "circle")
        b, info_b, keys_b = generate((1723, 2701, 1729), set(), "circle")
        self.assertEqual(info_a, info_b)
        self.assertEqual(keys_a, keys_b)
        for split in a:
            np.testing.assert_array_equal(a[split]["x"], b[split]["x"])
            np.testing.assert_array_equal(a[split]["y"], b[split]["y"])
            np.testing.assert_array_equal(a[split]["source_draw_ids"], b[split]["source_draw_ids"])
            self.assertFalse(np.array_equal(a[split]["ids"], b[split]["ids"]))

    def test_population_is_disjoint_and_ids_are_globally_unique(self):
        a, _, keys_a = generate((2723, 2727, 2729), set(), "circle")
        b, _, keys_b = generate((3723, 3727, 3729), keys_a, "ellipse")
        self.assertTrue(keys_a.isdisjoint(keys_b))
        self.assertTrue(set(np.concatenate([p["ids"] for p in a.values()])).isdisjoint(np.concatenate([p["ids"] for p in b.values()])))
        for parts in (a, b):
            source_draws = np.concatenate([p["source_draw_ids"] for p in parts.values()])
            np.testing.assert_array_equal(np.sort(source_draws), np.arange(8000))


if __name__ == "__main__":
    unittest.main()
