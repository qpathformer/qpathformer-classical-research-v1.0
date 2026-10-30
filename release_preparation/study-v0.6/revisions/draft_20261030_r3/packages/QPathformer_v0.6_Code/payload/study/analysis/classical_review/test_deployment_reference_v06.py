"""Synthetic parity/cost audit mutations; no actual checkpoint or test data."""
from pathlib import Path
import copy,sys,unittest
import numpy as np
import deployment_reference_v06 as d
import audit_endpoints_v06 as a
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'quantum'))
import deployment_compiler as production
import deployment_benchmark as benchmark

class DeploymentAuditTests(unittest.TestCase):
    def test_projection_matches_laurent_then_rejects_bank_and_basis_mutations(self):
        rng=np.random.Generator(np.random.PCG64(606028))
        for method in ('qscalar_kmeans','qmulti_kmeans'):
            theta=a.expected_initial(method,1201)[0];theta+=rng.uniform(-.3,.3,theta.shape)
            compiled=production.compile_model(method,theta);expected,report=d.coefficients(method,theta,compiled)
            self.assertLess(report['maximum_coefficient_absolute_error'],2e-14)
            for bad in (compiled[::-1],compiled.reshape(5,5,5).transpose(0,2,1).reshape(5,25)):
                with self.assertRaisesRegex(ValueError,'Coefficient tolerance'):d.coefficients(method,theta,bad)
            corrupt=compiled.copy();corrupt[2,13]+=1e-8
            with self.assertRaisesRegex(ValueError,'Coefficient tolerance'):d.coefficients(method,theta,corrupt)

    def test_class_band_requires_both_and_preserves_raw_disagreements(self):
        p=np.array([.5,.5+.5*d.BAND]);q=np.array([.5-d.BAND/2,.5-d.BAND/2]);z=np.zeros(2)
        r=d.parity(p,z,q,z,np.array([41,42]));self.assertEqual(r['class_disagreements'],2)
        self.assertEqual([x['record_id'] for x in r['disagreements']],[41,42])
        q[0]=.5-1.5*d.BAND
        with self.assertRaises(ValueError):d.parity(p,z,q,z,np.array([41,42]))
        q=p.copy();zz=z.copy();zz[1]=1.01e-9
        with self.assertRaises(ValueError):d.parity(p,z,q,zz,np.array([41,42]))

    def test_true_voronoi_edges_independent_intersection_and_mutations(self):
        centers=np.array([[-.7,-.4],[-.4,.7],[0.,0.],[.6,-.6],[.7,.5]])
        policy={'centroids':centers.tolist()};_,points,records=benchmark.fixed_parity_inputs(policy)
        result=d.verify_boundary_fixtures(centers,points,records)
        self.assertGreater(result['edge_count'],4)
        bad=points.copy();bad[0,0]+=.001
        with self.assertRaisesRegex(ValueError,'displacement'):d.verify_boundary_fixtures(centers,bad,records)
        rec=copy.deepcopy(records);rec[1]['centroid_pair']=[0,4]
        with self.assertRaisesRegex(ValueError,'pair'):d.verify_boundary_fixtures(centers,points,rec)
        with self.assertRaisesRegex(ValueError,'Missing, duplicate or unordered'):
            d.verify_boundary_fixtures(centers,points[3:],records[3:])

    def test_equal_centroid_distance_selects_lowest_index(self):
        c=np.array([[-1.,0.],[-.5,0.],[0.,0.],[.5,0.],[1.,0.]])
        np.testing.assert_array_equal(d.route([[-.75,0.],[.25,0.]],c),[0,2])

    def test_exact_timing_work_quartiles_and_missing_repeat_rejected(self):
        for size,(calls,n) in {1:(128,128),32:(32,1024),1024:(32,32768)}.items():
            rows=[{'key':'fake','population':'synthetic','seed':0,'method':'trig_global','representation':'fast_trig',
                'batch_size':size,'trial':i,'warmup':i<0,'calls':calls,'prediction_records':n,
                'elapsed_ns':n*(16-i),'ns_per_record':float(16-i),'probability_sha256':'a','logit_sha256':'b'} for i in range(-2,15)]
            summary=d.timing_summary(rows);self.assertEqual(summary['median_ns_per_record'],9.)
            self.assertEqual(summary['q25_ns_per_record'],5.5);self.assertEqual(summary['q75_ns_per_record'],12.5)
            with self.assertRaises(ValueError):d.timing_summary(rows[:-1])
            broken=copy.deepcopy(rows);broken[7]['prediction_records']-=1
            with self.assertRaises(ValueError):d.timing_summary(broken)
            broken=copy.deepcopy(rows);broken[8]['probability_sha256']='c'
            with self.assertRaises(ValueError):d.timing_summary(broken)

if __name__=='__main__':unittest.main()
