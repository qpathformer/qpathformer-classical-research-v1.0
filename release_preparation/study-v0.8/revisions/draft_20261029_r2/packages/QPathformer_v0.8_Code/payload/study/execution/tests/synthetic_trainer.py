"""Deterministic file-writing child fixture. No numerical model or real data."""
import argparse
import hashlib
import json
from pathlib import Path
import time

parser = argparse.ArgumentParser()
parser.add_argument("--job-id", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--authorization", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent
authorization = json.loads(Path(args.authorization).read_text())
matrix = json.loads((root/"matrix.json").read_text())
job = next(x for x in matrix["runs"] if x["run_id"] == args.job_id)
output = Path(args.output)
output.mkdir(exist_ok=False)
counter = root/"invocations.jsonl"
with counter.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"job_id": args.job_id, "output": str(output)})+"\n")
    stream.flush()
action = job.get("fixture_action", "success")
if action == "sleep":
    time.sleep(job.get("fixture_sleep_seconds", 1.5))
if action == "nonzero":
    (output/"partial.txt").write_text("preserved")
    raise SystemExit(19)
if action == "fail_once" and len(counter.read_text().splitlines()) == 1:
    (output/"partial.txt").write_text("preserved")
    raise SystemExit(21)
result = {"status": "completed", "completed_rounds": job["rounds"], "optimizer_global_updates": job["updates"],
          "test_accessed": False}
(output/"result.json").write_text(json.dumps(result))
(output/"config.json").write_text(json.dumps({"test_accessed": False, "fixture": True}))
(output/"prediction.txt").write_text("fixed reproducible synthetic value")
files = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
         for p in output.iterdir()}
commit = {"status": "completed", "job_id": job["run_id"], "arm": job["arm"], "seed": job["training_seed_id"],
          "stage": {"development": "A", "confirmation": "B"}.get(job["stage"], job["stage"]),
          "population": job["population_id"], "test_accessed": False,
          "authorization_sha256": hashlib.sha256(Path(args.authorization).read_bytes()).hexdigest(), "files": files}
(output/"endpoint_commit.json").write_text(json.dumps(commit))
