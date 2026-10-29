import unittest
import numpy as np
import readout_reference_v05 as r
import reference_v05 as pure

class ReadoutTests(unittest.TestCase):
    def test_random_ideal_density_matches_separate_pure_matrix_reference(self):
        rng=np.random.Generator(np.random.PCG64(5057811))
        for _ in range(80):
            x=rng.uniform(-1,1,2);theta=rng.uniform(-3,3,(2,2,2));rho=r.core_density(x,theta)
            np.testing.assert_allclose(r.moments(rho),pure.scalar_observables(x,theta),atol=2e-14,rtol=0)
            xx=r.setting_distribution(rho,'XX');zz=r.setting_distribution(rho,'ZZ')
            np.testing.assert_allclose(r.grouped_moments(xx,zz),r.moments(rho),atol=2e-14,rtol=0)
            legacy=r.setting_distribution(rho,'legacy_q0')
            self.assertAlmostEqual(legacy[2:].sum(),(1+r.moments(rho)[0])/2,places=14)

    def test_known_plus_state_readout_sign_and_qiskit_endianness(self):
        state=np.array([1,0,1,0])/np.sqrt(2);rho=np.outer(state,state)
        xx=r.setting_distribution(rho,'XX');self.assertAlmostEqual(xx@r.Q0,1)
        self.assertAlmostEqual(r.setting_distribution(rho,'legacy_q0')[2:].sum(),1)
        counts={'00':1,'01':2,'10':3,'11':4}
        np.testing.assert_array_equal(r.qiskit_count_vector(counts),[1,2,3,4])
        np.testing.assert_array_equal(r.qiskit_count_vector(counts,logical_q0_wire=0),[1,3,2,4])

    def test_local_pauli_twirl_matches_partial_trace_channel(self):
        rng=np.random.Generator(np.random.PCG64(5057812));a=rng.normal(size=4)+1j*rng.normal(size=4);a/=np.linalg.norm(a);rho=np.outer(a,a.conj());tensor=rho.reshape(2,2,2,2)
        for p in (0.,.001,.37,1.):
            partial1=np.einsum('iaja->ij',tensor);partial0=np.einsum('aiaj->ij',tensor)
            np.testing.assert_allclose(r.depolarize(rho,p,0),(1-p)*rho+p*np.kron(np.eye(2)/2,partial0),atol=1e-15,rtol=0)
            np.testing.assert_allclose(r.depolarize(rho,p,1),(1-p)*rho+p*np.kron(partial1,np.eye(2)/2),atol=1e-15,rtol=0)

    def test_noise_physicality_and_local_q1_marginal_invariance(self):
        rng=np.random.Generator(np.random.PCG64(5057813))
        for strength in (0.,.001,.005,1.):
            rho=r.core_density([.17,-.31],rng.normal(size=(2,2,2)),strength,min(.03+strength,1.))
            r.check_density(rho);xx=r.setting_distribution(rho,'XX',strength,.03);legacy=r.setting_distribution(rho,'legacy_q0',strength,.03)
            self.assertAlmostEqual(legacy[2:].sum(),(1+xx@r.Q0)/2,places=14)
            if strength==1:np.testing.assert_allclose(rho,np.eye(4)/4,atol=1e-14,rtol=0)

    def test_symmetric_readout_flips_scale_correlations_correctly(self):
        p=np.array([.47,.13,.19,.21]);rate=.17;q=r.bit_flip_joint(p,rate)
        self.assertAlmostEqual(q@r.Q0,(1-2*rate)*(p@r.Q0))
        self.assertAlmostEqual(q@r.Q1,(1-2*rate)*(p@r.Q1))
        self.assertAlmostEqual(q@(r.Q0*r.Q1),(1-2*rate)**2*(p@(r.Q0*r.Q1)))

    def test_joint_counts_preserve_correlation_and_nonlinear_head_bias(self):
        rng=np.random.Generator(np.random.PCG64(5057814));counts=rng.multinomial(1024,[.5,0,0,.5])
        m=r.moments_from_counts(counts,counts);self.assertEqual(m[4],1);self.assertEqual(m[2],m[3]);self.assertLess(m[2]*m[3],1)
        theta=np.array([4.,0,0,0,0,1.]);f=np.zeros(5);f[0]=.6;plus=r.apply_head('qfrozen_kmeans',theta,f)[0];f[0]=-.6;minus=r.apply_head('qfrozen_kmeans',theta,f)[0]
        self.assertNotAlmostEqual((plus+minus)/2,r.apply_head('qfrozen_kmeans',theta,np.zeros(5))[0],places=2)

    def test_invalid_distribution_core_or_counts_rejected(self):
        with self.assertRaises(ValueError):r.core_density([0,0],np.zeros((1,2,2)))
        with self.assertRaises(ValueError):r.bit_flip_joint([.1,.2,.3,.8],.1)
        with self.assertRaises(ValueError):r.moments_from_counts(np.zeros(4,int),np.ones(4,int))
        with self.assertRaises(ValueError):r.qiskit_count_vector({'001':1})
        with self.assertRaises(ValueError):r.depolarize(np.eye(4)/4,np.inf)

if __name__=='__main__':unittest.main()
