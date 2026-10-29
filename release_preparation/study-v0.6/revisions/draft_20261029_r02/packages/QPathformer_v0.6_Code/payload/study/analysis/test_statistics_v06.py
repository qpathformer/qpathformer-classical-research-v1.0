import unittest
import numpy as np
from statistics_v06 import metric_arrays, calibration, class_quality, _bootstrap_metrics, _interval

class StatisticsTests(unittest.TestCase):
    def test_average_precision_groups_ties_without_order_advantage(self):
        y=np.array([1,0,1,0]); p=np.array([.9,.9,.2,.1])
        expected=.5*.5+.5*(2/3)
        a=class_quality(y,p)
        self.assertAlmostEqual(a['average_precision'],expected)
        self.assertEqual(a['confusion'],[[1,1],[1,1]])
        self.assertEqual(a['positive_recall'],.5)
        self.assertEqual(a['positive_precision'],.5)
        for order in ([1,0,2,3],[3,2,1,0]):
            self.assertEqual(class_quality(y[order],p[order])['average_precision'],a['average_precision'])

    def test_all_negative_predictions_do_not_hide_positive_recall(self):
        a=class_quality([0,0,0,1],[.1,.1,.1,.1])
        self.assertEqual(a['prevalence'],.25)
        self.assertEqual(a['average_precision'],.25)
        self.assertEqual(a['positive_recall'],0.)
        self.assertEqual(a['positive_precision'],0.)
        self.assertEqual(a['negative_recall'],1.)

    def test_undefined_average_precision_and_no_negative_recall(self):
        self.assertIsNone(class_quality([0,0],[.9,.1])['average_precision'])
        self.assertIsNone(class_quality([0,0],[.9,.1])['positive_recall'])
        a=class_quality([1,1],[.9,.1])
        self.assertEqual(a['average_precision'],1.)
        self.assertIsNone(a['negative_recall'])

    def test_hand_computed_metrics_and_clipping(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([[[0., .5, .75, 1.]]])
        metrics, losses, brier = metric_arrays(y, p)
        self.assertAlmostEqual(metrics[0, 0, 1], (2/3+4/5)/2)
        self.assertEqual(metrics[0, 0, 2], .75)
        self.assertEqual(metrics[0, 0, 3], (.25+.0625)/4)
        self.assertAlmostEqual(losses.mean(), (-2*np.log(1-1e-7)-np.log(.5)-np.log(.75))/4)
        np.testing.assert_array_equal(brier, [[[0, .25, .0625, 0]]])

    def test_paired_counts_equal_explicit_record_resampling(self):
        y = np.array([0, 0, 1, 1, 1])
        p = np.random.default_rng(423).uniform(size=(5, 3, 5))
        metrics, loss, brier = metric_arrays(y, p)
        counts = np.array([[1, 1, 1, 1, 1], [2, 0, 1, 2, 0], [0, 0, 0, 0, 5]])
        actual = _bootstrap_metrics(y, p, loss, brier, counts)
        for i, count in enumerate(counts):
            ix = np.repeat(np.arange(len(y)), count)
            expected = metric_arrays(y[ix], p[:, :, ix])[0].mean(axis=0)
            np.testing.assert_allclose(actual[i], expected, atol=1e-14, rtol=0)
        np.testing.assert_allclose(actual[0], metrics.mean(axis=0), atol=1e-14, rtol=0)

    def test_identical_models_preserve_pairing(self):
        y = np.array([0, 1, 0, 1])
        p = np.tile(np.array([.1, .7, .6, .9]), (5, 2, 1))
        _, loss, brier = metric_arrays(y, p)
        counts = np.random.default_rng(61).multinomial(4, [.25]*4, size=100)
        actual = _bootstrap_metrics(y, p, loss, brier, counts)
        np.testing.assert_array_equal(actual[:, 0], actual[:, 1])

    def test_f1_not_metric_of_mean_probability(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([[[.1, .1, .51, .51]], [[.49, .49, .1, .1]]])
        m, loss, brier = metric_arrays(y, p)
        boot = _bootstrap_metrics(y, p, loss, brier, np.ones((1, 4), dtype=int))
        self.assertAlmostEqual(boot[0, 0, 1], m[:, 0, 1].mean())
        self.assertNotAlmostEqual(boot[0, 0, 1], metric_arrays(y, p.mean(axis=0, keepdims=True))[0][0, 0, 1])

    def test_calibration_edges_empty_bins_and_endpoints(self):
        edges = np.linspace(0, 1, 11)
        p = np.array([0., edges[1], np.nextafter(edges[1], 0), 1.])
        result = calibration(np.array([0, 1, 0, 1]), p)
        self.assertEqual([r['count'] for r in result['bins']], [2, 1, 0, 0, 0, 0, 0, 0, 0, 1])
        self.assertIsNone(result['bins'][2]['mean_probability'])
        self.assertAlmostEqual(result['ece'], (.1+.9)/4)

    def test_invalid_values_and_degenerate_interval(self):
        for bad in [np.nan, -0.01, 1.01]:
            with self.assertRaises(ValueError):
                metric_arrays([0], np.array([[[bad]]]))
        with self.assertRaises(ValueError):
            metric_arrays([.5], np.array([[[.4]]]))
        interval = _interval([.2]*5, .9958333333333333)
        self.assertEqual(interval['lower'], interval['upper'])

if __name__ == '__main__':
    unittest.main(verbosity=2)

