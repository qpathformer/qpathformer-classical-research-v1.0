Q-Pathformer v0.8 exact conversion and isolated inference preparation

STATUS: SOURCE PREPARATION, NOT RELEASE-READY
No official checkpoint, validation/test array, conversion or timing phase has
been read/run by this preparation. The current readiness_gates.py implements
the exact peer replay/reproduction contracts; final synthetic checks and
independent review are pending. No registration snapshot has been created.

SCOPE
Convert all 256 selected circuit predictors (MultiK_U/P, MultiHash_U/P)
to five banks of 25 real trigonometric logit coefficients, retaining the exact
router, affine head and sigmoid. Repack all 384 learned Trig predictors into
the same optimized feature kernel without fitting or checkpoint reselection.
Conversion is representation equivalence, not an accuracy improvement or
compression claim. There is no new shot, noise, Aer or hardware campaign.

COUNT CONTRACT
640 selected original predictors; 256 additional converted circuit forms.
896 timing representations; batch sizes 1,32,1024 => 2688 conditions/session.
Each condition has 2 warmups and 15 timed single raw-input forwards.
Per session: 5376 warmups,40320 timed trials,768 circuit/batch matched pairs.
Three sessions: 16128 warmups,120960 timed trials. Technical repeats/sessions
do not increase independent population n. Warmups have committed counters
and reviewed-loop provenance, not individually logged raw trial rows.

CURRENT SCIENTIFIC KERNELS
compiler.py: exact per-bank 25-node logit projection plus learned Trig repack.
fixtures.py: deterministic offgrid and geometric-boundary fixtures, all banks,
  parity tolerances and every near-threshold disagreement retained.
producer.py: full ordered 640-model conversion and parity artifact writer.
timing.py: exclusive fresh process, raw routing/features/head/sigmoid inside
  clock, resident parameters, paired order alternation, block interleaving,
  actual BLAS/runtime and available-memory telemetry.
support.py: source/protocol/evaluation/environment checks and full file commits.
readiness_gates.py: hash-only complete peer evidence/identity/source gates;
  exact independent score replay, reproduction and conversion contracts.

RELEASE CHAIN TO TEST AND REVIEW BEFORE REGISTRATION
Conversion requires complete official evaluation and independent score replay.
Timing also requires all four clean reproductions and independent reproduction
audit, plus independent conversion and every prior timing session commit.
Required agreed binding field names ({path,sha256,bytes}):
  independent_score_replay_commit
  reproduction_commit
  independent_reproduction_commit
  independent_reproduction_audit
  conversion_commit
  independent_conversion_commit
  independent_conversion_audit

Independent conversion must prove 640 matrix-ordered replay identities, all
1280 validation/test reference files, 256 algebraic circuit reconstructions,
384 learned-Trig repacks and exact producer/evaluation/source/authorization
chain. A PASS summary count alone is insufficient.

DRAFT PRODUCER COMMANDS (DO NOT INVOKE BEFORE GATES/REVIEW)
PY -B -X utf8 analysis/deployment/producer.py --root ROOT --phase registration
  --output ROOT/analysis/deployment/REGISTRATION_v01.json
PY -B -X utf8 analysis/deployment/producer.py --root ROOT --phase conversion
  --authorization ROOT/governance/CONVERSION_RELEASE_v01.json
  --output ROOT/analysis/deployment_results/conversion_v01
PY -B -X utf8 analysis/deployment/timing.py --root ROOT --session 1
  --authorization ROOT/governance/TIMING_SESSION1_RELEASE_v01.json
  --output ROOT/analysis/deployment_results/timing_session1_v01

ROOT is C:\Anthony Siljeg\Q2_improvement_study_v08.
PY is C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe.
All six numeric thread variables are1; PYTHONDONTWRITEBYTECODE=1 and -B.
Each invocation is a fresh process. Conversion owns auxiliary lease; timing
owns timing lease. No fit/audit/reproduction/support numerical work overlaps
the three separately root-released timing sessions.

CONVERSION ARTIFACTS
endpoint_index.json contains exact640 matrix-ordered job_id/arm rows.
Each endpoints/<run_id>/ directory contains representation.npz,
validation_parity.npz,test_parity.npz,fixture_parity.npz,conversion.json.
Each conversion record retains source checkpoint, parameter/coefficient bytes,
container bytes, single construction/load durations and all numerical errors
and decision disagreements. CONVERSION_COMMIT.json schema is
qpath-v08-conversion-commit-1, completed, authorization/registration/
evaluation_commit bindings and all relative files->{sha256,bytes}.

TIMING ARTIFACTS
trials.csv retains 40320 timed raw observations per session in exact order.
conditions.json has2688 summaries; matched_ratios.json has768 matched pairs.
components.json holds separate instrumented probes outside primary timing.
models_and_loading.json retains640 loading/representation records.
START.json/summary.json and population_memory_snapshots.json retain identity,
actual environment, clock, memory and scope. TIMING_COMMIT.json binds every
payload. Construction-only break-even is reported only for positive measured
matched saving; loading and storage are not silently included.

PREPARATION EVIDENCE
The earlier SYNTHETIC_PREPARATION_v01.log records11 tiny fixture checks.
Subsequent source-only work completed peer readiness gates, added the full
640/1280 reference inventory regression and removed an unreachable MLP branch.
Final gate integration requires new bounded synthetic checks and independent
review before registration; do not treat the earlier log as a current freeze.
At the next root-coordinated resource window, invoke the lease-owning wrapper:
PY -B -X utf8 analysis/deployment/synthetic_preflight.py
  --output ROOT/analysis/deployment/SYNTHETIC_PREFLIGHT_v03.json
  --log ROOT/analysis/deployment/SYNTHETIC_PREFLIGHT_v03.log
It fails immediately if a study/audit lease remains active; do not double-wrap.
The v03 handoff additionally binds all16 peer replay sources, including the
wrapper regression test_replay_wrapper_v08.py. Prior candidates are preserved.
