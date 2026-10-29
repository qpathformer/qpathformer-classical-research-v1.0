Q-Pathformer v0.8 independent evaluation replay
Internal. Source preparation does not authorize any test or latent-data access.

Root authority
The existing governance/EVALUATION_RELEASE.json must use
schema qpath-v08-test-release-1, review_status approved_by_root, stage B,
test_access_authorized true, latent_diagnostics_authorized true and
all_confirmation_endpoints_independently_audited true.
It enumerates all 640 B run_ids in exact RUN_MATRIX.json order and binds:
analysis_protocol, study_plan, run_matrix, data_seal, runtime_environment,
evaluator_freeze, author_audit, independent_audit and independent_replay_freeze.
Every binding is {path:absolute,sha256,bytes}.

Independent replay additionally requires:
- independent_replay_freeze schema qpath-v08-independent-replay-source-freeze-1,
  exact current sources inventory named by replay_evaluation_v08.SOURCES and
  unchanged STUDY_PLAN/RUN_MATRIX/ANALYSIS_PROTOCOL bindings.
- independent_replay_output equal to the exact fresh requested output directory
  beneath this working root's analysis directory.
- evaluation_output equal to the completed official evaluation directory.
- distinct complete author/independent B audits, both naming the same 640
  current durable attempts and full 200-round/15000-update endpoint commits.
- completed qpath-v08-evaluation-commit-1 count640 with the exact recorded
  release, every hash-verified output and no failure/uncommitted file.

CLI after root explicitly assigns this numerical phase
C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe -B -X utf8 analysis\independent_audit\run_replay_leased.py --release ABS_RELEASE --output ABS_FRESH_OUTPUT --log ABS_FRESH_LOG
All six registered thread variables are 1. The wrapper owns its auxiliary audit
lease; do not double-wrap or overlap official training, other audits or timing.
It checks the effective historical scientific runtime. Numerical replay runs by
direct callable in that same lease-owning process, with stdout/stderr redirected
to an exclusive new log; there is no numerical child process. The PID is retained
in the log. Exceptions remain logged and propagate while the lease exits.
No automatic retry.

Successful output contract
REPLAY_COMMIT.json:
  schema: qpath-v08-independent-replay-commit-1
  status: completed
  count: 640
  run_ids: exact ordered matrix B IDs
  release: original root release binding
  official_evaluation_commit: exact official EVALUATION_COMMIT binding
  independent_replay_freeze: same binding from root release
  files: exact package-relative payload map {sha256,bytes}, excluding the
         commit itself; no self-reference and no extra uncommitted files.

summary.json:
  status PASS, replayed_endpoints640, reference_prediction_files1280,
  ordered_run_ids exact matrix order, primary_comparisons_replayed20,
  independent_populations_per_family8,
  priority_endpoint_diagnostics_replayed640,
  priority_round_diagnostics_replayed128000,
  priority_training_draws_reconstructed614400000,
  priority_family_arm_summaries_replayed40,
  descriptive_priority_effects_replayed20,
  release/official_evaluation_commit/independent_replay_freeze matching commit,
  seconds and process_cpu_seconds for this independent replay.

Other exact payloads:
- endpoint_replay.json: 640 rows, job_id exact matrix order. Each contains
  splits.validation and splits.test with prediction_binding, probability/logit
  parity errors, scalar checks, threshold diagnostics and recomputed BCE.
  priority_diagnostics records the completed per-endpoint exposure/curve checks.
- predictions/<run_id>/validation_reference.npz and test_reference.npz:
  exactly 1280 files, keys record_ids/probabilities/native_logits, each bound
  from the corresponding endpoint_replay row.
- independent_primary_analysis.json: all20 weighted contrasts, each with
  all8 population records and both paired seed components/differences.

Downstream acceptance
Verify the commit binding and full inventory; reject REPLAY_FAILURE.json.
Verify summary/commit root, source and official evaluation bindings agree.
Require exact640 unique ordered IDs and all1280 unique reference paths/hashes,
not just count fields. All20 contrasts and40/20 priority summaries must have
passed independent replay. Never infer success from a folder or process exit
without the committed evidence. Conversion/reproduction/timing retain their
separate root releases and independent audits.

Independent numerical implementation
The replay imports no producer model, score, statistic or priority module.
It uses the separate dense/scalar model oracle and independently reconstructed
raw-coordinate routing. It recomputes all saved-probability metrics, grouped AP,
class composition, reliability, bank and margin diagnostics; df7 critical values
come from an analytic density integral and bisection, not the official SciPy call.
Priority counts are reconstructed from every sampled record position, with
released latent flags aligned by training IDs. Learning curves are checked
against previously audited full ledgers; no training or checkpoint reselection.
Canonical metric calculations use committed probabilities after independent
prediction parity checks, preserving documented threshold-band sensitivity.

Preparation checks and timing separation
The initial16-test synthetic suite already passed in1.672s wall/1.03125s CPU,
2026-10-20T18:51:31.918895Z to18:51:33.590351Z. It completed before root's
subsequent hold on numerical preparation tests; the receipt and log are retained.
The peer-review wrapper correction is preserved in replay_prefreeze_history/
wrapper_lease_v01. New same-process mocked regression cases are prepared but
remain unexecuted while Stage A owns the compute lease.
Any source correction after peer review requires a fresh versioned test receipt
in the root-coordinated audit window, never concurrent with active training.
Pending rerun command if required:
python -B -X utf8 analysis\independent_audit\run_replay_preflight.py --version v02
No rerun is required solely to duplicate already-passing unchanged checks.
