"""Root-only explicit stage approval after inspecting independent evidence.

This utility cannot approve itself or launch training. The approving root supplies
the immutable audit and the engineering pilot; an existing freeze is never replaced.
"""
from pathlib import Path
import argparse, hashlib, json, sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'quantum'))
import qstudy as s

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=['A','B'], required=True)
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--root-review', type=Path, required=True)
    a = p.parse_args()
    pilot = ROOT/'quantum/engineering_pilot_v02/pilot_summary.json'
    evidence = [pilot, a.audit.resolve(), a.root_review.resolve()]
    if a.stage == 'B': evidence.append(ROOT/'quantum/STAGE_A_FREEZE.json')
    for path in evidence:
        if not path.is_file(): raise FileNotFoundError(path)
    if s.read_json(pilot)['status'] != 'PASS': raise RuntimeError('Pilot not passed')
    if s.read_json(pilot)['source_hashes'] != s.source_hashes(): raise RuntimeError('Pilot source changed')
    review = s.read_json(a.root_review)
    if review.get('approval') != 'approved_by_root' or review.get('stage') != a.stage:
        raise RuntimeError('Explicit matching root review required')
    if review.get('source_hashes') != s.source_hashes(): raise RuntimeError('Reviewed source changed')
    value = {
        'study_id':'QPATH-QMECH-v0.3', 'stage':a.stage,
        'review_status':'approved_by_root', 'approved_utc':datetime.now(timezone.utc).isoformat(),
        'methods':list(s.METHODS), 'training_seeds':list(s.SEEDS[a.stage]),
        'settings':s.SETTINGS, 'source_hashes':s.source_hashes(),
        'data_seal_sha256':s.digest(ROOT/'quantum/data/DATA_SEAL.json'),
        'protocol_hashes':{n:s.digest(ROOT/'governance'/n) for n in ('STUDY_PLAN.json','ANALYSIS_PROTOCOL.json')},
        'evidence':{str(path.relative_to(ROOT)).replace('\\','/'):s.digest(path) for path in evidence},
        'test_release':False,
        'scope':'All registered arms retained; no hardware/cloud; train and validation only',
    }
    path = ROOT/f'quantum/STAGE_{a.stage}_FREEZE.json'
    with path.open('x',encoding='utf-8') as f: json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    print(path, s.digest(path))

if __name__ == '__main__': main()
