# Study v0.7 release notes

Q-Pathformer v0.7 examines whether grouping nearby inputs into specialist model banks improves classification, and how trained circuit models can run through an equivalent classical representation. Its advances are independent population replication, matched-count routing controls, a wider classical feature baseline and study-specific execution integration.

Eight model recipes were compared on checkerboard, spiral, noisy annulus and rare disks. Confirmation uses eight independently generated populations per task, with two paired optimizer seeds within each population. The completed design has 32 engineering, 64 development and 512 confirmation fits: 608 total. The 576 full fits completed 200 rounds and 15,000 updates each.

## Historical findings

Common clipped BCE is primary.

| Recipe | Checkerboard | Spiral | Noisy annulus | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Flexible circuit (MultiK) | 0.50907 | 0.37167 | 0.39927 | 0.01562 |
| Routed Trig25 | 0.26559 | 0.24968 | 0.39400 | 0.01314 |
| Global Trig121 | 0.04971 | 0.07878 | 0.39457 | 0.00827 |

Geometric routing achieved lower common clipped BCE than matched-count hash routing for both Multi and Trig25 on all four task families. All eight adjusted routing intervals favor geometric routing; seven establish improvement beyond the 0.01 practical reference, with rare-disk Trig the exception. The result concerns the tested data, feature representations and optimization, not universal routing superiority.

Classical conversion preserved every checked class prediction. For matched single-input CPU calls, reported speedups were **4.28–4.58× relative to the original circuit implementation**. Conversion changes how the same fitted predictor is evaluated; it adds no accuracy gain, compression or quantum-advantage claim. The MLP is fastest in the timing tables, and learned Trig controls use the optimized common kernel.

The Code package includes the study-specific execution integration for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**, using retained ETEL source version **0.2.0**. It schedules complete registered fits in isolated local processes. The component label, historical source version, study v0.7 and repository edition v1.0 identify different things. This selection is not a standalone ETEL component release.

## Verification and limits

The findings concern four small synthetic binary task families on classical CPU hardware. Eight population differences per task and small-sample t assumptions limit generalization. Historical cross-version scores are context, not paired improvement evidence. No physical-QPU performance, device-noise tolerance, full language-architecture benchmark or quantum advantage is established.

Bounded startup verifies exact package integrity before and after execution, parses all 52 Python files, imports NumPy/SciPy and selected modules, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful `--help` from `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`. It does not test all eight model families, independently compare matrices, run conversion parity, execute ETEL fits/recovery, score official data or rerun timing/sampling.

The report and Study ZIP/seal remain unchanged. Current documentation and package helpers have revised identities, with historical evidence preserved. Read the [overview](OVERVIEW.md) and [rights](RIGHTS.md).

Identified original report content and explanatory prose use **CC BY 4.0**. The exact selected Python files, including the retained ETEL files and package helpers, are **source available under the unchanged Q-Pathformer Platform License 1.0**. Existing applicable grants remain in force. Package scopes identify exclusions; dependencies, datasets, trained models, architecture documents and whole archives retain separate terms.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony is licensor; affiliations do not transfer ownership.
