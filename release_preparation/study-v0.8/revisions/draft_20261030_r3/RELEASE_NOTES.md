**Draft for owner review · Private repository · Study · Documentation · Code**

Q-Pathformer v0.8 asks whether giving higher-loss training examples more sampling opportunities helps models with fixed input routing. It compares uniform and priority sampling across five circuit and classical model designs on checkerboard, spiral, noisy-annulus and rare-disk tasks.

### Historical findings

Four of eight prespecified direct comparisons supported lower common clipped binary cross-entropy (BCE; lower is better) with priority sampling. The other four were inconclusive. None established an absolute reduction greater than 0.01 BCE across its entire adjusted interval.

| Task | Circuit MultiK | Routed TrigK |
| --- | --- | --- |
| Checkerboard | Inconclusive | Lower BCE with priority |
| Spiral | Inconclusive | Lower BCE with priority |
| Noisy annulus | Inconclusive | Inconclusive |
| Rare disks | Lower BCE with priority | Lower BCE with priority |

Priority did not close the routed circuit’s gap to the wider global trigonometric baseline on checkerboard or spiral. Macro-F1 is descriptive; a higher F1 need not imply lower BCE. The findings support further work on representation and routing, with priority retained as an optional training policy.

The twenty primary comparisons use paired population-mean differences and nominal 99.75% Bonferroni t intervals (df = 7). Two seed differences are averaged within each population; sixteen endpoints are not sixteen independent populations. Native-logit BCE used for training is a separate diagnostic.

### What changed in this study

The study completed 40 short engineering fits, 80 development fits and 640 confirmation fits. Five base models—MultiK, MultiHash, TrigK, TrigHash and TrigG121—each have uniform and priority arms. Confirmation uses eight independent populations per task and two paired optimizer seeds within each population.

The included adapter belongs to **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1** and retains historical vendor source version **0.2.0**. Priority sampling chooses training examples; model routing chooses the predictor bank for an input; ETEL coordinates complete training fits. At most five fit processes ran concurrently; 64 logical slots are bookkeeping, not a measured speedup. Repository v1.0, study v0.8 and ETEL versions identify different things.

### Historical verification and limitations

Four preselected clean-directory retrains reproduced earlier configurations in the historical environment; they add no independent populations. Conversion checked 256 circuit coefficient tables and 384 trigonometric repacks, with maximum independent probability discrepancy below 2.62e−14 and no checked class changes. These are representations of existing predictors, not additional efficacy arms.

Reported paired CPU latency ratios favored compiled circuits, but all three timing sessions varied and loading was excluded. Conversion adds no accuracy or compression claim. Detailed results and boundaries remain in the report and Documentation overview.

All results use classical CPU computation; v0.8 includes no physical-QPU run or new finite-shot experiment. Four synthetic binary task families and eight independent populations per task limit generalization. No quantum advantage or universal training benefit is established.

### Downloads and release-packaging checks

Download each ZIP with its matching `.seal.json`, verify it, then open `START_HERE.md`.

| Download | Contents |
| --- | --- |
| `QPathformer_v0.8_Study.zip` | Preserved PDF/Word report, viewing guidance, rights and provenance |
| `QPathformer_v0.8_Documentation.zip` | Updated overview, findings, original guidance and reproduction boundaries |
| `QPathformer_v0.8_Code.zip` | Selected scientific implementation, ETEL adapter and corrected bounded verification tools |

Use the supplied PDF for the reviewed page layout. The Word edition preserves the editable report content, but pagination and table rendering can vary by application. Check all table rows before exporting a replacement PDF. The [current clarification](report/VISUAL_REVIEW_CLARIFICATION.json) corrects a cross-study reference in preserved visual-review metadata. Report PDF/DOCX bytes remain unchanged.

Bounded startup verifies package integrity before and after execution, parses all 85 selected Python files, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful help output from three CLI paths. It does not run training, official scoring, conversion parity, timing, ETEL fits/recovery or QPU work. Raw data, checkpoints, environments and the complete archive are excluded. Full replay needs separately retained inputs. Seals are integrity records, not digital signatures.

[Exact package identities](PACKAGE_INDEX.json) · [Fresh startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Package verification](receipts/ROOT_PACKAGE_VERIFICATION.json) · [Source inventory](receipts/SOURCE_INVENTORY.json).

### Scoped licensing

Identified original report content and explanatory prose use **CC BY 4.0**. Exact selected Python files, including retained ETEL files and package helpers, are **source available under the unchanged Q-Pathformer Platform License 1.0**. Existing applicable grants remain in force. Dependencies, datasets, trained models, architecture documents and full archives retain separate terms; package scopes identify covered content and exclusions. [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.

This remains a draft in the private repository. **Study v0.9.5 remains Latest.**
