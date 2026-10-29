**Draft for owner review · Private repository · Study · Documentation · Code**

Q-Pathformer v0.4 asks what shallow circuit models contribute when the same routing choices are also available to conventional models. This completed study is presented in **Q-Pathformer Classical Research, repository edition v1.0**. Study v0.4 and repository edition v1.0 are separate identifiers.

The study crosses three model families with three routing policies: a **two-qubit, depth-two circuit model (Q2)**, a raw-coordinate ReLU MLP and a 25-feature trigonometric sigmoid-logit model; each is evaluated globally, with coordinate-hash routing or with training-only k-means routing. Routed examples activate one of five parameter banks. The fixed k-means router is fitted to training coordinates without labels.

All **54 development and 135 confirmation endpoints** completed **200 rounds and 15,000 optimizer updates per endpoint**. Confirmation used five training seeds for every model/population combination across two independent circle populations and a rotated ellipse. All circuit execution was simulated on classical compute.

### Historical findings

**Binary cross-entropy (BCE) was the primary metric; lower is better.** Spatial k-means routing improved Q2 over its hash-routing control on all three confirmation populations. The following values are means over five confirmation training seeds; macro-F1 is secondary.

| Q2 k-means confirmation population | Mean test BCE | Mean macro-F1 |
| --- | ---: | ---: |
| Circle population 1 | 0.17689 | 98.32% |
| Circle population 2 | 0.18280 | 97.16% |
| Rotated ellipse | 0.21207 | 94.41% |

**The classical controls remained stronger.** Global MLP and global trigonometric models achieved lower mean BCE and higher mean macro-F1 on every confirmation population. Routed trigonometric models also achieved lower BCE than routed Q2 throughout. Q2's favorable mean BCE differences against the small routed MLP remain **unresolved across training seeds**: the adjusted paired-seed intervals include zero on all three populations. This is neither equivalence nor evidence of a general circuit advantage.

The nine registered primary contrasts use **99.4444% Bonferroni-adjusted intervals**. Paired-seed intervals and the separate 5,000-resample record bootstrap describe different sources of uncertainty. The record bootstrap conditions on the trained models; it does not add training replications or resolve training instability.

### Historical verification and limitations

Historical independent replay checked **135 endpoints and 216,000 checkpoint–record predictions**. Each population has 1,600 held-out test records shared by its 45 checkpoints; the prediction count is not a count of independent test cases. Replay verifies saved states, predictions and statistics; it is not a second execution of every optimizer update.

Local readiness checks covered all **45 circuit checkpoints** and included **737,280 simulated Aer measurement shots**. Separate conditional binomial diagnostics are documented in the report; no physical shots or hardware jobs are reported. Illustrative logical-noise scenarios are not device calibration or current IBM device qualification.

Five seeds, synthetic tasks, fixed routers and unequal model capacities do not isolate a circuit-specific benefit or establish quantum advantage, speed or real-world generalization. Validation crossings of the 97% macro-F1 milestone were learning diagnostics: every run completed its full budget, so they show neither realized early-stopping savings nor held-out performance at an earlier update. Original future-study recommendations remain historical recommendations; packaging adds no experiments or completed later studies.

### Downloads and release-packaging checks

Download each ZIP with its matching `.seal.json`, verify the external seal and safe extraction, then open `START_HERE.md`.

| Download | Contents |
| --- | --- |
| `QPathformer_v0.4_Study.zip` | Preserved PDF and Word report, edition note, rights scope and provenance |
| `QPathformer_v0.4_Documentation.zip` | Study overview, research guidance, historical findings and reproduction boundaries |
| `QPathformer_v0.4_Code.zip` | Selected scientific sources, dependency inventory, strict package verifier and bounded startup helper |

[Exact package identities](PACKAGE_INDEX.json) identify the selected ZIP/seal pairs and their actual build origins. Updated current guidance and package helpers require refreshed package inventories and seals. The original report, scientific sources and historical records are preserved.

**Release-packaging verification is separate from the historical study.** The bounded startup helper parses the selected Python files, checks finite in-memory predictions for the nine registered model/routing combinations, displays training CLI help and runs the selected full-matrix agreement invariant. It does not rerun training, historical scientific replay, shot sampling or QPU jobs, and does not establish installation from scratch or every optional dependency. Consult the final receipts for the checks performed against the selected assets.

Datasets, checkpoints, complete operational archives, installed environments and credentials are omitted. Exact historical replay requires the retained inputs, recorded dependency versions and reviewed path bindings. Historical full-archive commands are evidence, not a batch to run in these curated downloads. No ETEL implementation is supplied.

[Fresh extraction and startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Independent package verification](receipts/ROOT_PACKAGE_VERIFICATION.json) · [Report review](report/REPORT_REVIEW.json) · [Source inventory](receipts/SOURCE_INVENTORY.json).

### Scoped licensing

The owner adopted **CC BY 4.0** for identified controlled original report content and selected explanatory prose. The exact selected Python files and helpers are **source available under the unchanged Q-Pathformer Platform License 1.0**. Each package contains its adoption record and precise scopes. Earlier grants remain in force. Third-party materials, dependencies, datasets, checkpoints, architecture documents and full archives retain their separate terms; neither licence is a blanket grant for the entire package. [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains the licensor; affiliation does not transfer ownership.

This release remains a draft in the private repository. The publisher's public release remains subject to owner review. This does not limit reuse permitted under the adopted CC BY 4.0 grant. Scoped licensing is adopted separately from publication. **Study v0.9.5 remains Latest.**
