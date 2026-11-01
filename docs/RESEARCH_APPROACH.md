# Q-Pathformer research approach

**Research edition v1.0 · 30 October 2026.** See [rights and changes](RESEARCH_APPROACH_RIGHTS.md).

## Purpose

Q-Pathformer investigates how learning systems choose where to spend effort. The research studies which examples receive training, how specialist components are selected or combined, and how limited execution budgets are allocated across competing models.

The aim is to turn an architectural idea into evidence that others can inspect and extend. A useful result can be an improvement, an explanation of why a mechanism helps, a faster implementation of the same predictor, or a finding that a simpler control remains preferable. Each outcome should inform a specific next decision.

This document explains the research method, contribution opportunities and edition cycle. The [main findings paper](papers/QPathformer_Main_Paper_v1.0.pdf) synthesises completed studies. The [architecture companion](papers/QPathformer_Architecture_and_Experimental_Specification_v1.0.pdf) provides the proposed three-state design and experimental specification. Individual study reports retain their own methods, results and limitations.

## Why this work matters

AI and quantum research both benefit from comparisons that explain the source and cost of an effect. Routing, sampling and execution policies can change different parts of the learning process. A gain attributed to one mechanism may depend on extra parameters, different input information, a larger tuning allowance or a changed measurement boundary.

For quantum-circuit learning, classical controls and numerical references are particularly useful. They help identify whether the tested behaviour requires the circuit representation, whether a classical function can reproduce it, and which questions remain for physical-device evaluation. The relevant prior work is discussed in the main paper. [Fedus et al. (2022)](https://jmlr.org/papers/v23/21-0998.html), [Mattson et al. (2020)](https://proceedings.mlsys.org/paper_files/paper/2020/hash/411e39b117e885341f25efb8912945f7-Abstract.html), [Bowles et al. (2024, preprint)](https://arxiv.org/abs/2403.07059), and [Schuld et al. (2021)](https://arxiv.org/abs/2008.08605).

Q-Pathformer contributes a focused programme of questions, implementations and preserved evidence. Its current results concern defined text tasks and small classical or simulated-circuit models. Broader applications remain research directions.

## What the completed studies contribute

The study series examines circuit allocation, spatial routing, readout flexibility, training-example priority, learned routing and training-budget allocation. Each report preserves the controls, metrics and resource conditions needed to interpret its findings.

Selected circuit predictors admit equivalent classical inference implementations. This is useful engineering evidence for those fitted functions. Several studies also show the importance of stronger classical controls and report effects that are small, inconclusive or unfavourable to the proposed method.

Later execution work includes Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1. ETEL coordinates bounded work and supports execution records and recovery. Its suitability allocation policy has its own empirical evaluation; the existence of an execution layer does not establish an allocation-quality benefit.

The public research collection provides identified papers, selected code, explanations and provenance. Curated downloads have explicit reproduction boundaries. Some datasets, checkpoints, environments and full evidence archives remain separately retained.

## How we investigate a question

Begin with a question that can be answered by a comparison. State the mechanism, eligible data, baselines, tuning opportunities, stopping rule and resource budget. Freeze final evaluation and selection rules before inspecting held-out results.

Change one declared mechanism at a time where possible. Treat sampling examples, routing model computation and allocating training jobs as separate interventions. Include controls that test alternative explanations such as additional capacity, useful geometry or different information.

Measure quality and cost within named boundaries. Keep parameter counts, active computation, storage, elapsed time, device use and energy separate. Record preparation, validation, retries and failed attempts when they belong to the claimed cost.

Distinguish independent populations from optimizer seeds and repeated measurements. Preserve negative and inconclusive results. Use uncertainty appropriate to the registered comparison and avoid treating an unresolved difference as equivalence.

Verify implementation correctness independently where feasible. Numerical agreement, reproducibility and predictive benefit answer different questions. Integrity records identify artifacts; they do not prove a scientific claim.

## Research priorities

**Routing and representation.** Test when useful input structure improves routing, when a learned gate adds value beyond an equally sized output correction, and when a global classical model is sufficient. Extend task coverage without losing control of the comparison.

**Training priority.** Keep loss-based sampling separate from the proposed evidence-quality rubric. A semantic-priority experiment first requires a usable rubric, annotation evidence, agreement checks and meaningful class occupancy.

**Adaptation and accepted updates.** Specify a defensible task sequence, replay policy and acceptance rule before testing the complete adaptation cycle. Retention and new-task quality must both be measured, including failed or rejected updates.

**Execution and allocation.** Evaluate recovery and resource accounting as execution properties. Evaluate budget-allocation policies through separate quality and resource comparisons that include simple alternatives such as fixed allocation and successive halving.

**Physical quantum evaluation.** Start with a frozen predictor and a specific fidelity or measurement question. Qualify a current backend, compiled circuit, measurement budget and comparison with saved classical references. Record the simulator or physical backend used, calibration context, job identities where shareable, and all relevant classical costs. Hardware inference, hardware training and a claim of advantage require different evidence.

These are directions for separately specified studies. Their inclusion here does not launch an experiment or commit a compute budget.

## Contributing and private research

Research v1.0 welcomes independent reproductions, corrections, stronger controls, resource measurements and documented negative findings. Start with a public issue or a permitted pull request and follow the [contribution guide](../CONTRIBUTING.md). Implementation patches require the confirmed incoming-rights route described there.

At least two distinct substantive qualifying merged public contributions establish eligibility for an owner review of private Lab access. Admission is a separate decision based on the evidence, rights, reproducibility, safety, conduct and proposed participation scope. Access is reassessed for each cycle; this does not automatically require two newly earned merges at every transition.

Approved participants receive defined access to the private Research Lab. Strategic development is a separate workstream for specifically authorised internal Q-Pathformer developers. Lab admission does not grant Strategic access. The [governance policy](../GOVERNANCE.md) defines the audiences and approval responsibilities.

For a private-intake enquiry, contact Anthony Siljeg at [asiljeg@alnotrea.com](mailto:asiljeg@alnotrea.com) with a non-sensitive description. Agree the review scope and transfer route before sending restricted material.

## Editions and availability

Public research editions remain available for permitted contributions while the next cycle develops privately. The proposed Research v2.0 Lab will investigate the next defined questions. Following review of the evidence, reproducibility, rights, safety and disclosure scope, an approved selection may become a public Research v2.0 edition. Later editions follow the same process.

Some work may remain private or continue into a later cycle. New Strategic retention or use of contributed private work requires a recorded agreement with the contributor or applicable rights holder and the authorised project representative for the identified assets and purposes. Existing public permissions remain in force. Each release identifies its contents and reproduction boundaries.

Research editions are separate from the public Enterprise Standards releases and Access-PoD document versions. Participation categories are also independent of the architecture's three processing states. See the [research-cycle guide](RESEARCH_CYCLE.md) for the development and publication process.

## Attribution and rights

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.

Existing controlled original content grants and their exclusions remain in force. The [rights and changes](RESEARCH_APPROACH_RIGHTS.md) record identifies the historical grants, current file identities and status of later revisions. Code, datasets, models, third-party material and restricted assets retain their separate terms.
