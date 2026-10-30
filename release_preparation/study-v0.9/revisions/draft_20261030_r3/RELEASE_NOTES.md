**Draft for owner review · Private repository · Study · Documentation · Code**

Q-Pathformer v0.9 tests whether learning how inputs are shared among small experts improves prediction beyond fixed routing and an equally sized output correction. It compares circuit emulation and classical models on four synthetic classification tasks, with a separate Banknote Authentication check.

### Historical findings

Across twelve registered comparisons against fixed-soft routing (C_S), a parameter-count-matched output residual (C_R) and the global G121 control, the learned-soft circuit model (C_L) had lower common clipped binary cross-entropy (BCE; lower is better) in five, higher loss in three and inconclusive differences in four. Table entries describe C_L relative to the named control.

| Task | C_L versus fixed-soft C_S | C_L versus residual C_R | C_L versus global G121 |
| --- | --- | --- | --- |
| Checkerboard | Inconclusive | Inconclusive | Higher BCE |
| Spiral | Lower BCE | Lower BCE | Higher BCE |
| Noisy annulus | Inconclusive | Inconclusive | Lower BCE |
| Rare disks | Lower BCE | Lower BCE | Higher BCE |

Three favorable intervals established an absolute reduction greater than 0.01 BCE: C_L versus C_S on spiral and rare disks, and C_L versus G121 on noisy annulus. The annulus result compares model families; its direct routing-control comparisons remained inconclusive. Neither favorable C_L-versus-C_R interval establishes improvement greater than 0.01 throughout the interval.

G121 remained substantially stronger on checkerboard and spiral and held a smaller BCE advantage on rare disks. A four-feature MLP led the descriptive Banknote check, where most other models received two PCA-derived inputs. The results support task-dependent choices and further work on routing and representation.

Synthetic primary comparisons use paired population-mean differences and nominal 99.5833% Bonferroni t intervals (df = 7). Native training loss is a separate diagnostic; macro-F1 is secondary.

### What changed in this study

Confirmation included 636 fits: 576 across four synthetic families and 60 on Banknote. Synthetic inference uses eight independent populations per task, with two paired optimizer seeds. Banknote uses one grouped split with five optimizer seeds. Four additional retrains check selected results in the historical environment; they do not add independent populations.

This study includes the study-specific execution adapter for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**. Its retained vendor source records version **0.2.0**. ETEL coordinates complete training fits; the learned router controls expert mixture weights within a predictor. v0.9 uses uniform sampling with replacement; v0.8's priority intervention is historical context. Repository v1.0, study v0.9 and the ETEL versions identify different things.

### Historical verification and limitations

Conversion covered 276 circuit predictors and 1,380 expert cores while retaining routing, gates, residuals and preprocessing. Checked predictions agreed to floating-point tolerance, and conversion reduced local inference latency relative to the original emulators. It does not establish the fastest overall model or compression.

The four clean retrains copied frozen source, data and protocols into new directories and reused the historical environment. Timing conditions are technical comparisons, not independent accuracy replications.

All results use classical CPU computation. No physical-QPU performance, quantum advantage, universally superior model or broad real-world generalization is established. v0.9 includes no new finite-shot campaign.

### Downloads and release-packaging checks

Download each ZIP with its matching `.seal.json`, verify it, then open `START_HERE.md`.

| Download | Contents |
| --- | --- |
| `QPathformer_v0.9_Study.zip` | Preserved PDF/Word report, edition note, current introduction, rights and provenance |
| `QPathformer_v0.9_Documentation.zip` | Updated study overview, research context and reproduction boundaries |
| `QPathformer_v0.9_Code.zip` | Selected scientific sources, ETEL adapter, dependency inventory and corrected startup tools |

Datasets, checkpoints, installed environments and full archives are excluded. Complete historical replay also requires separately retained accepted recovery implementations, supporting protocols and reviewed environment/path bindings.

Bounded startup verifies exact package integrity before and after execution, parses all 57 Python files, checks two in-memory circuit inputs and a sigmoid calculation, and requires three successful CLI help paths. It does not exercise all model variants, Banknote preprocessing, complete accepted replay, conversion parity or ETEL recovery. Release preparation runs no training, official scoring, timing, sampling or QPU jobs. [Report preservation review](report/REPORT_REVIEW_BOUNDARIES.json) records unchanged report identities and the applicable v0.9 disclosure context. Seals are integrity records, not digital signatures.

[Exact package identities](PACKAGE_INDEX.json) · [Fresh startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Package verification](receipts/ROOT_PACKAGE_VERIFICATION.json) · [Source inventory](receipts/SOURCE_INVENTORY.json).

### Scoped licensing

CC BY 4.0 applies to identified controlled original report content and listed explanatory prose. The unchanged Q-Pathformer Platform License 1.0 applies to exact selected Python files, including the retained ETEL files and package helpers; these are source available. Adopted scopes identify covered content and exclusions. Earlier permissions and separate third-party terms remain in force; datasets, trained models, architecture documents and full archives retain separate treatment. [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.

This remains a draft in the private repository. **Study v0.9.5 remains Latest.**
