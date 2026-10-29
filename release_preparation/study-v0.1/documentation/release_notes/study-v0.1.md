# Study v0.1 — local benchmark and IBM readiness

**Draft release for review in the official private repository.** Release `study-v0.1` records the completed local benchmark of 18 October 2026 in `qpathformer/qpathformer-classical-research-v1.0`. Its source report is **QPATH-RPT-002 — Local Benchmark and IBM Readiness Report v0.1**. The derived public-report edition is prepared for owner review; its editorial label does not make the repository or release public.

## Completed scope

- **Synthetic classification:** nine methods × five paired training seeds, 200 epochs per method; 4,800 training, 1,600 validation and 1,600 test records. The binary label is whether `x1² + x2² < 2/π` for points drawn from `[-1,1]²`. Eight independent allocation categories assign circuit depth; they are not semantic-quality labels.
- **Text classification:** shared versus 18 content-routed adapters over five paired AG News seeds. Each method received 1,000 warm-up and 10,000 main updates. The common warm-up was executed once per seed and reused, giving 105,000 actual updates across the study. The fixed data split has 107,951 training, 11,995 validation and 7,600 test records.
- **Local trained-circuit audit:** six circuit methods × five trained seeds × eight declared validation fixtures, producing 240 circuits. Three local profiles and five shot seeds produced 3,600 sampled executions and 3,686,400 simulated shots. Physical shots and hardware jobs were both zero.

## Results and interpretation

| Synthetic method | Mean test macro-F1 | Interpretation |
| --- | ---: | --- |
| Scheduled circuit | 73.13% | Below the information-matched MLP and fixed depth 4. |
| Matched-information MLP | 98.52% | Same feature/depth information; 129 parameters versus 16 circuit angles, with different compute. |
| Fixed depth 4 | 92.05% | A stronger circuit control on this task. |

Scheduled minus matched-MLP macro-F1 was **-25.40 percentage points**, with a descriptive paired-seed 95% interval of **-27.17 to -23.62**. Scheduled minus shuffled circuit depth was **+1.88 points**, with an interval of **-2.74 to +6.49**. The latter remains unresolved with five seeds; an interval spanning zero is not evidence of equivalence. Posthoc validation diagnostics are kept distinct from the frozen outcomes.

AG News mean macro-F1 was **91.11%** for shared adapters and **91.07%** for content routing. The content-minus-shared difference was **-0.04 percentage points**; its descriptive seed interval was **-0.30 to +0.23**, and a separate conditional test-group bootstrap interval was **-0.22 to +0.16**. These describe different uncertainty sources and are not a joint guarantee over new datasets and retraining. Content routing used 52.7% more mean charged wall time in this implementation; timings reflect local execution conditions, and the study made no qualified speedup claim.

The local circuit audit passed its numerical and sampling checks. The synthetic noise profiles were declared stress scenarios, not measured device calibration. This is engineering evidence for translation and sampling, not physical-QPU performance, independent predictive accuracy or quantum advantage.

## What the release should contain

Use the same three-download route as the existing study release: **Study · Documentation · Code**, with names `QPathformer_v0.1_Study.zip`, `QPathformer_v0.1_Documentation.zip` and `QPathformer_v0.1_Code.zip`. Keep each ZIP beside its matching external seal. Package records identify the actual build and checks; a draft upload is not a published release or a new license grant. The published study-v0.9.5 release remains unchanged.

The small release should exclude raw AG News contents, trained model checkpoints, installed environments and the complete reproduction archive. The original report, source READMEs, frozen results and source identities remain preserved. The earlier prototype is background implementation evidence; its untrained capsule is not a substitute for this completed benchmark.

## Reproduction and rights boundaries

The full benchmark's delivery manifest records **9,179,407,633 logical payload bytes**, excluding the **418,598-byte** manifest itself. The current tree contains **9,179,826,231 logical bytes (9.18 decimal GB)** including that manifest. These are archive-file totals, not download sizes, RAM requirements or tested hardware minima. See [reproduction and storage accounting](../docs/REPRODUCIBILITY.md).

Existing v0.9.5 code/report and identified repository-documentation grants remain unchanged. No new grant is inferred for the v0.1 report, selected code, figures or new prose. Dataset and dependency terms remain separate. Any review of reusable content must identify its actual files and rights rather than applying a whole-ZIP label.

Sources: [exact file identities and preparation checks](../provenance/SOURCES.json), particularly the final report, quantum summary, classical aggregate/independent analysis, readiness summary and delivery manifest. The [source verification receipt](../provenance/source_verification.json) records a passing audit of all 2,081 payload paths and SHA-256 values. This preparation did not rerun training, recalculate the full statistical analysis or execute QPU work.
