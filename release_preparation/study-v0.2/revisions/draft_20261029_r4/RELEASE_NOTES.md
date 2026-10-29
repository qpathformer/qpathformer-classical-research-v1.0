**Draft for owner review · Private repository · Study · Documentation · Code**

Q-Pathformer v0.2 tested two design questions: whether stable text routing improves classification, and whether separate parameter banks improve small circuits that operate at different depths. This completed study is presented in **Q-Pathformer Classical Research, repository edition v1.0**; the repository edition and study version are separate identifiers.

The work combines a classical GPU text experiment on **DBpedia14 title-plus-content classification** with a separate synthetic circuit experiment. All **94 registered main runs** (27 text and 67 circuit-study runs) and **eight separate common text warmups** completed. Confirmation covered 15 text endpoints and 40 circuit-study endpoints, including classical controls in the latter.

### Main findings

**Text routing:** Hash18 reached **97.659% macro-F1**, compared with **97.642%** for current content routing and **97.602%** for shared adapters. Its primary mean gain over current content routing was **0.01694 percentage points**, with paired seed t95 interval **[-0.11024, +0.14412]**. The interval includes zero; the study did not establish a resolved primary improvement.

**Circuit parameters:** Giving each depth its own parameter bank improved the selected comparison with the original shared-parameter schedule. Untied assigned circuits reached **81.44% macro-F1**, compared with **71.83%** for the shared schedule. The change increased allocated angles from **16 to 40**. The fixed four-layer circuit reached **93.32%**, and the matched-information classical **MLP129 reached 99.04%**. The primary circuit comparison used binary cross-entropy: untied assigned minus shared schedule was **-0.14441**, with paired seed t95 interval **[-0.15434, -0.13449]**; lower is better. F1 is secondary.

The text experiment used a classical GPU; the quantum circuits were simulated locally. No physical-QPU execution or quantum advantage is reported. These are separate models on separate tasks, not an integrated quantum text model. The parameter-bank comparison does not isolate a scheduling or gradient-interference benefit, and MLP129 is information-matched rather than parameter- or compute-matched.

### Downloads

| Download | Contents | External seal |
| --- | --- | --- |
| `QPathformer_v0.2_Study.zip` | Preserved PDF and Word report, report rights and provenance | `QPathformer_v0.2_Study.seal.json` |
| `QPathformer_v0.2_Documentation.zip` | Research guide, findings, reproduction boundaries and historical guidance | `QPathformer_v0.2_Documentation.seal.json` |
| `QPathformer_v0.2_Code.zip` | Selected unchanged scientific sources, package helpers and bounded offline startup | `QPathformer_v0.2_Code.seal.json` |

The packages omit datasets, checkpoints, installed environments and complete operational archives. Code startup checks imports, in-memory predictions, an explicit invariant, CLI help and a small CPU text forward; it does not establish full reproduction or a clean-room installation. Verify each ZIP and seal before use. [Exact download sizes and SHA-256 values](PACKAGE_INDEX.json) identify this candidate.

### Rights and verification

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains the licensor. **CC BY 4.0** applies to identified controlled original report content and explanatory prose; **Q-Pathformer Platform License 1.0** applies to the exact selected Python files and helpers. The package scope records identify covered content. Existing grants remain applicable; datasets, dependencies, checkpoints and full archives are outside these grants. [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).

The report PDF/DOCX and the 40 scientific Python files retain their reviewed bytes. This candidate corrects the active scientific summaries, clarifies publisher review versus CC BY reuse, and strengthens receipt creation and package-integrity checks in the two helpers.

[Independent package verification](receipts/ROOT_PACKAGE_VERIFICATION.json) · [Fresh Code startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Report preservation and visual review](report/REPORT_REVIEW.json) · [Source inventory](receipts/SOURCE_INVENTORY.json).

This remains a private draft for owner review. The publisher's public release remains subject to owner review; this does not limit reuse under the adopted CC BY 4.0 grant. Study v0.9.5 remains designated Latest.
