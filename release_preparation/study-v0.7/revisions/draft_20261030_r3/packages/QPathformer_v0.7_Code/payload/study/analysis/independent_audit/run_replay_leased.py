"""External coordination wrapper for root-authorized independent replay."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import json

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument("--release",type=Path,required=True)
parser.add_argument("--output",type=Path,required=True)
parser.add_argument("--log",type=Path,required=True)
args=parser.parse_args()
for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","VECLIB_MAXIMUM_THREADS","BLIS_NUM_THREADS"):
    os.environ[key]="1"
sys.path.insert(0,str(ROOT/"execution"))
import durable
import resource_probe
with durable.auxiliary_lease(ROOT,"audit"):
    release=durable.read(args.release)
    expected=durable.read(durable.verify_binding(release["runtime_environment"]))
    actual=resource_probe.inspect()
    for key in ("python","interpreter","numpy_version","openblas_dll_sha256","openblas_config","effective_blas_threads","gpu_used"):
        durable.require(actual[key]==expected[key],"Independent replay runtime differs: "+key)
    durable.require(actual["numpy_version"]=="2.5.4" and actual["effective_blas_threads"]==1 and actual["gpu_used"] is False,
                    "Independent replay requires registered NumPy and one CPU BLAS thread")
    with args.log.open("x",encoding="utf-8") as log:
        log.write(json.dumps({"independent_replay_environment":actual})+"\n");log.flush()
        result=subprocess.run([r"C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe","-B","-X","utf8",
                               str(Path(__file__).with_name("replay_evaluation_v07.py")),
                               "--release",str(args.release),"--output",str(args.output)],
                              stdout=log,stderr=subprocess.STDOUT,check=False)
if result.returncode:raise SystemExit(result.returncode)
print(args.output)
