# Study v0.9 research overview

Q-Pathformer v0.9 tests whether learning how inputs are shared among small experts improves prediction beyond fixed routing and an equally sized output correction. It compares circuit emulation and classical models on four synthetic classification tasks, with a separate Banknote Authentication check.

## Primary findings and inference

Across twelve registered comparisons against fixed-soft routing (C_S), a parameter-count-matched output residual (C_R) and the global G121 control, the learned-soft circuit model (C_L) had lower common clipped binary cross-entropy (BCE; lower is better) in five, higher loss in three and inconclusive differences in four. Table entries describe C_L relative to each control.

| Task | C_L versus fixed-soft C_S | C_L versus residual C_R | C_L versus global G121 |
| --- | --- | --- | --- |
| Checkerboard | Inconclusive | Inconclusive | Higher BCE |
| Spiral | Lower BCE | Lower BCE | Higher BCE |
| Noisy annulus | Inconclusive | Inconclusive | Lower BCE |
| Rare disks | Lower BCE | Lower BCE | Higher BCE |

Three favorable intervals established an absolute reduction greater than 0.01 BCE: C_L versus C_S on spiral and rare disks, and C_L versus G121 on noisy annulus. The annulus result compares model families; its direct routing-control comparisons remained inconclusive. Neither favorable C_L-versus-C_R interval establishes improvement greater than 0.01 throughout the interval.

The clearest routing-specific evidence is on spiral and rare disks, where C_L beats both C_S and C_R. C_L versus hard routing is secondary. The twelve primary comparisons are three controls across four tasks, not twelve isolated gate interventions. G121 remained substantially stronger on checkerboard and spiral and held a smaller BCE advantage on rare disks. A four-feature MLP led the descriptive Banknote check, where most other models received two PCA-derived inputs. The results support task-dependent choices and further work on routing and representation.

Primary common clipped natural-log BCE clips probabilities to `[1e-7, 1-1e-7]`. Native Bernoulli-mixture/logit training loss is separately reported. Do not substitute the native-BCE primary outcome of the later v0.9.5 allocation study. Two paired optimizer-seed differences are averaged within each synthetic population before inference across eight population means. Nominal 99.5833% two-sided Bonferroni t intervals use seven degrees of freedom and small-sample assumptions. Sixteen endpoints are not sixteen independent populations. The 0.01 reference is absolute BCE, not a relative percentage or an F1 change. Crossing zero is inconclusive, not equivalence. Secondary nominal 95% intervals remain separate; there is no pooled task score.

## Model mechanism and training

Nine synthetic arms comprise circuit and trigonometric families, each with hard (H), fixed soft (S), learned soft (L) and fixed soft plus residual (R), plus G121. Banknote adds MLP2, MLP4 and LR2. Circuit H/S have 70 predictor parameters and L/R 82; Trig H/S have 125 and L/R 137. L adds twelve gate coefficients, while R adds twelve output-correction coefficients. Equal counts do not make their function classes, optimization paths or costs identical.

Soft mixtures combine probabilities, not logits. Fixed soft routing remains input dependent. Dense S/L/R evaluate all five experts; hard routing selects one. Centroids and preprocessing are fitted on training inputs. S/L/R share expert initialization and minibatch draws; extra coefficients begin at zero and remain frozen for 750 updates before their own optimizer starts.

v0.9 uses uniform sampling with replacement, not v0.8 priority training. Full fits complete 200 rounds and 15,000 updates. Each round is a fixed budget of 75 minibatches, not an epoch over Banknote. Validation F1 milestones do not cause early stopping. The postfit learned-argmax diagnostic is not a separately trained hard-routing arm. Effective experts summarizes routing weights; it neither counts invoked experts nor demonstrates execution savings.

The registered matrix contains 48 short engineering, 72 development and 636 confirmation fits: 756 in total. Four separate retrains bring the overall count to 760. Synthetic confirmation is 4 tasks × 8 populations × 2 seeds × 9 arms = 576; Banknote contributes 12 arms × 5 seeds = 60. Confirmation included 636 fits: 576 across four synthetic families and 60 on Banknote. Synthetic inference uses eight independent populations per task, with two paired optimizer seeds. Banknote uses one grouped split with five optimizer seeds. Four additional retrains check selected results in the historical environment; they do not add independent populations.

