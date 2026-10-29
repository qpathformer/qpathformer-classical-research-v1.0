# Reproducing study v0.1

The study-v0.1 release explains and selects material from the completed benchmark. It is not the full training archive, an installed runtime or proof of fresh-machine reproducibility. Package startup checks and release seals describe their own selected bytes and verification scope.

## Keep the evidence roots separate

| Root | Role |
| --- | --- |
| `C:\Q2\Full_Local_Benchmark_v0.1` | Completed benchmark: frozen protocols, selected checkpoints, ledgers, predictions, independent analyses, trained-circuit audit and report. |
| `C:\Q2\Implementation_v0.1` | Earlier engineering prototype, local correctness capsule and its historical CPU environment. The prototype's reduced synthetic smoke test is not the AG News study. |

The canonical benchmark README identifies safe rechecks and their dependencies. Its historical paths identify the original context. A different machine or layout needs explicit qualification; do not edit frozen source or protocol files simply to bypass identity checks. Reanalysis and verification outputs belong in new directories outside the preserved evidence trees.

## Different checks answer different questions

1. **Package integrity:** verify the exact file set, every size/hash, internal manifest/checksums and the matching external ZIP seal. This checks delivered bytes, not study conclusions.
2. **Saved-prediction reanalysis:** the retained `analysis/analyse_classical_independently.py` verifies frozen source/data/checkpoint bindings and recomputes the saved text endpoints. Use a new output directory and the full retained study evidence. This does not retrain models.
3. **Local trained-circuit audit:** `ibm_readiness/evaluate_readiness.py` reads frozen protocol and checkpoints relative to the retained study. Use its documented package path and a new output, without `--freeze`. This uses Qiskit/Aer locally and submits no physical jobs.
4. **Full retraining:** follow the two branch READMEs and exact protocols in a separately registered experiment copy. The synthetic study used full 200-epoch runs for seeds 201–205; the default three-epoch prototype smoke run does not reproduce it. The text runner checks frozen source, data and environment identities and resumes incomplete runs; new scientific work needs a new protocol and destination.

No scientific reanalysis, retraining or fresh-install validation was performed to prepare these pages. The historical independent-analysis receipts describe their own recorded checks. The [final package verification record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/FRESH_PACKAGE_VERIFICATION.json) binds the final ZIP and seal to the [bounded startup receipt](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/QPathformer_v0.1_Code.startup.json), which identifies the environment, commands, results and limitations. These package-startup checks are separate from the original training and simulated-shot experiments.

## Recorded environments

The study records Windows and Python 3.12. The numerical/audit environment used NumPy 2.5.4, SciPy 1.18.1, Qiskit 2.6.0 and Qiskit Aer 0.17.2. The full text benchmark used PyTorch 2.11.0 with CUDA 12.8 on an RTX 5090 Laptop GPU, float32, with TF32 and mixed precision disabled. These are recorded historical environments, not a verified current installer recipe or hardware minimum.

Plotting used a separate environment, including NumPy 2.3.5 and Matplotlib 3.11.2. Keep its lock file separate from the analysis runtime. Figure scripts assume Arial and overwrite their output figures; regenerate on a working copy. The report-authoring helpers require the historical template, Word and rendering tools, and contain host-specific paths. The delivered archive contains the final Word document but intentionally excludes the full report QA PDF and page renders.

## Storage accounting

| Boundary | Files | Logical bytes |
| --- | ---: | ---: |
| Payload listed in `DELIVERY_MANIFEST.json` | 2,081 | 9,179,407,633 |
| Delivery manifest itself | 1 | 418,598 |
| Current benchmark tree including manifest | 2,082 | 9,179,826,231 |

On 29 October 2026, the read-only [full frozen-source audit](../provenance/source_verification.json) verified exact membership, sizes and every SHA-256 for all **2,081 payload files**. It hashed **2,036 unique payload file objects**, safely reusing hashes for repeated hardlinks after identity, size and modification-time checks. The 418,598-byte delivery manifest has SHA-256 `03bcfc043585696c1288d926fba882c9cc5be8c36f87681c38bb2f6fa77465c3`. This is a complete source-integrity check, not a new scientific run.

The archive preserves checkpoint hardlink aliases. Counting each observed Windows file ID once gave 2,037 distinct file IDs and **5,369,883,818 unique-file logical bytes**. This is not measured disk allocation or a portable archive size. Copying through a format that expands hardlinks can require the full per-path logical total. Plan for the full **9.18 GB** per independent expanded copy, plus the chosen environment, downloads, temporary extraction and new outputs. A separate full working copy doubles the retained-file allowance to about **18.36 GB**, before those additions. These are storage calculations, not tested RAM, CPU or GPU requirements.

The earlier prototype directory has an installed environment and later result folders; its current tree size is not the completed study's accepted-payload boundary. Do not mix it into the benchmark total or use the later v0.9.5 archive's 117.39 GB figure for v0.1.

## Data and distribution

The benchmark retained AG News for internal research. Its source README records academic/non-commercial context. The small release excludes raw articles, split text, tokenizer contents, trained checkpoints and the full archive. Identified original report prose, table presentation and three figures use the separate CC BY 4.0 scope supplied with the Study package. Controlled original explanatory prose in this Documentation package uses the adopted [guidance scope](../../../GUIDANCE_LICENSE_SCOPE.json); the Code package separately identifies 24 Python files under Platform License 1.0. These grants do not license the datasets, dependencies, models or whole archive. Existing permissions remain applicable within their scopes.

The source manifest, report and original READMEs remain unchanged. [SOURCES.json](../provenance/SOURCES.json) records the exact sources, selected-source checks and storage-measurement boundary for this preparation.
