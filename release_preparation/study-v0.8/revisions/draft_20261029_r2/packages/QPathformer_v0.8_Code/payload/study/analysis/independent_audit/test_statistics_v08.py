"""Synthetic independent statistical checks; no sealed study reads."""
import copy
import math
import unittest
import numpy as np
from scipy.stats import t
import statistics_v08 as s


class StatisticalTests(unittest.TestCase):
    def test_analytic_t7_cdf_and_critical_against_scipy(self):
        for value in (-20,-5,-1,0,.5,1,5,20):
            self.assertAlmostEqual(s.cdf_t7(value),float(t.cdf(value,7)),places=14)
        for probability in (.00125,.025,.5,.975,.99875):
            self.assertAlmostEqual(s.quantile_t7(probability),float(t.ppf(probability,7)),places=10)

    def test_interval_uses_eight_population_means_df7(self):
        a=np.array([-.03,-.01,-.02,-.015,-.018,-.005,-.027,-.011])
        got=s.population_interval(a)
        expected=float(a.mean()+t.ppf(.99875,7)*a.std(ddof=1)/math.sqrt(8))
        self.assertAlmostEqual(got["upper"],expected,places=13)
        self.assertEqual(got["df"],7);self.assertEqual(got["n_independent_populations"],8)
        with self.assertRaises(ValueError):s.population_interval(np.tile(a,2))

    def test_exact_primary_family_pairing_and_seed_average(self):
        populations=[{"population_id":f"{family}_{i}","family":family} for family in s.FAMILIES for i in range(8)]
        rows=[]
        for p in populations:
            for seed in s.SEEDS:
                for a_index,arm in enumerate(s.ARMS):
                    rows.append({"population_id":p["population_id"],"training_seed_id":seed,
                                 "arm":arm,"common_bce":.1+.01*a_index+.001*(seed-1601)})
        result=s.primary_contrasts(rows,populations)
        self.assertEqual(len(result),20)
        self.assertAlmostEqual(result[0]["mean_difference"],.01,places=14)
        self.assertEqual(len(result[0]["paired_population_records"]),8)
        for malformed in (rows[:-1],rows+[rows[0]],rows[:-1]+[rows[0]]):
            with self.assertRaises(ValueError):s.primary_contrasts(malformed,populations)

    def test_tied_ap_is_grouped_and_permutation_invariant(self):
        y=np.array([1,0,1,0]);p=np.array([.9,.9,.8,.2])
        first=s.positive_metrics_and_grouped_ap(y,p)
        order=[1,0,2,3]
        second=s.positive_metrics_and_grouped_ap(y[order],p[order])
        self.assertEqual(first,second)
        self.assertAlmostEqual(first["grouped_tie_average_precision"],(.5+2/3)/2)
        self.assertEqual(first["positive_recall"],1.)
        self.assertAlmostEqual(first["positive_precision"],2/3)

    def test_zero_positive_reports_undefined_ap_and_recall(self):
        result=s.positive_metrics_and_grouped_ap([0,0],[.1,.2])
        self.assertIsNone(result["positive_precision"])
        self.assertIsNone(result["positive_recall"])
        self.assertIsNone(result["grouped_tie_average_precision"])

    def test_milestones_observed_grid_and_nonreacher_censoring(self):
        values=np.full(200,.5);values[9]=.9;values[100]=.96
        result=s.validation_milestones(values)
        self.assertEqual(result[0]["first_observed_optimizer_update"],750)
        self.assertEqual(result[1]["first_observed_optimizer_update"],7575)
        self.assertFalse(result[2]["reached"])
        self.assertEqual(result[2]["right_censored_after_updates"],15000)
        with self.assertRaises(ValueError):s.validation_milestones(values[:199])


if __name__=="__main__":
    unittest.main(verbosity=2)