## Banknote interpretation and attribution

Banknote uses one fixed split grouped by identical raw feature vectors before splitting. Specimen and capture-session identifiers are unavailable, so this grouping does not establish independence at those acquisition levels. Five optimizer seeds describe optimization variability on that one split, not five independent datasets.

Most arms receive two PCA-derived inputs. MLP4 receives all four transformed features; MLP2 uses two. Preprocessing is fitted only on training data. MLP4's reported mean BCE is 0.0165 and macro-F1 is 99.12%. Its stronger result compares different input information and architecture; the synthetic population-level inference does not transfer to this fixed split.

The upstream dataset contains 1,372 instances and four features and has its own CC BY 4.0 attribution: Volker Lohweg, Banknote Authentication, UCI Machine Learning Repository, DOI 10.24432/C55P57. [Official dataset record](https://archive.ics.uci.edu/dataset/267/banknote+authentication). Its terms are separate from Anthony's original-content grant. Dataset bytes are not bundled in the curated downloads.

## Reproduction and accepted replay prerequisites

The four clean retrains are checkerboard C_L seed 1801, spiral C_R seed 1801, noisy-annulus T_L seed 1801 and Banknote MLP4 seed 1901. Frozen source, data and protocols were copied into new directories; datasets and routers were not freshly regenerated as in v0.8. Trained checkpoints were not copied as initialization. Original endpoint evidence was later read for comparison. The report displays zero validation/test probability differences for these selected checks. This is same-environment implementation reproducibility, not new populations, a fresh installation, arbitrary relocation or different-hardware replay.

Full historical replay also requires the accepted versioned recovery entrypoints, supporting contracts and protocols, qualification sources and operational bindings retained with the complete study evidence. Some included entrypoints preserve earlier historical implementations. The curated Code ZIP supports source inspection and bounded startup; it does not contain every component used by the final accepted replay.

Excluded versioned directories include `analysis/independent_audit_recovery03/`, `analysis/independent_derived_recovery03/` and `analysis/independent_derived_recovery04/`. Selected entrypoints also require excluded `governance/DEPLOYMENT_PROTOCOL.json`, `governance/REPRODUCTION_PROTOCOL.json` and `analysis/reproduction/tests/test_reproduction.py`.

The included original `analysis/independent_audit/replay_analysis_v09.py` uses `ref.sigmoid` for the postfit argmax diagnostic. Accepted scoring recovery03 uses installed SciPy `expit` there and retains the earlier common-expert-BCE diagnostic arithmetic correction. Independent model, metric and statistical calculations retain their disclosed separate implementations. The narrow shared diagnostic primitive limits independence at that operation; it does not erase all independent verification.

Derived recovery03 adapts dependencies to the accepted scoring lineage. Recovery04 addresses runtime-metadata schema mismatch without changing numerical algorithms, tolerances, models or producer outputs. Historical preparation READMEs predate later accepted runs and are not final completion statuses. This package keeps its selected historical sources unchanged; no omitted recovery implementation is silently added. A fuller reproduction distribution would require its own exact lineage and scope. This revision checks selection boundaries and retained records, not a complete accepted replay.


## Conversion and timing

The study converted 276 circuit predictors and 1,380 expert cores to 25-term trigonometric representations. Routing, learned gates, residuals and Banknote preprocessing remain; a mixture of five converted experts does not become one global 25-term model. Reported maximum Laurent-coefficient discrepancy is 2.132e−14 and maximum complete-pipeline probability discrepancy is 8.382e−15. Exact conversion describes algebraic equivalence with finite floating-point checks, not bitwise equality, another trained efficacy arm or a fresh conversion run during packaging.

Converted predictors were faster than their original emulators in all 2,484 matched endpoint/batch/session conditions. This does not say every raw timing call was faster. Tables use complete-call microseconds, including preprocessing where applicable, routing and residual work, with loading excluded. Three sessions and fifteen timed calls per endpoint condition are technical repetitions; figure spans are observed session ranges, not confidence intervals. All arms and sessions remain included.

Conversion does not establish the fastest overall model. Banknote batch-one means are 21.4 microseconds for MLP4 and 149.6 microseconds for converted C_L. Dense expert evaluation retains its cost. Serialized coefficient/policy sizes are distinct from raw coefficient sizes and do not establish compression. Measurement-setting work counters are simulator accounting; no v0.8 speedup ranges or new finite-shot campaign are imported.

## ETEL naming and resource accounting

This study includes the study-specific execution adapter for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**. Its retained vendor source records version **0.2.0**. ETEL coordinates complete training fits; the learned router controls expert mixture weights within a predictor.

At most five fit workers ran, with one BLAS thread each. Logical blocks of 64 slots are bookkeeping, not physical workers, extra model capacity or demonstrated 64× acceleration. Worker CPU, nested training CPU and stage wall time have different scopes: subtraction does not isolate ETEL overhead and addition can double-count work. Model routing is separate from the later v0.9.5 allocation study.

Repository v1.0, study v0.9, component ETEL v0.1, vendor source 0.2.0 and future qpu-prep-v0.1 are distinct. Historical source version strings, vendor provenance and future v1.1 report language remain unchanged. This selection is not a standalone ETEL release.

## Packaging, reports and limits

Bounded startup verifies exact package integrity before and after execution, parses all 57 Python files, checks two in-memory circuit inputs and a sigmoid calculation, and requires three successful CLI help paths. It does not exercise all model variants, Banknote preprocessing, complete accepted replay, conversion parity or ETEL recovery.

The numerical smoke imports NumPy/SciPy and selected modules; importing `reference_v03` is not independent matrix parity. Required help targets are `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`. Final receipts record actual versions and exact package identity outside the entire extracted package. All 55 scientific Python files and original protocols remain unchanged. SOURCE_SELECTION lists 59 implementation/protocol files plus a separately mapped/scoped execution README: 60 retained payload files. Historical Windows observations are Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1; bounded startup is not fresh-install or Windows process-recovery validation.

Both report formats are preserved. The supplied PDF has 40 pages, including the edition note. The owner-supplied review reports a compatible alternate DOCX rendering without v0.8's missing-row issue; this revision makes no replacement export or universal rendering claim. The v0.9 page-37 operational usage disclosure applies to this report. Historical token equivalents, account debit and operational multipliers are not billed study-specific prices or current pricing. Exact balances are not repeated in current release prose.

Historical internal labels and future recommendations remain source chronology. The old top-level READ_ME is a preserved preparation notice; current START_HERE, the findings report and release evidence guide the reader. No cross-study disclosure correction or automatic redaction is introduced.

The retained archive records 34,582,760,206 logical payload bytes, excluding its manifest and reserved sidecars. That is archival accounting, not download size, model size, RAM requirement or tested hardware minimum. Selected sources and manifest identities are checked; the excluded full archive is not rescanned.

All results use classical CPU computation. No physical-QPU performance, quantum advantage, universally superior model or broad real-world generalization is established. v0.9 includes no new finite-shot campaign.

CC BY 4.0 applies to identified controlled original report content and listed explanatory prose. The unchanged Q-Pathformer Platform License 1.0 applies to exact selected Python files, including the retained ETEL files and package helpers; these are source available. Adopted scopes identify covered content and exclusions. Earlier permissions and separate third-party terms remain in force; datasets, trained models, architecture documents and full archives retain separate treatment.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains licensor; affiliations do not transfer ownership.

## Retained source guidance

- [Original README_EVALUATION.txt](source/evidence/analysis/author/README_EVALUATION.txt)
- [Original README_DERIVED.txt](source/evidence/analysis/deployment/README_DERIVED.txt)
- [Original README_INDEPENDENT_ANALYSIS.txt](source/evidence/analysis/independent_audit/README_INDEPENDENT_ANALYSIS.txt)
- [Original README_INDEPENDENT_AUDIT.txt](source/evidence/analysis/independent_audit/README_INDEPENDENT_AUDIT.txt)
- [Original README_RESOURCE_ACCOUNTING.txt](source/evidence/analysis/independent_audit/README_RESOURCE_ACCOUNTING.txt)
- [Original README_EXECUTION.txt](source/evidence/execution/README_EXECUTION.txt)
- [Original REPRODUCIBILITY.txt](source/REPRODUCIBILITY.txt)
