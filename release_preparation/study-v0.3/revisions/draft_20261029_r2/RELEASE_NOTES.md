# Q-Pathformer Study v0.3 — Shallow Circuits and Routing

**Draft release for owner review.** Repository edition v1.0 is separate from study v0.3.

All 104 registered training runs completed: 39 development and 65 confirmation. Thirteen methods continued to five-seed confirmation on fresh synthetic circle data. Independent replay checked 65 endpoints, 104000 predictions and 150 saved shot arrays.

Confirmation mean macro-F1 was 97.42% for k-means routed depth-two circuits, 90.10% for hash routing with the same 40 circuit angles, 94.06% for a fixed depth-four circuit and 98.70% for the larger classical MLP. Routing improved the circuit model, while the spatial partition also added classical capacity.

One synthetic task and five confirmation training seeds do not establish quantum advantage or real-domain generalization. A development numerical-threshold failure and a verification-only pre-confirmation amendment are preserved in the historical evidence. Confirmation had zero ambiguous predictions. Local Aer checks used 150 circuits and 3840000 simulated measurement shots; separate probability-level binomial analysis is not hardware execution or device-noise simulation.

| Download | Contents |
| --- | --- |
| QPathformer_v0.3_Study.zip | Preserved PDF and Word report with edition note, scope and provenance |
| QPathformer_v0.3_Documentation.zip | Study overview, original guidance, findings and reproduction boundaries |
| QPathformer_v0.3_Code.zip | Selected unchanged implementation, dependency inventory and bounded startup helper |

Each ZIP has its matching external `.seal.json`. [Package identities](receipts/PACKAGE_INDEX.json), [fresh extraction and startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json), [report review](report/REPORT_REVIEW.json), and [source inventory](receipts/SOURCE_INVENTORY.json) identify the exact prepared assets.

Startup result: `PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP`. Full experiment reproduction, clean-room installation, shot sampling and QPU jobs were not performed. Datasets, checkpoints, full archives, installed environments and credentials are omitted. No ETEL is supplied by this study.

The owner adopted the same scoped licensing scheme as the earlier two studies: CC BY 4.0 for exact controlled original report and explanatory prose; unchanged Platform License 1.0 for exact selected Python. Each package includes its adoption record and precise scope. Existing grants remain in force; excluded materials retain separate terms.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliation does not transfer ownership. Repository visibility and publication remain separate from licensing.
