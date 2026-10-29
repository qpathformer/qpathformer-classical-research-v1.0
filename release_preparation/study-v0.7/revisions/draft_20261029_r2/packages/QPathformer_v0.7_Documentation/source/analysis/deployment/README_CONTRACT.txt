Q-Pathformer v0.7 derived deployment and finite-shot producers
INTERNAL. No official arrays or learned outcomes were read during implementation.

Authority and immutable scope
-----------------------------
The frozen scientific trainers, data, routers, budgets and endpoint selection are
unchanged. These producers derive representations and diagnostics from the exact
validation-selected B checkpoints after all512 B endpoints have been committed,
both audited, released by root, officially scored and committed.

The implementation is six modules plus its one test file as enumerated by
support.SOURCE_FILES (compiler, joint, fixtures, support, producer, timing, tests).
Registration binds their SHA256 digests, the active matrix and both protocols.
The exact12800 multinomial streams are frozen in the registration before scoring.
Registration alone authorizes no numerical work or test access.

Runtime: C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe -B
NumPy2.5.4 and the registered historical OpenBLAS build; all six numerical thread
environment variables are1 before NumPy imports, and actual OpenBLAS threads are
read back as1. No interpreter/environment installation or mutation is performed.

Source registration (metadata only)
-----------------------------------
Run from the study root:
  python -B analysis/deployment/producer.py --root "<study-root>"
    --phase registration --output "<study-root>/analysis/deployment/REGISTRATION_v01.json"
This refuses an existing output file. Do not replace a versioned registration;
if an implementation issue is found before official use, preserve it and produce
a new reviewed registration, documenting the change. No completed official
derived phase may be repeated without a documented root recovery authorization.

Strict phase authorization
--------------------------
Root writes a new JSON authorization with:
  schema: "qpath-v07-deployment-release-1"
  review_status: "approved_by_root"
  phase: "conversion" or "shots" or "timing"
  output: absolute NEW directory below <study-root>/analysis
  test_access_authorized: true
  max_parallel_tasks: 1
  required_blas_threads: 1
  registration: {path,sha256,bytes}
  evaluation_release: {path,sha256,bytes}
  evaluation_commit: {path,sha256,bytes}
Each binding is an absolute existing file with exact bytes and SHA256.

support.verify first checks this authorization and registration, then invokes
official/gate.verify_completed_evaluation. That gate rechecks original root
release, source/data/execution freezes, both512 endpoint audits and every endpoint
payload, followed by all official evaluation output files and its commit. It
does not merely trust an existing directory. All consumed checkpoints, policies,
data and canonical predictions are checked again when loaded.

Conversion and shot commands
----------------------------
  python -B analysis/deployment/producer.py --root "<study-root>"
    --phase conversion --authorization "<root-conversion-authorization>"
    --output "<new-conversion-output>"
  python -B analysis/deployment/producer.py --root "<study-root>"
    --phase shots --authorization "<root-shots-authorization>"
    --output "<new-shots-output>"
Both acquire their own exclusive ETEL auxiliary lease for the full phase.
They cannot overlap live/pending training or isolated timing. Phase errors write
FAILURE.json and preserve every payload. No in-place resume/overwrite is allowed.

Conversion output contract
--------------------------
CONVERSION_COMMIT.json schema qpath-v07-conversion-commit-1, status completed,
authorization/registration/evaluation_commit bindings, exact files map
{relative:{sha256,bytes}}. summary.json PASS requires192 circuit conversions and
256 same-checkpoint learned-Trig transforms, totaling448 representations.
endpoint_index.json gives job_id,arm,conversion-record binding,representation binding.

endpoints/{run_id}/:
  representation.npz: coefficients[5,25] for circuits/routed Trig, [1,25]
    for TrigG25, [1,121] for TrigG121. Circuit files also retain grid[25,2],
    bank{0..4}_grid_moments[25,1or5], bank{0..4}_grid_logits[25].
  validation_parity.npz and test_parity.npz:
    record_ids, original_probability, original_logits, transformed_probability,
    transformed_logits, decision_disagreement; all1600 records retained.
  fixture_parity.npz:
    x,offgrid_count,original_probability,original_logits,transformed_probability,
    transformed_logits, plus route for routed models and bank{0..4}_* for all
    forced-bank probabilities/logits.
  conversion.json: identity, load/source bindings, all parity maxima and every
    disagreement, coefficient bytes, original bytes, NPZ bytes, one instrumented
    construction time, boundary geometry metadata.

Coefficient ordering: real tensor basis x0-major, row-major x1:
  [1,cos(pi*x),sin(pi*x),cos(2*pi*x),sin(2*pi*x)].
TrigG121 extends each axis through frequency5. Conversion is exact orthogonal
projection on25 construction nodes with analytic norms, not learned regression.
It fits no labels and has no claimed accuracy improvement. Original probability
and class outputs remain canonical. Probability parity tolerance2e-12, logit1e-9.
Class differences are all retained and allowed only if both probabilities lie
within32float64eps of0.5. This decision band is distinct from numerical error.

