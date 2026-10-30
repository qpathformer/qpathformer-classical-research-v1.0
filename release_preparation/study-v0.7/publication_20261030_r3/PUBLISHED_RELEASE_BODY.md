**Published release · Private repository · Study · Documentation · Code**

Q-Pathformer v0.7 examines whether grouping nearby inputs into specialist model banks improves classification, and how trained circuit models can run through an equivalent classical representation. Its advances are independent population replication, matched-count routing controls, a wider classical feature baseline and study-specific execution integration.

Study v0.7 and repository edition v1.0 are separate identifiers.

### Historical findings

**Common clipped binary cross-entropy (BCE) was primary; lower is better.** These descriptive means average two seeds within each population, then eight populations per task. Macro-F1 is secondary.

| Recipe | Checkerboard | Spiral | Noisy annulus | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Flexible circuit (MultiK) | 0.50907 | 0.37167 | 0.39927 | 0.01562 |
| Routed Trig25 | 0.26559 | 0.24968 | 0.39400 | 0.01314 |
| Global Trig121 | 0.04971 | 0.07878 | 0.39457 | 0.00827 |

Geometric routing achieved lower common clipped BCE than matched-count hash routing for both Multi and Trig25 on all four task families. All eight adjusted routing intervals favor geometric routing; seven establish improvement beyond the 0.01 practical reference, with rare-disk Trig the exception. The result concerns the tested data, feature representations and optimization, not universal routing superiority.

The wider global Trig121 control led the two harder clean tasks. Its mean macro-F1 was **98.47% on checkerboard and 96.57% on spiral**, compared with **76.57% and 86.82%** for MultiK. It does not lead every metric or family: routed Trig25 has higher descriptive F1 on noisy annulus, where its primary contrast with Trig121 is inconclusive.

The twenty primary comparisons use eight paired population-level differences, seven degrees of freedom and nominal 99.75% Bonferroni-adjusted t intervals. There is no paired-record bootstrap. An interval crossing zero is inconclusive; the practical reference is not an equivalence test.

Classical conversion preserved every checked class prediction. For matched single-input CPU calls, reported speedups were **4.28–4.58× relative to the original circuit implementation**. Conversion changes how the same fitted predictor is evaluated; it adds no accuracy gain, compression or quantum-advantage claim. The MLP is fastest in the timing tables, and learned Trig controls use the optimized common kernel.

### What changed in this study

Eight model recipes were compared on checkerboard, spiral, noisy annulus and rare disks. Confirmation uses eight independently generated populations per task, with two paired optimizer seeds within each population. The completed design has 32 engineering, 64 development and 512 confirmation fits: 608 total. The 576 full fits completed 200 rounds and 15,000 updates each.

The Code package includes the study-specific execution integration for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**, using retained ETEL source version **0.2.0**. It schedules complete registered fits in isolated local processes. The component label, historical source version, study v0.7 and repository edition v1.0 identify different things. This selection is not a standalone ETEL component release.

Model routing selects a bank for an input record; ETEL schedules an entire fit. Logical 64-slot groups and peak ready capacity 192 are scheduling bookkeeping. At most five fit workers ran concurrently; logical slots are not physical processors, qubits, model banks or measured speedup.

### Historical verification and limitations

The study converted 192 circuit predictors and repacked 256 learned Trig predictors. These 448 representations are existing fitted models, not extra training fits. The algebraic identity is specific to the retained core/readout; finite floating-point checks do not promise bitwise equality for every input or efficient conversion of arbitrary deeper circuits.

Timing uses microseconds per complete batch call, with matched ratios calculated before aggregation. Three timing sessions and fifteen trials per condition are technical repeats, not additional population replications. Host conditions and unexplained session drift limit inference.

Historical shot sensitivity used ideal local multinomial sampling at equal **total** budgets per prediction: Scalar uses one setting and Multi splits the budget between two. These are simulated measurement outcomes, not Aer/device-noise or physical shots. Release preparation does not repeat these experiments.

The findings concern four small synthetic binary task families on classical CPU hardware. Eight population differences per task and small-sample t assumptions limit generalization. Historical cross-version scores are context, not paired improvement evidence. No physical-QPU performance, device-noise tolerance, full language-architecture benchmark or quantum advantage is established.

### Downloads and release-packaging checks

Download each ZIP with its matching `.seal.json`, check the external identity and safe extraction, then open `START_HERE.md`.

| Download | Contents |
| --- | --- |
| `QPathformer_v0.7_Study.zip` | Preserved report in PDF and Word, edition note, rights and provenance |
| `QPathformer_v0.7_Documentation.zip` | Updated overview, findings, original guidance and reproduction boundaries |
| `QPathformer_v0.7_Code.zip` | Selected models, audits, classical conversion, ETEL execution integration and bounded startup tools |

The Study ZIP/seal and report bytes are reused unchanged. The [visual-review clarification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/b5284a346b21d86c663df01e239aa56f49a07fa5/release_preparation/study-v0.7/revisions/draft_20261030_r3/report/VISUAL_REVIEW_CLARIFICATION.json) identifies a cross-study sentence in the retained receipt; it is not a report erratum or new all-page visual review.

Bounded startup verifies exact package integrity before and after execution, parses all 52 Python files, imports NumPy/SciPy and selected modules, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful `--help` from `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`. It does not test all eight model families, independently compare matrices, run conversion parity, execute ETEL fits/recovery, score official data or rerun timing/sampling. See the final receipts for actual execution against the revised assets. Historical scientific verification is separate from these packaging checks.

Raw datasets, trained checkpoints, installed environments and the full archive are excluded. Full replay requires separately retained inputs and reviewed environment/path bindings. Seals are integrity records, not digital signatures.

[Exact package identities](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/b5284a346b21d86c663df01e239aa56f49a07fa5/release_preparation/study-v0.7/revisions/draft_20261030_r3/PACKAGE_INDEX.json) · [Fresh extraction and startup](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/b5284a346b21d86c663df01e239aa56f49a07fa5/release_preparation/study-v0.7/revisions/draft_20261030_r3/receipts/FRESH_PACKAGE_VERIFICATION.json) · [Package verification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/b5284a346b21d86c663df01e239aa56f49a07fa5/release_preparation/study-v0.7/revisions/draft_20261030_r3/receipts/ROOT_PACKAGE_VERIFICATION.json) · [Source inventory](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/b5284a346b21d86c663df01e239aa56f49a07fa5/release_preparation/study-v0.7/revisions/draft_20261030_r3/receipts/SOURCE_INVENTORY.json).

### Scoped licensing

Identified original report content and explanatory prose use **CC BY 4.0**. The exact selected Python files, including the retained ETEL files and package helpers, are **source available under the unchanged Q-Pathformer Platform License 1.0**. Existing applicable grants remain in force. Package scopes identify exclusions; dependencies, datasets, trained models, architecture documents and whole archives retain separate terms. [Owner licensing record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/b5284a346b21d86c663df01e239aa56f49a07fa5/release_preparation/study-v0.7/revisions/draft_20261030_r3/OWNER_LICENSE_AUTHORIZATION.json).

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony is licensor; affiliations do not transfer ownership.

Published on 30 October 2026 in the private repository. Repository access remains restricted; publication does not change the adopted scoped licences. Study v0.9.5 remains designated Latest.

[Historical prepublication asset verification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/0f7dea4575f0ac8313e70a3dcf4afd74618f51ee/release_preparation/study-v0.7/revisions/draft_20261030_r3/DRAFT_RELEASE.json).
