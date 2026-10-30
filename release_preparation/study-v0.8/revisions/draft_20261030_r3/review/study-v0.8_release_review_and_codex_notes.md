# Q-Pathformer Study v0.8 — Release review and Codex revision notes

**Review date:** 30 October 2026  
**Owner:** Anthony Siljeg  
**Repository:** `qpathformer/qpathformer-classical-research-v1.0`  
**Reviewed preparation:** `study-v0.8 / draft_20261029_r2`  
**Purpose:** Prepare the private release candidate for final owner review. This note does not publish a release, change repository visibility, adopt a new license or run a new scientific experiment.

## 1. Decision

**Retain the v0.8 study and its scientific findings. Prepare a focused packaging and presentation revision before treating this as the final publication candidate.**

The supplied ZIPs and seals are internally consistent and match all six hashes in the pasted draft. The report supports the headline findings. Its original scientific prose, tables and embedded figures are preserved, and all 45 pages of the supplied PDF are readable. The current package records support the stated adopted, separately scoped licenses.

The main actionable defect is in the two new package helpers: Python optimization can disable checks and still produce a success result. Duplicate integrity records are also silently accepted. These are release-tool defects; the review found no corresponding corruption of the actual supplied packages.

There are two presentation/provenance issues: a copied v0.9 disclosure clause in the v0.8 visual-review receipt, and a conversion-specific loss of seven table rows when the DOCX is exported by the review environment's alternative word processor. The supplied PDF and underlying DOCX table both contain those rows.

| Priority | Action | Required outcome |
| --- | --- | --- |
| Before final packaging | Replace assertion-based acceptance checks in both package helpers; reject duplicate manifest/checksum paths | Altered or incomplete packages cannot emit a successful verification/startup result |
| Before final review | Gate startup on successful verification, preserve exit codes and verify package bytes afterward | A receipt accurately describes the exact package tested |
| Before final review | Add a current v0.8 clarification for the foreign v0.9 visual-review clause | Historical receipt remains preserved; current review describes this report |
| Before release wording is finalized | Clarify common clipped BCE, priority sampling, routing and ETEL's role | Readers can distinguish the intervention, predictor and execution layer |
| Before any report re-export | Retain the supplied PDF as the reading edition; check every table row in any replacement export | No incomplete alternate rendering replaces the complete PDF |
| At the final authenticated handoff | Check final uploaded identities, commit links, draft/visibility state and Latest selection | Uploaded candidate and current records agree |

No new training campaign is needed to resolve these findings. Avoid broad changes to the established main README, historical scientific implementation or scientific conclusions.

## 2. Evidence reviewed and limits

The review used the three local ZIP/seal pairs, all extracted members, the original v0.8 internal DOCX available from the earlier research collection, registered protocols and selected implementation. It also inspected the current report edition, its metadata, legal scopes and inherited-license records.

Independent checks covered ZIP safety and CRCs; complete member sets; manifest, checksum, source-map and external-seal bindings; JSON duplicate keys; local Markdown links; Python syntax and import inventories; report-content preservation; supplied-PDF rendering; bounded startup; and specific failure probes on disposable copies.

The genuine startup used **Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0** in this Linux review environment. The historical study records **Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1** on Windows. These are different environments. Successful bounded startup here does not establish historical replay, a Windows ETEL execution test or portable fresh installation.

The review did not run training, optimizer updates, official scoring, shot sampling, inference timing experiments, ETEL fit launches/recovery/cancellation, QPU jobs or dependency installation. It did not rescan the excluded full archive. Reported numerical findings were checked against the retained report, protocols and code; omitted experimental arrays were not recomputed.

Attempts to read the two pinned GitHub verification/draft records through the available authenticated connection returned 404. This does not establish that those private records are absent or invalid. Live GitHub state and authenticated download identity remain for the final release environment to verify.

### Source key used below

Paths are relative to the corresponding extracted package unless stated otherwise.

