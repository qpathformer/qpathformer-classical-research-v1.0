"""Independent retained-cost reconciliation; no observer or model predictions."""
import argparse,hashlib,json,math,sqlite3,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import audit_endpoints_v09 as a
import replay_analysis_v09 as analysis

HERE=a.HERE;ROOT=a.ROOT
STAGES=('engineering','A','B')
TIMES=('training_seconds','training_process_cpu_seconds','endpoint_total_seconds','invocation_process_cpu_seconds_through_result',
       'diagnostic_forward_wall_seconds','diagnostic_forward_cpu_seconds','sampler_wall_seconds','sampler_cpu_seconds')
EXTRA=('work','expert_parameter_count','extra_parameter_count','full_training_record_visits')
SOURCE_NAMES=('resource_accounting_v09.py',)
MISSING='No final resource sample retained; unobserved CPU is not treated as zero.'
SCOPE='Native lifetime peak and whole-process CPU through the retained resource sample, normally after endpoint verification. The final exit interval is not sampled; this is not training-only memory or an exact final-exit peak.'
LIMITATION='Sum of child elapsed times is compute occupancy, not parallel study wall time. Whole-child CPU and native lifetime peak extend through the post-verification sample, not final exit or training alone. Exact worker creation identity and terminal resource equality are checked. Reproduction, conversion, audits and timing have separate phase receipts. Missing failed-attempt resource samples remain unknown.'

