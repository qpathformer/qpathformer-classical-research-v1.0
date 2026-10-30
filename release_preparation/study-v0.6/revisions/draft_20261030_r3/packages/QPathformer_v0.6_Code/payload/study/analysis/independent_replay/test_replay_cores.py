"""Synthetic-only independent analysis tests; no official study imports/data."""
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import unittest
import numpy as np
from scipy.stats import t

import statistics_reference as independent
from threshold_reference import diagnostics, CASES

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE.parents[1] / "governance/ANALYSIS_PROTOCOL.json").read_text(encoding="utf-8-sig"))


class StatisticsTests(unittest.TestCase):
    def test_hand_calculated_binary_metrics_and_missing_class(self):
        value = independent.metrics([0, 1, 1, 0], [.2, .8, .5, .9])
        self.assertEqual(value["confusion"], [[1, 1], [0, 2]])
        self.assertAlmostEqual(value["bce"], -(math.log(.8) + math.log(.8) + math.log(.5) + math.log(.1)) / 4)
        self.assertAlmostEqual(value["macro_f1"], (2 / 3 + 4 / 5) / 2)
        self.assertAlmostEqual(value["brier"], (.04 + .04 + .25 + .81) / 4)
        self.assertEqual(value["accuracy"], .75)
        self.assertEqual(independent.metrics([1, 1], [.9, .9])["macro_f1"], .5)
        self.assertEqual(independent.metrics([1, 1], [.1, .1])["macro_f1"], 0.)

    def test_saturated_probabilities_invalid_values_and_native_loss(self):
        value = independent.metrics([1, 0], [0., 1.])
        self.assertEqual(value["clipped"], 2)
        self.assertEqual(value["brier"], 1.)
        self.assertTrue(math.isfinite(value["bce"]))
        self.assertEqual(independent.native_logit_bce([1, 0], [-1000., 1000.]), 1000.)
        self.assertEqual(independent.native_logit_bce([0, 1], [-1000., 1000.]), 0.)
        self.assertAlmostEqual(independent.native_logit_bce([0, 1], [0., 0.]), math.log(2))
        for y, p in (([0, 2], [.1, .2]), ([0], [np.nan]), ([1], [1.01]), ([], [])):
            with self.assertRaises(ValueError):
                independent.metrics(y, p)
            with self.assertRaises(ValueError):
                independent.calibration(y, p)
        with self.assertRaises(ValueError):
            independent.native_logit_bce([1], [np.inf])

    def test_calibration_edges_and_decimal_representation(self):
        edges = np.linspace(0, 1, 11)
        p = np.concatenate(([0.], edges[1:-1], [1.]))
        y = np.arange(len(p)) % 2
        result = independent.calibration(y, p)
        self.assertEqual([row["count"] for row in result["bins"]], [1] * 9 + [2])
        p = np.array([np.nextafter(edges[3], -np.inf), edges[3], np.nextafter(edges[3], np.inf), .3])
        result = independent.calibration([0, 1, 0, 1], p)
        self.assertEqual(result["bins"][2]["count"], 2)
        self.assertEqual(result["bins"][3]["count"], 2)
        self.assertIsNone(result["bins"][0]["mean_probability"])
        self.assertIsNone(result["bins"][0]["positive_fraction"])
        self.assertAlmostEqual(result["ece"], .2)

    def test_df4_critical_against_scipy_and_degenerate_intervals(self):
        for level in (.95, 1 - .05 / 16):
            self.assertLess(abs(independent.t_critical_df4(level) - t.ppf((1 + level) / 2, 4)), 2e-11)
        same = independent.interval(np.full(5, -.02))
        self.assertEqual(same["lower"], same["upper"])
        ordinary = independent.interval([1, 2, 3, 4, 5])
        adjusted = independent.interval([1, 2, 3, 4, 5], 1 - .05 / 16)
        self.assertAlmostEqual(ordinary["sample_sd"], math.sqrt(2.5))
        self.assertLess(adjusted["lower"], ordinary["lower"])
        self.assertGreater(adjusted["upper"], ordinary["upper"])
        with self.assertRaises(ValueError):
            independent.interval([1, 2, 3, 4])

    def test_bootstrap_matches_expanded_records_including_one_class(self):
        rng = np.random.Generator(np.random.PCG64(5771))
        y = np.array([0, 0, 1, 0, 1, 1, 1, 0])
        p = rng.uniform(.01, .99, (5, 6, len(y)))
        p[0, 0] = .5
        p[1, 1, :2] = [0, 1]
        counts = rng.multinomial(len(y), np.full(len(y), 1 / len(y)), size=13).astype(np.uint16)
        counts[0] = [8, 0, 0, 0, 0, 0, 0, 0]
        actual = independent.bootstrap_metrics(y, p, counts)
        expected = np.empty_like(actual)
        for sample, row in enumerate(counts):
            selection = np.repeat(np.arange(len(y)), row)
            for method in range(6):
                measures = [independent.metrics(y[selection], p[seed, method, selection]) for seed in range(5)]
                expected[sample, method] = [sum(measure[name] for measure in measures) / 5 for name in independent.METRICS]
        np.testing.assert_allclose(actual, expected, atol=2e-12, rtol=0)
        invalid = counts.astype(np.int64)
        invalid[0] = [-1, 9, 0, 0, 0, 0, 0, 0]
        with self.assertRaises(ValueError):
            independent.bootstrap_metrics(y, p, invalid)

    def test_nonlinear_f1_is_checkpoint_mean_not_pooled_confusion(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([[[.1, .1, .9, .9]], [[.9, .9, .9, .9]], [[.1, .1, .1, .1]],
                      [[.1, .1, .9, .9]], [[.9, .9, .1, .1]]])
        counts = np.ones((1, 4), dtype=np.uint16)
        value = independent.bootstrap_metrics(y, p, counts)[0, 0, 1]
        self.assertAlmostEqual(value, (1 + 1 / 3 + 1 / 3 + 1 + 0) / 5)
        pooled = independent.metrics(np.tile(y, 5), p[:, 0].ravel())["macro_f1"]
        self.assertGreater(abs(value - pooled), .01)

    def test_all_populations_counts_contrasts_calibration_and_units(self):
        y = np.array([0, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1, 0])
        rng = np.random.Generator(np.random.PCG64(5773))
        p = rng.uniform(.001, .999, (5, 6, len(y)))
        p[0, 0, :3] = [0, .5, 1]
        identities = []
        for population in PROTOCOL["population_order"]:
            reference, counts, boot = independent.summarise_population(population, y, p, PROTOCOL)
            separate_rng = np.random.Generator(np.random.PCG64(PROTOCOL["record_bootstrap"]["seeds"][population]))
            expected_counts = separate_rng.multinomial(len(y), np.full(len(y), 1 / len(y)), size=10000).astype(np.uint16)
            np.testing.assert_array_equal(counts, expected_counts)
            encoded = io.BytesIO()
            np.save(encoded, expected_counts, allow_pickle=False)
            self.assertEqual(reference["bootstrap_counts_sha256"], hashlib.sha256(encoded.getvalue()).hexdigest())
            identities.append(reference["bootstrap_counts_sha256"])
            self.assertEqual(boot.shape, (10000, 6, 4))
            self.assertEqual(len(reference["aggregate"]), 6)
            self.assertEqual(len(reference["contrasts"]), 10)
            self.assertEqual(sum(row["primary"] for row in reference["contrasts"]), 4)
            self.assertEqual(reference["primary_family_size"], 16)
            for row in reference["contrasts"]:
                first, second = [term[0] for term in row["terms"]]
                for index, name in enumerate(independent.METRICS):
                    values = np.array(reference["aggregate"][first][name]["seed_values"]) - reference["aggregate"][second][name]["seed_values"]
                    scale = 100 if name in ("macro_f1", "accuracy") else 1
                    np.testing.assert_allclose(row["metrics"][name]["seed_values"], values * scale, atol=1e-14, rtol=0)
                    delta = (boot[:, independent.METHODS.index(first), index] - boot[:, independent.METHODS.index(second), index]) * scale
                    np.testing.assert_allclose(row["metrics"][name]["record_interval95"], np.percentile(delta, [2.5, 97.5], method="linear"), atol=1e-14, rtol=0)
                    adjusted = "seed_interval_adjusted" in row["metrics"][name]
                    self.assertEqual(adjusted, row["primary"] and name == "bce")
                    if adjusted:
                        self.assertEqual(row["metrics"][name]["seed_interval_adjusted"]["confidence"], 1 - .05 / 16)
                self.assertEqual(row["metrics"]["brier"]["units"], "squared_probability_error")
                self.assertEqual(row["metrics"]["macro_f1"]["units"], "percentage_points")
            for method in independent.METHODS:
                rows = reference["aggregate"][method]["calibration"]["seed_results"]
                self.assertEqual(len(rows), 5)
                self.assertTrue(all(sum(bin["count"] for bin in row["bins"]) == len(y) for row in rows))
        self.assertEqual(len(set(identities)), 4)

    def test_grouped_tie_aware_average_precision_and_absent_classes(self):
        # Highest tied group:1positive/2total; next:2positives/4total;
        # final1positive/5total. Contributions (1/3)*.5+(1/3)*.5+(1/3)*.6.
        y=np.array([1,0,1,0,1]); p=np.array([.9,.9,.6,.6,.1])
        result=independent.class_quality(y,p)
        self.assertAlmostEqual(result["average_precision"], (.5+.5+.6)/3)
        self.assertEqual(result["confusion"],[[0,2],[1,2]])
        self.assertEqual(result["positive_precision"],.5)
        self.assertEqual(result["positive_recall"],2/3)
        self.assertEqual(result["negative_recall"],0.)
        for order in ([1,0,3,2,4],[4,3,2,1,0]):
            self.assertEqual(independent.class_quality(y[order],p[order]),result)
        self.assertEqual(independent.class_quality([0,1,1,0],[.5]*4)["average_precision"],.5)
        self.assertEqual(independent.class_quality([1,1],[.9,.1])["average_precision"],1.)
        self.assertIsNone(independent.class_quality([0,0],[.9,.1])["average_precision"])
        self.assertIsNone(independent.class_quality([0,0],[.9,.1])["positive_recall"])
        self.assertIsNone(independent.class_quality([1,1],[.9,.1])["negative_recall"])
        self.assertEqual(independent.class_quality([0,1],[.1,.2])["positive_precision"],0.)

    def test_class_quality_mean_sd_not_pooled_predictions(self):
        y=np.array([0,1,1,0]);rng=np.random.Generator(np.random.PCG64(6619))
        p=rng.uniform(0,1,(5,6,4));p[:,:,1]=p[:,:,0]
        summary,_,_=independent.summarise_population(independent.POPULATIONS[0],y,p,PROTOCOL)
        for mi,method in enumerate(independent.METHODS):
            rows=[independent.class_quality(y,p[si,mi]) for si in range(5)]
            actual=summary["aggregate"][method]["class_quality"]
            self.assertEqual(actual["seed_results"],rows)
            for key in independent.QUALITY:
                values=np.array([row[key] for row in rows])
                self.assertAlmostEqual(actual["descriptive"][key]["mean"],values.mean())
                self.assertAlmostEqual(actual["descriptive"][key]["sample_sd"],values.std(ddof=1))

    def test_protocol_mutations_fail(self):
        changes = (("study_id", "wrong"), ("primary_family_size", 9), ("practical_difference", .02),
                   ("methods", list(reversed(PROTOCOL["methods"]))), ("training_seeds", [801, 802, 803, 804, 805]))
        for key, value in changes:
            changed = copy.deepcopy(PROTOCOL)
            changed[key] = value
            with self.assertRaises(ValueError):
                independent.validate_protocol(changed)
        changed = copy.deepcopy(PROTOCOL)
        changed["record_bootstrap"]["replicates"] = 5000
        with self.assertRaises(ValueError):
            independent.validate_protocol(changed)


class NumericalTests(unittest.TestCase):
    def diagnose(self, y, p, q):
        n = len(y)
        return diagnostics(y, p, q, np.arange(n, dtype=np.int64),
                           {"hash": np.arange(n, dtype=np.int64) % 5, "kmeans": np.zeros(n, dtype=np.int64)},
                           PROTOCOL["numerical"])

    def test_inside_band_disagreement_disclosed_canonical_unchanged(self):
        epsilon = np.finfo(np.float64).eps
        y, p, q = [0, 1, 1, 0], [.5 - epsilon, .5, .8, .1], [.5 + epsilon, .5 - epsilon, .8, .1]
        result = self.diagnose(y, p, q)
        self.assertEqual(result["counts"]["class_disagreements"], 2)
        self.assertFalse(result["counts"]["exact_class_agreement"])
        self.assertEqual(result["counts"]["outside_band_class_disagreements"], 0)
        self.assertEqual(result["canonical_metrics"], independent.metrics(y, p))
        self.assertEqual(len(result["disagreements"]), 2)
        self.assertEqual(set(result["sensitivity"]), set(CASES))
        self.assertIn("brier", result["raw_reference_minus_canonical"])
        for value in result["sensitivity"].values():
            self.assertNotIn("bce", value)
            self.assertNotIn("brier", value)

    def test_outside_band_probability_and_bce_failures(self):
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
        possible = [independent.class_metrics(y, [left, right, 1, 0]) for left in (0, 1) for right in (0, 1)]
        for key in ("macro_f1", "accuracy"):
            self.assertEqual(result["sensitivity"]["label_assisted_all_incorrect"][key], min(item[key] for item in possible))
            self.assertEqual(result["sensitivity"]["label_assisted_all_correct"][key], max(item[key] for item in possible))


if __name__ == "__main__":
    unittest.main()
