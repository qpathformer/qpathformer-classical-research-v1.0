# Study v0.5 research guide

## Study design and endpoints

Q-Pathformer v0.5 examines how learned output heads change shallow circuit classifiers when compared with strong classical controls. Eleven recipes were evaluated on two independently generated circle populations and a rotated ellipse, using five paired training seeds and one fixed split per confirmation population. All circuit execution used classical compute.

The study completed 22 short engineering endpoints, 66 full development endpoints and 165 full confirmation endpoints. Every full endpoint completed 200 rounds and 15,000 optimizer updates. All eleven recipes continued to confirmation; early stopping was not used.

The eleven registered recipes comprise Legacy, Scalar, Multi, a random frozen-core control, four routed MLP controls (width four or eight, ReLU or tanh), routed Trig25, global Trig25 and a global MLP. Routed recipes use the fixed training-only k-means router and five parameter banks. The router is not relearned for each model, so this study does not re-establish the v0.4 routing-benefit claim. Labels are binary; five moments are observables, not classes.

Each depth-two circuit bank contains eight trainable angles when the core is trained. Legacy uses the probability link `(1 + X0) / 2` and clipped-probability training loss. Scalar uses `sigmoid(w X0 + b)` and stable native logit BCE. Multi extends that head to `X0`, `X1`, `Z0`, `Z1` and `Z0Z1`. Scalar versus Legacy changes the output link, head parameters, capacity and native loss together; it measures a complete recipe change, not an isolated readout effect. Legacy is trained within v0.5, not imported as a paired v0.4 result.

The Frozen control starts with the same random circuit core, leaves that core untrained and trains only its readout head. It is not pretrained. Its training and validation moments are cached, with cache creation/storage accounted for separately; raw-input inference still evaluates the circuit. Its poor result does not settle the usefulness of every frozen or pretrained encoder.

The primary endpoint is **common clipped BCE**, using natural logarithms and probabilities clipped to `[1e-7, 1-1e-7]`; lower is better. It is a bounded comparison/selection score, not the native objective of every recipe or a strictly proper score on the full raw probability interval. Keep it separate from native-logit loss and the later v0.9.5 endpoint. Macro-F1, raw Brier score and probability-quality diagnostics provide complementary information. The selected checkpoint is the earliest exact minimum of full validation clipped BCE across the 200 rounds.

## Historical findings

The following are means over five training seeds on the same 1,600 held-out records within each confirmation population. The original report retains every recipe and its uncertainty; these compact tables highlight the circuit and global classical comparisons.

| Recipe | Mean common clipped BCE: circle 1 | Circle 2 | Rotated ellipse |
| --- | ---: | ---: | ---: |
| Legacy | 0.22279 | 0.17937 | 0.21335 |
| Scalar | 0.01362 | 0.01676 | 0.02599 |
| Multi | 0.01315 | 0.01298 | 0.02096 |
| Random frozen core | 0.39163 | 0.44890 | 0.40698 |
| Trig25 routed | 0.01054 | 0.01201 | 0.01399 |
| Trig25 global | 0.01243 | 0.01425 | 0.02012 |
| MLP global | 0.01413 | 0.01784 | 0.02217 |

Macro-F1 is secondary:

| Recipe | Mean macro-F1: circle 1 | Circle 2 | Rotated ellipse |
| --- | ---: | ---: | ---: |
| Legacy | 95.22% | 97.08% | 94.69% |
| Scalar | 99.54% | 99.22% | 99.06% |
| Multi | 99.55% | 99.51% | 99.29% |
| Random frozen core | 81.36% | 76.43% | 82.67% |
| Trig25 routed | 99.77% | 99.56% | 99.59% |
| Trig25 global | 99.91% | 99.74% | 99.37% |
| MLP global | 99.70% | 99.35% | 99.17% |

The learned-readout recipes substantially improved on the same-study Legacy recipe. Scalar changes the probability link, head parameters, capacity and native training loss together, so this comparison does not isolate the readout's contribution. Five-moment Multi adds a smaller, task-dependent benefit over Scalar: both circle adjusted seed intervals include zero; the ellipse loss reduction is below the registered 0.01 practical reference. The random frozen-core control performed substantially worse.

On the ellipse, Multi minus Scalar has mean common BCE difference −0.0050 and adjusted seed interval [−0.0083, −0.0017]. It excludes zero but is smaller than the registered 0.01 practical reference. Both circle seed intervals include zero. This is not a formal equivalence result or evidence that five moments consistently improve every task/seed.

Routed Trig25 had the lowest mean common clipped BCE on all three confirmation populations. Its advantage over Multi was unresolved by the adjusted seed intervals on the circles and resolved on the ellipse. Trig25 controls combined high mean accuracy with much lower measured local execution time than the circuit recipes. These are measurements of the retained CPU implementations, not general hardware-efficiency or monetary-cost claims.

The global MLP is faster than Trig25 in the recorded measurements; Trig25 is not claimed to be the fastest method. Measured loop seconds include validation and evidence writes under concurrent seed workers. They are elapsed wall times, not process CPU seconds, isolated hardware benchmarks, energy estimates or cloud costs. Raw-input inference timings include routing and prediction after warmup, excluding loading/I/O; cache preparation is accounted for separately.

