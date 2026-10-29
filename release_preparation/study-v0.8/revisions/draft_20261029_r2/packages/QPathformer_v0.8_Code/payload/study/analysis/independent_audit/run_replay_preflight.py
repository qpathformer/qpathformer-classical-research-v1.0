"""Bounded synthetic-only score replay checks; never invoke an official replay."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,sys,time,unittest

HERE=Path(__file__).resolve().parent
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main(version):
    receipt=HERE/f'REPLAY_SYNTHETIC_PREFLIGHT_{version}.json';log=receipt.with_suffix('.log')
    if receipt.exists() or log.exists():raise RuntimeError('Preserve prior preflight evidence')
    started=time.perf_counter();cpu=time.process_time();utc=datetime.now(timezone.utc).isoformat()
    import replay_evaluation_v08 as replay
    before={name:digest(HERE/name) for name in replay.SOURCES}
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in
        ('test_statistics_v08','test_replay_metrics_v08','test_replay_evaluation_v08','test_replay_priority_v08','test_replay_wrapper_v08'))
    with log.open('x',encoding='utf-8') as stream:result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    stable=before=={name:digest(HERE/name) for name in replay.SOURCES}
    data={'schema':'qpath-v08-independent-replay-synthetic-1','status':'PASS' if result.wasSuccessful() and stable else 'FAIL',
        'started_utc':utc,'completed_utc':datetime.now(timezone.utc).isoformat(),'tests_run':result.testsRun,
        'errors':len(result.errors),'failures':len(result.failures),'source_sha256':before,
        'source_stable':stable,'log_sha256':digest(log),'wall_seconds':time.perf_counter()-started,
        'process_cpu_seconds':time.process_time()-cpu,'scope':'Synthetic arrays, source/protocol metadata and pure statistics only; no official data, checkpoint, trace, ledger or model/test outcome access.',
        'official_outcomes_read':False}
    with receipt.open('x',encoding='utf-8') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':data['status'],'tests':result.testsRun,'receipt':str(receipt),'sha256':digest(receipt),'wall_seconds':data['wall_seconds'],'process_cpu_seconds':data['process_cpu_seconds']}))
    if data['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',default='v01');main(p.parse_args().version)
