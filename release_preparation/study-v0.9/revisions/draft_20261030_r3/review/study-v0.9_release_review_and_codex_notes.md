# Q-Pathformer Study v0.9 — Release review and Codex revision notes

**Review date:** 30 October 2026  
**Owner:** Anthony Siljeg  
**Repository:** `qpathformer/qpathformer-classical-research-v1.0`  
**Reviewed preparation:** `study-v0.9 / draft_20261029_r2`  
**Purpose:** Prepare a corrected private release candidate and clearer reader-facing release notes. This review does not publish a release, change visibility, adopt a new license or run a new scientific experiment.

## 1. Decision

**Retain the study, report edition and headline numerical findings. Make a focused packaging and explanatory revision before final publication preparation.**

All three supplied ZIP/seal pairs pass independent local integrity checks. All six attachment hashes match the v0.9 draft. The original report content is preserved, the supplied PDF is readable, and the adopted rights records are consistent.

The main technical defect is the same helper defect demonstrated independently in this v0.9 selection: optimization can remove acceptance checks while the verifier or startup helper still reports PASS. Duplicate integrity records are also accepted. These defects concern handling of failures; the genuine supplied package passes the independent checks and bounded startup.

A v0.9-specific documentation improvement is needed: the curated Code ZIP contains selected historical entrypoints but omits the accepted recovery implementations and some protocols required for full replay. State those prerequisites explicitly.

| Priority | Revision | Completion condition |
| --- | --- | --- |
| Before final packaging | Correct both package helpers and duplicate-record handling | Changed or incomplete packages cannot produce false PASS results |
| Before final review | Gate startup on verification and bind its receipt to the final package | Exit codes, pre/post checks and package identity agree |
| Before release wording is finalized | Describe the twelve comparisons as learned-soft model comparisons against named controls | The three practical-reference results are not all attributed causally to learning the gate |
| Before final review | Expand reproduction prerequisites to cover accepted recovery code and protocols | The curated selection is not presented as a complete accepted replay distribution |
| Before final wording is finalized | Explain Banknote input differences and ETEL naming | Readers can distinguish information, model routing and execution coordination |
| At final authenticated handoff | Verify uploaded identities, immutable links and release state | The selected GitHub candidate matches the final Q2 artifacts |

Two findings from earlier releases **do not carry over**. The v0.9 page-37 usage disclosure is accurate for this report, and the alternate DOCX rendering did not show the v0.8 missing-row problem. Do not create corrections for either issue here.

No new scientific training is needed for these release corrections.

## 2. Review scope and evidence

The active draft is the first v0.9 section of `Pasted markdown(6).md`; its later release sections are context. The review used the three attached ZIP/seal pairs, all extracted members, the original v0.9 DOCX from the earlier research collection, retained guidance, protocols, selected code and current rights/provenance records.

Checks included ZIP paths and CRCs; exact membership; manifest/checksum/source-map/seal bindings; duplicate JSON keys; local Markdown links; Python syntax and static imports; report XML/media preservation; visual inspection of all supplied-PDF pages; an independent DOCX export; bounded startup; and specific failure probes on disposable copies.

The genuine startup ran here with **Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0**. The recorded scientific environment is **Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1** on Windows. A bounded Linux startup pass does not validate the historical environment, Windows ETEL process behavior or clean installation.

No training, optimizer updates, official scoring, shot sampling, timing experiment, ETEL fit launch/recovery/cancellation, QPU job or dependency installation ran. The excluded full archive and its experimental arrays were not rescanned or recomputed. Numerical findings below were checked against report, protocol and source consistency.

The available authenticated GitHub connection returned 404 for the pinned package-verification and draft-receipt records. That does not prove those private records are absent or invalid. Live release state and authenticated asset-download identity remain for the final release environment.

### Source key

Paths below are relative to the corresponding extracted package unless otherwise stated.

