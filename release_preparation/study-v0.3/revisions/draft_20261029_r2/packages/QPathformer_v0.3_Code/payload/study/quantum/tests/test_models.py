"""Meaningful preflight checks: independent circuit oracle, gradients and design."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import qstudy as s
import circuits
import reference_v03 as ref


class ModelChecks(unittest.TestCase):
    def setUp(self):
        rng=np.random.Generator(np.random.PCG64(9101))
        self.x=rng.uniform(-.8,.8,(40,2));self.y=rng.integers(0,2,40)
        self.depth=np.tile(np.arange(1,5),10);self.route=np.tile(np.arange(5),8)

    def test_all_gradients_and_parameter_counts(self):
        counts=[16,16,40,4,8,16,4,5,40,40,40,41,129]
        for method,count in zip(s.METHODS,counts):
            with self.subTest(method=method):
                model=s.Model(method,9102);self.assertEqual(len(model.parameters),count)
                _,g,p,w=model.gradient(self.x,self.y,self.depth,self.route)
                numeric=[];epsilon=1e-6
                for k in range(count):
                    old=model.parameters[k];model.parameters[k]=old+epsilon
                    plus=s.quantum.binary_cross_entropy(self.y,model.predict(self.x,self.depth,self.route))
                    model.parameters[k]=old-epsilon
                    minus=s.quantum.binary_cross_entropy(self.y,model.predict(self.x,self.depth,self.route))
                    model.parameters[k]=old;numeric.append((plus-minus)/(2*epsilon))
                np.testing.assert_allclose(g,numeric,atol=3e-7,rtol=3e-5)

    def test_master_initialization_pairing_and_readout_match(self):
        a=s.Model('scheduled',9103);u=s.Model('untied_assigned',9103)
        np.testing.assert_allclose(a.predict(self.x,self.depth),u.predict(self.x,self.depth),atol=1e-15)
        models=[s.Model(m,9103) for m in s.FIVE_BANK]
        for m in models[1:]:np.testing.assert_array_equal(models[0].parameters,m.parameters)
        banks=models[0].parameters.reshape(5,8)
        self.assertEqual(len({row.tobytes() for row in banks}),5)
        f,r=s.Model('fixed1',9103),s.Model('readout1',9103)
        self.assertEqual(r.parameters[-1],np.pi/2)
        np.testing.assert_array_equal(f.parameters,r.parameters[:4])
        np.testing.assert_allclose(f.predict(self.x,self.depth),r.predict(self.x,self.depth),atol=0)
        for d in (1,2,4):np.testing.assert_array_equal(s.Model(f'fixed{d}',9103).parameters,a.parameters[:4*d])

    def test_bounded_matrices_probabilities_and_analytic_readout(self):
        for seed in (9201,9202,9203):
            rng=np.random.Generator(np.random.PCG64(seed));bank=rng.uniform(-np.pi,np.pi,(4,2,2))
            for x0 in np.linspace(-1,1,5):
                for x1 in np.linspace(-1,1,5):
                    x=np.array([x0,x1])
                    for d,encoding,beta in [(1,False,np.pi/2),(2,False,np.pi/2),(4,False,np.pi/2),(1,True,np.pi/2),(1,False,.41)]:
                        u=circuits.unitary(x,bank[:d],d,encoding,beta);v=ref.unitary(x,bank[:d],d,encoding,beta)
                        np.testing.assert_allclose(u,v,atol=2e-14,rtol=0)
                        np.testing.assert_allclose(u.conj().T@u,np.eye(4),atol=2e-14,rtol=0)
                        p=circuits.predict(x[None],bank[:d],d,encoding,beta)[0]
                        self.assertAlmostEqual(p,ref.probability(x,bank[:d],d,encoding,beta),places=13)
                        if d==1 and not encoding:self.assertAlmostEqual(p,ref.analytic_d1(x,bank,beta),places=13)

    def test_all_circuit_arm_predictions_against_matrix_oracle(self):
        for method in s.METHODS:
            if method.startswith('mlp'):continue
            with self.subTest(method=method):
                m=s.Model(method,9104)
                np.testing.assert_allclose(m.predict(self.x,self.depth,self.route),m.reference_predict(self.x,self.depth,self.route),atol=2e-14,rtol=0)

    def test_inactive_banks_and_prefix_coordinates_have_zero_gradient(self):
        for method in ('hash40','kmeans40'):
            m=s.Model(method,9105);_,g,_,_=m.gradient(self.x,self.y,self.depth,np.zeros(len(self.x),int))
            np.testing.assert_array_equal(g[8:],np.zeros(32))
        m=s.Model('scheduled',9105);_,g,_,_=m.gradient(self.x,self.y,np.ones(len(self.x),int))
        np.testing.assert_array_equal(g[4:],np.zeros(12))

    def test_ensemble_joint_objective_and_identical_bank_invariant(self):
        e=s.Model('ensemble40',9106);f=s.Model('fixed2',9106)
        for k in range(5):e.parameters[8*k:8*(k+1)]=f.parameters
        loss,ge,pe,we=e.gradient(self.x,self.y,self.depth)
        lf,gf,pf,wf=f.gradient(self.x,self.y,self.depth)
        self.assertAlmostEqual(loss,lf,places=14);np.testing.assert_allclose(pe,pf,atol=1e-15)
        for k in range(5):np.testing.assert_allclose(ge[k*8:(k+1)*8],gf/5,atol=1e-14)
        for key in wf:
            self.assertEqual(we[key],wf[key] if key=='model_record_visits' else 5*wf[key])
        distinct=s.Model('ensemble40',9107)
        correct=distinct.gradient(self.x,self.y,self.depth)[1]
        # A mean of independent bank BCE gradients must NOT pass as joint BCE.
        wrong=[]
        for k in range(5):
            f.parameters[:]=distinct.parameters[k*8:(k+1)*8]
            wrong.extend(f.gradient(self.x,self.y,self.depth)[1]/5)
        self.assertGreater(float(np.linalg.norm(correct-np.asarray(wrong))),1e-5)

    def test_work_counts_and_encoding_is_not_equivalent(self):
        n=len(self.x)
        for method,depth,angles in [('fixed1',1,4),('fixed2',2,8),('readout1',1,5),('encoding1',1,4)]:
            m=s.Model(method,9108);w=m.accounting(self.x,self.depth,gradient=True)
            self.assertEqual(w['forward_circuit_examples'],n)
            self.assertEqual(w['shift_circuit_examples'],2*angles*n)
            self.assertEqual(w['layer_applications'],(1+2*angles)*n*depth)
            self.assertEqual(w['feature_rz_gates'],2*w['layer_applications'] if method=='encoding1' else 0)
        a,b=s.Model('fixed1',9108),s.Model('encoding1',9108)
        self.assertGreater(float(np.max(abs(a.predict(self.x,self.depth)-b.predict(self.x,self.depth)))),.01)

    def test_gradient_at_random_angles(self):
        rng=np.random.Generator(np.random.PCG64(9301));bank=rng.uniform(-np.pi,np.pi,(1,2,2));beta=.7
        for encoding,readout in [(False,False),(True,False),(False,True)]:
            j=circuits.jacobian(self.x,bank,1,encoding,beta,readout)
            for k in range(4+readout):
                plus,minus=bank.copy(),bank.copy();bp,bm=beta,beta;eps=1e-6
                if k==4:bp+=eps;bm-=eps
                else:plus.ravel()[k]+=eps;minus.ravel()[k]-=eps
                numeric=(circuits.predict(self.x,plus,1,encoding,bp)-circuits.predict(self.x,minus,1,encoding,bm))/(2*eps)
                np.testing.assert_allclose(j[:,k],numeric,atol=1e-8,rtol=1e-6)

    def test_train_loader_and_official_gate(self):
        with self.assertRaises(ValueError):s.load_population('confirmation','SEALED_test')
        with tempfile.TemporaryDirectory() as folder,patch.object(s,'ROOT',Path(folder)):
            with self.assertRaises(RuntimeError):s.verify_freeze('A',501,'fixed1')
            with self.assertRaises(RuntimeError):s.verify_freeze('B',601,'fixed1')


if __name__=='__main__':unittest.main()
