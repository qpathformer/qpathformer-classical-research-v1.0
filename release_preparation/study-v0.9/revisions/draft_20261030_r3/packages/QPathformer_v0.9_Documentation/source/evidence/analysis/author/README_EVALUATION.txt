Q-Pathformer v0.9 Plan B author evaluation
INTERNAL. Implementation only until the complete confirmation release.

Entry point
  PYTHON -B -X utf8 analysis/author/evaluate_v09.py --root ROOT
      --release ROOT/governance/EVALUATION_RELEASE.json --output NEW_OUTPUT

There is no bypass or partial-stage scoring option. No official test model outcome
was used to develop or qualify these sources. test_author_v09.py constructs its
own numeric arrays and inert release fixtures under qualification_runs.

Required root evaluation release
  schema: qpath-v09-evaluation-release-1
  review_status: approved_by_root
  stage: B
  protocols: exactly four {path, sha256, bytes} bindings:
    study_plan -> governance/STUDY_PLAN.json
    run_matrix -> governance/RUN_MATRIX.json
    analysis_protocol -> governance/ANALYSIS_PROTOCOL.json
    data_seal -> quantum/data/DATA_SEAL.json
  scientific_source_hashes: the exact seven-file source map used by B
  evaluator_sources: relative filename -> SHA256 for the four Python files
    returned by release_gate_v09.evaluator_sources(ROOT)
  author_audit: binding of qpath-v09-author-stage-audit-1, PASS, stage B, 636
  independent_audit: binding of qpath-v09-independent-endpoint-audit-1,
    PASS, stage B, 636, binding that same author audit
  endpoints: complete 636-entry author endpoint map, with job_id, arm,
    population, seed, completed_rounds, optimizer_global_updates,
    selected_round, endpoint, commit binding and selected_checkpoint binding.

The root reviews the author plus independent endpoint audits and evaluator source
review before writing this release. A child implementation never self-authorizes.
The gate compares both audit maps and the root map, requires both audits to declare
no test outcome access and to bind the same complete B manifest, validates matrix identities,
full 200-round/15,000-update budgets, the stage B authorization, all frozen source
and protocol hashes, every committed endpoint payload, and selected checkpoints.
Only after this complete gate may the evaluator load sealed test inputs or labels.

API for downstream phases
  release_gate_v09.verify_release(root, release_path)
returns release, release_binding, jobs (636), endpoints (dict by job_id),
protocols (loaded dict), seal, scientific_source_hashes, endpoint_payloads_rehashed.
  verify_completed_evaluation(root, release_path, commit_binding)
also requires a completed 636-endpoint EVALUATION_COMMIT.json bound to the same
release and verifies its payloads. It adds evaluation_commit and its binding.
Both functions only read committed evidence and do not score any model.
Conversion, reproduction and timing need their separately approved releases and
independent acceptance. An author evaluation commit alone does not authorize them.

Computation and outputs
The whole evaluation holds the ETEL auxiliary audit lease, excluding managed
training/reproduction/conversion/timing. The preserved CPU runtime must match
Python 3.12.14 / NumPy 2.5.4 and measured OpenBLAS one thread.

Each endpoint keeps all train/validation/test probabilities, stable native logits,
IDs, labels, bank weights and expert logits in a compressed numeric archive.
It records common clipped BCE, stable native BCE, raw Brier and fixed-bin ECE,
two-class macro F1, accuracy, positive precision/recall, tied-probability average
precision, clipping, reliability tables and confusion matrices. The selected
validation probabilities must replay exactly; test data never select a checkpoint.

Class and fixed-geometric-bank/margin diagnostics use the same input geometry for
all arms. Empty slices report undefined values. Single-class slices keep both
registered classes in macro F1 and state that limitation. Selected gate entropy,
effective expert count, occupancy and class-conditional weighted expert losses
are descriptive. Postfit learned-gate argmax predictions are a diagnostic ablation,
not a newly trained model or selected winner. Annulus clean-label and flip-stratum
diagnostics are loaded only after release and aligned by IDs.

Historical training gate exposure is distinguished from selected-state weights.
Fixed gates use exact retained sampler visit counts. Learned gates replay only
their 12 coefficients through saved raw minibatch gradients and retained indices;
every round is checked against the retained parameters. The first 750 updates
remain frozen and the extra Adam clock starts at one on update 751. No experts are
trained again and no hidden-label routing is introduced. Weighted visit totals are
fractional gate mass, not counts of physical quantum executions.

The primary family has 12 common-BCE contrasts: C_L minus C_S, C_R and G121,
separately for each of four synthetic task families. Two paired seed differences
are averaged within each of eight independent populations. Student t intervals
use df 7 with Bonferroni family alpha .05. Upper bound below -.01 exceeds the
registered practical reference. Intervals including zero do not establish
equivalence. Secondary contrasts carry nominal 95% exploratory intervals.
Banknote's five optimizer seeds on one split are shown descriptively, with no
synthetic population confidence interval and no pooled headline score.

Validation first-observed F1 90/95/97 percent milestones retain never-reached
counts, update counts and elapsed time at round boundaries. They do not imply
early stopping or test performance. Cost inventory retains successful and failed
attempts, whole-child CPU, summed child elapsed occupancy and memory samples.
Present resource samples must match the durable worker PID/creation identity,
ownership journal event and the same attempt's terminal resource payload. Native
lifetime peaks are measured through that sample, normally after endpoint verification;
they are not training-only peaks or exact final-exit measurements.
Unknown costs after an unobserved crash remain unknown rather than zero.
Reproduction, conversion, audit and timing costs stay in their own phase receipts.

A fresh output directory is required. Failures retain a failure receipt and any
completed evidence. No automatic recovery, test-driven source modification or
reselection is provided. A corrected evaluator requires a reviewed new source
binding/root release and a new output directory. Final EVALUATION_COMMIT binds all
payloads; sources, consumed split and latent diagnostic data, routers and protocols
are checked again before committing.

Qualification
  PYTHON -B -X utf8 analysis/author/test_author_v09.py
Ten tests check hand-computed metrics and ties/tails, exact fixed-bin boundaries,
population-unit confidence intervals, all 12 models against the independent
oracle, historical gate exposure, full-release completeness, independent audit
test-access/manifest declarations, resource identity/terminal binding and payload tampering.
The first fixture failure was preserved in
governance/AUTHOR_EVALUATOR_QUALIFICATION_FAILURE_01.json. Its fixture used g*g
instead of the registered g**2 in Adam's float64 variance expression. Exact round
replay caught this expression-level rounding difference. Production code and
registered scientific sources were unchanged; the corrected fixture passed.
