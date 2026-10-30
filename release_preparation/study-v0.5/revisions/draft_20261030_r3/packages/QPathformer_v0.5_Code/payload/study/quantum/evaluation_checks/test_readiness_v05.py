"""Generated coordinates and untrained states only; no registered data loads."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
import tempfile
import inspect
from unittest.mock import patch
import numpy as np
from qiskit.quantum_info import Operator
import local_readiness as r
import study as s


class ReadinessTests(unittest.TestCase):
    def test_public_capsule_requires_release_with_no_engineering_bypass(self):
        self.assertEqual(list(inspect.signature(r.run).parameters),['output'])
        with tempfile.TemporaryDirectory(prefix='qpath_capsule_gate_') as name:
            output=Path(name)/'must_remain_absent'
            with patch.object(r.evaluation,'verify_guard',side_effect=RuntimeError('root release absent')) as gate:
                with self.assertRaisesRegex(RuntimeError,'root release absent'):r.run(output)
                gate.assert_called_once_with(output_must_be_absent=False)
            self.assertFalse(output.exists())

    def test_joint_moment_signs_and_legacy_identity(self):
        rng=np.random.default_rng(590501)
        for _ in range(40):
            x=rng.uniform(-1,1,2);bank=rng.uniform(-np.pi,np.pi,(2,2,2));core=r.build_core(x,bank)
            psi=Operator(core).data[:,0]
            expected={k:float(np.real(np.vdot(psi,P@psi))) for k,P in zip(r.MOMENTS,r.OPERATORS)}
            joints={k:r.valid_joint(abs(Operator(r.measurement_circuit(core,k)).data[:,0])**2) for k in ('XX','ZZ')}
            actual=r.estimate_moments(joints)
            np.testing.assert_allclose([actual[k] for k in r.MOMENTS],[expected[k] for k in r.MOMENTS],atol=2e-12,rtol=0)
            legacy=abs(Operator(r.measurement_circuit(core,'legacy')).data[:,0])**2
            self.assertAlmostEqual(float(sum(legacy[2:])),(1+expected['X0'])/2,places=13)
            self.assertEqual(dict(core.count_ops()),{'ry':8,'rz':4,'cx':2})
            self.assertEqual(r.measurement_circuit(core,'XX').count_ops()['ry'],10)

    def test_joint_readout_channel_and_covariance(self):
        q=np.array([.3,.1,.2,.4]);rate=.03;actual=r.readout_joint(q,rate);manual=np.zeros(4)
        for before in range(4):
            for after in range(4):
                flips=(before^after).bit_count();manual[after]+=q[before]*rate**flips*(1-rate)**(2-flips)
        np.testing.assert_allclose(actual,manual,atol=1e-16,rtol=0)
        # Perfectly correlated joint Z bits imply identical individual outcomes;
        # estimating the two moments from independent counts would violate this.
        counts=np.random.default_rng(590502).multinomial(1024,[.4,0,0,.6]);m=r.SIGNS@(counts/1024)
        self.assertEqual(m[0],m[1]);self.assertEqual(m[2],1.)

    def test_multivariate_head_and_band(self):
        m={'X0':.2,'X1':-.4,'Z0':.8,'Z1':-.3,'Z0Z1':.1};row={'method':'qmulti_kmeans','head':[1.,2.,3.,4.,5.,.2]}
        z=sum(row['head'][i]*m[k] for i,k in enumerate(r.MOMENTS))+.2
        self.assertAlmostEqual(r.head_probability(row,m),1/(1+np.exp(-z)),places=15)
        self.assertTrue(r.classification_pair(.5,np.nextafter(.5,0))['class_disagreement'])
        with self.assertRaises(RuntimeError):r.classification_pair(.5,.5-1e-13)


if __name__=='__main__':unittest.main()
