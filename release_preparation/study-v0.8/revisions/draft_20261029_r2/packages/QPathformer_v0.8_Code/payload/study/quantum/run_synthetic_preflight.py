"""Run explicitly named synthetic-only checks and bind the prepared source."""
import os
import sys
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[key]='1'
from contextlib import redirect_stdout,redirect_stderr
from datetime import datetime,timezone
import json
from pathlib import Path
import time
import unittest
import study

ROOT=Path(__file__).resolve().parent
def bind(p):return {'path':str(p.resolve()),'sha256':study.digest(p),'bytes':p.stat().st_size}
def main():
    output=ROOT/'SCIENTIFIC_PREFLIGHT_v01.json';log=ROOT/'FINAL_SYNTHETIC_PREFLIGHT_v01.log'
    if output.exists() or log.exists():raise FileExistsError('Preserve prior preflight')
    before=study.source_hashes();started=datetime.now(timezone.utc).isoformat()
    wall=time.perf_counter();cpu=time.process_time()
    suite=unittest.TestSuite()
    for name in ('test_v08_science.py','test_routers_data.py','test_author_audit_fixture.py'):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=name))
    with log.open('x',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    wall=time.perf_counter()-wall;cpu=time.process_time()-cpu
    unchanged=before==study.source_hashes()
    # Bind every copied starting source to the sealed v0.7 inventory, read only.
    sealed=Path(r'C:\Q2\Improvement_Study_v0.7');manifest=sealed/'DELIVERY_MANIFEST.json'
    inventory={r['relative_path'].replace('\\','/'):r for r in study.read_json(manifest)['files']}
    provenance=[]
    for entry in study.read_json(ROOT/'SOURCE_PROVENANCE_INITIAL.json'):
        relative=Path(entry['source']).relative_to(Path(r'C:\Anthony Siljeg\Q2_improvement_study_v07')).as_posix()
        original=sealed/relative
        if study.digest(original)!=entry['sha256'] or inventory[relative]['sha256']!=entry['sha256']:
            raise RuntimeError('Sealed provenance mismatch '+relative)
        provenance.append({'sealed_original':bind(original),'relative_path':relative,
                           'initial_working_copy_sha256':entry['sha256'],'original_working_path':entry['source']})
    record={'schema':'qpath-v08-scientific-preflight-1','status':'PASS' if result.wasSuccessful() and unchanged else 'FAIL',
            'classification':'SYNTHETIC_ONLY_NOT_OFFICIAL_STUDY_OR_ROOT_APPROVAL','started_utc':started,
            'finished_utc':datetime.now(timezone.utc).isoformat(),'tests_run':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'source_sha256':before,'sources_unchanged':unchanged,
            'settings':study.SETTINGS,'wall_seconds':wall,'process_cpu_seconds':cpu,'log':bind(log),
            'executable':sys.executable,'numpy_version':study.np.__version__,'environment_threads':{k:os.environ[k] for k in study.THREAD_KEYS},
            'author_auditor':bind(ROOT/'audit_stage_v08.py'),'author_audit_test':bind(ROOT/'tests/test_author_audit_fixture.py'),
            'harness':bind(Path(__file__)),'sealed_starting_source_provenance':provenance,'v07_delivery_manifest':bind(manifest),
            'scope':'13 science tests,21 data/router tests and1 author-audit integration. New preserved synthetic fits use4800/1600records and12rounds/900updates. Official matrix metadata checked760identities only. No official data generation/training/test outcomes.',
            'known_limits':'Synthetic checks qualify implementation; root stage gates and independent audits remain mandatory. Legacy copied test_v07_science.py and audit_stage_v07.py are preserved provenance, never part of active test discovery or command.'}
    study.write_json(output,record,True)
    print(json.dumps({'status':record['status'],'tests':result.testsRun,'wall_seconds':wall,'cpu_seconds':cpu,'receipt':str(output),'sha256':study.digest(output)}))
    return 0 if record['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
