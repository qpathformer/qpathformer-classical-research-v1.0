# Q-Pathformer Classical Research v1.0

**Routed learning, classical baselines and quantum circuit simulation.**

> **Private final-check edition.** The papers and guides are available here for owner review. See [current rights and publication status](docs/EDITION_STATUS.md) before the planned public transition.

**[Latest consolidated research release: research-v1.0](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/research-v1.0)** · [Papers ZIP](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/download/research-v1.0/QPathformer_All_Papers_v1.0.zip) · [Consolidated ZIP](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/download/research-v1.0/QPathformer_Consolidated_Release_v1.0.zip)

Q-Pathformer investigates how learning systems choose where to spend their effort: which examples receive training, which specialist models handle an input, and which training jobs receive more computation.

This research edition brings together completed component studies, selected implementations and a separate specification for the proposed three-state architecture. It records improvements, adverse comparisons and inconclusive findings so that the next experiment can build on what the evidence supports.

The aim is to make architectural ideas testable. Comparisons examine whether a result comes from useful routing, additional model flexibility, different information or a larger resource budget. Strong classical controls and numerical reference implementations help identify what a circuit-based approach contributes under the tested conditions.

## Start reading

| Read | What it helps you understand |
| --- | --- |
| **[Q-Pathformer Routed States: Classical Models and Quantum Circuit Simulation](docs/papers/QPathformer_Main_Paper_v1.0.pdf)** | Completed findings on circuit readouts, routing, classical inference conversion and training allocation, centred on studies v0.6, v0.9 and v0.9.5. |
| **[Q-Pathformer Three-State Architecture and Experimental Specification](docs/papers/QPathformer_Architecture_and_Experimental_Specification_v1.0.pdf)** | The proposed system, experimental controls and decisions to settle before future integrated runs. |
| **[Research Approach](docs/RESEARCH_APPROACH.md)** | The research questions, comparison method, contribution opportunities and future research cycle. |

[Collection reading guide](docs/COLLECTION_GUIDE.md) · [Main paper in Word](docs/papers/QPathformer_Main_Paper_v1.0.docx) · [Architecture companion in Word](docs/papers/QPathformer_Architecture_and_Experimental_Specification_v1.0.docx)

## What the studies show

- **Routing and richer readouts can help on selected tasks.** The gains depend on the task, model and control; stronger classical alternatives remain important counterexamples.
- **Some trained circuit predictors support equivalent classical inference.** The converted implementations preserve their predictions within the reported numerical checks and improve local inference time under the measured conditions.
- **An execution layer and a successful allocation policy require different evidence.** In study v0.9.5, the tested Elastic Task Execution Layer (ETEL) suitability policy did not establish its registered practical quality gain. Capped successive halving used less mean CPU across the four tested tasks.
- **Simulation and component results define a starting point for further work.** The completed series reports no physical-QPU result and does not validate the full integrated architecture or establish quantum advantage.

The studies use different tasks, controls, populations and budgets. Their results should be read within each protocol, rather than combined into a version-to-version leaderboard. See the [main findings paper](docs/papers/QPathformer_Main_Paper_v1.0.pdf) and [v0.9.5 study summary](release_notes/study-v0.9.5.md) for the comparisons and uncertainty.

## Choose a download

Start with the [research-v1.0 consolidated release](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/research-v1.0), currently marked Latest. It brings together the findings and supporting documents. [All releases](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases) also retain the individual study packages.

| Package | Best starting point |
| --- | --- |
| **`QPathformer_All_Papers_v1.0.zip`** | Read the main paper, architecture companion, supporting study reports and preserved original architecture, with reading and rights indexes. |
| **`QPathformer_Consolidated_Release_v1.0.zip`** | Read the Papers collection together with the separate Research Approach, repository guidance and documentation. It already contains Papers. |

Download a ZIP with its matching `.seal.json` from that same release and extract it once. Open `README.md` for Papers or `START_HERE.md` for Consolidated. The seal records file identity; it does not establish a scientific result.

GitHub also offers automatic **Source code (zip)** and **Source code (tar.gz)** downloads. These contain the tagged repository tree; they are separate from the curated Papers, Consolidated and study Code packages.

Individual studies retain three separately scoped downloads:

| Part | Purpose |
| --- | --- |
| **Study** | Report, methods, findings and limitations. |
| **Documentation** | Study guidance, provenance and reproduction boundaries. |
| **Code** | Selected implementation and package-specific startup instructions. |

The consolidated papers do not introduce a unified software implementation. To inspect or run selected code, choose the relevant study's Code package and follow its own instructions.

## What has been built

The programme has produced training and evaluation software, circuit and classical-model implementations, routing and readout components, equivalent classical inference implementations for selected predictors, and records supporting the reported comparisons. Individual study releases provide selected source code and guidance. Trained checkpoints, datasets and full experiment archives remain separately retained where the study specifies.

