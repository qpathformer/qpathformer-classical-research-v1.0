"""Small synthetic qualification only; never loads registered population data."""
import copy,json,os,sys,time,unittest
from pathlib import Path
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):os.environ[k]='1'
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from models import Model,Adam,METHODS,PARAMETER_COUNTS,native_losses,sigmoid,trig_features,residual_features
import study

STREAMS={'paired_circuit_core_initialization':123456789,'mlp_initialization':987654321,'training_order':314159}
POLICY={'centroids':[[-.7,-.7],[-.7,.7],[.7,-.7],[.7,.7],[0.,0.]],'tau':.4,'residual_scale':[1.]*12}
X=np.array([[-.8,.1],[.25,-.5],[.1,.9],[.7,.4],[-.4,-.6]],dtype=float);Y=np.array([0,1,0,1,1])

def objective(model,x,y):
    p,z=model.predict_with_logits(x);loss=float(np.mean(native_losses(y,z)))
    if model.method=='LR2':loss+=.0005*float(model.parameters[:2]@model.parameters[:2])
    return loss

class ScienceTests(unittest.TestCase):
    def test_parameter_counts_and_input_dimensions(self):
        for arm in METHODS:
            model=Model(arm,1,STREAMS,POLICY);self.assertEqual(len(model.parameters),PARAMETER_COUNTS[arm])
            x=np.column_stack((X,X)) if arm=='MLP4' else X
            p,z=model.predict_with_logits(x);self.assertTrue(np.isfinite(p).all() and np.isfinite(z).all())
            self.assertEqual(model.extra_size,12 if arm.endswith(('_L','_R')) else 0)
        with self.assertRaises(ValueError):Model('MLP4',1,STREAMS,POLICY).predict(X)

    def test_full_finite_difference_gradients(self):
        rng=np.random.default_rng(412);records=[]
        for arm in METHODS:
            model=Model(arm,1,STREAMS,POLICY);model.parameters+=rng.normal(0,.17,len(model.parameters))
            x=np.column_stack((X,X[:,::-1])) if arm=='MLP4' else X
            loss,g,p,work=model.gradient(x,Y);numeric=np.empty_like(g);eps=2e-6
            for j in range(len(g)):
                old=model.parameters[j];model.parameters[j]=old+eps;plus=objective(model,x,Y)
                model.parameters[j]=old-eps;minus=objective(model,x,Y);model.parameters[j]=old;numeric[j]=(plus-minus)/(2*eps)
            error=float(np.max(abs(g-numeric)));records.append((arm,error))
            self.assertLess(error,3e-8,(arm,error));self.assertAlmostEqual(loss,objective(model,x,Y),places=12)
            self.assertEqual(work['expert_forward_examples'],len(x)*(5 if model.routed and model.routing!='H' else 1))
        print('FINITE_DIFFERENCES',json.dumps(records))

    def test_stable_extreme_mixture_and_residual(self):
        for arm in ('T_S','T_L','T_R','C_S','C_L','C_R'):
            model=Model(arm,1,STREAMS,POLICY)
            # All experts very wrong on some labels: avoid probability division.
            for b in range(5):model.parameters[b*model.bank_width+(13 if model.quantum else 0)]=1000.
            if arm.endswith('_L'):model.parameters[model.expert_size:]=np.linspace(-100,100,12)
            if arm.endswith('_R'):model.parameters[model.expert_size:]=np.linspace(-10,10,12)
            loss,g,p,w=model.gradient(X,Y);self.assertTrue(np.isfinite(g).all());self.assertTrue(np.isfinite(loss));self.assertGreater(loss,100.)
            self.assertTrue(np.any(abs(g)>1e-8))
            # Check representative expert intercept, gate/residual coefficients.
            chosen=[13 if model.quantum else 0,model.expert_size-1]
            if model.extra_size:chosen.extend([model.expert_size,model.expert_size+11])
            for j in chosen:
                old=model.parameters[j];eps=1e-3;model.parameters[j]=old+eps;plus=objective(model,X,Y)
                model.parameters[j]=old-eps;minus=objective(model,X,Y);model.parameters[j]=old
                self.assertLess(abs(g[j]-(plus-minus)/(2*eps)),2e-6,(arm,j))

    def test_probability_mixture_not_logit_average(self):
        model=Model('T_L',1,STREAMS,POLICY)
        for b in range(5):model.parameters[b*25]=(-5,-1,0,2,7)[b]
        model.parameters[125:]=np.linspace(-.3,.3,12)
        logq,q,_=model.gate(X);manual=q@sigmoid(np.array([-5.,-1.,0.,2.,7.]))
        np.testing.assert_allclose(model.predict(X),manual,rtol=0,atol=3e-16)
        self.assertGreater(float(np.max(abs(manual-sigmoid(q@np.array([-5.,-1.,0.,2.,7.]))))),.01)

    def test_initial_and_exact_warmup_expert_equality(self):
        # Actual circuit path qualifies ten updates; all official engineering
        # endpoints additionally provide the full 750-update circuit equality.
        for core,updates in [('C',10),('T',750)]:
            models=[Model(core+'_'+r,1,STREAMS,POLICY) for r in ('S','L','R')]
            opts=[Adam((m.expert_size,)) for m in models]
            extra=[Adam((m.extra_size,),.001) for m in models]
            for i in range(updates):
                for m,o,e in zip(models,opts,extra):
                    _,g,_,_=m.gradient(X,Y);o.step(m.parameters[:m.expert_size],g[:m.expert_size])
                for m in models[1:]:np.testing.assert_array_equal(m.parameters[:m.expert_size],models[0].parameters)
            for m,o,e in zip(models,opts,extra):
                self.assertEqual(o.t,updates);self.assertEqual(e.t,0);self.assertTrue(np.all(m.parameters[m.expert_size:]==0))
            if core=='T':
                m=models[1];o=opts[1];e=extra[1];saved=o.m.copy();_,g,_,_=m.gradient(X,Y)
                o.step(m.parameters[:m.expert_size],g[:m.expert_size]);e.step(m.parameters[m.expert_size:],g[m.expert_size:])
                self.assertEqual(o.t,751);self.assertEqual(e.t,1);np.testing.assert_allclose(o.m,.9*saved+.1*g[:m.expert_size],rtol=0,atol=0)
                self.assertTrue(np.any(m.parameters[m.expert_size:]!=0))

    def test_sampler_and_budget_for_small_dataset(self):
        # Each round retains 4800 draws even when Banknote has fewer records.
        a=np.random.Generator(np.random.PCG64(np.random.SeedSequence(STREAMS['training_order'])))
        b=np.random.Generator(np.random.PCG64(np.random.SeedSequence(STREAMS['training_order'])))
        u=a.random(4800);order=np.floor(823*u).astype(np.uint32)
        np.testing.assert_array_equal(u,b.random(4800));self.assertEqual(len(order),75*64);self.assertLess(int(order.max()),823)
        self.assertGreater(len(order),len(np.unique(order)))
        self.assertEqual(study.SETTINGS['engineering_optimizer_updates'],1500)
        self.assertEqual(study.SETTINGS['optimizer_updates'],15000)

    def test_test_loader_blocked_and_clip_selection(self):
        with self.assertRaises(ValueError):study.load_population('anything','test')
        with self.assertRaises(ValueError):study.load_population('anything','SEALED_test')
        result=study.metrics(np.array([0,1]),np.array([.5,.5]));self.assertEqual(result['confusion'],[[0,1],[0,1]])
        self.assertEqual(result['reliability10'][5]['count'],2)

if __name__=='__main__':unittest.main(verbosity=2)
