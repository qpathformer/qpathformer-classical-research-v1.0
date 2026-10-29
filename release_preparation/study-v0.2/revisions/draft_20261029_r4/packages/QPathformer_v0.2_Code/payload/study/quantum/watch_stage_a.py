"""Persist Stage A health and audit/select only after every process completes.

This does not start Stage B or access a test population. Root remains the sole
approver of the next training stage and later test evaluation release.
"""
import os
for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[name]="1"
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
import qstudy as s


def main():
    watch=s.ROOT/"stage_A_watch"
    watch.mkdir(exist_ok=False)
    s.write_json(watch/"identity.json",{"pid":os.getpid(),"started_utc":s.now(),
                 "watcher_sha256":s.digest(__file__),"purpose":"Audit all 27 development endpoints then apply frozen selector; no Stage B launch or test access"})
    previous=None
    try:
        while True:
            statuses=[]
            for path in sorted((s.ROOT/"stage_A").glob("seed_*/*/status.json")):
                try:
                    statuses.append(s.read_json(path))
                except json.JSONDecodeError:
                    continue  # A concurrently written status will be read next time.
            completed=sum(r["status"]=="completed" for r in statuses)
            snapshot={"utc":s.now(),"completed":completed,"registered":27,"statuses":statuses}
            with (watch/"health.jsonl").open("a",encoding="utf-8") as handle:
                handle.write(json.dumps(snapshot)+"\n")
            if completed!=previous:
                print(f"{snapshot['utc']} Completed {completed}/27",flush=True)
                previous=completed
            status=s.ROOT/"stage_A/stage_status.json"
            if status.exists():
                stage=s.read_json(status)
                if stage["status"]!="completed" or completed!=27:
                    raise RuntimeError("Stage A ended with incomplete endpoints or failures; preserve for root review")
                break
            time.sleep(60)
        for script,artifact in (("audit_stage_a.py","STAGE_A_ENDPOINT_AUDIT.json"),
                                ("select_candidate.py","STAGE_A_SELECTION.json")):
            if (s.ROOT/artifact).exists():
                raise FileExistsError("Unexpected prior completion artifact; root must review instead of rerunning")
            command=[sys.executable,str(s.ROOT/script)]
            with (watch/(script+".log")).open("w",encoding="utf-8") as handle:
                child=subprocess.run(command,cwd=s.ROOT,stdout=handle,stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
            if child.returncode:
                raise RuntimeError(f"{script} failed; see preserved log")
        selection=s.read_json(s.ROOT/"STAGE_A_SELECTION.json")
        s.write_json(watch/"READY_FOR_STAGE_B_REVIEW.json",{
            "status":"Awaiting separate root Stage B freeze; no automatic Stage B launch",
            "created_utc":s.now(),"selected_candidate":selection["selected_candidate"],
            "development_promising_flag":selection["development_promising_flag"],
            "stage_b_methods":selection["proposed_stage_b_methods"],"stage_b_seeds":[401,402,403,404,405],
            "stage_a_audit_sha256":s.digest(s.ROOT/"STAGE_A_ENDPOINT_AUDIT.json"),
            "stage_a_selection_sha256":s.digest(s.ROOT/"STAGE_A_SELECTION.json"),
            "evaluation_registration_sha256":s.digest(s.ROOT/"EVALUATION_REGISTRATION.json"),
            "test_population_read":False})
        print("Stage A verified and selected; awaiting root Stage B review",flush=True)
    except BaseException as exc:
        s.write_json(watch/"failure.json",{"utc":s.now(),"type":type(exc).__name__,"error":str(exc),"traceback":traceback.format_exc()})
        raise


if __name__=="__main__":
    main()
