"""Launch one externally approved complete stage, two/five CPU seed workers.

Each worker runs every registered population and arm. A failure is preserved
and remaining arms continue, but the stage fails. No retry or resume is implied.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import argparse
from pathlib import Path
import subprocess
import sys
import time
import study


def method_order(stage,population,seed):
    pi=study.POPULATIONS[stage].index(population);si=study.SEEDS[stage].index(seed)
    shift=(pi*len(study.SEEDS[stage])+si)%len(study.METHODS)
    result=study.METHODS[shift:]+study.METHODS[:shift]
    return result[::-1] if (pi+si)%2 else result


def worker(stage,seed):
    for population in study.POPULATIONS[stage]:
        for method in study.METHODS:study.verify_freeze(stage,population,seed,method)
    stage_dir=study.ROOT/f'stage_{stage}';failures=[]
    orders={pop:list(method_order(stage,pop,seed)) for pop in study.POPULATIONS[stage]}
    study.write_json(stage_dir/f'seed_{seed}_execution_order.json',{'seed':seed,'methods_by_population':orders,
        'rule':'rotate by population index times seed count plus seed index; reverse on odd population+seed index; not fully timing-balanced'},True)
    for population in study.POPULATIONS[stage]:
        folder=stage_dir/population/f'seed_{seed}';folder.mkdir(parents=True,exist_ok=False)
        for method in orders[population]:
            try:
                print(f'START {stage}/{population}/{seed}/{method}',flush=True)
                study.train(method,seed,stage,population,folder/method)
                print(f'DONE {stage}/{population}/{seed}/{method}',flush=True)
            except Exception as error:
                failures.append({'population':population,'seed':seed,'method':method,'type':type(error).__name__,'error':str(error),'utc':study.now()})
                study.write_json(stage_dir/f'seed_{seed}_failures.json',failures)
                print(f'FAILED {population}/{method}: {error}',flush=True)
    study.write_json(stage_dir/f'seed_{seed}_failures.json',failures)
    return int(bool(failures))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=study.SEEDS,required=True)
    parser.add_argument('--seed',type=int);a=parser.parse_args()
    if a.seed is not None:return worker(a.stage,a.seed)
    for pop in study.POPULATIONS[a.stage]:
        for seed in study.SEEDS[a.stage]:
            for method in study.METHODS:study.verify_freeze(a.stage,pop,seed,method)
    folder=study.ROOT/f'stage_{a.stage}';folder.mkdir(exist_ok=False)
    children=[];commands=[];start=time.perf_counter()
    for seed in study.SEEDS[a.stage]:
        command=[sys.executable,str(Path(__file__).resolve()),'--stage',a.stage,'--seed',str(seed)]
        log=(folder/f'seed_{seed}.log').open('x',encoding='utf-8')
        child=subprocess.Popen(command,cwd=study.ROOT,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        children.append((seed,child,log));commands.append({'seed':seed,'pid':child.pid,'command':command})
    study.write_json(folder/'launch.json',{'started_utc':study.now(),'commands':commands,'stage':a.stage,
            'source_hashes':study.source_hashes(),'stage_freeze_sha256':study.digest(study.ROOT/f'STAGE_{a.stage}_FREEZE.json'),
            'one_blas_thread_per_process':True,'network_scope':'No network code; no socket guard installed'},True)
    exits=[]
    # Observe exited processes without making the first seed a reporting barrier.
    pending=list(children)
    while pending:
        for seed,child,log in pending.copy():
            code=child.poll()
            if code is None:continue
            log.close();exits.append({'seed':seed,'exit_code':code,'observed_finished_utc':study.now()})
            pending.remove((seed,child,log));study.write_json(folder/'process_exits.json',exits)
        if pending:time.sleep(2)
    success=all(e['exit_code']==0 for e in exits)
    count=len(list(folder.glob('*/seed_*/*/endpoint_commit.json')))
    expected=len(study.POPULATIONS[a.stage])*len(study.SEEDS[a.stage])*len(study.METHODS)
    success=success and count==expected
    study.write_json(folder/'stage_status.json',{'status':'completed' if success else 'failures_present',
         'stage':a.stage,'observed_wall_seconds':time.perf_counter()-start,'expected_endpoints':expected,
         'committed_endpoints':count,'exits':exits,'finished_utc':study.now()},True)
    return int(not success)


if __name__=='__main__':raise SystemExit(main())
