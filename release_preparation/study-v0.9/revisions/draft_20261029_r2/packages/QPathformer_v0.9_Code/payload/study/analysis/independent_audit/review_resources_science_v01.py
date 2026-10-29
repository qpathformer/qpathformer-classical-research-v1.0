"""Bounded reviewer metadata fixtures, without official ledger/outcome access."""
from datetime import datetime,timezone
import copy
import json
from pathlib import Path
from unittest.mock import patch
import audit_endpoints_v09 as a
import resource_accounting_v09 as candidate
import test_resource_accounting_v09 as fixture_source

root=a.ROOT
cp=a.HERE/'INDEPENDENT_RESOURCE_CONTRACT.json'
assert a.sha(cp)=='5ad9a52ee34525aa793cdd444d4e7043397d27c281f35d65e06831ea0510bb99'
contract=a.read(cp)
for b in contract['source_bindings'].values():a.check_binding(b)
qualification=a.read(a.check_binding(contract['qualification']))
assert qualification['status']=='PASS' and qualification['tests_run']==5 and qualification['errors']==qualification['failures']==0
a.check_binding(qualification['test_log'])
a.check_binding(contract['analysis_contract'])
prior=a.read(root/'governance/INDEPENDENT_ANALYSIS_SOURCE_REVIEW_v01.json')
assert prior['contract']==contract['analysis_contract']

fixture,jobs=fixture_source.ResourceTests().fixture()
snap=candidate.snapshot(fixture);consumed={}
with patch.object(a.np,'load',side_effect=AssertionError('Metadata checker opened model arrays')):
    inv=candidate.inventory(fixture,snap,consumed)
    costs={row['attempt_id']:candidate.committed_costs(fixture,row,jobs[row['job_id']],consumed) for row in snap['attempts'] if row['status']=='succeeded'}
    summary=candidate.elapsed_summary(inv['attempts'],costs)
by_stage={item['stage']:item for item in summary}
assert len(inv['attempts'])==7 and len(costs)==6
assert by_stage['engineering']['worker_envelope_wall_seconds']==2
assert by_stage['engineering']['sum_attempt_elapsed_seconds']==4
assert by_stage['engineering']['measured_worker_cpu_seconds']==3
assert by_stage['engineering']['successful_training_cpu_seconds_sum']==1
assert by_stage['B']['worker_envelope_wall_seconds']==4
assert by_stage['B']['sum_attempt_elapsed_seconds']==6
assert by_stage['B']['unknown_resource_attempt_ids']==['failed_prior']
assert by_stage['B']['measured_worker_cpu_seconds']==3
assert 'unknown' in by_stage['B']['cpu_scope']

# A self-consistent native record must still be rejected when its PID was reused.
changed=copy.deepcopy(snap)
successful=next(row for row in changed['attempts'] if row['status']=='succeeded')
changed['ownership'][successful['attempt_id']]['details']['process_identity']['creation_token']='different_creation_same_pid'
try:
    candidate.inventory(fixture,changed,{})
    raise AssertionError('Reused PID accepted')
except RuntimeError as error:assert 'creation ownership' in str(error)

# Rebind a synthetic result and its commit to test semantic nested-time checks,
# rather than relying only on a hash mismatch.
row=copy.deepcopy(next(row for row in snap['attempts'] if row['status']=='succeeded'))
ep=Path(row['endpoint']);rp=ep/'result.json';commitp=ep/'endpoint_commit.json'
result=a.read(rp);result['training_seconds']=result['endpoint_total_seconds']+1
rp.write_text(json.dumps(result));commit=a.read(commitp)
commit['files']['result.json']={k:a.binding(rp)[k] for k in ('sha256','bytes')}
commitp.write_text(json.dumps(commit));row['commit_sha']=a.sha(commitp)
try:
    candidate.committed_costs(fixture,row,jobs[row['job_id']],{})
    raise AssertionError('Training time exceeding endpoint accepted')
except RuntimeError as error:assert 'Nested timing inconsistency' in str(error)

receipt={
 'schema':'qpath-v09-independent-resource-source-review-1',
 'status':'PASS_SOURCE_AND_BOUNDED_METADATA_REVIEW',
 'reviewer':'/root/v09_science','utc':datetime.now(timezone.utc).isoformat(),
 'contract':a.binding(cp),'qualification':contract['qualification'],
 'source_bindings':contract['source_bindings'],'reviewer_source':a.binding(__file__),
 'independent_analysis_review':a.binding(root/'governance/INDEPENDENT_ANALYSIS_SOURCE_REVIEW_v01.json'),
 'constructed_fixture_root':str(fixture),
 'reviewer_checks':[
  'Seven constructed attempts/six successes across three stages; parallel worker envelope2s, summed elapsed4s, measured CPU3s and training CPU1s remain separate.',
  'Failed attempt without sample remains unknown while contributing its time interval; no missing CPU is imputed as zero.',
  'Same PID with changed creation token is rejected against durable ownership.',
  'Hash-consistent but semantically impossible training time larger than endpoint total is rejected.',
  'All metadata/cost operations completed with np.load disabled; no checkpoint or prediction arrays opened.'
 ],
 'source_review':[
  'Separate root resource release binds this resource contract and the already reviewed independent analysis authorization; full636 confirmation and committed official scoring barriers are reused before resource reconciliation.',
  'Read-only SQLite snapshot joins only engineering/A/B attempts and checks unique native ownership events. Request, terminal, worker PID/creation identity, native sample counters and terminal sample equality are validated.',
  'All756 unique successful study jobs must match the registered matrix; result and selected-checkpoint hashes/budgets are checked. B636 author cost fields must agree with committed result values.',
  'Independent sums use math.fsum. Negative/nonfinite counters, impossible nested timing, duplicate ownership, mismatched IDs and modified files fail closed. Ledger and bound files are rechecked before receipt.',
  'Output is exclusive-create, failures are retained, and the CLI uses ETEL auxiliary audit lease without training or an observer.'
 ],
 'limits':[
  'Source and constructed-fixture qualification only: no official resource reconciliation or outcomes accepted by this receipt.',
  'Native peak and CPU stop at the retained sample, not necessarily final process exit; no claim of training-only memory or isolated scheduler overhead.',
  'Worker envelope includes gaps/recovery but excludes preparation and later audits. Summed child elapsed is not stage wall time; nested counters must not be added.',
  'Qualification, audits, conversion, reproduction and timing require separate phase receipts. The checker reconciles recorded work/cost fields; scientific semantic work checks are also covered by preceding endpoint audits.',
  'Fixture metadata builder is reused only to create inert records; reviewer expectations and adversarial mutations are independently specified.'
 ],
 'blocking_findings':[],'official_metadata_or_model_outcomes_accessed':False,'observer_or_training_launched':False
}
out=root/'governance/INDEPENDENT_RESOURCE_SOURCE_REVIEW_v01.json'
a.write_new(out,receipt)
print(json.dumps({'status':receipt['status'],'receipt':a.binding(out)}))
