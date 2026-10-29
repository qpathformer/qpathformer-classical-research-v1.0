"""Synthetic-only tests. Official-model comparisons are in preflight.py."""
import unittest
import json
from pathlib import Path
import sys
import numpy as np
from matrix_reference import predict, circuit_probability, PARAMETERS, METHODS, routes_from_policy
from statistics_reference import metrics, seed_statistics, t_critical_df4, paired_record_bootstrap, METRICS
from readout_reference import exact_counts, nested_summary, READOUT_METHODS, TRAINING_SEEDS, SHOT_BUDGETS, MEASUREMENT_SEEDS
from comparison import compare_statistics


class ReferenceTests(unittest.TestCase):
    def test_known_readout_probabilities(self):
        angles = np.zeros((1, 2, 2))
        self.assertAlmostEqual(circuit_probability([0, 0], angles, 1, beta=0), 0.)
        self.assertAlmostEqual(circuit_probability([0, 0], angles, 1, beta=np.pi), 1.)
        self.assertAlmostEqual(circuit_probability([0, 0], angles, 1), .5)
        self.assertAlmostEqual(circuit_probability([1, 0], angles, 1, beta=0), 1.)

    def test_d1_closed_form_all_inputs(self):
        rng = np.random.default_rng(73)
        for _ in range(20):
            x, bank, beta = rng.uniform(-1, 1, 2), rng.normal(size=(1, 2, 2)), rng.normal()
            a = np.pi * x + bank[0, :, 0]
            xx = np.prod(np.sin(a) * np.cos(bank[0, :, 1]))
            exact = (1 - np.cos(beta) * np.cos(a[0]) + np.sin(beta) * xx) / 2
            self.assertAlmostEqual(circuit_probability(x, bank, 1, beta=beta), exact, places=13)

    def test_model_bank_slices_and_ensemble(self):
        rng = np.random.default_rng(17)
        p = rng.normal(size=40); x = rng.uniform(-1, 1, (5, 2)); d = np.arange(5) % 4 + 1
        routes = {'hash_route': np.arange(5), 'kmeans_route': np.arange(5)[::-1]}
        for name, key in (('hash40', 'hash_route'), ('kmeans40', 'kmeans_route')):
            actual = predict(name, p, x, d, routes)
            expected = [circuit_probability(row, p[8 * k:8 * k + 8].reshape(2, 2, 2), 2)
                        for row, k in zip(x, routes[key])]
            np.testing.assert_allclose(actual, expected, atol=1e-15)
        actual = predict('ensemble40', p, x, d)
        expected = np.mean([[circuit_probability(row, p[k * 8:k * 8 + 8].reshape(2, 2, 2), 2)
                             for row in x] for k in range(5)], axis=0)
        np.testing.assert_allclose(actual, expected, atol=1e-15)

    def test_mlp_declared_inputs_and_shapes(self):
        x = np.zeros((4, 2)); depth = np.arange(1, 5)
        for name, h in (('mlp41', 5), ('mlp129', 16)):
            p = np.zeros(PARAMETERS[name]); p[2 * h] = 2; p[7 * h] = 1
            result = predict(name, p, x, depth)
            np.testing.assert_allclose(result, [1 / (1 + np.exp(-2)), .5, .5, .5])
        with self.assertRaises(ValueError): predict('mlp41', np.zeros(40), x, depth)

    def test_metrics_threshold_clip_and_absent_class(self):
        m = metrics([0, 0, 1, 1], [0, .5, .5, 1])
        self.assertEqual(m['confusion'], [[1, 1], [0, 2]])
        self.assertEqual(m['accuracy'], .75)
        self.assertAlmostEqual(m['macro_f1'], (.6666666666666666 + .8) / 2)
        self.assertEqual(m['clipped'], 2)
        self.assertAlmostEqual(metrics([0, 0], [0, 0])['macro_f1'], .5)
        self.assertEqual(metrics([1], [.5])['accuracy'], 1.)

    def test_t_quantiles_and_paired_intervals(self):
        self.assertAlmostEqual(t_critical_df4(.95), 2.7764451051977987, places=10)
        from scipy.stats import t
        self.assertAlmostEqual(t_critical_df4(1 - .05 / 3), t.ppf(1 - .05 / 6, 4), places=9)
        stat = seed_statistics(np.ones(5) * .125, primary=True)
        self.assertEqual(stat['t95'], [.125, .125])
        self.assertEqual(stat['primary_bonferroni_t_interval'], [.125, .125])
        with self.assertRaises(ValueError): seed_statistics(np.ones(25))

    def test_bootstrap_matches_explicit_record_resampling(self):
        rng = np.random.default_rng(61)
        y = rng.integers(0, 2, 17); p = rng.uniform(.01, .99, (3, 5, 17))
        actual = paired_record_bootstrap(y, p, replicates=20, seed=98003)
        draws = np.random.Generator(np.random.PCG64(98003)); expected = []
        for _ in range(20):
            positions = draws.integers(0, len(y), size=len(y))
            per = [[[metrics(y[positions], row[positions])[key] for key in METRICS]
                    for row in arm] for arm in p]
            expected.append(np.asarray(per).mean(axis=1))
        np.testing.assert_allclose(actual, expected, rtol=0, atol=5e-16)

    def test_router_fixed_ties_and_signed_zero(self):
        policy = {'centroids': [[-1, 0], [-.5, 0], [0, 0], [.5, 0], [1, 0]],
                  'hash_salt': 'unit-test-only', 'hash_cutpoints_hex': [k * 64 for k in '369c']}
        r = routes_from_policy([[-.75, 0], [0, -0.], [-0., 0]], policy)
        self.assertEqual(r['kmeans_route'].tolist(), [0, 2, 2])
        self.assertEqual(r['hash_route'][1], r['hash_route'][2])

    def test_readout_registered_rng_and_boundaries(self):
        probabilities = np.asarray([0., .125, .5, .875, 1.])
        counts = exact_counts(probabilities, 601, 801, 1024, 'encoding1')
        expected = np.random.Generator(np.random.PCG64(np.random.SeedSequence([601, 801, 1024, 6]))).binomial(1024, probabilities)
        np.testing.assert_array_equal(counts, expected)
        self.assertEqual(int(counts[0]), 0)
        self.assertEqual(int(counts[-1]), 1024)
        with self.assertRaises(ValueError): exact_counts(probabilities, 601, 801, 1024, 'fixed1')

    def test_official_statistics_schema_on_synthetic_fixture(self):
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / 'quantum'))
        import evaluation_stats  # Synthetic-only comparison, never production replay.
        from statistics_reference import summarize
        protocol = json.loads((root / 'governance/ANALYSIS_PROTOCOL.json').read_text(encoding='utf-8'))
        protocol['record_bootstrap']['replicates'] = 17  # Clearly synthetic, inexpensive fixture.
        rng = np.random.default_rng(9001)
        labels = rng.integers(0, 2, 29)
        probabilities = rng.uniform(.001, .999, (len(METHODS), 5, len(labels)))
        independent, independent_boot = summarize(labels, probabilities, list(METHODS), protocol)
        official, official_boot = evaluation_stats.summarize(labels, probabilities, METHODS, protocol)
        result = compare_statistics(independent, official, independent_boot, official_boot)
        self.assertEqual(result['status'], 'PASS')
        self.assertLess(result['maximum_numeric_error'], 1e-10)

    def test_readout_measurements_remain_nested_within_five_checkpoints(self):
        y = np.array([0, 0, 1, 1])
        probabilities = {(m, s): np.array([.4, .4, .6, .6]) for m in READOUT_METHODS for s in TRAINING_SEEDS}
        counts = {(m, s, b, r): np.array([b // 4, b // 4, 3 * b // 4, 3 * b // 4], dtype=np.int64)
                  if r % 2 else np.array([3 * b // 4, b // 4, b // 4, 3 * b // 4], dtype=np.int64)
                  for m in READOUT_METHODS for s in TRAINING_SEEDS for b in SHOT_BUDGETS for r in MEASUREMENT_SEEDS}
        report = nested_summary(y, probabilities, counts)
        values = report['aggregates']['encoding1']['1024']['macro_f1']['checkpoint_measurement_mean']
        self.assertEqual(values['n'], 5)
        self.assertEqual(len(values['values']), 5)
        self.assertAlmostEqual(values['mean'], .8)
        self.assertEqual(report['count_arrays'], 150)
        self.assertEqual(report['represented_bernoulli_trials'], 1536000)
        del counts[('encoding1', 601, 1024, 801)]
        with self.assertRaises(ValueError): nested_summary(y, probabilities, counts)


if __name__ == '__main__': unittest.main(verbosity=2)
