# Q-Pathformer Study v0.4 — release review and Codex revision notes

**Review date:** 29 October 2026, Australia/Sydney  
**Repository:** `qpathformer/qpathformer-classical-research-v1.0`  
**Study:** v0.4 · **Repository edition:** v1.0  
**Recommended release title:** Q-Pathformer Study v0.4 — Routing and Circuit Contribution

## Decision

The supplied packages have consistent ZIP/seal identities, preserved scientific content and adopted licensing scopes. The actual bounded Code startup also passed in the review environment. **Make a focused packaging revision before finalizing the Code release:** correct the receipt-overwrite race and duplicate-record acceptance in the two package helpers, refresh the affected identities, and verify the final extracted package.

The scientific report, results and retained implementation do not need new experiments or a numerical correction. Improve the release explanation and remove the unrelated v0.2 quickstart wording. Keep the current sealed packages as historical review artifacts.

This review examined the six attached v0.4 assets. The available draft wording was `QPathformer_v0.4_Documentation/RELEASE_NOTES.md`, together with the package guides. No separate live GitHub v0.4 release body, final tag/commit, authenticated download receipt or Windows startup binding was supplied. Consequently, this is a package-and-text review, not confirmation of the live draft's final publication state.

### Review outcome

| Area | Result | Meaning for Codex |
| --- | --- | --- |
| ZIPs, seals and internal inventories | PASS | All three pairs match; no current corruption, duplicate member or missing selected file was found. |
| Original report preservation | PASS | Original scientific body, 31 tables and four figures are unchanged. |
| Report presentation | PASS | All 40 supplied PDF pages were visually inspected; the independently rendered DOCX has the same page count and matching page text. |
| Scientific release claims | PASS with clarity edits | Define Q2 and BCE, name the populations and make the stronger classical controls prominent. |
| Actual bounded startup | PASS | All nine model variants, CLI help and the selected circuit-matrix invariant ran successfully. |
| Package-helper negative probes | FIX | Duplicate checksum paths are accepted; a receipt created after the initial check can be overwritten. |
| Adopted code/report/guidance scopes | PASS | Preserve the recorded adoption; no repeat adoption decision is indicated. |
| Live GitHub and Windows publication records | NOT VERIFIED HERE | Bind the final selected assets to the actual preparation, startup and download records before finalizing the release. |

## Required Codex changes

### Make startup receipt creation exclusive

**File:** `QPathformer_v0.4_Code/tools/startup_check.py`

The helper calls `out.exists()` before running its subprocesses, then later calls `out.write_text(...)`. A second process can create that path between those operations, after which the helper truncates the new file. This contradicts the stated intent to preserve existing receipts.

A controlled probe reproduced the overwrite by creating a sentinel receipt after the initial check. All child commands in that probe were mocked: it demonstrated the file-handling defect and is **not** a scientific startup result. The separate genuine startup completed successfully with real commands.

Reserve the output with exclusive creation, such as `open(..., "x")`, before starting checks and retain the owned handle through the write. Preserve the existing rule that the output must be outside the entire package. If a check or timeout fails, record failure in the receipt owned by this invocation and exit unsuccessfully; never overwrite another invocation's result.

While correcting the helper, run package integrity verification before importing selected scientific modules and again after startup. The current quickstart correctly requests a separate verifier run, but the helper does not enforce that prerequisite or check for changes during execution. Record the integrity outcome and exact extracted-package identity in the receipt. Keep the external ZIP/seal binding in the publisher's verification record.

### Reject duplicate inventory records before building dictionaries

**File:** `QPathformer_v0.4_Code/tools/verify_package.py`

The helper converts manifest entries and checksum lines into dictionaries immediately. Repeated paths are collapsed before membership is checked. In a disposable copy, appending an identical checksum line still produced `PASS`, even though `VERIFY.md` explicitly says duplicate paths must be rejected.

Validate the raw entry sequence first. Reject repeated paths, malformed records and unsafe or ambiguous path representations before constructing lookup tables. Apply the same explicit uniqueness rule to both the manifest and checksum file. Keep exact membership, byte-size and SHA-256 checks. Use the same documented case-collision/path policy as the ZIP preparation checks.

The current uploaded inventories contain no duplicate entries. Their independently checked seal chain passes, and a trusted external seal would detect the altered checksum file used by the probe. **This is a standalone-verifier defect, not evidence that the supplied ZIPs are damaged.**

### Keep startup guidance specific to v0.4

**Files:** `Code/QUICKSTART.md` and `Code/tools/startup_check.py` receipt description.