| Key | Source |
| --- | --- |
| S1 | Study: `reports/QPathformer_v0.8_Report_Edition_1.pdf` and matching DOCX |
| S2 | Code: `payload/study/governance/STUDY_PLAN.json`, `ANALYSIS_PROTOCOL.json`, `RUN_MATRIX.json` |
| S3 | Code: `payload/study/quantum/sampling.py`, `models.py`, `routers.py`, `study.py` |
| S4 | Code: `payload/study/analysis/official_evaluation/statistics_core.py` |
| S5 | Documentation: `OVERVIEW.md`, `REPRODUCTION_BOUNDARIES.md`, `source/analysis/reproduction/README_REPRODUCTION.txt` |
| S6 | Code: `payload/study/execution/VENDOR_PROVENANCE.json`, `durable.py`, `vendor/etel/core.py`, `vendor/etel/__init__.py` |
| S7 | Code: `tools/verify_package.py`, `tools/startup_check.py`, `QUICKSTART.md`, `DEPENDENCY_INVENTORY.json` |
| S8 | Every package: adoption, scope, legal-text, source-map, manifest and checksum records; Code inherited-license map |
| S9 | Study: `provenance/EDITION_CHANGES.json`, `EDITION_CHANGES.md`, `VISUAL_REVIEW.json`, `RENDER.json` |

## 3. Scientific interpretation to preserve

### Priority produced small, task-dependent benefits

The eight direct primary comparisons are **MultiK priority minus uniform** and **TrigK priority minus uniform**, separately on four tasks. They are not eight tasks, eight classes or the complete set of twenty primary comparisons.

Four direct comparisons support lower loss with priority:

| Task | Circuit model MultiK | Routed trigonometric model TrigK |
| --- | --- | --- |
| Checkerboard | Inconclusive | Lower BCE with priority |
| Spiral | Inconclusive | Lower BCE with priority |
| Noisy annulus | Inconclusive | Inconclusive |
| Rare disks | Lower BCE with priority | Lower BCE with priority |

Use **common clipped binary cross-entropy (BCE; lower is better)** on first mention. The registered primary metric uses natural logarithms and clips probabilities to `[1e-7, 1-1e-7]`. Training and priority scores use native logit BCE, which is separately reported as a diagnostic. Do not import the native-BCE primary-outcome wording from study v0.9.5. On spiral, the report's TrigK priority means differ: native BCE 0.250964 versus common clipped BCE 0.240354. [S1, pp. 1, 5 and Appendix A; S2–S4]

The following rounded values provide a private editorial cross-check. Keep them in review evidence; a public release needs only the interpretation and report link.

| Task | MultiK P−U: mean and adjusted interval | TrigK P−U: mean and adjusted interval |
| --- | --- | --- |
| Checkerboard | −0.00351 [−0.01346, +0.00644] | −0.00926 [−0.01140, −0.00712] |
| Spiral | −0.00508 [−0.01203, +0.00187] | −0.00866 [−0.01146, −0.00586] |
| Noisy annulus | −0.00168 [−0.00378, +0.00042] | −0.00045 [−0.00404, +0.00315] |
| Rare disks | −0.00409 [−0.00604, −0.00214] | −0.00213 [−0.00298, −0.00127] |

**None establishes an absolute BCE reduction greater than 0.01 across its entire adjusted interval.** Under the P−U convention, that would require the interval's upper endpoint to be below −0.01. The reference is not a relative percentage reduction, an F1 percentage-point gain or an equivalence margin. Inconclusive comparisons do not establish equivalence or absence of benefit. [S1, Appendix B]

### The independent unit is a population

Confirmation contains **eight independent populations per task**. Two paired optimizer-seed differences are averaged within each population before inference. The twenty primary comparisons use nominal **99.75% two-sided Bonferroni t intervals, df = 7**. Do not describe the sixteen seeded endpoints per task/model as sixteen independent population replications. Small-sample distributional assumptions remain material. [S1, pp. 5–7; S2; S4]

