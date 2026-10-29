import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
import numpy as np
import deployment_benchmark as b
import routers


class BenchmarkTests(unittest.TestCase):
    def test_fixed_geometry_and_edge_pairing(self):
        policy={'schema':'qpath-v03-input-route-1','banks':5,'centroids':[[-.6,-.5],[-.4,.6],[0.,0.],[.5,-.4],[.6,.6]]}
        offgrid,x,records=b.fixed_parity_inputs(policy)
        self.assertEqual(offgrid.shape,(128,2));self.assertGreater(len(x),0)
        np.testing.assert_array_equal(offgrid,b.fixed_parity_inputs(policy)[0])
        centers=np.asarray(policy['centroids'])
        for point,record in zip(x,records):
            self.assertTrue(np.all(abs(point)<=1+1e-10))
            d=((centers-point)**2).sum(axis=1);i,j=record['centroid_pair']
            if record['side']==0:
                self.assertLess(abs(d[i]-d[j]),2e-12)
                self.assertLessEqual(d[i],d.min()+2e-12)
            else:
                self.assertEqual(int(routers.route(point[None,:],policy,'kmeans')[0]),i if record['side']<0 else j)

    def test_timed_work_and_output_arrays(self):
        x=np.zeros((1024,2))
        expected={1:(128,128),32:(32,1024),1024:(32,32768)}
        for size,(calls,records) in expected.items():
            batches=b.trial_batches(x,size);seen=[]
            def forward(a):seen.append(len(a));return np.full(len(a),.5),np.zeros(len(a))
            elapsed,p,z=b.measure_trial(forward,batches)
            self.assertEqual(len(seen),calls);self.assertEqual(sum(seen),records)
            self.assertEqual(len(p),records);self.assertEqual(len(z),records);self.assertGreaterEqual(elapsed,0)

    def test_parity_rejects_nonmatching_outputs_and_discloses_threshold(self):
        p=np.array([.5-1e-13,.2]);q=np.array([.5+1e-13,.2]);z=np.zeros(2)
        result=b.parity(p,z,q,z,np.array([7,8]));self.assertEqual(result['class_disagreements'],1)
        self.assertEqual(result['disagreements'][0]['record_id'],7)
        with self.assertRaises(RuntimeError):b.parity(p,z,np.array([.6,.2]),z)
        with self.assertRaises(RuntimeError):b.parity(p,z,p,np.ones(2))
        p=np.array([.5-3e-12]);q=np.array([.5+1e-13])
        with self.assertRaises(RuntimeError):b.parity(p,np.zeros(1),q,np.zeros(1))


if __name__=='__main__':unittest.main()
