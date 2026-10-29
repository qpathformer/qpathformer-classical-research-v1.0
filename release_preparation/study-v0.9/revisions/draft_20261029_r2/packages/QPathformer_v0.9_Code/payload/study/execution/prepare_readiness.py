"""Record adapter provenance/readiness without approving or launching a stage."""
from pathlib import Path
import difflib
import json
import os
import sys
from durable import binding, sha, read, write_new, require, now, stage_jobs, PHASE_COUNTS
from bind_stage import EXECUTION_FILES

HERE = Path(__file__).resolve().parent
PRIOR = Path(r'C:\Anthony Siljeg\Q2_improvement_study_v08\execution')


def run(version='v02'):
    results = sorted(HERE.glob('test_runs/session_*/TEST_RESULT.json'), key=lambda p: p.stat().st_mtime)
    require(results, 'No synthetic integration test receipt')
    latest = read(results[-1])
    require(latest['status'] == 'PASS' and latest['skipped'] == 0 and latest['official_fits'] == 0,
            'Complete synthetic suite required')
    for name, digest in latest['source_hashes'].items():
        require(sha(HERE/name) == digest, 'Tested source changed: '+name)
    provenance = read(HERE/'VENDOR_PROVENANCE.json')
    imports = []
    for name in EXECUTION_FILES:
        old, new = binding(PRIOR/name), binding(HERE/name)
        imports.append({'name': name, 'source_v08': old, 'v09': new, 'byte_identical': old['sha256']==new['sha256']})
    for item in provenance['vendored_files']:
        require(sha(HERE/item['path']) == item['sha256'], 'ETEL vendor source changed')
    require(all(x['byte_identical'] for x in imports if x['name'] in
                ('process_identity.py', 'resource_probe.py', 'vendor/etel/core.py', 'vendor/etel/__init__.py')),
            'Stable core/native identity/runtime probe changed')
    matrix = read(HERE.parent/'governance/RUN_MATRIX.json')
    counts = {s: len(stage_jobs(matrix,s)) for s in PHASE_COUNTS}
    require(counts == PHASE_COUNTS, 'Wrong official matrix counts')
    for stage in PHASE_COUNTS:
        require(all((j['rounds'], j['updates']) == ((20,1500) if stage=='engineering' else (200,15000))
                    for j in stage_jobs(matrix,stage)), 'Wrong budgets')
    diff = ''.join(''.join(difflib.unified_diff((PRIOR/name).read_text(encoding='utf-8-sig').splitlines(True),
                    (HERE/name).read_text(encoding='utf-8-sig').splitlines(True),
                    fromfile='v08/'+name, tofile='v09/'+name)) for name in EXECUTION_FILES)
    diff_path = HERE/('V08_TO_V09_ADAPTER_DIFF_'+version+'.txt')
    with diff_path.open('x',encoding='utf-8',newline='\n') as f: f.write(diff)
    failures = [binding(p) for p in results if read(p)['status'] != 'PASS']
    recovery = {'schema':'qpath-v09-execution-synthetic-recovery-1', 'utc':now(),
        'scope':'Pre-freeze integration fixtures only; no official scientific fit affected',
        'failed_receipts':failures, 'latest_passing_receipt':binding(results[-1]),
        'cause':'Initial new closure check incorrectly equated Windows venv bootstrap PID with scientific worker PID.',
        'correction':'Retain exact native creation-identity inspection when bootstrap PID differs. No liveness inference from bootstrap exit.',
        'preservation':'Every failed test root, attempt, log and observation remains in test_runs; no prior study was modified.',
        'additional_checks':'Bounded terminal-exit wait and stage-admission block for a terminal but live worker.',
        'root_review_finding': 'The v01 manifest validator compared an integer concurrency to the actual dictionary resource_ceiling. No official run was released. v02 validates all explicit resource fields and numerical runtime against the actual v09 policy shape.',
        'official_schema_regression': 'Non-launching disposable OFFICIAL_STUDY schema fixture checks real 48-job engineering inventory, dictionary resource limits, environment, source bindings, deadline and authority.'}
    recovery_path = HERE/('SYNTHETIC_FAILURE_RECOVERY_'+version+'.json')
    write_new(recovery_path,recovery)
    report = {'schema':'qpath-v09-execution-readiness-1','status':'PASS_IMPLEMENTATION_PENDING_ROOT_REVIEW',
        'utc':now(),'official_training_launched':False,'scientific_qualification_claimed':False,
        'stage_counts':counts,'max_processes':5,'tests':binding(results[-1]),'imports':imports,
        'vendor_provenance':binding(HERE/'VENDOR_PROVENANCE.json'),'diff':binding(diff_path),
        'documentation':binding(HERE/'README_EXECUTION.txt'),
        'failure_recovery':binding(recovery_path),
        'runtime_and_data_seal':'Bound by root-prepared manifests; no official manifest or release created here',
        'credit_scope':'Root owns usage snapshots and approximate 30000-credit target with bounded safe-checkpoint continuation; adapter provides persistent graceful drain.'}
    report_path = HERE/('EXECUTION_READINESS_'+version+'.json')
    write_new(report_path,report)
    print(json.dumps({'status':report['status'],'tests_run':latest['tests_run'],'stage_counts':counts,
                      'readiness':binding(report_path)},indent=2))


if __name__=='__main__': run()
