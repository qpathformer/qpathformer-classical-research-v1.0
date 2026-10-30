# Study v0.7 research overview

Q-Pathformer v0.7 examines whether grouping nearby inputs into specialist model banks improves classification, and how trained circuit models can run through an equivalent classical representation. Its advances are independent population replication, matched-count routing controls, a wider classical feature baseline and study-specific execution integration.

Eight model recipes were compared on checkerboard, spiral, noisy annulus and rare disks. Confirmation uses eight independently generated populations per task, with two paired optimizer seeds within each population. The completed design has 32 engineering, 64 development and 512 confirmation fits: 608 total. The 576 full fits completed 200 rounds and 15,000 updates each.

## Metrics, routing and replication

All eight arms train stable native-logit BCE. Validation selection and primary comparisons use common clipped natural-log BCE, with clipping to `[1e-7, 1-1e-7]`. Native loss remains separate, as does the later v0.9.5 native-BCE primary outcome. Average two paired optimizer-seed differences within each population, then analyse eight independent population differences per task. The independent sample size is eight, not sixteen checkpoints or prediction rows. Twenty primary contrasts use seven degrees of freedom and nominal 99.75% adjusted t intervals. No paired-record bootstrap is used.

Geometric routing fits frozen k-means groups on training coordinates. The hash control has the same bank count and exact training occupancy; cutpoints are then fixed for validation/test, whose occupancy and class composition are not forced to match. MultiK/MultiHash each have 70 trainable scalars; TrigK/TrigHash each have 125. The comparison changes which examples train each bank, so it remains tied to these data and optimization settings.

Geometric routing achieved lower common clipped BCE than matched-count hash routing for both Multi and Trig25 on all four task families. All eight adjusted routing intervals favor geometric routing; seven establish improvement beyond the 0.01 practical reference, with rare-disk Trig the exception. The result concerns the tested data, feature representations and optimization, not universal routing superiority.

Mean common clipped BCE:

| Recipe | Checkerboard | Spiral | Noisy annulus | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Flexible circuit (MultiK) | 0.50907 | 0.37167 | 0.39927 | 0.01562 |
| Routed Trig25 | 0.26559 | 0.24968 | 0.39400 | 0.01314 |
| Global Trig121 | 0.04971 | 0.07878 | 0.39457 | 0.00827 |

Secondary mean macro-F1:

| Recipe | Checkerboard | Spiral | Noisy annulus | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Flexible circuit (MultiK) | 76.57% | 86.82% | 87.14% | 98.70% |
| Routed Trig25 | 90.18% | 92.42% | 87.75% | 98.94% |
| Global Trig121 | 98.47% | 96.57% | 87.28% | 99.16% |

These are seed averages within populations followed by population means. Reported standard deviations describe population variability, not confidence intervals. Global Trig121 leads the two harder clean tasks, not every metric or family. Routed Trig25 has higher descriptive annulus F1, where its primary contrast with Trig121 is inconclusive. MultiK versus ScalarK has a favorable BCE direction on checkerboard, spiral and annulus, but only spiral establishes improvement beyond 0.01 throughout the adjusted interval. Rare disks are inconclusive. Historical v0.6 means are context, not paired evidence of change.

The eight recipes are not eight classes. Tasks are binary; circuit banks have two qubits, two layers and eight trainable core angles. Angle counts do not enumerate every gate. Similar parameter totals do not isolate feature constraints or optimization geometry.

## Equivalent conversion and timing

Classical conversion preserved every checked class prediction. For matched single-input CPU calls, reported speedups were **4.28–4.58× relative to the original circuit implementation**. Conversion changes how the same fitted predictor is evaluated; it adds no accuracy gain, compression or quantum-advantage claim. The MLP is fastest in the timing tables, and learned Trig controls use the optimized common kernel.

The study converts 192 selected circuit models and repacks 256 learned Trig models for the common kernel. The 448 representations preserve the original router and sigmoid. The algebraic identity applies to the retained two-qubit/two-layer core and affine Pauli readout. Producer circuit-conversion maxima are `9.936e-15` in probability and `7.816e-14` in logit; independent replay across all representations has maxima `1.893e-14` and `9.059e-14`. These are different checks. Every checked class agrees, but finite checks are not a bitwise guarantee for all inputs or a result for arbitrary circuits.

Timing is **microseconds per complete batch call**, including every record, routing, core/features, head and sigmoid; v0.6 used per-record tables. Matched ratios are computed before aggregation, so dividing displayed aggregate cells does not reproduce the estimator. Three sessions and fifteen trials per condition are technical repeats. Session drift is retained, with its cause unmeasured. Trig121 is not uniformly faster at all batch sizes.

Five-bank coefficient tables use 1,000 bare parameter bytes versus 400 for ScalarK or 560 for Multi. Router state, loading, serialization and evidence containers are separate. Construction-only break-even excludes other deployment costs and is not an end-to-end cost guarantee. No compression or accuracy gain is claimed.

