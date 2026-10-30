# Q-Pathformer Study v0.6 release review and Codex notes

**Reviewed:** 30 October 2026, Australia/Sydney.  
**Study:** v0.6 — Harder Tasks and Faster Inference.  
**Repository:** `qpathformer/qpathformer-classical-research-v1.0`; repository edition v1.0.  
**Reviewed preparation:** `draft_20261029_r02`.  
**Disposition:** Package identities, report preservation and adopted licensing scopes pass. Revise the verification/startup helpers and tighten current explanatory prose before publishing the next prepared revision.

## Decision for Codex

Keep the scientific report and the three-package structure. The draft accurately describes a completed study with two distinct results: richer circuit readouts help on checkerboard and spiral, and an equivalent classical representation reduces the measured inference time of the same circuit checkpoints. The equally optimized classical control remains an essential comparison.

The supplied ZIPs are internally consistent and match all six hashes in the pasted draft. This review found defects in how the Code package checks an altered extraction, not evidence that the supplied scientific files are corrupted. Three behaviors need correction: optimized Python bypasses the verifier's assertions; duplicate inventory records are accepted; and startup can skip the required compiler tests and still report PASS.

Make narrow changes to the current packaging helpers and guidance in a new revision under `C:\Q2`. Preserve the retained implementation, report, original protocols, historical records and existing sealed packages. This handoff prepares revisions; it does not publish a GitHub release, change repository visibility, adopt a new license or authorize another experiment.

### Priority actions

| Priority | Action | Acceptance evidence |
| --- | --- | --- |
| Before publication | Replace assertion-based package validation with unconditional checks; reject duplicate manifest and checksum records before constructing mappings. | A valid extraction passes; altered content fails under ordinary Python, `-O` and `PYTHONOPTIMIZE=1`; duplicate entries fail. |
| Before publication | Make v0.6 startup require the coefficient-conversion component and its intended six tests, with package verification before and after execution. | Missing compiler or failed verification produces nonzero exit and no PASS summary. Genuine bounded startup still passes without changing the extraction. |
| Editorial revision | State the task-specific result and qualify numerical equality and speed claims. | Release body and research guide agree with report pages 3–6 and 21–26. |
| Final preparation | Rebuild affected packages and refresh dependent scope identities, manifests, seals, receipt bindings and draft links. | Final attachments downloaded through an authenticated session match the final recorded identities. |

There is no current report-preservation or licensing mismatch requiring a scientific report rewrite or a renewed adoption decision. The report already contains the needed qualifications.

## What this review verified

The review used the six attachments supplied with the v0.6 draft, their extracted contents, the original retained v0.6 Word report, and the complete pasted release text. Independent work covered archive integrity, rights scope, report preservation, page presentation, scientific consistency and bounded runtime behavior.

| Area | Finding |
| --- | --- |
| Download identity | All three ZIP hashes and all three seal hashes match the pasted draft. |
| Archive integrity | 1,251 independent checks passed. Complete member sets, sizes, hashes, exclusions, source-map bindings and copied guidance agree. |
| Package structure | No CRC failures, unsafe member paths, duplicate ZIP members, case collisions, encrypted members, symlinks or unexplained extra/missing files were found. |
| Rights records | 639 independent checks passed. Adopted scopes, inherited coverage and canonical license texts agree with the selected files. |
| Report preservation | The original scientific body, 39 tables and three figures are unchanged. Six edition-note elements and metadata changes account for the Word edition differences. |
| Presentation | All 35 supplied PDF pages were individually inspected. No clipping, overlapping content, missing glyphs, broken tables or footer collisions were found. |
| DOCX/PDF consistency | A fresh Word-file render also has 35 pages; whitespace-normalized text agrees page by page with the supplied PDF. Representative rendered pages were visually checked. |
| Bounded startup | The actual supplied helper passed six tests on the genuine extraction. No training, optimizer updates, official scoring, shot sampling, benchmark timing or QPU work ran. |
| Failure handling | Deliberately altered disposable copies exposed the verifier and startup defects described below. The original extraction remained byte-for-byte unchanged. |