The full family contains eight direct effects, eight geometry-versus-hash priority interactions and four MultiK priority versus TrigG121 priority comparisons. Two Trig interactions favor geometric routing on checkerboard and spiral; a favorable interaction alone does not establish an absolute benefit. The routed circuit remains substantially behind the wider global baseline on those two tasks. Preserve all twenty comparisons and all ten arms. No record-level bootstrap should be added to the description of this registered analysis.

Macro-F1 is descriptive. Higher F1 need not mean lower probability loss: rare-disk MultiK priority has the highest reported mean F1, while the global control has lower descriptive BCE. The F1 plot's whiskers are population sample SDs, not confidence intervals. Avoid a headline suggesting universal F1 improvement. [S1, pp. 6–8 and Appendices A–B]

### Run counts and retrains are coherent

The matrix has **40 short engineering fits, 80 development fits and 640 confirmation fits**. Confirmation arithmetic is four tasks × eight populations × two seeds × ten arms. All full fits complete 200 rounds and 15,000 updates; engineering fits use 12 rounds and 900 updates. These counts belong in the report or detailed study page; the release need not repeat every subtotal. [S1, p. 3; S2]

The four additional preselected retrains cover:

| Family | Target arm | Population / optimizer seed |
| --- | --- | --- |
| Checkerboard | MultiK priority | Confirmation population 01 / 1601 |
| Spiral | TrigK priority | Confirmation population 01 / 1601 |
| Noisy annulus | MultiHash uniform | Confirmation population 01 / 1601 |
| Rare disks | TrigG121 uniform | Confirmation population 01 / 1601 |

They regenerate data and routers and train from unchanged sources in new directories without copying a trained checkpoint as initialization. They reuse the historical environment and reviewable path bindings. Original coordinate arrays support freshness reconstruction; original endpoint evidence is read for later comparison. These are same-environment reproduction checks, not new independent populations, autonomous installation or proof of relocation to arbitrary hardware. [S1, pp. 9, 44; S5]

## 4. Explain sampling, routing and ETEL separately

The current draft title can remain. Add a plain-language opening question: **Does giving higher-loss training examples more sampling opportunities help models with fixed input routing?**

| Operation | What it changes | What readers should understand |
| --- | --- | --- |
| Priority sampling | Which existing training records enter a minibatch | A training-only intervention with importance-weighted gradients |
| Model routing | Which frozen parameter bank handles an input | Geometric or hash routing within the predictor |
| ETEL execution | Which complete training jobs run and how execution state is tracked | Coordination around the scientific fit, separate from the sampling policy |

There are five base models, each paired with uniform and priority sampling: MultiK, MultiHash, TrigK, TrigHash and TrigG121. The circuit pair has 70 learned predictor parameters; the routed trigonometric pair has 125; the global control has 121. Routing metadata, optimizer state and audit traces are additional. Similar parameter counts do not make function classes or computational costs identical. [S1, pp. 2–5; S3]

Both policies draw with replacement. The first ten rounds are uniform. Subsequent priority probabilities use training-record native losses and remain fixed within each round; inverse-probability weights correct the sampled raw gradient. The frozen router is not refitted from priority scores, labels or held-out outcomes. The conditional gradient target remains ordinary empirical BCE, without guaranteeing identical Adam trajectories or better generalization. [S3]

Uniform controls also pay the scheduled diagnostic-refresh cost. All full fits still receive the complete update budget. Therefore, these results do not establish early-stopping savings or end-to-end training savings against an uninstrumented uniform trainer. Historical v0.7 used shuffled passes; comparisons with v0.7 scores remain context rather than a pooled, paired improvement estimate. [S1, pp. 2, 5]

### ETEL naming bridge

ETEL **is present** in this Code package. The Documentation overview currently says “ETEL 0.2.0 schedules whole fits.” Replace or expand that current explanatory sentence:

