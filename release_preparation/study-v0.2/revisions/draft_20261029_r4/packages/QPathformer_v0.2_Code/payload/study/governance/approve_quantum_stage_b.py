"""Root approval after independent complete-development and selection checks.

Run manually by root after reviewing the concrete Stage B proposal. This never
reads confirmation data or test outcomes and refuses to replace a prior freeze.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import statistics

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT/'quantum'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8'))

out = Q/'STAGE_B_FREEZE.json'
if out.exists(): raise FileExistsError(out)
a = read(Q/'STAGE_A_FREEZE.json')
proposal = read(Q/'STAGE_B_PROPOSAL.json')
selection = read(Q/'STAGE_A_SELECTION.json')
audit = read(Q/'STAGE_A_ENDPOINT_AUDIT.json')
review = read(Q/'EVALUATOR_INDEPENDENT_REVIEW.json')
registration = read(Q/'EVALUATION_REGISTRATION.json')
assert sha(Q/'STAGE_A_FREEZE.json') == '06446dbe10db21a5fa317f0beab731122bedf2ecb438943459e9895879266b0f'
assert sha(Q/'EVALUATOR_INDEPENDENT_REVIEW.json') == '8ea50e5ea49ade3f47b356b4ece42bce360563677ba8ecf9387ed301654d348d'
assert sha(Q/'EVALUATION_REGISTRATION.json') == '04dfc5c53af098a6a4a34e6dcee590452ec1efa48c6981d8684165d6a711832f'
assert review['status'] == 'PASS' and not review['test_outcomes_accessed']
assert proposal['source_hashes'] == a['source_hashes']
for field in ['batch_size','optimizer','initialization','pairing','checkpoint_selection','metric','exposure',
              'capacity_controls','diagnostics','failures','parallelism','data']:
    assert proposal[field] == a[field], field
for hashes in [a['source_hashes'], registration['source_hashes'], review['reviewed_source_sha256'],
               proposal['additional_reporting_sources_sha256']]:
    for name, expected in hashes.items():
        assert sha(Q/name) == expected, name
assert sha(Q/'data/DATA_SEAL.json') == a['data_seal_sha256'] == proposal['data_seal_sha256']
assert sha(ROOT/'governance/ANALYSIS_PROTOCOL.json') == a['root_analysis_protocol_sha256'] == proposal['root_analysis_protocol_sha256']
assert audit['status']=='pass' and audit['count']==27 and not audit['test_file_read']
assert audit['audit_source_sha256']==sha(Q/'audit_stage_a.py')
assert audit['independent_evaluator_sha256']==sha(Q/'evaluate_confirmation.py')
assert audit['stage_a_freeze_sha256']==sha(Q/'STAGE_A_FREEZE.json')
assert selection['stage_a_freeze_sha256']==sha(Q/'STAGE_A_FREEZE.json') and not selection['test_accessed']
identities = {(seed, method) for seed in [301,302,303] for method in a['methods']}
assert len(audit['endpoints'])==27 and {(r['seed'],r['method']) for r in audit['endpoints']}==identities
assert len(selection['all_27_results'])==27 and {(r['seed'],r['method']) for r in selection['all_27_results']}==identities
assert read(Q/'stage_A/stage_status.json')['status']=='completed'
rows=[]
for seed, method in sorted(identities):
    folder=Q/'stage_A'/f'seed_{seed}'/method
    result=read(folder/'result.json')
    status=read(folder/'status.json')
    locked=next(r for r in audit['endpoints'] if (r['seed'],r['method'])==(seed,method))
    chosen=next(r for r in selection['all_27_results'] if (r['seed'],r['method'])==(seed,method))
    assert locked['status']=='pass' and locked['probability_max_error']<=1e-10 and locked['metric_max_error']<=1e-10
    assert status['status']==result['status']=='completed' and not result['engineering'] and not result['test_accessed']
    assert result['completed_rounds']==200 and result['optimizer_global_updates']==15000
    assert result['stage_freeze_sha256']==sha(Q/'STAGE_A_FREEZE.json')
    assert result['data_seal_sha256']==a['data_seal_sha256']
    assert sha(folder/'result.json')==locked['result_sha256']==chosen['result_sha256']
    assert sha(folder/'selected_checkpoint.npz')==locked['checkpoint_sha256']==result['selected_checkpoint_sha256']
    assert sha(folder/'ledger.jsonl')==locked['ledger_sha256']
    ledger=[json.loads(line) for line in (folder/'ledger.jsonl').read_text().splitlines()]
    assert [r['round'] for r in ledger]==list(range(1,201))
    best=min(ledger,key=lambda r:(r['validation']['bce'],r['round']))
    assert best['round']==result['selected_round']==locked['selected_round']
    for metric in ['bce','macro_f1','accuracy']:
        assert abs(result['selected_validation'][metric]-locked['independent_validation'][metric])<1e-10
        assert abs(result['selected_validation'][metric]-best['validation'][metric])<1e-10
    assert chosen['validation_bce']==result['selected_validation']['bce']
    assert chosen['training_circuit_examples']==result['work']['training_circuit_examples']
    assert chosen['parameter_count']==result['parameter_count']
    rows.append(chosen)

summaries={m:{'bce':statistics.mean(r['validation_bce'] for r in rows if r['method']==m),
              'work':statistics.mean(r['training_circuit_examples'] for r in rows if r['method']==m),
              'parameters':next(r['parameter_count'] for r in rows if r['method']==m)} for m in a['methods']}
candidates=['min_depth2','untied_assigned','untied_balanced']
minimum=min(summaries[m]['bce'] for m in candidates)
tied=[m for m in candidates if summaries[m]['bce']<=minimum+.002]
winner=min(tied,key=lambda m:(summaries[m]['work'],summaries[m]['parameters'],m))
assert winner==selection['selected_candidate']==proposal['selected_candidate']
promising=summaries['scheduled']['bce']-summaries[winner]['bce']>=.01
assert promising==selection['development_promising_flag']==proposal['development_promising_flag']
methods=a['stage_b']['if_min_depth2' if winner=='min_depth2' else 'if_untied']
assert methods==selection['proposed_stage_b_methods']==proposal['methods']
assert proposal['training_seeds']==[401,402,403,404,405]
assert proposal['registered_stage_b_runs']==5*len(methods)
assert proposal['rounds']==200 and proposal['global_updates_per_run']==15000
for field,path in [('stage_a_selection_sha256','STAGE_A_SELECTION.json'),
                   ('stage_a_endpoint_audit_sha256','STAGE_A_ENDPOINT_AUDIT.json'),
                   ('evaluation_registration_sha256','EVALUATION_REGISTRATION.json'),
                   ('evaluation_source_sha256','evaluate_confirmation.py'),
                   ('readiness_protocol_sha256','READINESS_PROTOCOL.json')]:
    assert proposal[field]==sha(Q/path), field

freeze=dict(proposal)
freeze.update(review_status='approved_by_root', approved_utc=datetime.now(timezone.utc).isoformat(),
              proposal_sha256=sha(Q/'STAGE_B_PROPOSAL.json'), root_approval_script_sha256=sha(Path(__file__)),
              independent_review='Root verified all27 completed development endpoints, independent validation replay audit, ledger and checkpoint hashes, reconstructed candidate/tie/promising rules, predeclared conditional confirmation matrix and reviewed evaluator/readiness identities. No confirmation outcome used.',
              next_action='Execute every registered Stage B run. After complete validation endpoint audit and local readiness, obtain a separate root-issued one-time test release.')
out.write_text(json.dumps(freeze,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'APPROVED','selected_candidate':winner,'confirmation_runs':5*len(methods),
                  'freeze_sha256':sha(out),'development_mean_bce':summaries,'test_outcomes_read':False},indent=2))
