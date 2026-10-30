# Study v0.9 release notes

Q-Pathformer v0.9 tests whether learning how inputs are shared among small experts improves prediction beyond fixed routing and an equally sized output correction. It compares circuit emulation and classical models on four synthetic classification tasks, with a separate Banknote Authentication check.

## Historical findings

Across twelve registered comparisons against fixed-soft routing (C_S), a parameter-count-matched output residual (C_R) and the global G121 control, the learned-soft circuit model (C_L) had lower common clipped binary cross-entropy (BCE; lower is better) in five, higher loss in three and inconclusive differences in four.

| Task | C_L versus fixed-soft C_S | C_L versus residual C_R | C_L versus global G121 |
| --- | --- | --- | --- |
| Checkerboard | Inconclusive | Inconclusive | Higher BCE |
| Spiral | Lower BCE | Lower BCE | Higher BCE |
| Noisy annulus | Inconclusive | Inconclusive | Lower BCE |
| Rare disks | Lower BCE | Lower BCE | Higher BCE |

Three favorable intervals established an absolute reduction greater than 0.01 BCE: C_L versus C_S on spiral and rare disks, and C_L versus G121 on noisy annulus. The annulus result compares model families; its direct routing-control comparisons remained inconclusive. Neither favorable C_L-versus-C_R interval establishes improvement greater than 0.01 throughout the interval.

G121 remained substantially stronger on checkerboard and spiral and held a smaller BCE advantage on rare disks. A four-feature MLP led the descriptive Banknote check, where most other models received two PCA-derived inputs. The results support task-dependent choices and further work on routing and representation.

Confirmation included 636 fits: 576 across four synthetic families and 60 on Banknote. Synthetic inference uses eight independent populations per task, with two paired optimizer seeds. Banknote uses one grouped split with five optimizer seeds. Four additional retrains check selected results in the historical environment; they do not add independent populations.

This study includes the study-specific execution adapter for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**. Its retained vendor source records version **0.2.0**. ETEL coordinates complete training fits; the learned router controls expert mixture weights within a predictor.

## Verification and limits

Bounded startup verifies exact package integrity before and after execution, parses all 57 Python files, checks two in-memory circuit inputs and a sigmoid calculation, and requires three successful CLI help paths. It does not exercise all model variants, Banknote preprocessing, complete accepted replay, conversion parity or ETEL recovery.

Full historical replay also requires the accepted versioned recovery entrypoints, supporting contracts and protocols, qualification sources and operational bindings retained with the complete study evidence. Some included entrypoints preserve earlier historical implementations. The curated Code ZIP supports source inspection and bounded startup; it does not contain every component used by the final accepted replay.

All three wrapper packages have revised identities. Scientific sources, protocols, reports, historical provenance and legal texts remain unchanged. No earlier page-37 or alternate-render defect is carried over.

All results use classical CPU computation. No physical-QPU performance, quantum advantage, universally superior model or broad real-world generalization is established. v0.9 includes no new finite-shot campaign.

Read the [overview](OVERVIEW.md), [reproduction boundaries](REPRODUCTION_BOUNDARIES.md) and [rights](RIGHTS.md).

CC BY 4.0 applies to identified controlled original report content and listed explanatory prose. The unchanged Q-Pathformer Platform License 1.0 applies to exact selected Python files, including the retained ETEL files and package helpers; these are source available. Adopted scopes identify covered content and exclusions. Earlier permissions and separate third-party terms remain in force; datasets, trained models, architecture documents and full archives retain separate treatment.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.
