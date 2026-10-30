Q-Pathformer v0.8 independent conversion and timing audit
Internal source preparation. No numerical phase is authorized by this file.

Conversion scope
256 validation-selected MultiK_U/P and MultiHash_U/P checkpoints are independently
converted by Laurent polynomial amplitude propagation, bra/ket convolution,
and an algebraic real-basis transform. This differs from the producer's
25-node orthogonal projection. Five banks,25 coefficients each,1000 float64
coefficient bytes per model; original Multi parameters are70*8=560 bytes.
Retaining both is1560 bytes before routers, metadata and containers.

384 learned TrigK_U/P, TrigHash_U/P and TrigG121_U/P coefficient tables are
independently checked as exact repacks, not additional trained models.
All640 representations are checked against validation and released test
predictions,1280 retained reference NPZs, fixed off-grid and geometric boundary
fixtures, every forced bank, and independently calculated immutable routes.
Conversion changes representation, not scientific selection or expected accuracy.

Numerical conventions retained from the preceding reviewed conversion
Coefficient maximum absolute tolerance2e-11, native logits1e-9,
probabilities2e-12; every threshold crossing retained. A crossing is allowed
only if BOTH probabilities lie within32 float64 eps of0.5. These conventions
are explicit in source before any official conversion is authorized.
No finite-shot, logical-noise, Aer or hardware campaign exists in this version.

Source preparation (metadata only)
PY -B -X utf8 analysis/independent_deployment/audit_artifacts.py
  --phase freeze --output ABS_NEW_SOURCE_FREEZE
PY -B -X utf8 analysis/independent_deployment/audit_timing.py
  --freeze --output ABS_NEW_TIMING_SOURCE_FREEZE
PY is C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe.
All six numerical thread variables are1. Numerical fixture tests are pending
the root-coordinated post-A window; no official derived outputs have been read.

Independent conversion release
schema qpath-v08-independent-deployment-release-1
review_status approved_by_root, phase conversion, test_access_authorized true,
max_parallel_tasks1, required_blas_threads1, output fresh under ROOT/analysis.
Bindings: source_freeze, evaluation_release, evaluation_commit,
producer_commit, independent_score_replay_commit.
Each binding is {path:absolute,sha256,bytes}.
Full640 author/independent B commits and completed official evaluation are
reverified through the existing completed-output gate. Independent score replay
must pass its exact640 endpoint/1280 reference/priority/statistics contract.
Producer conversion root approval, registration, all current sources/protocols,
every committed payload and all640 ordered endpoint identities are checked.

Invocation after root explicitly assigns the phase
PY -B -X utf8 analysis/independent_deployment/audit_artifacts.py
  --phase conversion --authorization ABS_RELEASE --output ABS_FRESH_OUTPUT
It owns one auxiliary audit lease. Do not double-wrap it. No overwrites, automatic
resumption or selective omissions. Failure evidence is preserved.

Conversion output
START.json, conversion_replay.json with640 ordered job_id/arm records and both
splits, predictions/<run_id>/{validation,test}_reference.npz (1280 files),
summary.json, INDEPENDENT_DEPLOYMENT_COMMIT.json.
Commit: qpath-v08-independent-deployment-commit-1, completed, phase conversion,
authorization binding and files map relative->{sha256,bytes}.
Summary PASS: representations_replayed640,circuit_endpoints256,
independent_circuit_coefficients256,learned_trig_exact_repacks384,
validation_and_test_probability_rows2048000,phase conversion,
authorization,producer_commit,conversion_commit, measured phase and process costs.

Timing audit
The auditor measures no model calls. It independently verifies all raw archived
trials from three fresh isolated processes and the complete root/commit/source
chain through score replay, conversion and four clean reproductions.
640 original predictors +256 converted representations =896 representations.
At batches1,32,1024:2688 conditions/session;15 timed trials and2 reported warmups
per condition. Three sessions yield120960 raw timed calls and16128 reported
warmups. The warmups have committed counters/reviewed loop provenance, not
individual retained warmup call records; they were not independently observed.

The audit reconstructs outcome-independent task/population blocks, seeded arm
ordering, alternating original/converted pair order,15-call inventories, linear
quantiles, first/last-five drift, paired savings/ratios, positive-saving-only
construction break-even, source/runtime/process identity and memory telemetry.
Construction/loading/component counters are single instrumented observations;
they are provenance checked, not independently remeasured or additive latencies.
Sessions collapse within models, then two seeds average within each population.
Technical trials and sessions do not add independent model/population n.

Independent timing release
schema qpath-v08-independent-timing-release-1, approved_by_root,
phase timing_evidence,timing_evidence_access_authorized true,
max_parallel_tasks1,required_blas_threads1,fresh output,source_freeze,
evaluation_release/evaluation_commit,independent_score_replay_commit,
conversion_commit,independent_conversion_commit,independent_conversion_audit,
reproduction_commit,independent_reproduction_commit,independent_reproduction_audit,
session_commits [three exact commits in session order].
PY -B -X utf8 analysis/independent_deployment/audit_timing.py
  --authorization ABS_RELEASE --output ABS_FRESH_OUTPUT
The audit owns an auxiliary audit lease and starts only after all timing has ended.
Output INDEPENDENT_TIMING_COMMIT.json uses qpath-v08-independent-timing-commit-1.
