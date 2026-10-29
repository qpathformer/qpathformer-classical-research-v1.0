# A guide to the research

[Main README](../README.md) · [Latest study](../release_notes/study-v0.9.5.md) · [Reproduction limits](REPRODUCIBILITY.md)

## Four separate decisions

| Decision | Purpose | Study context |
|---|---|---|
| Prediction and routing | Select a specialist or combine predictions. | Especially v0.3–v0.9. |
| Example sampling | Choose examples for the next update. | Uniform versus importance-corrected priority sampling in v0.8. |
| Training allocation | Choose which recipe receives more training. | Fixed, capped successive halving and ETEL suitability in v0.9.5. |
| Execution | Coordinate bounded work, preserve recovery records and account for resources. | ETEL execution workflows documented from v0.7. |

A router is part of a predictor. An allocation policy manages competing recipes. Execution infrastructure supports both but does not establish that an allocation policy improves prediction or efficiency.

## Circuit models and classical comparisons

Small quantum circuits are emulated on classical hardware. Inputs determine features, trained angles alter the response, and a readout turns measured quantities into probabilities. In v0.6–v0.8, circuit experts have a two-qubit, two-layer core with eight trainable core angles; routed configurations use five parameter banks. These are different counts: five separately emulated two-qubit experts do not form a coherent ten-qubit system.

Hard routing selects one expert. Fixed-soft routing combines predictions with fixed geometric weights. Learned-soft routing adjusts those weights; in v0.9 all five experts are evaluated. A residual control adds equally many trainable parameters after expert predictions. Matching parameter counts does not match function classes or computation.

| Model label | Meaning |
|---|---|
| Scalar / Multi | Circuit measurement/readout recipes; definitions vary by study. |
| C_H / C_S / C_L / C_R | v0.9 circuit hard, fixed-soft, learned-soft and fixed-soft-plus-residual variants. |
| T_H / T_S / T_L / T_R | Corresponding trigonometric expert controls. |
| Trig25 / TrigK / TrigHash | Classical trigonometric models with study-specific routing and features. |
| G121 / TrigG121 | Wider global trigonometric model with 121 parameters. |
| MLP | Conventional multilayer perceptron control. |
| Recipe / portfolio | A model with training settings / the six recipes managed by a v0.9.5 allocation policy. |

The v0.5 Scalar comparison changed the output link, learned readout and native loss together; its full gain cannot be attributed to readout alone. Early AG News and DBpedia14 encoder experiments form a separate branch with different class counts and GPU work.

## The benchmarks

The v0.6 four-task suite samples coordinates x and y uniformly in [−1, 1]. These formulas define analytic regions; later studies have their own population, split and budget records.

| Task | Positive region |
|---|---|
| Spiral | sin(2 atan2(y, x) + 4π √(x²+y²)) > 0. |
| Checkerboard | sin(3πx + π/7) sin(3πy + π/5) > 0. |
| Rare disks | Within radius 0.22 of (−0.55, −0.45), (0.50, −0.35) or (0, 0.55), about 11.4% of the square. |
| Noisy annulus | Latent label 0.25 < x²+y² < 0.85, then independent label flips with probability 0.10. |

The [figures](../assets/ILLUSTRATIONS.md) display these regions; the annulus shows the latent label. Earlier circle/disk and ellipse populations differ. v0.9 also includes a descriptive Banknote Authentication check with one grouped split and five optimization seeds, not five independent datasets.

## Reading findings

Binary cross-entropy (BCE) evaluates probabilities; lower is better. Macro-F1 evaluates thresholded classifications with equal class weight; higher is better. Keep the registered primary outcome visible. An interval crossing the stipulated improvement threshold is inconclusive, not proof of equivalence.

v0.9 uses primary BCE after clipping probabilities to [1e−7, 1−1e−7]. v0.9.5 selects checkpoints and compares hidden-test results using stable, unclipped native Bernoulli loss; its clipped scores are descriptive. Their raw scores are not a matched progress curve. Independent populations, optimization seeds, fits and replay actions carry different meanings.

Exact classical conversion concerns the same fitted circuit prediction function. Faster CPU inference does not demonstrate a physical-QPU advantage, nor does it create an accuracy gain. The original study reports remain the authority for completed findings. The final v0.9.5 report edition is supplied in the companion Study package; other internal report editions remain separately retained. Source identities and selected provenance accompany the packages.
