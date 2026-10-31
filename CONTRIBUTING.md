# Contributing to Q-Pathformer Classical Research

**Repository guidance. Existing material licenses and incoming-contribution permissions are separate.**

Questions, corrections, reproduction reports and experiment proposals are welcome. Name the study and supporting evidence, keep changes focused, and credit material you use. A small wording correction needs only its location and suggested replacement.

For reproduction reports, identify the archive or commit, environment, steps, result and relevant logs. For new experiments, explain the question, controls, selection/evaluation rule and resource needs. Report negative and inconclusive findings as well as improvements.

Preserve original protocols, trained checkpoints, reports and results. Make corrections or new analyses as identifiable revisions, with links to the earlier evidence. Keep classical emulation, equivalent classical inference and physical QPU execution distinct; also distinguish model routing, sampling, allocation and execution.

Read [LICENSE](LICENSE), [LICENSE_SCOPE.md](LICENSE_SCOPE.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Implementation contributions are not yet open for general public submission: obtain a confirmed contribution and redistribution route before publishing a modified code patch. Submission alone does not transfer copyright or supply additional licensing permissions.

Share only material you are entitled to share, identify upstream sources and preserve notices. Maintainers must confirm the terms before incorporating or republishing contributions. The [documentation content grant](DOCUMENTATION_RIGHTS.md), like the adopted code/report grants, does not create a blanket incoming-contribution agreement. The identified new wrapper/support prose has a separate [CC BY 4.0 scope](NEW_GUIDANCE_LICENSE_SCOPE.json). No DCO or CLA requirement is introduced here.

Describe material AI assistance and the checks performed; the submitting person remains responsible for accuracy and provenance. AI tools are not human authors or independent release authorities. Contribution credit is recorded in [CONTRIBUTORS.md](CONTRIBUTORS.md); paper authorship is agreed separately.

## Findings and pull requests

1. Identify the study, question, sources and permitted evidence. Use the [evidence guide](docs/CONTRIBUTION_EVIDENCE.md) for experiments; a small documentation correction needs only its location, reason and checks.
2. Share only public-safe findings here. Do not put restricted datasets, weights, credentials, personal information or Enterprise/Strategic evidence into a public issue, PR, branch or attachment. Arrange private intake with an owner before transferring restricted material. A public branch cannot become private through a label.
3. Create a focused branch or fork from current `main` and open a draft PR using the supplied template. Identify changed assets and their provenance, permission and intended audience; [asset review](docs/ASSET_REVIEW.md) applies before merge. The implementation-permission boundary above still applies.
4. Record the checks performed and material AI assistance. Run the applicable [repository checks](.github/CHECKS.md). Do not execute untrusted model loaders or scripts with credentials or commit to paid/QPU work without the owner's separate approval.
5. Mark the PR ready when the diff and evidence can be reviewed. Resolve conversations, update the branch if `main` advances and wait for **Documentation links** and **Content scope** from GitHub Actions. An owner reviews and merges the change.

The rules require zero approving reviews for the single-maintainer workflow; self-review is not independent approval. PRs, resolved conversations, passing checks and an up-to-date branch are enforced without bypass actors. Force pushes and deletion of `main` are blocked. Check results validate the stated maintenance boundaries, not scientific conclusions or legal authority.

## Private Lab eligibility

At least two distinct substantive qualifying public merges establish eligibility for owner review, not automatic access. The owner records each contribution's benefit and reproducibility evidence; useful classical work, simulator/QPU findings, negative results and evidence-based corrections may qualify. Small edits or an artificially split change do not automatically count. See [governance](GOVERNANCE.md) and the [Lab access review template](templates/LAB_ACCESS_REVIEW.md); completed access records stay private.

An owner then reviews rights, reproducibility, safety, conduct and participation scope. Enterprise means approved Lab participants; Strategic means organisation owners only in separately restricted storage. The proposed research Lab is distinct from the public Enterprise Standards repositories. This process introduces no blanket incoming licence, access entitlement or publication promise.
