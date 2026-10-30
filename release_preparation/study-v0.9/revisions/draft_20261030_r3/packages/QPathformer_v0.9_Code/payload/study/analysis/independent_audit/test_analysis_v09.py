"""Constructed numerical and inert636-release tests; no official test outcomes."""
import json,math,shutil,sys,tempfile,unittest,uuid
from pathlib import Path
import numpy as np
import audit_endpoints_v09 as a
import reference_v09 as ref
import statistics_v09 as independent
import replay_analysis_v09 as replay

AUTHOR=a.ROOT/'analysis/author';sys.path.insert(0,str(AUTHOR))
import metrics_v09 as author_metrics
import evaluate_v09 as author_eval
import test_author_v09 as author_tests
from scipy.stats import t as scipy_t

TESTROOT=a.HERE/'test_runs'/('analysis_'+uuid.uuid4().hex);TESTROOT.mkdir(parents=True)
MEASUREMENTS=[]

class AnalysisTests(unittest.TestCase):
    def test_independent_metrics_edges_ties_random_and_empty(self):
        g=np.random.default_rng(63312)
        edges=np.linspace(0,1,11)
        for n in (0,1,2,53,1600):
            p=g.choice(np.r_[edges,np.nextafter(edges[1:-1],0.),np.nextafter(edges[1:-1],1.)],size=n)
            y=g.integers(0,2,n);z=g.normal(0,10,n)
            replay.Comparisons().tree(author_metrics.metrics(y,p,z),independent.metrics(y,p,z))
        for y in (np.zeros(5),np.ones(5),np.array([0,1,0,1,1])):
            p=np.array([0,.5,.5,1,1e-8]);z=np.array([-1000,0,0,1000,-1000.])
            replay.Comparisons().tree(author_metrics.metrics(y,p,z),independent.metrics(y,p,z))

    def test_independent_beta_t7_quantiles_and_probabilities(self):
        differences=[]
        for confidence in (.90,.95,1-.05/12,.9999):
            actual=independent.critical_t7(confidence);expected=scipy_t.ppf((1+confidence)/2,7)
            self.assertAlmostEqual(actual,expected,delta=2e-10);differences.append(abs(actual-expected))
        for value in (0.,1e-12,1e-10,1e-8,1e-6,1e-5,.001,.5,1.,3.,8.,20.,1000.):
            self.assertAlmostEqual(independent.two_sided_t7(value),2*scipy_t.sf(value,7),delta=2e-13)
        MEASUREMENTS.append({'maximum_t7_quantile_error':max(differences)})

    def synthetic_rows(self):
        rows=[];families=('checkerboard','spiral','annulus','disks');arms=('C_H','C_S','C_L','C_R','T_H','T_S','T_L','T_R','G121')
        for family in families:
            for pop in range(8):
                for seed in (1801,1802):
                    for i,arm in enumerate(arms):
                        value=.5+.001*i*(pop+1)+.01*(seed-1801)
                        rows.append({'job_id':f'{family}/{pop}/{seed}/{arm}','family':family,'population':f'{family}_{pop}','seed':seed,'arm':arm,
                          'test':{k:value for k in independent.SCALARS}})
        for seed in range(1901,1906):
            for arm in arms+('MLP2','MLP4','LR2'):rows.append({'job_id':f'banknote/{seed}/{arm}','family':'banknote','population':'banknote_01','seed':seed,'arm':arm,'test':{k:.2+.001*(seed-1901) for k in independent.SCALARS}})
        return rows

    def test_all636_registered_population_statistics(self):
        protocol=a.read(a.ROOT/'governance/ANALYSIS_PROTOCOL.json');rows=self.synthetic_rows();comparison=replay.Comparisons()
        comparison.tree(author_metrics.analyze(rows,protocol),independent.analyze(rows,protocol),'statistics')
        self.assertEqual(len(independent.analyze(rows,protocol)['primary_contrasts']),12)
        MEASUREMENTS.append({'statistical_comparisons':comparison.count,'maximum_discrepancies':comparison.maximum})
        with self.assertRaises(RuntimeError):independent.analyze(rows[:-1],protocol)

    def test_all12_routing_and_slice_diagnostics(self):
        sys.path.insert(0,str(a.ROOT/'quantum'));from models import Model
        g=np.random.default_rng(18726);x=g.uniform(-1,1,(21,2));y=g.integers(0,2,len(x))
        policy={'centroids':g.normal(0,.5,(5,2)).tolist(),'tau':.27,'residual_scale':[1.]*12,
          'margin_bins':{'bins':4,'unique_edges':[0,.1,.3,.6,10]}}
        data={'x':x,'y':y,'kmeans_route':np.arange(len(x))%5,'margin_bin':np.arange(len(x))%4}
        for arm in ref.ARMS:
            theta,master=ref.initial(arm,{'paired_circuit_core_initialization':11,'mlp_initialization':27});theta+=g.normal(0,.1,len(theta))
            model=Model(arm,1,{'paired_circuit_core_initialization':11,'mlp_initialization':27},policy);model.parameters[:]=theta
            xx=np.c_[x,x] if arm=='MLP4' else x;p,z=model.predict_with_logits(xx);bd,q,ez=author_eval.bank_diagnostics(model,xx,y)
            comp=replay.Comparisons();comp.tree(bd,replay.bank_diagnostics(arm,y,q,ez));comp.array(q,replay.weights(arm,theta,xx,policy),'q',2e-12)
            comp.tree(author_eval.diagnostic_slices(data,p,z,policy),replay.slices(data,p,z,policy))

    def test_full15000_historical_gate_and_milestone_replay(self):
        root=TESTROOT/'history';root.mkdir();g=np.random.default_rng(87);x=g.uniform(-1,1,(7,2));y=np.arange(7)%2
        policy={'centroids':g.normal(0,.4,(5,2)).tolist(),'tau':.4,'residual_scale':[1.]*12};expert=125
        orders=np.tile(np.arange(4800)%7,(200,1)).astype(np.uint32);gradients=np.zeros((15000,137));gradients[:,expert:]=g.normal(0,.01,(15000,12));parameters=np.zeros((200,137))
        coeff=np.zeros(12);m=np.zeros(12);v=np.zeros(12)
        for step in range(15000):
            if step>=750:
                # Construct producer-format archived coefficients. The implementation
                # under qualification separately replays them using reference Adam.
                gg=gradients[step,expert:];m=.9*m+.1*gg;v=.999*v+.001*gg**2;local=step-749
                coeff-=.001*(m/(1-.9**local))/(np.sqrt(v/(1-.999**local))+1e-8)
            if (step+1)%75==0:parameters[step//75,expert:]=coeff
        for name,array in (('record_orders',orders),('minibatch_gradients',gradients),('round_parameters',parameters),('training_record_exposure',np.bincount(orders.ravel(),minlength=7))):np.save(root/(name+'.npy'),array)
        class Model:pass
        model=Model();model.routing='L';model.banks=5;model.expert_size=expert;model.centres=np.asarray(policy['centroids']);model.tau=policy['tau']
        expected=author_eval.actual_training_exposure(model,{'x':x,'y':y},root);actual=replay.training_exposure('T_L',np.zeros(137),{'x':x,'y':y},policy,root)
        np.testing.assert_allclose(expected['class_bank_weighted_visits'],actual['class_bank_weighted_visits'],atol=1e-6,rtol=0)
        for key in ('total_visits','replayed_gate_updates','scope'):self.assertEqual(expected[key],actual[key])
        lines=[{'round':r+1,'optimizer_updates':75*(r+1),'elapsed_seconds':float(r),'validation':{'macro_f1':.8+(r%50)*.004}} for r in range(200)]
        (root/'rounds.jsonl').write_text('\n'.join(json.dumps(l) for l in lines))
        self.assertEqual(author_eval.milestones(root),replay.milestones(root))

    def gate_fixture(self):
        root,release_path,release=author_tests.ReleaseTests().fixture()
        folder=root/'evaluation';folder.mkdir();payload=folder/'dummy.json';payload.write_text('{}')
        commit={'schema':'qpath-v09-author-evaluation-commit-1','status':'PASS','scored_endpoints':636,
          'release':a.binding(release_path),'evaluator_sources':release['evaluator_sources'],
          'files':{'dummy.json':{k:a.binding(payload)[k] for k in ('sha256','bytes')}}}
        cp=folder/'EVALUATION_COMMIT.json';cp.write_text(json.dumps(commit))
        independent_folder=root/'analysis/independent_audit';independent_folder.mkdir()
        sources={}
        for name in replay.SOURCE_NAMES:
            p=independent_folder/name;p.write_text('inert independent gate fixture source');sources[name]=a.binding(p)
        contract=independent_folder/'INDEPENDENT_ANALYSIS_CONTRACT.json';contract.write_text(json.dumps({'source_bindings':sources}))
        authority={'schema':'qpath-v09-independent-analysis-release-1','review_status':'approved_by_root','stage':'B','action':'independent_prediction_statistics',
          'evaluation_release':a.binding(release_path),'author_evaluation_commit':a.binding(cp),'independent_contract':a.binding(contract)}
        path=root/'governance/independent_analysis_release.json';path.write_text(json.dumps(authority));return root,path,authority

    def test_full636_release_and_author_commit_gate(self):
        root,path,authority=self.gate_fixture();verified=replay.verify_gate(root,path);self.assertEqual(len(verified['jobs']),636)
        Path(authority['author_evaluation_commit']['path']).parent.joinpath('uncommitted.txt').write_text('tamper')
        with self.assertRaisesRegex(RuntimeError,'inventory'):replay.verify_gate(root,path)

    def test_gate_rejects_missing_audit_or_changed_checkpoint(self):
        root,path,authority=self.gate_fixture();release=a.read(authority['evaluation_release']['path'])
        target=Path(release['endpoints'][0]['selected_checkpoint']['path']);target.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'Binding changed'):replay.verify_gate(root,path)
        unauthorized=TESTROOT/'unapproved.json';unauthorized.write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'root analysis'):replay.verify_gate(root,unauthorized)

if __name__=='__main__':unittest.main(verbosity=2)