> This study includes the study-specific execution adapter for Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1. Its retained vendor source records version 0.2.0. ETEL coordinates complete training fits; the study's priority policy controls sampling within each fit.

Preserve `__version__ = "0.2.0"` and vendor provenance unchanged. The study ran at most five concurrent fit processes; 64 logical slots are bookkeeping. This is not evidence of 64 physical workers, extra circuit states, increased model capacity or a measured 64× speedup. It is also separate from the later ETEL suitability-allocation study. [S1, pp. 4, 39; S5–S6]

Keep repository edition **v1.0**, study **v0.8**, component **ETEL v0.1**, incorporated source **0.2.0** and future **qpu-prep-v0.1** distinct. This release does not report a new QPU-preparation run or physical-QPU experiment.

## 5. Conversion and latency claims

The prediction-preserving conversion is a separate deployment result. The report covers 256 circuit coefficient tables and 384 learned-trigonometric repacks. Its independent maximum probability discrepancy is **2.615e−14**, which supports the draft's “below 2.62e−14.” The reported checks found no classification changes. This establishes agreement to the checked floating-point tolerance, not bitwise-identical probabilities or fresh verification of excluded checkpoints in this review. [S1, pp. 9–10]

For context, reported group medians of paired original/compiled latency ratios are 4.33–4.59× at batch size 1, 11.82–16.03× at batch size 32 and 2.33–5.36× at batch size 1,024. They concern complete resident-model CPU calls, including routing and feature/readout work, with model loading excluded. They are not ratios reconstructed from aggregate means or per-record timings mislabeled as complete calls. Keep the detailed timing table in the report.

All three timing sessions must remain included. Session three was substantially faster; its cause was not isolated. Do not pick the fastest session, imply a hardware-independent guarantee or treat technical timing repetitions as independent populations. Several learned classical controls remain faster in relevant conditions. [S1, pp. 2, 10 and Appendix E]

Conversion is not compression: the circuit parameter payload is 560 bytes, the compiled coefficient payload is 1,000 bytes, and retaining both is 1,560 bytes before router/container overhead. The “exact conversion” phrase describes algebraic equivalence with numerical verification; it is not another efficacy arm or quantum hardware acceleration.

Use this limitation sentence:

> All results use classical CPU computation; v0.8 includes no physical-QPU run or new finite-shot experiment.

Do not carry v0.7's shot counts or measurement campaign into v0.8.

## 6. Required package-helper correction

### Observed behavior

