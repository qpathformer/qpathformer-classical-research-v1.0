# Q-Pathformer Study v0.1 — Local Benchmark and QPU Readiness

These are the final adopted scopes and verification records for the three curated downloads in the [study-v0.1 release](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.1). Repository edition v1.0 and study v0.1 are separate identifiers. The historical report title uses “IBM Readiness”; the release title uses “QPU Readiness” for the same local translation and simulator preparation, without physical-QPU or current-device qualification claims.

## Licensed content and boundaries

- [Report scope](scopes/Study_REPORT_LICENSE_SCOPE.json): CC BY 4.0 for controlled original prose, table presentation and three figures.
- [Python scope](scopes/Code_CODE_LICENSE_SCOPE.json): unchanged Q-Pathformer Platform License 1.0 for 24 Python files.
- Selected explanatory prose: CC BY 4.0 under the exact [Study](scopes/Study_GUIDANCE_LICENSE_SCOPE.json), [Documentation](scopes/Documentation_GUIDANCE_LICENSE_SCOPE.json) and [Code](scopes/Code_GUIDANCE_LICENSE_SCOPE.json) lists.
- [Owner adoption record](LICENSE_ADOPTION.json), dated 29 October 2026, with Anthony Siljeg as licensor and his established founder/company/initiative attribution.

Scope paths identify files inside their corresponding packages; this record directory is not a substitute package. Existing grants and already-licensed expression remain covered within their scopes. Datasets, third-party dependencies, checkpoints, architecture documents, full archives and surrounding records do not receive a blanket grant.

## Findings and reproduction

[Study guide](packages/QPathformer_v0.1_Documentation/payload/project/README.md) · [Study summary](packages/QPathformer_v0.1_Documentation/payload/project/release_notes/study-v0.1.md) · [Reproduction boundaries](packages/QPathformer_v0.1_Documentation/payload/project/docs/REPRODUCIBILITY.md).

[Package identities](PACKAGE_INDEX.json) · [ZIP/seal/startup binding](FRESH_PACKAGE_VERIFICATION.json) · [Windows startup receipt](QPathformer_v0.1_Code.startup.json) · [Retained original archive audit](FROZEN_SOURCE_VERIFICATION.json) · [Report edition changes](report/EDITION_CHANGES.md) · [Report verification](report/REPORT_REVIEW.json).

The new final Code ZIP passed the bounded Windows check: imports, four CLI help paths, 15 selected non-training tests and a local circuit compilation/matrix comparison. It did not train, score the full study, sample shots, install dependencies or submit hardware jobs. The original review packages and their dated proposals remain historical evidence, with different identities. Actual publication is recorded separately after the release event.
