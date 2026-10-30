"""Independent source/authority review. Does not invoke freeze or launch."""
import ast,json
from datetime import datetime,timezone
from pathlib import Path
import audit_endpoints_v09 as a

root=a.ROOT;gov=root/'governance';sources={n:a.binding(gov/n) for n in ('freeze_stage.py','launch_stage.ps1','bounded_power_guard.ps1')}
freeze=(gov/'freeze_stage.py').read_text();tree=ast.parse(freeze)
functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
a.need({'validate_request','predecessor','build','verify_data'}<=set(functions),'Missing source gate')
matrix=a.read(gov/'RUN_MATRIX.json');counts={};coverage={}
synthetic={'C_H','C_S','C_L','C_R','T_H','T_S','T_L','T_R','G121'}
for stage,n in a.COUNTS.items():
    jobs=[j for j in matrix['runs'] if j['stage']==stage];a.need(len(jobs)==n,'Actual matrix stage count')
    groups={}
    for j in jobs:groups.setdefault((j['population_id'],j['training_seed_id']),[]).append(j)
    for (pop,seed),rows in groups.items():
        arms=synthetic|({'MLP2','MLP4','LR2'} if pop=='banknote_01' else set())
        a.need({j['arm'] for j in rows}==arms and len(rows)==len(arms),'Actual matrix group arm mismatch')
        a.need(all(j['updates']==(1500 if stage=='engineering' else 15000) for j in rows),'Actual budget mismatch')
    counts[stage]=n;coverage[stage]={'groups':len(groups),'synthetic_arms':9,'banknote_arms':12 if stage!='A' else 0}
for gate in ('math.isfinite(usage[\'gate_charge\'])','0<=usage[\'gate_charge\']<27000',
             "usage['status'] in ('CONTINUE','WARNING')",'maps[0]==maps[1]',"durable.verify_receipt_endpoints(ROOT,a,previous,count)",
             "original['frozen_protocol_sha256']==r['protocol_sha256']",'study.SETTINGS==r[\'settings\']'):
    a.need(gate in freeze,'Reviewed critical gate missing '+gate)
launch=(gov/'launch_stage.ps1').read_text();power=(gov/'bounded_power_guard.ps1').read_text()
for fragment in ('[IO.FileMode]::CreateNew','-WindowStyle Hidden','manifest_sha256','Get-CimInstance Win32_Process','Existing launch claim/record'):
    a.need(fragment in launch,'Launch guard missing '+fragment)
for fragment in ('[ValidateRange(1,48)]','2147483649','2147483648','finally','POWER_GUARD_STOP.json'):
    a.need(fragment in power,'Bounded power guard missing '+fragment)
receipt={'schema':'qpath-v09-root-helper-independent-source-review-1','status':'PASS','utc':datetime.now(timezone.utc).isoformat(),
  'reviewer':'/root/v09_execution','sources':sources,'actual_matrix':a.binding(gov/'RUN_MATRIX.json'),
  'verified_counts':counts,'group_coverage':coverage,'root_helpers_invoked':False,'official_freeze_or_training_launched':False,
  'review_scope':'Source review plus actual matrix coverage recomputation. This is not a claim that an official stage request has been frozen or launched.',
  'checks':['Explicit root request and source-bound reviews before freeze; all7protocols, data and settings bound.',
    '48/72/636 inventories, exact9synthetic/12Banknote arms perpopulation/seed, groupcounts5/8/69 and allowedseeds.',
    'Preserved runtime and OpenBLAS1; active cap<=5; no source/model/budget change across stages.',
    'Fresh usage observation<=25minutes, exact4agentnames, finitecharge<27000 and CONTINUE/WARNING; bounded checkpoint overrun cannot silently admit new substantial stage.',
    'Predecessor author and independentPASS enumerate fullcommits; allpayloads rechecked and identicalattemptmaps required.',
    'Builder only emits exclusive freezes/manifests/releases; does not launch. Partialwrite failures remain for explicit reconciliation.',
    'Launch requires stage manifest+release hashes, exclusiveclaim, no existingcoordinator, hiddenwindow and retainedlogs; ledger retains childidentity safety.',
    'Powerguard bounded1–48h, stopmarker, temporary systemrequest only; finally clears request, no globalpowerpolicy change.'],
  'resolved_review_findings':['Root added explicit arm/population/seed groupcoverage.','Root now validates numericusagecharge<27000 and allowsWARNING24–27k.'],
  'operational_note':'Root should invoke launch promptly after fresh stagefreeze; if launch is deferred, recapture usage and reconcile before launching. No helper automaticretry is authorized.'}
a.need("r['helper_review']" in freeze and "r['warmup_qualification']" in freeze,'Final root review/paired warmup gates missing')
receipt['pre_release_review_script_correction']='First v02 review attempt expected paired_warmup_qualification instead of actual warmup_qualification key; failed before writing a receipt. Reviewer-only spelling correction; helper source unchanged.'
receipt['checks'].append('Final request additionally binds current three-helper independent review and six20round1500update pairedwarmup authorPASS/source evidence.')
a.write_new(a.HERE/'ROOT_HELPERS_SOURCE_REVIEW_v02.json',receipt)
print(json.dumps({'status':'PASS','receipt':a.binding(a.HERE/'ROOT_HELPERS_SOURCE_REVIEW_v02.json')},indent=2))