The supplied `verify_package.py` uses `assert` for membership, containment, symlink, size and hash checks. The supplied `startup_check.py` uses `assert` for moment checks and subprocess return codes/help output. Python removes assertions under optimization; `-B` does not change that behavior. See the official [assert documentation](https://docs.python.org/3.12/reference/simple_stmts.html#the-assert-statement) and [command-line/environment reference](https://docs.python.org/3.12/using/cmdline.html).

Focused probes changed disposable copies only:

| Probe | Normal Python | `python -O` | `PYTHONOPTIMIZE=1` |
| --- | --- | --- | --- |
| Change `START_HERE.md`, then run verifier | Rejects, exit 1 | Incorrect PASS, exit 0 | Incorrect PASS, exit 0 |
| Remove required execution launcher, then run startup | Rejects, exit 1 | Incorrect PASS, exit 0 | Incorrect PASS, exit 0 |

In the missing-launcher optimized startup, the three child return codes were **0, 2, 0**, while the top-level result still said PASS. This is a concrete false-success defect.

An identical duplicate checksum line also passed. An identical duplicate manifest entry passed after refreshing only the manifest's checksum to isolate duplicate-record handling. The trusted external seal detects those changed integrity-file bytes; the defect is that the internal verifier collapses duplicate paths into sets/dictionaries instead of rejecting them. The supplied original integrity files themselves have no duplicates.

### Codex implementation scope

Change **the two package helpers and their current guidance**, while preserving retained scientific source bytes.

1. Replace every acceptance-critical `assert` with explicit conditional validation and a nonzero failure path. Cover numerical shape/finiteness/range checks, exact membership, path rules, size/hash checks, required child exit status and required help output.
2. Parse integrity records strictly. Reject duplicate manifest paths and checksum paths before creating sets/dictionaries. Reject duplicate JSON object keys, malformed hashes, malformed rows and unsafe or ambiguous member paths. Retain exact membership and containment checks.
3. Keep expected CLI paths explicit. Missing modules or files must fail; do not silently skip a required check and print PASS.
4. Make startup contingent on a successful package verification. Verify bytes again afterward, and bind the receipt to the final package identity and actual interpreter/dependency versions.
5. Update the quickstart so a failed verification stops the sequence. Its two independent PowerShell command lines currently do not enforce that gate. Capture and check exit status explicitly, including startup failure, before accepting a receipt.
6. Keep receipts outside the complete extracted package and use distinct revision-specific names. The current helper writes stdout only; there is no internal receipt-writing implementation to patch. Handle redirection/receipt persistence in the documented wrapper without overwriting prior accepted evidence.
7. Keep the bounded scope unchanged unless there is a concrete reason to extend it. Importing `reference_v03` is not an independent matrix-parity test. Three help screens are not an ETEL execution/recovery test.

The genuine supplied package passed pre-verification, bounded startup and post-verification, with all three help commands exiting zero. Its files stayed unchanged. All 85 Python files parsed, and the import-root inventory matches the selected code and helpers. These successful checks do not erase the negative-probe failures.

The final correction gate needs the valid package, changed-payload, duplicate-record and missing-required-CLI cases. Exercise both optimization mechanisms. Either perform explicit checks successfully under optimization or reject optimized startup clearly; a false PASS is unacceptable. Avoid expanding this into training, timing, shot or hardware testing.

## 7. Report fidelity and viewing guidance

### What is preserved

The original DOCX is 890,193 bytes, SHA-256:

`499c25c86dba1a81486cd38edca25ba4b9741499d8f2a5a3e3145645ac2caa95`

The edition DOCX is 891,122 bytes, SHA-256:

`36287155f1a6f0a90773e3da01dc1666eaee5cd3d89e8add77e25c3787328657`

All 268 original body elements remain an exact XML prefix; seven edition-note elements are appended. All 57 tables and two embedded images are unchanged. Only document-body and core-metadata parts differ among the 21 DOCX parts. The supplied PDF is 2,020,094 bytes, SHA-256:

`92e06293cac5b1f796159a127dd9201bd7b83abc51f22a80cdf2aaeed7a3bd08`

All 45 supplied-PDF pages were visually inspected. No material clipping, overlap, missing glyph, truncated table/figure or unintended blank page was found. Historical internal labels and future-study recommendations remain historical. Do not silently rewrite those recommendations into current publication authority. [S1, S9]

### A specific alternate-render failure

A fresh DOCX export in **LibreOfficeDev 26.8.0.0.alpha0** also produced 45 pages, but did not preserve all content. The Appendix F Spiral cost table, the DOCX's 50th table, contains all ten arm rows in both original and edition XML. The supplied PDF displays them on page 38. The alternative export omitted seven rows across its pages 37–38:

- MultiK priority;
- MultiHash uniform and priority;
- TrigK uniform and priority;
- TrigHash uniform and priority.

This is a demonstrated conversion-compatibility issue in that reviewed engine/version. It is not missing scientific source data, a defective supplied PDF or proof that Microsoft Word renders the DOCX incorrectly. Its cause was not established.

**Keep the supplied PDF as the recommended reading edition.** Add a short viewing note to current guidance:

> Use the supplied PDF for the reviewed page layout. The Word edition preserves the editable report content, but pagination and table rendering can vary by application. Check all table rows before exporting a replacement PDF.

Do not replace the supplied PDF with the defective review export. A future compatibility edition would need separate identity, an edition note, complete content comparison and updated package bindings. Page-count equality alone is insufficient. There is no need to redesign the complete preserved report to finish this packaging revision.

### Correct the visual-review disclosure reference

`Study/provenance/VISUAL_REVIEW.json` contains a foreign clause: “v0.9 includes account/credit/token usage on original page 37.” That is not a v0.8 disclosure finding. Actual v0.8 page 37 contains inference-ratio material and the beginning of Appendix F's training-cost accounting. [S9]

Preserve the old receipt and add a current clarification/review record binding the unchanged DOCX and PDF. Suggested wording:

> This review concerns study v0.8. The historical visual-review receipt contains a v0.9/page-37 disclosure reference that does not describe this report. The v0.8 edition retains local evidence paths, host configuration and resource/execution accounting. Page 37 contains inference-ratio and training-cost tables. The report edition and scientific content remain unchanged.

The new review should distinguish supplied-PDF inspection from the alternate DOCX-render result. If included in a revised Study ZIP, regenerate that package's integrity records and seal. This is a provenance clarification, not a scientific erratum.

A bounded scan found no matches for the specific private-key/token patterns checked. That limited result does not replace disclosure review of retained paths and operational details.

## 8. Rights and provenance

The current packages record **ADOPTED on 29 October 2026**, with Anthony Siljeg as licensor. The adoption records bind the supplied scopes and preserve earlier grants. Do not revert this release to “proposed” or “unadopted” based on earlier draft conversations. [S8]

The scopes cover all 85 packaged Python files, controlled original report content and explicitly listed explanatory prose. Report scope identifies both formats, the two embedded figures and table presentation. The unchanged Platform 1.0 and CC BY 4.0 legal texts are consistent across all three packages. Exact inherited-file and shared-expression mappings were checked against available earlier source bytes.

Retain separate treatment of code, report/prose, third-party material, datasets, model artifacts, architecture documents and full archives. The report's CC BY grant is not constrained by Platform terms merely because the downloads accompany each other. Hashes identify the publisher's edition; they do not require allowed adaptations to preserve its file hash. The [CC BY 4.0 legal text](https://creativecommons.org/licenses/by/4.0/legalcode.en) supplies the applicable reuse conditions.

A helper revision changes exact file identities. Regenerate current scope/provenance bindings transparently, preserve the previous adopted record and describe the new revision under the applicable existing authority. Do not silently edit old hashes or claim changed helper bytes were already the exact old attachment. Additional content should be covered accurately without inventing a blanket grant or requesting a redundant adoption of unchanged material.

Preserve this attribution:

**Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.**

Anthony remains licensor; affiliations do not imply ownership transfer. Licensing, GitHub release publication and repository visibility remain separate.

### Final packages must originate under C:\Q2

All three source maps record final assembly under:

`C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.8\draft_20261029_r2`

The historical helper origins under `C:\Anthony Siljeg\draft_releases_20261029\v07_09`, the ETEL upstream archive under Downloads, and earlier report-build paths are real source provenance. They are not contradictory final-build locations. Preserve them rather than fabricating Q2 origins.

Prepare updated helpers, guidance and final assets in a new revision directory **inside C:\Q2**. The present Linux review confirms recorded provenance, not the live Windows filesystem.

## 9. Suggested shorter GitHub release text

Use the existing title:

**Q-Pathformer Study v0.8 — Priority Training and Routed Models**

The body below is for a corrected, verified private candidate. Update its evidence link to the final immutable revision before use. Do not assert that the recommended helper fixes have passed until they actually have.

---

**Draft for owner review · Study · Documentation · Code**

Q-Pathformer v0.8 asks whether giving higher-loss training examples more sampling opportunities helps models with fixed input routing. It compares uniform and priority sampling across five circuit and classical model designs on checkerboard, spiral, noisy-annulus and rare-disk tasks.

### Main findings

Four of eight prespecified direct comparisons supported lower common clipped binary cross-entropy (BCE; lower is better) with priority sampling. The other four were inconclusive. None established an absolute reduction greater than 0.01 BCE across its entire adjusted interval.

Priority did not close the routed circuit's gap to the wider global trigonometric baseline on checkerboard or spiral. The results support further work on representation and routing, with priority sampling retained as an optional training policy.

A separate deployment result showed that classical coefficient conversion preserved observed classifications, with a maximum checked probability difference below 2.62e−14, while reducing resident-model inference latency on the recorded CPU. All three timing sessions remain reported, including their variability.

Confirmation comprised 640 fits across eight independent populations per task, with two paired optimizer seeds. All twenty registered primary comparisons are retained. Four additional clean-directory retrains checked selected results in the historical environment; they do not add independent populations.

### Downloads

Download each ZIP with its matching external `.seal.json`, extract it once and open `START_HERE.md`.

| Package | Start here for |
| --- | --- |
| `QPathformer_v0.8_Study.zip` | The preserved report, reviewed PDF, editable Word edition and report provenance |
| `QPathformer_v0.8_Documentation.zip` | The study overview, research context and reproduction boundaries |
| `QPathformer_v0.8_Code.zip` | Selected scientific implementation, the study-specific ETEL execution adapter, dependencies and bounded startup guidance |

Priority sampling chooses training examples. Model routing chooses the predictor bank for an input. ETEL coordinates complete training fits. The included adapter belongs to **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1** and retains historical vendor source version **0.2.0**.

### Scope and reuse

These are classical CPU results on small synthetic classification tasks. They do not establish quantum advantage, physical-QPU performance, broad real-world generalization or a new finite-shot result.

The downloads exclude datasets, trained checkpoints, installed environments and full experiment archives. Full reproduction requires separately retained inputs and review of historical environment and path bindings. The package review covers integrity and bounded offline startup; it does not rerun the full experiment. Use the supplied PDF for the reviewed report layout.

CC BY 4.0 applies to the identified controlled original report content and listed explanatory prose. The unchanged Q-Pathformer Platform License 1.0 applies to the exact selected Python files. Each package contains its adopted scope records; earlier permissions and separate third-party terms remain in force.

Repository edition **v1.0** and study **v0.8** are separate identifiers. This candidate remains a private draft for owner review.

[Review evidence and package identities](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/0649987b001fc3a499ec7ef1c14fd9dc457f9e3f/release_preparation/study-v0.8/revisions/draft_20261029_r2/README.md)

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.

---

**Editorial instructions:** replace the above historical r2 link with the actual final immutable evidence link after preparation. Keep full hashes, membership counters, receipt IDs and storage arithmetic in evidence records. GitHub already presents the asset list; do not paste “Assets6,” download-count artifacts or the site footer into the body. Keep `study-v0.9.5` as Latest according to the established release plan, checking that live setting at the final handoff.

## 10. Codex completion sequence

1. Create a new revision workspace under **C:\Q2**. Preserve r2 ZIPs, seals, records, source code and report editions.
2. Correct the two package helpers and gated quickstart. Add the ETEL naming bridge, clearer BCE explanation, PDF-viewing guidance and current v0.8 receipt clarification.
3. Preserve all original scientific implementation, figures, tables, protocol bytes, vendor version strings and legal texts. Record changes only in the new current revision.
4. Update exact file scopes, source maps, manifests, checksums and package indexes in dependency order. Preserve the existing schema's self-exclusions; do not introduce circular hashes.
5. Build the affected ZIPs under Q2 and derive their matching external seals from the final bytes. An unchanged asset may retain its identity; never claim a stale seal covers changed contents.
6. Fresh-extract the final packages into separate review directories. Verify trusted ZIP/seal identity, internal inventories, complete source-map bindings and local links.
7. Run the bounded startup and focused failure cases described above. Record actual environment, commands, exit codes, result scope and final package identity. Keep receipts outside extracted packages.
8. Confirm original report DOCX/PDF hashes remain unchanged. If any new rendering is proposed, check complete table content, including all ten Spiral cost rows, before substituting it.
9. Update the release body and evidence links together. In the authenticated release environment, download the exact final draft assets and compare them to the Q2 artifacts.
10. Leave a concrete owner-review candidate with the current draft/visibility/Latest state recorded. This review does not authorize publication or make the repository public.

The final completion note should identify the new revision, affected assets, final hashes, helper negative-test results, preserved report/source identities and any remaining authenticated verification. Do not describe packaging validation as a fresh scientific reproduction.

## Appendix A — Exact reviewed attachment identities

These are the supplied **r2 review inputs**, not the future corrected package identities.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `QPathformer_v0.8_Code.zip` | 381,497 | `d280df33db278d9b80779635e4ebfa7abc4ae07edeee6f0203c62ea47f2041d0` |
| `QPathformer_v0.8_Code.seal.json` | 1,288 | `5b443e4d72476460817de0cff848d11cf8219fbfc5b85e7790194bc63ac3d1c6` |
| `QPathformer_v0.8_Documentation.zip` | 39,852 | `a2c6902df294c725696ba0ee215871e6f43e796afe30329ceb6935624dc9b9cd` |
| `QPathformer_v0.8_Documentation.seal.json` | 1,356 | `6650b4424401cf233d5b0766adbfed117b4c63b517826daffacf5557470a9769` |
| `QPathformer_v0.8_Study.zip` | 2,129,826 | `d76bbd7c9c794e3615e7e5e05907145c71ee625a54b33580f63e714cd0b2fa87` |
| `QPathformer_v0.8_Study.seal.json` | 1,294 | `2a2f64d73639d655614d34437cb8d98ba77f7d693c7c6cea592a236dfb2311e6` |

The displayed asset labels in the copied page include the previously explained accidental leading download-count digit. The actual byte identities above agree with the seals; those labels are not evidence of corruption.

The retained archive's **64,335,733,380 logical payload bytes** exclude its manifest and reserved sidecars. That is archival evidence accounting, not a download size, model size, RAM requirement or tested hardware minimum. It was read from retained records rather than independently rescanned. [S5; Code `SOURCE_SELECTION.json`]

## Appendix B — Review evidence and handoff boundaries

Private membership details: Code 107 files, Documentation 19, Study 17. All 143 supplied files pass their applicable inventory/byte checks. The source-selection list identifies 87 implementation/protocol files; an additional execution README is separately and completely covered by guidance scope and source maps. No omission follows from those different counts.

The current review records are in:

`/workspace/scratch/c9c666df41fc/tmp/v08_release_review_20261030/`

Key receipts:

- `attachment_identity.json`
- `integrity_agent/integrity_summary.json` and `integrity_checks.json`
- `integrity_agent/visual_review_pages_01_22.json`
- `rights_agent/rights_review.json`
- `science_agent/report_fidelity.json` and `science_consistency.json`
- `science_agent/spiral_cost_table_render_check.json`
- `runtime_review/runtime_review_receipt.json` and `static_import_review.json`
- `visual_review/render_comparison.json` and supplied/alternate page renders
- `bounded_disclosure_scan.json`
- `remote_access_review.json`

These scratch paths document this review environment; they are not paths a Windows recipient should assume exist. The findings, exact identities and reproduction steps needed for Codex are contained in this note. Codex should create its own final receipts under the Q2 revision and bind them to the actual final assets.

Historical GitHub preparation commit: `0649987b001fc3a499ec7ef1c14fd9dc457f9e3f`.  
Historical draft-receipt commit: `e1cc8920d3459bfdea18fa84a003442e9ca118a9`.  
Preparation path: `release_preparation/study-v0.8/revisions/draft_20261029_r2/`.

**Release integrity seals record hashes and relationships; they are not digital signatures.** Local consistency checks support the supplied artifacts. Current publication state and final authenticated download identity remain separate release checks.

