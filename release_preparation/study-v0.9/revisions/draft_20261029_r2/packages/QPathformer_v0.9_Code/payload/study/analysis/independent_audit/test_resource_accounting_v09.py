"""Synthetic retained-metadata fixtures only; never official model outcomes."""
import json,sqlite3,sys,tempfile,unittest,uuid
from pathlib import Path
import audit_endpoints_v09 as a
import resource_accounting_v09 as r
import test_analysis_v09 as analysis_tests
sys.path.insert(0,str(a.ROOT/'analysis/author'))
import evaluate_v09 as author

SESSION=a.HERE/'test_runs'/('resources_'+uuid.uuid4().hex);SESSION.mkdir(parents=True)
def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return a.binding(path)

class ResourceTests(unittest.TestCase):
    def fixture(self):
        root=Path(tempfile.mkdtemp(prefix='fixture_',dir=SESSION));(root/'execution/state').mkdir(parents=True)
        db=sqlite3.connect(root/'execution/state/ledger.sqlite3')
        db.executescript('CREATE TABLE jobs(job_id TEXT,phase TEXT);CREATE TABLE attempts(attempt_id TEXT,job_id TEXT,metadata_dir TEXT,endpoint TEXT,status TEXT,identity_json TEXT,started_utc TEXT,finished_utc TEXT,commit_sha TEXT);CREATE TABLE journal(attempt_id TEXT,job_id TEXT,event TEXT,details_json TEXT);')
        jobs={};counter=0
        for stage in r.STAGES:
            for variant in range(2):
                counter+=1;job=f'{stage}/test{variant}';attempt=f'a{counter}';rounds=20 if stage=='engineering' else 200
                recipe={'run_id':job,'stage':stage,'rounds':rounds,'updates':75*rounds,'arm':'G121'};jobs[job]=recipe
                meta=root/'metadata'/attempt;endpoint=root/'endpoints'/attempt;identity={'pid':7000+counter,'creation_token':'creation'+attempt}
                resource={'pid':identity['pid'],'process_cpu_seconds':1.5,'seconds_since_durable_ownership':2.,'memory_source':'Win32_GetProcessMemoryInfo',
                  'peak_working_set_bytes':12000,'working_set_bytes_at_sample':10000,'private_usage_bytes_at_sample':9000,'scope':'Whole fit child through sample'}
                save(meta/'REQUEST.json',{'attempt_id':attempt,'job':recipe,'metadata_dir':str(meta)})
                save(meta/'PROCESS_RESOURCES.json',resource)
                save(meta/'TERMINAL.json',{'attempt_id':attempt,'job_id':job,'status':'succeeded','details':{'process_identity':identity,'process_resources':resource}})
                result={k:.25 for k in r.TIMES};result.update(training_seconds=1.,endpoint_total_seconds=1.5,training_process_cpu_seconds=.5,invocation_process_cpu_seconds_through_result=1.,
                  status='completed',job_id=job,stage=stage,arm='G121',completed_rounds=rounds,optimizer_global_updates=rounds*75,test_accessed=False,
                  work={'training':{'expert_evaluations':rounds*4800}},expert_parameter_count=121,extra_parameter_count=0,full_training_record_visits=rounds*4800)
                rb=save(endpoint/'result.json',result);checkpoint=endpoint/'selected_checkpoint.npz';checkpoint.write_bytes(b'inert metadata fixture')
                commit={'status':'completed','job_id':job,'stage':stage,'arm':'G121','completed_rounds':rounds,'optimizer_global_updates':rounds*75,'test_accessed':False,
                  'files':{'result.json':{k:rb[k] for k in ('sha256','bytes')},'selected_checkpoint.npz':{k:a.binding(checkpoint)[k] for k in ('sha256','bytes')}}}
                cb=save(endpoint/'endpoint_commit.json',commit)
                db.execute('INSERT INTO jobs VALUES (?,?)',(job,stage))
                db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?)',(attempt,job,str(meta),str(endpoint),'succeeded',json.dumps(identity),'2026-10-22T01:00:00Z','2026-10-22T01:00:02Z',cb['sha256']))
                db.execute('INSERT INTO journal VALUES (?,?,?,?)',(attempt,job,'scientific_process_owned',json.dumps({'process_identity':identity})))
        # Earlier failed attempt for an existing job is retained, with unknown CPU.
        attempt='failed_prior';job='B/test0';meta=root/'metadata'/attempt
        save(meta/'REQUEST.json',{'attempt_id':attempt,'job':jobs[job],'metadata_dir':str(meta)})
        save(meta/'TERMINAL.json',{'attempt_id':attempt,'job_id':job,'status':'failed','details':{}})
        db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?)',(attempt,job,str(meta),str(root/'failed'),'failed',None,'2026-10-22T00:59:58Z','2026-10-22T01:00:00Z',None))
        db.commit();db.close();return root,jobs

    def test_full_inventory_failed_unknown_and_parallel_wall(self):
        root,jobs=self.fixture();snap=r.snapshot(root);consumed={};actual=r.inventory(root,snap,consumed)
        a.tree_close(author.cost_inventory(root),actual,'resource oracle',tol=1e-10)
        costs={row['attempt_id']:r.committed_costs(root,row,jobs[row['job_id']],consumed) for row in snap['attempts'] if row['status']=='succeeded'}
        summaries=r.elapsed_summary(actual['attempts'],costs);e=next(s for s in summaries if s['stage']=='engineering');b=next(s for s in summaries if s['stage']=='B')
        self.assertEqual(e['worker_envelope_wall_seconds'],2.);self.assertEqual(e['sum_attempt_elapsed_seconds'],4.);self.assertEqual(e['measured_worker_cpu_seconds'],3.)
        self.assertEqual(b['unknown_resource_attempt_ids'],['failed_prior']);self.assertEqual(b['failed_or_cancelled_attempts'],1)
        self.assertEqual(b['worker_envelope_wall_seconds'],4.);self.assertEqual(b['sum_attempt_elapsed_seconds'],6.)

    def test_pid_reuse_and_terminal_tampering_rejected(self):
        root,_=self.fixture();snap=r.snapshot(root);row=snap['attempts'][0];owner=snap['ownership'][row['attempt_id']]
        owner['details']['process_identity']['creation_token']='reused'
        with self.assertRaisesRegex(RuntimeError,'creation ownership'):r.inventory(root,snap,{})
        snap=r.snapshot(root);path=Path(row['metadata_dir'])/'TERMINAL.json';terminal=a.read(path);terminal['details']['process_resources']['pid']+=1;save(path,terminal)
        with self.assertRaisesRegex(RuntimeError,'PID/terminal'):r.inventory(root,snap,{})

    def test_missing_sample_contradiction_and_negative_counter(self):
        root,_=self.fixture();snap=r.snapshot(root);row=snap['attempts'][0];path=Path(row['metadata_dir'])/'PROCESS_RESOURCES.json';path.rename(path.with_suffix('.retained'))
        with self.assertRaisesRegex(RuntimeError,'contradicts terminal'):r.inventory(root,snap,{})
        path.with_suffix('.retained').rename(path);resource=a.read(path);resource['process_cpu_seconds']=-1;save(path,resource)
        terminal_path=path.parent/'TERMINAL.json';terminal=a.read(terminal_path);terminal['details']['process_resources']=resource;save(terminal_path,terminal)
        with self.assertRaisesRegex(RuntimeError,'Invalid resource time'):r.inventory(root,snap,{})

    def test_result_binding_and_duplicate_ownership_rejected(self):
        root,jobs=self.fixture();snap=r.snapshot(root);row=snap['attempts'][0];path=Path(row['endpoint'])/'result.json';result=a.read(path);result['training_seconds']=999;save(path,result)
        with self.assertRaisesRegex(RuntimeError,'Committed result changed'):r.committed_costs(root,row,jobs[row['job_id']],{})
        with sqlite3.connect(root/'execution/state/ledger.sqlite3') as db:db.execute('INSERT INTO journal SELECT * FROM journal LIMIT 1')
        with self.assertRaisesRegex(RuntimeError,'Duplicate worker'):r.snapshot(root)

    def test_root_gate_requires_scoring_and_bound_resource_contract(self):
        root,analysis_path,unused=analysis_tests.AnalysisTests().gate_fixture();source=root/'analysis/independent_audit/resource_accounting_v09.py';source.write_text('inert resource fixture')
        contract_path=root/'analysis/independent_audit/INDEPENDENT_RESOURCE_CONTRACT.json'
        contract={'source_bindings':{'resource_accounting_v09.py':a.binding(source)},'analysis_contract':a.read(analysis_path)['independent_contract']};save(contract_path,contract)
        path=root/'governance/resource_release.json';auth={'schema':'qpath-v09-independent-resource-release-1','review_status':'approved_by_root','stage':'B',
          'action':'independent_resource_accounting','resource_contract':a.binding(contract_path),'independent_analysis_authorization':a.binding(analysis_path)};save(path,auth)
        self.assertEqual(len(r.verify_release(root,path)[1]['jobs']),636)
        auth['action']='unapproved';save(path,auth)
        with self.assertRaisesRegex(RuntimeError,'Root resource release'):r.verify_release(root,path)

if __name__=='__main__':unittest.main(verbosity=2)
