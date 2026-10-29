"""Synthetic-only replay core tests; official helpers used only as test comparators."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np

import statistics_reference as independent
from threshold_reference import diagnostics, CASES

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
PROTOCOL = json.loads((STUDY / "governance/ANALYSIS_PROTOCOL.json").read_text())


def load_official_for_synthetic_comparison_only():
    spec = importlib.util.spec_from_file_location("official_statistics_fixture_comparator", HERE.parent / "statistics_v04.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compare(actual, expected, tolerance=2e-12, path="root"):
    if isinstance(expected, dict):
        for key, value in expected.items():
            compare(actual[key], value, tolerance, path + "/" + key)
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError(path + " list length")
        for index, value in enumerate(expected):
            compare(actual[index], value, tolerance, path + "/" + str(index))
    elif isinstance(expected, float):
        if not math.isfinite(actual) or abs(actual - expected) > tolerance:
            raise AssertionError(f"{path}: {actual} versus {expected}")
    elif actual != expected:
        raise AssertionError(path + " differs")


class StatisticsTests(unittest.TestCase):
    def test_hand_calculated_binary_metrics_and_missing_class(self):
        value = independent.metrics([0, 1, 1, 0], [.2, .8, .5, .9])
        self.assertEqual(value["confusion"], [[1, 1], [0, 2]])
        self.assertAlmostEqual(value["bce"], -(math.log(.8) + math.log(.8) + math.log(.5) + math.log(.1)) / 4)
        self.assertAlmostEqual(value["macro_f1"], (2 / 3 + 4 / 5) / 2)
        self.assertEqual(value["accuracy"], .75)
        self.assertEqual(independent.metrics([1, 1], [.9, .9])["macro_f1"], .5)
        self.assertEqual(independent.metrics([1, 1], [.1, .1])["macro_f1"], 0.)

    def test_saturated_probabilities_and_invalid_values(self):
        value = independent.metrics([1, 0], [0., 1.])
        self.assertEqual(value["clipped"], 2)
        self.assertTrue(math.isfinite(value["bce"]))
        for y, p in (([0, 2], [.1, .2]), ([0], [np.nan]), ([1], [1.01]), ([], [])):
            with self.assertRaises(ValueError):
                independent.metrics(y, p)

    def test_df4_closed_form_critical_and_degenerate_intervals(self):
        self.assertAlmostEqual(independent.t_critical_df4(.95), 2.7764451051977987, places=11)
        official = load_official_for_synthetic_comparison_only()
        for level in (.95, 1 - .05 / 9):
            self.assertLess(abs(independent.t_critical_df4(level) - official.t.ppf((1 + level) / 2, 4)), 2e-11)
        same = independent.interval(np.full(5, -.02))
        self.assertEqual(same["lower"], same["upper"])
        ordinary = independent.interval([1, 2, 3, 4, 5])
        adjusted = independent.interval([1, 2, 3, 4, 5], 1 - .05 / 9)
        self.assertLess(adjusted["lower"], ordinary["lower"])
        self.assertGreater(adjusted["upper"], ordinary["upper"])

    def test_bootstrap_matches_expanded_records_including_one_class(self):
        rng = np.random.Generator(np.random.PCG64(4771))
        y = np.array([0, 0, 1, 0, 1, 1, 1, 0])
        p = rng.uniform(.01, .99, (5, 9, len(y)))
        p[0, 0] = .5
        counts = rng.multinomial(len(y), np.full(len(y), 1 / len(y)), size=13).astype(np.uint16)
        counts[0] = [8, 0, 0, 0, 0, 0, 0, 0]
        actual = independent.bootstrap_metrics(y, p, counts)
        expected = np.empty_like(actual)
        for sample, row in enumerate(counts):
            selection = np.repeat(np.arange(len(y)), row)
            for method in range(9):
                measures = [independent.metrics(y[selection], p[seed, method, selection]) for seed in range(5)]
                expected[sample, method] = [sum(measure[name] for measure in measures) / 5 for name in independent.METRICS]
        np.testing.assert_allclose(actual, expected, atol=2e-12, rtol=0)
        invalid = counts.astype(np.int64)
        invalid[0] = [-1, 9, 0, 0, 0, 0, 0, 0]
        with self.assertRaises(ValueError):
            independent.bootstrap_metrics(y, p, invalid)

    def test_all_population_synthetic_summaries_and_exact_count_hashes(self):
        official = load_official_for_synthetic_comparison_only()
        fixture_root = HERE / "synthetic_fixture_work"
        fixture_root.mkdir(exist_ok=True)
        attempt = Path(tempfile.mkdtemp(prefix="statistics_synthetic_", dir=fixture_root))
        (attempt / "SYNTHETIC_ONLY.txt").write_text("Generated artificial probabilities for preflight; no study test data or checkpoints.\n")
        y = np.array([0, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1, 0])
        rng = np.random.Generator(np.random.PCG64(4773))
        p = rng.uniform(.001, .999, (5, 9, len(y)))
        p[0, 0, :3] = [0, .5, 1]
        checks = []
        for population in PROTOCOL["population_order"]:
            reference, counts, boot = independent.summarise_population(population, y, p, PROTOCOL)
            official.analyse_population(population, y, p, PROTOCOL["training_seeds"], PROTOCOL["methods"], attempt / population)
            # The committed JSON contract represents official tuple terms as lists.
            expected = json.loads((attempt / population / "population_summary.json").read_text())
            for name in ("population", "n", "seeds", "methods", "bootstrap_replicates", "primary_family_size",
                         "bootstrap_counts_sha256", "aggregate", "contrasts", "limits"):
                compare(reference[name], expected[name])
            stored = np.load(attempt / population / "bootstrap_counts.npy", allow_pickle=False)
            np.testing.assert_array_equal(counts, stored)
            self.assertEqual(hashlib.sha256(independent.npy_bytes(counts)).hexdigest(), expected["bootstrap_counts_sha256"])
            _, loss = official.metric_arrays(y, p)
            np.testing.assert_allclose(boot, official._bootstrap_metrics(y, p, loss, counts), atol=2e-12, rtol=0)
            checks.append({"population": population, "status": "PASS", "counts_sha256": expected["bootstrap_counts_sha256"],
                           "contrast_count": len(reference["contrasts"]), "replicates": len(counts)})
        (attempt / "SYNTHETIC_COMPARISON_PASS.json").write_text(json.dumps({"status": "PASS", "synthetic_only": True, "populations": checks}, indent=2) + "\n")


class NumericalTests(unittest.TestCase):
    def diagnose(self, y, p, q):
        n = len(y)
        return diagnostics(y, p, q, np.arange(n, dtype=np.int64),
                           {"hash": np.arange(n, dtype=np.int64) % 5, "kmeans": np.zeros(n, dtype=np.int64)},
                           PROTOCOL["numerical"])

    def test_inside_band_disagreement_is_disclosed_without_canonical_change(self):
        epsilon = np.finfo(np.float64).eps
        y, p, q = [0, 1, 1, 0], [.5 - epsilon, .5, .8, .1], [.5 + epsilon, .5 - epsilon, .8, .1]
        result = self.diagnose(y, p, q)
        self.assertEqual(result["counts"]["class_disagreements"], 2)
        self.assertFalse(result["counts"]["exact_class_agreement"])
        self.assertEqual(result["counts"]["outside_band_class_disagreements"], 0)
        self.assertEqual(result["canonical_metrics"], independent.metrics(y, p))
        self.assertEqual(len(result["disagreements"]), 2)
        self.assertEqual(set(result["sensitivity"]), set(CASES))
        for value in result["sensitivity"].values():
            self.assertNotIn("bce", value)

    def test_outside_both_band_and_probability_bce_failures(self):
        for p, q in (([.5 - 2e-14], [.5 + 2e-14]), ([.1], [.1 + 3e-12]), ([1e-7], [1e-7 + 1e-12])):
            with self.assertRaises(ValueError):
                self.diagnose([1], p, q)

    def test_canonical_mask_only_and_label_assisted_extrema(self):
        result = self.diagnose([1], [.5 + 2e-14], [.5])
        self.assertEqual(result["counts"]["canonical_near_band"], 0)
        self.assertEqual(result["counts"]["reference_near_band"], 1)
        for value in result["sensitivity"].values():
            self.assertEqual(value, independent.class_metrics([1], [1]))
        epsilon = np.finfo(float).eps
        y, p = np.array([0, 1, 1, 0]), np.array([.5 - epsilon, .5, .9, .1])
        result = self.diagnose(y, p, p)
        possible = []
        for left in (0, 1):
            for right in (0, 1):
                possible.append(independent.class_metrics(y, [left, right, 1, 0]))
        for key in ("macro_f1", "accuracy"):
            self.assertEqual(result["sensitivity"]["label_assisted_all_incorrect"][key], min(item[key] for item in possible))
            self.assertEqual(result["sensitivity"]["label_assisted_all_correct"][key], max(item[key] for item in possible))


if __name__ == "__main__":
    unittest.main()
