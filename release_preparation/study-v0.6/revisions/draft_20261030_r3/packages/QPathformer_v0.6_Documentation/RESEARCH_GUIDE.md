# Study v0.6 research guide

## Design and metrics

Q-Pathformer v0.6 asks whether richer circuit readouts help on harder classification boundaries, and whether the same trained circuit can run faster through an equivalent classical representation. Six recipes were compared on checkerboard, spiral, noisy annulus and rare-positive disks, using five paired training seeds on one fixed confirmation split per task family. All circuit execution used classical compute.

The completed design includes 48 development and 120 confirmation endpoints, plus 24 separate engineering endpoints. Every full endpoint completed 200 rounds and 15,000 optimizer updates. All six models train using stable native-logit BCE; checkpoint selection and registered comparisons use common clipped BCE.

The six registered methods are Scalar, Multi, routed Tanh, routed Trig25, global Trig25 and global MLP. There is no active Legacy, Frozen or trained hash-routing arm, and no ETEL component. Circuit banks have two qubits, two encoding layers and eight trainable angles; eight angles are not eight classes or a count of all gates. Routed methods use five fixed training-only k-means banks. Routed Trig25 has 125 coefficients versus 25 globally, so that contrast changes spatial partitioning and capacity together rather than isolating routing.

Primary common clipped BCE uses natural logarithms and probabilities clipped to `[1e-7, 1-1e-7]`. It is the bounded selection/comparison score, distinct from stable native-logit training loss and the later v0.9.5 primary endpoint. Selection uses minimum validation common clipped BCE. Macro-F1, raw Brier and probability diagnostics are complementary; the v0.5 Legacy-to-Scalar loss-change limitation does not apply to this six-arm design.

## Historical findings

Mean common clipped BCE across five paired training seeds:

| Recipe | Checkerboard | Spiral | Noisy annulus | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Scalar | 0.57805 | 0.50069 | 0.41064 | 0.01345 |
| Multi | 0.52162 | 0.42532 | 0.40911 | 0.01456 |
| Routed Tanh | 0.65108 | 0.56822 | 0.43216 | 0.05229 |
| Routed Trig25 | 0.30504 | 0.24828 | 0.40317 | 0.01487 |
| Global Trig25 | 0.69655 | 0.66792 | 0.45973 | 0.01666 |
| Global MLP | 0.56668 | 0.46946 | 0.41843 | 0.05234 |

Secondary mean macro-F1:

| Recipe | Checkerboard | Spiral | Noisy annulus | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Scalar | 73.03% | 77.60% | 86.20% | 99.12% |
| Multi | 78.55% | 84.71% | 86.92% | 98.85% |
| Routed Tanh | 60.02% | 66.05% | 83.07% | 94.17% |
| Routed Trig25 | 89.57% | 92.05% | 86.81% | 98.67% |
| Global Trig25 | 48.89% | 57.57% | 82.14% | 99.30% |
| Global MLP | 69.55% | 75.77% | 85.28% | 95.12% |

Multi improves on Scalar on checkerboard and spiral, while routed Trig25 achieves lower mean common clipped BCE on both. Noisy-annulus and rare-disk results do not establish a general improvement from the richer readout. Small or unresolved differences are not equivalence results.

Multi minus Scalar mean BCE is −0.0564 on checkerboard and −0.0754 on spiral. Adjusted paired-seed intervals are [−0.0920, −0.0209] and [−0.1036, −0.0471]; separate adjusted record intervals also favor Multi. Routed Trig25 remains better on primary loss for both tasks. The report's checkerboard gain of 5.53 F1 percentage points is compatible with separately rounded displayed endpoints; no report correction is inferred from their subtraction.

On annulus, some circuit-versus-Trig seed intervals exclude zero while record intervals include zero, and the mean differences are below the 0.01 BCE reference. On rare disks all primary mean differences are below that reference and all adjusted record intervals include zero. These are limited findings, not equivalence. Observed noisy annulus labels remain the primary target; latent-clean labels are diagnostic. A 10% label-flip probability does not impose a hard 90% finite-sample F1 ceiling. Rare-disk macro-F1 must be read with its class-specific metrics.

## Uncertainty and accounting

The sixteen primary comparisons use five paired seed differences, four degrees of freedom and 99.6875% Bonferroni-adjusted t intervals. Five seeds limit precision and coverage depends on the t assumptions. The separate 10,000-draw paired-record bootstrap conditions on fixed fitted checkpoints and reuses the same record multiplicities across methods/seeds. It does not create more training seeds or combine population and training uncertainty into one interval.

There is one fixed confirmation split per task family. The four held-out test sets contain 6,400 unique records; 192,000 checkpoint-record classifications reuse those records across six models and five seeds. Engineering, development and confirmation populations are distinct. Validation milestones are descriptive, with nonreachers retained; every full endpoint completed 15,000 updates, so no early-stopping saving was measured.

## Equivalent conversion and inference timing