## Ideal sampling sensitivity

Equal total simulated budgets are 1,024 or 8,192 per prediction. Scalar uses the full budget in XX; Multi divides it equally between XX and ZZ. Five moments do not mean five independent budgets. Joint multinomial counts retain within-setting covariance. The 1,132,462,080 represented measurement outcomes are local ideal simulation, with no Aer, archived Manila noise, live IBM service or physical shots.

The larger total budget reduces displayed MAE, MSE and class disagreement across all twelve task/arm groups. These deviations are conditional on each checkpoint's ideal prediction. Class disagreement is not label misclassification; a weak classifier can be stable under sampling. Independent replay checked a `2e-12` tolerance; the exact maximum individual probability discrepancy was not retained.

## ETEL naming and scope

The Code package includes the study-specific execution integration for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**, using retained ETEL source version **0.2.0**. It schedules complete registered fits in isolated local processes. The component label, historical source version, study v0.7 and repository edition v1.0 identify different things. This selection is not a standalone ETEL component release.

Model routing selects a parameter bank per input. ETEL schedules an entire registered training fit. Logical 64-slot groups and reported peak ready capacity 192 are bookkeeping; at most five fit workers ran concurrently. These counts do not describe physical processors, model size, qubits or a measured 64×/192× speedup.

The adapter adds persistent claims, process identity, immutable attempts and committed hashes around local whole-fit execution. The study does not test the later v0.9.5 allocation policy or distributed provisioning; the native untrained vector fixture is unused. No matched serial experiment establishes an ETEL parallel speedup. Zero failed training fits/retries is distinct from the separately retained independent-replay wrapper failure before launch. Recovery permits a reviewed fresh attempt where allowed, not exact optimizer/sampler continuation.

The retained `__version__ = "0.2.0"`, original vendor archive name and source guides are unchanged. Both vendor files have current adopted code coverage and matching earlier v0.9.5 grants. CLI help success does not establish Windows recovery, monitoring or resource supervision.

## Packaging and boundaries

The findings concern four small synthetic binary task families on classical CPU hardware. Eight population differences per task and small-sample t assumptions limit generalization. Historical cross-version scores are context, not paired improvement evidence. No physical-QPU performance, device-noise tolerance, full language-architecture benchmark or quantum advantage is established.

Bounded startup verifies exact package integrity before and after execution, parses all 52 Python files, imports NumPy/SciPy and selected modules, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful `--help` from `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`. It does not test all eight model families, independently compare matrices, run conversion parity, execute ETEL fits/recovery, score official data or rerun timing/sampling.

Historical requirements remain observations, including NumPy 2.5.4 and SciPy 1.18.1. Current runtime versions appear in startup receipts. Code retains a 94-byte requirements wrapper; Documentation retains the original 156-byte requirements file. Their differing identities are intentional. Code SOURCE_SELECTION identifies 55 implementation/protocol files; the additional execution README is separately mapped, scoped and inventoried.

The original report's 42 pages plus the edition note produce the 43-page release. Historical paths, internal labels, preparation-stage pending statements and commands are provenance. They are not instructions to launch completed jobs. The v0.9 reference in the retained visual-review disclosure field is cross-study metadata carryover, clarified externally; the report and sealed Study package are unchanged.

The retained archive declares 6,533,819,005 payload bytes plus a 13,147,346-byte manifest: 6,546,966,351 logical bytes. These are archival storage figures, not download sizes, model sizes or RAM minima. This preparation checks selected sources and the manifest identity, not a new full-archive scan.

Identified original report content and explanatory prose use **CC BY 4.0**. The exact selected Python files, including the retained ETEL files and package helpers, are **source available under the unchanged Q-Pathformer Platform License 1.0**. Existing applicable grants remain in force. Package scopes identify exclusions; dependencies, datasets, trained models, architecture documents and whole archives retain separate terms.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony is licensor; affiliations do not transfer ownership.

## Retained source guidance

- [Original README_CONTRACT.txt](source/analysis/deployment/README_CONTRACT.txt)
- [Original README_INDEPENDENT_REPLAY.txt](source/analysis/independent_audit/README_INDEPENDENT_REPLAY.txt)
- [Original README_INDEPENDENT_DEPLOYMENT.txt](source/analysis/independent_deployment/README_INDEPENDENT_DEPLOYMENT.txt)
- [Original README_EVALUATION_CONTRACT.txt](source/analysis/official/README_EVALUATION_CONTRACT.txt)
- [Original README_EXECUTION.txt](source/execution/README_EXECUTION.txt)
- [Original README_REPRODUCIBILITY.txt](source/reproducibility/README_REPRODUCIBILITY.txt)
- [Original requirements-scientific.txt](source/reproducibility/requirements-scientific.txt)
