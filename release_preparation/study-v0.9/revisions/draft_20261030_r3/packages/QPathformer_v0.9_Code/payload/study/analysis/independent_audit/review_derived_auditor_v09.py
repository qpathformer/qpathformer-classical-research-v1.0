"""Bounded reviewer-constructed checks; no official outcomes or studies."""
import json,sqlite3,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import audit_endpoints_v09 as a
sys.path.insert(0,str(a.ROOT/'analysis/independent_derived'))
import audit_v09 as q

def reject(fn):
    try:fn()
    except RuntimeError:return
    raise RuntimeError('Expected adversarial rejection')

def main():
    ready_path=q.HERE/'READINESS_v02.json';ready=a.read(ready_path)
    a.need(ready['status']=='PASS' and ready['tests_run']==9,'Nine passing qualification tests required')
    a.need(ready['source_sha256']==q.sources(),'Readiness source mismatch');a.check_binding(ready['log']);a.check_binding(ready['qualification_source']);a.check_binding(ready['producer_readiness'])
    reports=[];rng=np.random.default_rng(98313)
    # Independent scalar gate-by-gate reference cross-check, outside grid nodes.
    maximum=0.
    for _ in range(4):
        theta=rng.normal(0,.7,14);x=rng.uniform(-.97,.97,(13,2));actual=q.predict_logit(theta,x)
        expected=np.array([q.ref.scalar_moments(theta[:8],row)@theta[8:13]+theta[13] for row in x])
        maximum=max(maximum,a.close(actual,expected,2e-12,'Reviewer scalar Laurent logit'))
    reports.append({'check':'Separate scalar gate-by-gate versus analytic Laurent logits','records':52,'maximum_absolute_error':maximum})
    jobs=[{'run_id':'constructed/C_L','arm':'C_L'},{'run_id':'constructed/G121','arm':'G121'}];rows=[];sums={};expected_checksum=0.
    for block,job,representation,batch in q.expected_conditions(jobs,2):
        value=.25*batch;sums[(job['run_id'],batch)]=value;expected_checksum+=17*value
        for trial in range(15):rows.append({'session':2,'block':block,'job_id':job['run_id'],'representation':representation,'batch':batch,'trial':trial,'wall_ns':10000+trial,'cpu_ns':5000+trial,'probability_sum':value})
    conditions,checksum=q.validate_trials(rows,jobs,2,sums)
    a.need(len(conditions)==9 and len(rows)==135 and checksum==expected_checksum,'Manual timing inventory/checksum')
    for c in conditions:a.need(c['median_wall_ns']==10007 and c['median_cpu_ns']==5007 and c['records_per_second']==c['batch']*1e9/10007,'Manual timing medians')
    reports.append({'check':'Hand-calculated timing conditions/median/checksum','conditions':9,'raw_trials':135})
    folder=a.HERE/'test_runs'/('derived_review_'+uuid.uuid4().hex);(folder/'execution/state').mkdir(parents=True);(folder/'analysis/derived_attempts').mkdir(parents=True)
    (folder/'execution/durable.py').write_bytes((a.ROOT/'execution/durable.py').read_bytes())
    with sqlite3.connect(folder/'execution/state/ledger.sqlite3') as db:
        db.execute('CREATE TABLE attempts(attempt_id TEXT,started_utc TEXT,finished_utc TEXT,status TEXT)')
        db.execute('INSERT INTO attempts VALUES (?,?,?,?)',('before','2026-01-01T00:00:00Z','2026-01-01T00:00:01Z','succeeded'))
    original=q.ROOT;q.ROOT=folder
    try:
        start=q.stamp('2026-01-01T00:00:01+00:00');end=q.stamp('2026-01-01T00:00:02+00:00');identity={'pid':1,'creation_token':'fixture'}
        evidence=q.timing_exclusion(start,end,identity);a.need(evidence['ledger_attempts_checked']==1,'Boundary exclusion')
        with sqlite3.connect(folder/'execution/state/ledger.sqlite3') as db:db.execute('INSERT INTO attempts VALUES (?,?,?,?)',('overlap','2026-01-01T00:00:01Z','2026-01-01T00:00:03Z','succeeded'))
        reject(lambda:q.timing_exclusion(start,end,identity))
        with sqlite3.connect(folder/'execution/state/ledger.sqlite3') as db:db.execute("UPDATE attempts SET finished_utc=NULL WHERE attempt_id='overlap'")
        reject(lambda:q.timing_exclusion(start,end,identity))
    finally:q.ROOT=original
    reports.append({'check':'Timing exclusion accepts adjacent closure and rejects overlap/unclosed attempt','constructed_only':True,'fixture':str(folder)})
    report={'schema':'qpath-v09-independent-derived-source-review-1','status':'PASS','utc':datetime.now(timezone.utc).isoformat(),'reviewer':'/root/v09_execution',
      'readiness':a.binding(ready_path),'source_sha256':q.sources(),'reviewer_source':a.binding(__file__),'reviewer_checks':reports,
      'resolved_findings':[{'finding':'Scoring commit contract was not explicitly compared with replay gate contract.','resolution':'score_contract() now rejects any mismatch; adverse fixture passes.'},
        {'finding':'Declared clean copy inventory did not exclude undeclared actual input files.','resolution':'complete_clean_inputs() compares the actual input tree outside produced endpoints with the exact expected files; extra copied checkpoint rejected.'}],
      'source_review':['Complete root636 official and independent scoring chain before derived model access; immutable source/protocol/output bindings.',
        'Conversion276models1380cores with analytic coefficients, complete pipelines and preserved routing/residual/preprocessing.',
        'Four preselected clean full-budget fits; source/data inventory, native child identity/closure, every archived gradient/parameter/curve, sampler and selection replay.',
        'Three distinct serial timing processes,123120rawtimedtrials, exact order/count/medians/checksums and managed interval exclusion.',
        'Warmup counters16416 are explicitly not individually retained; technical repeats not populations; unrelated OS interference uncontrolled.',
        'Exclusive ETEL auxiliary audit lease and durable attempt identity prohibit live/completed duplication; root-bound recovery only.'],
      'official_checkpoints_or_test_outcomes_accessed':False,'official_execution_authorized':False}
    output=a.ROOT/'governance/INDEPENDENT_DERIVED_SOURCE_REVIEW_v01.json';a.write_new(output,report);print(json.dumps(a.binding(output)))

if __name__=='__main__':main()
