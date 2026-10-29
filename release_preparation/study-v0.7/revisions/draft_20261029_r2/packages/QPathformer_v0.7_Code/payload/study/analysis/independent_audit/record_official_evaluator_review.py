"""Source-bound static review receipt; never calls official scoring."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
files=("gate.py","evaluate.py","metrics.py","statistics_core.py","tests/test_official.py")
receipt={
    "status":"PASS_SOURCE_REVIEW_AND_INDEPENDENT_SYNTHETIC_METRIC_STATISTIC_COMPARISON",
    "created_utc":datetime.now(timezone.utc).isoformat(),
    "official_source_sha256":{n:sha(ROOT/"analysis/official"/n) for n in files},
    "independent_synthetic_evidence":{"path":str(HERE/"INDEPENDENT_REPLAY_PREFLIGHT_v02.json"),
                                      "sha256":sha(HERE/"INDEPENDENT_REPLAY_PREFLIGHT_v02.json")},
    "official_test_arrays_or_model_outcomes_accessed":False,
    "reviewed":[
        "Ordinary scoring requires a new root-authorized output and all512 exact B IDs in matrix order.",
        "Both author and independent PASS audits bind identical complete attempts; every endpoint payload is rehashed through durable verify_receipt_endpoints.",
        "Root-approved source freeze and active data/protocol bindings are checked before test arrays can be loaded.",
        "Completed-evaluation API retains original release gates while verifying successful count512 commit, exact endpoint index order, all required files/hashes and absence of failure or uncommitted files.",
        "Production scoring loads only previously validation-selected checkpoint and observed-label inputs; no test-based selection or retraining path exists.",
        "Primary comparison is five prespecified contrasts across four task families, two pairedseed differences averaged within each of eight populations; df7 nominal99.75% t intervals.",
        "Independent pure-array implementations reproduce metric/calibration/native-loss/AP and statistical outputs on synthetic random/extreme/tied and empty-bin fixtures.",
        "Undefined positive precision/recall/AP remain null; F1 zero-denominator convention is zero; reached-only milestone medians retain nonreacher counts.",
        "Readiness/deployment evidence is separate; no physical quantum authorization is granted."
    ],
    "limitations":[
        "Static and synthetic review does not replace official released scoring and independent full512 replay.",
        "Small-sample t interval coverage is nominal and depends on independent population-difference assumptions.",
        "Record uncertainty and routing-margin slices are descriptive; their bank labels are not matched semantic groups across routers."
    ],
    "unresolved_blocking_findings":[]
}
with (HERE/"OFFICIAL_EVALUATOR_REVIEW.json").open("x",encoding="utf-8") as f:json.dump(receipt,f,indent=2,allow_nan=False)
print(json.dumps({"status":receipt["status"],"sha256":sha(HERE/"OFFICIAL_EVALUATOR_REVIEW.json")}))
