"""External coordination wrapper; numerical auditor imports no execution code."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument("--stage",choices=("engineering","A","B"),required=True)
parser.add_argument("--output",type=Path,required=True)
parser.add_argument("--log",type=Path,required=True)
args=parser.parse_args()
for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","VECLIB_MAXIMUM_THREADS","BLIS_NUM_THREADS"):
    os.environ[key]="1"
sys.path.insert(0,str(ROOT/"execution"))
import durable
with durable.auxiliary_lease(ROOT,"audit"):
    with args.log.open("x",encoding="utf-8") as log:
        result=subprocess.run([r"C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe","-B","-X","utf8",
                               str(Path(__file__).with_name("audit_endpoints_v07.py")),
                               "--stage",args.stage,"--output",str(args.output)],
                              stdout=log,stderr=subprocess.STDOUT,check=False)
if result.returncode:raise SystemExit(result.returncode)
print(args.output)