| Key | Evidence |
| --- | --- |
| S1 | Study: `reports/QPathformer_v0.9_Report_Edition_1.pdf` and matching DOCX |
| S2 | Code: `payload/study/governance/STUDY_PLAN.json`, `ANALYSIS_PROTOCOL.json`, `RUN_MATRIX.json` |
| S3 | Code: `payload/study/quantum/models.py`, `routers.py`, `prepare_data.py`, `study.py` |
| S4 | Code: `payload/study/analysis/independent_audit/statistics_v09.py`, `replay_analysis_v09.py` and related reference code |
| S5 | Code: `payload/study/analysis/deployment/` and `analysis/reproduction/` |
| S6 | Documentation: `OVERVIEW.md`, `REPRODUCTION_BOUNDARIES.md`, `source/REPRODUCIBILITY.txt` and historical phase READMEs |
| S7 | Code: `tools/verify_package.py`, `tools/startup_check.py`, `QUICKSTART.md`, `DEPENDENCY_INVENTORY.json` |
| S8 | Every package: adoption/scope records, legal texts, source maps, manifests and checksums; Code inherited-license map |
| S9 | Study: `provenance/EDITION_CHANGES.json`, `EDITION_CHANGES.md`, `VISUAL_REVIEW.json`, `RENDER.json` |
| S10 | Earlier collection: `readmes/v0.9/INDEX.md`, recovery READMEs 006/011/012 and `032_READ_ME.txt` |

## 3. Scientific finding: keep the result, identify the controls

### What the twelve primary comparisons actually test

The primary family compares the learned-soft circuit model **C_L** with:

- **C_S:** fixed soft routing;
- **C_R:** fixed soft routing plus a parameter-count-matched output residual;
- **G121:** the wider global trigonometric control.

Each comparison is made separately on checkerboard, spiral, noisy annulus and rare disks. C_L versus hard routing is secondary; it is not part of the twelve primary contrasts. [S1, pp. 5–7; S2; S4]

The draft's **five favorable, three unfavorable and four inconclusive** counts are correct. Prefer “the learned-soft circuit model had lower BCE in five comparisons” to “learned routing won five.” The former accurately describes comparisons with different controls without attributing every difference to the gate itself.

Use **common clipped binary cross-entropy (BCE; lower is better)** at first mention. The primary metric uses natural logarithms and probabilities clipped to `[1e-7, 1-1e-7]`. Native Bernoulli-mixture/logit loss is the training objective and a separate diagnostic. Do not substitute the native-BCE primary-outcome wording used in the later v0.9.5 allocation study.

### Private numerical cross-check

The following values are rounded report values for editorial verification. The public release can summarize the interpretation and link to the report.

| Task | Contrast | Mean BCE difference | Adjusted interval | Interpretation |
| --- | --- | ---: | --- | --- |
| Checkerboard | C_L − C_S | −0.0181 | [−0.0420, +0.0057] | Inconclusive |
| Checkerboard | C_L − C_R | −0.0036 | [−0.0244, +0.0172] | Inconclusive |
| Checkerboard | C_L − G121 | +0.4673 | [+0.4360, +0.4987] | Favors G121 |
| Spiral | C_L − C_S | −0.0422 | [−0.0576, −0.0267] | Favors C_L; exceeds 0.01 reference |
| Spiral | C_L − C_R | −0.0244 | [−0.0474, −0.0013] | Favors C_L; 0.01 not established |
| Spiral | C_L − G121 | +0.2528 | [+0.2264, +0.2793] | Favors G121 |
| Noisy annulus | C_L − C_S | −0.0035 | [−0.0123, +0.0053] | Inconclusive |
| Noisy annulus | C_L − C_R | +0.0012 | [−0.0055, +0.0079] | Inconclusive |
| Noisy annulus | C_L − G121 | −0.0223 | [−0.0315, −0.0131] | Favors C_L; exceeds 0.01 reference |
| Rare disks | C_L − C_S | −0.0225 | [−0.0302, −0.0147] | Favors C_L; exceeds 0.01 reference |
| Rare disks | C_L − C_R | −0.0097 | [−0.0131, −0.0064] | Favors C_L; 0.01 not established |
| Rare disks | C_L − G121 | +0.0072 | [+0.0044, +0.0101] | Favors G121 |

The three intervals establishing more than **0.01 absolute BCE reduction** concern spiral versus C_S, annulus versus G121, and rare disks versus C_S. **The annulus result does not isolate a benefit from learning the router:** its C_L-versus-C_S and C_L-versus-C_R comparisons remain inconclusive.

The clearest routing-specific evidence appears on spiral and rare disks, where C_L beats both C_S and C_R. Neither C_L-versus-C_R interval establishes a minimum improvement exceeding 0.01. G121 remains substantially stronger on checkerboard and spiral and has a smaller established BCE advantage on rare disks. Preserve that third unfavorable result even if the short lead emphasizes the two large gaps.

