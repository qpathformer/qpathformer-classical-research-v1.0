Q-Path Multiplier (ETEL) - v0.9 Plan B execution integration
INTERNAL. This adapter executes whole fits. It does not implement the model router.

Stable and versioned components
- vendor/etel/core.py and __init__.py are unchanged ETEL 0.2.0 sources.
- process_identity.py and resource_probe.py are byte-identical to the v0.8 copies.
- durable.py, worker.py, launcher.py and bind_stage.py are the separately versioned
  v0.9 integration. Counts, schema names, safe draining and exact process-closure
  evidence differ; the scientific model, training budgets and ETEL core do not.
- The original v0.8 files, ledger, data and endpoints are never modified or reused.

Stage releases
1. Complete data/source/scientific qualification and independent review.
2. Root writes a qpath-v09-stage-authorization-1 for the exact matrix job IDs.
   Required fields: review_status approved_by_root; stage engineering, A or B;
   run_ids; matrix_sha256; protocol_sha256; data_seal_sha256;
   scientific_source_hashes. The trainer may require additional frozen settings.
3. Capture resource_probe.inspect() using the retained scientific interpreter,
   with OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS,
   NUMEXPR_NUM_THREADS, BLIS_NUM_THREADS and VECLIB_MAXIMUM_THREADS all set to 1.
4. Run bind_stage.py --root ROOT --stage STAGE --interpreter PYTHON
   --authorization FREEZE --max-parallel N --deadline-seconds SECONDS
   --environment ENVIRONMENT_JSON --output MANIFEST_JSON.
   Use at most five processes; deadline must equal the active study protocol.
5. Root reviews the resulting manifest and separately writes an execution release:
   {review_status:approved_by_root,stage:STAGE,manifest_sha256:HASH,
    predecessor_audit:{path:ABSOLUTE,sha256:HASH,bytes:N}}
   The predecessor audit is required for A (48 engineering endpoints) and
   B (72 development endpoints). Its status must be PASS and its endpoints must
   enumerate exact matrix identities and hash-bound complete commits.
6. Run PYTHON -B -X utf8 execution/launcher.py run --manifest MANIFEST --release RELEASE.
   This invocation releases only one stage, never the next stage or test scoring.

Official counts and budgets
- Engineering: 48 fits, each 20 rounds / 1,500 updates.
- Development A: 72 fits, each 200 rounds / 15,000 updates.
- Confirmation B: 636 fits, each 200 rounds / 15,000 updates.
- The four later clean retrains use distinct identities and a separate approved
  reproduction workflow. They are not members of the official 756-job ledger.

Durability and recovery
- SQLite WAL with FULL synchronization stores canonical jobs, immutable attempt
  references, process ownership, controls and append-only events.
- One kernel compute lease excludes concurrent coordinators. Surviving workers
  are adopted first after parent loss. A worker claims ownership transactionally
  before loading scientific code. Process creation identity is required, not PID alone.
- Completed commits are verified and skipped. Changed evidence fails closed.
- Interrupted, failed, timed-out and orphaned attempts remain preserved. There
  is no automatic retry or resumption of an optimizer/sampler checkpoint.
- Root may approve a new whole-fit attempt with identical recipe, data, source,
  seed and full budget. Required recovery JSON:
   {review_status:approved_by_root,job_id:ID,previous_attempt_id:ID,
    manifest_sha256:HASH,recipe_sha256:HASH,
    recovery_action:fresh_same_recipe_attempt}
  Use launcher.py recover --manifest ... --release ... --job-id ... --approval ...,
  followed by the same run command. Failed computation remains in cost accounting.
- launcher.py cancel --root ROOT --attempt ID --reason TEXT interrupts a fit;
  the watchdog preserves a terminal record and the artifacts already written.
  Prefer drain for a budget pause so no active fit is discarded.

Safe draining for a credit/usage pause
- launcher.py drain --root ROOT --reason TEXT records an immutable drain request
  and a transactional admission barrier. Active fits finish their full budgets;
  queued fits remain launch_pending. The child checks the barrier in the same
  transaction as scientific ownership, covering the parent/child launch race.
- The coordinator returns status drained and exit code 20 after active work ends.
  A drain survives parent loss and restart. It is never cleared automatically.
- Root must write a resume approval binding the active request and renewed usage
  review: {review_status:approved_by_root,action:resume_after_drain,
  drain_request:{path,sha256,bytes},usage_review:{path,sha256,bytes}}.
  launcher.py resume --root ROOT --approval APPROVAL clears only that exact drain;
  it does not launch anything. Then the same stage run command resumes pending fits.
- There is no OpenAI API call, credit polling or model invocation in the workers.
  Root governance owns the 30,000-credit ceiling and reserve policy. Pausing AI
  supervision can leave an already authorized local stage running; the separate
  drain mechanism is available when a controlled whole-fit stopping point is wanted.
- A credit pause never releases the next scientific stage, changes a recipe,
  reduces a budget, removes an arm or allows premature test access.

Status and process closure
- launcher.py status --root ROOT is a cheap read-only SQLite summary. It does not
  create a ledger, verify model files, reconcile workers or inspect test outcomes.
- Add --reconcile for explicit payload checking and dead-worker reconciliation.
- The adapter records PROCESS_CLOSED.json after native evidence shows the exact
  recorded worker has exited. A Windows venv bootstrap can have a different PID;
  its exit is never treated as proof that the scientific worker has exited.
- If a later PID owner is inaccessible (Win32 error 5), only the previously
  recorded exact creation identity, terminal hash and journal-bound closure proof
  may establish the old worker's absence. Unknown errors or missing/mismatched
  proofs fail closed. A currently live matching identity always blocks progress.
- Closure is recorded before later PID reuse; no privilege escalation, OS access
  bypass, service modification or replacement of process_identity.py is involved.
- Terminal workers still exiting block new stage admission. Closure waits are bounded.

Other phases
- Test scoring is absent from this adapter. It requires a separate root release
  after all 636 B endpoints have passed author and independent audits.
- Wrap full audits, conversions and reproduction work in durable.auxiliary_lease.
  Wrap each complete serial timing session in durable.timing_lease with an exact
  636-endpoint confirmation audit and max_parallel_tasks=required_blas_threads=1.
- These kernel leases exclude managed numerical work, not unrelated user programs.
- There is no finite-shot/noise/hardware phase in v0.9.

Qualification
PYTHON -B -X utf8 execution/tests/test_execution.py
The tests use isolated stdlib file-writing children, never a scientific trainer.
They test no-repeat, parent-loss adoption, process caps, cancellation, timeout,
failure recovery, exact gates, tamper rejection, persistent drain, root resume,
native closure, and matrix counts/budgets. Numerical qualification is separate.
All test directories and failed test observations are retained under test_runs.

Scope
This is bounded single-host scheduling, not distributed elastic provisioning or
a demonstrated model speedup. Native closure and durable commits support recovery;
they do not replace independent scientific audits, data checks or root stage review.