def snapshot(root):
    with sqlite3.connect((root/'execution/state/ledger.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=[dict(r) for r in db.execute('SELECT a.*,j.phase FROM attempts a JOIN jobs j USING(job_id) ORDER BY a.job_id,a.started_utc') if r['phase'] in STAGES]
        owners={}
        for row in db.execute("SELECT attempt_id,job_id,details_json FROM journal WHERE event='scientific_process_owned'"):
            a.need(row['attempt_id'] not in owners,'Duplicate worker ownership event')
            owners[row['attempt_id']]={'job_id':row['job_id'],'details':json.loads(row['details_json'])}
    return {'attempts':rows,'ownership':owners}

def metadata(root,row,owner,consumed):
    folder=a.inside(root,row['metadata_dir']);request_path=folder/'REQUEST.json';terminal_path=folder/'TERMINAL.json'
    request=a.read(request_path);terminal=a.read(terminal_path)
    for p in (request_path,terminal_path):consumed[str(p)]=a.binding(p)
    a.need(request['attempt_id']==row['attempt_id'] and request['job']['run_id']==row['job_id'] and
      Path(request['metadata_dir']).resolve()==folder,'Request attempt identity mismatch')
    a.need(terminal['attempt_id']==row['attempt_id'] and terminal['job_id']==row['job_id'] and terminal['status']==row['status'],'Terminal attempt mismatch')
    a.need(row['finished_utc'] is not None,'Unfinished attempt cannot be final accounting')
    path=folder/'PROCESS_RESOURCES.json'
    if not path.exists():
        a.need(not terminal['details'].get('process_resources'),'Missing resource file contradicts terminal')
        return None,{'resource_limitation':MISSING}
    resources=a.read(path);consumed[str(path)]=a.binding(path);identity=json.loads(row['identity_json'])
    a.need(identity and identity.get('creation_token') and owner and owner['job_id']==row['job_id'] and
      owner['details']['process_identity']==identity,'Worker PID/creation ownership mismatch')
    a.need(resources['pid']==identity['pid'] and terminal['details'].get('process_resources')==resources,'Resource PID/terminal mismatch')
    if 'process_identity' in terminal['details']:a.need(terminal['details']['process_identity']==identity,'Terminal creation identity mismatch')
    a.need(resources['memory_source']=='Win32_GetProcessMemoryInfo','Unexpected native memory source')
    for key in ('peak_working_set_bytes','working_set_bytes_at_sample','private_usage_bytes_at_sample'):
        a.need(type(resources[key]) is int and resources[key]>=0,'Invalid native memory counter')
    a.need(resources['peak_working_set_bytes']>=resources['working_set_bytes_at_sample'],'Peak smaller than current working set')
    for key in ('process_cpu_seconds','seconds_since_durable_ownership'):
        a.need(math.isfinite(resources[key]) and resources[key]>=0,'Invalid resource time')
    return resources,{'resource_binding':a.binding(path),'terminal_binding':a.binding(terminal_path),
      'request_binding':a.binding(request_path),'exact_worker_identity':identity,'resource_limitation':SCOPE}

def inventory(root,snap,consumed):
    output=[]
    for row in snap['attempts']:
        resource,evidence=metadata(root,row,snap['ownership'].get(row['attempt_id']),consumed)
        output.append({k:row[k] for k in ('job_id','attempt_id','status','started_utc','finished_utc')}|
          {'stage':row['phase'],'resources':resource}|evidence)
    groups=[]
    for stage in STAGES:
        for success in (True,False):
            subset=[r for r in output if r['stage']==stage and (r['status']=='succeeded')==success]
            observed=[r['resources'] for r in subset if r['resources'] is not None]
            groups.append({'stage':stage,'success':success,'attempts':len(subset),'measured_attempts':len(observed),
              'measured_process_cpu_seconds':math.fsum(r['process_cpu_seconds'] for r in observed),
              'measured_sum_child_elapsed_seconds':math.fsum(r['seconds_since_durable_ownership'] for r in observed),
              'max_observed_peak_working_set_bytes':max((r['peak_working_set_bytes'] for r in observed),default=None)})
    return {'attempts':output,'groups':groups,'limitation':LIMITATION}

def committed_costs(root,row,job,consumed):
    folder=a.inside(root,row['endpoint']);cp=folder/'endpoint_commit.json';commit=a.read(cp)
    a.need(a.sha(cp)==row['commit_sha'],'Ledger endpoint commit changed');consumed[str(cp)]=a.binding(cp)
    rp=folder/'result.json';result=a.read(rp);consumed[str(rp)]=a.binding(rp)
    expected=commit['files']['result.json'];a.need(a.sha(rp)==expected['sha256'] and rp.stat().st_size==expected['bytes'],'Committed result changed')
    a.need(commit['status']=='completed' and result['status']=='completed' and commit['job_id']==result['job_id']==row['job_id']==job['run_id'],'Cost endpoint identity mismatch')
    for key,jkey in (('stage','stage'),('completed_rounds','rounds'),('optimizer_global_updates','updates'),('arm','arm')):
        a.need(commit[key]==result[key]==job[jkey],'Cost endpoint recipe mismatch')
    a.need(result['test_accessed'] is False and commit['test_accessed'] is False,'Training result reports test access')
    for key in TIMES:a.need(math.isfinite(result[key]) and result[key]>=0,'Nonfinite/negative cost '+key)
    for first,second in (('training_seconds','endpoint_total_seconds'),('training_process_cpu_seconds','invocation_process_cpu_seconds_through_result'),
      ('diagnostic_forward_wall_seconds','training_seconds'),('sampler_wall_seconds','training_seconds'),
      ('diagnostic_forward_cpu_seconds','training_process_cpu_seconds'),('sampler_cpu_seconds','training_process_cpu_seconds')):
        a.need(result[first]<=result[second]+1e-9,'Nested timing inconsistency '+first)
    a.need(result['full_training_record_visits']==job['rounds']*4800,'Record visit cost differs from budget')
    def nonnegative(value):
        if isinstance(value,dict):
            for v in value.values():nonnegative(v)
        else:a.need(isinstance(value,(int,float)) and math.isfinite(value) and value>=0,'Invalid work count')
    nonnegative(result['work'])
    selected=folder/'selected_checkpoint.npz';selected_binding=commit['files']['selected_checkpoint.npz']
    a.need(selected.stat().st_size==selected_binding['bytes'] and a.sha(selected)==selected_binding['sha256'],'Cost checkpoint binding changed')
    consumed[str(selected)]=a.binding(selected)
    return {key:result[key] for key in TIMES+EXTRA}|{'checkpoint_bytes':selected_binding['bytes'],
      'endpoint_payload_bytes':sum(f['bytes'] for f in commit['files'].values())}

def elapsed_summary(records,costs):
    summaries=[]
    for stage in STAGES:
        chosen=[r for r in records if r['stage']==stage];success=[r for r in chosen if r['status']=='succeeded']
        times=[(datetime.fromisoformat(r['started_utc'].replace('Z','+00:00')),datetime.fromisoformat(r['finished_utc'].replace('Z','+00:00'))) for r in chosen if r['started_utc']]
        for start,end in times:a.need(end>=start,'Negative attempt elapsed interval')
        measured=[r for r in chosen if r['resources'] is not None];known=[costs[r['attempt_id']] for r in success]
        summaries.append({'stage':stage,'attempts':len(chosen),'succeeded_attempts':len(success),'failed_or_cancelled_attempts':len(chosen)-len(success),
          'unknown_resource_attempt_ids':[r['attempt_id'] for r in chosen if r['resources'] is None],
          'first_worker_started_utc':min((x[0] for x in times),default=None).isoformat() if times else None,
          'last_worker_finished_utc':max((x[1] for x in times),default=None).isoformat() if times else None,
          'worker_envelope_wall_seconds':(max(x[1] for x in times)-min(x[0] for x in times)).total_seconds() if times else None,
          'sum_attempt_elapsed_seconds':math.fsum((end-start).total_seconds() for start,end in times),
          'measured_worker_cpu_seconds':math.fsum(r['resources']['process_cpu_seconds'] for r in measured),
          'successful_training_wall_seconds_sum':math.fsum(r['training_seconds'] for r in known),
          'successful_training_cpu_seconds_sum':math.fsum(r['training_process_cpu_seconds'] for r in known),
          'successful_endpoint_payload_bytes_sum':sum(r['endpoint_payload_bytes'] for r in known),
          'wall_scope':'First registered attempt start to last finish, including pauses/recovery gaps. Excludes preparation, initial supervisor startup and post-training audits; not a total project wall time.',
          'cpu_scope':'Sum retained whole-worker CPU through sample, including measured failed attempts. Missing resource samples remain unknown; never substitute zero.',
          'overlap_note':'Training, sampler and diagnostic times are nested. Do not add nested counters or label sums of worker elapsed times as stage wall time.'})
    return summaries

def verify_release(root,path):
    path=a.inside(root,path);auth=a.read(path)
    a.need(auth.get('schema')=='qpath-v09-independent-resource-release-1' and auth.get('review_status')=='approved_by_root' and
      auth.get('stage')=='B' and auth.get('action')=='independent_resource_accounting','Root resource release required')
    contract_path=a.inside(root,a.check_binding(auth['resource_contract']));contract=a.read(contract_path)
    a.need(contract_path==root/'analysis/independent_audit/INDEPENDENT_RESOURCE_CONTRACT.json','Wrong resource contract')
    a.need(set(contract['source_bindings'])==set(SOURCE_NAMES),'Resource source inventory mismatch')
    for name,b in contract['source_bindings'].items():a.need(a.inside(root,a.check_binding(b))==root/'analysis/independent_audit'/name,'Resource source location')
    analysis_path=a.inside(root,a.check_binding(auth['independent_analysis_authorization']));verified=analysis.verify_gate(root,analysis_path)
    a.need(verified['contract_binding']==contract['analysis_contract'],'Analysis implementation changed')
    return auth,verified,contract

def run(root,authorization,output):
    root=Path(root).resolve();output=a.inside(root,output);a.need(root==ROOT and not output.exists(),'Official root/new output required')
    auth,verified,contract=verify_release(root,authorization);output.mkdir(parents=True);started=time.perf_counter();cpu=time.process_time()
    try:
        snap=snapshot(root);consumed={};actual=inventory(root,snap,consumed);evaluation=verified['evaluation_root'];saved=a.read(evaluation/'RESOURCE_ACCOUNTING.json')
        a.tree_close(saved,actual,'Independent resource inventory',tol=1e-8)
        jobs={j['run_id']:j for j in verified['protocols']['run_matrix']['runs']};successful=[r for r in snap['attempts'] if r['status']=='succeeded']
        a.need(len(successful)==756 and len({r['job_id'] for r in successful})==756 and {r['job_id'] for r in successful}==set(jobs),'All756 committed unique successful jobs required')
        costs={};rows={r['job_id']:r for r in a.read(evaluation/'ENDPOINT_RESULTS.json')}
        for row in successful:
            costs[row['attempt_id']]=committed_costs(root,row,jobs[row['job_id']],consumed)
            if row['phase']=='B':a.tree_close(rows[row['job_id']]['costs'],costs[row['attempt_id']],'Independent endpoint costs',tol=1e-8)
        stages=elapsed_summary(actual['attempts'],costs)
        for b in consumed.values():a.check_binding(b)
        a.need(snapshot(root)==snap,'Ledger accounting evidence changed during audit');verify_release(root,authorization)
        report={'schema':'qpath-v09-independent-resource-accounting-1','status':'PASS','utc':datetime.now(timezone.utc).isoformat(),
          'authorization':a.binding(authorization),'resource_contract':auth['resource_contract'],'official_evaluation_commit':verified['evaluation_commit'],
          'verified_successful_endpoints':len(successful),'verified_attempts':len(snap['attempts']),'inventory':actual,'stage_summaries':stages,
          'successful_endpoint_costs':costs,'metadata_bindings':list(consumed.values()),
          'ledger_selected_rows_sha256':hashlib.sha256(a.canonical(snap)).hexdigest(),
          'worker_cpu_minus_training_cpu_not_called_ETEL_overhead':'The difference also includes Python imports, preprocessing, verification and unobserved measurement boundaries. No isolated scheduler-only cost is inferred.',
          'separate_costs':'Qualification, data preparation, audits, conversion, reproduction and inference timing require their separate receipts; not folded into training totals.',
          'monitor_started':False,'training_performed':False,'test_prediction_arrays_loaded':False,
          'wall_seconds':time.perf_counter()-started,'process_cpu_seconds':time.process_time()-cpu}
        a.write_new(output/'INDEPENDENT_RESOURCE_ACCOUNTING.json',report);return a.binding(output/'INDEPENDENT_RESOURCE_ACCOUNTING.json')
    except BaseException as error:
        a.write_new(output/'RESOURCE_RECONCILIATION_FAILURE.json',{'error':repr(error),'traceback':traceback.format_exc(),'automatic_retry':False});raise

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--authorization',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    sys.path.insert(0,str(ROOT/'execution'));import durable
    with durable.auxiliary_lease(ROOT,'audit'):receipt=run(ROOT,args.authorization,args.output)
    print(json.dumps(receipt))

if __name__=='__main__':main()