### Statistical interpretation

Two paired optimizer-seed differences are averaged within each synthetic population. Inference uses **eight independent population means per task**, Student-t **df = 7**, and nominal **99.5833% intervals** for the twelve-comparison Bonferroni family. It does not use sixteen independent population replicates or treat all confirmation endpoints as independent statistical units. [S1, p. 5; S2; S4]

The 0.01 reference is an absolute BCE difference, not a one-percent relative improvement or an F1 percentage-point change. An interval crossing zero is inconclusive; it does not establish equivalence. Keep the small-sample assumptions, task-specific analysis and secondary/descriptive status of macro-F1. Secondary nominal 95% intervals must not be merged with the corrected primary family. There is no pooled task score.

## 4. Make the model mechanism understandable

A suitable opening question is:

> Does learning how inputs are shared among small experts improve prediction beyond fixed routing and an equally sized output correction?

Nine arms run on each synthetic family. The circuit and trigonometric families each include hard routing, fixed soft routing, learned soft routing and a fixed soft model with a residual. G121 supplies the global control. Banknote adds three further classical controls. [S1, pp. 2–4; S3]

| Variant | Circuit parameters | Trigonometric parameters | Behavior |
| --- | ---: | ---: | --- |
| Hard H | 70 | 125 | Selects one expert using geometric routing |
| Fixed soft S | 70 | 125 | Combines all five expert probabilities using a fixed, input-dependent geometric routing rule |
| Learned soft L | 82 | 137 | Learns twelve additional routing coefficients |
| Fixed soft plus residual R | 82 | 137 | Adds twelve output-correction coefficients |

The gate and residual have matched added parameter counts, but different function classes, optimization paths and costs. Soft mixtures combine **probabilities**, not logits. All five experts are evaluated by the dense soft variants; hard routing evaluates one.

The geometric centroids and preprocessing are fitted using training inputs. S/L/R share expert initialization and minibatch draws. The extra coefficients start at zero and remain frozen for 750 updates before their own optimizer starts. These controls support the intended comparison without establishing universal superiority.

**v0.9 uses uniform sampling with replacement.** It studies learned routing; v0.8's priority-sampling intervention is historical context. Do not describe this release as continuing priority training unless explicitly discussing that earlier study.

The postfit argmax diagnostic is not a separately trained hard-routing arm. “Effective experts” is a routing-weight summary, not a count of invoked experts or an execution saving. Dense models still evaluate all five. Keep these distinctions in detailed guidance rather than adding them all to the release lead.

## 5. Banknote: retain the information difference

The Banknote check is secondary and descriptive. It uses one fixed grouped split and five optimizer seeds. Identical raw feature vectors are grouped before splitting, but specimen/capture-session identifiers are unavailable, so grouping does not establish independence at those acquisition levels. [S1, pp. 4, 16–18; S3]

Most arms receive **two PCA-derived inputs**. **MLP4 receives all four transformed features**, while MLP2 uses two. Preprocessing is fitted on training data only. The report gives MLP4 mean BCE **0.0165** and macro-F1 **99.12%**. Its stronger result should retain the qualification that input information and architecture differ.

Recommended wording:

> A four-feature MLP led the separate Banknote check. Most other models received two PCA-derived inputs, so this result compares different information and model configurations. Five optimizer seeds on one fixed split describe optimization variability.

Do not present those five seeds as independent datasets or extend the synthetic population-level confidence interpretation to Banknote.

