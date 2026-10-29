"""Root-gated clean-directory four-fit reproduction, serial in one leased process."""
from __future__ import annotations
import os
import sys
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[key]='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
import argparse
from datetime import datetime,timezone
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import time
import traceback

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'analysis/official_evaluation'))
import gate

SOURCE_FILES=('run.py','regenerate.py','compare.py','tests/test_reproduction.py')

def now():return datetime.now(timezone.utc).isoformat()
def sources(root):
    return {'analysis/reproduction/'+name:gate.sha(Path(root)/'analysis/reproduction'/name) for name in SOURCE_FILES}
def registration(root):
    root=Path(root).resolve();protocol=gate.read(root/'governance/REPRODUCTION_PROTOCOL.json')
    matrix=gate.read(root/'governance/RUN_MATRIX.json')
    jobs={j['run_id']:j for j in matrix['runs']}
    required=protocol['endpoints']
    gate.require(len(required)==len(set(required))==4,'Exactly four registered reproduction targets required')
    gate.require(all(jobs[i]['stage']=='B' and jobs[i]['rounds']==200 and jobs[i]['updates']==15000 for i in required),
                 'Reproduction changes original budget')
    return {'schema':'qpath-v08-reproduction-registration-1','status':'PREPARED_FOR_ROOT_REVIEW',
            'created_utc':now(),'sources':sources(root),'test_access_authorized':False,
            'protocol':gate.binding(root/'governance/REPRODUCTION_PROTOCOL.json'),
            'matrix':gate.binding(root/'governance/RUN_MATRIX.json'),'run_ids':required,
            'procedure':'One fresh process holds auxiliary lease; exact source/data generation and four sequential full fits in a new clean directory; no original checkpoint copied.',
            'same_environment_tolerances':protocol['same_environment_tolerances']}

def validate_release(release,output,registered):
    gate.require(release.get('schema')=='qpath-v08-reproduction-release-1' and
                 release.get('review_status')=='approved_by_root','Separate root reproduction approval required')
    gate.require(release.get('phase')=='reproduction' and release.get('test_access_authorized') is True,
                 'Wrong reproduction release phase/access')
    gate.require(release.get('max_parallel_tasks')==release.get('required_blas_threads')==1,
                 'Serial single-thread reproduction required')
    gate.require(release.get('run_ids')==registered['run_ids'],'Reproduction targets/order changed')
    gate.require(Path(release['output']).resolve()==Path(output).resolve(),'Reproduction output not root-bound')

def copy_clean_sources(root,clean,verified,training_authorization):
    root,clean=Path(root),Path(clean)
    clean.mkdir(exist_ok=False);(clean/'quantum/tests').mkdir(parents=True);(clean/'governance').mkdir()
    records=[]
    for name in gate.SCIENCE_FILES:
        source=root/'quantum'/name;destination=clean/'quantum'/name
        gate.require(gate.sha(source)==verified['source_freeze']['sources']['quantum/'+name],'Original science source drift')
        shutil.copyfile(source,destination)
        gate.require(gate.sha(destination)==gate.sha(source),'Clean source copy drift')
        records.append({'original':gate.binding(source),'clean':gate.binding(destination),'kind':'frozen_scientific_source'})
    for name in ('STUDY_PLAN.json','RUN_MATRIX.json'):
        source=root/'governance'/name;destination=clean/'governance'/name;shutil.copyfile(source,destination)
        gate.require(gate.sha(destination)==gate.sha(source),'Clean protocol copy drift')
        records.append({'original':gate.binding(source),'clean':gate.binding(destination),'kind':'frozen_registration_metadata'})
    destination=clean/'governance/STAGE_B_FREEZE.json';shutil.copyfile(training_authorization,destination)
    records.append({'original':gate.binding(training_authorization),'clean':gate.binding(destination),'kind':'original_B_training_authorization_metadata'})
    return records

def verify_endpoint_payloads(item,root):
    """Hash-only verification; never trust a changed file behind a bound commit."""
    path=gate.verify_binding(item,root);commit=gate.read(path);folder=path.parent
    gate.require(commit.get('schema')=='qpath-v08-endpoint-1' and
                 commit.get('status')=='completed','Invalid reproduction endpoint commit')
    actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    gate.require(actual==set(commit['files'])|{path.name},'Endpoint payload inventory changed')
    for relative,expected in commit['files'].items():
        file=(folder/relative).resolve()
        gate.require(file.is_relative_to(folder) and file.is_file() and
                     file.stat().st_size==expected['bytes'] and gate.sha(file)==expected['sha256'],
                     'Endpoint committed payload changed: '+relative)
    return folder

