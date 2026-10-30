Independent v0.7 audit and replay
Internal; no cloud or physical quantum operations.

Completed engineering audit:
ENGINEERING_INDEPENDENT_AUDIT.json binds all32 exact registered attempts,
102400 independently replayed validation predictions, every saved round,
paired initialization/sample order, strict BCE selection and complete150updates.
This is not independent retraining of every optimizer update.

Stages A and B:
Use run_audit_leased.py --stage A|B --output NEW_RECEIPT --log NEW_LOG.
The wrapper acquires ETEL's auxiliary lease. The audit implementation itself
imports neither production models nor execution code and opens SQLite read-only.
It requires successful closed supervision and exact full64/512 endpoint sets.
Never rerun a completed audit merely to overwrite its receipt.

Independent evaluation source preparation:
replay_evaluation_v07.py --freeze --output NEW_SOURCE_FREEZE
This writes source hashes only. It cannot grant test access.

Future root EVALUATION_RELEASE.json must add independent_replay_freeze:
{"path": absolute source-freeze path, "sha256": exact SHA256, "bytes": size}
All official release fields remain required. Author and independent B audits
must enumerate and bind the identical512 complete attempts. A complete committed
official evaluation and its exact index/files are required before replay.

After all gates and official scoring, root invokes:
run_replay_leased.py --release ROOT_RELEASE --output NEW_REPLAY_DIR --log NEW_LOG
Use C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe -B -X utf8.
No source edits after the root-bound freeze; preserve any failed attempt.

Replay reconstructs routing from raw coordinates using a separate SHA256/struct
and centroid implementation, vector tensor-matrix predictions plus fixed scalar
spotchecks, native logits, all canonical saved-probability metrics, every bank/
margin slice, validation milestones, copied training costs, all20 primary
contrasts, population descriptive summaries and diagnostic population summaries.
Undefined ratios remain null. Every threshold disagreement within the registered
numeric band is retained; out-of-band disagreement fails.

The Student df7 critical value is independently inverted from its analytic
trigonometric CDF, not delegated to the official SciPy calculation. Synthetic
tests crosscheck it against SciPy and exercise paired populations, ties, empty
and collapsed diagnostic bins, extreme logits and incomplete release flags.

The numerical reference and replay import no producer/evaluator module.
Synthetic tests deliberately import both independent and official code for
comparison, using synthetic inputs only. No test payload or model outcome was
opened while these sources and fixtures were prepared.

Remaining separate work:
Exact circuit conversion, isolated inference benchmarks and shot/simulator
diagnostics have their own release, source and independent replay requirements.
Successful model prediction/statistical replay alone does not complete the study.