The Code package contains 61 Python files: 59 retained scientific/source files and two packaging helpers. The full extracted selection has 130 files across the three packages. These counts belong in audit records; they need not appear in the public-facing release body.

All 29 packaged JSON files and the three external seals parsed without duplicate object keys. All 26 active local Markdown links resolved. Twelve original guidance files copied into both Code and Documentation matched. A targeted screen of package bytes and Word XML found no common private-key, GitHub-token, AWS-key or OpenAI-project-key patterns; this is a bounded disclosure check, not a security certification.

### Access and reproduction limits

The pinned `PACKAGE_INDEX.json` and `DRAFT_RELEASE.json` could not be read through the available GitHub connection: both requests returned HTTP 404. For a private repository this does not establish that the files are missing. It means this review cannot independently confirm the live authenticated download receipt, publication state, visibility or Latest setting.

The separately retained experiment archive, official prediction arrays, trained checkpoints and historical deployment/readiness outputs were not supplied. Their reported results were checked for consistency with the report and selected protocols/code, not recomputed from omitted artifacts. The Windows environment and live `C:\Q2` build tree were not accessed. The Linux startup result is new local evidence for the selected check, not a Windows receipt or a fresh-install portability claim.

## Code changes required

### Replace assertions in the verifier

**File:** Code package `tools/verify_package.py`.

The helper implements membership, size and SHA-256 checks using Python `assert`. Optimization removes these checks. The quickstart's `-B` flag only prevents bytecode writes; it does not disable optimization inherited through `PYTHONOPTIMIZE`.

A disposable copy had additional text appended to `START_HERE.md`. The scientific Python files were unchanged.

| Invocation | Observed result | Required result |
| --- | --- | --- |
| `python -B tools/verify_package.py` | Exit 1; changed content rejected | Reject |
| `python -B -O tools/verify_package.py` | Exit 0; printed `PASS exact membership and all hashes` | Reject |
| `python -B tools/verify_package.py` with `PYTHONOPTIMIZE=1` | Exit 0; printed PASS | Reject |

Replace each integrity assertion with an explicit conditional that raises a clear exception or exits nonzero. Keep validation independent of interpreter optimization. A guard rejecting optimized execution may be additional defense, but unconditional integrity checks should be the primary correction. Do not bulk-rewrite assertions in preserved scientific tests or historical source files.

