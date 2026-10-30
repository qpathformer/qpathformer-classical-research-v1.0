**Published release · Private repository · Study · Documentation · Code**

Q-Pathformer v0.6 asks whether richer circuit readouts help on harder classification boundaries, and whether the same trained circuit can run faster through an equivalent classical representation. Six recipes were compared on checkerboard, spiral, noisy annulus and rare-positive disks, using five paired training seeds on one fixed confirmation split per task family. All circuit execution used classical compute.

This completed study is presented in Q-Pathformer Classical Research, repository edition v1.0. Study v0.6 and repository edition v1.0 are separate identifiers. The design includes **48 development and 120 confirmation endpoints**, plus 24 separate engineering endpoints.

### Historical findings

**Common clipped binary cross-entropy (BCE) was the primary endpoint; lower is better.** These are means over five confirmation training seeds. Macro-F1 is secondary.

| Recipe | Checkerboard | Spiral | Noisy annulus | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Scalar | 0.57805 | 0.50069 | 0.41064 | 0.01345 |
| Multi | 0.52162 | 0.42532 | 0.40911 | 0.01456 |
| Routed Trig25 | 0.30504 | 0.24828 | 0.40317 | 0.01487 |

Multi improves on Scalar on checkerboard and spiral, while routed Trig25 achieves lower mean common clipped BCE on both. Noisy-annulus and rare-disk results do not establish a general improvement from the richer readout. Small or unresolved differences are not equivalence results.

Checkerboard mean macro-F1 rises from **73.03% to 78.55%**, and spiral from **77.60% to 84.71%**, for Scalar to Multi. The sixteen primary contrasts use 99.6875% Bonferroni-adjusted paired-seed intervals. A separate 10,000-draw paired-record bootstrap conditions on the trained checkpoints; it does not add training replications.

Forty selected circuit checkpoints were converted to equivalent classical coefficients. The checks found no classification differences and numerical agreement within the declared tolerances. Conversion reduced measured CPU inference time. It is another representation of the same fitted predictor, not an additional trained model.

An equally optimized routed Trig25 control uses the same coefficient inference kernel and has comparable inference cost; the global MLP is faster in the displayed tables. Conversion improves the retained circuit implementation without establishing a speed advantage over equally optimized classical controls or quantum speedup.

### Historical verification and limitations

The analytical conversion applies to the retained two-layer encoding and linear Pauli-logit heads. Finite validation/test, off-grid, boundary and forced-bank checks quantify floating-point agreement, not bitwise equality for every input or arbitrary circuit families. The coefficient representation increases parameter storage; it is a time/representation tradeoff, not compression.

Deployment timings used an isolated process with one BLAS thread and no concurrent training. Hot inference includes routing, features and sigmoid, excluding loading; compilation is separate. Batch size and unexplained timing drift limit comparisons, so no universal speedup multiplier is claimed.

Historical local readiness covers **40 checkpoints and 983,040 Aer simulated shots**, with separate probability-level multinomial diagnostics. The Manila device properties are an archived 27 May 2024 snapshot, not current calibration. Release preparation does not repeat these experiments.

These are small two-dimensional synthetic binary classifiers with fixed routers and unequal capacities. Five paired training seeds on one fixed confirmation split per task family do not establish population-wide or real-world generalization. Historical prior-version scores provide context, not paired improvement evidence. No physical-QPU result, quantum advantage, ETEL implementation or full language-architecture benchmark is supplied.

### Downloads and release-packaging checks

Download each ZIP with its matching `.seal.json`, verify the external seal and safe extraction, then open `START_HERE.md`.

| Download | Contents |
| --- | --- |
| `QPathformer_v0.6_Study.zip` | The preserved report in PDF and Word, edition note, rights scope and provenance |
| `QPathformer_v0.6_Documentation.zip` | Research guide, original protocols, historical findings and reproduction boundaries |
| `QPathformer_v0.6_Code.zip` | Selected implementation, coefficient conversion, tests, dependency inventory and bounded startup tools |

[Exact package identities](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/fe509de7d8b73683da89bf82c3009043c75b6e06/release_preparation/study-v0.6/revisions/draft_20261030_r3/PACKAGE_INDEX.json) identify the revised ZIP/seal pairs. Current helper and wrapper changes are distinct from the preserved scientific source, report and historical records.

**Release-packaging verification is separate from historical study verification.** The bounded startup checks exact package integrity before and after its six required tests, parses all 61 selected Python files, and imports the selected numerical modules. The tests cover model shapes/paired initialization, independent circuit-state/moment agreement, orthogonal conversion nodes, both heads off grid and forced banks, constant logits/invalid contracts, and the learned Trig25 coefficient kernel. Missing compiler or test components fail startup. It does not train, score official data, sample shots, rerun benchmarks or submit QPU jobs. Success is not full scientific reproduction or a clean installation. Consult the final receipts for the checks performed against these assets.

Raw datasets, trained checkpoints, installed environments and the full retained archive are excluded. Full replay requires that separately retained evidence and its recorded environment/path bindings. Historical commands are provenance, not a batch to run from these downloads. Seals are integrity records, not digital signatures.

[Fresh extraction and startup binding](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/fe509de7d8b73683da89bf82c3009043c75b6e06/release_preparation/study-v0.6/revisions/draft_20261030_r3/receipts/FRESH_PACKAGE_VERIFICATION.json) · [Package verification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/fe509de7d8b73683da89bf82c3009043c75b6e06/release_preparation/study-v0.6/revisions/draft_20261030_r3/receipts/ROOT_PACKAGE_VERIFICATION.json) · [Report review](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/fe509de7d8b73683da89bf82c3009043c75b6e06/release_preparation/study-v0.6/revisions/draft_20261030_r3/report/REPORT_REVIEW.json) · [Source inventory](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/fe509de7d8b73683da89bf82c3009043c75b6e06/release_preparation/study-v0.6/revisions/draft_20261030_r3/receipts/SOURCE_INVENTORY.json).

### Scoped licensing

The identified original report content and explanatory prose are licensed under **CC BY 4.0**. Selected Python source and package helpers are **source available under the unchanged Q-Pathformer Platform License 1.0**. Each package identifies its adopted scope and exclusions; applicable earlier grants remain in force. Third-party dependencies, datasets, model artifacts, architecture documents and full archives retain their separate terms. [Owner licensing record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/fe509de7d8b73683da89bf82c3009043c75b6e06/release_preparation/study-v0.6/revisions/draft_20261030_r3/OWNER_LICENSE_AUTHORIZATION.json).

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains the licensor; company affiliation does not transfer ownership.

Published on 30 October 2026 in the private repository. Repository access remains restricted; publication does not change the adopted scoped licences. Study v0.9.5 remains designated Latest.

[Historical prepublication asset verification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/5005040d829edf64d4d4c8fac6fe7f7076d94650/release_preparation/study-v0.6/revisions/draft_20261030_r3/DRAFT_RELEASE.json).
