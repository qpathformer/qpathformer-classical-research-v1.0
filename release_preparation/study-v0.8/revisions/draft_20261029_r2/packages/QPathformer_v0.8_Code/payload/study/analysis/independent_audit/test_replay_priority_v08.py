"""Pure synthetic priority diagnostics and nested summary comparison."""
from pathlib import Path
import copy,importlib.util,sys,unittest
import numpy as np
import replay_priority_v08 as independent
import replay_metrics_v08 as metrics
import statistics_v08 as stats

OFFICIAL=Path(__file__).resolve().parents[1]/'official_evaluation'
sys.path.insert(0,str(OFFICIAL))
def module(name):
    spec=importlib.util.spec_from_file_location('synthetic_'+name,OFFICIAL/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
producer=module('priority_diagnostics');summaries=module('statistics_core')

class PriorityReplayTests(unittest.TestCase):
    def test_exhaustive_counts_noise_and_probability_mass(self):
        rng=np.random.Generator(np.random.PCG64(901732));n=31
        orders=rng.integers(0,n,(12,n),dtype=np.uint16)
        p=rng.uniform(.5,1.5,(12,n));p/=p.sum(1)[:,None]
        loss=rng.uniform(0,9,(2,n));y=np.arange(n)%2;flips=np.arange(n)%7==0
        routes={'hash':np.arange(n)%5,'kmeans':(np.arange(n)*3)%5}
        expected,counts,exposure=independent.reconstruct(orders,p,loss,y,flips,routes)
        actual,official_exposure=producer.describe_trace(counts,p,y,flips,routes,loss)
        metrics.compare(expected,actual,tolerance=1e-9)
        np.testing.assert_array_equal(exposure,official_exposure)
        self.assertNotAlmostEqual(expected['rounds'][0]['flipped_label_probability_mass'],expected['rounds'][0]['flipped_label_draw_fraction'])
        broken=copy.deepcopy(actual);broken['rounds'][10]['high_loss_draws']+=1
        with self.assertRaises(ValueError):metrics.compare(expected,broken,tolerance=1e-9)
    def test_invalid_or_out_of_range_sampling_identity_fails(self):
        order=np.zeros((12,8),dtype=np.uint16);p=np.full((12,8),1/8)
        order[11,0]=8
        with self.assertRaises(RuntimeError):
            independent.reconstruct(order,p,np.zeros((2,8)),np.zeros(8),np.zeros(8),
                                    {'hash':np.zeros(8),'kmeans':np.zeros(8)})
    def test_complete_population_priority_summary_and_duplicate_rejection(self):
        curve=[{'round':r,'optimizer_updates':75*r,
                'full_training':{'bce':.1,'macro_f1':.8,'accuracy':.85},
                'validation':{'bce':.2,'macro_f1':.7,'accuracy':.75},
                'full_training_native':{'native_bce':.11},'validation_native':{'native_bce':.21}}
               for r in range(1,201)]
        rows=[]
        for family in stats.FAMILIES:
            for i in range(8):
                for seed in stats.SEEDS:
                    for k,arm in enumerate(stats.ARMS):
                        rows.append({'family':family,'population':family+str(i),'seed':seed,'arm':arm,
                            'learning_curve':curve,'priority':{field:(i+k+1)/100 for field in independent.EXPOSURE_FIELDS},
                            'test':{'bce':.1+.01*k+.001*i+.0001*(seed-1601)}})
        actual=summaries.priority_summary(rows);independent.check_summary(rows,actual)
        wrong=copy.deepcopy(actual);wrong['exposure_and_learning'][-1]=wrong['exposure_and_learning'][0]
        with self.assertRaises(RuntimeError):independent.check_summary(rows,wrong)
        wrong=copy.deepcopy(actual);wrong['all_base_priority_effects_descriptive'][0]['population_blocks'][0]['paired_seed_differences'][0]+=.1
        with self.assertRaises(ValueError):independent.check_summary(rows,wrong)

if __name__=='__main__':unittest.main(verbosity=2)
