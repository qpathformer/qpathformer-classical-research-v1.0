# Q-Pathformer Study v0.5 — review and Codex revision notes

**Reviewed:** 30 October 2026, Australia/Sydney  
**Release title:** Q-Pathformer Study v0.5 — Flexible Readouts and Classical Controls  
**Repository:** `qpathformer/qpathformer-classical-research-v1.0`  
**Study tag:** `study-v0.5` · **Repository edition:** v1.0  
**Supplied preparation revision:** `draft_20261029_r02`

## Decision

The three supplied ZIPs match their seals, and all six attachment hashes match the v0.5 draft. The scientific report is preserved, its current presentation passes review, the adopted licensing scopes are consistent, and the actual bounded startup succeeds.

**Correct the package verifier before finalizing the Code release.** Its integrity checks can be disabled by Python optimization, and it accepts duplicate checksum records. Also refine the scientific summary so readers understand that the learned-readout comparison changes the output link and native training loss together. Remove the unrelated v0.6 startup wording.

These are focused packaging and explanation changes. No numerical correction to the historical report, new training, shot sampling or full experiment replay is indicated. Preserve the reviewed packages as historical artifacts and build any successor packages from `C:\Q2`.

### Scope of this review

The draft reviewed is the first v0.5 section of `Pasted markdown(3).md`, ending before “Repository packaging record v1.0 (superseded).” The later v1.0, v0.9.5, v0.4, v0.3 and v0.2 entries are copied release-page context, not material to append to v0.5.

The review also covers the attached Study, Documentation and Code ZIP/seal pairs, their current guidance, the report and selected source. Pinned private-repository records could not be retrieved through the available GitHub access; the API returned 404. That does not establish that those records are missing or their links are wrong. Live publication state, authenticated-download binding and the Latest designation remain final checks for Codex in the accessible repository.

## Findings and priorities

| Priority | Finding | Action |
| --- | --- | --- |
| Required | Verifier integrity checks use `assert` and can disappear under optimization. | Replace them with unconditional validation and explicit failure exits. |
| Required | Manifest/checksum entries become dictionaries before duplicate rejection. | Validate uniqueness and record structure before constructing lookups. |
| Required text clarification | Readout, output link, capacity and native training loss change together in Scalar versus Legacy. | Describe the complete recipe improvement and its attribution limit. |
| Required text clarification | Five-moment benefit and classical-control ranking need their uncertainty boundaries. | Qualify the incremental result and distinguish mean performance from statistically resolved superiority. |
| Current guidance correction | v0.6 conversion-test text appears in v0.5 guidance and startup output. | Make the startup description and helper branch specific to the supplied v0.5 selection. |
| Presentation improvement | “One split per family” and “report editions” are ambiguous. | Use “one fixed split per confirmation population” and “the report in PDF and Word.” |
| Verified | ZIP/seal chain, report preservation, adopted scopes and bounded startup. | Preserve these findings; bind successor verification to the new exact bytes. |

## Code-helper corrections

### Replace optimization-sensitive validation

**File:** `QPathformer_v0.5_Code/tools/verify_package.py`

The verifier uses `assert` for manifest membership, file size/hash validation and checksum membership/hash validation. Python removes assert statements under `-O`; `PYTHONOPTIMIZE=1` enables the same behavior. This is documented Python behavior and was reproduced against this exact helper.

A disposable package copy had only `START_HERE.md` changed. The scientific Python files were untouched:

| Invocation on the altered copy | Observed result | Correct behavior |
| --- | --- | --- |
| Ordinary Python | Exit 1; mismatch rejected | Reject |
| Python with `-O` | Exit 0; printed `PASS exact membership and all hashes` | Reject |
| Python with `PYTHONOPTIMIZE=1` | Exit 0; printed the same PASS | Reject |

Use explicit conditions that raise a suitable exception or return a nonzero exit code. Integrity validation must remain effective regardless of optimization. A diagnostic refusal of optimized execution is acceptable in addition, but the validation logic should not rely on removable assertions. `-B` controls bytecode-file creation; it does not prevent optimization.

Keep this change in the release helper. The review does not call for a bulk rewrite of assertions in preserved historical scientific code or tests.

### Reject repeated manifest and checksum records

**File:** `Code/tools/verify_package.py`

The manifest and checksum parsers immediately create dictionaries. A repeated path can therefore disappear into the dictionary before membership is checked. Appending an identical checksum line to a disposable copy produced a normal, non-optimized PASS.

