"""Label-free and synthetic checks for independent vector/scalar oracles."""
import unittest,time
import numpy as np
import reference_v04 as r

class IndependentReferenceTests(unittest.TestCase):
    def test_scalar_vector_and_round_chunk_equivalence(self):
        rng=np.random.default_rng(790019);x=rng.uniform(-1,1,(21,2));route=np.arange(21)%5
        for method in r.METHODS:
            with self.subTest(method=method):
                p=rng.normal(0,.4,(7,r.PARAMETERS[method]));assigned=None if method.endswith('_global') else route
                batched=r.predict_many(method,p,x,assigned,chunk_rounds=3)
                separately=np.stack([r.scalar_predict(method,v,x,assigned) for v in p])
                np.testing.assert_allclose(batched,separately,rtol=0,atol=2e-14)
                np.testing.assert_array_equal(batched,r.predict_many(method,p,x,assigned,chunk_rounds=1))

    def test_depth_two_probability_frequency_envelope(self):
        n=17;axis=-1+2*np.arange(n)/n;x=np.array([(a,b) for a in axis for b in axis]);rng=np.random.default_rng(790023)
        frequency=np.fft.fftfreq(n)*n;outside=(abs(frequency[:,None])>2)|(abs(frequency[None,:])>2)
        for _ in range(5):
            p=rng.uniform(-np.pi,np.pi,8);value=r.predict('q2_global',p,x).reshape(n,n)
            fourier=np.fft.fft2(value)/(n*n)
            self.assertLess(float(abs(fourier[outside]).max()),2e-14)
            theta=np.linalg.lstsq(r.trig_features(x),value.ravel(),rcond=None)[0]
            self.assertLess(float(abs(r.trig_features(x)@theta-value.ravel()).max()),2e-14)
        self.assertEqual(np.linalg.matrix_rank(r.trig_features(x)),25)

    def test_trig_zero_logit_and_constant_basis_packing(self):
        x=np.array([[.2,.7],[-.3,.4],[0,0.]])
        for method in ('trig_global','trig_hash','trig_kmeans'):
            p=np.zeros(r.PARAMETERS[method]);route=None if method.endswith('_global') else np.array([0,3,4])
            np.testing.assert_array_equal(r.predict(method,p,x,route),np.full(3,.5))
            p.reshape(-1,25)[:,0]=np.log(3)
            np.testing.assert_allclose(r.predict(method,p,x,route),.75,atol=1e-15)

    def test_routes_are_required_and_out_of_bounds_rejected(self):
        x=np.zeros((3,2));p=np.zeros(40)
        for route in (None,np.array([0,1,5]),np.array([0.,1.,2.]),np.array([0,1])):
            with self.assertRaises(ValueError):r.predict('q2_hash',p,x,route)

    def test_scalar_features_do_not_use_labels_or_record_ids(self):
        x=np.array([[.2,.7],[-.3,.4],[0,0.]])
        base=r.scalar_predict('mlp_global',np.arange(129)*.001,x)
        # Permuting only coordinates changes output order, with no metadata API.
        np.testing.assert_allclose(base[[2,0,1]],r.scalar_predict('mlp_global',np.arange(129)*.001,x[[2,0,1]]),atol=0,rtol=0)

if __name__=='__main__':unittest.main(verbosity=2)
