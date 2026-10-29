"""Bounded preflight of synthetic timing evidence; records activity CPU and UTC."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time
import unittest

parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True)
args = parser.parse_args()
started = datetime.now(timezone.utc).isoformat()
wall, cpu = time.perf_counter(), time.process_time()
stream = io.StringIO()
suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_timing.py")
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
import audit_timing
receipt = {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun,
           "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
           "wall_seconds": time.perf_counter()-wall, "process_cpu_seconds": time.process_time()-cpu,
           "scope": "Synthetic timing values and active matrix/protocol metadata only. No official outcomes, timing measurements or archived timing sessions read.",
           "sources": audit_timing.source_hashes(), "log": stream.getvalue()}
with Path(args.output).open("x", encoding="utf-8") as output:
    json.dump(receipt, output, indent=2, allow_nan=False)
    output.write("\n")
print(json.dumps({k: v for k, v in receipt.items() if k not in ("sources", "log")}, indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
