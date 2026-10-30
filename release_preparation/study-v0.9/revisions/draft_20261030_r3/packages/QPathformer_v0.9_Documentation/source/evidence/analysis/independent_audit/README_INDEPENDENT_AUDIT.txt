Q-Pathformer v0.9 independent endpoint audit

The root invokes only after every endpoint of the stage is committed and the
author audit has passed. This tool does not launch training or evaluate test data.

Command (use the retained scientific Python, no installs):
python.exe -B analysis/independent_audit/audit_endpoints_v09.py --manifest PATH --author-audit PATH --authorization PATH --output NEW_PATH

Root audit authorization JSON:
  review_status: approved_by_root
  action: independent_endpoint_audit
  stage: engineering | A | B
  manifest: {path, sha256, bytes}
  author_audit: {path, sha256, bytes}
  independent_contract: {path, sha256, bytes}

The contract is INDEPENDENT_AUDIT_CONTRACT.json beside this document. It binds
the independent implementation, tests, numerical tolerances and qualification.
Stage counts are fixed 48 / 72 / 636. The official command takes an exclusive
ETEL auxiliary audit lease. Its output is exclusive-create and includes every
endpoint commit and selected checkpoint hash plus numerical error maxima.

Scope: all payload hashes, initial states, source/data/recipe bindings, uniform
draws, sampled indices, exposure, all Adam updates using retained gradients,
independent first/last minibatch gradient per round, all train/validation forward
predictions and metrics, strict earliest common validation-BCE selection, every
improvement checkpoint and final selection, optimizer states, operation counts,
and exact paired 750-update warmup trajectories through initial vectors and all
750 expert gradients. This is bounded independent verification, not independent
retraining of every gradient. No training source is imported by the auditor or
reference. Qualification tests import production code only for comparison.

Banknote uses dynamic sealed train/validation counts. Training remains 75 batches
of 64 draws per round regardless of sample count. All numerical audit tolerances
are implementation checks, not scientific effect thresholds. Threshold rounding
disagreements must be within 32 float64 eps of 0.5 on both implementations and
are retained in the receipt. Primary metric values use the producer's saved,
independently checked probabilities without reselecting on roundoff differences.

All pre-release qualification and failure evidence remains in test_runs/. Never
replace a contract or existing report after an official stage uses it. A required
repair must be recorded, versioned, independently checked and root approved.
