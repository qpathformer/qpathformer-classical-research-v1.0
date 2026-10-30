# Study v0.8 research overview

Q-Pathformer v0.8 asks whether giving higher-loss training examples more sampling opportunities helps models with fixed input routing. It compares uniform and priority sampling across five circuit and classical model designs on checkerboard, spiral, noisy-annulus and rare-disk tasks.

The study completed 40 short engineering fits, 80 development fits and 640 confirmation fits. Five base models—MultiK, MultiHash, TrigK, TrigHash and TrigG121—each have uniform and priority arms. Confirmation uses eight independent populations per task and two paired optimizer seeds within each population.

## Metrics and primary findings

Four of eight prespecified direct comparisons supported lower common clipped binary cross-entropy (BCE; lower is better) with priority sampling. The other four were inconclusive. None established an absolute reduction greater than 0.01 BCE across its entire adjusted interval.

| Task | Circuit MultiK | Routed TrigK |
| --- | --- | --- |
| Checkerboard | Inconclusive | Lower BCE with priority |
| Spiral | Inconclusive | Lower BCE with priority |
| Noisy annulus | Inconclusive | Inconclusive |
| Rare disks | Lower BCE with priority | Lower BCE with priority |

Priority did not close the routed circuit’s gap to the wider global trigonometric baseline on checkerboard or spiral. Macro-F1 is descriptive; a higher F1 need not imply lower BCE. The findings support further work on representation and routing, with priority retained as an optional training policy.

The primary metric is common clipped natural-log BCE, with probabilities clipped to `[1e-7, 1-1e-7]`. Training and priority scores use native-logit BCE, separately reported as a diagnostic. For spiral TrigK priority, native BCE is 0.250964 while common clipped BCE is 0.240354. The later v0.9.5 native-BCE primary outcome must not be substituted here.

The twenty-comparison family comprises eight direct priority-minus-uniform contrasts, eight geometric-versus-hash priority interactions, and four MultiK-priority versus TrigG121-priority contrasts. Two paired seed differences are averaged within each population before inference across eight population differences. Nominal 99.75% two-sided Bonferroni t intervals use seven degrees of freedom, with small-sample distributional assumptions. No record bootstrap is used. The 0.01 reference is absolute BCE, not a percentage, F1 change or equivalence test; crossing zero means inconclusive.

The two Trig interaction intervals favor geometric routing on checkerboard and spiral, but an interaction alone does not establish absolute priority benefit. Rare-disk MultiK priority has the highest descriptive mean F1 while the global control has lower BCE. F1 plot whiskers are population sample standard deviations, not confidence intervals. There is no universal F1 improvement claim.

## Sampling and model routing

Both policies draw training records with replacement. The first ten rounds are uniform. Subsequent priority probabilities use training-record native losses and remain fixed within a round; inverse-probability weights `1/(N*p_i)` correct raw gradients before the batch mean. The frozen input router is not refitted from priority scores, labels or held-out outcomes. The conditional raw-gradient target remains ordinary empirical BCE; this does not guarantee identical Adam trajectories or improved generalization.

The uniform control also performs scheduled diagnostic refreshes. All full fits use 200 rounds and 15,000 updates, with no early stopping; engineering fits use 12 rounds and 900 updates. Validation-selected predictors are compared after full budgets. The study does not demonstrate end-to-end training savings against an uninstrumented uniform baseline. v0.7 used shuffled passes, so cross-version values remain historical context rather than a paired population pool.

MultiK and MultiHash each have 70 learned predictor scalars, routed TrigK and TrigHash 125, and global TrigG121 121. Router metadata, optimizer state and audit traces are additional. Similar totals do not make function classes or computational costs identical.

## ETEL naming and execution scope

The included adapter belongs to **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1** and retains historical vendor source version **0.2.0**. Priority sampling chooses training examples; model routing chooses the predictor bank for an input; ETEL coordinates complete training fits.

At most five fit processes ran concurrently. The 64 logical slots describe bookkeeping, not 64 physical workers, model banks, qubits or a 64× speedup. This study does not establish the later ETEL suitability-allocation policy or distributed provisioning. Component ETEL v0.1, incorporated source 0.2.0, study v0.8, repository edition v1.0 and future qpu-prep-v0.1 are distinct identifiers.

The original vendor `__version__ = "0.2.0"`, vendor archive/provenance and original guides remain unchanged. This is a study-specific adapter, not a standalone ETEL component release. CLI help is not a Windows execution, recovery, cancellation or resource-supervision test.

## Historical reproduction and conversion

