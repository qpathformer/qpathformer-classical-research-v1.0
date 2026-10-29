"""Root-authorized replay runs directly in its auxiliary-lease-owning process."""
from pathlib import Path
import argparse
from contextlib import redirect_stdout, redirect_stderr
import os
import sys
import json
import traceback

ROOT=Path(__file__).resolve().parents[2]
THREAD_VARIABLES=("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","VECLIB_MAXIMUM_THREADS","BLIS_NUM_THREADS")


def run_leased(args):
    for key in THREAD_VARIABLES:os.environ[key]="1"
    sys.path.insert(0,str(ROOT/"execution"))
    import durable
    import resource_probe
    with durable.auxiliary_lease(ROOT,"audit"):
        # The same PID owns the lease, runtime probe, replay, and output commit.
        # No numerical subprocess can outlive stale-lease cleanup.
        with args.log.open("x",encoding="utf-8") as log:
            with redirect_stdout(log),redirect_stderr(log):
                try:
                    release=durable.read(args.release)
                    expected=durable.read(durable.verify_binding(release["runtime_environment"]))
                    actual=resource_probe.inspect()
                    for key in ("python","interpreter","numpy_version","openblas_dll_sha256","openblas_config","effective_blas_threads","gpu_used"):
                        durable.require(actual[key]==expected[key],"Independent replay runtime differs: "+key)
                    durable.require(actual["numpy_version"]=="2.5.4" and actual["effective_blas_threads"]==1 and actual["gpu_used"] is False,
                                    "Independent replay requires registered NumPy and one CPU BLAS thread")
                    print(json.dumps({"independent_replay_environment":actual,"lease_owner_and_replay_pid":os.getpid()}),flush=True)
                    import replay_evaluation_v08
                    summary=replay_evaluation_v08.replay(args.release,args.output)
                    print(json.dumps(summary),flush=True)
                except BaseException:
                    traceback.print_exc();log.flush()
                    raise
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--log",type=Path,required=True)
    args=parser.parse_args()
    run_leased(args)
    print(args.output)


if __name__=="__main__":main()
