# Q-Pathformer Study v0.7 release review and Codex notes

**Reviewed:** 30 October 2026, Australia/Sydney.  
**Study:** v0.7 — Routing Capacity and Classical Deployment.  
**Repository:** `qpathformer/qpathformer-classical-research-v1.0`; repository edition v1.0.  
**Reviewed preparation:** `draft_20261029_r2`.  
**Disposition:** The supplied package identities, report preservation and adopted rights scopes pass. Correct the two packaging helpers, clarify ETEL naming and refine the current release explanation before publishing a revised preparation.

## Recommendation for Codex

Keep the report and the Study · Documentation · Code structure. The draft's main scientific findings are supported by the supplied report and selected protocols. The most useful explanatory change is to show what v0.7 adds: independent population replication, a stronger routing control, a wider classical feature baseline, and a study-specific ETEL execution integration.

The supplied archives are internally consistent. The defects found concern how the packaging helpers handle an altered extraction: Python optimization can bypass checks in both helpers, and duplicate inventory records are accepted. Fix those helpers in a new revision under **`C:\Q2`**, then refresh the affected package identities and final receipts. Preserve the scientific source, report, adopted license texts and historical sealed records.

This handoff prepares corrections and reviewable release prose. It does not publish a release, change repository visibility, adopt a new license or initiate training, ETEL jobs, shot sampling or hardware work.

### Actions before final preparation

| Priority | Required action | Acceptance evidence |
| --- | --- | --- |
| Packaging | Replace `assert` validation in both helpers with unconditional checks. | Changed payload and failed CLI checks fail under ordinary Python, `-O` and `PYTHONOPTIMIZE=1`. |
| Packaging | Reject duplicate manifest/checksum paths before constructing sets or dictionaries. | Both duplicate-record probes fail; the genuine package still passes. |
| Packaging | Make startup depend on successful package verification and all three declared CLI checks; verify the extraction afterwards. | Invalid extraction or failed child command produces nonzero exit and no PASS summary. |
| Explanation | Add the ETEL component/source-version bridge and clarify its whole-fit scheduling role. | Current release, overview and Code description agree; historical source names remain unchanged. |
| Evidence clarity | Add a v0.7-specific clarification for the v0.9 sentence in the visual-review receipt. | New clarification identifies the historical carryover and binds the unchanged report or Study package. |
| Final binding | Rebuild affected packages and update scopes, inventories, seals, receipt references and final draft links. | Fresh extraction and authenticated download checks identify the exact final assets. |

No scientific report rewrite or renewed license adoption is required to resolve a mismatch in the supplied report or scopes: none was found.

## Review results and limits

Only the first v0.7 section of `Pasted markdown(5).md` is the current release draft. The subsequent v0.6 and earlier entries are separate releases and context, not additional v0.7 body text or attachments to replace.

| Review area | Result |
| --- | --- |
| Six attachment identities | Every attached ZIP and seal matches its SHA-256 in the v0.7 draft. |
| Archive integrity | 1,163 independent checks passed: member sets, sizes, hashes, source-map bindings, exclusions, copied records and active local links agree. |
| ZIP structure | No CRC errors, unsafe paths, duplicate members, case collisions, encrypted members or symlinks were found. |
| Adopted rights | 489 checks passed against selected bytes, scope records, earlier-grant evidence and canonical license texts. |
| Scientific preservation | All original body elements, 58 tables and four figures remain unchanged. The edition note and core metadata explain the Word changes. |
| Presentation | All 43 supplied PDF pages were individually inspected; no clipping, overlap, broken tables, missing glyphs or footer collisions were found. |
| DOCX consistency | A fresh render has 43 pages and agrees with the supplied PDF's whitespace-normalized text page by page. Representative rendered pages also passed visual inspection. |
| Genuine startup | Numerical imports, the two-input circuit/sigmoid checks and all three CLI help paths passed. The extracted package remained unchanged. |
| Failure handling | Disposable-copy probes confirmed the helper defects described below. No supplied source or report was modified. |

