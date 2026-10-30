# Q-Pathformer study v0.8 Code

Q-Pathformer v0.8 asks whether giving higher-loss training examples more sampling opportunities helps models with fixed input routing. It compares uniform and priority sampling across five circuit and classical model designs on checkerboard, spiral, noisy-annulus and rare-disk tasks.

Four of eight prespecified direct comparisons supported lower common clipped binary cross-entropy (BCE; lower is better) with priority sampling. The other four were inconclusive. None established an absolute reduction greater than 0.01 BCE across its entire adjusted interval.

Priority did not close the routed circuit’s gap to the wider global trigonometric baseline on checkerboard or spiral. Macro-F1 is descriptive; a higher F1 need not imply lower BCE. The findings support further work on representation and routing, with priority retained as an optional training policy.

The included adapter belongs to **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1** and retains historical vendor source version **0.2.0**. Priority sampling chooses training examples; model routing chooses the predictor bank for an input; ETEL coordinates complete training fits.

Read the [quickstart](QUICKSTART.md), [source selection](SOURCE_SELECTION.json), [dependencies](DEPENDENCY_INVENTORY.json) and [earlier permissions](INHERITED_LICENSE_MAP.json), [rights](RIGHTS.md), [verification guidance](VERIFY.md) and [source map](SOURCE_MAP.json). The companion Study package contains the preserved report in PDF and Word.

Use the supplied PDF for the reviewed page layout. The Word edition preserves the editable report content, but pagination and table rendering can vary by application. Check all table rows before exporting a replacement PDF.

Bounded startup verifies package integrity before and after execution, parses all 85 selected Python files, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful help output from three CLI paths. It does not run training, official scoring, conversion parity, timing, ETEL fits/recovery or QPU work.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.
