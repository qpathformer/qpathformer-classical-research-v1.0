# Q-Pathformer Study v0.1 — Local Benchmark and QPU Readiness

**Study release study-v0.1 · Repository edition v1.0.** This release records the completed local benchmark of 18 October 2026 in `qpathformer/qpathformer-classical-research-v1.0`. Its source report is **QPATH-RPT-002 — Local Benchmark and IBM Readiness Report v0.1**. The report edition preserves the scientific content, tables and figures, with updated author metadata and an edition note.

“QPU readiness” here means the historical local circuit-translation and simulator checks called “IBM readiness” in the source report. These checks did not involve physical hardware or qualify a currently selected device.

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

## Downloads

The [study-v0.1 release](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.1) supplies **Study · Documentation · Code** as `QPathformer_v0.1_Study.zip`, `QPathformer_v0.1_Documentation.zip` and `QPathformer_v0.1_Code.zip`. Keep each ZIP beside its matching external seal and open its START_HERE instructions. Package records identify the delivered bytes and checks. The existing study-v0.9.5 release and its packages remain unchanged.

The small release excludes raw AG News contents, trained model checkpoints, installed environments and the complete reproduction archive. The original report, source READMEs, frozen results and source identities remain preserved. The earlier prototype is background implementation evidence; its untrained capsule is not a substitute for this completed benchmark.

## Reproduction and rights boundaries

The full benchmark's delivery manifest records **9,179,407,633 logical payload bytes**, excluding the **418,598-byte** manifest itself. The current tree contains **9,179,826,231 logical bytes (9.18 decimal GB)** including that manifest. These are archive-file totals, not download sizes, RAM requirements or tested hardware minima. See [reproduction and storage accounting](../docs/REPRODUCIBILITY.md).

Controlled original report content, table presentation and three figures use **CC BY 4.0** under the separate scope in the Study package. Identified original explanatory prose uses CC BY 4.0 under the [documentation guidance scope](../../../GUIDANCE_LICENSE_SCOPE.json). The exact 24 Python files identified in the Code package use the unchanged **Q-Pathformer Platform License 1.0**. Existing v0.9.5 and repository grants remain unchanged, including permissions in already-licensed expression wherever reused. Datasets, dependencies, models, architecture documents and whole archives are outside these grants; no whole-ZIP license is implied.

Sources: [exact file identities and preparation checks](../provenance/SOURCES.json), particularly the final report, quantum summary, classical aggregate/independent analysis, readiness summary and delivery manifest. The [source verification receipt](../provenance/source_verification.json) records a passing audit of all 2,081 payload paths and SHA-256 values. This preparation did not rerun training, recalculate the full statistical analysis or execute QPU work.