Validate raw entries first: reject duplicate paths, malformed sizes/hashes, invalid checksum syntax and unsafe or ambiguous path forms. Apply the same explicit uniqueness policy to the manifest and checksum file, including the documented case-collision policy. Then check exact file membership and every size/hash.

The supplied inventories contain no duplicate entries and pass the independent audit. A trusted external seal also detects the altered checksum file used in the probe. **These are defects in the standalone helper, not evidence of corruption in the attached ZIPs.**

### Make the quickstart stop on integrity failure

The current quickstart lists verifier, startup and verifier as three separate commands. It does not explicitly stop the sequence when a command fails, and the startup helper does not invoke integrity verification itself.

Have startup call the corrected verifier before scientific imports and after the checks, and report failure if either verification fails. Alternatively, provide a wrapper that enforces this sequence and propagates every failure; prefer one reliable entry point for readers. Update the quickstart to state clearly that a failed verification stops startup. Preserve external ZIP/seal verification before any package code is run.

Keep successful startup narrower than reproduction: it verifies the named bounded checks, not the study's recorded endpoints or a clean installation. Bind the publisher's final startup receipt to the final ZIP, seal and internal integrity identities.

### Describe the checks that actually run

**Files:** `Code/tools/startup_check.py`, `Code/QUICKSTART.md`, `Documentation/RESEARCH_GUIDE.md`.

The actual v0.5 helper runs two selected tests: model parameter shapes/paired initialization, and independent circuit-state/moment agreement. It imports the selected numerical modules and parses retained payload Python. It does not run the v0.4 CLI-help test or a text-model forward pass.

Remove the guide's “plus coefficient-conversion tests for v0.6” phrase and the equivalent v0.6 text in the JSON output. The conditional deployment-compiler test branch is inactive because that implementation is not supplied in v0.5. Make this helper specific to v0.5 or use an explicit study configuration with an accurate recorded scope; do not imply that a later study's checks ran here.

The output also says “AST parse all selected Python,” while the explicit loop scans only `payload/`. Either include both package helpers in that parse or describe it as parsing retained scientific/source Python. The independent review parsed all 52 selected Python files successfully, but that does not change what the shipped helper itself does.

The current helper writes to standard output and has no receipt-file writer. **The v0.4 receipt-overwrite race is not a finding against this v0.5 implementation.** Keep captured output outside the package. If Codex adds a receipt-file option, use exclusive creation and preserve existing receipts as part of that new implementation.

Minor inventory housekeeping: `observed_import_roots` exactly describes the retained source's 55 import roots. It omits helper-only roots such as `ast`, `socket`, `test_models` and the inactive `test_compiler` branch. Label the inventory's coverage explicitly or update it for the final helper. This is not a missing third-party runtime dependency.

## Scientific wording to revise

The current title is suitable. Keep the report's scientific text and result tables unchanged; apply these clarifications to the release and current explanatory guidance.

### State what improved without isolating the wrong cause

The Legacy recipe uses `(1 + X0) / 2` as its probability link and a clipped-probability training objective. Scalar uses a learned sigmoid head, `sigmoid(w X0 + b)`, and stable native logit BCE. Multi extends that learned sigmoid head to five circuit moments. Scalar versus Legacy therefore changes the output link, head parameters, capacity and native training loss together.

Recommended wording:

> The learned-readout recipes substantially improved on the same-study Legacy recipe. This comparison also changes the probability link and native training loss, so it does not isolate the readout's contribution.

The word “Legacy” identifies a control trained within v0.5. Do not present the comparison as a paired improvement over the historical v0.4 scores. The spatial router is fixed in this study; the v0.4 routing-benefit headline is not the v0.5 study question.

### Qualify the incremental five-moment result

The five-moment Multi recipe has better mean results than Scalar, but its added benefit is smaller and task-dependent. Both circle Multi-minus-Scalar adjusted seed intervals include zero. On the ellipse, the common BCE difference is −0.0050 with adjusted seed interval [−0.0083, −0.0017]: it excludes zero, but its magnitude is below the registered 0.01 practical reference.

Recommended wording:

> Five moments added a smaller, task-dependent benefit over one: the circle seed intervals included zero, while the ellipse loss reduction was below the registered practical reference.

This is not equivalence. Do not turn the small mean F1 differences into a general claim that five moments are superior across tasks or seeds.

### Explain the Frozen control accurately

