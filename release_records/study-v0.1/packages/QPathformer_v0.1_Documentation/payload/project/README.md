# Q-Pathformer Study v0.1 — Local Benchmark and QPU Readiness

**Study release study-v0.1 · Repository edition v1.0.** This release brings together the completed v0.1 benchmark, its documentation and selected implementation in `qpathformer/qpathformer-classical-research-v1.0`. The repository edition identifies the collection; each study release retains its experiment identifier.

The v0.1 work created a runnable research prototype and then completed a larger local benchmark. The benchmark trained nine synthetic circuit/MLP methods across five seeds and compared shared versus content-routed text adapters across five paired AG News seeds. A separate local audit checked trained circuits using Qiskit/Aer. No physical QPU jobs or shots were used.

“QPU readiness” here means the historical local circuit-translation and simulator checks called “IBM readiness” in the source report. These checks did not involve physical hardware or qualify a currently selected device.

| Route | Package | Start here |
| --- | --- | --- |
| Study | `QPathformer_v0.1_Study.zip` | The report in PDF and Word, with an edition note, author metadata and its adopted report-content scope. Its source is the retained QPATH-RPT-002 internal report. |
| Documentation | `QPathformer_v0.1_Documentation.zip` | [Study summary](release_notes/study-v0.1.md) and [reproduction boundaries](docs/REPRODUCIBILITY.md). |
| Code | `QPathformer_v0.1_Code.zip` | Selected implementation, dependencies and bounded startup instructions. Read its verification records for the actual checks performed. |

[Open the study-v0.1 release and downloads](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.1).

Keep each ZIP with its matching external seal and verify its internal manifest and checksums. Trained checkpoints, dataset contents, installed environments and the full evidence archive are outside the small-download boundary. The existing study-v0.9.5 release and its packages remain unchanged.

## Main findings

On the synthetic radial classification task, scheduled circuit depth achieved mean test macro-F1 of **73.13%**, compared with **98.52%** for the matched-information MLP and **92.05%** for the fixed four-layer circuit. Information matching did not match parameter count or compute. These results favor the controls on this task and do not establish quantum advantage.

On AG News, shared adapters achieved **91.11%** mean macro-F1 and content routing **91.07%**. The paired difference was **-0.04 percentage points**; the reported uncertainty intervals include zero. This does not establish equivalence or a reliable endpoint benefit from content routing. The two experiments use different datasets and their scores are not a cross-task ranking.

## Benchmark and capsule are distinct

| Evidence | What it establishes |
| --- | --- |
| `Implementation_v0.1` prototype | Connected classical and circuit components, short synthetic smoke runs and an offline capsule. Its capsule used untrained fixture banks and 215,040 simulated shots. |
| `Full_Local_Benchmark_v0.1` study | 45 synthetic training runs and ten AG News method results across five paired seeds, with frozen protocols, held-out reporting and retained evidence. The text methods reuse the common warm-up within each seed. |
| Trained-circuit readiness within the study | 30 trained checkpoints, 240 fixture circuits and 3,686,400 simulated shots. Numerical translation and bounded sampling checks passed locally. |

Both capsule and trained-readiness checks used a local RY/RZ/CX target. They did not qualify a current physical device. Device-native compilation, final layout/readout checks, submission adapter, protocol and resource limits remain necessary for a future hardware experiment.

This study predates the later four-task and ETEL allocation studies. It covers one synthetic radial task and one text dataset. It does not report the later spiral/checkerboard/rare-disk/noisy-annulus suite, a trained language model, multimodal learning or a semantic-priority benefit.

**Licensing:** controlled original prose identified in the [documentation guidance scope](../../GUIDANCE_LICENSE_SCOPE.json) uses **CC BY 4.0**. The Study package has a separate CC BY 4.0 scope for identified original report content, table presentation and three figures. The Code package identifies the exact 24 Python files under the unchanged **Q-Pathformer Platform License 1.0**. These are scoped grants; datasets, dependencies, models, architecture documents and whole archives are not licensed by placement beside them. Earlier grants remain unchanged, including permissions in previously licensed expression wherever reused.

**Attribution:** Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains the named licensor; affiliation does not transfer ownership.

The retained [source preparation index](provenance/SOURCES.json) records the exact local files used to prepare these pages. The [source verification receipt](provenance/source_verification.json) records the complete frozen-source hash audit. No original report, result, protocol or dataset was changed.
