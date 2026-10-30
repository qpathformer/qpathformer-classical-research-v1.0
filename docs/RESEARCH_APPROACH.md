# Q-Pathformer research approach

**Research edition v1.0 · 30 October 2026.** The owner adopted CC BY 4.0 for controlled original content in this current edition on 31 October 2026, with the recorded exclusions. Existing grants remain in force. See [rights and changes](RESEARCH_APPROACH_RIGHTS.md).

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

The public research collection is intended to provide approved papers, selected code, explanations and provenance. Curated downloads have explicit reproduction boundaries. Some datasets, checkpoints, environments and full evidence archives remain separately retained.

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

Useful contributions include independent reproductions, corrections, stronger controls, numerical checks, clearer resource measurements and documented negative findings. Reports should include enough configuration, provenance and permitted evidence for a reviewer to assess the claim.

The owner-confirmed participation model requires at least two distinct, substantive qualifying merged public contributions to establish eligibility for private Lab access review. Owner approval follows a review of the contribution, rights, reproducibility, safety and participation scope. Eligibility is not automatic admission.

Approved Lab participants may access Enterprise materials within their permissions. Strategic materials remain restricted to organisation owners and are held separately. These are project access categories, not commercial software licence grants. Participation does not promise authorship, publication, a release date or access to every asset or future edition.

Proposed code, datasets, adapters, weights and other artifacts pass through the contribution and asset-review process before merge. Implementation patches must follow the confirmed incoming-rights route in [CONTRIBUTING.md](../CONTRIBUTING.md). That process does not introduce a blanket incoming-contribution agreement. Existing licences and separately agreed permissions continue to apply.

## Editions and availability

The planned public v1.0 foundation brings together the approved main paper, supporting studies and explanatory documents. The proposed private v2.0 Lab will investigate the next questions. A later public edition and subsequent private research cycle follow review of the actual evidence and assets, with scope and access reassessed for each edition.

Not all working material will be distributed. Each release identifies what is included, what is omitted and which limitations affect reproduction. Public permissions already granted remain applicable to their identified content.

The [governance](../GOVERNANCE.md), [contribution](../CONTRIBUTING.md), [evidence](CONTRIBUTION_EVIDENCE.md), [asset-review](ASSET_REVIEW.md) and [publication](RELEASE_POLICY.md) documents provide the operational details. Research claims remain tied to the relevant study rather than to membership or release status.

## Attribution and rights

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.

The existing Research Approach original prose has an adopted CC BY 4.0 scope dated 30 October 2026. The revised edition and its added prose require an explicit current edition/scope record before publication. The grant for the original text remains in force. Code, the main manuscript, datasets, model artifacts, restricted Lab material and third-party expression retain their separately determined terms.
