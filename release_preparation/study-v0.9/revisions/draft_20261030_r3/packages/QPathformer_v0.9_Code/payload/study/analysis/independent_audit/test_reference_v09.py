"""Synthetic independent-oracle comparison; producer is imported only by tests."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import sys,unittest,json
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'quantum'))
from models import Model
import study
import reference_v09 as r

STREAMS={'training_order':314159,'paired_circuit_core_initialization':123456789,'mlp_initialization':987654321}
POLICY={'centroids':[[-.7,-.7],[-.7,.7],[.7,-.7],[.7,.7],[0.,0.]],'tau':.4,'residual_scale':[1.]*12}
X=np.array([[-.8,.1],[.25,-.5],[.1,.9],[.7,.4],[-.4,-.6]])
Y=np.array([0,1,0,1,1])

class ReferenceTests(unittest.TestCase):
    def test_initial_and_all_model_predictions_gradients(self):
        rng=np.random.default_rng(859);results=[]
        for arm in r.ARMS:
            m=Model(arm,1,STREAMS,POLICY);theta,master=r.initial(arm,STREAMS)
            np.testing.assert_array_equal(theta,m.parameters);np.testing.assert_array_equal(master,m.master_initial)
            m.parameters+=rng.normal(0,.2,len(theta));x=np.c_[X,X[:,::-1]] if arm=='MLP4' else X
            p,z=r.predict(arm,m.parameters,x,POLICY);expected_p,expected_z=m.predict_with_logits(x)
            np.testing.assert_allclose(p,expected_p,atol=2e-12,rtol=0)
            np.testing.assert_allclose(z,expected_z,atol=1e-10,rtol=0)
            g=r.gradient(arm,m.parameters,x,Y,POLICY);producer=m.gradient(x,Y)[1]
            np.testing.assert_allclose(g,producer,atol=2e-10,rtol=2e-9)
            numeric=np.empty_like(g);eps=2e-6
            for k in range(len(g)):
                plus=m.parameters.copy();minus=plus.copy();plus[k]+=eps;minus[k]-=eps
                numeric[k]=(r.objective(arm,plus,x,Y,POLICY)-r.objective(arm,minus,x,Y,POLICY))/(2*eps)
            np.testing.assert_allclose(g,numeric,atol=3e-8,rtol=0)
            results.append({'arm':arm,'gradient_producer_abs':float(np.max(abs(g-producer))),
                            'gradient_finite_difference_abs':float(np.max(abs(g-numeric)))})
        print('ORACLE_COMPARISONS',json.dumps(results))

    def test_extreme_logits_gate_and_residual(self):
        for arm in ('C_S','C_L','C_R','T_S','T_L','T_R'):
            m=Model(arm,1,STREAMS,POLICY);expert,extra=r.sizes(arm)
            width=14 if arm.startswith('C') else 25
            for bank in range(5):m.parameters[bank*width+(13 if width==14 else 0)]=1000.
            if arm.endswith('_L'):m.parameters[expert:]=np.linspace(-1000,1000,12)
            if arm.endswith('_R'):m.parameters[expert:]=np.linspace(-10,10,12)
            g=r.gradient(arm,m.parameters,X,Y,POLICY)
            np.testing.assert_allclose(g,m.gradient(X,Y)[1],atol=1e-8,rtol=1e-8)
            self.assertTrue(np.isfinite(g).all())

    def test_tensor_circuit_agrees_separate_gate_scalar_oracle(self):
        theta=np.random.default_rng(94).uniform(-3,3,(3,8))
        values=r.moments(theta,X)
        for b in range(3):
            for k in range(len(X)):
                np.testing.assert_allclose(values[b,k],r.scalar_moments(theta[b],X[k]),atol=3e-15,rtol=0)

    def test_metrics_boundaries_and_single_class(self):
        for labels in (Y,np.zeros(5,int),np.ones(5,int)):
            p=np.array([0.,1e-8,.5,.9,1.])
            a,b=r.metrics(labels,p),study.metrics(labels,p)
            for key in ('bce','macro_f1','accuracy','brier','ece10'):self.assertAlmostEqual(a[key],b[key],places=14)
            for key in ('confusion','n','clipped','reliability10'):self.assertEqual(a[key],b[key])

if __name__=='__main__':unittest.main(verbosity=2)
