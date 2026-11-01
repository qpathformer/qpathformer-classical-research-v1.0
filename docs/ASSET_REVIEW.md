# Candidate asset review

Every submission begins as a candidate asset, including a proposed PR diff, findings report, adapter, weight file, dataset, script, configuration and documentation change. Classification is an access decision; it does not establish ownership, a licence or scientific validity.

## Intake and identity

Before merging or distributing an asset, create a record using [the template](../templates/ASSET_RECORD.json). Record source and contributor, exact bytes and SHA256, parent artifacts, proposed use, proposed audience and the licence or permission evidence. Keep the candidate immutable; a changed file needs a new hash and review. Large or restricted binary assets belong in approved private storage, with a manifest in the permitted repository.

Public findings PRs may contain only public-safe material. Restricted submissions use private owner-arranged intake; a submitter should not gain access to unrelated Lab or Strategic assets by using that route. For private intake, contact Anthony Siljeg at [asiljeg@alnotrea.com](mailto:asiljeg@alnotrea.com) with a non-sensitive description first. If no private intake is available, accept no restricted payload until one is arranged. Emailing a request does not itself establish a private artifact-transfer route. Do not add such payloads to public issues, PRs or their attachments.

## Review before execution

Confirm the submitter's authority, redistribution scope, upstream licences and attribution. For datasets, inspect access terms, consent where relevant, personal information and train/evaluation contamination. For weights and adapters, identify the base model, derivative terms, training-data provenance and redistribution restrictions. Do not infer that a published model or dataset is unrestricted.

Inspect executable content before running it. Use an isolated environment without production credentials and with limited network, storage and compute access. Treat executable serialization formats and scripts as code, including model-loading paths that execute custom code. Do not run untrusted PR code in a privileged workflow or on a shared self-hosted runner. Review external dependencies and workflow changes explicitly. Record permission and cost limits before any paid compute or QPU job.

For research, assess the question, data/split identities, comparator, evaluation rule, reproduction steps and actual evidence. Review failures and omitted results. Keep a successful integrity check separate from scientific reproducibility and from a safety decision.

## Classification and merge

An owner selects Public, Enterprise or Strategic and records a reason. Unclassified restricted submissions stay in owner-controlled intake. Enterprise means approved Lab participants; Strategic means specifically authorised internal Q-Pathformer developers, with owners retaining approval and administrative authority. Lab admission and an internal developer appointment are separate decisions. The receiving repository and storage must match that audience before upload or merge. A public-safe redacted summary is a new derived asset with its own review and provenance.

The reviewer records pass, needs changes, reject or defer separately for rights, scientific assessment, security and public disclosure. Scientific assessment includes reproducibility and the quality/limits of the claimed inference; the terms are not interchangeable. The owner records a final decision, destination, permitted uses, release eligibility and any expiry. An owner must not merge into an accepted branch while any required review remains unresolved. These are owner-operated decisions; the current GitHub maintenance checks do not automatically validate the rights, scientific, security or public-disclosure review fields. Preserve rejected records privately as appropriate; do not include restricted detail in public rejection comments.

For contributed private material proposed for Strategic retention or a new Strategic use, record an asset-specific agreement with the contributor or applicable rights holder and the authorised project representative. Identify the permitted purpose, audience, duration and disclosure terms, together with any additional permissions required. Existing public permissions remain unchanged. Identify the actual rights holder where different from the submitter. The [Strategic retention review](../templates/STRATEGIC_RETENTION_REVIEW.md) records the agreement and review; it does not create an agreement by completion. If required agreement is absent, defer the proposed new use. Existing rights and obligations continue to govern existing material; no assignment, exclusivity, confidentiality or incoming licence is inferred.

After approval, merge the reviewed diff and associate the asset record with the merge commit. Public contributions must already be safe and permitted to disclose before a public issue, fork or PR is opened. A later promotion from Strategic to Enterprise or from private to Public requires a new owner disclosure decision and an updated rights/safety review. A classification change cannot undo prior public disclosure or revoke an existing licence.

## Asset record format

The blank JSON template retains `qpath-candidate-asset-1` and all existing fields. `reviews.scientific` retains its broader scientific meaning; `reviews.public_disclosure` retains its public-transition meaning. They have not been renamed or narrowed.

Optional fields add the research cycle, permitted uses, release eligibility, expiry, and a reference to the Strategic agreement. Optional `review_extensions.reproducibility` can record a specific reproduction assessment, while `review_extensions.audience_disclosure` records a non-public audience transition separately. Missing optional fields mean not recorded, not approved. Existing records remain under their original schema and are not rewritten.

No executable consumer or validator was found in the captured full repository. These additive template fields do not prove compatibility with an external or private validator; check that consumer before use. Blank templates may be public. Completed applicant, consent and restricted asset records remain in appropriate private storage.