The Frozen recipe starts with the same random circuit core as the other circuit variants, leaves that core untrained and trains its readout head. It was not pretrained. Its substantially worse results support the value of core training under this initialization and recipe; they do not settle the usefulness of all frozen or pretrained encoders.

Use **“random frozen-core control”** in the release so the distinction is visible.

### Describe the classical controls through measured outcomes

The draft's “most attractive accuracy and cost combination” reflects a practical judgment in the historical report. A clearer release sentence is:

> Trig25 controls combined high mean accuracy with much lower measured local execution time. Routed Trig25 had the lowest mean BCE on all three confirmation populations.

Keep “mean” in that statement. The two circle Multi-versus-routed-Trig25 adjusted seed intervals include zero; the ellipse comparison favors routed Trig25. The study does not establish statistically resolved Trig25 superiority across all populations or all possible circuit recipes.

Reported training-loop times are elapsed wall times under concurrent CPU workers, including validation and evidence writes. They are not process CPU seconds, isolated hardware benchmarks, energy estimates or cloud costs. The global MLP is faster than Trig25 in the reported measurements; do not call Trig25 the fastest method.

### Clarify populations, losses and research boundaries

Replace **“five paired seeds and one split per family”** with **“five paired training seeds per confirmation population and one fixed split per population.”** Confirmation uses two independently generated circle populations and one rotated ellipse. The ellipse changes the label boundary under the same uniform input distribution; it is not an out-of-distribution benchmark.

The common primary endpoint is BCE on probabilities clipped to `[1e-7, 1-1e-7]`, using natural logarithms. Call it **common clipped BCE**, lower is better, in the technical guide. It is not the native objective of every recipe and must not be conflated with the later v0.9.5 native-BCE endpoint.

The registered primary family contains twelve contrasts, with 99.5833% Bonferroni-adjusted paired-seed t intervals using five differences and four degrees of freedom. The separate 10,000-resample record bootstrap conditions on the trained models. Keep the two uncertainty sources separate; record resampling does not add training replications.

Each circuit bank has eight circuit angles, and the classification labels are binary. Multi uses five moments: `X0`, `X1`, `Z0`, `Z1`, `Z0Z1`. Those are observables, not five classification classes. The release supplies no ETEL implementation, physical-QPU result or full language-model benchmark.

### Preserve the useful research direction

The report supports a classical implementation direction led by the strong Trig25 controls and an exact representation of the learned circuit logits. Its v0.5 Fourier-span argument covers the depth-two Scalar/Multi/Frozen logits per bank; it does not establish a finite Trig25 logit representation of the Legacy Born-probability link. It does not constitute deployment benchmarking of a newly compiled evaluator.

For future circuit experiments, Scalar remains a simpler comparison candidate; Multi should justify its extra measurement setting. These are historical research directions to explain, not new experiments authorized or completed by this packaging pass. Preserve the report's original recommendations and keep later v0.6 work separate.

## Results checked against the report

The study counts are consistent: 22 short engineering endpoints, 66 full development endpoints and 165 full confirmation endpoints. Each full endpoint completes 200 rounds and 15,000 updates. All eleven recipes continue to confirmation; early stopping is not used.

The following are five-seed mean macro-F1 values on the same held-out records within each population. The full report also includes the smaller routed MLP controls and their uncertainty.

| Recipe | Circle 1 | Circle 2 | Rotated ellipse |
| --- | ---: | ---: | ---: |
| Legacy | 95.22% | 97.08% | 94.69% |
| Scalar | 99.54% | 99.22% | 99.06% |
| Multi | 99.55% | 99.51% | 99.29% |
| Random frozen core | 81.36% | 76.43% | 82.67% |
| Trig25 routed | 99.77% | 99.56% | 99.59% |
| Trig25 global | 99.91% | 99.74% | 99.37% |
| MLP global | 99.70% | 99.35% | 99.17% |

Local-readiness accounting also agrees across the report and protocol: 60 selected circuit checkpoints, 1,920 checkpoint-fixture pairs, 1,474,560 simulated Aer measurement shots and a separate 398,131,200 represented multinomial trials. These are historical recorded results, not experiments rerun by this review.

Multi/Frozen use two measurement settings; Scalar/Legacy use one. A stated shot budget is per setting, so the two-setting recipes consume twice the shots per record at that nominal budget. Do not add multinomial trials to the Aer shot count or describe either as physical hardware shots. Keep the detailed counters in the guide/report rather than the release introduction.

## Rights and publication