Four preselected clean-directory retrains cover checkerboard MultiK priority, spiral TrigK priority, annulus MultiHash uniform and rare-disk TrigG121 uniform, each population 01 and seed 1601. Data and routers were regenerated using unchanged code in new output directories; the fits were not initialized from trained checkpoints. Historical environment/path bindings and original coordinates were reused, with earlier endpoint evidence used for comparison. These are same-environment reproductions, not new populations, fresh installations or portability tests.

The study converted 256 circuit predictors to coefficient tables and repacked 384 learned Trig predictors. The 640 representations are existing fitted models, not extra efficacy arms. The independent maximum probability discrepancy was 2.615e−14 and every checked class remained unchanged. Algebraic equivalence and finite floating-point checks do not promise bitwise equality or efficient conversion of arbitrary deeper circuits. Release startup does not freshly verify excluded checkpoints.

Group medians of paired original/compiled CPU latency ratios were 4.33–4.59× for batch 1, 11.82–16.03× for batch 32 and 2.33–5.36× for batch 1,024. Timings cover complete resident-model calls, including routing, features and heads, with loading excluded. They are not per-record times or ratios reconstructed from aggregate cells. All three sessions remain included: session three was substantially faster and the cause was not isolated. Technical repetitions are not population replications or hardware-independent guarantees. Several classical controls remain faster in relevant conditions.

The bare circuit payload is 560 bytes, compiled coefficients 1,000 bytes and retaining both 1,560 bytes before router/container overhead. Conversion is not compression, an accuracy gain or quantum hardware acceleration.

## Packaging, viewing and boundaries

All results use classical CPU computation; v0.8 includes no physical-QPU run or new finite-shot experiment. Four synthetic binary task families and eight independent populations per task limit generalization. No quantum advantage or universal training benefit is established.

Bounded startup verifies package integrity before and after execution, parses all 85 selected Python files, checks two inputs through a zero-angle circuit plus a sigmoid comparison, and requires successful help output from three CLI paths. It does not run training, official scoring, conversion parity, timing, ETEL fits/recovery or QPU work. The numerical smoke imports NumPy/SciPy and selected modules; importing `reference_v03` does not constitute an independent matrix comparison. Required help paths are `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`. Receipts record actual versions, exit status and exact final package identities, outside the complete package. All 83 retained scientific Python files and original protocols remain unchanged.

Historical Windows observations include Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1. The supplied review's Linux runtime used different numerical-library versions; neither its checks nor current bounded startup establish a fresh installation or full historical replay. Code SOURCE_SELECTION identifies 87 implementation/protocol files, with an additional execution README separately mapped and scoped.

Use the supplied PDF for the reviewed page layout. The Word edition preserves the editable report content, but pagination and table rendering can vary by application. Check all table rows before exporting a replacement PDF.

The supplied report PDF has 45 pages. Both original and edition DOCX contain all ten Appendix F Spiral cost rows, which appear on supplied-PDF page 38. The review notes report seven rows omitted by LibreOfficeDev 26.8.0.0.alpha0 export; this preparation preserves the complete supplied PDF and does not reproduce that alternative export or infer a Word defect. The cause is unestablished. Historical visual-review metadata includes a v0.9/page-37 sentence that does not describe v0.8; a current external clarification binds the unchanged report. This is provenance correction, not a scientific erratum. Historical source labels and pending workflow statements remain evidence, not instructions to rerun jobs.

The archive's 64,335,733,380 logical payload bytes exclude its manifest and reserved sidecars. This is retained archival accounting, not download size, model size, RAM requirement or a tested hardware minimum. Selected sources and manifest identities are checked; the full excluded archive is not rescanned.

Identified original report content and explanatory prose use **CC BY 4.0**. Exact selected Python files, including retained ETEL files and package helpers, are **source available under the unchanged Q-Pathformer Platform License 1.0**. Existing applicable grants remain in force. Dependencies, datasets, trained models, architecture documents and full archives retain separate terms; package scopes identify covered content and exclusions.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.

## Retained source guidance

- [Original README_PREPARATION.txt](source/analysis/deployment/README_PREPARATION.txt)
- [Original README_REPLAY_CONTRACT.txt](source/analysis/independent_audit/README_REPLAY_CONTRACT.txt)
- [Original README_INDEPENDENT_DEPLOYMENT.txt](source/analysis/independent_deployment/README_INDEPENDENT_DEPLOYMENT.txt)
- [Original README_EVALUATION_CONTRACT.txt](source/analysis/official_evaluation/README_EVALUATION_CONTRACT.txt)
- [Original README_REPRODUCTION.txt](source/analysis/reproduction/README_REPRODUCTION.txt)
- [Original README_EXECUTION.txt](source/execution/README_EXECUTION.txt)
