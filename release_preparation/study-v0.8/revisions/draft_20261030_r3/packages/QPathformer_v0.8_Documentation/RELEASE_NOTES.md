# Study v0.8 release notes

Q-Pathformer v0.8 asks whether giving higher-loss training examples more sampling opportunities helps models with fixed input routing. It compares uniform and priority sampling across five circuit and classical model designs on checkerboard, spiral, noisy-annulus and rare-disk tasks.

The study completed 40 short engineering fits, 80 development fits and 640 confirmation fits. Five base models—MultiK, MultiHash, TrigK, TrigHash and TrigG121—each have uniform and priority arms. Confirmation uses eight independent populations per task and two paired optimizer seeds within each population.

## Historical findings

Four of eight prespecified direct comparisons supported lower common clipped binary cross-entropy (BCE; lower is better) with priority sampling. The other four were inconclusive. None established an absolute reduction greater than 0.01 BCE across its entire adjusted interval.

| Task | Circuit MultiK | Routed TrigK |
| --- | --- | --- |
| Checkerboard | Inconclusive | Lower BCE with priority |
| Spiral | Inconclusive | Lower BCE with priority |
| Noisy annulus | Inconclusive | Inconclusive |
| Rare disks | Lower BCE with priority | Lower BCE with priority |

Priority did not close the routed circuit’s gap to the wider global trigonometric baseline on checkerboard or spiral. Macro-F1 is descriptive; a higher F1 need not imply lower BCE. The findings support further work on representation and routing, with priority retained as an optional training policy.

The included adapter belongs to **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1** and retains historical vendor source version **0.2.0**. Priority sampling chooses training examples; model routing chooses the predictor bank for an input; ETEL coordinates complete training fits.

## Verification and limits

All results use classical CPU computation; v0.8 includes no physical-QPU run or new finite-shot experiment. Four synthetic binary task families and eight independent populations per task limit generalization. No quantum advantage or universal training benefit is established.

Bounded startup verifies package integrity before and after execution, parses all 85 selected Python files, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful help output from three CLI paths. It does not run training, official scoring, conversion parity, timing, ETEL fits/recovery or QPU work.

All three package pairs have revised wrapper identities; the report PDF/DOCX, scientific source, historical provenance and legal texts remain unchanged.

Use the supplied PDF for the reviewed page layout. The Word edition preserves the editable report content, but pagination and table rendering can vary by application. Check all table rows before exporting a replacement PDF.

Read the [overview](OVERVIEW.md) and [rights](RIGHTS.md).

Identified original report content and explanatory prose use **CC BY 4.0**. Exact selected Python files, including retained ETEL files and package helpers, are **source available under the unchanged Q-Pathformer Platform License 1.0**. Existing applicable grants remain in force. Dependencies, datasets, trained models, architecture documents and full archives retain separate terms; package scopes identify covered content and exclusions.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.
