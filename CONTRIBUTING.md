# Contributing to Q-Pathformer Classical Research

**Repository guidance. Existing material licenses and incoming-contribution permissions are separate.**

Questions, corrections, reproduction reports and experiment proposals are welcome. Name the study and supporting evidence, keep changes focused, and credit material you use. A small wording correction needs only its location and suggested replacement.

For reproduction reports, identify the archive or commit, environment, steps, result and relevant logs. For new experiments, explain the question, controls, selection/evaluation rule and resource needs. Report negative and inconclusive findings as well as improvements.

Preserve original protocols, trained checkpoints, reports and results. Make corrections or new analyses as identifiable revisions, with links to the earlier evidence. Keep classical emulation, equivalent classical inference and physical QPU execution distinct; also distinguish model routing, sampling, allocation and execution.

Read [LICENSE](LICENSE), [LICENSE_SCOPE.md](LICENSE_SCOPE.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Implementation contributions are not yet open for general public submission: obtain a confirmed contribution and redistribution route before publishing a modified code patch. Submission alone does not transfer copyright or supply additional licensing permissions.

Share only material you are entitled to share, identify upstream sources and preserve notices. Maintainers must confirm the terms before incorporating or republishing contributions. The [documentation content grant](DOCUMENTATION_RIGHTS.md), like the adopted code/report grants, does not create a blanket incoming-contribution agreement. The identified new wrapper/support prose has a separate [CC BY 4.0 scope](NEW_GUIDANCE_LICENSE_SCOPE.json). No DCO or CLA requirement is introduced here.

Describe material AI assistance and the checks performed; the submitting person remains responsible for accuracy and provenance. AI tools are not human authors or independent release authorities. Contribution credit is recorded in [CONTRIBUTORS.md](CONTRIBUTORS.md); paper authorship is agreed separately.

## Contact and current submission routes

Public questions and proposals can start in [issues](https://github.com/qpathformer/qpathformer-classical-research-v1.0/issues/new). For permitted findings or corrections, fork the public repository, create a branch and open a [pull request](https://github.com/qpathformer/qpathformer-classical-research-v1.0/pulls) using the template. Public findings are visible before merge, including on a public fork.

Direct contact: Anthony Siljeg - [asiljeg@alnotrea.com](mailto:asiljeg@alnotrea.com). For private intake, send only a non-sensitive description first. Wait for an owner-arranged private transfer and review scope before sending restricted artifacts. A contact request does not grant private access or implementation-redistribution rights.

See the [research cycle](docs/RESEARCH_CYCLE.md) for how public contributions, the next private Lab and selected public releases relate. No open private Lab upload service is established by this guidance.

## Findings and pull requests

1. Identify the study, question, sources and permitted evidence. Use the [evidence guide](docs/CONTRIBUTION_EVIDENCE.md) for experiments; a small documentation correction needs only its location, reason and checks.
2. Share only public-safe findings here. Do not put restricted datasets, weights, credentials, personal information or Enterprise/Strategic evidence into a public issue, PR, branch or attachment. Arrange private intake with an owner before transferring restricted material. A public branch cannot become private through a label.
3. Create a focused branch or fork from current `main` and open a draft PR using the supplied template. Identify changed assets and their provenance, permission and intended audience; [asset review](docs/ASSET_REVIEW.md) applies before merge. The implementation-permission boundary above still applies.
4. Record the checks performed and material AI assistance. Run the applicable [repository checks](.github/CHECKS.md). Do not execute untrusted model loaders or scripts with credentials or commit to paid/QPU work without the owner's separate approval.
5. Mark the PR ready when the diff and evidence can be reviewed. Resolve conversations, update the branch if `main` advances and wait for **Documentation links** and **Content scope** from GitHub Actions. An owner reviews and merges the change.

The rules require zero approving reviews for the single-maintainer workflow; self-review is not independent approval. PRs, resolved conversations, passing checks and an up-to-date branch are enforced without bypass actors. Force pushes and deletion of `main` are blocked. Check results validate the stated maintenance boundaries, not scientific conclusions or legal authority.

## Private Lab eligibility

At least two distinct, substantive qualifying merged public contributions establish eligibility for an owner review, not admission. Useful classical work and negative findings can qualify; buying QPU time is not required. The [governance policy](GOVERNANCE.md#eligibility-for-lab-access) defines qualifying contributions, evidence and owner assessment. Record the prior qualifying contributions considered for each cycle; neither a contribution-count reset nor access carryover is automatic.

Approved participants receive defined Private Research Lab access. Strategic materials are restricted to specifically authorised internal Q-Pathformer developers. Organisation owners retain approval and administrative authority. An internal-development appointment and explicit access grant are separate from Lab admission. Lab admission also grants no authorship or authority to publish. Access is reassessed for each cycle; see the [research-cycle guide](docs/RESEARCH_CYCLE.md).

For contributed private material proposed for Strategic retention or a new Strategic use, record an asset-specific agreement with the contributor or applicable rights holder and the authorised project representative. Identify the permitted purpose, audience, duration and disclosure terms, together with any additional permissions required. Existing public permissions remain unchanged. The actual rights holder may differ from the submitter. The applicable agreement and asset review govern the proposed use; a PR or classification alone supplies no new rights. Completed [Lab access records](templates/LAB_ACCESS_REVIEW.md), consent records and restricted evidence stay private.
