"""Externally approved full stage only; one BLAS thread per seed subprocess."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import argparse
from pathlib import Path
import subprocess
import sys
import time
import qstudy as study


def run_seed(stage,seed):
    for method in study.METHODS:study.verify_freeze(stage,seed,method)
    folder=study.ROOT/f'stage_{stage}'/f'seed_{seed}';folder.mkdir(parents=True,exist_ok=False)
    failures=[]
    # Rotate order across seeds; recorded explicitly, never selected by outcomes.
    shift=study.SEEDS[stage].index(seed)%len(study.METHODS)
    methods=study.METHODS[shift:]+study.METHODS[:shift]
    study.write_json(folder/'execution_order.json',{'methods':methods,'rule':'cyclic by registered seed index; incomplete balance acknowledged'})
    for method in methods:
        try:
            print(f'START {stage}/{seed}/{method}',flush=True)
            result=study.train(method,seed,stage,folder/method)
            print(f'DONE {method} validation BCE {result["selected_validation"]["bce"]:.6f}',flush=True)
        except Exception as error:
            failures.append({'method':method,'type':type(error).__name__,'message':str(error)})
            study.write_json(folder/'failures.json',failures);print(f'FAILED {method}: {error}',flush=True)
    study.write_json(folder/'failures.json',failures)
    return int(bool(failures))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=['A','B'],required=True);parser.add_argument('--seed',type=int)
    args=parser.parse_args()
    if args.seed is not None:return run_seed(args.stage,args.seed)
    for seed in study.SEEDS[args.stage]:
        for method in study.METHODS:study.verify_freeze(args.stage,seed,method)
    folder=study.ROOT/f'stage_{args.stage}';folder.mkdir(exist_ok=False)
    children=[];commands=[];start=time.perf_counter()
    for seed in study.SEEDS[args.stage]:
        command=[sys.executable,str(Path(__file__).resolve()),'--stage',args.stage,'--seed',str(seed)]
        log=(folder/f'seed_{seed}.log').open('x',encoding='utf-8')
        child=subprocess.Popen(command,cwd=study.ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        children.append((seed,child,log));commands.append({'seed':seed,'command':command,'pid':child.pid})
    study.write_json(folder/'launch.json',{'started_utc':study.now(),'commands':commands,'source_hashes':study.source_hashes(),
                'stage_freeze_sha256':study.digest(study.ROOT/f'STAGE_{args.stage}_FREEZE.json'),'one_blas_thread_per_process':True,
                'network_scope':'No network code; no socket guard installed'})
    exits=[]
    for seed,child,log in children:
        code=child.wait();log.close();exits.append({'seed':seed,'exit_code':code,'observed_finished_utc':study.now()})
        study.write_json(folder/'process_exits.json',exits)
    study.write_json(folder/'stage_status.json',{'status':'completed' if all(x['exit_code']==0 for x in exits) else 'failures_present',
                'observed_wall_seconds':time.perf_counter()-start,'exits':exits,'finished_utc':study.now()})
    return int(any(x['exit_code'] for x in exits))


if __name__=='__main__':raise SystemExit(main())
