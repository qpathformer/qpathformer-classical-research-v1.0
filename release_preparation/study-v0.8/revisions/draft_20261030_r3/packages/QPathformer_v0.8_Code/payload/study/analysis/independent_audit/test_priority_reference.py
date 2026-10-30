import unittest
import numpy as np
import reference_v08 as ref
import sampler_reference as sampler

class PriorityReferenceTests(unittest.TestCase):
    def test_warmup_and_true_refresh_transition(self):
        for mode in ('U','P'):
            for t in (1,10):
                got=sampler.effective_probabilities(mode,t,4)
                np.testing.assert_array_equal(got['probabilities'],np.full(4,.25))
                self.assertFalse(got['refreshed'])
            for t in (11,12,200):
                got=sampler.effective_probabilities(mode,t,4,np.array([0.,.1,2.,20.]))
                self.assertTrue(got['refreshed'])
                self.assertEqual(np.array_equal(got['probabilities'],np.full(4,.25)),mode=='U')
        with self.assertRaises(ValueError):sampler.effective_probabilities('P',10,4,np.ones(4))
        with self.assertRaises(ValueError):sampler.effective_probabilities('U',11,4)

    def test_cap_floor_equal_loss_limit_and_weights(self):
        scores,p=sampler.proposal(np.array([0.,1.,5.,50.]))
        self.assertEqual(scores[2],scores[3]);self.assertTrue(np.all(p>=.125))
        np.testing.assert_allclose(sampler.proposal(np.full(9,.9))[1],np.full(9,1/9),atol=1e-16)
        u=np.array([0.,.1,.5,np.nextafter(1.,0.)])
        ix,w=sampler.replay_draws(p,u)
        np.testing.assert_array_equal(w,1/(4*p[ix]));self.assertTrue(np.all(w<=2))
        self.assertGreater(abs(w.sum()-4),.01)

    def test_inverse_cdf_edges_are_right_sided(self):
        p=np.array([.125,.25,.25,.375]);u=np.array([0.,.125,.375,.625,np.nextafter(1.,0.)])
        ix,_=sampler.replay_draws(p,u)
        np.testing.assert_array_equal(ix,[0,1,2,3,3])

    def test_stream_pairing_and_consumption(self):
        seed=2**90+71
        complete=sampler.expected_uniform_stream(seed,4800*12)
        g=np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed)))
        np.testing.assert_array_equal(complete,np.concatenate([g.random(4800) for _ in range(12)]))
        np.testing.assert_array_equal(complete,sampler.expected_uniform_stream(seed,4800*12))

    def test_raw_weighted_gradient_all_five_bases(self):
        rng=np.random.default_rng(2008001)
        x=rng.uniform(-.8,.8,(4,2));y=np.array([0,1,1,0]);routes=np.array([0,1,1,0])
        w=np.array([.3,1.8,.7,1.4])
        for method in ref.METHODS:
            theta=rng.normal(0,.12,ref.PARAMETERS[method])
            route=None if method.endswith('_global') else routes
            analytical=ref.weighted_gradient(method,theta,x,y,route,w)
            numerical=ref.weighted_central_gradient(method,theta,x,y,route,w)
            np.testing.assert_allclose(analytical,numerical,atol=3e-10,rtol=3e-8,err_msg=method)
            if route is not None:
                width=len(theta)//5
                np.testing.assert_array_equal(analytical[2*width:],np.zeros(len(theta)-2*width))

    def test_importance_corrected_expected_gradient(self):
        rng=np.random.default_rng(2008002)
        x=rng.uniform(-.8,.8,(4,2));y=np.array([0,1,1,0]);routes=np.array([0,1,1,0])
        p=sampler.proposal(np.array([0.,.1,2.,8.]))[1]
        for method in ref.METHODS:
            theta=rng.normal(0,.1,ref.PARAMETERS[method])
            route=None if method.endswith('_global') else routes
            expected=np.zeros_like(theta)
            for i in range(4):
                expected+=p[i]*ref.weighted_gradient(method,theta,x[i:i+1],y[i:i+1],
                    None if route is None else route[i:i+1],np.array([1/(4*p[i])]))
            target=ref.weighted_gradient(method,theta,x,y,route)
            np.testing.assert_allclose(expected,target,atol=3e-16,rtol=2e-14,err_msg=method)

    def test_forbidden_normalization_changes_gradient(self):
        x=np.array([[.2,.3],[-.5,.6],[.1,-.2]]);y=np.array([0,1,1])
        theta=np.linspace(-.1,.1,121);w=np.array([.3,.5,1.9])
        raw=ref.weighted_gradient('trig121_global',theta,x,y,weights=w)
        normalized=ref.weighted_gradient('trig121_global',theta,x,y,weights=w/w.mean())
        self.assertGreater(np.max(abs(raw-normalized)),1e-3)

    def test_extreme_logits_and_invalid_inputs(self):
        loss=sampler.native_losses(np.array([0,1,0,1]),np.array([-1000.,1000.,1000.,-1000.]))
        np.testing.assert_array_equal(loss,[0.,0.,1000.,1000.])
        for value in [np.array([np.nan]),np.array([np.inf]),np.array([-1.])]:
            with self.assertRaises(ValueError):sampler.proposal(value)
        with self.assertRaises(ValueError):sampler.replay_draws([.5,.5],[1.])
        with self.assertRaises(ValueError):sampler.replay_draws([0.,1.],[.1])

if __name__=='__main__':unittest.main()
