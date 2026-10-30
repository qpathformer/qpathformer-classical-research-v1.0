Q-Pathformer v0.9 independent prediction/statistics replay

Invoke only after all 636 B endpoints have passed author and independent
endpoint audits, root has released evaluation, and official scoring is committed.
The command revalidates these gates before opening any prediction/model outcome.

Use the preserved scientific Python with no installs:
C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe -B analysis/independent_audit/replay_analysis_v09.py --authorization ROOT_RELEASE_JSON --output NEW_OUTPUT_DIRECTORY

Root authorization JSON fields:
  schema: qpath-v09-independent-analysis-release-1
  review_status: approved_by_root
  stage: B
  action: independent_prediction_statistics
  independent_contract: {path, sha256, bytes}
  evaluation_release: {path, sha256, bytes}
  author_evaluation_commit: {path, sha256, bytes}

The contract is INDEPENDENT_ANALYSIS_CONTRACT.json beside this file. It binds
four production independent sources, numerical tolerances and synthetic tests.
The author commit is the completed evaluator's EVALUATION_COMMIT.json. Root
must independently review the source/qualification contract before authorizing.

Official output is exclusive-create; failures are retained and never retried
automatically. The command holds ETEL's existing exclusive auxiliary audit
lease; it cannot overlap training, conversion or serial timing. It performs no
training or selection. Source/authority/data/endpoint/scored-payload hashes are
checked before replay and checked again before an independent commit.

The numerical oracle uses the separately qualified independent reference. It
does not import the producer model, trainer, evaluator or statistics. Metrics
are recomputed from saved probabilities only after independent parity checks.
Any class rounding differences within 32 float64 eps of 0.5 are counted; both
probabilities must lie within that band, otherwise replay fails.

Scope: all 636 selected checkpoints, all train/validation/test predictions,
all registered metrics and descriptive class/bank/boundary slices, gate and
expert diagnostics, annulus latent labels, validation milestones and committed
endpoint cost fields. Learned-gate historical exposure is separately replayed
through all 15,000 updates from archived gradients and verified at each round.
No expert refitting occurs. Primary analysis has 12 Bonferroni BCE contrasts,
eight independent population means per family with two paired nested seeds.
Banknote's five optimizer seeds on one fixed split remain descriptive.

Resource inventory at the evaluator's RESOURCE_ACCOUNTING.json is hash-bound
but is not independently reconstructed by this command; separate exact-worker
resource verification and report accounting review cover that inventory.

Outputs:
  INDEPENDENT_METRICS.json
  INDEPENDENT_STATISTICS.json
  INDEPENDENT_REPLAY.json
  INDEPENDENT_ANALYSIS_COMMIT.json

Synthetic qualification command:
python.exe -B analysis/independent_audit/test_analysis_v09.py
Set all six numerical thread variables to 1 before running. These tests use
constructed arrays and inert 636-job authority fixtures only. No official test
outcomes are read. qualify_analysis_v09.py additionally persists receipts and
creates the contract; use only before release and never overwrite a contract.
