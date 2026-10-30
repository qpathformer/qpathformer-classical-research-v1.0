"""Metadata and inert mocked scheduling tests; invoke only in root-assigned window."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,time,unittest

HERE=Path(__file__).resolve().parent
NAMES=('run_audit_in_process_v02.py','test_audit_coordination_v02.py','run_coordination_preflight_v02.py')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main(version):
    output=HERE/f'ENDPOINT_COORDINATION_SYNTHETIC_{version}.json';log=output.with_suffix('.log')
    if output.exists() or log.exists():raise RuntimeError('Preserve previous coordination test evidence')
    start=time.perf_counter();cpu=time.process_time();utc=datetime.now(timezone.utc).isoformat()
    sources={name:sha(HERE/name) for name in NAMES}
    suite=unittest.defaultTestLoader.loadTestsFromName('test_audit_coordination_v02')
    with log.open('x',encoding='utf-8') as stream:result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    stable=sources=={name:sha(HERE/name) for name in NAMES}
    record={'schema':'qpath-v08-endpoint-coordination-synthetic-2','status':'PASS' if result.wasSuccessful() and stable else 'FAIL',
        'started_utc':utc,'completed_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sources,'source_stable':stable,
        'tests_run':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'log_sha256':sha(log),
        'wall_seconds':time.perf_counter()-start,'process_cpu_seconds':time.process_time()-cpu,
        'scope':'Inert temporary fixtures and mocked lease/runtime/numerical callbacks only. No real lease, official ledger, data, checkpoint or model outcomes.'}
    with output.open('x',encoding='utf-8') as handle:json.dump(record,handle,indent=2,allow_nan=False)
    print(json.dumps({'status':record['status'],'receipt':str(output),'sha256':sha(output),'tests':result.testsRun}))
    if record['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',default='v02');main(parser.parse_args().version)
