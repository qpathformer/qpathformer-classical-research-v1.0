# Study v0.1 release review

This branch prepares a draft release in the official private repository. The main branch and published study-v0.9.5 release are unchanged. The three ZIP/seal pairs use the established Study, Documentation and Code layout; no new license adoption or public publication is implied.

Read the [release notes](RELEASE_NOTES.md), [study overview](documentation/README.md) and [research guide](documentation/RESEARCH_GUIDE.md). The report PDF and Word candidate are in the Study ZIP, with [edition changes](report/EDITION_CHANGES.md) and [report verification](report/REPORT_REVIEW.json).

## Rights decisions for review

- [Report scope proposal](scope_proposals/REPORT_LICENSE_SCOPE_PROPOSAL.json): controlled original prose, table presentation and three report figures; proposed CC BY 4.0.
- [Code scope proposal](scope_proposals/CODE_LICENSE_SCOPE_PROPOSAL.json): 22 original Python files and two new helpers; proposed unchanged Platform License 1.0.
- New explanatory prose: proposed CC BY 4.0 in the exact [Study](scope_proposals/Study_GUIDANCE_SCOPE_PROPOSAL.json), [Documentation](scope_proposals/Documentation_GUIDANCE_SCOPE_PROPOSAL.json) and [Code](scope_proposals/Code_GUIDANCE_SCOPE_PROPOSAL.json) lists.

These proposals are unadopted. Existing grants remain in force for their earlier scopes, including already-licensed expression wherever reused. No blanket grant covers dependencies, datasets, models, architecture documents or complete archives. Anthony remains proposed licensor, with the established attribution: Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.

## Verification

[Package identities](PACKAGE_INDEX.json) · [Final ZIP/seal/startup binding](FRESH_PACKAGE_VERIFICATION.json) · [Windows startup receipt](QPathformer_v0.1_Code.startup.json) · [Full original archive integrity check](FROZEN_SOURCE_VERIFICATION.json) · [Draft upload record](DRAFT_RELEASE.json).

Startup checked imports, four CLI help paths, 15 selected non-training tests and one local circuit compilation/matrix comparison. It did not train, score the official study, sample shots, install dependencies or submit hardware jobs. Code selection and dependencies are recorded under code/. Each sealed ZIP contains its complete human-readable rights statement and scope proposals.

After owner review, any content or license changes require refreshed package identities and seals before final release approval. The historical staging repository remains private and unchanged.
