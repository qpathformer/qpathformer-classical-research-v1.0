"""Engineering-only checks and full-size three-round timing pilot. No official training."""
import os
for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[name] = "1"
from pathlib import Path
import json
import platform
import sys
import subprocess
import time
import argparse
import qstudy as study


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=study.ROOT/"preflight_v01")
    args=parser.parse_args()
    out = args.output
    out.mkdir(exist_ok=False)
    start=time.perf_counter()
    tests=subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-v"],
                         cwd=study.ROOT,capture_output=True,text=True)
    (out/"unit_tests.txt").write_text(tests.stdout+tests.stderr,encoding="utf-8")
    if tests.returncode:
        raise RuntimeError("Preflight tests failed; inspect retained transcript")
    checks=study.reference.bounded_checks()
    study.write_json(out/"independent_3240_checks.json",checks)
    if checks["status"] != "pass":
        raise RuntimeError("Reference checks failed")
    results=[]
    for method in study.STAGE_A_METHODS:
        print("Engineering timing pilot:",method,flush=True)
        r=study.train(method,901,"A",out/method,rounds=3,engineering=True)
        results.append({"method":method,"parameter_count":r["parameter_count"],
                        "measured_training_seconds_3_rounds":r["training_seconds"],
                        "linear_200_round_projection_seconds":r["training_seconds"]*200/3,
                        "work_3_rounds":r["work"],"parameter_count":r["parameter_count"],
                        "global_updates":r["optimizer_global_updates"]})
    summary={"status":"pass","classification":"ENGINEERING PREFLIGHT ONLY",
             "official_training_started":False,"test_population_loaded":False,
             "unit_test_returncode":tests.returncode,"reference_status":checks["status"],
             "timings":results,"total_seconds":time.perf_counter()-start,
             "environment":{"python":sys.version,"numpy":study.np.__version__,"platform":platform.platform(),
                            "executable":sys.executable,"threads":{k:os.getenv(k) for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}},
             "source_hashes":study.source_hashes(),
             "timing_limit":"Three rounds on one process; linear projections exclude contention, diagnostics and reporting. Pilot uses an independent engineering dataset and seed, not development results."}
    study.write_json(out/"PREFLIGHT_SUMMARY.json",summary)
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
