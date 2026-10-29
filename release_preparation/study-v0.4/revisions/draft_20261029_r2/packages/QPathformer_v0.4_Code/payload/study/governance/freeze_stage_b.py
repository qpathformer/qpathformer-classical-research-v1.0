"""Root-only completion gate and approval of the predeclared full Stage B matrix.

Running this does not launch training and does not load model test outcomes.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'quantum';G=ROOT/'governance'
sys.path.insert(0,str(Q));import study
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return study.digest(p)
def need(c,m):
 if not c:raise RuntimeError(m)
def run(independent_path,evaluator_review_path):
 independent_path=(ROOT/Path(independent_path)).resolve();evaluator_review_path=(ROOT/Path(evaluator_review_path)).resolve()
 need(independent_path.resolve().is_relative_to(ROOT) and evaluator_review_path.resolve().is_relative_to(ROOT),'Reviews outside study')
 need(not (Q/'stage_B').exists() and not (Q/'STAGE_B_FREEZE.json').exists(),'StageB already approved or exists; never duplicate')
 first=read(Q/'STAGE_A_FREEZE.json');launch=read(Q/'stage_A/launch.json');status=read(Q/'stage_A/stage_status.json')
 lock_path=Q/'STAGE_A_ENDPOINT_LOCK.json';lock=read(lock_path);ind=read(independent_path);review=read(evaluator_review_path)
 need(launch['stage_freeze_sha256']==sha(Q/'STAGE_A_FREEZE.json'),'StageAfreeze changed')
 need(first['source_hashes']==study.source_hashes()==lock['source_hashes'],'Frozen training source changed')
 need(first['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json')==lock['data_seal_sha256']==ind['data_seal_sha256'],'Data changed')
 for name,h in first['protocol_hashes'].items():need(sha(G/name)==h,'Frozen protocol changed '+name)
 for key,name in [('resource_notes_sha256','RESOURCE_ACCOUNTING_NOTES.json'),('runtime_sha256','RUNTIME.json')]:need(first[key]==sha(G/name),'Frozen runtime/accounting changed')
 need(first['settings']==study.SETTINGS,'Training settings changed')
 for obj in (lock,ind):need(obj['status']=='PASS' and obj['stage']=='A' and obj['engineering'] is False and obj['endpoint_count']==54,'All54 fullA audits required')
 need(ind['endpoint_lock_sha256']==sha(lock_path),'Independent audit does not bind current authorlock')
 need(ind['validation_rounds_replayed']==10800 and ind['validation_predictions_replayed']==17280000,'All200 validationrounds required')
 need(lock['stage_freeze_sha256']==sha(Q/'STAGE_A_FREEZE.json'),'Authorlockfreeze mismatch')
 need(lock['analysis_protocol_sha256']==ind['analysis_protocol_sha256']==sha(G/'ANALYSIS_PROTOCOL.json'),'Audit protocol differs')
 need(status['status']=='completed' and status['committed_endpoints']==54 and sorted((r['seed'],r['exit_code']) for r in status['exits'])==[(s,0) for s in study.SEEDS['A']],'Aworkers notclosedcomplete')
 expected={(p,s,m) for p in study.POPULATIONS['A'] for s in study.SEEDS['A'] for m in study.METHODS}
 authorrows={(r['population'],r['seed'],r['method']):r for r in lock['endpoints']};indrows={(r['population'],r['seed'],r['method']):r for r in ind['endpoints']}
 need(len(lock['endpoints'])==len(ind['endpoints'])==54 and set(authorrows)==set(indrows)==expected,'Incomplete endpoint identities')
 for key,row in authorrows.items():
  p,s,m=key;folder=Q/'stage_A'/p/f'seed_{s}'/m;ir=indrows[key]
  need(Path(row['path']).resolve()==folder.resolve(),'Unexpected original endpoint path')
  need(sha(folder/'endpoint_commit.json')==row['endpoint_commit_sha256']==ir['endpoint_commit_sha256'],'Endpoint commit differs')
  need(row['rounds']==ir['rounds_verified']==200 and row['optimizer_updates']==15000,'Wrong fullendpoint budget')
  commit=read(folder/'endpoint_commit.json');need(commit['files']==row['files'],'Author file inventory differs')
  need({p.name for p in folder.iterdir() if p.is_file() and p.name!='endpoint_commit.json'}==set(row['files']),'Unexpected endpoint payload')
  for name,info in row['files'].items():
   need(Path(name).name==name,'Unsafe payload filename');path=folder/name
   need(path.stat().st_size==info['bytes'] and sha(path)==info['sha256'],'Changed endpoint payload')
  need(ir['selected_checkpoint_sha256']==row['files']['selected_checkpoint.npz']['sha256'],'Independent selectedcheckpoint differs')
 for name,h in lock['audit_source_hashes'].items():need(Path(name).resolve().is_relative_to(ROOT) and sha(name)==h,'Authoraudit source differs')
 for name,h in ind['independent_source_sha256'].items():need(sha(ROOT/'analysis/classical_review'/name)==h,'Independent source changed')
 peer_path=ROOT/'analysis/classical_review/STATISTICS_AND_NUMERICAL_PEER_REVIEW.json';peer=read(peer_path)
 need(peer['status']=='PASS','Statistics peer review incomplete')
 for name,h in peer['source_sha256'].items():need(sha(ROOT/name)==h,'Statistics reviewed source changed')
 need(review['status']=='PASS','Evaluator/readiness peer review incomplete')
 reg_path=Q/'EVALUATION_REGISTRATION.json';reg=read(reg_path)
 need(reg['status']=='REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS' and reg['original_working_root']==str(ROOT),'Evaluation registration scope differs')
 need(review['registration_sha256']==sha(reg_path),'Evaluator review binds a different registration')
 need(review['registered_source_sha256']==reg['source_hashes'],'Evaluator reviewed source set differs')
 for name,h in reg['source_hashes'].items():need(sha(ROOT/name)==h,'Registered evaluation source changed '+name)
 freeze={'study_id':'QPATH-ROUTING-v0.4','stage':'B','review_status':'approved_by_root','approved_utc':datetime.now(timezone.utc).isoformat(),
  'selection':'All9 predeclared arms continue; no outcome-based arm filtering, source change, optimizer change or budget change.',
  'methods':list(study.METHODS),'populations':list(study.POPULATIONS['B']),'training_seeds':list(study.SEEDS['B']),
  'settings':study.SETTINGS,'source_hashes':study.source_hashes(),'data_seal_sha256':sha(Q/'data/DATA_SEAL.json'),'expected_endpoints':135,
  'protocol_hashes':first['protocol_hashes'],'resource_notes_sha256':first['resource_notes_sha256'],'runtime_sha256':first['runtime_sha256'],
  'stage_a_freeze_sha256':sha(Q/'STAGE_A_FREEZE.json'),'stage_a_endpoint_lock_sha256':sha(lock_path),
  'stage_a_independent_audit_path':independent_path.relative_to(ROOT).as_posix(),'stage_a_independent_audit_sha256':sha(independent_path),
  'stage_a_status_sha256':sha(Q/'stage_A/stage_status.json'),'statistics_peer_review_sha256':sha(peer_path),
  'evaluation_registration_sha256':sha(reg_path),'evaluator_readiness_review_path':evaluator_review_path.relative_to(ROOT).as_posix(),'evaluator_readiness_review_sha256':sha(evaluator_review_path),
  'test_release':'Not released. All135fullB endpoints must be independently audited and root issue a separate hash-bound evaluation release.'}
 with (Q/'STAGE_B_FREEZE.json').open('x',encoding='utf-8') as f:json.dump(freeze,f,indent=2);f.write('\n')
 for p in study.POPULATIONS['B']:
  for s in study.SEEDS['B']:
   for m in study.METHODS:study.verify_freeze('B',p,s,m)
 state=read(G/'CONTINUATION_STATUS.json');state.update(updated_utc=datetime.now(timezone.utc).isoformat(),phase='StageA54 endpoints independentlyverified; StageB135 rootfrozen, notyetlaunched; teststillsealed',stage_b_freeze_sha256=sha(Q/'STAGE_B_FREEZE.json'))
 (G/'CONTINUATION_STATUS.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
 print('APPROVED135 StageB endpoints',sha(Q/'STAGE_B_FREEZE.json'))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--independent-audit',type=Path,required=True);parser.add_argument('--evaluator-review',type=Path,required=True)
 args=parser.parse_args();run(args.independent_audit,args.evaluator_review)
