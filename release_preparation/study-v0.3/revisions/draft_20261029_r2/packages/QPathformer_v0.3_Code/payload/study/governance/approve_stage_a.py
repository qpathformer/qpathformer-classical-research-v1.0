"""Explicit root approval recorded after review of the registered implementation."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'quantum'))
import qstudy as s

def main():
    target=ROOT/'governance/ROOT_STAGE_A_REVIEW.json'
    if target.exists(): raise FileExistsError(target)
    paths=[ROOT/'analysis/classical_review/model_audit_attempt02.json',
           ROOT/'analysis/classical_review/data_audit_attempt01.json',
           ROOT/'quantum/engineering_pilot_v02/pilot_summary.json']
    for p in paths:
        if s.read_json(p)['status']!='PASS':raise RuntimeError(f'Failed evidence {p}')
    if s.read_json(paths[-1])['source_hashes']!=s.source_hashes():raise RuntimeError('Pilot did not bind current sources')
    data_audit=s.read_json(paths[1])
    if data_audit['data_seal_sha256']!=s.digest(ROOT/'quantum/data/DATA_SEAL.json'):raise RuntimeError('Data seal changed')
    plan_path=ROOT/'governance/STUDY_PLAN.json'
    plan=s.read_json(plan_path)
    plan['status']='FROZEN_BEFORE_STAGE_A'
    s.write_json(plan_path,plan)
    value={
        'approval':'approved_by_root','stage':'A','created_utc':s.now(),
        'source_hashes':s.source_hashes(),
        'evidence':{str(p.relative_to(ROOT)).replace('\\','/'):s.digest(p) for p in paths},
        'review':'Root reviewed all model, circuit, trainer, launcher, data, router and test source; verified plan and analysis matrix; independent model and data audits pass; exact-final-source engineering pilot passes all13arms225updates; no official test outcomes.',
        'reviewed_final_trainer_changes':'Official 4800/1600 length guard, zero routing time for nonrouted methods, validation route occupancy metadata. These do not change model or gradient calculations reviewed independently.',
        'coverage':'15 unit checks; separate tensor-product/finite-difference review; independent full data/router reconstruction; full-population3roundengineeringpilot.',
        'engineering_attempts_preserved':['engineering_pilot_v01 precedes final guard/metadata changes; engineering_pilot_v02 binds final sources',
          'Independent model audit attempt01 stopped on outdated MLP41 oracle; attempt02 matches approved six-input model and passes',
          'Preliminary analytic extra encoding diagnostic used full angle; production audit uses registered half angle'],
        'approved_work':'39 development endpoints, all13methods x seeds501-503, 200rounds15000updates each; no test release; no candidate filtering',
        'no_hardware_or_cloud':True,
    }
    with target.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    print(target,s.digest(target))

if __name__=='__main__':main()
