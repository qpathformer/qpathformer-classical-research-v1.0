"""Bounded synthetic review activity receipt, no official arrays or training."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import argparse
import io
import json
import os
import time
import unittest

parser=argparse.ArgumentParser()
parser.add_argument("--output",type=Path,required=True)
args=parser.parse_args()
for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","VECLIB_MAXIMUM_THREADS","BLIS_NUM_THREADS"):
    os.environ[key]="1"
started=datetime.now(timezone.utc).isoformat();wall=time.perf_counter();cpu=time.process_time()
import test_independent_audit
import test_statistics_v07
import test_replay_metrics_v07
import test_replay_evaluation_v07
import replay_evaluation_v07 as replay
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources={name:sha(HERE/name) for name in replay.SOURCES}
suite=unittest.TestSuite()
for module in (test_independent_audit,test_statistics_v07,test_replay_metrics_v07,test_replay_evaluation_v07):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
receipt={"status":"PASS" if result.wasSuccessful() else "FAIL","started_utc":started,
         "finished_utc":datetime.now(timezone.utc).isoformat(),"wall_seconds":time.perf_counter()-wall,
         "process_cpu_seconds":time.process_time()-cpu,"tests":result.testsRun,
         "failures":len(result.failures),"errors":len(result.errors),"source_sha256":sources,
         "official_data_or_outcomes_accessed":False,"training_performed":False,"log":log.getvalue()}
replay.write_new(args.output,receipt)
print(json.dumps({k:receipt[k] for k in ("status","tests","failures","errors","wall_seconds","process_cpu_seconds")}))
print(log.getvalue())
if not result.wasSuccessful():raise SystemExit(1)
