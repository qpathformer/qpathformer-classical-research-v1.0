# Candidate asset review

Proposed procedure. Every submission begins as a candidate asset, including a proposed PR diff, findings report, adapter, weight file, dataset, script, configuration and documentation change. Classification is an access decision; it does not establish ownership, a licence or scientific validity.

## Intake and identity

Before merging or distributing an asset, create a record using [the template](../templates/ASSET_RECORD.json). Record source and contributor, exact bytes and SHA256, parent artifacts, proposed use, proposed audience and the licence or permission evidence. Keep the candidate immutable; a changed file needs a new hash and review. Large or restricted binary assets belong in approved private storage, with a manifest in the permitted repository.

Public findings PRs may contain only public-safe material. Restricted submissions use private owner-arranged intake; a submitter should not gain access to unrelated Lab or Strategic assets by using that route. If no private intake is available, accept no restricted payload until one is arranged. Do not add such payloads to public issues, PRs or their attachments.

## Review before execution

Confirm the submitter's authority, redistribution scope, upstream licences and attribution. For datasets, inspect access terms, consent where relevant, personal information and train/evaluation contamination. For weights and adapters, identify the base model, derivative terms, training-data provenance and redistribution restrictions. Do not infer that a published model or dataset is unrestricted.

Inspect executable content before running it. Use an isolated environment without production credentials and with limited network, storage and compute access. Treat executable serialization formats and scripts as code, including model-loading paths that execute custom code. Do not run untrusted PR code in a privileged workflow or on a shared self-hosted runner. Review external dependencies and workflow changes explicitly. Record permission and cost limits before any paid compute or QPU job.

For research, assess the question, data/split identities, comparator, evaluation rule, reproduction steps and actual evidence. Review failures and omitted results. Keep a successful integrity check separate from scientific reproducibility and from a safety decision.

## Classification and merge

An owner selects Public, Enterprise or Strategic and records a reason. Unclassified restricted submissions stay in owner-controlled intake. Enterprise means approved Lab participants; Strategic means organisation owners only. The receiving repository and storage must match that audience before upload or merge. A public-safe redacted summary is a new derived asset with its own review and provenance.

The reviewer records pass, needs changes, reject or defer separately for rights, reproducibility, security and disclosure. The owner records a final decision, destination, permitted uses, release eligibility and any expiry. An unresolved required review blocks merge into an accepted branch. Preserve rejected records privately as appropriate; do not include restricted detail in public rejection comments.

After approval, merge the reviewed diff and associate the asset record with the merge commit. A later promotion from Strategic to Enterprise or from private to Public requires a new owner disclosure decision and an updated rights/safety review. A classification change cannot undo prior public disclosure or revoke an existing licence.
