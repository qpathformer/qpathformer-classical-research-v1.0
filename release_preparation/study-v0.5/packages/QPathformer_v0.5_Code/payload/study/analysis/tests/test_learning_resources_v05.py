"""Synthetic-only milestone, accounting, full-stage integrity and relocation tests."""
import builtins
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import numpy as np

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('learning_resources_fixture_subject',HERE.parent/'learning_resources_v05.py')
s=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(s)
ORIGINAL=Path(r'C:\QPATH_SYNTHETIC_ORIGINAL_NO_READ')
COUNTS={'q2_kmeans':40,'qscalar_kmeans':50,'qmulti_kmeans':70,'qfrozen_kmeans':30,
        'mlp4relu_kmeans':85,'mlp8relu_kmeans':165,'mlp4tanh_kmeans':85,'mlp8tanh_kmeans':165,
        'trig_kmeans':125,'trig_global':25,'mlp_global':129}


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,allow_nan=False)+'\n',encoding='utf-8')


def metric(round_number):
    return {'bce':.6-round_number*.001,'macro_f1':.98 if round_number>=5 else .9,
            'accuracy':.98,'brier':.05,'ece10':.02,'clipped':2,'n':1600,'confusion':[[790,10],[10,790]],'reliability10':[]}


def endpoint(root,stage,pop,seed,method,source):
    folder=root/'quantum'/f'stage_{stage}'/pop/f'seed_{seed}'/method;folder.mkdir(parents=True)
    frozen=method=='qfrozen_kmeans';legacy=method=='q2_kmeans';pc=COUNTS[method];banks=1 if method.endswith('_global') else 5
    ext={'minimum_raw_probability':.01,'maximum_raw_probability':.99,
         'minimum_native_logit':None if legacy else -4.,'maximum_native_logit':None if legacy else 4.}
    native=lambda i:{'native_bce':metric(i)['bce']+(.01 if not legacy else 0),'has_native_logits':not legacy,
                     **ext,'clipped_wrong_prediction_count':1}
    ledger=[]
    for i in range(1,201):
        ledger.append({'round':i,'optimizer_updates':75*i,'validation':metric(i),'validation_native':native(i),
            'elapsed_seconds':float(i),'mean_batch_gradient_norm':.1,'maximum_batch_gradient_norm':.2,
            'mean_batch_gradient_group_norms':{'core':0. if frozen else .1,'head':.1},
            'maximum_batch_gradient_group_norms':{'core':0. if frozen else .2,'head':.2},
            'training_loss':.5,'training_common_clipped_bce':.49,'training_forward_extrema':ext,
            'training_clipped_probabilities':3,'training_clipped_wrong_probabilities':1,
            'legacy_outside_clip_zero_derivative_visits':3 if legacy else 0})
    (folder/'ledger.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in ledger),encoding='utf-8')
    np.savez(folder/'round_gradient_means.npz',gradients=np.ones((200,pc))*.001)
    np.savez(folder/'selected_checkpoint.npz',parameters=np.zeros(pc))
    cache={'enabled':frozen,'seconds':2. if frozen else 0.,'bytes':256000 if frozen else 0,'work':{}}
    if frozen:
        cache['records']={}
        for split,n in (('train',4800),('validation',1600)):
            name=f'frozen_{split}_moments.npy';np.save(folder/name,np.zeros((n,5)))
            cache['records'][split]={'file':name,'bytes':n*5*8,'file_bytes':(folder/name).stat().st_size,
                                     'file_sha256':s.sha(folder/name)}
            cache['work'][split]={'core_statevector_examples':n,'moment_values_computed':5*n,'model_record_visits':0}
    work={'training':{'core_statevector_examples':0 if frozen else 16320000,'model_record_visits':960000},
          'validation':{'core_statevector_examples':0 if frozen else 320000,'model_record_visits':320000},
          'fixed_feature_preparation':cache['work']}
    prep={'generation_seconds_charged':.1,'joint_router_fit_seconds_charged':.2,'train_validation_cache_seconds_charged':.3}
    result={'status':'completed','completed_rounds':200,'optimizer_global_updates':15000,'selected_round':200,
       'test_accessed':False,'selected_validation':metric(200),'selected_training':metric(200),
       'selected_validation_native':native(200),'selected_training_native_bce':.38,
       'selected_training_forward_extrema':ext,'training_objective':'synthetic native objective',
       'has_native_logits':not legacy,'selected_training_gradient_norm':.2,
       'selected_training_gradient_group_norms':{'core':0. if frozen else .1,'head':.1},
       'parameter_count':pc,'fixed_core_parameter_count':40 if frozen else 0,'stored_model_parameter_count':pc+(40 if frozen else 0),
       'bank_count':banks,'parameters_per_bank':pc//banks,'train_bank_counts':[4800//banks]*banks,
       'bank_training_record_visits':[960000//banks]*banks,'validation_route_counts':{'kmeans':[320]*5,'hash':[320]*5},
       'training_clipped_probabilities':600,'training_clipped_wrong_probabilities':200,
       'legacy_outside_clip_zero_derivative_visits':600 if legacy else 0,'frozen_cache':cache,'preparation':prep,'work':work,
       'training_seconds':210.,'charged_training_seconds':210.+cache['seconds']+.6,'endpoint_total_seconds':215.+cache['seconds'],
       'inference':{'work_four_uncached_forwards':{'core_statevector_examples':4096},
           'work_fifth_cached_comparison':{'core_statevector_examples':1024},'mean_seconds_per_record':.003/1024,
           'total_repeat_seconds':[.003]*3,'route_repeat_seconds':[.001]*3}}
    put(folder/'result.json',result);put(folder/'config.json',{'test_accessed':False,'source_hashes':source})
    files={p.name:{'sha256':s.sha(p),'bytes':p.stat().st_size} for p in folder.iterdir() if p.is_file()}
    commit={'status':'completed','test_accessed':False,'source_hashes':source,'population':pop,'seed':seed,'method':method,'files':files}
    put(folder/'endpoint_commit.json',commit)
    a={'population':pop,'seed':seed,'method':method,'path':str(ORIGINAL/folder.relative_to(root)),
       'rounds':200,'optimizer_updates':15000,'files':files,'endpoint_commit_sha256':s.sha(folder/'endpoint_commit.json')}
    i={'population':pop,'seed':seed,'method':method,'rounds_verified':200,'validation_predictions_replayed':320000,
       'endpoint_commit_sha256':a['endpoint_commit_sha256']}
    return a,i


def make_stage(root,stage='A'):
    q=root/'quantum';g=root/'governance';review=root/'analysis/classical_review'
    for folder in (q,g,review):folder.mkdir(parents=True)
    for path in (q/'models.py',q/'audit_stage.py',review/'audit_endpoints_v05.py',review/'reference_v05.py'):
        path.write_text('# Synthetic source identity; never executed.\n')
    source={'models.py':s.sha(q/'models.py')}
    protocol={'study_id':s.STUDY_ID,'methods':list(s.METHODS),'training_seeds':list(s.SEEDS['B']),
              'milestones':{'threshold':.97,'cadence_updates':75,'confirmation_checks':3}}
    put(g/'ANALYSIS_PROTOCOL.json',protocol);put(g/'STUDY_PLAN.json',{'study_id':s.STUDY_ID,'working_root':str(ORIGINAL)})
    put(q/'data/DATA_SEAL.json',{'datasets':{p:{'synthetic_only':True} for p in s.POPULATIONS[stage]}})
    seal=s.sha(q/'data/DATA_SEAL.json');ph=s.sha(g/'ANALYSIS_PROTOCOL.json')
    freeze={'review_status':'approved_by_root','source_hashes':source,'methods':list(s.METHODS),
        'populations':list(s.POPULATIONS[stage]),'training_seeds':list(s.SEEDS[stage]),'data_seal_sha256':seal}
    put(q/f'STAGE_{stage}_FREEZE.json',freeze)
    ar=[];ir=[]
    for pop in s.POPULATIONS[stage]:
        for seed in s.SEEDS[stage]:
            for method in s.METHODS:
                a,i=endpoint(root,stage,pop,seed,method,source);ar.append(a);ir.append(i)
    author={'status':'PASS','stage':stage,'engineering':False,'endpoint_count':len(ar),'endpoints':ar,
        'source_hashes':source,'data_seal_sha256':seal,'stage_freeze_sha256':s.sha(q/f'STAGE_{stage}_FREEZE.json'),
        'analysis_protocol_sha256':ph,'test_accessed':False,
        'audit_source_hashes':{str(ORIGINAL/'quantum/audit_stage.py'):s.sha(q/'audit_stage.py')}}
    author_path=q/('STAGE_A_ENDPOINT_LOCK.json' if stage=='A' else 'CONFIRMATION_ENDPOINT_LOCK.json');put(author_path,author)
    audit={'status':'PASS','stage':stage,'engineering':False,'endpoint_count':len(ir),'endpoints':ir,
        'endpoint_lock_sha256':s.sha(author_path),'data_seal_sha256':seal,'analysis_protocol_sha256':ph,
        'validation_rounds_replayed':len(ir)*200,'validation_predictions_replayed':len(ir)*320000,
        'auditor_sha256':s.sha(review/'audit_endpoints_v05.py'),'model_test_outcomes_accessed':False,
        'independent_source_sha256':{name:s.sha(review/name) for name in ('audit_endpoints_v05.py','reference_v05.py')}}
    audit_path=review/f'STAGE_{stage}_INDEPENDENT_AUDIT.json';put(audit_path,audit)
    status={'status':'completed','stage':stage,'expected_endpoints':len(ar),'committed_endpoints':len(ar),
            'exits':[{'seed':seed,'exit_code':0} for seed in s.SEEDS[stage]],'observed_wall_seconds':450.}
    put(q/f'stage_{stage}/stage_status.json',status)
    return author_path,audit_path


class Milestones(unittest.TestCase):
    def test_first_crossing_and_third_check_distinct(self):
        r=s.milestones([.97,.96,.97,.98,.97,.95],np.arange(6)+1.)
        self.assertEqual((r['first_update'],r['confirmed_sequence_start_update'],r['confirmed_update']),(75,225,375))
        self.assertEqual(r['confirmed_elapsed_seconds'],5.)
    def test_exact_threshold_and_horizon(self):
        self.assertEqual(s.milestones([.97]*200)['confirmed_update'],225)
        r=s.milestones([.9]*197+[.97]*3);self.assertEqual(r['confirmed_update'],15000)
        self.assertEqual(r['confirmed_sequence_start_update'],14850)
        self.assertIsNone(s.milestones([.9]*198+[.97]*2)['confirmed_update'])
    def test_nonreachers_are_not_imputed_success(self):
        rows=[{'milestones':s.milestones([.97]*200)},{'milestones':s.milestones([.1]*200)},
              {'milestones':s.milestones([.1]*199+[.97])}]
        r=s.reaching_summary(rows,'confirmed');self.assertEqual((r['reached'],r['not_reached']),(1,2))
        self.assertEqual(r['conditional_update_summary']['median'],225)
        self.assertIsNone(s.reaching_summary(rows[1:],'confirmed')['conditional_update_summary'])
    def test_invalid_clocks_scores_and_work(self):
        for values,times in (([],None),([np.nan],None),([1.1],None),([.8,.9],[2,1]),([.8],[-1])):
            with self.assertRaises(RuntimeError):s.milestones(values,times)
        for counter in (-1,.5,True):
            with self.assertRaises(RuntimeError):s.add_counters({}, {'training':{'count':counter}})
    def test_nested_cache_work_is_not_multiplied_by_moments(self):
        part={'fixed_feature_preparation':{'train':{'core_statevector_examples':4800,'moment_values_computed':24000}}}
        result={};s.add_counters(result,part);s.add_counters(result,part)
        self.assertEqual(result['fixed_feature_preparation']['train'],{'core_statevector_examples':9600,'moment_values_computed':48000})


class StageGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=HERE/'synthetic_learning_work';base.mkdir(exist_ok=True)
        cls.root=Path(tempfile.mkdtemp(prefix='SYNTHETIC_ONLY_',dir=base))
        (cls.root/'SYNTHETIC_ONLY.txt').write_text('Artificial metadata/validation evidence; no real models or data.\n')
        cls.author,cls.audit=make_stage(cls.root)
    def setUp(self):
        self.patches=[mock.patch.object(s,'ROOT',self.root),mock.patch.object(s,'Q',self.root/'quantum')]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
    def test_full_relocated_stage_and_output_commit(self):
        real_open=builtins.open;real_path_open=Path.open
        def forbid(path):
            if str(path).casefold().startswith(str(ORIGINAL).casefold()):raise AssertionError('Original-tree read attempted')
        def guarded_open(path,*args,**kwargs):forbid(path);return real_open(path,*args,**kwargs)
        def guarded_path_open(path,*args,**kwargs):forbid(path);return real_path_open(path,*args,**kwargs)
        output=self.root/'analysis/result'
        with mock.patch('builtins.open',guarded_open),mock.patch.object(Path,'open',guarded_path_open):
            s.run('A',self.author,self.audit,output)
        result=s.read(output/'summary.json');commit=s.read(output/'ANALYSIS_COMMIT.json')
        self.assertEqual(result['endpoint_count'],66);self.assertEqual(len(commit['files']),6)
        self.assertEqual(result['sum_actual_endpoint_frozen_cache_creation_seconds'],12.)
        self.assertEqual(result['stage_execution_observed_wall_seconds'],450.)
        for pop in s.POPULATIONS['A']:
            frozen=result['populations'][pop]['qfrozen_kmeans']
            self.assertEqual(frozen['parameter_counts']['fixed_core_parameter_count'],[40])
            self.assertEqual(frozen['parameter_counts']['trainable_parameter_count'],[30])
            self.assertEqual(frozen['timing']['charged_training_loop_seconds']['mean'],212.6)
            self.assertEqual(frozen['sum_recorded_work_by_phase']['fixed_feature_preparation']['train']['core_statevector_examples'],14400)
            self.assertEqual(frozen['confirmed97']['conditional_update_summary']['median'],525.)
        for name,row in commit['files'].items():
            self.assertEqual(s.sha(output/name),row['sha256']);self.assertEqual((output/name).stat().st_size,row['bytes'])
        with self.assertRaises(RuntimeError):s.run('A',self.author,self.audit,output)
    def test_modified_payload_rejected_before_output(self):
        row=s.read(self.author)['endpoints'][0];folder=s.endpoint_folder('A',row,ORIGINAL)
        path=folder/'result.json';raw=path.read_bytes()
        try:
            path.write_bytes(raw+b' ')
            with self.assertRaisesRegex(RuntimeError,'payload changed'):s.input_gate('A',self.author,self.audit)
        finally:path.write_bytes(raw)
    def test_missing_round_audit_and_incomplete_worker_rejected(self):
        audit=s.read(self.audit);raw=self.audit.read_bytes()
        try:
            audit['validation_rounds_replayed']-=1;put(self.audit,audit)
            with self.assertRaisesRegex(RuntimeError,'Every validation round'):s.input_gate('A',self.author,self.audit)
        finally:self.audit.write_bytes(raw)
        status=self.root/'quantum/stage_A/stage_status.json';raw=status.read_bytes();value=s.read(status)
        try:
            value['status']='running';put(status,value)
            with self.assertRaisesRegex(RuntimeError,'workers not complete'):s.input_gate('A',self.author,self.audit)
        finally:status.write_bytes(raw)
    def test_outside_original_and_endpoint_identity_rejected(self):
        with self.assertRaises(RuntimeError):s.mapped_historical_path(r'C:\outside\payload.npz',ORIGINAL)
        with self.assertRaises(RuntimeError):s.mapped_historical_path('../payload.npz',ORIGINAL)
        row=s.read(self.author)['endpoints'][0];row['method']='mlp_global'
        with self.assertRaises(RuntimeError):s.endpoint_folder('A',row,ORIGINAL)
    def test_cache_charge_and_nested_work_mutations_rejected(self):
        row=next(r for r in s.read(self.author)['endpoints'] if r['method']=='qfrozen_kmeans')
        folder=s.endpoint_folder('A',row,ORIGINAL);path=folder/'result.json';raw=path.read_bytes();value=s.read(path)
        try:
            value['charged_training_seconds']+=2;put(path,value)
            with self.assertRaisesRegex(RuntimeError,'Charged time arithmetic'):s.endpoint_summary('A',row,ORIGINAL)
            value=json.loads(raw);value['work']['fixed_feature_preparation']['train']['core_statevector_examples']+=1;put(path,value)
            with self.assertRaisesRegex(RuntimeError,'Cache work differs'):s.endpoint_summary('A',row,ORIGINAL)
        finally:path.write_bytes(raw)


class ConfirmationSchema(unittest.TestCase):
    def test_full_synthetic165_stage_b_count_and_commit(self):
        base=HERE/'synthetic_learning_work';base.mkdir(exist_ok=True)
        root=Path(tempfile.mkdtemp(prefix='SYNTHETIC_B_ONLY_',dir=base))
        (root/'SYNTHETIC_ONLY.txt').write_text('Artificial confirmation-shaped evidence; no real test records.\n')
        author,audit=make_stage(root,'B')
        output=root/'analysis/result'
        with mock.patch.object(s,'ROOT',root),mock.patch.object(s,'Q',root/'quantum'):
            s.run('B',author,audit,output)
        result=s.read(output/'summary.json');commit=s.read(output/'ANALYSIS_COMMIT.json')
        self.assertEqual(result['endpoint_count'],165)
        self.assertEqual(set(result['populations']),set(s.POPULATIONS['B']))
        self.assertEqual(len(commit['files']),8)
        self.assertEqual(result['sum_actual_endpoint_frozen_cache_creation_seconds'],30.)
        self.assertEqual(result['populations']['confirmation_ellipse']['qfrozen_kmeans']['seeds'],[1001,1002,1003,1004,1005])


if __name__=='__main__':unittest.main()