def claim(root,release,authorization,output,identity):
    """Exclusive auxiliary lease surrounds this registry; never resume implicitly."""
    import process_identity
    folder=root/'analysis/reproduction_attempts';folder.mkdir(exist_ok=True)
    previous=sorted(folder.glob('*.json'))
    for path in previous:
        row=gate.read(path)
        gate.require(not process_identity.alive(row['process_identity']),'A reproduction process remains live')
        old_output=Path(row['output'])
        gate.require(not (old_output/'REPRODUCTION_COMMIT.json').exists(),'A completed reproduction must never be duplicated')
    if previous:
        expected=[gate.binding(p) for p in previous]
        recovery=release.get('recovery')
        gate.require(isinstance(recovery,dict) and recovery.get('review_status')=='approved_by_root'
                     and recovery.get('prior_attempts')==expected and bool(recovery.get('reason')),
                     'Preserved incomplete reproduction requires root-reviewed exact prior-attempt recovery')
    name=hashlib.sha256(str(output).encode('utf-8')).hexdigest()+'.json'
    path=folder/name
    gate.write_new(path,{'schema':'qpath-v08-reproduction-attempt-1','created_utc':now(),'process_identity':identity,
                        'authorization':gate.binding(authorization),'output':str(output),'automatic_resume':False})
    return gate.binding(path)

