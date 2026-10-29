"""Run only the small NONSTUDY reproduction suite under the shared compute lease."""
from __future__ import annotations
import os
import sys
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS',
            'NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[key]='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'execution'))
import durable

def binding(path):
    p=Path(path).resolve()
    return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}

def main(output,log_path):
    output,log_path=Path(output).resolve(),Path(log_path).resolve()
    if not (output.is_relative_to(HERE) and log_path.is_relative_to(HERE)):
        raise RuntimeError('Synthetic evidence must remain in reproduction preparation directory')
    if output.exists() or log_path.exists():
        raise RuntimeError('Preserve existing synthetic receipt and log')
    # Acquisition fails immediately if the scientific stage or audit still owns it.
    # There are no numerical imports, new fixtures or output files before this lease.
    with durable.auxiliary_lease(ROOT,'audit'):
        start=datetime.now(timezone.utc).isoformat()
        wall=time.perf_counter();cpu=time.process_time()
        with log_path.open('x',encoding='utf-8') as stream:
            suite=unittest.defaultTestLoader.discover(str(HERE/'tests'),pattern='test_reproduction.py')
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        receipt={'schema':'qpath-v08-reproduction-synthetic-preflight-1',
                 'status':'PASS' if result.wasSuccessful() else 'FAILED_PRESERVED',
                 'started_utc':start,'finished_utc':datetime.now(timezone.utc).isoformat(),
                 'wall_seconds':time.perf_counter()-wall,'process_cpu_seconds':time.process_time()-cpu,
                 'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
                 'sources':[binding(HERE/name) for name in
                     ('run.py','regenerate.py','compare.py','tests/test_reproduction.py','synthetic_preflight.py')],
                 'log':binding(log_path),'official_model_data_accessed':False,
                 'scope':'Tiny synthetic metadata, 4x200-record fixture regeneration, artificial endpoint-array checks; no training fit or official array opened.'}
        durable.write_new(output,receipt)
        print(json.dumps({'status':receipt['status'],'tests_run':result.testsRun,
                          'receipt':binding(output),'wall_seconds':receipt['wall_seconds']}))
        return 0 if result.wasSuccessful() else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True);p.add_argument('--log',required=True)
    a=p.parse_args()
    raise SystemExit(main(a.output,a.log))
