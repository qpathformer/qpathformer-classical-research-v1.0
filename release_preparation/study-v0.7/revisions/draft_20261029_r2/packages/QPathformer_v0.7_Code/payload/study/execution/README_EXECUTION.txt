Q-Path Multiplier (ETEL) — v0.7 execution integration
Internal. This layer does not change any scientific model, RNG stream or budget.

Components
- vendor/etel/core.py and __init__.py are unmodified ETEL 0.2.0 sources. The native
  untrained vector engine is not used. The logical 64-slot blocks remain bookkeeping.
- bind_stage.py produces a bound execution manifest. It never approves or runs it.
- launcher.py run requires both that manifest and a separate root execution release.
- worker.py executes one whole scientific fit in a child process. It commits its
  own PID plus kernel process-creation identity before loading the trainer through
  runpy in the same process. This eliminates a numerical-training launch/PID gap.
- execution/state/ledger.sqlite3 uses WAL, FULL synchronization and transactions for
  canonical job identities, immutable attempt references and append-only events.
- A kernel compute lease prevents concurrent coordinators. Parent loss releases
  the lease but does not erase claims or stop child watchdogs.
- The child records effective OpenBLAS identity/threads before training. Require
  the historical interpreter, NumPy version and DLL identity bound in the manifest.
- PROCESS_RESOURCES.json records whole-child CPU and kernel peak working set.
  CPU includes imports/preflight/watchdog through the sample; it is not model-only.

Root stage construction, after independent scientific/implementation review
1. Create the trainer's qpath-v07-stage-authorization-1 freeze for engineering, A or B.
   Exact run IDs come from governance/RUN_MATRIX.json. It and STUDY_PLAN.json are
   active authority; PROPOSED_* files remain preserved provenance.
2. Capture resource_probe.inspect() using the historical interpreter with all six
   numerical thread variables equal to 1. Save the JSON under governance.
3. Run bind_stage.py --root ROOT --stage STAGE --interpreter PYTHON
   --authorization FREEZE --max-parallel N --deadline-seconds 3600
   --environment ENVIRONMENT_JSON --output MANIFEST_JSON.
   The new manifest includes exact stage jobs, scientific and execution source
   hashes, data/router payloads, environment DLL and authorization hash.
4. Root creates a separate execution-release JSON:
   {
     "review_status": "approved_by_root",
     "stage": "engineering" | "A" | "B",
     "manifest_sha256": "<sha256 of exact bound manifest>",
     "predecessor_audit": {"path": "<absolute receipt>", "sha256": "...", "bytes": N}
   }
   predecessor_audit is required for A (32 engineering endpoints) and B (64 A
   endpoints). A passing audit must contain stage, verified_endpoints, status PASS,
   and endpoints [{job_id, commit:{path,sha256,bytes}}]. The gate rechecks exact
   matrix IDs, saved attempt recipes, complete budgets and all committed payloads.
5. Run PYTHON -B -X utf8 execution/launcher.py run --manifest MANIFEST --release RELEASE.
   Root may redirect console output; detailed stage observations are also written
   exclusively under execution/stage_reports. No endpoint may be overwritten.

Restart/recovery
- The same command reconciles live claims before admitting new work. Surviving
  processes are adopted first so restarting does not raise scientific concurrency.
- A launch-pending bootstrap may be submitted again, but a transactional compare-
  and-set permits only one bootstrap to enter scientific execution.
- Valid completed commits are verified and skipped. Altered completed evidence
  blocks continuation; it is never silently replaced.
- A dead recorded process with an incomplete endpoint becomes orphaned. Failure,
  interruption and timeout are preserved and do not automatically retry.
- For a reviewed fresh same-recipe attempt, root supplies:
   {review_status:"approved_by_root",job_id,previous_attempt_id,
    manifest_sha256,recipe_sha256,recovery_action:"fresh_same_recipe_attempt"}
  Then launcher.py recover --manifest ... --release ... --job-id ... --approval ...
  creates a distinct attempt. The old attempt remains. A repeated run command
  executes the new attempt. This is a full deterministic restart, not exact sampler
  or optimizer continuation. The original source, seed, data and complete budget
  remain fixed; consumed failed work is retained in accounting.
- launcher.py cancel --root ROOT --attempt ID --reason TEXT requests interruption.
  The child watchdog persists a terminal event and exits. Its deadline also works
  after parent loss. Hard exit preserves existing artifacts, but cannot promise
  that the most recent unflushed in-memory state becomes a resumable checkpoint.
- A kernel identity prevents PID reuse from being mistaken for a live owner.
  Ambiguous process inspection fails closed. No descendant process is permitted
  by the current scientific runner; future child-spawning extensions require a
  reviewed process-tree/job-object cleanup policy.

Other numerical phases and test release
- The fit adapter has no evaluation command; the trainer allows train/validation
  only. Root must release test scoring after all 512 B endpoints are independently
  audited under the frozen scientific evaluation protocol.
- Wrap complete audit/conversion/shot invocations in durable.auxiliary_lease(root,
  purpose) so they share the compute lock and cannot overlap timing.
- Wrap each entire timing session in durable.timing_lease(root, release). Timing
  release requires stage:"timing", review_status:"approved_by_root",
  max_parallel_tasks:1, required_blas_threads:1 and confirmation_audit binding.
  That audit must enumerate all 512 B commits. Timing refuses pending/live fits;
  the lease remains held throughout the session. All managed numerical work must
  obey these leases; this is not an OS-wide restriction on unrelated user programs.

Resource qualification suggestion
Use fixed representative engineering recipes at physical process caps 1, 2 and 5,
with identical source/data/streams and one effective BLAS thread. Include circuit
readouts, the widest trigonometric control and the MLP; preserve validation and
optimizer-state equivalence across concurrency settings. Perform any repetitions
as explicitly labelled qualification work, in distinct output/ledger identities,
not as replacement or additional official confirmation endpoints. Record startup,
throughput, per-process CPU, peak RSS and sustained host behavior. Select the cap
before A freeze; do not select by accuracy or shorten any scientific budget.
The logical number 64 provides no physical-capacity or speedup estimate.

Tests
PYTHON -B -X utf8 execution/tests/test_execution.py
The suite creates retained execution_test_* roots under execution/test_runs. It
uses only a stdlib synthetic file-writing child, never a scientific trainer.
The actual 608-row run matrix is read only for a non-executing 32/64/512 stage test.
Test fixtures include child-process parent loss/restart, simultaneous coordinators,
completion no-repeat, nonzero failure, independent watchdog timeout, cancellation,
fresh same-recipe recovery, altered inputs/commits and strict audit/timing gates.

Limits
This is a local single-host scheduler with static measured process caps. It is not
a distributed elastic provisioner, model-replication mechanism or speedup proof.
SQLite durability and process identity improve recovery; independent scientific
endpoint/selection/prediction audits still remain mandatory.