def run(root,authorization,output):
    root,output=Path(root).resolve(),Path(output).resolve()
    gate.require(root==ROOT.resolve() and output.is_relative_to(root/'analysis') and not output.exists(),
                 'New root-local reproduction output required')
    sys.path.insert(0,str(root/'execution'))
    import durable
    import process_identity
    import resource_probe
    with durable.auxiliary_lease(root,'reproduction'):
        authorization_binding=gate.binding(authorization)
        release=gate.read(gate.verify_binding(authorization_binding,root))
        reg_path=gate.verify_binding(release['registration'],root);reg=gate.read(reg_path)
        gate.require(reg=={**registration(root),'created_utc':reg['created_utc']},'Reproduction registration/source/protocol changed')
        validate_release(release,output,reg)
        evaluation_release=gate.verify_binding(release['evaluation_release'],root)
        verified=gate.verify_completed_evaluation(root,evaluation_release,release['evaluation_commit'])
        training_auth=gate.verify_binding(release['training_authorization'],root)
        auth=gate.read(training_auth);jobs={j['run_id']:j for j in verified['jobs']}
        selected=[jobs[i] for i in reg['run_ids']]
        gate.require(auth.get('schema')=='qpath-v08-stage-authorization-1' and auth.get('review_status')=='approved_by_root'
                     and auth.get('stage')=='B' and auth['run_ids']==[j['run_id'] for j in verified['jobs']],
                     'Original complete B training authorization required')
        gate.require(auth['data_seal_sha256']==verified['release']['data_seal']['sha256'],'Reproduction data seal differs')
        start_bindings=[authorization_binding,release['registration'],release['evaluation_release'],
                        release['evaluation_commit'],release['training_authorization'],
                        reg['protocol'],reg['matrix'],verified['release']['data_seal'],
                        verified['release']['runtime_environment'],
                        gate.binding(root/'governance/DATA_REGISTRATION.json')]
        for job in selected:
            original=gate.read(verified['endpoint_commits'][job['run_id']]['path'])
            gate.require(original['authorization_sha256']==gate.sha(training_auth),'Original endpoint authorization differs')
        environment=resource_probe.inspect()
        expected=gate.read(gate.verify_binding(verified['release']['runtime_environment'],root))
        for key in ('python','interpreter','numpy_version','openblas_dll_sha256','openblas_config','effective_blas_threads','gpu_used'):
            gate.require(environment[key]==expected[key],'Reproduction numerical environment differs: '+key)
        gate.require(environment['effective_blas_threads']==1,'Reproduction BLAS count differs')
        identity=process_identity.identity();gate.require(identity is not None,'No reproduction process identity')
        attempt=claim(root,release,authorization,output,identity)
        output.mkdir(parents=True,exist_ok=False)
        gate.write_new(output/'START.json',{'status':'RUNNING','started_utc':now(),'authorization':authorization_binding,
                       'registration':release['registration'],'evaluation_commit':verified['evaluation_commit'],
                       'attempt':attempt,'process_identity':identity,'environment':environment})
        wall=time.perf_counter();cpu=time.process_time()
        try:
            clean=output/'clean'
            copied=copy_clean_sources(root,clean,verified,training_auth)
            gate.write_new(output/'clean_source_inventory.json',copied)
            for name in ('models','study','prepare_data','routers','circuits','sampling','reference_v03'):
                gate.require(name not in sys.modules,'Scientific module was preloaded before clean reproduction: '+name)
            sys.path.insert(0,str(clean/'quantum'))
            d=importlib.import_module('prepare_data')
            import regenerate
            data_report=regenerate.recreate(root,clean,d,selected)
            gate.write_new(output/'data_recreation.json',data_report)
            study=importlib.import_module('study')
            for name in ('models','study','prepare_data','routers','circuits','sampling'):
                gate.require(Path(sys.modules[name].__file__).resolve().is_relative_to(clean/'quantum'),
                             'Scientific code escaped clean source directory')
            gate.require(study.source_hashes()==auth['scientific_source_hashes'],'Clean science hash mismatch')
            comparisons=[];fit_records=[]
            import compare
            protocol=gate.read(root/'governance/REPRODUCTION_PROTOCOL.json')
            with (output/'fit_ledger.jsonl').open('x',encoding='utf-8') as ledger:
                for job in selected:
                    destination=output/'endpoints'/job['run_id']
                    start=time.perf_counter();fit_cpu=time.process_time()
                    ledger.write(json.dumps({'job_id':job['run_id'],'event':'starting','utc':now(),'output':str(destination)})+'\n')
                    ledger.flush();os.fsync(ledger.fileno())
                    study.train(job['run_id'],destination,clean/'governance/STAGE_B_FREEZE.json')
                    original_binding=verified['endpoint_commits'][job['run_id']]
                    original=verify_endpoint_payloads(original_binding,root)
                    reproduced_binding=gate.binding(destination/'endpoint_commit.json')
                    verify_endpoint_payloads(reproduced_binding,root)
                    comparison=compare.compare_endpoint(original,destination,protocol)
                    comparison.update(original_commit=original_binding,reproduced_commit=reproduced_binding)
                    comparisons.append(comparison)
                    record={'job_id':job['run_id'],'event':'completed','utc':now(),
                            'wall_seconds_including_author_comparison':time.perf_counter()-start,
                            'process_cpu_seconds_including_author_comparison':time.process_time()-fit_cpu,
                            'endpoint_commit':gate.binding(destination/'endpoint_commit.json')}
                    fit_records.append(record);ledger.write(json.dumps(record)+'\n');ledger.flush();os.fsync(ledger.fileno())
            gate.write_new(output/'author_comparisons.json',comparisons)
            gate.write_new(output/'endpoint_index.json',fit_records)
            gate.require(sources(root)==reg['sources'],'Reproduction source drift during run')
            for item in start_bindings:gate.verify_binding(item,root)
            for item in copied:
                gate.verify_binding(item['original'],root)
                gate.verify_binding(item['clean'],root)
            for comparison in comparisons:
                verify_endpoint_payloads(comparison['original_commit'],root)
                verify_endpoint_payloads(comparison['reproduced_commit'],root)
            gate.require(study.source_hashes()==auth['scientific_source_hashes'],'Clean science changed during reproduction')
            summary={'schema':'qpath-v08-reproduction-summary-1','status':'PASS','count':4,
                     'phase':'reproduction','run_ids':reg['run_ids'],'authorization':authorization_binding,'registration':release['registration'],
                     'evaluation_commit':verified['evaluation_commit'],'training_authorization':release['training_authorization'],
                     'clean_data_recreation':gate.binding(output/'data_recreation.json'),
                     'author_comparisons':gate.binding(output/'author_comparisons.json'),'process_identity':identity,
                     'finished_utc':now(),'wall_seconds':time.perf_counter()-wall,'process_cpu_seconds':time.process_time()-cpu,
                     'process_resources':{**resource_probe.process_resources(),
                         'scope':'Whole serial reproduction process including imports, release verification, data recreation, four fits, author comparisons and writes through sampling time'},
                     'original_checkpoints_copied':False,'fit_count':4,'full_rounds':800,'full_updates':60000,
                     'independent_audit':'REQUIRED_SEPARATELY',
                     'scope':'Four same-environment clean reproduction checks; do not increase population n or B endpoint count.'}
            gate.write_new(output/'summary.json',summary)
            files={p.relative_to(output).as_posix():{'sha256':gate.sha(p),'bytes':p.stat().st_size}
                   for p in sorted(output.rglob('*')) if p.is_file()}
            gate.write_new(output/'REPRODUCTION_COMMIT.json',{'schema':'qpath-v08-reproduction-commit-1','status':'completed',
                           'count':4,'run_ids':reg['run_ids'],'authorization':gate.binding(authorization),
                           'registration':release['registration'],'evaluation_commit':verified['evaluation_commit'],'files':files})
            return summary
        except BaseException as error:
            gate.write_new(output/'FAILURE.json',{'status':'FAILED_PRESERVED','utc':now(),'error':repr(error),
                           'traceback':traceback.format_exc(),'automatic_resume':False,
                           'recovery':'Preserve all partial data, sources, fits and logs. Root-reviewed fresh output with identical recipes only.'})
            raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--phase',choices=('registration','reproduce'),required=True)
    parser.add_argument('--authorization')
    a=parser.parse_args()
    if a.phase=='registration':
        value=registration(a.root);gate.write_new(a.output,value);print(json.dumps({'status':value['status'],'output':a.output}))
    else:
        if not a.authorization:parser.error('--authorization required')
        print(json.dumps(run(a.root,a.authorization,a.output),allow_nan=False))
