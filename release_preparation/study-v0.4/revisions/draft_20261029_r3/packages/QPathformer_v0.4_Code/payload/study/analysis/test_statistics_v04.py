"""Synthetic analytical fixtures, never official data or model outcomes."""
import math
import unittest
import numpy as np
import statistics_v04 as s

def reference(y,p):
    y=list(map(int,y));p=list(map(float,p));pred=[int(z>=.5) for z in p]
    loss=sum(-math.log(min(max(z,1e-7),1-1e-7) if label else 1-min(max(z,1e-7),1-1e-7)) for label,z in zip(y,p))/len(y)
    scores=[]
    for label in (0,1):
        tp=sum(a==label and b==label for a,b in zip(y,pred))
        fp=sum(a!=label and b==label for a,b in zip(y,pred))
        fn=sum(a==label and b!=label for a,b in zip(y,pred))
        scores.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
    return [loss,sum(scores)/2,sum(a==b for a,b in zip(y,pred))/len(y)]

class TestStatistics(unittest.TestCase):
    def test_metric_extremes_and_single_class(self):
        for labels in ([0,0,1,1],[1,1,1,1]):
            for probabilities in ([0,1,.5,1e-8],[.5,.5,.5,.5],[.1,.2,.8,.9]):
                p=np.tile(probabilities,(5,9,1))
                actual,_=s.metric_arrays(labels,p)
                np.testing.assert_allclose(actual[2,6],reference(labels,probabilities),atol=1e-12,rtol=0)
    def test_shared_count_bootstrap_matches_expanded_records(self):
        rng=np.random.default_rng(47223)
        y=np.array([0,0,0,1,1,1,1,0])
        p=rng.uniform(.01,.99,(5,9,len(y)))
        p[0,0]=.5
        counts=rng.multinomial(len(y),np.full(len(y),1/len(y)),size=23).astype(np.uint16)
        counts[0]=[8,0,0,0,0,0,0,0]
        _,loss=s.metric_arrays(y,p)
        actual=s._bootstrap_metrics(y,p,loss,counts)
        expected=np.zeros_like(actual)
        for b,count in enumerate(counts):
            indices=np.repeat(np.arange(len(y)),count)
            for m in range(9):
                expected[b,m]=np.mean([reference(y[indices],p[seed,m,indices]) for seed in range(5)],axis=0)
        np.testing.assert_allclose(actual,expected,atol=2e-12,rtol=0)
    def test_seed_interval_degenerate_and_sign(self):
        exact=s._interval(np.full(5,-.02),.95)
        self.assertAlmostEqual(exact['mean'],-.02)
        self.assertAlmostEqual(exact['lower'],exact['upper'])
        values=np.array([.01,.02,.03,.04,.05])
        ordinary=s._interval(values,.95)
        adjusted=s._interval(values,1-.05/9)
        self.assertLess(adjusted['lower'],ordinary['lower'])
        self.assertGreater(adjusted['upper'],ordinary['upper'])
    def test_invalid_probabilities_fail(self):
        with self.assertRaises(ValueError):s.metric_arrays([0,1],np.full((5,9,2),np.nan))
        with self.assertRaises(ValueError):s.metric_arrays([0,1],np.full((5,9,2),1.1))

if __name__=='__main__':unittest.main()
