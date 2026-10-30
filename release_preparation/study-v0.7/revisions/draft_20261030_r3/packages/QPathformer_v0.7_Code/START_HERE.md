# Q-Pathformer study v0.7 Code

Q-Pathformer v0.7 examines whether grouping nearby inputs into specialist model banks improves classification, and how trained circuit models can run through an equivalent classical representation. Its advances are independent population replication, matched-count routing controls, a wider classical feature baseline and study-specific execution integration.

Eight model recipes were compared on checkerboard, spiral, noisy annulus and rare disks. Confirmation uses eight independently generated populations per task, with two paired optimizer seeds within each population. The completed design has 32 engineering, 64 development and 512 confirmation fits: 608 total. The 576 full fits completed 200 rounds and 15,000 updates each.

Common clipped BCE is primary. Geometric routing achieved lower common clipped BCE than matched-count hash routing for both Multi and Trig25 on all four task families. All eight adjusted routing intervals favor geometric routing; seven establish improvement beyond the 0.01 practical reference, with rare-disk Trig the exception. The result concerns the tested data, feature representations and optimization, not universal routing superiority.

Classical conversion preserved every checked class prediction. For matched single-input CPU calls, reported speedups were **4.28–4.58× relative to the original circuit implementation**. Conversion changes how the same fitted predictor is evaluated; it adds no accuracy gain, compression or quantum-advantage claim. The MLP is fastest in the timing tables, and learned Trig controls use the optimized common kernel.

The Code package includes the study-specific execution integration for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**, using retained ETEL source version **0.2.0**. It schedules complete registered fits in isolated local processes. The component label, historical source version, study v0.7 and repository edition v1.0 identify different things. This selection is not a standalone ETEL component release.

Read the [quickstart](QUICKSTART.md), [source selection](SOURCE_SELECTION.json), [dependencies](DEPENDENCY_INVENTORY.json) and [earlier permissions](INHERITED_LICENSE_MAP.json), [rights](RIGHTS.md), [verification guidance](VERIFY.md) and [source map](SOURCE_MAP.json). The companion Study package contains the preserved report in PDF and Word.

Bounded startup verifies exact package integrity before and after execution, parses all 52 Python files, imports NumPy/SciPy and selected modules, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful `--help` from `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`. It does not test all eight model families, independently compare matrices, run conversion parity, execute ETEL fits/recovery, score official data or rerun timing/sampling.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony is licensor; affiliations do not transfer ownership.