Forty selected circuit checkpoints were converted to equivalent classical coefficients. The checks found no classification differences and numerical agreement within the declared tolerances. Conversion reduced measured CPU inference time. It is another representation of the same fitted predictor, not an additional trained model.

The analytical identity is specific to the retained two-layer encoding and linear Pauli-logit heads. Each trained bank is expressed in a finite Trig25 coefficient basis using fixed construction nodes, without labels or regression. The five banks contain 125 coefficients. This alternate representation does not change the fitted model or produce a new accuracy arm.

Across reported validation/test, off-grid, routing-boundary and forced-bank checks, maximum absolute differences were **7.16e-15 in probabilities** and **6.39e-14 in logits**, with zero observed classification differences. Independent Laurent-polynomial reconstruction also passed. These finite numerical checks quantify agreement within declared tolerances; they are not bitwise equality for every possible input or a result for arbitrary circuits.

An equally optimized routed Trig25 control uses the same coefficient inference kernel and has comparable inference cost; the global MLP is faster in the displayed tables. Conversion improves the retained circuit implementation without establishing a speed advantage over equally optimized classical controls or quantum speedup.

The deployment benchmark used one isolated process, one BLAS thread and no concurrent training. Hot inference includes routing, feature construction and sigmoid; loading is excluded and compilation is recorded separately. Batch sizes 1, 32 and 1,024 have different workloads. Two warmups and fifteen timing trials are technical repeats, not independent training replications. Later annulus/disks blocks show broader timing drift with an unmeasured cause; do not attribute it to task complexity or promote one universal speedup multiplier.

The 125 float64 coefficients occupy **1,000 parameter bytes**, versus 400 for Scalar and 560 for Multi. The shared 80-byte router and file overhead are excluded. This is a representation/time tradeoff, not model compression.

## Historical simulator readiness

Local simulator coverage includes 40 selected circuit checkpoints, **983,040 Aer simulated measurement shots**, and separately **265,420,800 probability-level multinomial trials**. Each task reuses 32 validation fixtures; 1,280 checkpoint–fixture pairs are not 1,280 unique inputs. Scalar uses one measurement setting and Multi two, so equal per-setting shots cost twice as many shots per Multi prediction. Joint bitstring draws preserve within-setting moment dependence.

Archived Manila properties are dated **27 May 2024**. This is a historical snapshot with approximate noise, not current calibration or live service evidence. Independent historical reconstruction checked the recorded coefficient/noise/channel and sampling evidence within its stated limits; it did not rerun every compiler/Aer execution. No physical shots, hardware latency, live IBM service, full language-architecture benchmark or quantum advantage is established.

## Packages, verification and research boundaries

These are small two-dimensional synthetic binary classifiers with fixed routers and unequal capacities. Five paired training seeds on one fixed confirmation split per task family do not establish population-wide or real-world generalization. Historical prior-version scores provide context, not paired improvement evidence. No physical-QPU result, quantum advantage, ETEL implementation or full language-architecture benchmark is supplied.

The bounded startup checks exact package integrity before and after its six required tests, parses all 61 selected Python files, and imports the selected numerical modules. The tests cover model shapes/paired initialization, independent circuit-state/moment agreement, orthogonal conversion nodes, both heads off grid and forced banks, constant logits/invalid contracts, and the learned Trig25 coefficient kernel. Missing compiler or test components fail startup. It does not train, score official data, sample shots, rerun benchmarks or submit QPU jobs. Success is not full scientific reproduction or a clean installation.

The genuine final startup, helper regression probes and shell failure checks are recorded separately from historical study evidence. A PASS does not validate omitted datasets/checkpoints, install optional dependencies or establish full-archive relocation. Current dependency inventory includes direct Python imports and separately identified imports inside generated startup child programs; these include local and standard-library modules and are not all third-party requirements.

The companion Study download contains the preserved report in PDF and Word. Its original 34-page guide reference concerns the original report; the packaged edition has 35 pages including its edition note. Historical internal-use and internal held-out-test-release wording is retained as provenance and is distinct from GitHub publication. No new report render or scientific experiment is claimed in this revision.

The recorded full archive contains 20,859 payload files totaling 2,229,408,138 bytes plus a 5,077,038-byte delivery manifest: 2,234,485,176 logical bytes. This is historical archive storage accounting, not the curated download size, model size or a RAM requirement. The full archive was not rescanned during this revision. Full replay requires retained inputs, environments and path bindings; original command histories are not an automatic replay instruction.

Future work may examine matched-capacity routing controls, richer/localized features, independent population draws and real-world tasks. These are research directions, not unfinished release requirements.

The identified original report content and explanatory prose are licensed under **CC BY 4.0**. Selected Python source and package helpers are **source available under the unchanged Q-Pathformer Platform License 1.0**. Each package identifies its adopted scope and exclusions; applicable earlier grants remain in force.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains the licensor; company affiliation does not transfer ownership.
