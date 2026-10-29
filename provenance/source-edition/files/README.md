# Q-Pathformer Classical Research

### Quantum emulation on classical hardware and preparation for QPU testing

> **Private staging repository.** This workspace prepares the study, documentation and selected code for the planned v2.0 repository distribution. Completed studies retain their original identifiers. Release downloads currently require repository access.

Q-Pathformer studies how small learning systems make predictions, how examples are routed to specialist models, and where a limited training budget is most useful. The work compares quantum circuits emulated on classical computers with conventional and trigonometric models, recording improvements, negative findings and the cost of learning.

Ten completed studies span **v0.1–v0.9.5**. Additional classical runs are planned. This repository contains explanations, illustrations and the **[v0.9.5 study summary](release_notes/study-v0.9.5.md)**. The [v0.9.5 release](https://github.com/qpathformer/qpathformer-classical-research/releases/tag/study-v0.9.5) provides separately identified documentation, public-report and selected code attachments. Models and full reproduction archives remain separately retained. Physical QPU experiments will be documented separately.

## How this repository works

**Study · Documentation · Code**

Start with the study to understand the findings, use the documentation to explore the project, and open the code package to inspect the selected implementation.

| Part | What it provides | Where to start |
| --- | --- | --- |
| **Study** | Research questions, methods, findings and limitations | [Study summary](release_notes/study-v0.9.5.md) and the report downloads in the study release |
| **Documentation** | Project overview, research guide, illustrations and reproduction boundaries | [Research guide](docs/RESEARCH_GUIDE.md) |
| **Code** | Selected training, routing, allocation and ETEL sources, with package-specific startup instructions | [Code and ETEL ZIP](https://github.com/qpathformer/qpathformer-classical-research/releases/download/study-v0.9.5/QPathformer_study-v0.9.5_Code_ETEL_Edition_1.zip) |

[Open the study-v0.9.5 release](https://github.com/qpathformer/qpathformer-classical-research/releases/tag/study-v0.9.5). “Public report edition” identifies the editorial edition; access to this repository and its downloads remains private.

The report and selected code are supplied as release downloads. This Git tree provides the documentation and scope records. Trained models and full experiment archives are retained separately. For implementation sources, use the named Code and ETEL ZIP; GitHub's generated source archives contain the tagged documentation tree.

**Licensing:** the selected implementation sources use **Q-Pathformer Platform License 1.0**. The specified original study-report content uses **CC BY 4.0**. The specified original project explanations and illustrations use **CC BY 4.0** under the separate [documentation scope](DOCUMENTATION_LICENSE_SCOPE.json). QPATH-ARCH-001 retains its original notices. See [license scope](LICENSE_SCOPE.md).

**Attribution:** Anthony Siljeg — Founder, Alnotrea Labs. Company affiliation: Alnotrea Pty Ltd. Project: Q-Pathformer Initiative. Anthony remains the named licensor; these attribution details do not transfer ownership or amend the preserved code/report grants.

[Reproducibility](docs/REPRODUCIBILITY.md) · [Research direction](docs/RESEARCH_ROADMAP.md) · [Contributing](CONTRIBUTING.md) · [Planned private distribution](docs/DISTRIBUTION_PLAN.md)

## What has been built

The classical research has produced training and evaluation software, fitted circuit and classical models, routing and readout components, and records supporting the reported comparisons. Selected fitted circuit predictors also have equivalent classical implementations for inference. The repository explains this work; its release downloads provide the study report and selected implementation. Trained models and the full experiment archives are retained separately.

The implementation includes **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**. ETEL coordinates bounded tasks and workers, records execution state to support recovery, and accounts for resources. The selected code package includes the study's ETEL core and execution adapter.

The studies examine both execution workflows and policies for deciding which training jobs continue. Findings about an allocation policy apply to that policy; the execution and recovery functions have their own evidence.

ETEL's **v0.1** identifies the component. Study versions identify experiments and reports. See [naming and attribution](NOTICE.md) for the historical source identifiers.

## From classical studies to QPU experiments

**Classical study v0.1** established the initial benchmark and checked how trained circuits could be translated and sampled locally in preparation for future quantum-device testing. Later studies extended those checks, including comparisons using a historical device snapshot. This preparation used simulators and archived device information; no physical-QPU results are reported in the completed study series.

A first physical-device pilot is a proposed, separately recorded experiment. It would test a frozen, classically trained predictor on a qualified device, with a declared measurement budget and comparisons against the saved reference. Current-device qualification, the submission and result adapter, and the run protocol still need to be completed. Hardware inference and hardware training are separate milestones.

The [QPU preparation plan](docs/QPU_RELEASE_PLAN.md) records the completed checks, remaining work and evidence required before expanding the experiments.

## Three research questions

**What should a small model learn?** Circuit features and readouts turn an input into a probability. Neural and trigonometric controls test whether circuit-specific mechanisms earn their cost.

**Which specialist should handle an example?** Hard routing selects an expert; soft routing combines experts. Fixed and learned routing separate geometric structure from extra flexibility.

**Where should the next block of training go?** Fixed allocation, successive halving and ETEL suitability policies decide which competing recipes continue under a limited budget.

## Four training and evaluation tasks

These analytic illustrations show the task definitions introduced in v0.6. They are not model predictions or measured results.

| Spiral | Checkerboard |
|:---:|:---:|
| [![Spiral analytic task regions](assets/spiral.png)](assets/spiral.png) | [![Checkerboard analytic task regions](assets/checkerboard.png)](assets/checkerboard.png) |
| Curved, interleaved class boundaries. | Repeated changes between neighbouring regions. |

| Rare disks | Noisy annulus |
|:---:|:---:|
| [![Three rare positive disks](assets/disk.png)](assets/disk.png) | [![Latent annulus before label noise](assets/annulus.png)](assets/annulus.png) |
| Small positive regions among many negatives. | A ring with independent 10% observed-label flips. |

The annulus panel depicts the latent ring **before** label noise. [Definitions and model guide](docs/RESEARCH_GUIDE.md) · [PNG and SVG illustrations](assets/ILLUSTRATIONS.md).

## Models and lessons

Circuit models use learned parameters and readouts, with hard, fixed-soft, learned-soft and residual controls where specified by the study. Classical comparisons include multilayer perceptrons, routed trigonometric experts and the wider global **G121** model. Early text experiments also used conventional encoders. Model names and training settings must be read within each study.

Learned circuit routing in v0.9 improved on fixed-soft routing for spiral and rare disks. The learned circuit model beat G121 on noisy annulus, but that did not establish that learning the router was necessary. G121 remained stronger on checkerboard and spiral. Selected circuit predictors also admitted faster equivalent classical inference; that is a deployment result for the same fitted function, not a physical-QPU speed result.

In v0.9.5, none of eight registered comparisons established the required 0.01 native-BCE improvement for the tested ETEL allocation policy. Successive halving used less mean CPU on every task. The [release summary](release_notes/study-v0.9.5.md) explains the metrics, independent populations and replay limits.

## How the research developed

| Study | Question and main finding |
|---|---|
| v0.1 | Tested initial circuit schedules and text routing. Fixed-depth and conventional controls set a demanding baseline; local QPU-preparation fixtures were also checked. |
| v0.2 | Revised schedules and text-routing mechanisms. Some circuit improvement did not translate into a general content-routing advantage. |
| v0.3 | Tested spatial routing for shallow circuits. Geometry helped, while a larger MLP remained stronger. |
| v0.4 | Separated routing from predictor effects. Routing helped circuits, but strong classical controls still led. |
| v0.5 | Tested more flexible output recipes. A revised recipe helped, with competitive classical alternatives. |
| v0.6 | Extended the work to the four harder task families. Task differences became clearer, with selected predictors supporting faster equivalent classical inference. |
| v0.7 | Added stronger routing and capacity controls. Geometry mattered and a wider global model was a strong benchmark; ETEL execution workflows were documented. |
| v0.8 | Tested training-example prioritization. Effects were small and task dependent. |
| v0.9 | Tested learning the router. Gains were selective and strong baseline counterexamples remained. |
| v0.9.5 | Tested adaptive training allocation. The ETEL suitability policy did not establish the stipulated gain; halving used less mean CPU on all four tasks. |

Tasks, controls, populations, metrics and budgets change across the series. These results do not form a single version-to-version leaderboard. Earlier studies are context here; the v0.9.5 release has separately identified documentation, public-report and selected code attachments.

## Additional runs and reproducibility

Further classical runs will investigate routing, allocation, traceability and retrieval. **UGCCMT — Unit, Group, Colour, Code, Measure, Train** is a proposed provenance structure. See the [broader Q-Pathformer architecture below](#q-pathformer-a-broader-model-for-future-quantum-systems) for context.

This work is not yet final. Once completed and reviewed, results will be included in the planned new private repository distribution, **v2.0**, with their protocols, comparisons and reproducibility records.

The code package provides its own quickstart and bounded startup checks. Full study reproduction requires the separately retained frozen artifacts and a compatible environment. See [configuration, storage and reproduction limits](docs/REPRODUCIBILITY.md) and [artifact contents and rights](ARTIFACT_RIGHTS.md).

## Q-Pathformer: a broader model for future quantum systems

The broader proposal connects structured data, token clusters, specialist agents and staged learning. Its future direction explores hybrid classical–quantum systems in which selected computations could use quantum processors, including language and multimodal applications. The completed studies test individual components; a full quantum-assisted language model remains a research objective.

![Three-state conceptual architecture](assets/qpathformer-three-state.png)

The concept connects **preparation and priorities (State 3)**, **grouped representations and routing (State 2)**, and **token clusters and adaptation (State 1)**. This is an architecture illustration, not measured quantum hardware behaviour. The original architecture document records first publication on LinkedIn on **5 December 2024**.

[Open QPATH-ARCH-001 — Multi-state Machine Learning & LLM Training (PDF)](docs/architecture/QPATH-ARCH-001.pdf) · [Source and publication history](docs/architecture/README.md).
