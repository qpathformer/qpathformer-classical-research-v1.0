import importlib.util
from pathlib import Path
import unittest
import numpy as np
import replay_metrics_v07 as independent

path=Path(__file__).resolve().parents[1]/"official/metrics.py"
spec=importlib.util.spec_from_file_location("official_metrics_for_synthetic_test",path)
official=importlib.util.module_from_spec(spec);spec.loader.exec_module(official)


class MetricReplayTests(unittest.TestCase):
    def test_random_and_extreme_scores_all_fields(self):
        rng=np.random.Generator(np.random.PCG64(773833))
        for n in (1,2,16,1600):
            z=rng.uniform(-60,60,n);p=np.exp(-np.logaddexp(0.,-z));y=rng.integers(0,2,n)
            independent.compare(independent.score(y,p,z),official.score(y,p,z))

    def test_ties_threshold_bins_no_positive_and_empty(self):
        for y,p in (([0,1,0,1],[.5,.5,.2,.2]),([0,0],[0.,1.]),([1,1],[.1,.1]),([],[])):
            y=np.asarray(y);p=np.asarray(p);z=np.zeros(len(p))
            independent.compare(independent.score(y,p,z),official.score(y,p,z))

    def test_one_field_tamper_rejected(self):
        y=np.array([0,1]);p=np.array([.1,.9]);z=np.log(p/(1-p))
        actual=official.score(y,p,z);actual["grouped_tie_average_precision"]-=.01
        with self.assertRaises(ValueError):independent.compare(independent.score(y,p,z),actual)


if __name__=="__main__":unittest.main(verbosity=2)
