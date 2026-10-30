# Q-Pathformer Research v1.0 — Routed States and Three-State Architecture

**Routed learning, classical baselines and quantum circuit simulation.**

Q-Pathformer investigates how learning systems choose where to spend their effort: which examples receive training, which specialist models contribute to a prediction, and which training jobs receive more computation.

This research collection brings together completed component studies, the main findings paper and a separate specification for the proposed three-state architecture. It connects an architectural idea with experiments that examine its mechanisms, preserving improvements, adverse comparisons and inconclusive results.

## Why we created this collection

An architectural idea becomes useful when its mechanisms can be tested and its results explained. If a model improves, what produced the gain: routing, a more flexible predictor, different input information or a larger training budget?

These questions matter when assessing both AI systems and quantum-circuit models. The Q-Pathformer studies examine them through defined text tasks and small classical and simulated quantum-circuit models. The collection provides methods, comparison results, selected implementations through individual study releases, and a research direction that others can inspect and extend.

The aim is to identify which choices justify their cost, where simpler alternatives remain preferable, and what evidence would support the next stage of development.

## Start reading

| Document | What it offers |
| --- | --- |
| **[Q-Pathformer Routed States: Classical Models and Quantum Circuit Simulation](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/research-v1.0-20261031/docs/papers/QPathformer_Main_Paper_v1.0.pdf)** | The main findings on circuit readouts, routing, equivalent classical inference and training allocation, centred on studies v0.6, v0.9 and v0.9.5. |
| **[Q-Pathformer Three-State Architecture and Experimental Specification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/research-v1.0-20261031/docs/papers/QPathformer_Architecture_and_Experimental_Specification_v1.0.pdf)** | The proposed architecture, software responsibilities, experimental controls and decisions to settle before integrated experiments. |
| **[Research Approach](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/research-v1.0-20261031/docs/RESEARCH_APPROACH.md)** | A separate guide to the scientific questions, comparison method, contribution opportunities and future research cycle. |

Supporting study reports retain their individual methods, results and reproduction boundaries. The original architecture is preserved with its source history and notices.

## What the studies show

- **Richer readouts and routing can help on selected tasks.** Their value depends on the task and comparison. Strong classical controls remain better in important cases.
- **Selected trained circuit predictors support equivalent classical inference.** Conversion preserves their predictions within the reported numerical checks and improves local inference time under the measured conditions.
- **Execution and training allocation require separate evaluation.** The tested ETEL suitability policy did not establish its registered practical quality gain. Capped successive halving used less mean CPU across the four tested tasks.
- **Component evidence guides the next experiments.** These studies report classical computation and quantum-circuit simulation. The results do not establish physical-QPU performance, quantum advantage or validation of the full integrated architecture.

The studies use different tasks, populations, controls and budgets. Read each result within its protocol; the version sequence records the development of the research questions. The [main paper](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/research-v1.0-20261031/docs/papers/QPathformer_Main_Paper_v1.0.pdf) explains the comparisons and their limits.

## How we approach the research

The programme separates three decisions:

- **Training-example selection:** which examples receive attention during learning.
- **Model routing:** which specialist components contribute to a prediction and how their outputs are combined.
- **Training-budget allocation:** which candidate models receive more work under a limited budget.

Each comparison needs a defined question, suitable controls, a resource allowance and an evaluation rule. Predictive quality and execution cost are reported separately, with uncertainty appropriate to the comparison. Negative and inconclusive results help determine what to test next.

The later studies use spiral, checkerboard, noisy-annulus and rare-positive-disk tasks to make decision boundaries and routing behaviour inspectable. These controlled settings help isolate mechanisms; broader applications require further evidence.

## Choose a download

| Package | Best starting point |
| --- | --- |
| **`QPathformer_All_Papers_v1.0.zip`** | The main paper, architecture companion, supporting study reports and preserved original architecture, with reading and rights indexes. |
| **`QPathformer_Consolidated_Release_v1.0.zip`** | The Papers collection together with Research Approach, repository guidance and the identified repository source snapshot. It already contains Papers. |

Choose **one ZIP and its matching `.seal.json`** from the [release assets](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/research-v1.0-20261031). Extract it and open `README.md` for Papers or `START_HERE.md` for Consolidated. Research Approach is included in Consolidated at `repository/docs/RESEARCH_APPROACH.md`.

The seals and accompanying delivery receipt support file-integrity checking. GitHub’s automatic **Source code** archives contain the tagged repository tree; the curated ZIPs above provide the research collection and its reading guides.

Both papers include bookmarks and page labels. If a PDF reader blocks a link to the companion document, open the adjacent PDF directly.

## What has been built

The studies produced training and evaluation software, circuit and classical-model implementations, routing and readout components, and equivalent classical inference implementations for selected predictors.

Later work includes **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**, which coordinates bounded tasks and workers, records execution state for recovery and accounts for resources. Its execution role and the quality of its training-allocation policy are evaluated separately.

**ETEL v0.1** is a component version. **Study v0.1** is the initial experiment series, including local QPU-readiness checks, and contains no ETEL component. **Research v1.0** identifies this collection.

Individual [study releases](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases) retain three complementary downloads:

| Part | Purpose |
| --- | --- |
| **Study** | Report, methods, findings and limitations. |
| **Documentation** | Guidance, provenance and reproduction boundaries. |
| **Code** | Selected implementation and package-specific startup instructions. |

Use the relevant study’s Code package to inspect its implementation. The collection does not introduce a unified implementation of the proposed architecture. Each study’s guide identifies its reproduction requirements, including separately retained datasets, checkpoints and compatible environments where required.

## Where the research goes next

The next questions concern routing beyond the present tasks, training priorities, adaptation and retention, execution recovery and allocation policies measured against simple controls. A physical-QPU pilot would be a separate experiment, with a frozen predictor, saved reference outputs and a declared measurement budget.

Useful contributions include independent reproductions, stronger baselines, numerical checks, clearer resource measurements, corrections and documented negative findings. The [contribution guide](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/research-v1.0-20261031/CONTRIBUTING.md) explains how to participate.

Reuse terms are identified in the [research rights guide](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/research-v1.0-20261031/docs/RESEARCH_V1_RIGHTS.md) and the notices included with each package.

**Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.**
