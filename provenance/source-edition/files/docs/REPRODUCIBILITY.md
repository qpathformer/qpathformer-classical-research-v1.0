# Reproducibility and package verification

This repository remains private staging. “Public report edition” identifies an editorial edition; it does not change access to the downloads.

The Git tree is a documentation and scope-record selection, including task/concept illustrations and the unchanged QPATH-ARCH-001 architecture PDF with source provenance. The private [study-v0.9.5 release](https://github.com/qpathformer/qpathformer-classical-research/releases/tag/study-v0.9.5) separately provides the original documentation ZIP, QPATH RPT011 public report edition 1, and a selected code package. The code package preserves 36 study Python files, includes two review tools and provides its own quickstart. Generated data, trained checkpoints, full runtime trees and the complete reproduction archive are not distributed in those selections. The adopted [code](../CODE_LICENSE_SCOPE.json) and [report](../REPORT_LICENSE_SCOPE.json) grants remain separate from the historical unadopted documentation proposal and the new [documentation scope](../DOCUMENTATION_LICENSE_SCOPE.json), which records its own selection and adoption status.

For an experiment, select its full accepted archive, report, environment and protocol. Verify their identities independently, then distinguish saved-checkpoint evaluation, retraining, prescribed-action replay and fresh environment recreation. This documentation asset does not verify an archive obtained separately.

The v0.9.5 report records four prescribed clean-directory replays with fresh clocks. They do not establish fresh-install portability or autonomous allocation equivalence across machines. Historical restore paths remain unchanged in the original archive; no environment migration was performed here.

The live delivery receipt was read and hashed during preparation. It records 117,386,480,175 accepted payload bytes, excluding its manifest and later receipts. The full payload was not rehashed. This number is not model size, RAM or ZIP size.

Each sealed documentation, report and code ZIP retains its own internal records and external seal. The code's startup/regression receipts identify the exact final ZIP tested and the limited checks performed; they do not establish official reproduction or fresh-install equivalence. Current root `MANIFEST.json`, `SOURCE_RECORD.json`, `VALIDATION.json` and `CHECKSUMS.sha256` describe this Git-tree revision, including its copied scope records. They do not replace the original ZIP records or change historical seals. See the [verification guide](../VERIFY.md). Integrity checks do not themselves grant licenses; the actual owner decisions are recorded separately.

## Configuration and storage planning

The accepted v0.9.5 payload is recorded as 117,386,480,175 bytes, excluding its manifest and later receipts. Its original manifest adds 1,159,611,589 bytes. Together they are **118,546,091,764 logical file bytes (118.55 decimal GB)** before later receipts and filesystem allocation overhead. These figures were read from the verified delivery receipt, not remeasured by rehashing the full archive.

For planning, allow **150 GB free for one retained archive copy**, or **300 GB free for the archive plus a separate working copy**. These are provisional editorial allowances, not validated minimums or a guarantee that a new training run will fit. Add space for retained compressed downloads, temporary extraction, new outputs and additional filesystem overhead. The documentation assets themselves need only their actual download/extraction sizes.

The original restore README records Windows, Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1 and native OpenBLAS libraries. It records six BLAS/thread variables set to one and checks of effective thread counts. Windows process, locking and filesystem behaviour remain dependencies. The preserved virtual environment points to its original base-Python path; copying it does not produce a portable installation.

CPU, RAM and GPU minima have not been established by this packaging work. Match any future execution to its specific protocol and environment; archive byte size cannot supply those hardware requirements. Native Word, fonts and rendering dependencies matter if recreating the report, not simply reading these Markdown files. A fresh installation, different restore layout or numerical run would need its own qualification.

Historical local circuit checks and a future physical-device protocol are separated in the [QPU preparation plan](QPU_RELEASE_PLAN.md). The [planned private distribution](DISTRIBUTION_PLAN.md) will retain the original report/code payloads and add new wrapper verification; it has not been assembled or run.
