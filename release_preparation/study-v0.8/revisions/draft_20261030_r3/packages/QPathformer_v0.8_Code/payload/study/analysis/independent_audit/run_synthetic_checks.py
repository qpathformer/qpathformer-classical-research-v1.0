"""Run this independent audit suite, preserving exact source/log/cost identities."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,sys,time,unittest

HERE=Path(__file__).resolve().parent
SOURCES=('audit_endpoints_v08.py','audit_sampling_trace.py','reference_v08.py','sampler_reference.py',
         'run_audit_leased.py','AUDIT_NUMERICAL_PROTOCOL.json','test_priority_reference.py',
         'test_sampler_audit.py','test_endpoint_audit.py','run_synthetic_checks.py')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main(version):
    receipt=HERE/f'ENDPOINT_AUDITOR_SYNTHETIC_{version}.json';log=receipt.with_suffix('.log')
    if receipt.exists() or log.exists():raise RuntimeError('Preserve prior synthetic receipts')
    before={name:digest(HERE/name) for name in SOURCES}
    start=time.perf_counter();cpu=time.process_time();utc=datetime.now(timezone.utc).isoformat()
    with log.open('x',encoding='utf-8') as stream:
        suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_*.py')
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    stable=before=={name:digest(HERE/name) for name in SOURCES}
    value={'schema':'qpath-v08-independent-endpoint-auditor-synthetic-1',
        'status':'PASS' if result.wasSuccessful() and stable else 'FAIL','started_utc':utc,
        'completed_utc':datetime.now(timezone.utc).isoformat(),'tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'source_sha256':before,
        'sources_stable':stable,'log':{'path':str(log),'sha256':digest(log),'bytes':log.stat().st_size},
        'python':sys.version,'python_executable':sys.executable,
        'wall_seconds':time.perf_counter()-start,'process_cpu_seconds':time.process_time()-cpu,
        'scope':'Independent synthetic numerical checks plus read-only replay of preserved NONSTUDY producer endpoint traces and new copied inert authority fixtures; no official fits, study data, model test outcomes or releases.',
        'official_fits_run':0,'official_test_outcomes_read':False}
    with receipt.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':value['status'],'tests':result.testsRun,'receipt':str(receipt),'sha256':digest(receipt),'wall_seconds':value['wall_seconds'],'process_cpu_seconds':value['process_cpu_seconds']}))
    if value['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',default='v01')
    main(p.parse_args().version)