The current scopes are explicitly adopted on 29 October 2026. Anthony Siljeg is the licensor. Code/helpers use unchanged Q-Pathformer Platform License 1.0; identified original report content and explanatory prose use CC BY 4.0. The exact scope identities match the supplied files.

The three adoption records are intentionally package-specific because each binds its own scope files. Their common owner, date, licensor, conditions and publication explanation agree. Different adoption-file hashes are expected, not an inconsistency.

Use a self-contained rights paragraph rather than requiring new readers to know v0.1 and v0.9.5:

> The identified original report content and explanatory prose are licensed under CC BY 4.0. Selected Python source and package helpers are source available under Q-Pathformer Platform License 1.0. Each package includes its adopted scope; applicable earlier grants remain in force and excluded material retains its separate terms.

The inherited coverage is independently supported: `circuits.py` exactly matches the adopted v0.9.5 kernel, and `routers.py` contains two matching expression blocks. Historical scope records mentioning ETEL are rights references, not implementation contents of v0.5. Null entries where no positive inherited match was found do not cancel the current code grant.

The old v0.4 sentence that could imply extra owner permission for downstream CC BY use is absent here. Do not carry that finding forward. Publication and repository visibility remain separate from the adopted licensing state. No repeat licensing decision or change to the full license texts is indicated.

Keep the established attribution:

**Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.**

Anthony remains licensor; affiliation does not transfer ownership. Scoped grants do not license excluded datasets, environments, model artifacts, architecture documents or full archives as a whole.

## Recommended release body

This replacement keeps the suitable title and makes the findings and downloads easier to follow. Retain the draft/private label only while it remains true. The verification wording describes the intended use; it does not claim that future corrected assets have already passed.

```markdown
# Q-Pathformer Study v0.5 — Flexible Readouts and Classical Controls

**Draft for owner review · Study · Documentation · Code**

Q-Pathformer v0.5 examines how a learned output head changes a shallow circuit classifier's performance when compared with strong classical models. Eleven recipes were evaluated on two fresh circle populations and a rotated ellipse. All 66 development and 165 confirmation endpoints completed their full training budgets.

This release brings the completed study into Q-Pathformer Classical Research, repository edition v1.0. Study v0.5 and repository edition v1.0 are separate identifiers.

## Main findings

The learned-readout recipes substantially improved on the same-study Legacy recipe. Across the three confirmation populations, the one-moment Scalar recipe reached mean macro-F1 of **99.06–99.54%**, and the five-moment Multi recipe reached **99.29–99.55%**.

The Scalar-versus-Legacy comparison also changes the probability link and native training loss, so it does not isolate the readout's contribution. Five moments added a smaller, task-dependent benefit over one: the circle seed intervals included zero, while the ellipse loss reduction was below the registered practical reference. The random frozen-core control performed substantially worse.

**Strong classical controls remain central to the result.** Trig25 controls combined high mean accuracy with much lower measured local execution time. Routed Trig25 had the lowest mean binary cross-entropy (BCE; lower is better) on all three populations, although the adjusted seed intervals did not establish its advantage over Multi on either circle population.

These findings concern small synthetic classifiers on classical CPUs. Five paired training seeds and one fixed split per confirmation population provide limited evidence about broader tasks. Historical scores from earlier studies are context, not paired improvement evidence. No physical-QPU result, quantum advantage or full language-model benchmark is reported.

## Choose a download

Download each ZIP you need with its matching `.seal.json`, extract it once and open `START_HERE.md`.

| Package | What it contains |
| --- | --- |
| `QPathformer_v0.5_Study.zip` | The preserved report in PDF and Word, its edition note, report rights and provenance. |
| `QPathformer_v0.5_Documentation.zip` | The research guide, original guidance and reproduction boundaries. |
| `QPathformer_v0.5_Code.zip` | Selected scientific implementation, tests, dependency information and bounded startup/verification tools. |

The downloads exclude datasets, checkpoints, installed environments and the complete retained archive. No ETEL implementation is supplied. The release preserves historical results and adds no experiment.

## Verification and reproduction

Verify each ZIP and external seal, then follow `VERIFY.md` and the Code quickstart. The bounded checks cover selected numerical imports, model shapes/paired initialization and independent circuit-state/moment agreement. They do not install a clean environment, reproduce training, score the official data, sample quantum shots or submit hardware jobs.

The report's compilation, illustrative-noise and shot results are local simulator evidence. Full replay needs the separately retained data, checkpoints and operational records. Seals identify file integrity; they are not digital signatures.

## Rights

The identified original report content and explanatory prose are licensed under **CC BY 4.0**. Selected Python source and package helpers are **source available under Q-Pathformer Platform License 1.0**. Each package includes its adopted scope; applicable earlier grants remain in force and excluded material retains its separate terms.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.
```

