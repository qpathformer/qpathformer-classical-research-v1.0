# Reproducibility and package verification

Repository edition v1.0 begins with release study-v0.9.5. "Public report edition" identifies an editorial edition; repository access is a separate setting. Access is currently private while further releases are prepared.

The three companion packages separate Study, Documentation and Code. The Study package preserves the final v0.9.5 report PDF and Word edition. The Code package preserves the complete selected original code package: 36 study Python files, two review tools, its quickstart and integrity records. This Documentation package provides project explanations, task/concept illustrations and the unchanged QPATH-ARCH-001 PDF with source provenance. Generated data, trained checkpoints, full runtime trees and the complete reproduction archive are not included. The [code](../CODE_LICENSE_SCOPE.json), [report](../REPORT_LICENSE_SCOPE.json) and [documentation](../DOCUMENTATION_RIGHTS.md) scopes remain distinct.

For an experiment, select its full accepted archive, report, environment and protocol. Verify their identities independently, then distinguish saved-checkpoint evaluation, retraining, prescribed-action replay and fresh environment recreation. This documentation asset does not verify an archive obtained separately.

The v0.9.5 report records four prescribed clean-directory replays with fresh clocks. They do not establish fresh-install portability or autonomous allocation equivalence across machines. Historical restore paths remain unchanged in the original archive; no environment migration was performed here.

The retained delivery receipt was read and hashed during the original preparation. It records 117,386,480,175 accepted payload bytes, excluding its manifest and later receipts. The full payload was not rehashed. This number is not model size, RAM or ZIP size.

Each new ZIP has an outer manifest, checksums and external seal. The unchanged Study and Code payload trees retain their own original internal records. Older external seals and receipts describe the original ZIPs, not the new wrappers. The current outer seal verifies the downloaded wrapper; fully verifying the older compressed bytes requires the retained original ZIP. See the [verification guide](../VERIFY.md).

The original code startup/regression receipts remain historical. The separate [study-v0.9.5 startup receipt](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/QPathformer_v0.9.5_Code.startup.json) and [package verification record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/FRESH_PACKAGE_VERIFICATION.json) identify the exact new Code ZIP, its seal, environment, commands, outcome and bounded checks. Neither package integrity nor startup checks establish official study reproduction or fresh-install equivalence.

## Configuration and storage planning

The accepted v0.9.5 payload is recorded as 117,386,480,175 bytes, excluding its manifest and later receipts. Its original manifest adds 1,159,611,589 bytes. Together they are **118,546,091,764 logical file bytes (118.55 decimal GB)** before later receipts and filesystem allocation overhead. These figures were read from the verified delivery receipt, not remeasured by rehashing the full archive.

For planning, allow **150 GB free for one retained archive copy**, or **300 GB free for the archive plus a separate working copy**. These are provisional editorial allowances, not validated minimums or a guarantee that a new training run will fit. Add space for retained compressed downloads, temporary extraction, new outputs and additional filesystem overhead. The documentation assets themselves need only their actual download/extraction sizes.

The original restore README records Windows, Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1 and native OpenBLAS libraries. It records six BLAS/thread variables set to one and checks of effective thread counts. Windows process, locking and filesystem behaviour remain dependencies. The preserved virtual environment points to its original base-Python path; copying it does not produce a portable installation.

CPU, RAM and GPU minima have not been established by this packaging work. Match any future execution to its specific protocol and environment; archive byte size cannot supply those hardware requirements. Native Word, fonts and rendering dependencies matter if recreating the report, not simply reading these Markdown files. A fresh installation, different restore layout or numerical run would need its own qualification.

Historical local circuit checks and a future physical-device protocol are separated in the [QPU preparation plan](QPU_RELEASE_PLAN.md). The [distribution guide](DISTRIBUTION_GUIDE.md) explains this collection and its package boundaries.
