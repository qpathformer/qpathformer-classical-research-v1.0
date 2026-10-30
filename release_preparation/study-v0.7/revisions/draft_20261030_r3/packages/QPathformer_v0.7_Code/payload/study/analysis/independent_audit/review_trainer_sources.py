"""Independent prelaunch implementation review receipt, using synthetic fixtures."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import io
import json
import unittest
import numpy as np
import test_independent_audit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1];Q=ROOT/"quantum"
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))

matrix=load(ROOT/"governance/RUN_MATRIX.json")
sources=("models.py","study.py","circuits.py","reference_v03.py","prepare_data.py","routers.py","tests/test_v07_science.py")
before={n:sha(Q/n) for n in sources}
stream=io.StringIO()
suite=unittest.defaultTestLoader.loadTestsFromModule(test_independent_audit)
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
audit=test_independent_audit.audit
seen=set()
counts={}
for row in matrix["runs"]:
    if row["run_id"] in seen:raise RuntimeError("Duplicate run ID")
    seen.add(row["run_id"])
    method=audit.ARM_METHODS[row["arm"]]
    expected_rounds=2 if row["stage"]=="engineering" else 200
    if row["rounds"]!=expected_rounds or row["updates"]!=75*expected_rounds or row["batch_size"]!=64:
        raise RuntimeError("Independent budget mismatch")
    counts[row["stage"]]=counts.get(row["stage"],0)+1
    for item in row["paired_streams"].values():
        derived=int.from_bytes(hashlib.sha256(item["namespace"].encode("ascii")).digest()[:16],"little")
        if derived!=int(item["uint128_decimal"]):raise RuntimeError("Stream mismatch")
if counts!={"engineering":32,"A":64,"B":512}:raise RuntimeError("Stage counts differ")
if before!={n:sha(Q/n) for n in sources}:raise RuntimeError("Source changed during review")
status="PASS_INDEPENDENT_TRAINER_SOURCE_AND_NUMERICAL_PREFLIGHT" if result.wasSuccessful() else "FAIL"
receipt={
    "status":status,"created_utc":datetime.now(timezone.utc).isoformat(),
    "scope":"Independent source review and synthetic numerical tests, before official model endpoints; not stage completion.",
    "scientific_source_sha256":before,
    "audit_source_sha256":{p.name:sha(p) for p in (HERE/"audit_endpoints_v07.py",HERE/"reference_v07.py",HERE/"test_independent_audit.py")},
    "matrix_sha256":sha(ROOT/"governance/RUN_MATRIX.json"),"stage_job_counts":counts,
    "synthetic_tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"numpy_version":np.__version__,
    "test_log":stream.getvalue(),"model_test_outcomes_accessed":False,
    "reviewed_science":[
        "Eight arms and exact trainable widths 50,70,70,125,125,25,121,129; five banks for routed arms, one for global arms.",
        "Independent tensor-matrix and scalar-gate circuit calculations; all eight production forward/logit and analytic gradients agree with independent five-point native-loss derivatives on fixed synthetic inputs.",
        "Parameter initialization reconstructed from explicit registered circuit and MLP uint128 streams; paired core retained across scalar/multi/hash circuit arms.",
        "Stable native logit BCE training; clipped common validation BCE alone selects strict earliest minimum; full registered budget continues after selection.",
        "Hash and kmeans routing use raw coordinates and training-fitted fixed policies; observed labels alone train; sealed test/latent diagnostics not loadable by trainer.",
        "All round parameters/probabilities/logits/native losses/orders flushed before ledger; selected and last states retained with full optimizer counter.",
        "Packed Adam updates all banks at each global step; zero-gradient absent banks may still move under accumulated momentum; bank absence/exposure diagnostics retained.",
        "No inference timing inside training; preparation cache charges and circuit/feature operations separately recorded."
    ],
    "resolved_findings":[{
        "finding":"Trainer STAGE_MAP originally lacked active matrix A/B identities.",
        "resolution":"Author added A/B identity aliases and complete 608-row identity/budget test before freeze or launch.",
        "current_status":"RESOLVED"}],
    "limitations":[
        "Legacy/frozen helpers remain unreachable through the registered METHODS whitelist.",
        "Endpoint auditor replays every saved validation round, initialization and sampling orders; it does not independently retrain every optimizer update.",
        "Synthetic gradient fixture avoids nondifferentiable ReLU kinks; no universal equivalence proof across arbitrary models is claimed."
    ]
}
path=HERE/"INDEPENDENT_TRAINER_PREFLIGHT.json"
with path.open("x",encoding="utf-8") as f:json.dump(receipt,f,indent=2,allow_nan=False)
print(json.dumps({"status":status,"tests":result.testsRun,"receipt":str(path),"sha256":sha(path)}))
if not result.wasSuccessful():raise SystemExit(1)
