"""One bounded stdlib metadata closure review; no model-array or metric reads."""
import hashlib,json,sqlite3,sys,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'execution'))
import process_identity
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def binding(p):p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def require(ok,message):
    if not ok:raise RuntimeError(message)
def check(b):require(binding(b['path'])==b,'Binding changed '+b['path']);return Path(b['path'])
def main():
    start=time.perf_counter();defects=[];proofs=[];sourceproof=[]
    mp=ROOT/'governance/EXECUTION_B_MANIFEST.json';manifest=read(mp);mh=sha(mp);freeze=read(check(manifest['authorization']));matrix=read(check(manifest['matrix']))
    jobs=[j for j in matrix['runs'] if j['stage']=='B'];jobmap={j['run_id']:j for j in jobs};release_path=ROOT/'governance/EXECUTION_B_RELEASE.json';release=read(release_path)
    require(len(jobs)==len(jobmap)==636 and manifest['jobs']==jobs and freeze['run_ids']==[j['run_id'] for j in jobs],'Registered B matrix/manifest/freeze mismatch')
    require(mh=='61d930237d87518bb58a01c0d9bd45c8184508b07aff4f2954bf2ee0b38964df' and release['manifest_sha256']==mh,'Manifest release mismatch')
    require(release['review_status']=='approved_by_root' and release['scientific_authorization']==manifest['authorization'],'Root authorization mismatch')
    require(freeze['review_status']=='approved_by_root' and freeze['stage']=='B' and freeze['test_access']=='forbidden','Scientific stage not sealed')
    for item in manifest['bindings']:
        p=Path(item['path'])
        if p.suffix=='.py' and p.is_relative_to(ROOT):check(item);sourceproof.append(item)
    require(len(sourceproof)==15,'Expected7scientific+8execution source files')
    for name,digest in freeze['scientific_source_hashes'].items():require(sha(ROOT/'quantum'/name)==digest,'Frozen scientific source changed')
    for name,digest in freeze['frozen_protocol_sha256'].items():require(sha(ROOT/'governance'/name)==digest,'Frozen protocol changed')
    report_paths=list((ROOT/'execution/stage_reports').glob('B_*.json'));require(len(report_paths)==1,'One B stage report required');stage=read(report_paths[0])
    require(stage['stage']=='B' and stage['status']=='completed' and stage['manifest_sha256']==mh and stage['execution_release_sha256']==sha(release_path),'Stage report not matching completed B')
    summary=stage['etel']['summary'];require(summary['submitted']==summary['succeeded']==636 and summary['failed']==0 and summary['peak_running']<=5 and summary['peak_in_flight']<=5,'Stage counts/concurrency mismatch')
    reported={x['job_id']:x for x in stage['etel']['results']};require(len(reported)==636 and set(reported)==set(jobmap),'Stage report job identities mismatch')
    db=sqlite3.connect((ROOT/'execution/state/ledger.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    rows=[dict(x) for x in db.execute("SELECT a.*,j.current_attempt,j.phase,j.recipe_sha,j.manifest_sha FROM attempts a JOIN jobs j USING(job_id) WHERE j.phase='B' ORDER BY a.job_id")]
    journal=[dict(x) for x in db.execute("SELECT sequence,utc,job_id,attempt_id,event,details_json FROM journal WHERE event IN ('scientific_process_owned','stage_supervision_started','stage_supervision_finished')")];db.close()
    require(len(rows)==636 and len({r['job_id'] for r in rows})==636 and {r['job_id'] for r in rows}==set(jobmap),'B ledger identity/count mismatch')
    owners={}
    for event in journal:
        if event['event']=='scientific_process_owned' and event['job_id'] in jobmap:
            require(event['attempt_id'] not in owners,'Duplicate worker ownership');owners[event['attempt_id']]=json.loads(event['details_json'])
    observed=set()
    for row in rows:
        try:
            job=jobmap[row['job_id']];meta=Path(row['metadata_dir']);endpoint=Path(row['endpoint']);identity=json.loads(row['identity_json']);key=(identity['pid'],identity['creation_token'])
            require(key not in observed,'Reused exact worker identity');observed.add(key)
            require(row['status']=='succeeded' and row['current_attempt']==row['attempt_id'] and row['manifest_sha']==mh and row['finished_utc'],'B attempt not committed terminal current')
            request=read(meta/'REQUEST.json');terminal=read(meta/'TERMINAL.json');closed=read(meta/'PROCESS_CLOSED.json');cp=endpoint/'endpoint_commit.json';commit=read(cp)
            require(request['job']==job and request['attempt_id']==row['attempt_id'] and request['manifest_sha256']==mh and request['recipe_sha256']==row['recipe_sha'] and request['release_sha256']==sha(release_path),'Request/ledger recipe mismatch')
            require(commit['schema']=='qpath-v09-endpoint-1' and commit['status']=='completed' and commit['test_accessed'] is False and commit['stage']=='B','Incomplete/unsealed endpoint commit')
            for key,value in (('job_id',row['job_id']),('arm',job['arm']),('population',job['population_id']),('seed',job['training_seed_id']),('completed_rounds',200),('optimizer_global_updates',15000)):
                require(commit[key]==value,'Commit recipe mismatch '+key)
            require(commit['source_hashes']==freeze['scientific_source_hashes'] and commit['authorization_sha256']==manifest['authorization']['sha256'],'Commit source/authority changed')
            for key in ('matrix_sha256','protocol_sha256','data_seal_sha256'):require(commit[key]==freeze[key],'Commit frozen binding changed '+key)
            require(sha(cp)==row['commit_sha']==terminal['commit_sha256']==reported[row['job_id']]['output']['commit_sha256'],'Commit byte hash disagreement')
            require(terminal['status']=='succeeded' and terminal['job_id']==row['job_id'] and terminal['attempt_id']==row['attempt_id'] and terminal['details']['process_identity']==identity,'Terminal identity mismatch')
            require(owners[row['attempt_id']]['process_identity']==identity,'Ownership journal differs')
            require(closed['job_id']==row['job_id'] and closed['attempt_id']==row['attempt_id'] and closed['expected']==identity and closed['same_live_identity'] is False and closed['terminal']==binding(meta/'TERMINAL.json'),'Native closure binding mismatch')
            require(closed['observed'] is None or closed['observed']['creation_token']!=identity['creation_token'],'Closure retained original live identity')
            current=process_identity.identity(identity['pid']);require(current!=identity,'Registered native worker remains live')
            require(reported[row['job_id']]['status']=='succeeded' and reported[row['job_id']]['output']['status']=='succeeded' and reported[row['job_id']]['output']['attempt_id']==row['attempt_id'],'Stage outcome differs')
            proofs.append({'job_id':row['job_id'],'attempt_id':row['attempt_id'],'native_identity':identity,'current_observation':current,'commit':binding(cp),'request':binding(meta/'REQUEST.json'),'terminal':binding(meta/'TERMINAL.json'),'process_closed':binding(meta/'PROCESS_CLOSED.json')})
        except Exception as error:defects.append({'job_id':row['job_id'],'error':repr(error)})
    supervised=[x for x in journal if x['event'].startswith('stage_supervision_') and json.loads(x['details_json']).get('stage')=='B']
    require([x['event'] for x in supervised]==['stage_supervision_started','stage_supervision_finished'],'Unexpected B supervision chain')
    require(json.loads(supervised[-1]['details_json'])['succeeded'] is True,'Supervision did not finish successfully')
    coordinator={str(pid):process_identity.identity(pid) for pid in (4680,7560)}
    report={'schema':'qpath-v09-B-completion-closure-review-1','status':'PASS' if not defects else 'FAIL','utc':datetime.now(timezone.utc).isoformat(),'reviewer':'/root/v09_execution',
      'manifest':binding(mp),'scientific_authorization':manifest['authorization'],'execution_release':binding(release_path),'stage_report':binding(report_paths[0]),'review_source':binding(__file__),
      'registered_jobs':636,'ledger_attempts':len(rows),'successful_ledger_attempts':sum(r['status']=='succeeded' for r in rows),'failed_ledger_attempts':sum(r['status']!='succeeded' for r in rows),
      'verified_commit_hashes':len(proofs),'verified_native_worker_closures':len(proofs),'unique_native_creation_identities':len(observed),'frozen_scientific_sources_verified':7,'frozen_execution_sources_verified':8,'frozen_protocols_verified':len(freeze['frozen_protocol_sha256']),
      'source_bindings':sourceproof,'stage_summary':summary,'supervision_journal':supervised,'coordinator_pid_observations':coordinator,
      'coordinator_observation_scope':'Read-only PID observations at review time; launch/bootstrap4680 and root-identified native7560. Worker closures use exact retained creation identities.',
      'job_population_counts':dict(Counter(job['family'] for job in jobs)),'entries':proofs,'defects':defects,
      'test_model_outcomes_accessed':False,'model_arrays_loaded':False,'endpoint_payload_array_hash_replay_performed':False,'full_independent_endpoint_audit_performed':False,
      'numerical_lease_acquired':False,'training_or_other_study_work_launched':False,
      'scope':'Metadata-only closure and committed manifest-byte review. Does not independently certify gradient/model/selection correctness or release test evaluation.',
      'wall_seconds':time.perf_counter()-start}
    out=ROOT/'governance/B_COMPLETION_CLOSURE_REVIEW.json'
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False)
    print(json.dumps({'status':report['status'],'binding':binding(out),'verified_commits':len(proofs),'defects':defects,'coordinators':coordinator,'wall_seconds':report['wall_seconds']}))
if __name__=='__main__':main()
