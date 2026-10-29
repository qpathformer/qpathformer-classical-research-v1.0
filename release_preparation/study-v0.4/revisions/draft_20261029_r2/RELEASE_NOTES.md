# Q-Pathformer Study v0.4 — Routing and Circuit Contribution

**Draft release for owner review.** Repository edition v1.0 is separate from study v0.4.

Nine combinations of model family and routing were evaluated: two-qubit depth-two circuits, raw-input ReLU MLPs and 25-feature trigonometric logit models, each with global, coordinate-hash or train-only k-means routing. All 54 development and 135 confirmation endpoints completed 200 rounds and 15000 optimizer updates. Confirmation covered two independent circle populations and a rotated ellipse.

Q2 k-means mean macro-F1 was 98.32%, 97.16% and 94.41% across the three confirmation populations. Spatial routing substantially improved Q2 relative to hash routing, but trigonometric k-means models had lower BCE throughout. Global MLP and trigonometric controls also outperformed Q2 k-means in mean F1 and BCE. Q2 versus the small routed MLP was unresolved across training seeds.

Five seeds, synthetic tasks, fixed routers and unequal capacities do not isolate a circuit-specific benefit or establish quantum advantage, equivalence, speed or real-world generalization. Seed intervals and conditional record bootstraps answer different questions. Local readiness covered 45 quantum checkpoints, 1440 validation fixture circuits and 720 measured Aer experiments totaling 737280 simulated shots; 199065600 represented binomial trials are separate. Illustrative noise is not device calibration.

| Download | Contents |
| --- | --- |
| QPathformer_v0.4_Study.zip | Preserved PDF and Word report with edition note, scope and provenance |
| QPathformer_v0.4_Documentation.zip | Study overview, original guidance, findings and reproduction boundaries |
| QPathformer_v0.4_Code.zip | Selected unchanged implementation, dependency inventory and bounded startup helper |

Each ZIP has its matching external `.seal.json`. [Package identities](receipts/PACKAGE_INDEX.json), [fresh extraction and startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json), [report review](report/REPORT_REVIEW.json), and [source inventory](receipts/SOURCE_INVENTORY.json) identify the exact prepared assets.

Startup result: `PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP`. Full experiment reproduction, clean-room installation, shot sampling and QPU jobs were not performed. Datasets, checkpoints, full archives, installed environments and credentials are omitted. No ETEL is supplied by this study.

The owner adopted the same scoped licensing scheme as the earlier two studies: CC BY 4.0 for exact controlled original report and explanatory prose; unchanged Platform License 1.0 for exact selected Python. Each package includes its adoption record and precise scope. Existing grants remain in force; excluded materials retain separate terms.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliation does not transfer ownership. Repository visibility and publication remain separate from licensing.
