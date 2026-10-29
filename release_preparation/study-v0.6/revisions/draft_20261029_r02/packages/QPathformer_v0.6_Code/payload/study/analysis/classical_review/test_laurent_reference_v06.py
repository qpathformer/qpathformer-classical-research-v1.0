"""Synthetic-only independent polynomial/model checks, no data or checkpoints."""
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np
import laurent_reference_v06 as polynomial
import reference_v06 as matrix

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'quantum'))
spec=importlib.util.spec_from_file_location('v06_model_under_review',ROOT/'quantum/models.py')
producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
compiler_spec=importlib.util.spec_from_file_location('v06_compiler_under_review',ROOT/'quantum/deployment_compiler.py')
compiler=importlib.util.module_from_spec(compiler_spec);compiler_spec.loader.exec_module(compiler)


class PolynomialChecks(unittest.TestCase):
    def setUp(self): self.rng=np.random.default_rng(606019)

    def test_amplitude_polynomial_against_separate_scalar_matrix_gates(self):
        for _ in range(6):
            core=self.rng.uniform(-8,8,(2,2,2));terms=polynomial.amplitude_coefficients(core)
            self.assertEqual(set(terms),{(a,b) for a in (-1,0,1) for b in (-1,0,1)})
            for x in self.rng.uniform(-3,3,(19,2)):
                actual=sum(a*np.exp(1j*np.pi*np.dot(f,x)) for f,a in terms.items())
                np.testing.assert_allclose(actual,matrix.scalar_state(x,core),atol=2e-14,rtol=0)

    def test_all_five_observables_on_offgrid_edges_and_periodic_points(self):
        inputs=np.r_[self.rng.uniform(-1,1,(71,2)),[[-1,-1],[-1,1],[1,-1],[1,1],[0,0],[2.2,-3.4]]]
        for core in [np.zeros((2,2,2)),*self.rng.uniform(-np.pi,np.pi,(8,2,2,2))]:
            coefficients,diagnostics=polynomial.observable_trig_coefficients(core)
            expected=np.array([matrix.scalar_observables(x,core) for x in inputs])
            np.testing.assert_allclose(polynomial.features(inputs)@coefficients.T,expected,atol=2e-14,rtol=0)
            self.assertLess(diagnostics['maximum_conjugacy_residual'],2e-14)
            self.assertLess(diagnostics['maximum_real_basis_imaginary_residual'],2e-14)

    def test_bias_scalar_multi_and_head_linearity(self):
        core=self.rng.normal(size=(2,2,2));head=np.array([2.7,-1.8])
        scalar=polynomial.compile_bank(core,head,1)
        multi=polynomial.compile_bank(core,np.r_[head[0],0,0,0,0,head[1]],5)
        np.testing.assert_array_equal(scalar,multi)
        np.testing.assert_array_equal(polynomial.compile_bank(core,-head,1),-scalar)
        constant=polynomial.compile_bank(core,np.array([0.,7.25]),1)
        np.testing.assert_array_equal(constant,np.r_[7.25,np.zeros(24)])

    def test_five_bank_mixed_batches_and_large_native_logits(self):
        x=self.rng.uniform(-1,1,(85,2));route=np.tile(np.arange(5),17)
        for method,count in [('qscalar_kmeans',1),('qmulti_kmeans',5)]:
            packed=np.c_[self.rng.uniform(-np.pi,np.pi,(5,8)),self.rng.uniform(-200,200,(5,count+1))].ravel()
            coefficients=polynomial.compile_model(method,packed)
            p,z=polynomial.predict_compiled(x,coefficients,route)
            expected_p,expected_z=matrix.scalar_predict_with_logits(method,packed,x,route)
            np.testing.assert_allclose(z,expected_z,atol=1e-10,rtol=0)
            np.testing.assert_allclose(p,expected_p,atol=2e-12,rtol=0)
            order=self.rng.permutation(len(x))
            pp,zz=polynomial.predict_compiled(x[order],coefficients,route[order])
            np.testing.assert_array_equal(pp,p[order]);np.testing.assert_array_equal(zz,z[order])
            self.assertTrue(np.any(np.abs(z)>100))
            self.assertTrue(np.isfinite(matrix.stable_logit_bce(route%2,z)))

    def test_coefficient_l1_global_bound_and_sigmoid_lipschitz(self):
        c=self.rng.normal(size=(5,25));delta=self.rng.uniform(-1e-6,1e-6,(5,25))
        x=self.rng.uniform(-4,4,(200,2));route=np.tile(np.arange(5),40)
        p,z=polynomial.predict_compiled(x,c,route);q,w=polynomial.predict_compiled(x,c+delta,route)
        bound=np.abs(delta).sum(axis=1)[route]
        self.assertTrue(np.all(np.abs(z-w)<=bound+1e-14))
        self.assertTrue(np.all(np.abs(p-q)<=bound/4+1e-14))

    def test_constant_half_and_saturated_head(self):
        x=np.array([[.13,.21],[-.6,.84]]);route=np.array([0,4]);core=np.zeros((2,2,2))
        for bias in [0.,1000.,-1000.]:
            bank=polynomial.compile_bank(core,np.array([0.,bias]),1)
            p,z=polynomial.predict_compiled(x,np.tile(bank,(5,1)),route)
            np.testing.assert_array_equal(z,np.full(2,bias))
            np.testing.assert_array_equal(p,np.full(2,.5 if bias==0 else 1. if bias>0 else 0.))

    def test_invalid_contract_is_rejected(self):
        for core in [np.zeros((1,2,2)),np.zeros((3,2,2)),np.full((2,2,2),np.nan)]:
            with self.assertRaises(ValueError):polynomial.compile_bank(core,np.zeros(2),1)
        for method in ['q2_kmeans','qfrozen_kmeans','mlp_global']:
            with self.assertRaises(ValueError):polynomial.compile_model(method,np.zeros(50))
        with self.assertRaises(ValueError):polynomial.compile_bank(np.zeros((2,2,2)),np.zeros(3),2)
        with self.assertRaises(ValueError):polynomial.predict_compiled([[0,0]],np.zeros((5,25)),[.5])
        with self.assertRaises(ValueError):polynomial.predict_compiled([[np.inf,0]],np.zeros((5,25)),[0])