Remove the unrelated sentence, “v0.2 also checks a small CPU text forward,” and the equivalent receipt-scope wording. The v0.4 selection has no text-classification subtree. Describe the actual three checks:

- In-memory predictions for the nine v0.4 model/routing combinations.
- Argument help for the training CLI, without starting training.
- The selected full-matrix agreement invariant.

The helper also parses all selected Python files. Keep that distinct from executing every test or importing every optional dependency. Remove or make study-specific the dormant text-forward branch so future receipts describe only checks actually applicable to the selected package.

### Refresh affected package records from C:\Q2

Create a successor preparation revision beneath:

`C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.4\`

Use an unused revision directory. Preserve the attached packages and their old receipts. Update the changed helper/guidance scope identities, source map, dependency record where applicable, internal manifest/checksums and external seal. Preserve the unchanged full license texts and the owner's recorded adoption decision. Document routine scoped-file updates; do not relabel adopted material as an unadopted proposal.

Re-extract the final Code ZIP into a fresh directory and run the corrected verification/startup there, writing receipts outside it. Record the final ZIP and seal identities in the package index and startup/download binding. A PASS for an earlier file with the same name must not stand in for this final check.

The 48 retained scientific/source Python files should remain byte-identical. These changes concern the two package helpers and current explanatory/provenance records. If a selected source change becomes necessary, treat it explicitly as a separate revision with its own reason and validation.

## Scientific explanation to retain

### What v0.4 studied

The study crosses three model families with three routing policies: a two-qubit, depth-two circuit model (Q2), a raw-coordinate ReLU MLP and a 25-feature trigonometric sigmoid-logit model; each is evaluated globally, with coordinate-hash routing or with training-only k-means routing. Routed examples activate one of five parameter banks. The fixed k-means router is fitted to training coordinates without labels.

There were 54 development endpoints and 135 confirmation endpoints. Every full endpoint completed 200 rounds and **15,000 optimizer updates per endpoint**. The three confirmation populations are two independent circle populations and a rotated ellipse. Five training seeds are used for each confirmation model/population combination. These are controlled synthetic populations, not three unrelated real-world datasets.

### What the results show

Binary cross-entropy (BCE; lower is better) is the primary endpoint. Macro-F1 is also reported. The following five-seed circuit means match the preserved report:

| Q2 k-means population | Mean macro-F1 | Mean BCE |
| --- | ---: | ---: |
| Circle population 1 | 98.32% | 0.17689 |
| Circle population 2 | 97.16% | 0.18280 |
| Rotated ellipse | 94.41% | 0.21207 |

Spatial routing improves this circuit recipe over its hash-routing control. The stronger classical results must remain equally visible: global MLP and trigonometric models have higher mean F1 and lower BCE on every confirmation population, and the routed trigonometric model also has lower BCE than routed Q2 throughout.

The small routed MLP is a different comparison. Q2's favorable mean BCE difference against it is **unresolved across training seeds**: the adjusted paired-seed intervals include zero on all three populations. Do not summarize that as equivalence or as a general circuit advantage.

The registered primary family contains nine contrasts, with 99.4444% Bonferroni-adjusted intervals. Paired-seed t intervals use five seeds and four degrees of freedom. The separate 5,000-resample record bootstrap conditions on the trained models; it does not supply more training seeds or remove training instability. Keep these details in the research guide/report, with a brief uncertainty statement in the release.

### Terminology and interpretation boundaries

- Define **Q2** on first use. It is the two-qubit, depth-two model name in this study, separate from the `C:\Q2` build location.
- Each circuit bank has **eight trainable angles**, and five banks allocate forty angles. The classification labels are **binary**. Do not describe this as eight algorithmic classes or eight total circuit gates.
- Capacities differ across families: global/routed counts are Q2 8/40, MLP 129/45 and trigonometric 25/125; k-means also fits ten centroid coordinates. Nearby parameter counts do not make capacities equal.
- The trigonometric sigmoid-logit baseline is a different probability family. Do not call it an exact probability emulator of this circuit.
- Validation crossings of a 97% F1 milestone are learning diagnostics. All runs still completed their full budgets; the milestones do not demonstrate realized early-stopping savings or held-out performance at that earlier update.
- No ETEL implementation, physical-QPU execution, current IBM device qualification or quantum advantage is supplied by this study. Historical inherited-license records that mention ETEL do not change the selected implementation.
- Preserve the original report's future-study recommendations as historical recommendations. Packaging v0.4 adds no experiments and makes no claim that unfinished or later studies have been completed.

### Make local-readiness accounting readable

The detailed counters are consistent but too dense for the main release narrative. A sufficient public sentence is:

> Local readiness checks covered all 45 circuit checkpoints and included 737,280 simulated Aer measurement shots. Separate conditional binomial diagnostics are documented in the report; no physical shots or hardware jobs are reported.

For the research guide, preserve the distinction among 1,440 checkpoint-fixture cases, 720 measured Aer experiments, 737,280 simulated Aer shots and 199,065,600 represented binomial trials. The fixture count is not a count of unique data records. The binomial total is not additional Aer or physical shots. Illustrative logical noise is not a device-calibration study.

## Licensing and publication wording

The three current adoption records are identical and explicitly **ADOPTED on 29 October 2026**. The current selection applies unchanged Q-Pathformer Platform License 1.0 to identified Python source/helpers and CC BY 4.0 to identified controlled original report content and explanatory prose. The exact scope records match their selected files.

Anthony Siljeg remains the named licensor. Use the established attribution:

**Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.**

Affiliation does not transfer ownership. The code is source available under Platform 1.0; avoid describing the entire release as unrestricted open source or as licensed wholly under CC BY. Dataset, dependency, architecture, model-artifact and whole-archive rights are not implied by the scoped grants.

`Study/provenance/EDITION_CHANGES.md` and its JSON counterpart include the sentence “Private owner review required before public distribution.” Clarify the current publisher workflow without rewriting the historical record as a new decision:

> The publisher's public release remains subject to owner review. This does not limit reuse permitted under the adopted CC BY 4.0 grant.

Place this clarification in current `START_HERE.md` or `RIGHTS.md` guidance; keep dated preparation/review records unchanged when retaining them as historical evidence. This is an explanatory clarification, not a new adoption gate. CC BY already permits sharing and adaptation under its conditions and prohibits added downstream restrictions. Its official legal text is listed under Sources below.

Earlier grants remain applicable to inherited expression. The current code map positively identifies two inherited v0.9.5 expression records comprising three matching blocks. The report inheritance record has an empty `matches` list; do not claim that specific reused report passages were positively identified.

## Recommended release body

The following is replacement copy for the draft. Retain the draft/private label only while it remains true. Before publication, insert verified evidence links for the final selected revision; no commit or receipt URL has been invented here. The verification paragraph is deliberately an instruction to readers, not an unverified claim that corrected future assets already passed.

```markdown
# Q-Pathformer Study v0.4 — Routing and Circuit Contribution

