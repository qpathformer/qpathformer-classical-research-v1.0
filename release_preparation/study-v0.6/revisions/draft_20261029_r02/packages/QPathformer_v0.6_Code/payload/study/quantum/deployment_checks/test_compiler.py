import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
import numpy as np
import models
import deployment_compiler as c


class CompilerTests(unittest.TestCase):
    def test_orthogonal_period_two_nodes(self):
        b=c.real_basis(c.NODES)
        np.testing.assert_allclose(b.T@b/5,np.diag(c.NORMS),atol=3e-16,rtol=0)
        self.assertEqual(len(np.unique(c.NODES)),5)
        self.assertEqual(c.GRID.shape,(25,2))
        self.assertLess(c.NODES[-1]-c.NODES[0],2.)

    def test_both_heads_off_grid_and_forced_banks(self):
        rng=np.random.Generator(np.random.PCG64(690617))
        x=np.r_[rng.uniform(-1,1,(173,2)),[[-1,-1],[1,1],[-1,1],[1,-1],[0,0]]]
        route=np.arange(len(x))%5
        for name in c.METHODS:
            for magnitude in (.1,1.,10.):
                m=models.Model(name,1101);m.parameters[:]=rng.uniform(-magnitude,magnitude,m.parameters.size)
                with patch.object(models.Model,'route_for',side_effect=RuntimeError('Construction must not route')):
                    table,records=c.compile_model(name,m.parameters,True)
                a,az=m.predict_with_logits(x,route);b,bz=c.predict_compiled(x,table,route)
                np.testing.assert_allclose(az,bz,atol=1e-11,rtol=0)
                np.testing.assert_allclose(a,b,atol=2e-12,rtol=0)
                for bank,record in enumerate(records):
                    self.assertTrue(record['forced_bank']);self.assertEqual(record['bank'],bank)
                    p,z=m.predict_with_logits(c.GRID,np.full(25,bank))
                    np.testing.assert_array_equal(z,record['grid_logits'])
                self.assertEqual(sum(r['construction_statevector_examples'] for r in records),125)

    def test_constant_logits_and_invalid_contracts(self):
        core=np.zeros((2,2,2));head=np.array([0.,13.])
        coeff=c.compile_bank(core,head,1)
        np.testing.assert_allclose(coeff,np.r_[13.,np.zeros(24)],atol=5e-15,rtol=0)
        with self.assertRaises(ValueError):c.compile_bank(np.zeros((3,2,2)),head,1)
        with self.assertRaises(ValueError):c.compile_model('trig_kmeans',np.zeros(125))
        with self.assertRaises(ValueError):c.compile_bank(core,np.zeros(4),3)
        with self.assertRaises(ValueError):c.predict_compiled(np.zeros((1,2)),np.zeros((5,25)),[5])
        with self.assertRaises(ValueError):c.compile_model('qscalar_kmeans',np.zeros(70))

    def test_learned_trig_uses_identical_coefficient_kernel(self):
        rng=np.random.Generator(np.random.PCG64(690625));x=rng.uniform(-1,1,(137,2));route=np.arange(len(x))%5
        for name in ('trig_global','trig_kmeans'):
            model=models.Model(name,1101);model.parameters[:]=rng.uniform(-4,4,model.parameters.size)
            table=c.learned_trig_coefficients(name,model.parameters)
            np.testing.assert_array_equal(table.reshape(-1),model.parameters)
            routes=None if name=='trig_global' else route
            p,z=model.predict_with_logits(x,routes);fp,fz=c.predict_coefficients(x,table,routes)
            np.testing.assert_allclose(fz,z,atol=2e-14,rtol=0)
            np.testing.assert_allclose(fp,p,atol=2e-15,rtol=0)
            self.assertEqual(c.inference_work(len(x),len(table))['coefficient_bytes'],table.nbytes)
        with self.assertRaises(ValueError):c.predict_coefficients(x,np.zeros((1,25)),route)
        with self.assertRaises(ValueError):c.learned_trig_coefficients('qscalar_kmeans',np.zeros(50))


if __name__=='__main__':unittest.main()
