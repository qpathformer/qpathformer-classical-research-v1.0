# Q-Pathformer v0.9.5 — ETEL Training Allocation Study

**Completed classical study; private repository release: [`study-v0.9.5`](https://github.com/qpathformer/qpathformer-classical-research/releases/tag/study-v0.9.5).** This page summarizes the study. The release has separate documentation, public-report and selected code attachments, each with its own scope and integrity records. Models and the full reproduction archive remain separately retained.

The study compared fixed allocation, capped successive halving and ETEL suitability allocation over the same six recipes: fixed-soft circuit routing (C_S), learned-soft circuit routing (C_L) and the global trigonometric model G121, each at two learning rates. Allocation policies controlled training; they were not additional predictor families.

Confirmation included **192 portfolios** across four tasks, eight populations per task, two paired seeds and three policies. Separately, **192 full-horizon reference fits** and **four prescribed clean-directory replays** supported interpretation and reproduction checks. These count different experimental units.

Checkpoints were selected using native validation BCE and scored using native hidden-test BCE, a stable, unclipped Bernoulli negative log-likelihood; lower is better. The eight ETEL-minus-comparator contrasts use two-sided Bonferroni-adjusted **99.375% Student-t intervals** over eight independent population means, after averaging the two paired seed differences within each population (seven degrees of freedom). **No interval lay entirely below −0.01.** The study therefore did not establish the stipulated 0.01 native-BCE improvement. Inconclusive intervals and observed ties do not prove equivalence.

**Successive halving used less mean native CPU on all four tasks.** The tested ETEL suitability policy did not establish a training-efficiency advantage. That finding is separate from ETEL's execution and recovery role. G121 remained a strong classical comparator.

There were no physical-QPU results. The four replays used prescribed allocation actions and fresh clocks; they do not establish fresh-install portability or autonomous allocation equivalence on a different machine. v0.9 used a different primary BCE treatment, so the two studies do not form a directly comparable performance curve.

The verified delivery receipt records **117,386,480,175 bytes (117.39 decimal GB)** for the accepted archival payload, excluding its manifest and later receipts. This is evidence storage, not model size, RAM or the size of this ZIP. The full archive was not rehashed during this documentation build. The original report identities and receipt identity are recorded in the asset's `provenance/research_sources.json`; the unchanged source files are not bundled. QPATH RPT011 public report edition 1 is separately attached in PDF and Word formats, with its disclosed editorial omissions and adopted [report-content CC BY scope](../REPORT_LICENSE_SCOPE.json). Original internal editions remain separately retained.

The historical ETEL implementation used source version **0.2.0**. The confirmed component name **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1** does not change the version of that incorporated source. The selected code attachment has its own source/provenance inventory, bounded startup/regression receipts and adopted [38-file Platform 1.0 scope](../CODE_LICENSE_SCOPE.json). Supporting documents and model artifacts are not automatically covered by the code or report grants; the earlier documentation proposal is retained as an unadopted historical record. The revised [documentation scope](../DOCUMENTATION_LICENSE_SCOPE.json) records a separate selection and its own adoption status.

## Configuration and storage planning

| Storage item | Recorded size or planning allowance |
|---|---|
| Accepted evidence payload, excluding its manifest and later receipts | **117,386,480,175 bytes (117.39 GB)**. |
| Original package manifest | **1,159,611,589 bytes (1.16 GB)**, recorded by the same receipt. |
| Payload plus manifest | **118,546,091,764 bytes (118.55 GB)** of logical file content; later receipts and filesystem overhead are additional. |
| One retained archive copy | **Allow 150 GB free** as an initial storage-planning estimate. |
| Archive plus a separate working copy | **Allow 300 GB free** as an initial estimate for two copies. |

GB uses decimal units. The allowances are editorial recommendations, not measured minimums or guarantees for training. Add space for any compressed download retained alongside the files, temporary extraction, filesystem allocation overhead, later receipts and new experiment output; increase the allowance when those are known. The current documentation ZIP is much smaller and does not require 150 GB.

The historical restore record describes **Windows, Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1 and native OpenBLAS libraries**, with recorded BLAS/thread limits. These are recorded environment versions, not a newly qualified installation recipe. CPU, RAM and GPU requirements must be established separately for the intended workflow; they cannot be inferred from archive size. Fresh installation and a new restore layout remain unqualified. See `docs/REPRODUCIBILITY.md` for the configuration boundary.
