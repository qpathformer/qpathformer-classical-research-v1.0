"""Monitor approved confirmation training and prepare review without test access.

Runs only validation endpoint auditing and label-independent local Aer fixtures
after all endpoints complete. It never calls --evaluate or issues a release.
"""
import os
for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[name]="1"
import json
import subprocess
import sys
import time
import traceback
import qstudy as s


def main():
    freeze=s.read_json(s.ROOT/"STAGE_B_FREEZE.json")
    for seed in freeze["training_seeds"]:
        for method in freeze["methods"]:
            s.verify_freeze("B",seed,method)
    expected=len(freeze["training_seeds"])*len(freeze["methods"])
    output=s.ROOT/"stage_B_watch"
    output.mkdir(exist_ok=False)
    s.write_json(output/"identity.json",{"created_utc":s.now(),"pid":os.getpid(),"watcher_sha256":s.digest(__file__),
        "stage_b_freeze_sha256":s.digest(s.ROOT/"STAGE_B_FREEZE.json"),"registered_endpoints":expected,
        "purpose":"Completion monitoring, independent validation audit and local Aer fixtures only; no test evaluation or release"})
    previous=None
    try:
        while True:
            statuses=[]
            for path in sorted((s.ROOT/"stage_B").glob("seed_*/*/status.json")):
                try:
                    statuses.append(s.read_json(path))
                except json.JSONDecodeError:
                    continue
            completed=sum(r["status"]=="completed" for r in statuses)
            with (output/"health.jsonl").open("a",encoding="utf-8") as handle:
                handle.write(json.dumps({"utc":s.now(),"registered":expected,"completed":completed,"statuses":statuses})+"\n")
            if completed!=previous:
                print(f"{s.now()} Completed {completed}/{expected}",flush=True)
                previous=completed
            stage_path=s.ROOT/"stage_B/stage_status.json"
            if stage_path.exists():
                try:
                    stage=s.read_json(stage_path)
                except json.JSONDecodeError:
                    time.sleep(1)
                    continue
                if stage["status"]!="completed" or completed!=expected:
                    raise RuntimeError("Confirmation training has failed or missing endpoints; root review required")
                break
            time.sleep(60)
        operations=[("endpoint_audit",[sys.executable,str(s.ROOT/"evaluate_confirmation.py"),"--prepare"],"CONFIRMATION_ENDPOINT_LOCK.json"),
                    ("local_readiness",[sys.executable,str(s.ROOT/"local_readiness.py")],"local_readiness_results")]
        for name,command,artifact in operations:
            if (s.ROOT/artifact).exists():
                raise FileExistsError("A prior review artifact exists; preserve it and seek root review")
            with (output/f"{name}.log").open("w",encoding="utf-8") as handle:
                child=subprocess.run(command,cwd=s.ROOT,stdout=handle,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
            if child.returncode:
                raise RuntimeError(f"{name} failed; see preserved log")
        readiness=s.read_json(s.ROOT/"local_readiness_results/summary.json")
        s.write_json(output/"READY_FOR_EVALUATION_REVIEW.json",{
            "created_utc":s.now(),"status":"Awaiting separate root review and one-time test release",
            "registered_endpoints":expected,"endpoint_lock_sha256":s.digest(s.ROOT/"CONFIRMATION_ENDPOINT_LOCK.json"),
            "stage_b_freeze_sha256":s.digest(s.ROOT/"STAGE_B_FREEZE.json"),
            "evaluator_sha256":s.digest(s.ROOT/"evaluate_confirmation.py"),
            "readiness_summary_sha256":s.digest(s.ROOT/"local_readiness_results/summary.json"),
            "readiness_status":readiness["status"],"test_population_read":False,
            "required_next_action":"Root reviews locked endpoints and readiness, then independently writes EVALUATION_RELEASE.json if approved. This monitor cannot release or evaluate tests."})
        print("All confirmation endpoints audited; awaiting root one-time test release",flush=True)
    except BaseException as exc:
        s.write_json(output/"failure.json",{"utc":s.now(),"type":type(exc).__name__,"error":str(exc),"traceback":traceback.format_exc()})
        raise


if __name__=="__main__":
    main()