**Draft for owner review · Study · Documentation · Code**

Q-Pathformer v0.4 asks what shallow quantum-circuit models contribute when the same routing choices are also available to conventional models. This release brings the completed study into Q-Pathformer Classical Research, repository edition v1.0.

The local study compared nine model-and-routing combinations on two independent circle populations and a rotated ellipse. All 54 development and 135 confirmation endpoints completed their registered training budgets.

## Main finding

Spatial k-means routing improved the two-qubit, depth-two circuit model (Q2) over its hash-routing control. Averaged over five training seeds, Q2 k-means reached macro-F1 of **98.32% on circle population 1, 97.16% on circle population 2 and 94.41% on the rotated ellipse**.

**The classical controls remained stronger.** Global MLP and trigonometric models achieved higher mean F1 and lower binary cross-entropy (BCE; lower is better) on every confirmation population. Routed trigonometric models also had lower BCE than routed Q2. Q2's lower mean BCE than the small routed MLP was not established by the adjusted paired-seed intervals.

These results support a spatial-routing benefit for the tested circuit recipe without isolating a circuit-specific advantage. The evidence comes from controlled synthetic tasks, five training seeds and unequal model capacities. BCE is the primary endpoint; the report explains the separate seed and record-bootstrap uncertainty summaries.

## Choose a download

Download each ZIP you need with its matching `.seal.json`, extract it once and open `START_HERE.md`.

| Package | What it contains |
| --- | --- |
| `QPathformer_v0.4_Study.zip` | The preserved PDF and Word report, an edition note, report rights and provenance. |
| `QPathformer_v0.4_Documentation.zip` | The study overview, research guide, original guidance and reproduction boundaries. |
| `QPathformer_v0.4_Code.zip` | Selected unchanged scientific implementation, dependency information and bounded startup/verification tools. |

The report preserves the original findings, tables, figures and conclusions. This release adds packaging and explanation; it does not add experiments. Study v0.4 is separate from repository edition v1.0, and no ETEL implementation is supplied.

## Verification and reproduction

The packages include inventories and matching external seals. Follow `VERIFY.md` before running the Code quickstart. Seals are integrity records, not digital signatures.

