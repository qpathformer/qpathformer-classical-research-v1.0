"""Read-only audit of preserved explicitly synthetic producer endpoints."""
from pathlib import Path
import json,unittest
from unittest import mock
import numpy as np
import audit_endpoints_v08 as endpoints
import audit_sampling_trace as trace

ROOT=Path(__file__).resolve().parents[2]
class SamplerAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates=sorted(p for p in (ROOT/'quantum/synthetic_fixtures').glob('NOTSTUDY_contract_*')
            if (p/'uniform_control/endpoint_commit.json').is_file())
        if not candidates:raise RuntimeError('Preserved explicitly synthetic endpoint fixtures required')
        cls.source=candidates[-1]
        cls.jobs=json.loads((cls.source/'matrix.json').read_text())['runs']
        cls.job_by_arm={j['arm']:j for j in cls.jobs}
        pop=cls.jobs[0]['population_id']
        with np.load(cls.source/'data'/f'{pop}_train.npz',allow_pickle=False) as z:
            cls.train={k:z[k] for k in ('x','y','ids','source_draw_ids','hash_route','kmeans_route','margin_bin')}
    def invoke(self,name):
        folder=self.source/name;config=json.loads((folder/'config.json').read_text())
        job=self.job_by_arm[config['arm']]
        ledger=[json.loads(s) for s in (folder/'ledger.jsonl').read_text().splitlines()]
        states=np.load(folder/'round_parameters.npy',allow_pickle=False)
        orders=np.load(folder/'record_orders.npy',allow_pickle=False)
        with np.load(folder/'initial_state.npz',allow_pickle=False) as z:initial=z['parameters']
        return trace.audit_trace(folder,job,config['method'],self.train,states,orders,initial,ledger,
                                 endpoints.metric_check,endpoints.native_check)
    def test_priority_and_uniform_traces(self):
        for name in ('first','uniform_control'):
            result=self.invoke(name)['summary']
            self.assertEqual(result['all_adam_updates_replayed'],900)
            self.assertEqual(result['all_refreshes_independently_replayed'],2)
            self.assertEqual(len(result['raw_gradient_spotchecks']),8)
    def test_corrupt_weight_trace_rejected(self):
        original=np.load
        def changed(path,*a,**kw):
            value=original(path,*a,**kw)
            if Path(path).name=='sampling_weights.npy':
                value=np.array(value);value[11,0]+=.01
            return value
        with mock.patch.object(trace.np,'load',side_effect=changed):
            with self.assertRaisesRegex(RuntimeError,'trace hash differs'):
                self.invoke('first')
    def test_corrupt_raw_gradient_rejected(self):
        original=np.load
        def changed(path,*a,**kw):
            value=original(path,*a,**kw)
            if Path(path).name=='minibatch_gradients.npy':
                value=np.array(value);value[800,0]+=.01
            return value
        with mock.patch.object(trace.np,'load',side_effect=changed):
            with self.assertRaisesRegex(RuntimeError,'trace hash differs'):
                self.invoke('first')

if __name__=='__main__':unittest.main(verbosity=2)
