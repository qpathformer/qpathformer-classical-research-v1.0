import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
import numpy as np
import circuits
import reference_v03
import models
import study
import launch_stage


class ModelTests(unittest.TestCase):
    def test_parameter_shapes_and_initialization_pairing(self):
        counts=(8,40,40,129,45,45,25,125,125)
        for method,count in zip(models.METHODS,counts):
            m=models.Model(method,701);self.assertEqual(m.parameters.size,count)
        for family in ('q2','mlp','trig'):
            a=models.Model(family+'_hash',701);b=models.Model(family+'_kmeans',701)
            np.testing.assert_array_equal(a.parameters,b.parameters)
        q=models.Model('q2_hash',701).parameters.reshape(5,8)
        self.assertFalse(np.array_equal(q[0],q[1]))
        np.testing.assert_array_equal(q[0],models.Model('q2_global',701).parameters)
        self.assertFalse(np.array_equal(models.Model('mlp_hash',701).parameters[:9],models.Model('mlp_hash',701).parameters[9:18]))

    def test_complete_tensor_features(self):
        x=np.array([[0.,0.],[.3,-.7]])
        actual=models.trig_features(x)
        for row,xy in zip(actual,x):
            a=[1,np.cos(np.pi*xy[0]),np.sin(np.pi*xy[0]),np.cos(2*np.pi*xy[0]),np.sin(2*np.pi*xy[0])]
            b=[1,np.cos(np.pi*xy[1]),np.sin(np.pi*xy[1]),np.cos(2*np.pi*xy[1]),np.sin(2*np.pi*xy[1])]
            np.testing.assert_allclose(row,[v*w for v in a for w in b],atol=2e-16,rtol=0)
        self.assertEqual(actual.shape,(2,25));np.testing.assert_array_equal(actual[:,0],[1,1])

    def test_full_matrix_agreement(self):
        rng=np.random.Generator(np.random.PCG64(94701))
        for _ in range(60):
            x=rng.uniform(-1,1,2);bank=rng.uniform(-np.pi,np.pi,(2,2,2))
            a=circuits.unitary(x,bank,2);b=reference_v03.unitary(x,bank,2)
            np.testing.assert_allclose(a,b,atol=2e-12,rtol=0)
            p=circuits.predict(x[None],bank,2)[0]
            self.assertLessEqual(abs(p-float(np.sum(abs(b[2:,0])**2))),2e-12)

    def test_all_family_routed_gradients(self):
        rng=np.random.Generator(np.random.PCG64(94702));x=rng.uniform(-.8,.8,(11,2));y=np.arange(11)%2
        route=np.array([0,1,2,3,0,1,2,3,0,1,2]) # bank4 empty
        for method in models.METHODS:
            m=models.Model(method,701);r=None if m.routing=='global' else route
            if m.family=='trig':m.parameters[:]=rng.uniform(-.15,.15,m.parameters.shape)
            loss,g,p,w=m.gradient(x,y,r);h=1e-6;numeric=np.zeros_like(g)
            for j in range(len(g)):
                old=m.parameters[j];m.parameters[j]=old+h;plus=models.binary_cross_entropy(y,m.predict(x,r))
                m.parameters[j]=old-h;minus=models.binary_cross_entropy(y,m.predict(x,r));m.parameters[j]=old
                numeric[j]=(plus-minus)/(2*h)
            np.testing.assert_allclose(g,numeric,atol=2e-7,rtol=2e-5,err_msg=method)
            if m.banks==5:np.testing.assert_array_equal(g[-m.bank_width:],0.)

    def test_clipped_saturated_gradients(self):
        x=np.array([[0.,0.],[.1,-.2]]);y=np.array([0,1])
        for method in ('mlp_global','trig_global'):
            for sign in (-1,1):
                m=models.Model(method,701);m.parameters[:]=0
                m.parameters[-1 if m.family=='mlp' else 0]=sign*100.
                loss,g,p,w=m.gradient(x,y)
                self.assertTrue(np.isfinite(loss));np.testing.assert_array_equal(g,0.)
        for sign in (-1,1):
            m=models.Model('q2_global',701);m.parameters[:]=0;m.parameters[4]=sign*np.pi/2;m.parameters[6]=np.pi/2
            loss,g,p,w=m.gradient(np.zeros((2,2)),y)
            self.assertTrue(np.all((p<models.CLIP)|(p>1-models.CLIP)));np.testing.assert_array_equal(g,0.)

    def test_clipping_boundary_loss_and_threshold_convention(self):
        p=np.array([models.CLIP-1e-16,models.CLIP,models.CLIP+1e-16,1-models.CLIP-1e-16,1-models.CLIP,1-models.CLIP+1e-16])
        y=np.array([1,1,1,0,0,0]);a=models.binary_cross_entropy(y,p)
        q=np.clip(p,models.CLIP,1-models.CLIP)
        self.assertEqual(a,float(-np.mean(y*np.log(q)+(1-y)*np.log1p(-q))))
        oracle=p.copy();oracle[3]-=1e-16
        self.assertLess(abs(a-models.binary_cross_entropy(y,oracle)),1e-8)
        d=study.metrics(np.array([0,1,0]),np.array([np.nextafter(.5,0),.5,np.nextafter(.5,1)]))
        self.assertEqual(d['confusion'],[[1,1],[0,1]])

    def test_route_validation_and_actual_work(self):
        x=np.zeros((6,2));r=np.array([0,1,2,3,4,0]);y=np.arange(6)%2
        for method in models.METHODS:
            m=models.Model(method,701);rr=None if m.routing=='global' else r
            w=m.gradient(x,y,rr)[3]
            self.assertEqual(w['model_record_visits'],6);self.assertEqual(w['bank_record_visits'],6)
            self.assertEqual(w['circuit_examples'],102 if m.family=='q2' else 0)
            if m.family=='trig':self.assertEqual(w['trig_feature_values'],300)
            if m.family=='mlp':self.assertEqual(w['mlp_hidden_evaluations'],12*m.hidden)
        with self.assertRaises(ValueError):models.Model('q2_hash',701).predict(x,[0]*5+[5])
        with self.assertRaises(ValueError):models.Model('mlp_global',701).predict(x,r)

    def test_no_test_loader_and_no_implicit_official_training(self):
        with self.assertRaises(ValueError):study.load_population('engineering_circle','test')
        with self.assertRaises(ValueError):study.load_population('confirmation_circle_1','SEALED_test')
        with self.assertRaises(RuntimeError):study.verify_freeze('A','development_circle',999,'q2_global')
        with self.assertRaises(RuntimeError):study.verify_freeze('A','engineering_circle',701,'q2_global')

    def test_registered_execution_orders(self):
        for stage in ('A','B'):
            for population in study.POPULATIONS[stage]:
                for seed in study.SEEDS[stage]:
                    order=launch_stage.method_order(stage,population,seed)
                    self.assertEqual(len(order),9);self.assertEqual(set(order),set(models.METHODS))


if __name__=='__main__':unittest.main()
