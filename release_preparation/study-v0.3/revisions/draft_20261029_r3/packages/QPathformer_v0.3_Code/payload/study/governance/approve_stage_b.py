"""Record an explicit root decision to run every registered confirmation arm.

Run only after root has inspected both completed development audits. This does
not launch training, select methods, change budgets, or release test outcomes.
"""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'quantum'))
import qstudy as s
RECOVERY_SHA='049f4a627fda5fa08c739cc53375aa104e28d223bb78d525841d0f01d7931e0e'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--lock',type=Path,required=True)
    p.add_argument('--independent-audit',type=Path,required=True)
    a=p.parse_args()
    lock_path=a.lock.resolve();audit_path=a.independent_audit.resolve()
    lock=s.read_json(lock_path);audit=s.read_json(audit_path)
    for value in (lock,audit):
        if value.get('status')!='PASS' or value.get('stage')!='A' or value.get('endpoint_count')!=39:
            raise RuntimeError('Both complete Stage A audits must pass')
        if value.get('numerical_recovery_protocol_sha256')!=RECOVERY_SHA:
            raise RuntimeError('Both audits must use the documented pre-B numerical recovery')
    if audit.get('endpoint_lock_sha256')!=s.digest(lock_path):raise RuntimeError('Independent audit does not bind author lock')
    stage=s.read_json(ROOT/'quantum/stage_A/stage_status.json')
    if stage['status']!='completed' or any(v['exit_code'] for v in stage['exits']):raise RuntimeError('Stage A processes not closed successfully')
    freeze=s.read_json(ROOT/'quantum/STAGE_A_FREEZE.json')
    if freeze['source_hashes']!=s.source_hashes():raise RuntimeError('Frozen source changed')
    for name,digest in freeze['protocol_hashes'].items():
        if s.digest(ROOT/'governance'/name)!=digest:raise RuntimeError('Frozen protocol changed')
    if freeze['data_seal_sha256']!=s.digest(ROOT/'quantum/data/DATA_SEAL.json'):raise RuntimeError('Data seal changed')
    expected={(seed,method) for seed in s.SEEDS['A'] for method in s.METHODS}
    if {(v['seed'],v['method']) for v in lock['endpoints']}!=expected:raise RuntimeError('Incomplete development identities')
    recovery_path=ROOT/'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json'
    if s.digest(recovery_path)!=RECOVERY_SHA:raise RuntimeError('Recovery protocol changed')
    registration_path=ROOT/'quantum/EVALUATION_REGISTRATION.json'
    ready_path=ROOT/'analysis/independent_replay/ANALYSIS_READY.json'
    registration=s.read_json(registration_path);ready=s.read_json(ready_path)
    if registration.get('numerical_recovery_protocol_sha256')!=RECOVERY_SHA:
        raise RuntimeError('Revised evaluator registration required before B')
    if ready.get('status')!='READY_FOR_ROOT_RELEASE' or ready.get('numerical_recovery_protocol_sha256')!=RECOVERY_SHA:
        raise RuntimeError('Revised independent replay READY required before B')
    if ready['evaluation_registration_sha256']!=s.digest(registration_path):raise RuntimeError('Evaluator/replay registry differs')
    for name,digest in registration['source_hashes'].items():
        if s.digest(ROOT/'quantum'/name)!=digest:raise RuntimeError('Registered evaluator source changed')
    for name,digest in registration['external_source_hashes'].items():
        if s.digest(ROOT/name)!=digest:raise RuntimeError('Registered external audit source changed')
    for name,digest in ready['source_hashes'].items():
        if s.digest(ready_path.parent/name)!=digest:raise RuntimeError('Registered replay source changed')
    for name,digest in ready['evidence_hashes'].items():
        if s.digest(ROOT/name)!=digest:raise RuntimeError('Replay peer-review evidence changed')
    value={'approval':'approved_by_root','stage':'B','created_utc':s.now(),
      'source_hashes':s.source_hashes(),
      'evidence':{str(path.relative_to(ROOT)).replace('\\','/'):s.digest(path) for path in (lock_path,audit_path,recovery_path,registration_path,ready_path)},
      'numerical_recovery_protocol_sha256':RECOVERY_SHA,
      'decision':'All thirteen registered arms proceed to fresh confirmation, regardless of development ranking. No selection, tuning or source/budget change.',
      'approved_work':'65 full endpoints: seeds601to605,200rounds15000updates perarm. No test access before all endpoints independently verified and root release.',
      'scope':'Local CPU simulation and conventional MLP controls only; no hardware, cloud, text training, publication or external messages.'}
    target=ROOT/'governance/ROOT_STAGE_B_REVIEW.json'
    with target.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    print(target,s.digest(target))

if __name__=='__main__':main()