Bounded startup checks in-memory predictions, CLI help and a circuit-matrix invariant. It does not reproduce training, install a clean environment, score the official data, sample quantum shots or submit hardware jobs. Full replay requires the separately retained archive, including data, checkpoints and gate records omitted from these downloads.

The original local-readiness work covered 45 circuit checkpoints and included 737,280 simulated Aer measurement shots. Separate conditional binomial diagnostics are detailed in the report. No physical-QPU execution or quantum advantage is reported, and illustrative noise is not current device calibration.

## Rights

The identified original report content and explanatory prose are licensed under **CC BY 4.0**. Selected Python source and package helpers are **source available under Q-Pathformer Platform License 1.0**. Each package includes its adopted scope; excluded material retains its separate terms.

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.
```

Do not duplicate the heading in GitHub if the title field already presents it. Link the final study guide, package index and verification/publication record beneath the relevant paragraphs. Keep integrity counters, raw hashes and revision-by-revision explanations in those records rather than adding them to the release introduction.

When the draft becomes a published release, update the current status wording and publication receipt together. Repository visibility is a separate action. Preserve the user's existing intention that `study-v0.9.5` remains Latest; verify the live setting rather than inferring it from tag names. GitHub documents separate draft/publish and Latest controls.

## Evidence established by this review

### Package integrity and provenance

The independent audit completed 1,158 checks without a failure. It checked safe single-root ZIP members, CRCs, regular unencrypted files, exact/case-folded path uniqueness, complete internal inventories, every size/hash, source-map bindings and all 54 selected source records. All 31 packaged JSON records parse without duplicate object keys, and all 35 active local Markdown file links resolve.

Detailed inventories contain 75 Code files, 19 Documentation files and 18 Study files. Code has 50 Python files: 48 retained scientific/source files and two package helpers. These audit counts belong here, not in the public release narrative.

Code records preparation in `draft_20261029_r2`; Documentation and Study retain `draft_20261029`. Their records are consistent. Different revision suffixes do not require reassembly solely for uniform naming. All recorded final build roots are beneath `C:\Q2`. The Linux review environment cannot directly inspect that Windows filesystem.

The original-archive references identify 19,263 payload files and 1,204,159,807 logical payload bytes, plus a 4,529,463-byte delivery manifest. Those are retained-archive accounting figures, not download sizes, RAM requirements or tested hardware minimums. The full archive and delivery manifest were not supplied for a fresh scan in this review.

### Report preservation and presentation

The independently retained original report has SHA-256 `54ffcb4182d61471865ac457aa4da8647aa309f339709334252ba7dbf0e48a52`. Comparison against the current DOCX confirms all 185 original non-section body elements as an exact canonical-XML prefix, all 31 tables unchanged and all four embedded PNG figures byte-identical. Only the document body and application/core metadata parts changed; the edition adds its note/page break.

The supplied PDF has 40 pages. Every page was visually inspected, with no observed clipping, overlapping content, broken tables, missing figures or broken glyphs. The independently rendered DOCX also has 40 pages, and the whitespace-normalized text matches the supplied PDF page by page. This is not a claim of pixel-identical rendering. The PDF is not encrypted and has no embedded attachments.

Historical internal labels, source paths and future-study recommendations are explained by the appended edition note. The remaining historical DOCX keywords/timestamp are optional cataloguing housekeeping, not a reason to reissue the report. No presentation erratum was found.

### Genuine runtime checks and their limits

In Python 3.12.14 with NumPy 2.3.5 on Linux, all 50 selected Python files parsed, the current package verifier passed, and the actual startup helper completed all three checks. The numerical check produced finite, bounded predictions for all nine model variants. The selected unit test compared full circuit matrices on its generated fixtures. Existing-receipt and inside-package-output rejection checks also behaved as intended. The original extracted package's complete path/hash snapshot was unchanged afterward.

The dependency inventory matches all 357 top-level-module/file pairs in retained scientific source. It does not include the two helpers' 13 standard-library module/file pairs. As minor housekeeping during the helper revision, include those pairs or explicitly label the inventory as retained-source-only. This is not evidence of a missing third-party dependency.

No training, optimizer update, official-data scoring, shot sampling, noise experiment, dependency installation or QPU submission ran during this review. The original exact binomial/bootstrap replay requirements, including its recorded NumPy version, remain distinct from this bounded startup. This Linux receipt does not replace the publisher's final Windows startup or authenticated-download binding.

A targeted scan of all 112 extracted files, including report text/XML, found no matches for the recognized private-key, GitHub-token, AWS-access-key or OpenAI-key patterns checked. This is a limited content screen, not an exhaustive security or ownership certification.

## Focused acceptance checks for Codex

Complete the existing authorized packaging work before presenting a final publication decision:

1. Correct both helpers and the v0.4-only guidance. Preserve the 48 retained scientific files and report bytes.
2. Demonstrate that the valid package passes, duplicate manifest/checksum paths fail, and changed or unexpected files fail integrity verification before scientific imports.
3. Demonstrate that an existing or concurrently claimed receipt is preserved. Test the previously reproduced collision, not only the initial `exists()` case. Keep simulated probes clearly separate from genuine startup receipts.
4. Confirm that package changes during startup prevent a PASS and that failures/timeouts produce a failure result without overwriting evidence.
5. Rebuild affected packages from the new `C:\Q2` revision, update the necessary scopes/inventories/seals, and recheck the final extracted bytes.
6. Run genuine bounded startup on the exact final Code ZIP in the intended compatible environment; bind the receipt to its final ZIP/seal identities. Full scientific retraining is not needed for these packaging edits.
7. Compare the authenticated downloaded release assets to the selected local package index. Record actual target commit/tag, draft/publication state and Latest setting. Keep visibility unchanged unless separately instructed.
8. Use the simplified release body with verified final evidence links. Preserve historical sealed artifacts and earlier adopted grants.

After these checks, the remaining step is the owner's existing release workflow, not a new scientific validation campaign or a repeat licensing decision.

## Appendix — exact attachments reviewed

These identify the supplied review inputs. If Codex rebuilds a package, record its new identity separately and do not copy these hashes onto changed bytes.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `QPathformer_v0.4_Code.zip` | 224,507 | `94c2cbe8c79bd09640f2bdb44f1e2d96318d8192e08cb4c9abf7b3f6a9b03912` |
| `QPathformer_v0.4_Code.seal.json` | 1,366 | `03bd49549266c0f6eac77628061a2b83ac1ed6de2b9aa5c7a476c4aa59dcf5e0` |
| `QPathformer_v0.4_Documentation.zip` | 34,928 | `c9501ddd0f9bdca31dbcf069ec37261f6abcac9dab9642d1ab00e7ef7e126a7e` |
| `QPathformer_v0.4_Documentation.seal.json` | 1,429 | `4c497dcc9833bf43ca8f374efb4c2a5cb7d80f1679613ea62ca740fb97a30a13` |
| `QPathformer_v0.4_Study.zip` | 1,791,206 | `772483cd5575998473a6383959d39fa6edc89ae143d3770a8feee174a63d249b` |
| `QPathformer_v0.4_Study.seal.json` | 1,367 | `87bda71531713e97617e8045f723df4a02216652a42902913b54e51900ca77b6` |

Current report identities:

- DOCX: 834,465 bytes; SHA-256 `2e4cccb07f7753dc80fda7b410ce6b68f8b67737148591647d6fdf2eb9209d5f`.
- PDF: 1,345,176 bytes; SHA-256 `471cec4475e5c2a9d26591054fbee9dc19e9554c010ba272f8bba6abeef3a45f`.

## Sources and audit trail

The primary evidence is the attached packages identified above, especially the following paths inside their single roots:

- Documentation: `RELEASE_NOTES.md`, `RESEARCH_GUIDE.md`, `REPRODUCIBILITY.md`, original historical guidance and the included governance protocols.
- Study: both report formats, `provenance/EDITION_CHANGES.*`, `provenance/REPORT_REVIEW.json`, `REPORT_LICENSE_SCOPE.json` and `INHERITED_REPORT_EXPRESSION.json`.
- Code: `tools/startup_check.py`, `tools/verify_package.py`, `QUICKSTART.md`, `VERIFY.md`, `DEPENDENCY_INVENTORY.json`, model/circuit/test source and the source-selection/inheritance records.
- All packages: `LICENSE_ADOPTION.json`, relevant license scopes, source maps, internal manifests/checksums and matching external seals.

Independent review intermediates were retained beneath `/workspace/scratch/c9c666df41fc/tmp/v04_release_review_20261029/`: attachment identities; integrity and rights receipts; scientific preservation/arithmetic checks; genuine runtime receipt and explicitly labelled control probes; report render/page comparison and visual checklists. These are review evidence, not replacement publisher receipts.

External references used for licensing/publication interpretation:

- [CC BY 4.0 official legal text](https://creativecommons.org/licenses/by/4.0/legalcode.en), particularly sections 2 and 3 on granted rights, downstream restrictions and attribution.
- [GitHub: Managing releases in a repository](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository), including draft/publish, asset and Latest controls.

No uploaded package, original report, scientific source, license decision or GitHub release was modified by this review.