Official behavior is documented in [Python's assert statement reference](https://docs.python.org/3.12/reference/simple_stmts.html#the-assert-statement) and [command-line/environment reference](https://docs.python.org/3.12/using/cmdline.html#envvar-PYTHONOPTIMIZE).

### Reject duplicate records before mapping them

The verifier converts manifest entries and checksum lines directly into dictionaries. Duplicate paths therefore collapse into one entry.

Two targeted probes reproduced this:

- Appending an identical checksum line to a disposable extraction still produced exit 0 and PASS.
- Appending an identical manifest entry, then refreshing only its checksum to isolate duplicate handling, also produced exit 0 and PASS.

The genuine packages contain no such duplicates. A trusted external seal detects both altered copies; these probes establish a defect in the standalone internal verifier, not a bypass of a trusted externally recorded ZIP hash.

Validate the raw records before constructing dictionaries. Reject duplicate paths, malformed checksum lines, invalid digests and invalid manifest field types. Enforce canonical relative paths and the documented exclusions, with no silent path normalization that merges distinct entries. Reject absolute paths, parent traversal and case-colliding paths before access. Preserve the exact intended membership: `MANIFEST.json` excludes itself and `CHECKSUMS.sha256`; the checksum file excludes only itself.

Use strict JSON parsing that rejects duplicate object keys where the verifier relies on identity fields. Keep error messages specific enough to identify the failed file or record without printing its contents.

### Make the startup result depend on the required v0.6 checks

**File:** Code package `tools/startup_check.py`.

The current helper conditionally loads conversion tests only when `deployment_compiler.py` exists. A disposable copy with that file removed failed normal package verification, but standalone startup still reported **PASS with two tests**. The genuine package reports **PASS with six tests**.

For this v0.6 package, coefficient conversion is a required component. Require its declared files and the intended test selection. A missing component must fail startup, not silently reduce coverage. Run the unconditional package verifier before importing study modules and again after the bounded check. Print PASS only after those stages and the complete intended suite succeed. Keep logs outside the extraction.

The present quickstart lists three separate commands. It does not itself guarantee that execution stops after the first fails. Prefer one orchestration entry point that enforces the sequence and propagates failures, with the quickstart explaining the resulting scope.

The intended current suite is:

- Model shapes/parameter counts and paired Scalar/Multi initial predictions.
- State and moment agreement against independently constructed matrices.
- Four compiler tests covering construction nodes, both heads across off-grid/forced-bank fixtures, constants and invalid contracts, and the common learned-Trig coefficient kernel.

Do not describe this as full training reproduction, a new 40-checkpoint conversion audit or revalidation of the historical inference benchmark. The startup tests use generated fixtures and initialized/randomized model parameters; the trained study checkpoints are outside the download.

### Small related corrections

The startup JSON says “AST parse all selected Python,” but the parse loop covers only `payload/**/*.py`: 59 retained files. This review separately parsed all 61 selected Python files. Either include both helpers in the helper's AST scan or label its scope precisely.

`DEPENDENCY_INVENTORY.json` correctly lists all observed import roots from retained payload files. Clarify that boundary or include the helpers too; their additional roots are `socket`, `test_models` and `test_compiler`. The optional local device-snapshot path uses `qiskit_ibm_runtime.fake_provider.FakeManilaV2`, which is present in the observed-root inventory but absent from the short `optional_scientific` list. Label that list as selected examples or include the additional optional distribution. It is not needed for the six-test NumPy/SciPy startup.

The recorded `C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe` is an environment provenance path. Its name does not make this a v0.1 study or introduce ETEL. Preserve it as historical evidence rather than renaming it cosmetically.

The current startup tool writes its summary to stdout and has no output-file writer. The older receipt-overwrite finding from other packages does not apply here. Keep redirected output outside the package; if a receipt writer is introduced, make it refuse an existing destination atomically.

### Focused validation after the fix

Run the genuine extraction and the observed negative cases above, including a missing compiler. Require nonzero exit and no PASS summary for every invalid case. Capture the Python, NumPy and SciPy versions, selected test identifiers, return codes, package identity and before/after integrity results. No broader scientific rerun is needed to resolve these packaging defects.

The genuine review run used Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0 on Linux. All six tests passed. This observed environment is not a newly declared minimum, a replacement for historical dependency records or a cross-platform support guarantee.

## Scientific wording to preserve and clarify

### Make the improvement task-specific

The Multi readout improves on Scalar on **checkerboard and spiral**. Routed Trig25 achieves lower **common clipped binary cross-entropy** on both. The draft should name the tasks and score instead of leaving “difficult clean-boundary tasks” undefined.

| Mean macro-F1 | Checkerboard | Spiral | Noisy annulus, observed labels | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Scalar | 73.03% | 77.60% | 86.20% | 99.12% |
| Multi | 78.55% | 84.71% | 86.92% | 98.85% |
| Routed Trig25 | 89.57% | 92.05% | 86.81% | 98.67% |

These report values are descriptive means over five training seeds. The registered primary statistical comparisons use common clipped BCE, not F1. Multi-minus-Scalar mean BCE is −0.0564 on checkerboard and −0.0754 on spiral; the adjusted paired-seed intervals are [−0.0920, −0.0209] and [−0.1036, −0.0471]. The separate adjusted record intervals also favor Multi on these two tasks. See report pages 3–4.

Noisy-annulus and rare-disk results do not establish a general Multi improvement. On annulus, some circuit-versus-Trig seed intervals exclude zero while record intervals include zero, and the mean differences are below the 0.01 BCE reference. On rare disks, every primary mean difference is below that reference and every adjusted record interval includes zero. Neither unresolved differences nor small mean gaps establish equivalence. See pages 5–6.

The report states a checkerboard improvement of 5.53 F1 percentage points, while subtracting its separately rounded displayed means gives 5.52. This is compatible with rounding; the omitted underlying predictions were not recomputed here. Use the displayed endpoints or the report's stated gain without inventing a correction.

### Keep the metric and uncertainty definitions distinct

All six v0.6 models train using stable native-logit BCE. Checkpoint selection and registered comparisons use common clipped BCE, with natural logs and clipping to `[1e-7, 1-1e-7]`. This differs from the later v0.9.5 native-BCE primary outcome. Do not merge the studies into one loss leaderboard or carry the v0.5 Legacy-to-Scalar loss-change limitation into v0.6.

Sixteen primary comparisons use five paired seed differences, four degrees of freedom, and 99.6875% Bonferroni-adjusted t intervals. A separate 10,000-draw paired-record bootstrap describes uncertainty conditional on the fitted checkpoints. It does not create more training seeds or combine population and training uncertainty into one interval.

Use **“five paired training seeds on one fixed confirmation split per task family.”** Engineering, development and confirmation populations are distinct. The four confirmation test sets contain 6,400 unique records; 192,000 checkpoint-record classifications reuse these records across models and seeds. See pages 16, 20 and 34.

Observed noisy labels remain the primary annulus target. Latent-clean labels are diagnostic information, not substitutes for the headline scores. The generator's 10% flip probability does not impose a hard 90% finite-sample F1 ceiling. Rare-disk macro-F1 should retain its class-specific context.

### Explain exact conversion without implying universal numerical equality

The analytical conversion applies to the retained two-layer encoding and linear Pauli-logit heads. It expresses each trained bank in a finite Trig25 coefficient basis. It uses fixed construction points without labels or regression and creates an alternate representation of the same fitted predictor.

Forty selected circuit checkpoints were converted. Across reported validation/test, off-grid, routing-boundary and forced-bank checks, maximum absolute differences were `7.16e-15` for probabilities and `6.39e-14` for logits, with zero observed classification differences. Independent Laurent-polynomial reconstruction also passed. Finite checks quantify floating-point agreement; they are not a bit-for-bit guarantee for every input or a claim covering arbitrary circuit families. See pages 21–22.

Recommended wording:

> Equivalent classical coefficient conversion reduced measured CPU inference time for 40 selected circuit checkpoints. The checks found no classification differences and numerical agreement within the declared tolerances.

Avoid “identical decisions for all possible inputs” or “new model accuracy.” The original report's short headline is qualified by its detailed section; refine current wrappers rather than changing the preserved report.

### Make the fair timing comparison visible

An equally optimized routed Trig25 control uses the same coefficient inference kernel and has comparable inference cost. The global MLP is faster in the displayed tables. Conversion improves the circuit's classical implementation; it does not establish a speed advantage over equally optimized classical controls.

The benchmark includes routing, feature construction and sigmoid in hot inference. It excludes loading and reports compilation separately. Batch sizes 1, 32 and 1,024 have different workloads. Two warmups and fifteen timing trials are technical repeats, not independent training replications. Later annulus/disks blocks show broader timing drift with an unmeasured cause, so do not attribute their slower timings to task complexity or advertise one universal speedup multiplier. See pages 23–26.

The coefficient state also grows: 125 float64 values occupy 1,000 parameter bytes, compared with 400 for Scalar and 560 for Multi, excluding the shared router and file overhead. Describe this as a representation/time tradeoff, not model compression.

### Retain the right study boundaries

The design comprises 48 development and 120 confirmation endpoints, plus 24 engineering endpoints. Six registered methods are Scalar, Multi, routed Tanh, routed Trig25, global Trig25 and global MLP. There is no active Legacy, Frozen or trained hash-routing arm, and no ETEL component.

Routed Trig25 has 125 coefficients versus 25 globally; that comparison changes spatial partitioning and capacity together. It does not isolate a routing-only effect. Each circuit bank has two qubits, two layers and eight trainable angles; these are binary classification tasks. Eight angles do not mean eight classes or enumerate all circuit gates.

Local simulator coverage includes 40 checkpoints, 983,040 Aer simulated shots and, separately, 265,420,800 probability-level multinomial trials. Multi uses two measurement settings and Scalar one, so equal shots per setting cost twice as many shots per Multi prediction. The archived Manila properties are dated 27 May 2024; they are not current calibration. No physical shots, live IBM service, full language-architecture benchmark or quantum advantage is established. See pages 27–32.

Future work can investigate matched-capacity routing controls, richer/localized features, independent population draws and real-world tasks. These are research directions from page 33, not missing requirements that justify rerunning or enlarging this completed release.

## Report preservation and presentation

The retained original Word report is 867,873 bytes, SHA-256 `e26164a4e9378ec3b1a2a26cc0cf6d47421550493ca3fb5fab6b868c0138c012`. The packaged Word report is 868,690 bytes, SHA-256 `55db1c2b47569435e461b6756019c5767b81b0aca933e74b7b7c86da63d095b0`. The supplied PDF is 1,463,490 bytes, SHA-256 `e25614ebe1be5a9edf9d3efba0aacf9eaab406ce210fe09fd3ad3c3f55015647`.

Independent XML comparison confirms all 222 original non-section body elements as an exact prefix, with all 39 tables and three PNG figures unchanged. The same 22 OOXML parts remain; only `word/document.xml` and `docProps/core.xml` differ. The added six body elements form the release edition note.

The original guide's 34-page reference remains correct for the original report. The packaged edition has 35 pages because it adds the edition note. Preserve the original guide and internal-use labels as provenance. Current PDF metadata correctly names the title and Anthony's attribution. No report erratum was identified.

`REPORT_REVIEW.json` references a historical metadata-only PDF pixel-comparison receipt outside the downloads. This review confirms current page presentation and content preservation; it does not independently confirm that absent earlier comparison. Retrieve it for the final authenticated preparation record if needed, without claiming this local review did so.

Use “the preserved report in PDF and Word” in current guidance. Historical “root release” or “post-release” terminology refers to the internal held-out test release, separate from publishing on GitHub.

## Rights and naming

The supplied records show adoption on 29 October 2026. Keep **adopted** status for the identified original report/explanatory prose under **CC BY 4.0** and the exact selected Python under the unchanged **Q-Pathformer Platform License 1.0**. Describe the code as source available under Platform 1.0. Do not imply a blanket CC grant for code, whole archives, models, dependencies, architecture sources or datasets.

Current guidance scopes cover seven Code files, eight Documentation files and four Study files; report scope covers the two formats and three figures. The code scope covers all 61 selected Python files. These technical counts can remain in the scope records.

Package adoption-record hashes differ appropriately because their scope bindings differ; the common decision is consistent. The inherited circuit file and two identified router expression blocks match their recorded prior grants. A null earlier-license match in inheritance metadata does not cancel the separate current adopted code grant. Preserve historical wording in copied prior-version records.

When revising licensed helpers or guidance, record the new file identities and revision provenance under the applicable existing terms. Retain the historical adoption decision and previously sealed scope records; do not fabricate a new consent event, backdate a revised record or broaden the grant to new excluded material. Canonical license texts stay unchanged. See the supplied scope/adoption files and [CC BY 4.0 legal text](https://creativecommons.org/licenses/by/4.0/legalcode.en).

Attribution remains **Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative**. Anthony is the licensor; affiliations do not transfer ownership. Repository edition v1.0, study v0.6 and the separately named ETEL v0.1 component are distinct identifiers. This study supplies no ETEL implementation. Content licensing, release publication and repository visibility remain separate decisions.

## Proposed release body

Use the existing release title once in GitHub's title field:

**Q-Pathformer Study v0.6 — Harder Tasks and Faster Inference**

The following body is ready for Codex to adapt after the packaging fixes. Add final commit-pinned evidence links only when they bind the actual revised attachments; do not reuse r02 links as proof of new bytes.

---

**Draft for owner review · Study · Documentation · Code**  
Repository edition v1.0 is separate from study v0.6.

This study asks two practical questions: does a richer circuit readout help on difficult classification boundaries, and can the same trained circuit run faster through an equivalent classical representation?

Six model recipes were compared on **checkerboard, spiral, noisy annulus and rare-positive disks**. The completed study includes **48 development and 120 confirmation endpoints**, plus separate engineering checks.

### Main findings

The Multi readout improves on Scalar on checkerboard and spiral, while routed Trig25 achieves lower common clipped binary cross-entropy on both. The noisy-annulus and rare-disk results do not establish a general improvement from the richer readout.

Forty selected circuit checkpoints were converted to equivalent classical coefficients. The checks found no classification differences and numerical agreement within the declared tolerances. Conversion reduced measured CPU inference time; an equally optimized routed Trig25 control had comparable inference cost. This is another representation of the same fitted predictor, not an additional trained model or a quantum speedup.

### Downloads

Download each ZIP with its matching `.seal.json`, extract it once, and open `START_HERE.md`.

| Package | What it provides |
| --- | --- |
| `QPathformer_v0.6_Study.zip` | The preserved report in PDF and Word, with its edition note, rights scope and provenance. |
| `QPathformer_v0.6_Documentation.zip` | Study overview, research guide, original protocols and reproduction boundaries. |
| `QPathformer_v0.6_Code.zip` | Selected implementation, coefficient-conversion code, tests, dependency inventory and bounded startup tools. |

The downloads exclude raw datasets, trained checkpoints, installed environments and the full retained experiment archive. They provide a curated entry point to the completed work. No ETEL component is supplied.

### Evidence and limits

These are small two-dimensional synthetic classifiers evaluated on classical CPU hardware, with five paired training seeds on one fixed confirmation split per task family. The findings do not establish population-wide or real-world generalization. Historical prior-version scores provide context, not paired evidence of improvement.

Local compilation, noise and shot results are simulator evidence. The archived device snapshot is historical; no physical-QPU result, quantum advantage or full language-architecture benchmark is reported. Release preparation does not repeat the full study.

### Rights

Anthony Siljeg adopted CC BY 4.0 for the identified original report and explanatory prose, and the unchanged Q-Pathformer Platform License 1.0 for the exact selected Python files. Each package identifies its scope and exclusions. Applicable earlier grants remain in force.

This release remains a draft in the private repository. Content licensing is adopted separately from publication.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.

---

After final verification, append a compact line linking the review guide, exact package identities and final extraction/startup/upload receipts. Keep member counts and long hashes in those records and GitHub's asset metadata. Remove copied avatar, footer navigation, “Assets6,” download-count/size text and the duplicate body title. Retain `study-v0.9.5` as Latest according to the owner's existing direction, with its actual setting verified during the authenticated final check.

## Exact reviewed attachment identities

These identify the supplied r02 assets, not any future rebuild.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `QPathformer_v0.6_Code.zip` | 316,728 | `d5070fe265018f0100e2dc8806a3c72b7f585048881f1beec7936f810563a22e` |
| `QPathformer_v0.6_Code.seal.json` | 1,519 | `47d10c4a425809f8622d3d3b2791e0e885eb43dfa60f323f6a5704b4c4836056` |
| `QPathformer_v0.6_Documentation.zip` | 47,850 | `41f26786e1018f55c08511f2481d227617a9a5015efd89f5b1debb31308e940d` |
| `QPathformer_v0.6_Documentation.seal.json` | 1,551 | `8082653851287620d3dfc8bf43fe073eedee1d492a94c9e556936467c9203ce0` |
| `QPathformer_v0.6_Study.zip` | 1,967,452 | `4c5f85ae03acf03d3029497de0e630a102708f376265c58bdb9eaaaf8485cc36` |
| `QPathformer_v0.6_Study.seal.json` | 1,521 | `4d907488b26a435793d0d26ea1aff1c5f67db4905cdb9acf0ab2bb67c975d371` |

Copied GitHub labels such as “1309 KB” or “11.88 MB” can adjoin a download count to the displayed size. The measured bytes and supplied hashes agree; do not treat those pasted labels as package corruption.

The full archive's recorded boundary is 20,859 payload files totaling 2,229,408,138 bytes, plus a 5,077,038-byte delivery manifest. That is 2,234,485,176 logical bytes including the manifest. It is archival storage accounting, not this download's size, a model size or a RAM/hardware minimum. The omitted archive was not rescanned in this review.

## Build and publication handoff

1. Start a new revision beneath `C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.6\`; for example, use `draft_20261030_r03` if unused. The reviewed r02 packages consistently record the required `C:\Q2` build root. Keep that provenance and preserve historical source paths.
2. Fix only current package helpers and current explanatory guidance. Carry the report PDF/Word and retained scientific payload forward byte-for-byte. Do not silently edit original source guides, completed-run results, adoption events or historical seals.
3. Update the affected scope identities, source map, dependency-scope explanation, internal inventory and checksums, then build fresh affected ZIPs and external seals. Preserve unaffected Study assets when their bytes and bindings remain unchanged; do not reseal every package merely for cosmetic consistency.
4. Run the corrected genuine and negative checks against a fresh extraction. Store receipts outside the extraction and bind them to the exact final ZIP/seal identities. Keep Linux review evidence separate from final Windows evidence prepared under `C:\Q2` and from historical scientific results.
5. Regenerate the external package index, root verification and startup bindings that refer to changed assets. Preserve earlier revisions. A new receipt must identify the bytes actually tested, not inherit an earlier PASS by filename.
6. Update current draft prose and commit-pinned links. The supplied draft points preparation evidence at `60bda2ace84be02b83e23603b0610c0381572e03` and its later upload receipt at `72cda7268a65dbb991f89b1e5ce3c64bfddf2473`. Those are reviewed historical references; new assets need appropriate new bindings.
7. Through the owner's authorized GitHub session, verify that all six intended assets are attached, download them, compare exact bytes/hashes and inspect the final rendered release body. Confirm the intended draft/publication state, private visibility and Latest selection separately. The historical `study-v0.9.5` release remains unchanged.

No new training, dataset generation, optimizer replay, official scoring, shot sampling, hardware submission or dependency installation is necessary for these corrections. Once the packaging failure cases and final identity bindings pass, the remaining changes are editorial and preparation work.

## Evidence map

| Finding | Primary package evidence |
| --- | --- |
| Scientific design and result interpretation | Study `reports/QPathformer_v0.6_Report.pdf`, especially pages 3–6, 16, 20–28 and 33–35; Code `payload/study/governance/STUDY_PLAN.json` and `ANALYSIS_PROTOCOL.json`. |
| Conversion and timing | Report pages 21–26; Code `payload/study/quantum/deployment_compiler.py`, `deployment_benchmark.py`, `deployment_checks/test_compiler.py` and `governance/DEPLOYMENT_PROTOCOL.json`. |
| Simulator scope | Report pages 27–32; Code `payload/study/governance/LOCAL_READINESS_PROTOCOL.json`, `quantum/local_readiness.py` and `quantum/device_snapshot.py`. |
| Runtime findings | Code `tools/verify_package.py`, `tools/startup_check.py`, `QUICKSTART.md` and the independent disposable-copy probes. |
| Rights | Each package's `LICENSE_ADOPTION.json`, applicable scope records and `RIGHTS.md`; Code `INHERITED_LICENSE_COVERAGE.json`. |
| Preservation | Study `provenance/REPORT_PRESERVATION.json`, `REPORT_REVIEW.json`, `EDITION_CHANGES.md`, and independent comparison with the retained original Word report. |
| Artifact integrity | Three external seals, internal `MANIFEST.json`, `CHECKSUMS.sha256` and `provenance/SOURCE_MAP.json`. |

Independent review receipts are retained in `tmp/v06_release_review_20261030/`: `attachment_identity.json`; `integrity_agent/integrity_receipt.json`; `rights_agent/rights_scope_receipt.json`; `science_agent/report_preservation.json` and `science_arithmetic_checks.json`; `runtime_review/runtime_review_receipt.json` and `static_import_review.json`; `visual_review/render_comparison.json`; page-level visual receipts in the integrity/rights subdirectories; and `content_screen.json`. These support this review and are not replacement publisher receipts or new release assets.