class CurrentProducerMath(unittest.TestCase):
    def test_all_six_predictions_and_gradients_against_independent_reference(self):
        rng=np.random.default_rng(606020);x=rng.uniform(-.95,.95,(15,2));route=np.tile(np.arange(5),3);y=np.arange(15)%2
        for method in matrix.METHODS:
            model=producer.Model(method,10901);routes=None if method.endswith('_global') else route
            p,z=model.predict_with_logits(x,routes);rp,rz=matrix.scalar_predict_with_logits(method,model.parameters,x,routes)
            np.testing.assert_allclose(z,rz,atol=2e-13,rtol=0);np.testing.assert_allclose(p,rp,atol=2e-13,rtol=0)
            loss,gradient,_,_=model.gradient(x,y,routes)
            self.assertAlmostEqual(loss,matrix.stable_logit_bce(y,rz),places=13)
            numerical=np.empty_like(gradient);step=1e-6
            for j in range(len(gradient)):
                plus=model.parameters.copy();minus=plus.copy();plus[j]+=step;minus[j]-=step
                numerical[j]=(matrix.native_loss(method,plus,x,y,routes)-matrix.native_loss(method,minus,x,y,routes))/(2*step)
            np.testing.assert_allclose(gradient,numerical,atol=3e-8,rtol=1e-6,err_msg=method)

    def test_current_producer_scalar_multi_against_compilation(self):
        rng=np.random.default_rng(606021);x=rng.uniform(-1,1,(125,2));route=np.repeat(np.arange(5),25)
        for method in ('qscalar_kmeans','qmulti_kmeans'):
            model=producer.Model(method,10901)
            # Noninitial random parameters, including nonzero head weights for every moment.
            model.parameters[:]=rng.uniform(-3,3,len(model.parameters))
            coefficients=polynomial.compile_model(method,model.parameters)
            p,z=polynomial.predict_compiled(x,coefficients,route);op,oz=model.predict_with_logits(x,route)
            np.testing.assert_allclose(z,oz,atol=1e-12,rtol=0);np.testing.assert_allclose(p,op,atol=2e-13,rtol=0)

    def test_production_grid_coefficients_against_laurent_and_native_predictions(self):
        rng=np.random.default_rng(606022);x=rng.uniform(-1,1,(155,2));routes=np.tile(np.arange(5),31)
        for method,count in [('qscalar_kmeans',1),('qmulti_kmeans',5)]:
            for scale in [0.,1.,100.]:
                parameters=np.c_[rng.uniform(-9,9,(5,8)),rng.uniform(-scale,scale,(5,count+1))].ravel()
                reference=polynomial.compile_model(method,parameters)
                current,evidence=compiler.compile_model(method,parameters,True)
                np.testing.assert_allclose(current,reference,atol=1e-10,rtol=1e-12)
                self.assertLess(float(np.abs(current-reference).sum(axis=1).max()),2e-11)
                p,z=compiler.predict_compiled(x,current,routes)
                target_p,target_z=matrix.scalar_predict_with_logits(method,parameters,x,routes)
                np.testing.assert_allclose(z,target_z,atol=1e-9,rtol=0)
                np.testing.assert_allclose(p,target_p,atol=2e-12,rtol=0)
                self.assertEqual([row['bank'] for row in evidence],list(range(5)))
                for row in evidence:
                    self.assertTrue(row['forced_bank']);self.assertEqual(row['construction_statevector_examples'],25)
                    self.assertEqual(row['construction_moment_values'],25*count)
                # The construction mesh has exactly five distinct nodes per coordinate.
                self.assertEqual(len(np.unique(evidence[0]['grid'],axis=0)),25)

    def test_compiler_coefficient_order_and_bank_swap_mutations_are_detectable(self):
        rng=np.random.default_rng(606023)
        packed=np.c_[rng.uniform(-2,2,(5,8)),rng.normal(size=(5,6))].ravel()
        expected=polynomial.compile_model('qmulti_kmeans',packed)
        current=compiler.compile_model('qmulti_kmeans',packed)
        self.assertGreater(np.max(np.abs(current[::-1]-expected)),1e-3)
        self.assertGreater(np.max(np.abs(current.reshape(5,5,5).transpose(0,2,1).reshape(5,25)-expected)),1e-3)

if __name__=='__main__':unittest.main(verbosity=2)