The packages contain 112 files in total. Code includes 52 Python files: 50 retained source files and two packaging helpers. All 26 packaged JSON files and three seals parse without duplicate object keys; all 34 active local Markdown links resolve. Keep these audit counts in supporting records rather than adding them to the release introduction.

A targeted credential-pattern screen of the selected files and Word XML found no common private-key, GitHub-token, AWS-key or OpenAI-project-key patterns. This is a bounded disclosure check, not a security certification.

The original experiment archive, trained checkpoints, official predictions, execution receipts and timing/shot outputs are outside these downloads. This review checks the report's consistency, selected implementation and displayed arithmetic; it does not reproduce the omitted scientific evidence. All 20 displayed primary intervals are arithmetic-consistent with the rounded population differences, but that check is not a fresh analysis of the original prediction arrays.

The available GitHub connection returned HTTP 404 for the pinned package index and draft receipt. In a private repository that does not establish that they are missing. Live attachment contents, publication state, visibility, Latest selection and final Windows execution therefore remain unverified here. The recorded `C:\Q2` roots were checked as provenance; the live Windows filesystem was not accessed.

## Packaging corrections

### Make the verifier independent of optimization

**File:** Code `tools/verify_package.py`.

Membership, containment, symlink, size and hash checks currently use Python `assert`. Python removes assertions when optimization is enabled. The documented `-B` flag prevents bytecode writes; it does not neutralize `-O` or an inherited `PYTHONOPTIMIZE` setting.

A disposable copy had a line appended to `START_HERE.md`. All scientific Python remained unchanged.

| Test invocation | Current result | Required result |
| --- | --- | --- |
| `python -B tools/verify_package.py` | Exit 1; rejects changed bytes | Reject |
| `python -B -O tools/verify_package.py` | Exit 0; reports PASS | Reject |
| Ordinary command with `PYTHONOPTIMIZE=1` | Exit 0; reports PASS | Reject |

Replace integrity assertions with explicit conditions that raise or exit nonzero. Preserve the current intended membership and exclusions. An optional optimization guard may provide additional defense, but the integrity checks themselves should remain unconditional. Do not bulk-rewrite assertions in preserved scientific implementations or historical tests.