The official [UCI Banknote Authentication record](https://archive.ics.uci.edu/dataset/267/banknote+authentication) confirms 1,372 instances, four features, DOI [10.24432/C55P57](https://doi.org/10.24432/C55P57), and upstream CC BY 4.0 terms. Preserve the dataset's own attribution and terms separately from Anthony's original-content grant. Dataset bytes are excluded from these curated downloads; the report citation does not imply they are bundled.

## 6. Counts and clean retraining

The registered matrix is internally consistent:

| Stage | Fits | Scope |
| --- | ---: | --- |
| Engineering | 48 | Short implementation-qualification fits |
| Development | 72 | Synthetic development without outcome-based arm removal |
| Confirmation | 636 | 576 synthetic plus 60 Banknote fits |
| Separate clean retrains | 4 | Preselected same-environment reproduction checks |

There are **756 registered fits**, plus four retrains, giving 760 overall. Synthetic confirmation is four tasks × eight populations × two seeds × nine arms. Banknote confirmation is twelve arms × five seeds on one split. These arithmetic details belong in review evidence; the release can simply state 636 confirmation fits and the independent-population design. [S1, p. 5; S2]

Full fits complete 200 rounds and 15,000 updates. A round is a fixed sampling/update budget, not an epoch over Banknote. Validation F1 milestones do not introduce early stopping.

The four clean retrains are:

| Task | Arm | Optimizer seed |
| --- | --- | ---: |
| Checkerboard | C_L | 1801 |
| Spiral | C_R | 1801 |
| Noisy annulus | T_L | 1801 |
| Banknote | MLP4 | 1901 |

**This version copies frozen source, data and protocols into clean directories.** It does not regenerate fresh datasets and routers as described for v0.8. Trained checkpoints are not copied as initialization; original endpoint evidence is later read for comparison. The report records zero displayed validation/test probability differences for the four selected checks. [S1, p. 23; S5]

They establish selected same-environment implementation reproducibility, without adding independent populations or proving a fresh installation, arbitrary relocation or different-hardware replay.

## 7. Conversion, timing and ETEL

### Conversion preserves the routed predictor

The report describes **276 circuit predictors and 1,380 expert cores**: four circuit arms across 64 synthetic endpoints and five Banknote endpoints per arm, with five cores per predictor. Each core converts to a 25-term trigonometric representation. Routing, learned gates, residuals and Banknote preprocessing remain. A mixture of converted experts does not become one global 25-term model. [S1, p. 23; S5]

The reported maximum Laurent-coefficient discrepancy is **2.132e−14**, and the maximum complete-pipeline probability discrepancy is **8.382e−15**. “Exact conversion” refers to the algebraic representation with checked floating-point agreement. It does not imply bitwise equality, a newly trained efficacy arm or a fresh conversion verification in this packaging review.

### Timing remains a local deployment result

The report finds the converted predictors faster than their original emulators in all **2,484 matched endpoint/batch/session conditions**. Those conditions are technical comparisons, not independent accuracy replications or proof that every raw timing call is faster.

Displayed timings are **complete-call microseconds**, not per-record rates. They include input preprocessing where applicable, routing and residual calculations; loading is excluded. Each value summarizes three sessions, with fifteen timed calls per endpoint condition. Figure spans show observed session ranges rather than confidence intervals. Keep all arms and sessions. [S1, pp. 24–33]

Conversion does not establish the fastest overall model. For example, the Banknote batch-one table shows MLP4 at 21.4 microseconds and converted C_L at 149.6 microseconds. Dense expert evaluation retains a cost. Serialized coefficient/policy sizes are not raw coefficient sizes or evidence of compression.

Do not copy the v0.8 speedup ranges or session-drift figures into this release. The study contains no physical-QPU result, hardware speedup claim or new finite-shot campaign; measurement-setting work counters are simulator accounting.

### ETEL naming and role

ETEL **is included**. Use this bridge in `OVERVIEW.md`, the Code introduction and, briefly, the release body:

> This study includes the study-specific execution adapter for Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1. Its retained vendor source records version 0.2.0. ETEL coordinates complete training fits; the learned router controls expert mixture weights within a predictor.

Preserve the vendor source version and provenance. At most five fit workers ran, with one BLAS thread each. Logical blocks of 64 slots are bookkeeping, not 64 physical workers, extra model capacity or demonstrated 64× acceleration.

Worker CPU, nested training CPU and stage wall time have different scopes. Subtracting them does not isolate ETEL overhead, and adding them double-counts work. Keep model-routing results separate from the later v0.9.5 training-allocation study.

Repository edition **v1.0**, study **v0.9**, component **ETEL v0.1**, vendor source **0.2.0** and future **qpu-prep-v0.1** identify different things. The historical report's future v1.1 language remains source chronology.

## 8. Make the omitted accepted replay implementation explicit

The Code ZIP is an accurate selected-source package, but it is not the complete final accepted replay distribution.

It contains the original `analysis/independent_audit/replay_analysis_v09.py`, whose postfit argmax diagnostic uses `ref.sigmoid`. The report records accepted scoring recovery03 using installed SciPy `expit` for that diagnostic. The recovery lineage also preserves the earlier common-expert-BCE diagnostic arithmetic correction. Independent model, metric and statistical calculations retain their disclosed separate implementations. [S1, p. 36; S4; S10]

The accepted lineage involves separately versioned directories absent from this Code ZIP:

- `analysis/independent_audit_recovery03/`;
- `analysis/independent_derived_recovery03/`;
- `analysis/independent_derived_recovery04/`.

Recovery04 addresses the recorded runtime-metadata schema mismatch; it does not change numerical algorithms, tolerances, models or producer outputs. Historical recovery README preparation statuses precede later accepted runs; they should not be mistaken for the final completion status.

The selected entrypoints also refer to excluded prerequisites including:

- `governance/DEPLOYMENT_PROTOCOL.json`;
- `governance/REPRODUCTION_PROTOCOL.json`;
- `analysis/reproduction/tests/test_reproduction.py`.

The earlier research README collection documents this lineage; the selected file set confirms the omissions. This review did not independently validate the omitted accepted source bytes or execute the complete accepted replay.

Add this paragraph to current reproduction guidance:

> Full historical replay also requires the accepted versioned recovery entrypoints, supporting contracts and protocols, qualification sources and operational bindings retained with the complete study evidence. Some included entrypoints preserve earlier historical implementations. The curated Code ZIP supports source inspection and bounded startup; it does not contain every component used by the final accepted replay.

Keep the original scientific files unchanged. Do not patch their path guards, replace their numerical primitives or silently add an unreviewed recovery implementation to make the small ZIP appear self-contained. If a fuller reproduction distribution is later prepared, identify its exact accepted source lineage and scope separately.

The narrow shared SciPy diagnostic primitive is a disclosed limit on implementation independence. It is neither evidence of wholly independent implementations at every operation nor grounds for dismissing all independent verification.

## 9. Correct the package helpers

### Actual failure behavior

The supplied verifier uses `assert` for membership, path containment, symlink, size and hash checks. The startup helper uses `assert` for moment validity and CLI success/help output. Python optimization removes assertions; `-B` only controls bytecode writing. See the official [assert reference](https://docs.python.org/3.12/reference/simple_stmts.html#the-assert-statement) and [command-line/environment documentation](https://docs.python.org/3.12/using/cmdline.html).

Focused probes on disposable copies produced:

| Probe | Normal Python | `-O` | `PYTHONOPTIMIZE=1` |
| --- | --- | --- | --- |
| Change covered `START_HERE.md` bytes; run verifier | Rejects, exit 1 | Incorrect PASS, exit 0 | Incorrect PASS, exit 0 |
| Remove the required execution launcher; run startup | Rejects, exit 1 | Incorrect PASS, exit 0 | Incorrect PASS, exit 0 |

The optimized missing-launcher startup reported PASS while its child return codes were **0, 2, 0**.

A duplicate checksum line also passed. An identical duplicate manifest entry passed after refreshing the manifest's checksum solely to isolate duplicate-record handling. External trusted seal hashes detect these changed integrity files; the internal verifier nevertheless should reject duplicate records rather than collapse them into sets or dictionaries. The actual supplied records contain no duplicates.

### Focused Codex changes

1. Replace acceptance-critical assertions in both new package helpers with explicit validation and nonzero failure paths. Cover numerical validity, required child status/help output, membership, paths, sizes and hashes.
2. Reject duplicate manifest paths, checksum paths and JSON object keys before set/dictionary construction. Reject malformed entries and unsafe or ambiguous paths while preserving exact membership checks.
3. Keep required CLI targets explicit. Missing files or failed commands must never be silently skipped or accepted.
4. Gate startup on successful verification and verify bytes afterward. Bind the accepted receipt to the final package and actual interpreter/dependency versions.
5. Make the PowerShell quickstart stop after a nonzero verification/startup exit. Its current independent command lines do not enforce that sequence.
6. Keep receipts outside the complete extracted tree and preserve old accepted receipts with revision-specific names. The helper currently writes stdout only; there is no internal receipt writer whose overwrite behavior should be invented.
7. Regenerate current helper/source/scope/integrity bindings transparently. Preserve retained scientific code and historical r2 packages.

The genuine v0.9 package passed pre-verification, startup and post-verification, with unchanged files and all three help commands exiting zero. All 57 Python files parsed; the import-root inventory matches the selected files and helpers.

Actual startup covers numerical imports, two in-memory circuit inputs, a sigmoid calculation and three CLI help paths. It does not exercise all v0.9 model variants, independent matrix parity, Banknote preprocessing, complete accepted replay or ETEL recovery. Importing a reference module does not establish those checks.

After correction, rerun the valid-package and demonstrated failure cases under normal Python and both optimization mechanisms. Explicit checks may operate under optimization, or optimized operation may be rejected clearly. A false success result is unacceptable. No training or expanded scientific campaign is required to verify these helper fixes.

## 10. Report, disclosure and rights review

### Report preservation and rendering pass

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| Original internal DOCX | 1,113,738 | `6f35101e9d3fda4581c2ef7102d0b330c89cd3bacc1771cf0c0e21b5db556ad8` |
| Edition 1 DOCX | 1,114,685 | `6dd007d63937e67518b1fe312cdeb5b28596d06689f03c992be087a18d862244` |
| Supplied edition PDF | 2,177,249 | `13098d61dd1737f5f8646a3e56f8f85789aaabf909b954c0fc75db9ca2cd38ec` |

All 172 original body elements remain an exact XML prefix, with seven appended edition-note elements. All 37 tables and six embedded images are unchanged. Only document-body and core-metadata parts differ among the 25 DOCX parts. [S1, S9]

All 40 supplied-PDF pages were visually inspected and found readable. A fresh export using LibreOfficeDev 26.8.0.0.alpha0 also produced 40 pages, with identical whitespace-normalized text on every corresponding page; representative rendered pages were inspected. **No v0.8-style missing-row issue was found here.** This does not claim universal rendering equivalence across all applications.

Source DOCX timestamps describe the 22 October report, while the explicit edition note and PDF metadata identify 29 October edition preparation. Those dates record distinct events.

### Historical labels and page 37

The report's original “INTERNAL RESEARCH — NOT FOR PUBLICATION” label, future-study recommendations and old preparation READMEs are preserved historical wording. The appended edition note explains the current preservation edition. Current navigation should direct readers to `START_HERE.md`, the final findings report and current release records.

The original top-level `READ_ME.txt` really is a stale preparation notice; its earlier preserved copy was checked. Explain that in detailed provenance if needed, but remove it from the release lead. It need not distract a new reader from the completed study.

**The page-37 account/credit/token disclosure is accurate for v0.9.** Do not apply the foreign-version receipt correction from v0.7/v0.8. The report retains operational usage and account observations, with an explicit cutoff and qualifications. Token-derived equivalents, an operational multiplier and observed account debit do not establish a billed study-specific price. [S1, pp. 36–37; S9]

Avoid repeating exact account-balance values in public release prose or making current pricing claims from the historical estimates. The current private preservation edition can remain unchanged. If a narrower public report edition is later chosen, identify that edition and any omissions explicitly; preserve the historical original.

A bounded scan found no matches for the credential-shaped patterns checked. The operational accounting described above is not an authentication credential. No automatic redaction or new licensing-adoption requirement follows from its presence.

### Adopted licensing is consistent

All three packages record **ADOPTED on 29 October 2026**, with Anthony Siljeg as licensor and exact scope bindings intact. All packaged Python files, listed explanatory prose and identified original report content are covered by their stated scopes. The unchanged Platform 1.0 and CC BY 4.0 legal texts agree across packages. Earlier whole-file and shared-expression mappings were checked against available prior source bytes. [S8]

Do not revert current scopes to “proposed” using older draft history. Preserve earlier grants, third-party terms and the separation between code, report/prose, datasets, model artifacts, architecture documents and full archives.

The report's CC BY grant is separate from the Platform code terms. Publisher hashes identify the edition; they do not impose original-hash/filename requirements on permitted adaptations. The [CC BY 4.0 legal text](https://creativecommons.org/licenses/by/4.0/legalcode.en) governs its reuse conditions.

When helpers or current explanatory files change, update current exact identities and provenance transparently under the applicable authority. Preserve historical adoption/scope records and permissions; do not claim changed files were the exact old attachment or silently broaden a grant.

Retain the attribution:

**Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.**

Affiliations do not imply ownership transfer. Licensing, release publication and repository visibility remain separate.

## 11. Proposed shorter release body

Keep the title:

**Q-Pathformer Study v0.9 — Learned Routing and Classical Controls**

Use the body below after the packaging corrections have passed. Replace the historical r2 evidence link with the actual final immutable revision. Do not claim corrected helper checks passed before they have run.

---

**Draft for owner review · Study · Documentation · Code**

Q-Pathformer v0.9 tests whether learning how inputs are shared among small experts improves prediction beyond fixed routing and an equally sized output correction. It compares circuit emulation and classical models on four synthetic classification tasks, with a separate Banknote Authentication check.

### Main findings

Across twelve registered comparisons against fixed-soft routing, a parameter-count-matched residual control and the global G121 baseline, the learned-soft circuit model had lower common clipped binary cross-entropy (BCE; lower is better) in five, higher loss in three, and inconclusive differences in four.

Three favorable intervals established an absolute reduction greater than 0.01 BCE: learned-soft versus fixed-soft routing on spiral and rare disks, and learned-soft versus G121 on noisy annulus. The annulus result compares model families; its direct routing-control comparisons remained inconclusive.

The global G121 control remained substantially stronger on checkerboard and spiral and held a smaller BCE advantage on rare disks. A four-feature MLP led the descriptive Banknote check, where most other models received two PCA-derived inputs. The results support task-dependent choices and further work on routing and representation.

A separate deployment result converted the trained circuit cores to equivalent classical coefficients while retaining their routing, learned gates and preprocessing. Checked predictions agreed to floating-point tolerance, and conversion reduced local inference latency relative to the original circuit emulators.

### Study scope

Confirmation included 636 fits: 576 across the four synthetic families and 60 on Banknote. Synthetic inference uses eight independent populations per task, with two paired optimizer seeds. Banknote uses one grouped split with five optimizer seeds. Four additional retrains check selected results in the historical environment; they do not add independent populations.

All results use classical CPU computation. The study does not establish physical-QPU performance, quantum advantage, a universally superior model or broad real-world generalization.

### Downloads

Download each ZIP with its matching external `.seal.json`, extract it once and open `START_HERE.md`.

| Package | Contents |
| --- | --- |
| `QPathformer_v0.9_Study.zip` | Preserved PDF and Word report, edition note, report scope and provenance |
| `QPathformer_v0.9_Documentation.zip` | Study overview, research context and reproduction boundaries |
| `QPathformer_v0.9_Code.zip` | Selected scientific sources, ETEL execution adapter, dependency inventory and bounded startup tools |

The learned router controls expert mixtures within a model. **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1** coordinates complete fits; its retained vendor source records version **0.2.0**.

The packages exclude datasets, trained checkpoints, installed environments and full archives. Complete historical replay also requires the separately retained accepted recovery implementations, supporting protocols and reviewed environment/path bindings. Release checks cover integrity and bounded startup, without rerunning the full experiment.

### Rights and review status

CC BY 4.0 applies to identified controlled original report content and listed explanatory prose. The unchanged Q-Pathformer Platform License 1.0 applies to the exact selected Python files. Each package contains its adopted scopes; earlier permissions and separate third-party terms remain in force.

Repository edition **v1.0** and study **v0.9** are separate identifiers. This candidate remains a private draft for owner review.

[Review evidence and package identities](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/3885095cbb715f3d3df3f38d61b02b90bd3f944f/release_preparation/study-v0.9/revisions/draft_20261029_r2/README.md)

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.

---

Keep hashes, inventory counts, archive storage arithmetic, old README status and detailed recovery history in linked evidence. Do not paste GitHub's “Assets6,” download-count artifacts or footer into the release body. Keep `study-v0.9.5` designated Latest under the existing release plan and verify that live setting at handoff.

## 12. Codex completion sequence and C:\Q2 requirement

All current source maps record final assembly under:

`C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.9\draft_20261029_r2`

Historical helper origins under `C:\Anthony Siljeg\draft_releases_20261029\v07_09`, the ETEL vendor archive's Downloads path and earlier report-build directories describe actual input history. They do not contradict final assembly under Q2. Preserve them.

1. Create a new revision workspace **inside C:\Q2**. Preserve the reviewed r2 ZIPs, seals, report editions, scientific source and legal texts.
2. Correct the two package helpers and gated quickstart. Update current scientific summaries, Banknote qualification, ETEL naming and omitted-replay prerequisites.
3. Keep historical source code, protocols, figures, report text, version strings and prior records unchanged. Do not expand the selection to new operational recovery code without identifying its actual accepted lineage and rights.
4. Regenerate changed-file scope bindings, source maps, manifests, checksums and package indexes in dependency order. Retain explicit self-exclusions and avoid circular hashes.
5. Build affected ZIPs under Q2 and derive their external seals from final bytes. Unchanged assets may retain their identities; stale seals cannot cover changed packages.
6. Fresh-extract and verify the final package sets. Run genuine bounded startup and the demonstrated helper failure cases, recording actual exit codes and environment. Keep receipts outside extracted trees.
7. Confirm report DOCX/PDF hashes and retained scientific-source identities remain unchanged. Record that v0.9 disclosure/render findings differ from earlier releases.
8. Replace review links with actual final immutable references. In the authenticated release environment, download the exact final draft assets and compare them with the Q2 outputs.
9. Leave a concrete owner-review candidate and record current draft, visibility and Latest settings. This note itself does not publish the release or make the repository public.

The final Codex completion note should identify the new revision, changed assets, final identities, helper negative-test outcomes, preserved source/report bytes and any remaining authenticated verification. Packaging validation must not be described as a fresh scientific reproduction.

## Appendix A — Reviewed r2 attachment identities

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `QPathformer_v0.9_Code.zip` | 274,934 | `04994fd4cbbfb73dd5946c6f116ed92e0183e756a583cdd7276d460dca2473a6` |
| `QPathformer_v0.9_Code.seal.json` | 1,287 | `a984148629cbb38737f1fc7451d78b9e8598792b2d547aeca07391fb506ffc8b` |
| `QPathformer_v0.9_Documentation.zip` | 36,698 | `757c2d9551123542f3462807e52aea3ebf406fe89dcf1ba227d3d02b367b0a08` |
| `QPathformer_v0.9_Documentation.seal.json` | 1,356 | `0d2ab5510acb5c0c0c760f7172bc6a9e60022c445e609da9c39aa4dbe638d1f3` |
| `QPathformer_v0.9_Study.zip` | 2,638,081 | `db5e22d077abb129f2f6ae05b4475040f9115aba3e6ecdd2e68843e115109c7f` |
| `QPathformer_v0.9_Study.seal.json` | 1,294 | `f5a40f8cf9584b48324627a7f31a652f621e76b6b7a8d5ec39c3ee65a886ec19` |

These identify the supplied review inputs, not future corrected assets. The leading download-count digit in copied GitHub size labels is the previously explained display artifact; actual bytes agree with the seals.

The retained archive record declares **34,582,760,206 logical payload bytes**, excluding its manifest and reserved sidecars. This is archival accounting, not a curated download size, model size, RAM requirement or tested hardware minimum. The full archive was not rescanned here. [S6]

## Appendix B — Audit evidence and transfer notes

Private inventory details: Code 79 files, Documentation 20, Study 17; all 116 supplied files passed applicable membership and byte checks. The 57 Python files comprise 55 retained scientific sources and two package helpers. The source-selection list's 59 implementation/protocol files plus the separately covered execution README account for 60 retained payload files. These distinctions do not indicate missing inventory or rights coverage.

Review records are under:

`/workspace/scratch/c9c666df41fc/tmp/v09_release_review_20261030/`

Key records:

- `draft_v0.9_only.md` and `attachment_identity.json`;
- `integrity_agent/integrity_summary.json`, `integrity_checks.json` and `visual_review_pages_01_20.json`;
- `rights_agent/rights_review.json`;
- `science_agent/report_fidelity.json`, `matrix_review.json`, `science_consistency.json` and `reproduction_selection_boundary.json`;
- `runtime_review/runtime_review_receipt.json` and `static_import_review.json`;
- `visual_review/render_comparison.json` and rendered pages;
- `bounded_disclosure_scan.json`;
- `remote_access_review.json`.

These are review-environment paths, not assumed Windows paths. The material findings, exact identities and required correction tests are contained in this handoff. Codex should generate final receipts under the actual Q2 revision.

Historical preparation commit: `3885095cbb715f3d3df3f38d61b02b90bd3f944f`.  
Historical draft-receipt commit: `2350c164eeb28c0263359275a8f48c0734bdeb73`.  
Preparation path: `release_preparation/study-v0.9/revisions/draft_20261029_r2/`.

Integrity seals bind hashes and package relationships; they are not digital signatures. Local consistency, final authenticated download identity and publication state remain distinct checks.

