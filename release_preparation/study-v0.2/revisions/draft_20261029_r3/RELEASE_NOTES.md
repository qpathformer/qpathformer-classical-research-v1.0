# Q-Pathformer Study v0.2 — Improvement Study and Baseline Comparison

**Draft release for owner review.** Repository edition v1.0 is separate from study v0.2.

The study combines a classical GPU text experiment on DBpedia14 title-plus-content classification with a separate synthetic quantum-circuit schedule experiment. All 94 registered main runs and eight common text warmups completed. Classical confirmation includes 15 endpoints and quantum confirmation includes 40 endpoints.

Hash18 text macro-F1 was 97.659%, compared with 97.642% for current content routing and 97.602% for shared adapters. The primary mean gain was 0.01694 percentage points and its paired 95% interval crossed zero. In the quantum task, untied assigned circuits reached 81.44%, the original schedule 71.83%, fixed depth four 93.32%, and the matched-information MLP129 99.04%.

The text result does not establish a resolved primary improvement. Changing circuit scheduling improved the selected quantum comparison but the fixed-depth and classical controls performed better. This is local simulation, without quantum advantage or physical hardware evidence. Historical path bindings and exact NumPy replay guards limit relocation. The two task families must not be conflated.

| Download | Contents |
| --- | --- |
| QPathformer_v0.2_Study.zip | Preserved PDF and Word report with edition note, scope and provenance |
| QPathformer_v0.2_Documentation.zip | Study overview, original guidance, findings and reproduction boundaries |
| QPathformer_v0.2_Code.zip | Selected unchanged implementation, dependency inventory and bounded startup helper |

Each ZIP has its matching external `.seal.json`. [Package identities](receipts/PACKAGE_INDEX.json), [fresh extraction and startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json), [report review](report/REPORT_REVIEW.json), and [source inventory](receipts/SOURCE_INVENTORY.json) identify the exact prepared assets.

Startup result: `PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP`. Full experiment reproduction, clean-room installation, shot sampling and QPU jobs were not performed. Datasets, checkpoints, full archives, installed environments and credentials are omitted. No ETEL is supplied by this study.

The owner adopted the same scoped licensing scheme as the earlier two studies: CC BY 4.0 for exact controlled original report and explanatory prose; unchanged Platform License 1.0 for exact selected Python. Each package includes its adoption record and precise scope. Existing grants remain in force; excluded materials retain separate terms.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliation does not transfer ownership. Repository visibility and publication remain separate from licensing.