See [Python's assert reference](https://docs.python.org/3.12/reference/simple_stmts.html#the-assert-statement) and [optimization environment documentation](https://docs.python.org/3.12/using/cmdline.html#envvar-PYTHONOPTIMIZE).

### Validate raw inventory records before constructing mappings

The manifest membership uses a set, and the checksum file is parsed into a dictionary. Duplicate paths therefore lose their distinct identities before validation.

Two probes passed incorrectly under ordinary Python:

- An identical checksum line was appended to a disposable checksum file.
- An identical manifest entry was appended, with only that manifest's checksum refreshed to isolate duplicate-path handling.

The genuine supplied files contain no duplicates. A trusted external seal detects both altered copies. These results concern the standalone internal verifier, not a bypass of the trusted external ZIP identity.

Reject duplicate raw paths before conversion to sets/dictionaries. Validate checksum syntax and digests, manifest field types, canonical relative paths, case collisions, containment and symlink handling. Reject absolute paths, parent traversal and ambiguous normalized paths. Use strict JSON parsing for identity records so duplicate object keys cannot silently replace earlier values.

Keep the exclusion rules explicit: `MANIFEST.json` omits itself and `CHECKSUMS.sha256`; checksums cover every file except the checksum file itself. Malformed records should produce a clear nonzero failure rather than an apparently successful partial check.

### Make startup failure checks unconditional too

**File:** Code `tools/startup_check.py`.

This helper also uses assertions for circuit shape/finite-value checks and subprocess return-code/help-output checks. The optimization defect therefore affects the startup result, not just the verifier.

In a disposable extraction, `payload/study/execution/launcher.py` was removed. Normal verification and normal startup failed. Under `-O`, and separately under `PYTHONOPTIMIZE=1`, startup returned exit 0 and **PASS** even though its three child return codes were **0, 2, 0**. The failed launcher help command was present in the JSON alongside the misleading overall success.

Use explicit checks for every required condition and child return code. All three declared CLI help paths must succeed and produce the expected help output. Preserve the existing subprocess timeout and propagate failures in the final status and process exit code. Do not weaken validation to accommodate a missing entry point.

Run the unconditional package verifier before importing study modules and after the selected startup operations. The quickstart currently gives two separate commands and no automatic stop-on-failure or post-check. Prefer one bounded orchestration command that enforces the sequence; otherwise make the failure checks explicit in the documented shell procedure.

The current helper writes only stdout. It has no internal output-file writer, so an older receipt-overwrite implementation finding should not be attributed to it. Keep receipts outside the extraction. If Codex adds managed receipt creation, use explicit UTF-8 and exclusive creation; preserve earlier receipts rather than overwriting them through repeated redirection.

### Preserve the declared scope of startup

The actual v0.7 startup covers:

- NumPy, SciPy and selected scientific-module imports.
- Two input coordinates through a zero-angle circuit bank, with moment shape/range checks and a sigmoid comparison.
- `--help` for `quantum/study.py`, `execution/launcher.py` and `execution/bind_stage.py`.

It does not run the six-test v0.6 suite, conversion parity tests, all eight model families, ETEL fit execution/recovery, official evaluation or the historical deployment benchmark. Importing `reference_v03` is not the same as comparing the circuit with its independent matrices. Describe the performed checks accurately instead of enlarging their claimed coverage.

This review separately AST-parsed all 52 Python files. The dependency inventory's import roots agree with the selected sources; the helper import roots are already included. There is no missing-helper-import inventory finding to carry forward from v0.6.

The genuine run passed on Linux with Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0. It establishes that these bounded paths work in that environment. It does not validate the recorded Windows OpenBLAS DLL, process/resource APIs, worker supervision or exact historical numerical replay. The recorded historical NumPy 2.5.4 and SciPy 1.18.1 versions should remain unchanged as observations.

### Focused acceptance checks

After correction, test a genuine extraction, changed payload, duplicate checksum, duplicate manifest and missing launcher under the applicable ordinary and optimized modes. Every invalid case must exit nonzero without a PASS summary. Confirm that the genuine package's three help paths succeed and that its bytes are unchanged afterwards. Bind the receipt to the exact final assets.

These tests address observed failure cases. Full training, synthetic ETEL fit launches, cancellation/recovery tests, shot generation, deployment timing and dependency installation are unnecessary for this packaging correction.

## Explain what v0.7 contributes

### Routing now has a stronger control

Define geometric routing as assigning nearby inputs to specialist banks using a frozen k-means router fitted on training coordinates. Its matched-count hash control has the same number of banks and exactly the same training occupancy in each bank. The learned cutpoints are then applied unchanged to validation and test; held-out occupancy and class composition are not forced to match.

For both MultiK versus MultiHash and TrigK versus TrigHash, all four task families favor geometric routing on the registered **common clipped binary cross-entropy** comparisons. All eight adjusted routing intervals exclude zero in that direction. Seven also establish an improvement beyond the 0.01 practical reference; the rare-disk Trig comparison does not. Avoid saying every routing improvement exceeds the practical threshold or proves universal superiority. Report pages 3, 13–16 and 23 support this wording.

The paired routing models have matched parameter counts as well as training occupancy: MultiK/MultiHash each have 70 trainable scalars, and TrigK/TrigHash each have 125. This makes the comparison more informative than routed Trig25 versus global Trig25 alone. It still changes which examples train each bank; the result should remain tied to the tested data, feature representations and optimization.

### Population replication is the key design advance

Confirmation uses **eight independently generated populations per task, with two paired optimizer seeds within each population**. Average the two seed differences within a population, then analyse eight independent population differences. The independent sample size is eight per task, not sixteen checkpoints or hundreds of thousands of prediction rows.

The design has 32 engineering fits, 64 development fits and 512 confirmation fits: 608 total. The 576 full fits complete 200 rounds and 15,000 updates each. The primary analysis uses 20 paired population-level contrasts, seven degrees of freedom and nominal 99.75% Bonferroni-adjusted t intervals. Small-sample distributional assumptions still limit interpretation. No paired-record bootstrap is used in v0.7.

All eight arms train stable native-logit BCE. Validation selection and primary comparisons use common clipped natural-log BCE, with clipping to `[1e-7, 1-1e-7]`. Native loss is reported separately. Do not combine this outcome with the later v0.9.5 native-BCE primary measure. An interval crossing zero remains inconclusive; the 0.01 reference is not an equivalence test. See report page 3 and `ANALYSIS_PROTOCOL.json`.

Historical v0.6 means are context, not paired evidence that v0.7 improved or regressed. v0.7 has different replication, controls, timing sessions and shot-budget definitions. The report deliberately keeps the historical comparisons separate.

### Keep the classical baseline result visible

The release's quoted values are correct descriptive means. Two seed results are averaged within each population before the eight population means are summarized.

| Mean macro-F1 | Checkerboard | Spiral | Noisy annulus, observed labels | Rare disks |
| --- | ---: | ---: | ---: | ---: |
| Flexible circuit, MultiK | 76.57% | 86.82% | 87.14% | 98.70% |
| Routed Trig25 | 90.18% | 92.42% | 87.75% | 98.94% |
| Global Trig121 | 98.47% | 96.57% | 87.28% | 99.16% |

These F1 summaries are secondary to the primary BCE contrasts. Reported standard deviations describe population variability, not confidence intervals. Global Trig121 leads the two harder clean tasks; it is not the leader on every metric or family. Routed Trig25 has higher descriptive F1 on noisy annulus, where its primary contrast with Trig121 is inconclusive.

MultiK versus ScalarK has a favorable BCE direction on checkerboard, spiral and annulus, but the adjusted interval establishes the 0.01 improvement only on spiral. Do not copy v0.6's stronger checkerboard practical-threshold interpretation. Rare disks remain inconclusive for that contrast. See report pages 7–16.

The eight arms are model recipes, not eight output classes. These are binary tasks. Each circuit bank has two qubits, two layers and eight trainable core angles; the trainable-angle count does not enumerate every gate or create eight classes. The circuit and classical controls also differ in feature constraints and optimization geometry, so similar parameter totals do not isolate every aspect of capacity.

### Bound the conversion and timing claims

The study converts 192 selected circuit models and repacks 256 learned Trig models for a common kernel. Those 448 representations are existing fitted predictors, not additional training fits. The exact algebraic identity applies to the retained two-qubit, two-layer core and affine Pauli readout, with the original router and sigmoid preserved.

All checked class predictions agree. Report page 26 gives original-versus-converted circuit maxima of `9.936e-15` in probability and `7.816e-14` in logit. Independent replay across all representations gives maxima of `1.893e-14` and `9.059e-14`. Keep the producer and independent maxima separate. Finite floating-point checks are not a bit-for-bit guarantee for every input or an efficient conversion claim for arbitrary deeper circuits or the full architecture.

The **4.28–4.58×** range is supported for matched **single-input CPU calls relative to the original circuit implementation**. Preserve that comparison in the release. It is not a universal speedup or an advantage over every classical control. The MLP is fastest in the timing tables; learned Trig controls use the optimized common kernel. Trig121 is not uniformly faster at every batch size.

The v0.7 timing tables use **microseconds per complete batch call**, including all records, routing, feature/core evaluation, head and sigmoid. This differs from v0.6's per-record tables. Ratios are calculated on paired observations before aggregation; dividing displayed aggregate latency cells does not reproduce the estimator. Three sessions and fifteen timed trials per condition do not increase the independent population sample size. Session drift is retained and its cause was not measured. See pages 27–33.

Conversion also increases bare parameter storage: each five-bank coefficient table uses 1,000 bytes versus 400 for ScalarK or 560 for Multi. Loading, serialization, router state and evidence-container sizes are separate. Construction-only break-even excludes other deployment costs; it is not an end-to-end cost guarantee. Conversion adds no accuracy gain and should not be described as compression.

### Preserve the changed measurement budget

v0.7 uses equal **total** simulated measurement budgets of 1,024 or 8,192 per prediction. Scalar uses the entire budget in XX; Multi splits it equally between XX and ZZ. Five readout moments do not mean five independent budgets. Joint multinomial counts preserve covariance among moments measured in the same setting.

This historical diagnostic is ideal local multinomial sampling. It does not use Aer, an archived Manila noise model, live IBM services or physical shots. Device noise and calibration drift are outside this v0.7 diagnostic. The represented 1,132,462,080 measurement outcomes must not be presented as physical-QPU shots.

The larger total budget reduces the displayed MAE, MSE and class disagreement in all twelve task/arm groups. These are conditional deviations from each checkpoint's ideal prediction. Class disagreement is not misclassification against labels, and a weak classifier can still be stable under sampling. The replay bound `2e-12` is a checked tolerance; the exact maximum individual probability discrepancy was not retained. See pages 34–37.

## Clarify ETEL in the release and overview

v0.7 includes two retained ETEL files and the study-specific execution adapter. Current `OVERVIEW.md` calls it “ETEL 0.2.0,” accurately identifying the source version but leaving the confirmed component name unexplained.

Use this paragraph in current explanatory material:

> The Code package includes the study-specific execution integration for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**, using retained ETEL source version **0.2.0**. It schedules complete registered fits in isolated local processes. The component label, historical source version, study v0.7 and repository edition v1.0 identify different things.

Keep `__version__ = "0.2.0"`, the original vendor archive name and historical source guides unchanged. This selection is not a standalone ETEL component release. Both vendor files have current adopted code coverage and matching earlier adopted v0.9.5 coverage.

Separate two uses of routing for readers: model routing selects a parameter bank for an input record; ETEL schedules an entire training fit. ETEL's logical 64-slot groups and reported peak ready capacity 192 are bookkeeping. The study used at most five concurrent fit workers; slot counts are not physical processors, model banks, qubits or measured 64×/192× speedup.

The adapter provides persistent claims, process identity, immutable attempts and committed hashes around local whole-fit execution. This study does not test the later v0.9.5 allocation policy or supply distributed provisioning. The native untrained vector fixture is not used. No matched serial experiment establishes an ETEL parallel speedup. Startup CLI success does not validate Windows recovery or resource monitoring.

The report records zero failed training fits or retries. It separately retains an independent-replay wrapper failure before launch; avoid expanding “no training failures” into “no failures anywhere.” Recovery means a reviewed fresh attempt where permitted, not exact optimizer/sampler continuation. See report pages 4 and 38–40 and `execution/README_EXECUTION.txt`.

## Report and provenance treatment

Independent comparison confirms all 295 original non-section body elements as an exact canonical-XML prefix. All 58 tables and four PNG figures are unchanged. Both DOCX archives contain the same 23 parts; only `word/document.xml` and `docProps/core.xml` differ, with seven edition-note body elements appended. The original 42 pages plus the edition note produce the 43-page release PDF.

| Report identity | Bytes | SHA-256 |
| --- | ---: | --- |
| Retained original DOCX | 697,132 | `3b2c31ec5f56cd6c6207d2a1f04820b1433dd938e08f4e906ad1d6a945038bc1` |
| Packaged DOCX | 698,067 | `f2144ed93098717d44140ceee988f4a7ccd005806544d305c59de1cc1dd15b73` |
| Packaged PDF | 1,821,136 | `b5bd3d125798dc26682803770f0622a2ce026fdd2c9b8977c394a4f55532ead8` |

Metadata correctly identifies Anthony, study v0.7, the report edition and its scoped rights. Earlier `draft_20261029` paths in report/render records bind the same report bytes carried into the r2 package. They are valid history, not paths to rewrite merely because the assembly directory changed.

Preserve original internal labels, evidence paths, preparation-stage “pending” statements, projections and commands. The edition note explains the historical context. References to internal test release are distinct from GitHub publication, and original full-archive commands are not the curated quickstart. Future hardware/paper recommendations remain historical research directions, not current run instructions.

### Clarify one cross-study sentence in the visual-review record

Study `provenance/VISUAL_REVIEW.json` contains this sentence in `disclosure_review`:

> v0.9 includes account/credit/token usage on original page 37.

The actual v0.7 page 37 is **Joint measurement verification and costs**, describing local sampling and CPU/wall accounting. The v0.9 sentence is cross-study metadata carryover, not a report-content defect or hash mismatch.

Prefer a new current external clarification that identifies this carryover and records the v0.7-specific disclosure review, bound to the existing report and Study ZIP identities. Preserve the sealed historical receipt. This permits the Study ZIP/seal and report to remain unchanged. If a corrected record is instead included inside a new Study package, retain the previous revision and regenerate that package's identities; the scientific report itself still needs no reissue.

### Preserve two intentional selection differences

`SOURCE_SELECTION.json` lists 55 retained implementation/protocol files. An additional execution README is separately covered by the source map, guidance scope and complete inventories. Label the selection list precisely or add the README in a new record; do not describe this as unexplained content.

The Code package's 94-byte requirements file is a new wrapper. Documentation retains the original 156-byte historical requirements file. Their differing identities are documented and intentional. Do not normalize historical bytes merely to make these files match.

## Rights

The supplied adoption records consistently identify Anthony Siljeg, adoption on 29 October 2026, and separate grants: **CC BY 4.0** for the exact controlled report/explanatory prose and the unchanged **Q-Pathformer Platform License 1.0** for the exact Python selection. Describe the code as source available under Platform 1.0.

The code scope covers all 52 Python files, including both ETEL vendor files and the packaging helpers. Guidance scopes identify five Code, thirteen Documentation and four Study file instances; the report scope covers the two formats and four figures. These counts can remain in scope records.

All canonical license copies agree. Package adoption-record hashes differ appropriately because they bind different scopes, while the underlying decision agrees. Five whole-file earlier matches and nine shared-expression blocks were independently verified. Historical wording such as “proposal” inside a copied prior-version record does not reverse current adopted status.

When authorized helpers or current guidance change, update their identities and revision provenance under the applicable existing terms. Preserve the earlier scopes, adoption decision and seals. Do not fabricate another consent event, backdate changed records or extend the scope to excluded datasets, weights, dependencies, architecture documents or whole archives. The report's CC terms remain separate from the code's Platform terms. See the packaged rights/scope records and [CC BY 4.0 legal text](https://creativecommons.org/licenses/by/4.0/legalcode.en).

Attribution remains **Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative**. Anthony is licensor; affiliations are not an ownership transfer. Content licensing, publication state and repository visibility remain distinct.

## Proposed release body

Keep the release title:

**Q-Pathformer Study v0.7 — Routing Capacity and Classical Deployment**

The following body is intended for the corrected preparation. Codex should add final commit-pinned evidence links only after they bind the actual final assets.

---

**Draft for owner review · Study · Documentation · Code**  
Repository edition v1.0 is separate from study v0.7.

This study examines how grouping nearby inputs into specialist model banks affects classification, and how trained circuit models can run through an equivalent classical representation.

### Main findings

On **checkerboard, spiral, noisy annulus and rare disks**, geometric routing achieved lower common clipped binary cross-entropy than matched-count hash routing for both the flexible circuit and routed Trig25. The size and practical relevance of these gains varied by task.

The wider global Trig121 control led the two harder clean tasks. Its mean macro-F1 was **98.47% on checkerboard and 96.57% on spiral**, compared with **76.57% and 86.82%** for the flexible circuit. These are descriptive means; the primary analysis uses paired population-level BCE comparisons.

Classical conversion preserved every checked class prediction. For single-input calls, the reported matched CPU speedups were **4.28–4.58× relative to the original circuit implementation**. Conversion changes how the same fitted predictor is evaluated; it adds no accuracy gain or quantum-advantage claim.

### What changed in this study

Confirmation uses **eight independent populations per task, with two paired optimizer seeds per population**. The completed study includes 512 confirmation fits within 608 registered fits, adding population replication and matched training-bank occupancy controls to the earlier research sequence.

The Code download also includes the study-specific execution integration for **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**, using retained ETEL source version **0.2.0**. It coordinates complete training fits in isolated local processes. Logical slot counts describe scheduling capacity, not physical workers or model size.

### Downloads

Download each ZIP with its matching `.seal.json`, extract it once and open `START_HERE.md`.

| Package | What it provides |
| --- | --- |
| `QPathformer_v0.7_Study.zip` | The preserved report in PDF and Word, edition note, rights scope and provenance. |
| `QPathformer_v0.7_Documentation.zip` | Study overview, findings, original guidance and reproduction boundaries. |
| `QPathformer_v0.7_Code.zip` | Selected models, audits, classical conversion and ETEL execution integration, with dependency information and bounded startup tools. |

These curated downloads exclude raw datasets, trained checkpoints, installed environments and the full retained experiment archive. Full scientific replay requires those separately retained inputs and reviewed environment/path bindings.

### Evidence and limits

The findings concern four small synthetic task families on classical CPU hardware. Population replication improves the design, but small-sample assumptions and host-specific timing still limit generalization. Historical cross-version scores are context, not paired evidence of improvement.

Finite-shot diagnostics used ideal local multinomial sampling with equal total measurement budgets. They do not establish physical-hardware performance, device-noise tolerance or quantum advantage. The full proposed language architecture was not benchmarked. Release preparation does not repeat training or the complete scientific study.

### Rights

Anthony Siljeg adopted CC BY 4.0 for the identified original report and explanatory prose, and the unchanged Q-Pathformer Platform License 1.0 for the exact selected Python files. Each package identifies its scope and exclusions. Applicable earlier permissions remain in force.

This release remains a draft in the private repository. Content licensing is adopted separately from publication.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.

---

Append one compact line of final evidence links after verification. Keep detailed member counts and long hashes in the package index, scope records and asset metadata. Do not paste the other release entries, footer navigation or download-count/size labels into this body. Retain `study-v0.9.5` as Latest according to the owner's existing direction, with live state checked during final authenticated verification.

## Exact reviewed attachments

These are the supplied r2 identities, not identities for a future rebuild.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `QPathformer_v0.7_Code.zip` | 273,995 | `d4bf3e7513c4cb7a022e0340ca78e112988652c8f89c906536392abbb6082b51` |
| `QPathformer_v0.7_Code.seal.json` | 1,287 | `3852e80e820cf306e75909cdb2813066431ee0a8b0054aba06e6cfea821ba81e` |
| `QPathformer_v0.7_Documentation.zip` | 40,941 | `1e867fc80b4dffce839be3c0e8f405f570360bbaa79132ef9c2bb4211d566c87` |
| `QPathformer_v0.7_Documentation.seal.json` | 1,356 | `105ad6211e538f2c95ee18668a743d53b37d4afe5677e9dc7d92e510b38376f6` |
| `QPathformer_v0.7_Study.zip` | 1,917,796 | `d553edb203af47f8348ba51f11303cd908c9a330eee57b7b65f5206d647388e5` |
| `QPathformer_v0.7_Study.seal.json` | 1,294 | `77ef2c857ddd447e88b1840c93c93324b0653fc5fc873a2cbce948efa50d427b` |

The current seals use `qpath-package-seal-1` with fully prefixed ZIP-member paths for the manifest, checksums and root `SOURCE_MAP.json`. This differs from v0.6's schema. Validate the actual schema; do not impose v0.6's package-relative path convention or move files merely for cosmetic consistency. The seals are integrity records, not digital signatures.

Copied size labels such as “1268 KB” and “11.83 MB” can join a download-count digit to the displayed size. The measured bytes and hashes agree; those pasted labels are not evidence of corruption.

The retained archive record states 6,533,819,005 payload bytes, plus a 13,147,346-byte delivery manifest: 6,546,966,351 logical bytes together. The recorded manifest SHA-256 is `da1407baac8405cbc66ab53f321c970da688e31ae25de1ce0df527687f769ce5`. The archive was not supplied or rescanned. These are archival storage figures, not the curated download size, model size or a hardware/RAM minimum.

## Build and publication handoff

1. Use a fresh revision below `C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.7\`, for example `draft_20261030_r3` if unused. All reviewed seals record the r2 build under the required `C:\Q2` root. Preserve historical Downloads and earlier preparation paths as source provenance.
2. Correct only current packaging helpers and current explanatory material. Carry the 50 retained Python files, original protocols and report PDF/DOCX forward unchanged. Preserve the previous sealed packages and historical review records.
3. Add a current external clarification for the visual-review carryover, bound to the unchanged Study/report identities. This is the preferred route if no other Study package changes are needed.
4. Refresh affected code/guidance scope identities, source-map records, inventories and checksums; build fresh affected ZIPs and seals. Update adoption-to-scope bindings without inventing or backdating an adoption event. Keep canonical license text unchanged.
5. Verify a fresh extraction and run the corrected bounded checks and observed negative cases. Capture exact environment versions and before/after identities outside the extraction. Keep new Windows verification distinct from this Linux review and from historical scientific results.
6. Regenerate external package indices, root verification and startup bindings that reference changed bytes. Do not carry a historical PASS forward merely because a filename stayed the same. Preserve any unchanged Study ZIP/seal and explicitly bind them in the new combined index.
7. Replace current draft prose and pin final evidence links to the actual revised records. The supplied preparation reference is `e0f91d3b9d2b46bc656f4ca74db36005056f1160`; its later draft receipt is at `e7cad21db725878bbc3059d411c6aba3986a1230`, under `release_preparation/study-v0.7/revisions/draft_20261029_r2/`. Those identify the reviewed history, not new package bytes.
8. Through the authorized GitHub session, download the final six intended assets and compare their exact identities, then check the rendered release, visibility, intended draft/publication state and Latest selection. Leave historical releases unchanged. This review's inaccessible private receipts remain an explicit verification limit until that check succeeds.

No new scientific experiment, ETEL stage launch, optimizer continuation, official evaluation, measurement sampling, timing benchmark, QPU-prep run or dependency installation is required for this release correction.

## Evidence map

| Finding | Primary evidence |
| --- | --- |
| Design, routing and statistical interpretation | Report pages 2–5 and 7–24; Code `payload/study/governance/STUDY_PLAN.json`, `RUN_MATRIX.json`, `ANALYSIS_PROTOCOL.json`, `quantum/routers.py` and `analysis/official/statistics_core.py`. |
| Conversion and timing | Report pages 26–33; Code `payload/study/analysis/deployment/` and `analysis/independent_deployment/`; original deployment guidance in Documentation. |
| Ideal shot sensitivity | Report pages 34–37; Code `payload/study/analysis/deployment/joint.py` and the study plan's equal-total-budget specification. |
| ETEL role and naming | Report pages 4 and 38–40; Code `execution/README_EXECUTION.txt`, `VENDOR_PROVENANCE.json`, retained vendor files and execution adapter. |
| Helper defects | Code `tools/verify_package.py`, `tools/startup_check.py`, `QUICKSTART.md`; independent disposable-copy runtime probes. |
| Rights | Each package's adoption, rights and scope files; Code `INHERITED_LICENSE_MAP.json` and copied earlier adopted scope. |
| Preservation and current disclosure | Study `provenance/EDITION_CHANGES.json`, `EDITION_CHANGES.md`, `RENDER.json`, `VISUAL_REVIEW.json`; independent original/current Word comparison and page inspection. |
| Package identities | External seals; internal manifests, checksums and root source maps. |

Independent receipts are retained under `tmp/v07_release_review_20261030/`: `attachment_identity.json`; `integrity_agent/integrity_receipt.json`; `rights_agent/rights_scope_receipt.json`; `science_agent/report_preservation.json` and `science_arithmetic_checks.json`; `runtime_review/runtime_review_receipt.json` and `static_import_review.json`; `visual_review/render_comparison.json`; the integrity/rights page-level visual receipts; and `content_screen.json`. These support this review and are not replacement publisher receipts or additional release assets.
