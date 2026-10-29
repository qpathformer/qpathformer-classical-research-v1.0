"""Root-only development review and confirmation freeze; no test access."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / 'classical'
REVIEW = ROOT / 'analysis/classical_independent/CLASSICAL_STAGE_A_INDEPENDENT_REVIEW.json'

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4*1024*1024), b''): h.update(block)
    return h.hexdigest()

out = C / 'readiness/ROOT_STAGE_B_APPROVAL.json'
assert not out.exists() and not (C/'protocol_stage_b_frozen.json').exists(), 'Preserve existing approval/freeze'
assert not list((C/'results/stage_b').glob('seed_*/*/status.json')), 'Stage B already started'
assert sha(REVIEW)=='90517e69419f8919ac7a4fb5d5046b27c952ee2ad266dcd0f0dd62b2337020fa'
review = read(REVIEW)
assert review['status']=='PASS' and not review['test_outcomes_accessed'] and not review['test_payload_read']
assert review['audit_script_sha256']==sha(REVIEW.with_name('audit_stage_a.py'))
assert review['completed_main_endpoints']==12 and review['completed_warmups']==3 and review['incident_count']==0
protocol_path = C/'protocol_stage_a_frozen.json'
selection_path = C/'selection_frozen.json'
a, selection = read(protocol_path), read(selection_path)
assert sha(protocol_path)==review['stage_a_protocol_sha256']=='bdd5179589646e956d89e80bedc74f395a0aafa9bc50cf38ea90e1f2b534ca78'
assert sha(selection_path)==review['selection_sha256']=='b6d249f72c8fd274966177dc7a038cf2fdc81ae53854d7cef8641ccb8a589c17'
assert selection['test_accessed'] is False and selection['rule']==a['selection']
assert sha(C/'data/manifest.json')==review['data_manifest_sha256']==a['data_manifest_sha256']
assert sha(ROOT/'governance/ANALYSIS_PROTOCOL.json')=='9b409934d07e8eb7a6380a02fe93780cab3323401d595c846da1b2ce7ba1e414'
assert review['verified_frozen_code_files']==a['code_sha256']
for name, expected in a['code_sha256'].items(): assert sha(C/name)==expected, name
for name, expected in review['verified_data_files'].items(): assert sha(C/'data'/name)==expected, name
identities={(seed,method) for seed in a['seeds'] for method in a['methods']}
assert len(review['per_seed'])==len(selection['seed_rows'])==12
assert {(r['seed'],r['method']) for r in review['per_seed']}==identities
assert {(r['seed'],r['method']) for r in selection['seed_rows']}==identities
assert {tuple(r) for r in review['verified_main_identity_set']}==identities
for row in review['per_seed']+review['common_warmups']:
    folder=C/'results/stage_a'/f"seed_{row['seed']}"/row['method']
    for name,field in [('status.json','status_sha256'),('checkpoint_commit.json','commit_sha256'),('ledger.jsonl','ledger_sha256')]:
        assert sha(folder/name)==row[field], str(folder/name)
    state, commit=read(folder/'status.json'),read(folder/'checkpoint_commit.json')
    expected_horizon=1000 if row['method']=='common_warmup' else 3000
    assert state['status']=='completed' and state['phase_update']==state['latest_eligible_update']==expected_horizon
    assert state['protocol_sha256']==sha(protocol_path)
    checkpoint=C/'results/stage_a'/state['latest_eligible_checkpoint']
    assert checkpoint.resolve()==(folder/commit['checkpoint']).resolve()
    assert sha(checkpoint)==row['checkpoint_sha256']==commit['sha256']
    assert state['latest_validation']['macro_f1']==row['macro_f1']
    assert state['charged_total_seconds']==row['charged_seconds']
    if row['method']!='common_warmup':
        chosen=next(r for r in selection['seed_rows'] if r['seed']==row['seed'] and r['method']==row['method'])
        assert chosen['f1']==row['macro_f1'] and chosen['seconds']==row['charged_seconds']
        assert chosen['status_sha256']==row['status_sha256'] and chosen['checkpoint_sha256']==row['checkpoint_sha256']
means={m:{'f1':statistics.mean(r['macro_f1'] for r in review['per_seed'] if r['method']==m),
          'seconds':statistics.mean(r['charged_seconds'] for r in review['per_seed'] if r['method']==m)} for m in a['methods']}
best=max(means[m]['f1'] for m in ['frozen_content','hash18'])
near=[m for m in ['frozen_content','hash18'] if means[m]['f1']>=best-.001]
winner=min(near,key=lambda m:(means[m]['seconds'],m))
deltas=[next(r['macro_f1'] for r in review['per_seed'] if r['seed']==seed and r['method']==winner)-
        next(r['macro_f1'] for r in review['per_seed'] if r['seed']==seed and r['method']=='shared') for seed in a['seeds']]
gate=means[winner]['f1']>=max(means[m]['f1'] for m in ['shared','current_content'])-.002 and min(deltas)>=-.005
assert winner==selection['selected_candidate']==review['selected_candidate']
assert gate==selection['promising_gate']==review['promising_gate']
for method in a['methods']:
    assert abs(means[method]['f1']-selection['averages'][method]['f1'])<1e-14
    assert abs(means[method]['seconds']-selection['averages'][method]['seconds'])<1e-10

# Import only after frozen source/data identities pass. freeze() verifies the
# train/validation payloads and creates the existing registered Stage B protocol.
sys.path.insert(0,str(C))
import study
b, b_hash=study.freeze('stage_b')
expected=deepcopy(a)
expected.update(id='QPATH-DBPEDIA14-ROUTING-v0.2-stage_b', stage='stage_b', seeds=list(range(401,406)),
                methods=['shared','current_content',winner], selection_sha256=sha(selection_path),resource_cap_seconds_per_method=5400)
expected['schedules'].update(main_updates=10000,main_ramp=1000)
assert b==expected, 'Confirmation protocol differs from predeclared transition'
record={'review_status':'approved_by_root','approved_utc':datetime.now(timezone.utc).isoformat(),
        'root_approval_script_sha256':sha(Path(__file__)),'independent_review_sha256':sha(REVIEW),
        'stage_a_protocol_sha256':sha(protocol_path),'selection_sha256':sha(selection_path),
        'stage_b_protocol_sha256':b_hash,'selected_candidate':winner,'promising_gate':gate,
        'registered_confirmation_endpoints':15,'training_seeds':list(range(401,406)),
        'methods':b['methods'],'schedules':b['schedules'],'development_means':means,
        'test_outcomes_accessed':False,
        'interpretation':'Candidate passed the registered tolerance gate. This is not evidence that it improves over the original controls; final confirmation uses fresh seeds and sealed test evaluation.',
        'next_action':'Launch exactly one full Stage B training process. Independent endpoint review and a separate root release are required before test evaluation.'}
out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,indent=2))