Shot output contract
--------------------
SHOTS_COMMIT.json uses the analogous qpath-v07-shots-commit-1 schema.
summary.json PASS requires192 checkpoints,6144 checkpoint-input pairs,
12800 joint-count arrays,409600 four-outcome vectors,245760 scalar probabilities,
and1,132,462,080 represented measurement outcomes. No physical shots/Aer/cloud.
The32 fixture records are lowest numeric validation IDs, sorted ascending;
no labels, class balancing, margin selection or model-dependent selection.

endpoints/{run_id}/:
  ideal_fixture.npz:
    x[32,2],record_ids[32],route[32],heads[32,2or6],
    probabilities[32],logits[32],moments[32,1or5],joint_XX[32,4],
    and joint_ZZ[32,4] for multi-moment models.
  joint_counts.npz:
    N{1024|8192}_r{00..19}_{XX|ZZ}, each int64[32,4].
    Scalar has40 arrays, multi80. Outcomeorder00,01,10,11.
  shot_predictions.npz:
    total_budgets[2],technical_seed_ids[20],record_ids[32],
    probabilities[2,20,32],logits[2,20,32],moments[2,20,32,1or5].
  diagnostics.json: identity/source bindings, own-ideal parity, per-budget raw
    probability MAE/MSE/signed bias/bias-squared/technical variance(ddof0),
    every per-record moment, decision disagreements, head L1/L2, exact
    joint-covariance logit variance, observed logit variance and labelled
    first-order delta approximation. Technical repeats do not increase model n.

XX rotates both qubits with H and ZZ uses computational probabilities.
Signs for q0,q1,q0q1 are[1,1,-1,-1],[1,-1,1,-1],[1,-1,-1,1].
Moment order isX0,X1,Z0,Z1,Z0Z1; scalar usesX0.
Scalar spends totalN onXX; multi spendsN/2 each onXX/ZZ. A single multinomial
draw per setting/input preserves joint within-setting covariance.
Stream ASCII and PCG64 derivation are exactly LOCAL_READINESS_PROTOCOL.json.

Three fresh isolated timing sessions
-----------------------------------
Additional root authorization fields:
  stage: "timing"
  session: 1,2,or3
  confirmation_audit: hash binding to PASS B audit of512 endpoints
  conversion_commit: binding to completed CONVERSION_COMMIT.json
  independent_conversion_audit: binding to independent conversion summary.json
  independent_conversion_commit: binding to its INDEPENDENT_DEPLOYMENT_COMMIT.json
  previous_session_commits: [] for1; [session1commit] for2;
    [session1commit,session2commit] for3.
All previous sessions must share the exact registration and evaluation commit.
The independent commit must have schema qpath-v07-independent-deployment-commit-1,
status completed and a fully verified exact files inventory. Its bound summary
must be PASS,phase conversion,circuit_endpoints192,representations_replayed448,
learned_trig_exact_repacks256 and refer to this exact conversion_commit.
Each session must have a distinct process creation identity; root invokes three
separate Python processes and lets each finish before launching the next.
  python -B analysis/deployment/timing.py --root "<study-root>"
    --authorization "<root-session-authorization>" --session 1
    --output "<new-timing-session-output>"

Each session holds durable.timing_lease for its entire work. It times512 native
selected predictors plus192 converted circuits at batches1,32,1024:2112 conditions.
Each condition has2 warmups and15 timed trials, ONE complete forward call/trial.
Totals/session:31680 timed+4224 warmups; three sessions95040+12672.
Fixture batches use first1/32/1024 ascending validation IDs. Raw input routing,
features/core, head and sigmoid are inside the wall timer. Learned Trig uses the
same shared feature kernel as converted circuits; it is the same checkpoint.
No model or input feature/route caching is allowed inside this raw-input contract.
Resident parameter tables are allowed and explicitly separated from loading.
Interleaved population/family/seed/model blocks use registered deployment_order
streams; original/converted pair order alternates by session+trial parity.

trials.csv retains exact per-call nanoseconds, condition identity and trial order;
conditions.json retains medians/ranges/p10/p90 and first5/last5 drift summaries;
matched_ratios.json retains paired ratios/savings and construction-only break-even
when per-call saving is positive. Components and loading are separately
instrumented outside primary timers, and are not additive primary latency.
START/summary retain high-resolution clock, actual BLAS/build/thread state,
process creation identity, CPU/resident/peak statistics, system available RAM and
memory load. population_memory_snapshots.json retains32 further availability
samples, outside primary timers. External OS scheduling is not controlled.

Timing outputs end in TIMING_COMMIT.json, qpath-v07-timing-commit-1.
Independent coefficient, prediction/count and timing-coverage replay remains
required before report delivery. A producer PASS does not replace independent
verification or prove quantum hardware performance.
