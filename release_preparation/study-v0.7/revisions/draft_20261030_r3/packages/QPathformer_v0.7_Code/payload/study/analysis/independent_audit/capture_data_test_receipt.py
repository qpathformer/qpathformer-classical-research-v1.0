"""Record source-bound synthetic data tests without modifying registered sources."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import io
import json
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
Q=ROOT/"quantum"
sys.path.insert(0,str(Q));sys.path.insert(0,str(Q/"tests"))
import test_routers_data
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
names=("prepare_data.py","routers.py","tests/test_routers_data.py")
before={n:sha(Q/n) for n in names}
stream=io.StringIO()
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_routers_data))
if before!={n:sha(Q/n) for n in names}:raise RuntimeError("Source changed")
receipt={"status":"PASS" if result.wasSuccessful() else "FAIL",
         "created_utc":datetime.now(timezone.utc).isoformat(),
         "scope":"Synthetic data/router source checks only; no official generation or model training.",
         "source_sha256":before,"numpy_version":np.__version__,"tests_run":result.testsRun,
         "failures":len(result.failures),"errors":len(result.errors),"test_log":stream.getvalue(),
         "data_registration_sha256":sha(ROOT/"governance/DATA_REGISTRATION.json")}
path=ROOT/"governance/DATA_SOURCE_TEST_RECEIPT.json"
with path.open("x",encoding="utf-8") as f:json.dump(receipt,f,indent=2,allow_nan=False)
print(json.dumps({"status":receipt["status"],"tests":result.testsRun,"sha256":sha(path),"path":str(path)}))
if not result.wasSuccessful():raise SystemExit(1)
