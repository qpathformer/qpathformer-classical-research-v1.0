Independent v0.9 retained resource accounting

Run only after all training and endpoint audits are complete and official
scoring has committed. This is metadata reconciliation, not a new observer.
No training source or ETEL adapter is changed. No prediction array is loaded.

Command with preserved scientific Python:
python.exe -B analysis/independent_audit/resource_accounting_v09.py --authorization ROOT_RESOURCE_RELEASE --output NEW_DIRECTORY

Root authorization schema:
  schema: qpath-v09-independent-resource-release-1
  review_status: approved_by_root
  stage: B
  action: independent_resource_accounting
  resource_contract: {path, sha256, bytes}
  independent_analysis_authorization: {path, sha256, bytes}

resource_contract binds INDEPENDENT_RESOURCE_CONTRACT.json. The second binding
references the already prepared independent analysis authorization. Its gate
checks all636 B audits, root evaluation release and committed official scoring.
The resource checker contract also binds the exact qualified analysis contract.

The command takes the existing auxiliary audit lease, opens SQLite read-only,
and independently reconstructs the evaluator's RESOURCE_ACCOUNTING.json. Every
attempt is included, including prior failures. Unknown samples remain unknown.
It validates exact PID+creation ownership, request/terminal identities and native
sample equality, plus all756 successful result/commit cost fields. B636 cost
records are compared with the scored rows. The selected ledger rows and all
consumed metadata files are rechecked before the success receipt is written.

Elapsed stage reporting uses the first registered worker start through the last
finish, including any pause/recovery gaps. It excludes preparation and subsequent
audits. Summed child elapsed time is occupancy, not elapsed stage wall time.
Training, diagnostic and sampler costs are nested and must not be added together.
Whole-worker CPU minus training CPU includes imports, preflight and verification;
it cannot be called isolated ETEL overhead. Native peak memory is lifetime peak
through the retained sample, not exact exit peak or training-only memory.

Qualification/data/audit/conversion/reproduction/inference costs require their
separate receipts and remain outside these training sums. Missing failure CPU
must never be presented as zero. Failed fixture and qualification evidence is
retained under test_runs. Source review is required before official root release.