Add verified links to the final research guide, package index and verification/publication record beneath the relevant sections. Keep the exact hashes and inventory counts in those records. Do not duplicate the title in the body if GitHub's title field already presents it, or copy the other releases/footer from the supplied page.

As minor current-guidance cleanup, change “report editions” to “the report in PDF and Word,” standardize `Q Pathformer` headings to `Q-Pathformer`, and identify the source map by its actual `provenance/SOURCE_MAP.json` location. Preserve historical labels inside the original report and source.

## What was verified independently

### Integrity and selected provenance

The independent package audit completed 1,097 checks without a failure: ZIP CRCs, safe single-root members, regular unencrypted files, path uniqueness, complete manifests/checksums, all sizes/hashes, source maps, selected source identities and current scope bindings. All 27 packaged JSON files and three seals parse without duplicate object keys. All 26 active local Markdown file links resolve.

The detailed inventories contain 76 Code files, 19 Documentation files and 16 Study files. Code contains 52 Python files: 50 retained scientific/source files and two helpers. These counts belong in the audit record, not the public release introduction.

All three packages consistently identify `C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.5\draft_20261029_r02`. The new `qpath-study-release-seal-1` schema uses package-relative internal paths and is internally consistent; do not impose the earlier v0.4 schema on it. The Linux review cannot directly inspect the live Windows filesystem.

### Report preservation and presentation

The independently retained original DOCX is 675,200 bytes, SHA-256 `b08a039280e478710eeae7faa521fd37a41224bfd81100391ba8880f15992fb9`. All 189 original non-section body elements remain an exact canonical-XML prefix in the current DOCX. All 25 tables and four embedded PNG figures are unchanged. Only `word/document.xml` and `docProps/core.xml` changed; six elements append the edition note.

All 34 current PDF pages were individually inspected. No clipping, overlapping content, broken tables, missing figures, broken glyphs or numerical presentation defect was observed. The independently rendered DOCX also has 34 pages, and whitespace-normalized page text matches the supplied PDF on every page. This is not a pixel-identity claim between different renderers.

The earlier metadata-only PDF correction's separate pixel-comparison receipt is outside the attachments. This review verifies the current report and its presentation; it does not independently reproduce that earlier before/after pixel comparison. Historical internal labels, full-archive references and recommendations are explained by the appended edition note and need no report reissue for this review.

### Actual bounded startup

The supplied helper ran successfully with Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0 on Linux. Both selected tests passed. The first checks all eleven recipes' parameter counts and the defined initialization/prediction pairings; the second checks circuit states and moments against independent matrices. This is not a claim that every selected module/test or every optional dependency was exercised.

The unmodified package verifier passed before and after startup, and the full original extracted-file path/hash snapshot remained unchanged. All 52 Python files also parsed during the independent static review. The negative probes ran only on disposable copies and did not alter any attachment or original extraction.

No training, optimizer update, official scoring, quantum-shot sampling, noise study, dependency installation or QPU submission ran. This Linux startup does not replace final Windows preparation verification or full historical replay.

A targeted credential-pattern screen of all 111 extracted files, including report XML/text, found no recognized private-key, GitHub-token, AWS-access-key or OpenAI-key patterns. This is a limited screen, not a comprehensive security or ownership certification.

### Rights and external records

The rights audit completed 467 checks without a failure. Current code, guidance, report and figure identities match their adopted scopes. Canonical license texts are unchanged, and positive inherited-code matches were checked against retained prior bytes.

The pasted preparation links use commit `99dd3cadc9e3366dbf632352c56e0d0d06024e86`; the later draft/download receipt uses `1ec1e579b9cd49d2c14346c1176cff3e75aa8c4a`. These different commits are not inherently inconsistent. Available access returned 404 for the pinned package index and draft receipt, so their private contents and live publication state were not independently verified.

The full archive reference records 30,234 payload files and 2,812,931,271 logical payload bytes, plus a 7,420,512-byte delivery manifest. The archive and manifest were not supplied for a fresh scan. These figures describe retained evidence, not the download size, RAM requirement or a tested hardware minimum.

## Codex completion plan

