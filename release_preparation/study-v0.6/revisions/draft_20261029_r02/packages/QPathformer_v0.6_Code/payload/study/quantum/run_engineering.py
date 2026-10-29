"""One complete, explicitly root-approved engineering pilot; no sealed data."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import argparse
from pathlib import Path
import time
import traceback
import study as s


def run(approval_path,output):
    approval_path=Path(approval_path);output=Path(output)
    s.require(not output.exists(),'Preserve prior engineering outputs')
    a=s.read_json(approval_path);source=s.source_hashes();seal=s.digest(s.ROOT/'data/DATA_SEAL.json')
    plan_path=s.ROOT.parent/'governance/STUDY_PLAN.json';plan=s.read_json(plan_path)['engineering']
    s.require(a.get('status')=='approved_by_root','Root engineering approval required')
    s.require(a.get('source_hashes')==source and a.get('data_seal_sha256')==seal,'Approval source/data mismatch')
    s.require(a.get('protocol_sha256',{}).get('STUDY_PLAN.json')==s.digest(plan_path),'Engineering plan changed')
    s.require(a.get('engineering',{}).get('seed')==plan['seed']==10901 and a['engineering'].get('rounds')==plan['rounds']==3,'Engineering budget/seed mismatch')
    s.require(a['engineering'].get('populations')==list(s.ENGINEERING) and a.get('methods')==list(s.METHODS),'Engineering arm/population mismatch')
    s.require(a['engineering'].get('runs')==plan['runs']==24 and a['engineering'].get('updates')==plan['updates']==225,'Engineering total budget mismatch')
    output.mkdir(parents=True,exist_ok=False);start=time.perf_counter();failures=[];rows=[]
    s.write_json(output/'launch.json',{'approval_path':str(approval_path.resolve()),'approval_sha256':s.digest(approval_path),
        'source_hashes':source,'runner_sha256':s.digest(__file__),'data_seal_sha256':seal,'started_utc':s.now(),'seed':10901,'rounds':3,
        'threads':{key:os.getenv(key) for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},
        'network_scope':'Local only; no network code or socket guard'},True)
    for population in s.ENGINEERING:
        for method in s.METHODS:
            folder=output/population/'seed_10901'/method
            try:
                print('START '+population+'/'+method,flush=True)
                r=s.train(method,10901,'A',population,folder,rounds=3,engineering=True)
                rows.append({k:r[k] for k in ('population','method','training_seconds','endpoint_total_seconds','charged_training_seconds')})
                print('DONE '+population+'/'+method+' seconds='+str(r['training_seconds']),flush=True)
            except BaseException as error:
                failures.append({'population':population,'method':method,'error':str(error),'traceback':traceback.format_exc(),'utc':s.now()})
                s.write_json(output/'failures.json',failures)
                print('FAILED '+population+'/'+method+': '+str(error),flush=True)
    s.require(s.source_hashes()==source and s.digest(s.ROOT/'data/DATA_SEAL.json')==seal,'Source/data changed during pilot')
    s.write_json(output/'failures.json',failures)
    total=sum(r['training_seconds'] for r in rows)
    s.write_json(output/'pilot_summary.json',{'status':'PASS' if not failures and len(rows)==24 else 'FAIL',
        'completed_endpoints':len(rows),'expected_endpoints':24,'failures':failures,'rows':rows,
        'total_observed_wall_seconds':time.perf_counter()-start,'total_training_seconds':total,
        'linear_projected_200_round_seconds_per_four_population_seed_loop':total*200/3,
        'projection_scope':'Single-worker engineering measurement only; excludes official audits and non-scaling setup. Two/five concurrent workers may contend; not a measured official runtime.',
        'finished_utc':s.now(),'test_accessed':False},True)
    return int(bool(failures) or len(rows)!=24)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approval',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(run(a.approval,a.output))
