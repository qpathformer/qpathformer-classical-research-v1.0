"""Independent synthetic oracle checks; no official populations/model outcomes."""
import unittest
import numpy as np
import reference_v05 as ref


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.Generator(np.random.PCG64(5059301))
        self.x=self.rng.uniform(-1,1,(23,2));self.route=np.arange(23,dtype=np.int64)%5
        self.core=self.rng.uniform(-.8,.8,(5,2,2,2))

    def test_vector_scalar_all11_and_chunk_boundaries(self):
        for method in ref.METHODS:
            with self.subTest(method=method):
                theta=self.rng.normal(0,.35,(3,ref.PARAMETERS[method]))
                route=None if method.endswith('_global') else self.route
                core=self.core if method=='qfrozen_kmeans' else None
                p,z=ref.predict_many_with_logits(method,theta,self.x,route,core,chunk_rounds=2)
                for k in range(3):
                    ps,zs=ref.scalar_predict_with_logits(method,theta[k],self.x,route,core)
                    np.testing.assert_allclose(p[k],ps,rtol=0,atol=2e-14)
                    if z is None:self.assertIsNone(zs)
                    else:np.testing.assert_allclose(z[k],zs,rtol=0,atol=2e-14)
                np.testing.assert_array_equal(p,ref.predict_many(method,theta,self.x,route,core,chunk_rounds=1))

    def test_pauli_basis_and_legacy_readout_identity(self):
        np.testing.assert_allclose(ref.scalar_observables([0,0],np.zeros((2,2,2))),[0,0,1,1,1],atol=0,rtol=0)
        for x,bank in zip(self.x,self.route):
            phi=ref.scalar_observables(x,self.core[bank]);raw=ref.scalar_circuit(x,self.core[bank])
            self.assertAlmostEqual(raw,(1+phi[0])/2,places=14)
            self.assertTrue(np.all(abs(phi)<=1+1e-14))

    def test_frozen_cache_is_independently_computed_and_input_only(self):
        a=ref.frozen_features(self.x,self.route,self.core)
        b=np.asarray([ref.scalar_observables(x,self.core[k]) for x,k in zip(self.x,self.route)])
        np.testing.assert_allclose(a,b,atol=2e-14,rtol=0)
        np.testing.assert_array_equal(a[::-1],ref.frozen_features(self.x[::-1],self.route[::-1],self.core))
        with self.assertRaises(ValueError):ref.predict('qfrozen_kmeans',np.zeros(30),self.x,self.route)
        with self.assertRaises(ValueError):ref.predict('qmulti_kmeans',np.zeros(70),self.x,self.route,self.core)

    def test_stable_native_loss_saturated_wrong_predictions_keep_gradient(self):
        x=self.x[:10];y=np.array([0,1]*5)
        theta=np.zeros(25);theta[0]=100
        p=ref.predict('trig_global',theta,x)
        self.assertTrue(np.all(p==1))
        self.assertAlmostEqual(ref.native_loss('trig_global',theta,x,y),50)
        self.assertLess(ref.bce(y,p),9)
        gradient=ref.central_gradient('trig_global',theta,x,y,step=1e-3)
        self.assertAlmostEqual(gradient[0],.5,places=10)
        theta[0]=-100
        self.assertAlmostEqual(ref.central_gradient('trig_global',theta,x,y,step=1e-3)[0],-.5,places=10)
        self.assertGreater(ref.stable_logit_bce(np.ones(1),np.array([100.])),0)
        for z,yv in ((1000,0),(-1000,1)):
            self.assertEqual(ref.stable_logit_bce(np.array([yv]),np.array([z])),1000)

    def test_metrics_threshold_brier_and_fixed_bin_edges(self):
        p=np.array([0,.1,.2,.5,.999,1.]);y=np.array([0,1,0,1,0,1])
        m=ref.metrics(y,p)
        self.assertEqual(m['confusion'],[[2,1],[1,2]])
        self.assertAlmostEqual(m['macro_f1'],2/3)
        self.assertAlmostEqual(m['brier'],(0+.81+.04+.25+.998001+0)/6)
        self.assertAlmostEqual(m['ece10'],(0+.9+.2+.5+.999)/6)
        self.assertEqual([v['n'] for v in m['reliability10']],[1,1,1,0,0,1,0,0,0,2])
        self.assertIsNone(m['reliability10'][3]['mean_probability'])
        edges=np.linspace(0.,1.,11)
        edge_metrics=ref.metrics(np.zeros(11),edges)
        self.assertEqual([v['n'] for v in edge_metrics['reliability10']],[1]*9+[2])
        # Decimal .3 is immediately below the float64 linspace edge .30000000000000004.
        edge_metrics=ref.metrics(np.zeros(2),np.array([.3,edges[3]]))
        self.assertEqual(edge_metrics['reliability10'][2]['n'],1)
        self.assertEqual(edge_metrics['reliability10'][3]['n'],1)

    def test_frozen_gradient_never_contains_core_coordinates(self):
        theta=self.rng.normal(0,.3,30);y=np.arange(len(self.x))%2
        g=ref.central_gradient('qfrozen_kmeans',theta,self.x,y,self.route,self.core)
        self.assertEqual(g.shape,(30,))
        core_before=self.core.copy();ref.native_loss('qfrozen_kmeans',theta,self.x,y,self.route,self.core)
        np.testing.assert_array_equal(core_before,self.core)

    def test_two_layer_observable_and_readout_logit_fourier_envelope(self):
        # Two encodings per coordinate give amplitude exponents{-1,0,1};
        # conjugate products therefore give observable frequencies{-2..2}.
        grid=np.array([(a,b) for a in np.arange(5)*2/5-1 for b in np.arange(5)*2/5-1])
        basis=ref.trig_features(grid)
        for _ in range(4):
            core=self.rng.uniform(-3,3,(2,2,2))
            values=np.asarray([ref.scalar_observables(x,core) for x in grid])
            coefficients=np.linalg.solve(basis,values)
            holdout=self.rng.uniform(-1,1,(97,2))
            direct=np.asarray([ref.scalar_observables(x,core) for x in holdout])
            np.testing.assert_allclose(ref.trig_features(holdout)@coefficients,direct,atol=3e-14,rtol=0)
            head=self.rng.normal(size=6)
            fullcoeff=coefficients@head[:5];fullcoeff[0]+=head[-1]
            np.testing.assert_allclose(ref.trig_features(holdout)@fullcoeff,direct@head[:5]+head[-1],atol=8e-14,rtol=0)
            # The containment is for the per-bank logit. It is not raw-probability equivalence.

    def test_invalid_model_shapes_routes_and_nonfinite_inputs(self):
        for route in (np.zeros(23,float),np.full(23,5,int),np.zeros(22,int)):
            with self.assertRaises(ValueError):ref.predict('q2_kmeans',np.zeros(40),self.x,route)
        with self.assertRaises(ValueError):ref.predict('trig_global',np.zeros(25),self.x,self.route)
        with self.assertRaises(ValueError):ref.predict('trig_global',np.full(25,np.nan),self.x)
        with self.assertRaises(ValueError):ref.predict('trig_global',np.zeros(24),self.x)


if __name__=='__main__':unittest.main()
