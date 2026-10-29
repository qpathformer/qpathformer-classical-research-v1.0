# Study v0.2 research guide

The study combines a classical GPU text experiment on DBpedia14 title-plus-content classification with a separate synthetic circuit experiment on parameter sharing across depths. All 94 registered main runs (27 text and 67 circuit-study runs) and eight separate common text warmups completed. Confirmation includes 15 text endpoints and 40 circuit-study endpoints; the latter includes classical control models.

## Findings

The two task families are reported separately:

| Task family | Model | Mean macro-F1 |
| --- | --- | --- |
| Text | Hash18 | 97.659% |
| Text | Current content routing | 97.642% |
| Text | Shared adapters | 97.602% |
| Synthetic circuit study | Untied assigned circuits | 81.44% |
| Synthetic circuit study | Original shared-parameter schedule | 71.83% |
| Synthetic circuit study | Fixed four-layer circuit | 93.32% |
| Synthetic circuit study | Matched-information MLP129 | 99.04% |

The primary text contrast, Hash18 minus current content routing, was +0.01694 percentage points, with paired seed t95 interval [-0.11024, +0.14412]. The interval includes zero: the primary improvement is unresolved, and this is not a demonstration of equivalence.

The primary circuit contrast was binary cross-entropy (untied assigned minus shared schedule): -0.14441, with paired seed t95 interval [-0.15434, -0.13449]. Lower BCE is better. The +9.61 percentage-point macro-F1 difference is secondary.

Paired seed intervals and conditional record-bootstrap intervals answer different questions; they must not be pooled or treated as interchangeable. The matched-information MLP controls input information, not parameter count or compute.

## Interpretation

The text result does not establish a resolved primary improvement. Giving each circuit depth its own parameter bank improved the selected comparison with the original shared-parameter schedule, while increasing allocated angles from 16 to 40. The fixed four-layer circuit and matched-information MLP129 still performed better. This comparison does not isolate a benefit caused solely by scheduling or removal of gradient interference. The text experiment used a classical GPU; the quantum circuits were simulated locally. No physical-QPU execution or quantum advantage is reported. Historical path bindings and exact NumPy replay guards limit relocation. The text and circuit experiments are separate models on separate tasks; their F1 values are not a cross-task ranking or evidence of an integrated quantum text model.

The untied comparison preserved assigned depths, global batches, record visits and parameter-shift circuit-example work. It changed which records updated each parameter, and mean loop time increased 82.35%. These controls do not establish a runtime advantage or isolate the effect of removing gradient interference.

The report preserves all original tables, figures, numerical qualifications and historical recommendations. Read those alongside the original protocols before interpreting comparisons. No ETEL implementation is supplied by this source study.

## Selected evidence

The [original overview](historical/RUN_STATUS.txt) and [reproduction guide](historical/REPRODUCE_INTERNAL.txt) describe the full retained archive. Commands and absolute paths in those files are historical; they are not a batch to run in a curated download.
