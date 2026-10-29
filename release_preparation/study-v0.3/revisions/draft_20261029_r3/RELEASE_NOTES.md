**Draft for owner review · Private repository · Study · Documentation · Code**

Q-Pathformer v0.3 examines shallow circuits, parameter sharing and routing on a synthetic circle task. This completed study is presented in **Q-Pathformer Classical Research, repository edition v1.0**. Study v0.3, report edition 1 and repository edition v1.0 are separate identifiers.

The historical study completed all **104 registered training runs: 39 development and 65 confirmation**. All 13 methods continued to five-seed confirmation on fresh synthetic circle data, using the same **1,600 held-out test records**. All circuit execution was simulated on classical compute.

### Historical findings

**Binary cross-entropy (BCE) was the primary metric; lower is better.** K-means routed depth-two circuits achieved mean BCE **0.1897**, compared with **0.2897** for hash routing using the same 40 circuit angles. The paired difference was **−0.1000**, with a Bonferroni-adjusted **98.333% seed interval of [−0.1232, −0.0769]**. The separate conditional record-bootstrap interval was **[−0.1139, −0.0873]** at the same confidence level. Both intervals lie below the registered **−0.01 practical threshold**; they describe different uncertainty sources and must not be pooled.

The following values are means over five confirmation training seeds. Macro-F1 is secondary.

| Confirmation method | Mean test BCE | Mean macro-F1 |
| --- | ---: | ---: |
| K-means routed depth two | 0.1897 | 97.42% |
| Hash-routed depth two | 0.2897 | 90.10% |
| Fixed depth four | 0.2673 | 94.06% |
| Classical MLP41 | 0.0767 | 96.42% |
| Classical MLP129 | 0.0275 | 98.70% |

The **+7.32 percentage-point** k-means-versus-hash macro-F1 difference is secondary and descriptive. Spatial routing improved the circuit model on this task while adding classical partitioning capacity. Both listed MLP controls achieved lower mean BCE; MLP129 also achieved the highest mean macro-F1. The report finds no classical-simulation speed advantage for the circuit model.

### Historical verification and limitations

Historical independent replay checked **65 endpoints**, **104,000 checkpoint–record predictions** and **150 saved binomial shot-count arrays**. The prediction count is 65 checkpoints × the same 1,600 test records; it is not 104,000 independent test cases. Separate local Aer checks used **150 circuits and 3,840,000 simulated measurement shots**. The saved binomial arrays and the Aer circuits describe different analyses. Neither was physical-QPU execution or device-noise simulation.

A development numerical-threshold audit failure and the verification-only amendment made before confirmation remain documented. Confirmation had no predictions inside the specified numerical ambiguity band; that does not mean zero classification errors or zero statistical uncertainty. The amendment did not change the training sources, budgets, canonical prediction rule or primary BCE analysis.

One synthetic task and five confirmation training seeds do not establish quantum advantage or real-domain generalization. The report preserves the classical controls, uncertainty qualifications, historical internal labels and full-archive paths. Package guidance defines what these curated downloads include; historical references to full-archive evidence directories and `Verify_Delivery.ps1` do not imply those materials are included here.

### Downloads and release-packaging checks

Download each ZIP with its matching `.seal.json`, verify the external seal and safe extraction, then open `START_HERE.md`.

| Download | Contents |
| --- | --- |
| `QPathformer_v0.3_Study.zip` | Preserved PDF and Word report, edition note, rights scope and provenance |
| `QPathformer_v0.3_Documentation.zip` | Study overview, research guidance, historical findings and reproduction boundaries |
| `QPathformer_v0.3_Code.zip` | Selected scientific sources, dependency inventory, strict package verifier and bounded startup helper |

[Exact package identities](PACKAGE_INDEX.json) identify the selected ZIP/seal pairs and their actual build origins. The Study and Documentation pairs retain their reviewed bytes and existing seals; the Code successor addresses inventory-path validation and startup safeguards.

**During release packaging**, the publisher recorded `PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP` against the selected final Code ZIP. The bounded check parses the selected Python files, checks finite in-memory predictions for the 13 registered methods, displays CLI help and runs the selected circuit-versus-matrix invariant. It does not rerun the training study, full historical scientific replay, shot sampling or QPU jobs, and does not establish installation from scratch or every optional dependency.

Datasets, checkpoints, complete operational archives, installed environments and credentials are omitted. Exact historical replay requires the retained inputs, recorded dependency versions and reviewed path bindings. No ETEL component is supplied.

[Fresh extraction and startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Independent package verification](receipts/ROOT_PACKAGE_VERIFICATION.json) · [Report review](report/REPORT_REVIEW.json) · [Source inventory](receipts/SOURCE_INVENTORY.json).

### Scoped licensing

The owner adopted **CC BY 4.0** for identified controlled original report content and selected explanatory prose, and the unchanged **Q-Pathformer Platform License 1.0** for the exact selected Python files and helpers. Each package contains its adoption record and precise scopes. Earlier grants remain in force. Third-party materials, dependencies, datasets, checkpoints, architecture documents and full archives retain their separate terms; neither licence is a blanket grant for the entire package. [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains the licensor; affiliation does not transfer ownership.

This release remains a draft in the private repository. Scoped licensing is adopted separately from publication. **Study v0.9.5 remains Latest.**
