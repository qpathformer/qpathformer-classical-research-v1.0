# Research guide — study v0.1

This guide describes the completed local study of 18 October 2026, using its retained report and analysis records. It accompanies release `study-v0.1` in `qpathformer/qpathformer-classical-research-v1.0`. The [study summary](release_notes/study-v0.1.md) gives the findings; [reproduction guidance](docs/REPRODUCIBILITY.md) explains what is needed to check them.

## Two questions, two datasets

The synthetic experiment asks whether assigning different depths within a small shared circuit helps a binary classifier. It predicts whether a two-dimensional point lies inside a central disk. Eight independently assigned allocation categories choose depths `4,4,3,3,2,2,1,1`; they carry no demonstrated semantic quality. This is an early radial task, not the later rare-disk benchmark.

The text experiment asks whether content-routed adapters improve a fixed-budget AG News classifier relative to one shared adapter. It uses real news-topic records, separate from the prototype's hand-authored synthetic smoke examples. The synthetic and text F1 scores concern different problems and cannot be ranked against one another.

## Circuit and classical controls

| Family | Implemented comparison |
| --- | --- |
| Scheduled two-qubit circuit | A shared four-layer parameter bank, with the assigned category controlling the executed prefix depth; 16 angles in the full bank. |
| Shuffled circuit | A shuffled allocation control using the same shared-bank form. |
| Fixed circuits | Independently trained circuits of depths 1, 2, 3 and 4, with 4, 8, 12 and 16 angles respectively. |
| Matched-information MLP | Receives the two features and assigned-depth encoding; 129 parameters. |
| Shuffled-information MLP | Receives the corresponding shuffled-depth information; 129 parameters. |
| Richer-information MLP | Receives the two features and eight-category encoding; 193 parameters. Extra random metadata is not semantic knowledge. |

These nine methods ran over the same five registered seeds. Circuit training used a complex128 NumPy statevector, exact probabilities and parameter-shift derivatives. The MLP used analytic backpropagation. Each run completed 200 epochs; validation BCE selected its checkpoint before the fixed test evaluation. The information-matched comparison does not match parameters, execution depth or training compute.

The benchmark's nested finite-shot sensitivity uses binomial draws from saved exact probabilities at 256, 1,024 and 4,096 samples per test record. Repeated shot seeds remain nested within the trained checkpoints. They are not independent training runs, physical shots or finite-shot training.

## Text architecture and selection

Both text treatments use a six-layer encoder of width 256, four attention heads and feed-forward width 1,024, with bottleneck-16 adapters. The tokenizer uses an 8,192-entry BPE vocabulary and at most 256 tokens. One treatment shares an adapter; the other routes to 18 content adapters using training-only centroids. The encoder continues learning while those centroids remain fixed.

The benchmark corrected BOS/EOS and pooling conventions before its protocol freeze. Its trained classifier is therefore not interchangeable with the earlier reduced prototype smoke runner. Each seed executes a 1,000-update common warm-up once and reuses it for both 10,000-update treatments. The registered endpoint is the latest eligible checkpoint within the budget, not a retrospectively selected peak in a validation plot.

The two endpoint uncertainty summaries answer different questions: paired seed intervals describe training-seed variation on the fixed split; the test-group bootstrap conditions on the ten frozen models. Neither establishes equivalence, broad task generalization or the untested semantic-priority and adaptation claims.

## Local preparation for a later QPU experiment

The earlier prototype capsule checks untrained parameter banks against independent matrices and a local compiler. The later readiness audit instead uses 30 selected trained circuit checkpoints from this benchmark and eight declared validation fixtures per checkpoint. Both are local engineering checks.

The trained audit compares ideal and synthetic-noise profiles using Qiskit/Aer. Its 3,686,400 simulated shots and passing checks do not establish current-device qualification or accuracy on an independent population. The local RY/RZ/CX target is not a selected physical backend's native instruction set. A future physical study needs its own frozen objective, actual backend, calibration, layout/readout verification, adapter and resource limits. No physical run is part of this release.

## Boundaries and figures

The retained report has three figures: frozen quantum test F1; explicitly posthoc validation depth diagnostics; and text learning/routing diagnostics. The report edition preserves these three original figures. The four analytic task graphics used in later project documentation should not be presented as v0.1 experiments. Their original content is identified in the separate adopted report-content scope supplied with the Study package.

This v0.1 source selection does not establish an ETEL component, adaptive training-allocation result, language-model training result or multimodal system. Further hypotheses require separate protocols and evidence. The exact sources used for this guide are recorded in the retained [source preparation index](provenance/SOURCES.json). Controlled original explanatory prose is covered by the adopted [documentation guidance scope](../../GUIDANCE_LICENSE_SCOPE.json); the source records themselves do not expand that grant.
