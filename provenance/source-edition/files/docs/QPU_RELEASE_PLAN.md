# From classical studies to QPU experiments

[Main README](../README.md) · [Research direction](RESEARCH_ROADMAP.md) · [Reproduction boundaries](REPRODUCIBILITY.md) · [Identifier map](../NOTICE.md)

**Planning summary updated 29 October 2026.** This document reconciles the earlier local companion plan with retained study records. It is not an adopted physical-run protocol. No new preparation capsule, physical-device qualification or QPU result is created by this documentation revision.

## What already exists

The research has produced training software, fitted circuit and classical predictors, routers, readouts, local circuit exports and reference results. Selected fitted circuit predictors also have equivalent classical inference implementations. The full evidence archives and trained models remain separately retained; this documentation does not supply those archives as downloads.

Executing a frozen, classically trained circuit on a QPU is **hardware inference**. Updating its parameters through QPU evaluations is **hardware training**. The latter needs a separate experiment. Neither a successful software check nor a small physical fidelity fixture establishes quantum advantage.

## Initial prototype and classical study v0.1

Two distinct artifacts share an early version number:

| Retained artifact | Completed work | Boundary |
| --- | --- | --- |
| `Implementation_v0.1` engineering capsule | Prototype software, circuit fixtures, local compilation and simulator checks. Its eight IBM-interface fixtures used untrained parameter banks. | This small capsule is not the complete trained benchmark. Its sampled shots were simulated. |
| `Full_Local_Benchmark_v0.1` classical study | 45 synthetic circuit/MLP training runs and ten AG News method runs. Local readiness separately checked 30 trained circuit checkpoints across 240 fixture circuits, with 3,686,400 simulated shots. | The readiness record reports zero physical shots and zero hardware jobs. |

The prototype compiled to a local RY/RZ/CX target, rather than qualifying a current device's native instruction set. The earlier companion review also records that the trained-audit QASM exports and the measured simulator copies are distinct, with two-wire mapping assumptions. Before reuse, a new adapter must explicitly verify measurement construction, device-width layout and result-bit mapping; retained exports must not be assumed to be directly submittable.

## Later local preparation

Classical study v0.6 retained **40 trained circuit predictors** across spiral, checkerboard, rare disks and noisy annulus. Its local confirmation record covers **1,920 measurement circuits** and **983,040 simulated Aer shots**, alongside ideal and compiled comparisons. These counts describe different parts of the recorded local checks, not physical-device workloads.

The target was an archived **FakeManilaV2** snapshot, whose properties were dated **27 May 2024**. The snapshot was instantiated locally; it was not a live device qualification or current calibration. The record distinguishes passing matrix/ideal checks from a measured simulator smoke test recorded without a stochastic pass/fail gate.

The earlier companion plan identifies v0.6 as a possible basis for a four-task inference pilot because of its trained predictors, saved router/readout records and explicit measurement preparation. A smaller v0.1 fidelity fixture is another possibility. These are preparation options, not an adopted model-selection decision or a claim that v0.6 has the strongest predictive model.

Later studies have their own emulator, deployment or statistical diagnostics. The completed v0.9.5 allocation comparison does not itself newly qualify a predictor for physical hardware.

## Proposed progression

| Stage | Evidence required |
| --- | --- |
| Define the preparation record | Choose and register the source study, exact predictor and fixture-selection rule. If a new series uses **QPU preparation v0.1**, its proposed prefix `qpu-prep-v0.1` remains planned until a protocol and resulting evidence exist. |
| Freeze an offline candidate | Bind model parameters, preprocessing, router, readout, logical circuits, measurement conventions, ideal references, software versions and provenance. Run the declared offline checks and retain their outcomes. |
| Qualify a current device | Record the selected device and target/calibration snapshot; compile for its gates and topology; verify parameter, layout, observable and result-bit mappings. Test the submission/retrieval adapter and resource accounting. |
| Record a physical pilot | Use a distinct experiment identity and a frozen protocol with measurement budget, endpoints, tolerances, uncertainty method and stopping/retry rules. Retain actual job identifiers, raw results, costs and unsuccessful outcomes. |
| Expand the research | Design broader model comparisons or hardware training separately, with controls and replication appropriate to those new questions. |

The first proposed physical question is how closely the frozen circuit's measurements and predictions agree with the saved ideal reference within a declared budget. A small engineering fixture cannot establish population accuracy, training superiority or practical quantum advantage.

## What remains to be prepared

A candidate must preserve the original prediction rule: input preprocessing, expert selection or weights, circuit parameters and the saved classical readout. Hard routing evaluates the selected expert; soft routing may require every weighted expert. Measurement bases and repeated circuits must be included in resource accounting. A raw bit frequency cannot substitute for a learned readout without changing the model.

Current-device qualification, the submission/result adapter and the physical-run protocol remain to be completed. The protocol must distinguish shot counts, QPU usage, queue time and end-to-end elapsed time; any calibration, mitigation or repeated measurements belong in the declared budget. Raw results, circuit/configuration hashes, layouts, timestamps, software versions and analysis provenance must remain linked to the run.

Keep the future QPU records separate from the classical studies and the planned v2.0 repository distribution. Link any new capsule to its exact source artifacts, preserve the old evidence and label each achieved stage accurately. Repository distribution v2.0 does not imply that a new QPU series has run.

## Evidence and provenance

This is a summary of retained local evidence, not publication of the internal source reports. The following archive-relative records support the distinction between completed checks and future work:

- `Implementation_v0.1/docs/IBM_CAPSULE_GUIDE.txt`: prototype fixture, compilation and simulated-shot scope.
- `Full_Local_Benchmark_v0.1/README.txt`: full training benchmark and trained-readiness counts, including zero physical shots/jobs.
- `Improvement_Study_v0.6/quantum/local_readiness_confirmation/report.json`: local predictor/circuit counts, simulated shots and distinct ideal/measured check statuses.
- `Improvement_Study_v0.6/quantum/device_snapshot/SNAPSHOT_MANIFEST.json`: archived device provenance and property date.
- `Improvement_Study_v0.6/governance/LOCAL_READINESS_PROTOCOL.json`: the retained scope of local preparation.

Those source archives remain under `C:\Q2` and were consulted read-only for this revision. The earlier companion `QPU_RELEASE_PLAN.md`, prepared 27 October 2026 outside the repository, remains a historical draft; its suggested pilot identifiers, shot examples and broader per-version review are not adopted protocols. Source identities and this revision's preparation record are retained separately. No source report, retained scientific result or historical package was modified to prepare this summary.
