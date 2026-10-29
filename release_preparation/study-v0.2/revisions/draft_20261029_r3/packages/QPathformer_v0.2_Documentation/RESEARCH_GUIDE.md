# Study v0.2 research guide

The study combines a classical GPU text experiment on DBpedia14 title-plus-content classification with a separate synthetic quantum-circuit schedule experiment. All 94 registered main runs and eight common text warmups completed. Classical confirmation includes 15 endpoints and quantum confirmation includes 40 endpoints.

## Findings

Hash18 text macro-F1 was 97.659%, compared with 97.642% for current content routing and 97.602% for shared adapters. The primary mean gain was 0.01694 percentage points and its paired 95% interval crossed zero. In the quantum task, untied assigned circuits reached 81.44%, the original schedule 71.83%, fixed depth four 93.32%, and the matched-information MLP129 99.04%.

## Interpretation

The text result does not establish a resolved primary improvement. Changing circuit scheduling improved the selected quantum comparison but the fixed-depth and classical controls performed better. This is local simulation, without quantum advantage or physical hardware evidence. Historical path bindings and exact NumPy replay guards limit relocation. The two task families must not be conflated.

The report preserves all original tables, figures, numerical qualifications and historical recommendations. Read those alongside the original protocols before interpreting comparisons. No ETEL implementation is supplied by this source study.

## Selected evidence

The [original overview](historical/RUN_STATUS.txt) and [reproduction guide](historical/REPRODUCE_INTERNAL.txt) describe the full retained archive. Commands and absolute paths in those files are historical; they are not a batch to run in a curated download.
