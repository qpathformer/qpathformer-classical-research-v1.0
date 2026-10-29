"""Same-process scheduling wrapper around the unchanged frozen numerical audit.

Source preparation is not audit authorization. Root assigns each stage invocation.
"""
from pathlib import Path
from datetime import datetime,timezone
from contextlib import redirect_stdout,redirect_stderr
import argparse
import hashlib
import json
import os
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
THREAD_VARIABLES=("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","VECLIB_MAXIMUM_THREADS","BLIS_NUM_THREADS")
FROZEN=HERE/'INDEPENDENT_ENDPOINT_SOURCE_FREEZE_v01.json'
COORDINATION=HERE/'ENDPOINT_COORDINATION_SOURCE_FREEZE_v03.json'
COUNTS={'engineering':40,'A':80,'B':640}


def binding(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def need(condition,message):
    if not condition:raise RuntimeError(message)


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:json.dump(value,handle,indent=2,allow_nan=False)


def verify_preparation():
    coordination=read(COORDINATION)
    need(coordination['schema']=='qpath-v08-endpoint-coordination-source-freeze-2','Wrong coordination registration')
    for item in coordination['sources']:need(binding(item['path'])==item,'Coordination source changed')
    need(any(Path(item['path']).resolve()==Path(__file__).resolve() for item in coordination['sources']),'Wrapper missing from registration')
    need(coordination['numerical_source_freeze']==binding(FROZEN),'Frozen numerical registration changed')
    frozen=read(FROZEN)
    need(frozen['schema']=='qpath-v08-independent-endpoint-source-freeze-1','Wrong numerical source registration')
    expected={'audit_endpoints_v08.py','audit_sampling_trace.py','reference_v08.py','sampler_reference.py','run_audit_leased.py','AUDIT_NUMERICAL_PROTOCOL.json'}
    need(len(frozen['sources'])==6 and {Path(item['path']).name for item in frozen['sources']}==expected,'Frozen numerical inventory differs')
    for item in frozen['sources']:
        need(Path(item['path']).resolve()==HERE/Path(item['path']).name and binding(item['path'])==item,'Frozen numerical source changed')
    for key in ('runtime_environment','study_plan'):
        need(binding(coordination[key]['path'])==coordination[key],'Registered runtime/plan changed')
    need(Path(coordination['runtime_environment']['path']).resolve()==ROOT/'governance/NUMERICAL_ENVIRONMENT.json','Wrong runtime record')
    need(Path(coordination['study_plan']['path']).resolve()==ROOT/'governance/STUDY_PLAN.json','Wrong study plan')
    return coordination


def run_leased(args):
    for key in THREAD_VARIABLES:os.environ[key]='1'
    for path in (args.output,args.log,args.coordination_receipt):
        need(path.resolve().is_relative_to(ROOT.resolve()),'Audit outputs must stay within working root')
        need(path.parent.is_dir() and not path.exists(),'Fresh audit output/log/coordination receipt with existing parent required')
    need(len({p.resolve() for p in (args.output,args.log,args.coordination_receipt)})==3,'Output paths must be distinct')
    sys.path.insert(0,str(ROOT/'execution'))
    import durable
    import resource_probe
    import process_identity
    started=time.perf_counter();cpu=time.process_time();started_utc=datetime.now(timezone.utc).isoformat()
    with durable.auxiliary_lease(ROOT,'audit'):
        preparation=verify_preparation()
        stable={'coordination_source_freeze':binding(COORDINATION),'numerical_source_freeze':binding(FROZEN),
            'wrapper':binding(__file__),'runtime_environment':preparation['runtime_environment'],'study_plan':preparation['study_plan']}
        identity=process_identity.identity()
        need(identity is not None and set(identity)=={'pid','creation_token','identity_source'} and identity['pid']==os.getpid(),
             'Exact live process identity required')
        invoked=False;actual=None;audit_receipt=None
        with args.log.open('x',encoding='utf-8') as log:
            with redirect_stdout(log),redirect_stderr(log):
                try:
                    expected=read(preparation['runtime_environment']['path']);actual=resource_probe.inspect()
                    for key in ('python','interpreter','numpy_version','openblas_dll_sha256','openblas_config','effective_blas_threads','gpu_used'):
                        need(actual[key]==expected[key],'Independent audit runtime differs: '+key)
                    need(actual['python']=='3.12.14' and actual['numpy_version']=='2.5.4' and actual['effective_blas_threads']==1 and actual['gpu_used'] is False,
                         'Historical one-thread CPU runtime required')
                    need(sys.dont_write_bytecode and sys.flags.utf8_mode==1,'Invoke scientific Python with -B -X utf8')
                    print(json.dumps({'same_process_audit':identity,'environment':actual,'stage':args.stage}),flush=True)
                    import audit_endpoints_v08
                    invoked=True
                    audit_receipt=audit_endpoints_v08.audit_stage(args.stage)
                    need(audit_receipt['status']=='PASS' and audit_receipt['stage']==args.stage and
                         audit_receipt['verified_endpoints']==COUNTS[args.stage],'Numerical audit receipt incomplete')
                    for item in stable.values():need(binding(item['path'])==item,'Audit preparation changed during execution')
                    verify_preparation()
                    need(process_identity.identity()==identity,'Lease owner identity changed')
                    write_new(args.output,audit_receipt)
                    print(json.dumps({'status':'PASS','stage':args.stage,'verified_endpoints':COUNTS[args.stage],'receipt':binding(args.output)}),flush=True)
                except BaseException as error:
                    traceback.print_exc();log.flush()
                    if invoked and not args.output.exists():
                        write_new(args.output,{'status':'FAIL','stage':args.stage,'created_utc':datetime.now(timezone.utc).isoformat(),
                            'error':repr(error),'traceback':traceback.format_exc(),'test_model_outcomes_accessed':False})
                    write_new(args.coordination_receipt,{'schema':'qpath-v08-independent-audit-coordination-2','status':'FAIL_PRESERVED',
                        'stage':args.stage,'started_utc':started_utc,'completed_utc':datetime.now(timezone.utc).isoformat(),
                        'process_identity':identity,'same_process_lease_and_numerical_audit':True,'numerical_audit_invoked':invoked,
                        'bindings':stable,'runtime_observed':actual,'audit':binding(args.output) if args.output.exists() else None,
                        'log':binding(args.log),'error':repr(error),'traceback':traceback.format_exc(),
                        'wall_seconds':time.perf_counter()-started,'process_cpu_seconds':time.process_time()-cpu})
                    raise
        receipt={'schema':'qpath-v08-independent-audit-coordination-2','status':'PASS','stage':args.stage,
            'started_utc':started_utc,'completed_utc':datetime.now(timezone.utc).isoformat(),'process_identity':identity,
            'same_process_lease_and_numerical_audit':True,'numerical_audit_invoked':True,'bindings':stable,
            'runtime_observed':actual,'audit':binding(args.output),'log':binding(args.log),'verified_endpoints':COUNTS[args.stage],
            'wall_seconds':time.perf_counter()-started,'process_cpu_seconds':time.process_time()-cpu,
            'cost_scope':'This lease-owning process from pre-lease setup through completed numerical audit and checks; no numerical subprocess.',
            'test_model_outcomes_accessed':False}
        write_new(args.coordination_receipt,receipt)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=tuple(COUNTS),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--log',type=Path,required=True)
    parser.add_argument('--coordination-receipt',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run_leased(args)))


if __name__=='__main__':main()
