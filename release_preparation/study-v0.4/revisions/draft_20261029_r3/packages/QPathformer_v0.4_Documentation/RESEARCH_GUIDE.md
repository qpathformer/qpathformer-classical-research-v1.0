# Study v0.4 research guide

## Study design

The study crosses three model families with three routing policies: a two-qubit, depth-two circuit model (Q2), a raw-coordinate ReLU MLP and a 25-feature trigonometric sigmoid-logit model; each is evaluated globally, with coordinate-hash routing or with training-only k-means routing. Q2 is the model name, separate from the historical `C:\Q2` build location. The task has binary labels.

Routed examples activate one of five parameter banks. The fixed k-means router fits five centroids to training coordinates without labels. Within each family, hash versus k-means preserves bank capacity, paired initialization and training order while changing the partition. A circuit bank has eight trainable angles, and five banks allocate forty angles; this is not a count of classes or total circuit gates.

| Model family | Global trainable parameters | Routed trainable parameters |
| --- | ---: | ---: |
| Q2 | 8 | 40 |
| ReLU MLP | 129 | 45 |
| Trigonometric sigmoid-logit | 25 | 125 |

K-means additionally fits ten centroid coordinates. Nearby parameter counts do not establish equal functional capacity. The trigonometric sigmoid-logit control is a different probability family, not an exact probability emulator of Q2.

All 54 development and 135 confirmation endpoints completed 200 rounds and 15,000 optimizer updates per endpoint. Confirmation used five training seeds for every model/population combination across two independent circle populations and a rotated ellipse. Each population has 1,600 held-out test records shared across its model/seed checkpoints. The ellipse changes the label boundary while retaining the input distribution; it does not establish real-world transfer.

## Findings

Binary cross-entropy (BCE; lower is better) was the primary metric. Macro-F1 was secondary. These are mean test results over five training seeds for Q2 with k-means routing.

| Confirmation population | Mean BCE | Mean macro-F1 |
| --- | ---: | ---: |
| Circle population 1 | 0.17689 | 98.32% |
| Circle population 2 | 0.18280 | 97.16% |
| Rotated ellipse | 0.21207 | 94.41% |

Spatial routing improved Q2 relative to hash routing: the mean BCE reductions were 0.10838, 0.10103 and 0.14453, respectively. Both separately reported adjusted uncertainty intervals were below the registered −0.01 practical reference for all three populations.

The stronger classical controls remain central to the interpretation. Global MLP and global trigonometric models achieved lower mean BCE and higher mean macro-F1 than Q2 k-means on every confirmation population. Routed trigonometric models also achieved lower BCE than routed Q2 throughout. Successful prediction of these smooth synthetic boundaries did not require a circuit or a banked model.

Q2's favorable mean BCE differences versus the small routed MLP are unresolved across training seeds. The adjusted paired-seed intervals include zero on every population. The circle record-bootstrap intervals exclude zero conditional on the five trained checkpoints; this does not remove training instability. The ellipse mean BCE improvement, 0.00992, is below the predeclared 0.01 practical reference. Neither non-significance nor nearby parameter counts establishes equivalence or a general circuit advantage.

## Uncertainty and learning milestones

The registered primary family contains nine comparisons: three paired BCE contrasts on each of three populations. The paired-seed t intervals use five seeds, four degrees of freedom and 99.4444% Bonferroni-adjusted confidence. Five seeds provide limited precision, and the t-based coverage depends on its assumptions. Ordinary 95% intervals for secondary measures are descriptive.

A separate paired record bootstrap uses 5,000 resamples of the 1,600 test records within each population, conditional on the fixed trained checkpoints. The same record multiplicities are used across methods and checkpoints; macro-F1 is recomputed per checkpoint before averaging. This is not additional training replication. The seed and record intervals are not pooled, and the fifteen population/seed cells are not treated as independent tasks.

The 97% validation macro-F1 milestone is a learning diagnostic. Validation checks occur every 75 updates; sustained crossing is the third consecutive qualifying check, 150 updates after that sequence's first check. Nonreachers remain visible, and medians among successful runs are conditional. All endpoints still completed their full budgets. These diagnostics show neither realized early-stopping savings nor held-out performance at an earlier update.

## Historical local readiness

All circuit execution used classical compute and local simulators. The readiness capsule used 32 label-independent validation fixtures per population across all 45 selected circuit checkpoints. The accounting units must be kept separate.

| Historical quantity | Meaning |
| --- | --- |
| 45 circuit checkpoints | Three circuit/routing variants × three populations × five training seeds |
| 1,440 checkpoint–fixture cases | 45 checkpoints × 32 reused validation fixtures; not 1,440 unique data records |
| 720 measured Aer experiments | 45 checkpoints × eight fixtures × two scenarios |
| 737,280 simulated Aer measurement shots | 720 measured experiments × 1,024 shots |
| 199,065,600 represented binomial trials | Separate conditional NumPy binomial diagnostics; not additional Aer or physical shots |

The independent readiness audit also checked 4,320 density-scenario circuit evaluations and reproduced all 1,350 conditional sampling arrays. The binomial total follows 45 checkpoints × 32 fixtures × three scenarios × five replicates × (1,024 + 8,192) represented trials. No physical shots, hardware jobs or current IBM device qualification are reported. The predeclared logical-noise scenarios are illustrative, not device calibration or noise applied to the compiled target. Small-fixture diagnostics do not establish full-test robustness or hardware performance.

## Interpretation and selected evidence

Five seeds, synthetic tasks, fixed routers, unequal capacities and one frozen optimizer recipe do not isolate a circuit-specific benefit or establish quantum advantage, speed, equivalence or real-world generalization. Historical replay verified 135 endpoints and 216,000 checkpoint–record predictions; it was not a second execution of every optimizer update. Timings and work counters describe the retained software implementations and are not quantum-hardware costs.

The report preserves its original tables, figures, numerical qualifications and future-study recommendations. Packaging adds no experiments and makes no claim that unfinished or later studies have been completed. No ETEL implementation is supplied.

The [original overview](historical/README.txt) and [reproduction guide](historical/REPRODUCTION_GUIDE.txt) describe the full retained archive. Commands and absolute paths in those files are historical; they are not a batch to run in a curated download. Read the report alongside the included registered protocols. Bounded release-packaging checks are separate from historical scientific validation and do not recreate the full operational archive.
