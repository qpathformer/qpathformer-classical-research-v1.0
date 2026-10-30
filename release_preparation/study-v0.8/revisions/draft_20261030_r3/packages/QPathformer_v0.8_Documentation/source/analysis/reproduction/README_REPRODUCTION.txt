Q-Pathformer v0.8: four registered clean reproduction checks

STATUS
Source preparation only. No reproduction fit or official test access is
authorized by this document, a registration snapshot, or the synthetic tests.
The ten scientific arms and their nine frozen sources are unchanged.

PURPOSE
Recreate four populations and routers, then train four preselected endpoints
from initialization in a new directory. These checks establish repeatability
in the registered environment. They do not add independent populations,
increase the 640 confirmation endpoint count, or show hardware portability.

EXACT TARGETS, IN ORDER
B/B_checkerboard_01/seed_1601/MultiK_P
B/B_spiral_01/seed_1601/TrigK_P
B/B_annulus_01/seed_1601/MultiHash_U
B/B_disks_01/seed_1601/TrigG121_U

Each fit uses the unchanged 200-round/15,000-update recipe. Four fits are
serial: 800 complete rounds and 60,000 optimizer updates. The registered
numeric tolerances in governance/REPRODUCTION_PROTOCOL.json are unchanged.

RUNTIME AND ROOT
ROOT = C:\Anthony Siljeg\Q2_improvement_study_v08
PY = C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe
Invoke PY with -B -X utf8. PYTHONDONTWRITEBYTECODE=1 and all six numeric
thread variables are one before imports. The runner also sets them itself,
then checks the actual interpreter, NumPy and OpenBLAS against the released
environment. It claims the same exclusive auxiliary compute lease as audits.
No ETEL coordinator or timing process can overlap this phase.

SOURCE SNAPSHOT (metadata only, separate fresh output)
PY -B -X utf8 analysis/reproduction/run.py --root ROOT --phase registration
  --output ROOT/analysis/reproduction/REGISTRATION_v01.json

Root reviews this snapshot and creates a separate release. Its required fields:
schema: qpath-v08-reproduction-release-1
review_status: approved_by_root
phase: reproduction
test_access_authorized: true
max_parallel_tasks: 1
required_blas_threads: 1
run_ids: the exact four IDs above, in that order
output: a fresh absolute directory below ROOT/analysis
registration, evaluation_release, evaluation_commit, training_authorization:
  each is an exact {path, sha256, bytes} binding.

The training_authorization is the original complete B authorization. Completed
official evaluation must still pass its own full source, data, 640-endpoint,
author-audit, independent-audit and output-inventory checks. A source snapshot
is never an execution approval.

REGISTERED EXECUTION (only after root release)
PY -B -X utf8 analysis/reproduction/run.py --root ROOT --phase reproduce
  --authorization ROOT/governance/REPRODUCTION_RELEASE_v01.json
  --output ROOT/analysis/reproduction_results/reproduction_v01

The output must be absent. A root-local attempt registry records the fresh
process identity. A live attempt, completed reproduction or unexplained prior
incomplete attempt is rejected. Recovery never resumes partially trained
models: preserve evidence and use root-reviewed new output with exact prior
attempt bindings and a reason.

WHAT IS AND IS NOT COPIED
Copy nine scientific sources, STUDY_PLAN.json, RUN_MATRIX.json and the original
B training authorization byte-for-byte into output/clean. Recreate train,
validation, test and isolated latent arrays plus router policies from the
frozen streams; all arrays and complete NPZ/router bytes must agree with the
original seal. DATA_SEAL.json is copied as metadata only so the unchanged
trainer's source/data gate operates identically.

Historical and earlier v0.8 population coordinate arrays are read only to
reconstruct exact freshness exclusions. Original labels are not used for
regeneration. Original trained parameters/checkpoints are never copied into
the clean training root or used for initialization.

After each new full fit completes and commits, original endpoint payloads
are read to compare curves, selection, parameters and predictions. This
verification dependence on original reference evidence is distinct from
training initialization. The independent auditor separately compares
prediction traces and derives metrics; it does not rerun every model forward.
The official selected-model prediction replay covers the algebra independently.
The author's comparison is not a substitute for the independent audit.

OUTPUT CONTRACT
START.json: root release, registration, evaluation commit, actual environment,
  fresh process identity and attempt binding.
clean_source_inventory.json: original and copied paths/hashes for exact files.
clean/: copied sources/protocol metadata and recreated four populations.
data_recreation.json: original coordinate input bindings, generated payloads,
  router/latent hashes and newly measured preparation costs.
endpoints/<run_id>/: complete unchanged trainer endpoint payloads and commits.
fit_ledger.jsonl, endpoint_index.json: four exact fit identities and commits.
author_comparisons.json: 200-round parameter/curve/selection/sampler/prediction
  checks for each target; independent audit still separately required.
summary.json: schema qpath-v08-reproduction-summary-1, PASS, phase reproduction,
  count4, ordered run_ids, full_rounds800/full_updates60000, exact provenance,
  measured cost scope, original_checkpoints_copied:false.
REPRODUCTION_COMMIT.json: qpath-v08-reproduction-commit-1, completed, count4,
  ordered run_ids, authorization/registration/evaluation_commit bindings,
  files mapping every relative payload to {sha256, bytes}.

All input release/source bindings and both original/recreated committed
endpoint inventories are checked again before the final commit. Failures
retain partial artifacts and FAILURE.json. The phase never claims completion
from merely launching a fit.

COST INTERPRETATION
Whole-process resource samples include imports, verification, reconstruction,
fits, comparisons and writes through the sample time. Summary wall/CPU start
after initial release verification and attempt claim, so external invocation
timing must also be retained. Per-fit timers include author comparison and
associated payload verification. Historical preparation charges copied in
DATA_SEAL metadata are not new measured costs and must not be counted again.

DELIVERED PACKAGE AND REPLAY
See PACKAGE_REPLAY_GUIDE.txt. Preserve immutable absolute paths and hashes;
never rewrite source/protocol evidence to make a moved package appear to be
the original registered execution. The internal runner is deliberately
same-environment and same-root. No cross-machine portability claim is made.
