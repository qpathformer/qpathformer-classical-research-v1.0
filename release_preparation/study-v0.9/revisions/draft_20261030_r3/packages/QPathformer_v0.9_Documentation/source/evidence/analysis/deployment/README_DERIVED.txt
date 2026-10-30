Q-Pathformer v0.9 derived work: prepared, NOT authorized to execute.

Entry points with preserved scientific interpreter, -B -X utf8:
  analysis/deployment/producer.py --authorization RELEASE --output NEW_OUTPUT
  analysis/reproduction/run.py --authorization RELEASE --output NEW_OUTPUT
  analysis/deployment/timing.py --authorization RELEASE --output NEW_OUTPUT

Each release schema qpath-v09-derived-release-1 requires review_status approved_by_root,
phase conversion/reproduction/timing, exact output, test_access_authorized true,
required_blas_threads=1 and max_parallel_tasks=1. source_sha256 is support.sources()
for conversion/timing and reproduction.run.sources() for reproduction. protocols
bind DEPLOYMENT_PROTOCOL.json, REPRODUCTION_PROTOCOL.json and RUN_MATRIX.json.
Also bind evaluation_release, evaluation_commit, independent_score_replay (PASS,
636 endpoints, exact author_evaluation_commit binding), and runtime_environment.
The replay receipt uses canonical author_evaluation_commit; a legacy evaluation_commit
alias is optional but must agree. Both the independent analysis receipt and its
commit schema are accepted. Full B636 gate is reused.

Reproduction additionally binds original training_authorization. It copies exact
frozen sources/data/protocols to a clean directory and never copies checkpoints.
Four fresh child processes run serially, each with a child-owned7200s watchdog.
All curves, parameters, samplers, selected rounds and pipeline predictions compare.
This is implementation replay, not four new independent statistical replicates.

Timing additionally requires stage=timing, session1/2/3, confirmation_audit binding,
conversion_commit and reproduction_commit. independent_conversion_replay and
independent_reproduction_replay each require PASS and exact derived_commit binding.
All phases take an ETEL exclusive auxiliary/timing lease. Previous completed
same-phase/session work cannot be repeated. A failed attempt is retained and needs
root recovery.review_status=approved_by_root and prior_attempts exact binding list.

Conversion retains geometric policy, learned affine correction and residual terms;
only five two-layer circuit bank cores become25-term real trigonometric tables.
Dense probability mixtures do not become a single global25-term polynomial.
Checks cover257 off-grid points,30 clipped pair-midpoint/normal probes, all forced
banks, full validation and released test pipelines; maximum probability1e-10 and
zero changed classes. Independent Laurent coefficient checks remain separate.

Timing has636 original plus276 converted representations,3batches,15calls and2warmups
per condition, separately in3fresh serial sessions. Raw Banknote4-feature preprocessing,
routers, gates and residuals are recomputed within every timed call. No input cache.
A population's deployment_order stream plus session controls reproducible interleaving;
original/converted order alternates by session+block. Banknote1024rows cycle frozen
validation rows, not additional cases. Raw per-call wall/CPU nanoseconds are retained.
Managed work is excluded; unrelated OS activity remains uncontrolled.

Gate API: analysis/author/release_gate_v09.verify_completed_evaluation. End-of-phase
sources/protocols/data/selected checkpoint bindings are rechecked before commit.
DERIVED_COMMIT.json binds all output files. No official phase was run during preparation.
READINESS_v02.json lists nine passing synthetic tests and independent analytic Laurent qualification. Final independent source review and official post-release replay remain required.
