"""All 13 methods, three full engineering rounds (225 updates); never official."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import argparse
from pathlib import Path
import time
import qstudy as s


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(exist_ok=False)
    results=[];failures=[];start=time.perf_counter()
    for method in s.METHODS:
        try:
            result=s.train(method,9501,'A',a.output/method,rounds=3,engineering=True)
            results.append({k:result[k] for k in ('method','training_seconds','total_seconds','optimizer_global_updates','selected_validation','work')})
            print(method,result['training_seconds'],flush=True)
        except Exception as error:
            failures.append({'method':method,'type':type(error).__name__,'error':str(error)})
            print('FAILED',method,error,flush=True)
        s.write_json(a.output/'progress.json',{'results':results,'failures':failures})
    s.write_json(a.output/'pilot_summary.json',{'status':'PASS' if not failures and len(results)==13 else 'FAIL',
        'engineering_only':True,'test_accessed':False,'seed':9501,'rounds':3,'results':results,'failures':failures,
        'elapsed_seconds':time.perf_counter()-start,'full_horizon_per_seed_loop_projection_seconds':sum(r['training_seconds'] for r in results)*200/3,
        'projection_limit':'Single-process engineering timing; official 3/5-process concurrency, thermal load, diagnostics and I/O alter wall time.',
        'source_hashes':s.source_hashes(),'finished_utc':s.now()})
    return int(bool(failures))


if __name__=='__main__':raise SystemExit(main())
