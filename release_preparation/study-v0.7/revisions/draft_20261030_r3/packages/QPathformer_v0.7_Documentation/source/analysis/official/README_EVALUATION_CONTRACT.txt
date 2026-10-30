Q-Pathformer v0.7 official evaluation contract (internal)

No official test arrays or test model outcomes were read during implementation.
Scientific source and execution source are imported only for released scoring,
never changed by this evaluator. Metrics/statistics tests use synthetic arrays.

1. Source preparation before any test access
   python -B analysis/official/gate.py --root ROOT --freeze-output NEW_JSON
   This creates qpath-v07-evaluator-source-freeze-1, not an authorization.
   Root reviews and binds its SHA. It snapshots five evaluator/test files,
   seven scientific files and eight execution/vendor files, plus the three
   active protocols. A changed source requires explicit new pre-release review.

2. Root EVALUATION_RELEASE.json schema
   {
     "schema": "qpath-v07-test-release-1",
     "review_status": "approved_by_root",
     "stage": "B",
     "test_access_authorized": true,
     "all_confirmation_endpoints_independently_audited": true,
     "run_ids": [all 512 B IDs in exact RUN_MATRIX order],
     "evaluation_output": "absolute new path under ROOT/analysis",
     "analysis_protocol": binding of governance/ANALYSIS_PROTOCOL.json,
     "study_plan": binding of governance/STUDY_PLAN.json,
     "run_matrix": binding of governance/RUN_MATRIX.json,
     "data_seal": binding of quantum/data/DATA_SEAL.json,
     "runtime_environment": binding of execution/RESOURCE_ENVIRONMENT_CHECK.json
                            or root-reviewed equivalent with same keys,
     "evaluator_freeze": binding of source snapshot from step 1,
     "author_audit": binding of author B endpoint audit,
     "independent_audit": binding of independently produced B audit
   }
   A binding is {"path": absolute file, "sha256": SHA256, "bytes": integer}.
   Audit format: status PASS, stage B, verified_endpoints 512,
   endpoints [{job_id, commit: binding(endpoint_commit.json)}].
   Both audits must bind the identical 512 selected attempts, be distinct files
   with distinct hashes, and match exact matrix IDs, budgets and durable requests.
   The gate rehashes every endpoint payload and verifies current source/data/
   protocol bindings, not merely receipt counts. Root attests the independent
   reviewer role; separate receipt paths alone do not prove human independence.

3. Run only after release
   C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe -B -X utf8
     analysis/official/evaluate.py --root ROOT --release RELEASE --output OUTPUT
   Uses CPU only, one effective OpenBLAS thread, NumPy2.5.4/SciPy1.18.1.
   Takes the execution auxiliary audit lease, excluding training and timing.
   Never overwrites output. Failed/partial evaluations retain failure and
   progress evidence; a root-documented fresh attempt is needed for recovery.
   No per-arm stop, endpoint pruning, test-based reselection or retuning exists.

4. Retained output
   Per endpoint: validation/test NPZ containing record IDs, source draw IDs,
   observed labels, probabilities, native logits, threshold predictions,
   both cached routes and frozen geometric-margin bin.
   Per-endpoint metrics JSON: clipped and native BCE, F1, accuracy, raw Brier,
   fixed-bin ECE10/reliability, positive precision/recall and grouped-tie AP,
   clipping/extreme logit diagnostics, all bank/margin slices including empty
   bins, train-selected heads/coefficient norms, full-horizon bank exposure,
   absent-bank packed-Adam movement, training CPU/wall accounting, validation
   90/95/97 first observed crossing or right censor at15000 updates.
   Undefined precision/recall/AP is null, not zero; class F1 zero-denominator
   uses the inherited zero convention. AP averages precision at each distinct
   score group's endpoint, so tied example ordering cannot change its result.
   Route timers are single audit calls, not deployment latency measurements.

   primary_analysis.json: all5contrasts x4tasks; each of8 population differences
   is mean(two paired seed differences). t interval df7, confidence99.75%,
   alpha .05/20. Negative favors first; practical reference BCE .01.
   descriptive_summary.json: population seed averages and reached-only milestone
   medians with explicit nonreacher counts. No historical pooling.
   diagnostic_summary.json: descriptive population SD/range for slice BCE/F1/
   prevalence; all empty/missing bins retained. Record SD/SE and Wilson95
   prevalence intervals are conditional descriptive summaries, not additional
   primary inferential tests or independent sample-size claims.
   summary.json and EVALUATION_COMMIT.json bind all output artifacts.

5. Required independent replay
   A different implementation must reconstruct predictions/native logits and
   statistics from the frozen checkpoint, exact raw inputs and router policy.
   This official evaluator's PASS only means scoring/serialization succeeded.
   It explicitly leaves independent replay REQUIRED before final findings.
   Neither official nor reference scoring authorizes physical quantum testing.

6. Downstream read-only release verification (root-approved pre-release refactor)
   gate.verify_completed_evaluation(root, release_path, evaluation_commit_binding)
   rechecks all original release/source/data/dual-audit/512-endpoint gates, then
   verifies the bound successful completed EVALUATION_COMMIT and every output
   payload, exact512 endpoint index and required prediction/metric evidence.
   Partial, failed, modified or extra-uncommitted output fails closed.
   This uses verify_release(..., require_new_output=False) only for the original
   release-bound official output. Ordinary evaluate.py retains the defaultTrue.
   Deployment/replay output requires its own separate bound root authorization.
