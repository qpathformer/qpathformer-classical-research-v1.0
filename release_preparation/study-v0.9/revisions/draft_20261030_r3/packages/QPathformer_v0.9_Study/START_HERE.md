# Q-Pathformer study v0.9 Study

Q-Pathformer v0.9 tests whether learning how inputs are shared among small experts improves prediction beyond fixed routing and an equally sized output correction. It compares circuit emulation and classical models on four synthetic classification tasks, with a separate Banknote Authentication check.

Across twelve registered comparisons against fixed-soft routing (C_S), a parameter-count-matched output residual (C_R) and the global G121 control, the learned-soft circuit model (C_L) had lower common clipped binary cross-entropy (BCE; lower is better) in five, higher loss in three and inconclusive differences in four.

Three favorable intervals established an absolute reduction greater than 0.01 BCE: C_L versus C_S on spiral and rare disks, and C_L versus G121 on noisy annulus. The annulus result compares model families; its direct routing-control comparisons remained inconclusive. Neither favorable C_L-versus-C_R interval establishes improvement greater than 0.01 throughout the interval.

G121 remained substantially stronger on checkerboard and spiral and held a smaller BCE advantage on rare disks. A four-feature MLP led the descriptive Banknote check, where most other models received two PCA-derived inputs. The results support task-dependent choices and further work on routing and representation.

This study includes the study-specific execution adapter for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**. Its retained vendor source records version **0.2.0**. ETEL coordinates complete training fits; the learned router controls expert mixture weights within a predictor.

Read the [report PDF](reports/QPathformer_v0.9_Report_Edition_1.pdf), [Word report](reports/QPathformer_v0.9_Report_Edition_1.docx) and [edition changes](provenance/EDITION_CHANGES.md), [rights](RIGHTS.md), [verification guidance](VERIFY.md) and [source map](SOURCE_MAP.json). Repository edition v1.0 and study v0.9 are separate identifiers.

Full historical replay also requires the accepted versioned recovery entrypoints, supporting contracts and protocols, qualification sources and operational bindings retained with the complete study evidence. Some included entrypoints preserve earlier historical implementations. The curated Code ZIP supports source inspection and bounded startup; it does not contain every component used by the final accepted replay.

All results use classical CPU computation. No physical-QPU performance, quantum advantage, universally superior model or broad real-world generalization is established. v0.9 includes no new finite-shot campaign.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.
