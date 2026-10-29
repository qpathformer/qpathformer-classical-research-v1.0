# Research direction

[Main README](../README.md) · [Research guide](RESEARCH_GUIDE.md) · [QPU preparation plan](QPU_RELEASE_PLAN.md)

This private staging repository describes completed classical studies through **v0.9.5**. Additional classical studies and the curated **v2.0 repository distribution** are planned. The distribution version identifies a collection of materials; it does not rename the completed experiments.

## Completed classical findings

The studies examine circuit and classical predictors, routing, readout design and training allocation. Their tasks, controls and budgets differ, so they are not a single version-to-version leaderboard. The [research guide](RESEARCH_GUIDE.md) introduces the models and task definitions.

In **classical study v0.9.5**, none of the eight registered comparisons established the stipulated 0.01 improvement in native binary cross-entropy for ETEL suitability allocation. Successive halving used less mean native CPU on all four tasks. The [study summary](../release_notes/study-v0.9.5.md) records the statistical method and reproduction limits.

Further classical work can test when learned routing earns its cost, whether allocation can improve on capped successive halving, and how traceability and retrieval support larger systems. Each new study needs a defined comparator, selection rule, budget, primary metric and independent confirmation evidence. Unfinished versions are not presented as results.

## Execution and allocation

**Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1** supports bounded task and worker coordination, execution records for recovery, and resource accounting. Logical task slots are not physical qubits, cores or a measured multiplication of performance. Findings about an allocation policy apply to that policy; execution and recovery functions have their own evidence. The [identifier map](../NOTICE.md) distinguishes the component display version from the incorporated historical ETEL source version.

**UGCCMT — Unit, Group, Colour, Code, Measure, Train** proposes an organization of data identity, grouping, model versions, observations and learning. **TMCCGU — Train, Measure, Code, Colour, Group, Unit** proposes a reverse view for retrieval. Neither framework's name establishes a predictive benefit.

## Future QPU experiments

Classical study v0.1 included a full benchmark and local trained-circuit preparation checks. Later work extended the simulator evidence, including an archived device snapshot in classical study v0.6. These are completed local checks; they do not qualify a currently selected physical device. No physical-QPU results are reported in the completed study series.

A first hardware-inference experiment would freeze a classically trained predictor, router and readout; qualify compilation and measurement mapping for a current device; validate submission and result handling; and declare the measurement budget and comparison with saved references. Hardware training requires a separate protocol and evidence.

The [QPU preparation plan](QPU_RELEASE_PLAN.md) distinguishes retained readiness evidence from the remaining work. Any new preparation series, including the proposed label `qpu-prep-v0.1`, needs its own registered record. A physical run must have a separate experiment identity, protocol and results.