## Uncertainty and learning milestones

The registered primary family contains twelve contrasts: four paired BCE comparisons on each of three populations. Paired-seed t intervals use five differences, four degrees of freedom and 99.5833% Bonferroni-adjusted confidence. Their coverage depends on the t assumptions, and five seeds limit precision. Ordinary 95% intervals for secondary results are descriptive. The fifteen seed/population cells are not pooled as independent tasks.

The separate paired record bootstrap uses 10,000 multinomial resamples of each population's 1,600 test records, conditional on the fixed trained checkpoints. The same record multiplicities are used across methods and seeds. Macro-F1 is recomputed per checkpoint before averaging. Record resampling does not create more training seeds; seed and record intervals are not combined, and extreme adjusted bootstrap tails remain approximate.

The 97% validation macro-F1 milestone is diagnostic. Validation is checked every 75 updates; confirmation is the third consecutive qualifying check, 150 updates after its sequence's first check. Nonreachers remain visible, and medians among successful runs are conditional. Every endpoint still completed 15,000 updates: no early-stopping wall-time saving or held-out performance at an earlier update was established.

## Historical local readiness

The local capsule used four circuit recipes, three populations and five training seeds: 60 selected checkpoints. Each population reused 32 validation fixtures chosen without labels. These accounting units remain separate:

| Historical quantity | Meaning |
| --- | --- |
| 60 circuit checkpoints | Four circuit recipes × three populations × five seeds |
| 1,920 checkpoint–fixture pairs | 60 checkpoints × 32 reused fixtures; not 1,920 unique records |
| 1,440 measured Aer experiments | Required measurement settings across 60 checkpoints × eight fixtures × two scenarios |
| 1,474,560 simulated Aer measurement shots | 1,440 experiments × 1,024 shots |
| 398,131,200 represented multinomial trials | Separate conditional joint-bitstring sampling, not additional Aer or physical shots |

Scalar and Legacy use one XX setting per record. Multi and Frozen use XX for X0/X1 and ZZ for Z0/Z1/Z0Z1: two settings. A nominal shot budget is per setting, so Multi/Frozen consume twice the total shots per record at that budget. Moments sharing a setting use the same sampled bitstrings; they are not sampled independently. The conditional total follows 90 checkpoint-setting combinations × 32 fixtures × three scenarios × five replicates × (1,024 + 8,192) trials.

Compilation used an abstract two-qubit target. Illustrative noise acts on logical gates and is not device calibration or a measured noise model of the compiled target. The independent audit reconstructed moments, noise channels, joint draws and accounting; it checked recorded compilation residuals without independently rerunning the compiler or rerandomizing measured Aer experiments. These small-fixture diagnostics do not establish full-test robustness, physical-QPU accuracy, hardware latency or quantum advantage.

## Research direction and boundaries

The v0.5 Fourier-span argument places each depth-two circuit moment in the tensor Fourier basis with frequencies up to two in each coordinate. Consequently, Scalar, Multi and Frozen logits have exact Trig25 representations per fixed routing bank. This does not establish a finite Trig25 logit representation of the Legacy Born-probability link, identical training landscapes, equal capacity or equal hardware cost. No deployment-latency benchmark of a newly compiled evaluator was run in v0.5.

The report proposes building and checking a direct classical evaluator of learned circuit logits. Scalar remains a simpler future comparison candidate; Multi should justify its extra measurement setting. These are preserved historical recommendations, not new experiments performed by packaging or claims that later v0.6 work belongs to this release.

These results concern small synthetic classifiers, fixed routers and unequal capacities. The ellipse changes the label boundary under the same uniform input distribution; it is not an out-of-distribution benchmark. Five training seeds and one fixed split per population do not establish broad task or real-world generalization. Historical scores from earlier studies provide context, not paired improvement evidence. No physical-QPU result, quantum advantage, ETEL implementation or full language-model benchmark is supplied.

## Release-packaging checks and reproduction

The bounded startup helper checks package integrity before scientific imports and after its checks, parses all 52 selected Python files, imports the selected numerical modules and runs two selected tests: model parameter shapes/paired initialization, and independent circuit-state/moment agreement. It does not run training, official scoring, shot sampling, noise experiments or QPU jobs. Success does not establish a clean installation, every optional dependency or full historical reproduction.

Read the [original study overview](source_guidance/README.txt), [original reproduction guide](source_guidance/REPRODUCTION_GUIDE.txt), [registered analysis protocol](source_guidance/governance/ANALYSIS_PROTOCOL.json) and [local-readiness protocol](source_guidance/governance/LOCAL_READINESS_PROTOCOL.json). Historical source commands and absolute paths require the full retained evidence; they are not a batch to execute from these curated downloads. Full scientific replay needs separately retained data, checkpoints, operational records and the recorded numerical environment. The archive's logical payload bytes describe retained evidence, not this download size or a tested hardware minimum.