1. Correct the two package helpers and the current scientific/startup wording. Keep the 50 retained scientific/source files and both report formats byte-identical.
2. Demonstrate valid-package success and altered-file rejection under ordinary Python, `-O` and `PYTHONOPTIMIZE=1`. Reject duplicate manifest and checksum records before building dictionaries. Include missing/unexpected-file checks under the same unconditional logic.
3. Confirm that startup stops before scientific imports when verification fails and that post-startup changes prevent a PASS. Match its recorded scope to the tests actually executed. Keep output outside the sealed package.
4. Build affected successor packages in an unused revision directory below `C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.5\`. Preserve the current ZIPs, seals and historical receipts.
5. Refresh affected code/guidance scope identities, adoption-to-scope bindings, source maps, dependency coverage, internal inventories and seals. Preserve the owner's adoption decision and full license texts; distinguish a new package identity from a new licensing decision.
6. Re-extract the final Code ZIP, run genuine bounded startup in the intended compatible environment, and bind its output to the exact final ZIP/seal identities. A PASS for an earlier file with the same name is insufficient.
7. Verify authenticated downloads against the final package index and record the actual target commit/tag. Update release links to the selected successor evidence. Preserve the draft until the existing owner publication workflow is complete; repository visibility is separate. Keep `study-v0.9.5` Latest as directed and verify the live setting.
8. Use the simplified release body and preserve historical scientific evidence. No new scientific campaign or repeat adoption decision is required for these packaging corrections.

## Appendix — exact review inputs

These identities belong to the supplied `r02` assets. Rebuilt packages need new identities; do not assign these hashes to changed bytes.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `QPathformer_v0.5_Code.zip` | 267,317 | `ac992cafc3d6a50483a55db9265e1721a76f72c320761a08f56d3dc421a5d078` |
| `QPathformer_v0.5_Code.seal.json` | 1,518 | `10cda4969b19a0ec0bb432df74069788b33380b6c8bfb65495ccbd462630a714` |
| `QPathformer_v0.5_Documentation.zip` | 41,370 | `24f1080b7f8390f4aff8bb89d50cb924bb30a2b9291b4fcd26ca364e6771ef8c` |
| `QPathformer_v0.5_Documentation.seal.json` | 1,551 | `e7c4555842f87ed7af6256b43a987dd8dcc63bf716cde29345dfe7807dca16e5` |
| `QPathformer_v0.5_Study.zip` | 1,649,207 | `6ca8adce507a44cebfc5a99874409b0e0d1e400c4e04e90d89c3cd5e22b33978` |
| `QPathformer_v0.5_Study.seal.json` | 1,521 | `38ee2e5923baaac985e570cf495fd516ead6b7afed093205b3a44d6122599c90` |

Current report identities:

- DOCX: 675,972 bytes; SHA-256 `51580cfc9f21a69a815f3887c0405c5b5b854aee37513b189e67aa29f7eadeea`.
- PDF: 1,326,651 bytes; SHA-256 `54df391f847ee29016cb371df874d99516c3ba87c8aeec8f632d54c3c6d59080`.

The pasted asset display has download-count digits joined to size labels. Use the byte counts above and seal records for identity; this familiar display artifact is not a separate package-integrity finding.

## Sources and review evidence

Primary sources are the attached v0.5 draft and packages identified above, particularly:

- Study: both report formats, `provenance/REPORT_PRESERVATION.json`, `provenance/REPORT_REVIEW.json`, edition changes and report scope.
- Documentation: research guide, release notes, original study/reproduction guidance and analysis/readiness protocols.
- Code: the two helpers, quickstart, model/circuit source, selected tests, analysis protocol, dependency inventory and inherited-rights records.
- All packages: external seals, internal manifests/checksums, source maps, scope records and adoption records.

Independent scratch evidence is retained under `/workspace/scratch/c9c666df41fc/tmp/v05_release_review_20261030/`: attachment identities; integrity and rights receipts; report preservation and scientific arithmetic; genuine startup and disposable-copy probes; static import review; report render/page comparison and individual page checklists. These are review evidence, not replacement publisher receipts.

External primary references:

- [Python 3.12: the assert statement](https://docs.python.org/3.12/reference/simple_stmts.html#the-assert-statement).
- [Python 3.12: command line and environment](https://docs.python.org/3.12/using/cmdline.html), including `-O`, `PYTHONOPTIMIZE` and `-B`.
- [CC BY 4.0 official legal text](https://creativecommons.org/licenses/by/4.0/legalcode.en).

No uploaded package, original report, retained scientific source, adoption decision or GitHub state was modified by this review.