Later work includes **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**. ETEL coordinates bounded tasks and workers, records execution state for recovery and accounts for resources. Its execution role is distinct from the policy that allocates training budget. The v0.9.5 Code package includes the selected ETEL core and execution adapter.

**ETEL v0.1 is a component version. Study v0.1 is the initial experiment series and has no ETEL component.** Research edition v1.0 identifies this collection. Historical source identifiers are recorded in [naming and attribution](NOTICE.md).

## Four illustrative tasks

The later studies use small two-dimensional classification tasks to make routing and decision boundaries inspectable. These illustrations show analytic task regions introduced in v0.6; they are not fitted model predictions.

| Spiral | Checkerboard |
|:---:|:---:|
| [![Spiral task regions](assets/spiral.png)](assets/spiral.png) | [![Checkerboard task regions](assets/checkerboard.png)](assets/checkerboard.png) |
| Curved, interleaved boundaries. | Repeated changes between neighbouring regions. |

| Rare disks | Noisy annulus |
|:---:|:---:|
| [![Rare positive disks](assets/disk.png)](assets/disk.png) | [![Latent annulus before label noise](assets/annulus.png)](assets/annulus.png) |
| Small positive regions among many negatives. | The latent ring before independent 10% observed-label flips. |

[Task definitions and model guide](docs/RESEARCH_GUIDE.md) · [Illustration sources](assets/ILLUSTRATIONS.md)

## Release index

The [consolidated research-v1.0 release](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/research-v1.0) is the main entry. The studies below follow from newest to earliest; this is a navigation order, not a performance ranking. Each study preserves its own Study, Documentation and Code assets.

| Study | Main question |
| --- | --- |
| [v0.9.5](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.9.5) | Training-budget allocation with ETEL suitability, fixed allocation and successive halving. |
| [v0.9](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.9) | Learned routing and global classical controls. |
| [v0.8](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.8) | Training-example priority. |
| [v0.7](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.7) | Routing capacity, population replication and deployment. |
| [v0.6](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.6) | Harder task families and equivalent classical inference. |
| [v0.5](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.5) | More flexible output recipes and classical controls. |
| [v0.4](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.4) | Routing effects versus predictor effects. |
| [v0.3](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.3) | Spatial routing for shallow circuits. |
| [v0.2](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.2) | Revised schedules and stronger baseline comparisons. |
| [v0.1](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.1) | Initial circuit schedules, text routing and local QPU-readiness checks. |

## Reproduce and contribute

Start with the relevant Code package's quickstart. A passed startup check shows that selected commands ran in the recorded environment; it does not reproduce the study. Full reproduction needs the separately retained frozen artifacts and a compatible environment. Storage figures describe retained evidence and should be read separately from model size or hardware requirements.

Useful contributions include independent reproductions, corrections, stronger controls, numerical checks, clearer resource measurements and well-documented negative findings. See [Contributing](CONTRIBUTING.md), [reproduction boundaries](docs/REPRODUCIBILITY.md) and [artifact contents and rights](ARTIFACT_RIGHTS.md).

## Where the research goes next

The next questions concern routing beyond the present task families, training priorities, adaptation and retention, execution recovery, and allocation policies measured against simple controls. Each requires a declared protocol and evidence appropriate to its claim.

A first physical-QPU pilot is a separate proposed experiment. It would evaluate a frozen, classically trained predictor against saved references, using a qualified current device and a declared measurement budget. Hardware inference and hardware training are separate milestones. See the [research direction](docs/RESEARCH_ROADMAP.md) and [QPU preparation plan](docs/QPU_RELEASE_PLAN.md).

![Q-Pathformer three-state conceptual architecture](assets/qpathformer-three-state.png)

The illustration connects preparation and priorities, grouped representations and routing, and token clusters and adaptation. The [architecture companion](docs/papers/QPathformer_Architecture_and_Experimental_Specification_v1.0.pdf) specifies the proposed model and future experiments. The [original QPATH-ARCH-001](docs/architecture/QPATH-ARCH-001.pdf) remains unchanged, with its [source and publication history](docs/architecture/README.md).

## Rights and attribution

Selected Python sources are source available under **Q-Pathformer Platform License 1.0**. Identified report and explanatory content use their separately recorded content licences, including CC BY 4.0. The applicable scope records identify what is licensed; no licence applies to the entire collection merely because the files are packaged together. Platform License 1.0 requires a separate agreement for **production deployment or commercial integration** of its identified software. That condition does not extend to separately licensed CC BY content. QPATH-ARCH-001 retains its original notices. See [licence scope](LICENSE_SCOPE.md), [edition status](docs/EDITION_STATUS.md) and [artifact rights](ARTIFACT_RIGHTS.md).

Branding and endorsement are separate from copyright reuse and Lab participation. [Proposed trademark policy](TRADEMARKS.md) · Trademark enquiries: [Anthony Siljeg](mailto:asiljeg@alnotrea.com).

**Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.**

[Q-Pathformer research programme](https://github.com/qpathformer) · [Research Approach](docs/RESEARCH_APPROACH.md)
