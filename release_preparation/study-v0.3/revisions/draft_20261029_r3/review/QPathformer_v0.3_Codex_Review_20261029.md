# Q-Pathformer Study v0.3 release review and Codex notes

**Draft inspection notes · 29 October 2026 · Australia/Sydney**  
**Subject:** Q-Pathformer Study v0.3 — Shallow Circuits and Routing  
**Reviewed inputs:** the supplied release-page text and all six attached ZIP/seal assets.  
**Companion evidence:** `QPathformer_v0.3_Inspection_Receipt_20261029.json`.

The attached assets pass the integrity checks performed here. All six SHA-256 values match the supplied release text, all three ZIPs match their seals, and all 112 packaged files match the internal inventories. The supplied Code verifier and bounded startup also pass on the unmodified extraction. No scientific result discrepancy was found between the release's quoted F1 scores and the report.

The review identified two Code packaging issues to address: the internal verifier silently accepts a duplicate checksum row, and the PowerShell quickstart does not explicitly stop between a failed verification command and startup. The release summary should also identify BCE as the primary metric and distinguish historical study verification from release-packaging checks. These are inspection findings and proposed changes, not publication approval or a fresh scientific replication.

## 1. What was independently checked

| Package | ZIP bytes | ZIP files | Manifest entries | Checksum entries | Source-map entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| Code | 202,363 | 75 | 73 | 74 | 72 |
| Documentation | 33,759 | 19 | 17 | 18 | 16 |
| Study | 1,703,511 | 18 | 16 | 17 | 15 |
| Total | 1,939,633 | 112 | 106 | 109 | 103 |

The different entry counts are intentional. Each manifest excludes itself and `CHECKSUMS.sha256`; each checksum inventory excludes itself; each source map excludes those two generated files and itself. The external seals bind the manifest, checksum inventory and source map by size and SHA-256. No circular self-hash is required.

Checks completed:

- Recomputed all six asset hashes, each ZIP size, and the three internal identities named by each seal.
- Checked ZIP CRCs, exact root and membership, duplicate and case-colliding member names, unsafe paths, symlink entries and encrypted members. None were found in these ZIPs.
- Checked every manifest/checksum entry against actual bytes, with exact coverage and no missing or unexpected members. The reviewed JSON files contain no duplicate object keys; the current inventories contain no duplicate paths.
- Checked all 103 source-map entries against the packaged files and their recorded `source_identity` values. This establishes internal consistency; the original `C:\Q2` source archives were not available for an independent source-to-package comparison.
- Checked the exact scope identities for 49 Python files, 23 guidance-file instances and two report files. The 49 Python entries cover 47 scientific/source files and two package helpers.
- Checked all four DOCX embedded-image identities and the two report identities in `provenance/REPORT_REVIEW.json`.
- Confirmed that the adoption record and both licence texts are byte-identical across the three packages. The two inherited scope records match the identities in the Code inheritance map, and all seven cited inherited-scope entries resolve. This is a document/identity check, not an ownership or enforceability assessment.
- Opened all 22 PDF pages individually. No obvious clipping, overlap, broken glyphs or unintended blank pages were observed. Inspected DOCX structure and metadata; an independent Word render was not performed.
- Ran the supplied internal verifier: `PASS`, 75 files. Ran the supplied startup helper: `PASS`, three checks. All extracted files remained byte-identical afterward.

The startup checks parsed the 49 Python files, produced finite in-memory predictions for all 13 methods, displayed training CLI help, and passed the selected circuit-versus-matrix invariant. They performed no optimizer updates, official-data scoring, shot sampling or QPU execution.

**Review environment:** Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0 on Linux. Qiskit and Aer were absent and no dependencies were installed. The study records NumPy 2.5.4 and SciPy 1.18.1. This successful startup is therefore a bounded compatibility observation, not exact-version historical replay or verification of every optional dependency.

Three negative controls on disposable copies were correctly rejected: deleting `START_HERE.md`, changing one byte in it without changing its length, and adding an unexpected file. The separate duplicate-checksum probe below exposed a narrower verifier limitation.

## 2. Code packaging findings

### C01 — Reject duplicate inventory paths explicitly

**Priority:** medium; recommended packaging correction.  
**Source:** `QPathformer_v0.3_Code/tools/verify_package.py`, lines 8 and 12; the duplicate-path rule in `VERIFY.md`.

Both inventory readers construct dictionaries directly. Repeated paths can overwrite earlier entries silently. In a disposable copy, appending an exact duplicate of the first line to `CHECKSUMS.sha256` still produced exit code 0 and `{"status":"PASS","files":75}`. The original checksum inventory's external-seal identity correctly failed against the modified copy.

This does **not** invalidate the supplied assets: their inventories contain no duplicates, and the full seal-first workflow detects the change. It does mean the standalone helper does not itself enforce all of the duplicate-rejection behavior described in the verification guidance.

**Proposed Codex change:** parse entries sequentially, reject a repeated path before creating a mapping, and use an explicit exception rather than `assert`. Apply this to both manifest records and checksum lines. Keep the external ZIP/seal and safe-extraction checks as separate required parts of the workflow; an internal helper's `PASS` is not publisher authentication.

**Acceptance evidence:** the original extraction passes; identical and conflicting duplicate checksum paths fail; duplicate manifest paths fail; the existing missing/changed/unexpected-file controls continue to fail. These tests belong on temporary copies, with the originals preserved.

### C02 — Make the PowerShell quickstart stop on verification failure

**Priority:** medium; recommended packaging correction.  
**Source:** `QPathformer_v0.3_Code/QUICKSTART.md`, lines 5–8; `tools/startup_check.py`, which does not call the package verifier.

The snippet places two native Python commands on consecutive lines without checking the first exit code. Under ordinary PowerShell defaults, a nonzero native exit does not by itself guarantee that subsequent statements stop. Consequently, a pasted block can proceed to startup after an integrity failure. This is a static review finding, grounded in Microsoft's PowerShell documentation; PowerShell was not installed in this review environment.

**Proposed replacement snippet** after the separately documented external-seal and safe-extraction checks:

```powershell
& {
    & $Python -B tools/verify_package.py
    if ($LASTEXITCODE -ne 0) {
        throw "Package verification failed; startup was not run."
    }

    & $Python -B tools/startup_check.py --output ..\QPathformer_v0.3_Code.startup.json
    if ($LASTEXITCODE -ne 0) {
        throw "Bounded startup failed; inspect the output and any receipt."
    }
}
```

Codex should validate this in the supported PowerShell environment. A deliberately invalid extraction should stop before startup and create no startup receipt; the unchanged extraction should complete normally. An alternative implementation may make startup perform the internal check itself, while retaining the outer seal verification.

Primary technical reference, checked 29 October 2026: [Microsoft Learn — PowerShell preference variables](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables?view=powershell-7.5#psnativecommanduseerroractionpreference). This reference supports shell behavior only and has no authority over study or publication decisions.

### Optional cleanup during the same Code revision

Remove the irrelevant “v0.2 also checks a small CPU text forward” sentence from the v0.3 quickstart and make the startup receipt's scope specific to the checks actually executed. The current package has no classical-text subtree and correctly ran only the three v0.3 checks. Recording the imported NumPy version and parsed-file count in future receipts would also make their scope easier to inspect. These are secondary improvements, not failures of the current startup result.

## 3. Release-text findings

### R01 — Include the registered primary metric

The F1 values in the draft are correct, but the release omits the primary BCE result. `payload/study/governance/ANALYSIS_PROTOCOL.json` and report pages 10–11 identify BCE as primary, with macro-F1 and accuracy secondary.

For k-means versus hash routing, the report gives mean BCE 0.1897 versus 0.2897: a paired difference of −0.1000. The Bonferroni-adjusted 98.333% seed interval is [−0.1232, −0.0769]; the separate conditional record-bootstrap interval is [−0.1139, −0.0873]. Both lie below the registered −0.01 practical threshold. The +7.32 percentage-point F1 difference is secondary and descriptive. Report these as historical study findings rather than recomputed results from this inspection.

The following table is transcribed from report page 6. Values are mean ± sample SD over five training seeds; these SDs are not confidence intervals.

| Confirmation method | Test BCE, lower is better | Macro-F1, % |
| --- | ---: | ---: |
| K-means routed depth two | 0.190 ± 0.013 | 97.42 ± 0.24 |
| Hash-routed depth two | 0.290 ± 0.000 | 90.10 ± 0.12 |
| Fixed depth four | 0.267 ± 0.028 | 94.06 ± 2.03 |
| Classical MLP 41 | 0.077 ± 0.017 | 96.42 ± 0.85 |
| Classical MLP 129 | 0.027 ± 0.002 | 98.70 ± 0.20 |

The smaller MLP's lower F1 but better BCE is worth retaining in the report context. Avoid a general claim that the routed circuit outperformed classical models. The report also finds no classical-simulation speed advantage for the circuit model (pages 16–17).

### R02 — Separate historical evidence from packaging verification

The historical study includes Aer simulated measurements and probability-level binomial analysis. The later statement that “shot sampling ... was not performed” refers to the packaging check, but its subject is not explicit enough. Prefix that sentence with **“During release packaging”** and describe the 65-endpoint replay as **historical independent replay**.

Also explain that 104,000 predictions means 65 checkpoints × 1,600 common test records. It does not mean 104,000 independent test cases. The 150 saved binomial count arrays and the 150 local-readiness circuits describe different analyses (report pages 18–19).

Retain the development threshold failure and the pre-confirmation verification amendment. The report records zero ambiguous confirmation predictions under the specified numerical band; that does not mean zero classification errors or zero uncertainty.

### R03 — Resolve the pasted asset sizes without changing valid assets

All six pasted hashes match. The pasted sizes do not: for example, the Code ZIP is 202,363 bytes, approximately 197.62 KiB; Documentation is 33,759 bytes, approximately 32.97 KiB; Study is 1,703,511 bytes, approximately 1.625 MiB. The seals are approximately 1.33–1.40 KiB each.

The repeated leading “1” in the pasted display may be a UI/copy artifact, but its origin was not established. Check the raw release body and GitHub asset metadata. Do not regenerate a correct ZIP merely to match a pasted size. Use exact bytes in receipts and let the release interface display its own human-readable sizes.

The pasted GitHub footer and the trailing corrupted text are not release prose. Remove them only if they actually entered the saved release body; their presence in this chat paste alone does not establish a repository defect.

### R04 — Confirm the private receipt links in the repository context

The exact supplied `receipts/FRESH_PACKAGE_VERIFICATION.json` link at commit `dbcfe6cb00fdfd439f174059666c2dfb5fec71f1` returned GitHub API 404 through the connected account. That can reflect access or resource resolution; it is not proof that the private link is broken.

Therefore this review did not verify the live draft, current remote asset downloads, repository visibility, `study-v0.9.5` Latest status, or the authenticated-download receipt at commit `c3db98ebf7d03bad20c934716e53f6cc46cbde33`.

Codex should resolve the supplied links in its authorized repository context, compare the downloaded asset identities with this note, and confirm that the receipts bind those exact identities. The draft links to both root-level `PACKAGE_INDEX.json` and `receipts/PACKAGE_INDEX.json`; confirm that both exist and agree, or use one canonical index link. Different commits for preparation evidence and a later download receipt can be intentional and should not be silently flattened into one commit.

## 4. Suggested replacement release paragraphs

The title, three-download table, scoped-licensing language and author attribution can remain. The following passages are proposed edits for the scientific and verification portions of the release, subject to the repository checks above.

> The historical study completed all 104 registered training runs: 39 development and 65 confirmation. All 13 methods continued to five-seed confirmation on fresh synthetic circle data, using the same 1,600 held-out test records. All circuit execution was simulated on classical compute.
>
> Binary cross-entropy was the primary metric. K-means routed depth-two circuits achieved mean BCE 0.1897, compared with 0.2897 for hash routing using the same 40 circuit angles. The paired BCE difference was −0.1000, with a Bonferroni-adjusted 98.333% seed interval of [−0.1232, −0.0769]. Secondary mean macro-F1 was 97.42% for k-means routing, 90.10% for hash routing, 94.06% for fixed depth four and 98.70% for the larger classical MLP. Spatial routing improved the circuit model on this task while adding classical partitioning capacity; the larger MLP remained strongest on both metrics.
>
> Historical independent replay checked 65 endpoints, 104,000 checkpoint–record predictions and 150 saved binomial shot-count arrays. The prediction count reuses the same 1,600 test records. A development numerical-threshold audit failure and the verification-only pre-confirmation amendment remain documented; confirmation had no predictions inside the specified ambiguity band. Separate local Aer checks used 150 circuits and 3,840,000 simulated measurement shots. Neither analysis was QPU execution or device-noise simulation.
>
> One synthetic task and five confirmation training seeds do not establish quantum advantage or real-domain generalization. The report retains the classical controls, uncertainty qualifications and limitations.
>
> During release packaging, the publisher recorded `PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP`. That check did not rerun the training study, full scientific replay, shot sampling or QPU jobs, and did not establish installation from scratch. The downloads omit datasets, checkpoints, complete operational archives, installed environments and credentials. No ETEL component is supplied.

Use the publisher's status string only after confirming its linked receipt. The independent startup result from this review is separately recorded as `PASS` with three checks; it should not be substituted for the publisher's receipt.

For readers downloading the report alone, consider adding this sentence to the release body: **“The report preserves historical internal labels and full-archive paths; the accompanying package guidance defines what these curated downloads include.”** Report page 21 references evidence directories and `Verify_Delivery.ps1` from the retained full archive. Their absence from the curated downloads is disclosed, not an accidental incomplete extraction.

## 5. Preserve these distinctions

- Study v0.3, report edition 1 and repository edition v1.0 are distinct identifiers. The attached report has 21 historical pages plus its edition-note page.
- The Study and Documentation seals record `draft_20261029`; the Code seal records `draft_20261029_r2`. That is internally consistent with their source maps and can represent unchanged reuse. It is not itself a reason to re-seal the first two packages.
- The provided licence records say `ADOPTED`. Preserve the separation between scoped licensing and later release publication, together with existing grants and exclusions. Presence of both licence texts does not apply both licences to all package contents.
- The inherited v0.9.5 scope lists ETEL files as historical provenance. Those records do not mean ETEL implementation is included in this v0.3 Code payload.
- A hash match establishes byte identity relative to the supplied record. The seals correctly state that they are not digital signatures.
- Preservation of the original historical report body and source code is recorded by the publisher. This inspection checked the packaged identities but could not independently compare against the unavailable original DOCX or full source archive.

Optional next-edition metadata cleanup: the Word package still records `Pages=1`, zero word/character counts, the old modified timestamp, and an `IBM readiness` keyword. The PDF has 22 pages and the appropriate edition metadata. These stale Word properties did not affect the observed PDF layout or quoted findings; do not describe them as a scientific error or rewrite the historical report solely to modernize labels.

## 6. Codex handoff and acceptance evidence

1. Record this review against the exact six input assets below. Keep the current sealed candidate and historical report/source material intact.
2. Prepare the C01 verifier correction and C02 quickstart correction in a new working revision. Keep scientific source, protocols, numerical thresholds, training budgets and results unchanged.
3. Run the narrow duplicate-inventory and stop-on-failure checks described above, plus the existing bounded startup. Use fresh extraction directories and external receipt paths.
4. Prepare the R01/R02 release-body changes. Resolve R03 against actual remote metadata and R04 against the authenticated repository receipts.
5. If a Code-package file changes, update the affected code/guidance scope identities, source mapping, manifest and checksums under the existing documented licensing scheme; then create a new Code ZIP and external seal. Retain the predecessor identities and show the exact changed-file list.
6. Reuse byte-identical Study and Documentation assets with their existing seals. Update release-level package indexes, verification receipts and any new draft-download receipt to reference the chosen asset set. A release-body-only edit does not change archive bytes and does not require re-sealing them.
7. Return a reviewable revision summary: findings addressed or deferred with reasons, old/new asset identities, bounded verification results, authenticated link checks and remaining evidence limitations. Keep publication, visibility changes, tag/Latest changes and additional experiments outside this review handoff.

No new training, QPU execution, ETEL integration or licensing redesign is needed to resolve these findings.

## 7. Exact reviewed asset identities

| File | Exact bytes | Result |
| --- | ---: | --- |
| `QPathformer_v0.3_Code.seal.json` | 1,366 | Matches pasted SHA-256 |
| `QPathformer_v0.3_Code.zip` | 202,363 | Matches pasted SHA-256 and seal |
| `QPathformer_v0.3_Documentation.seal.json` | 1,429 | Matches pasted SHA-256 |
| `QPathformer_v0.3_Documentation.zip` | 33,759 | Matches pasted SHA-256 and seal |
| `QPathformer_v0.3_Study.seal.json` | 1,367 | Matches pasted SHA-256 |
| `QPathformer_v0.3_Study.zip` | 1,703,511 | Matches pasted SHA-256 and seal |

```text
cb8f240b8883f3c4aaa5c7ec6977964cc8accbbd4a348c436291ff2961f62422  QPathformer_v0.3_Code.seal.json
a3f830709d73f02347f9eca3f7ac93bfe1d2b5c7264033e5bcfb50307d7ee535  QPathformer_v0.3_Code.zip
7f9b0cc08dcc18364a553ffdff7353a7cf1f322ba5b427bc950fc6b8d1cdd9e0  QPathformer_v0.3_Documentation.seal.json
e7b9bfd9ef535113c33c3438c75d7d11c12fca09b143d53ae32cd268b8ed38a5  QPathformer_v0.3_Documentation.zip
369cc3e7135fe4e6de150bcaa262ae6e8b927b0ee3d1fc811d6f891308e15607  QPathformer_v0.3_Study.seal.json
f2a27d4e8c24754cade334fbd0121c698f2f368b4d55be83ecac2ede33a6fa98  QPathformer_v0.3_Study.zip
```

## 8. Evidence classification

The attached files and this inspection receipt are direct evidence for byte-level and bounded-startup observations. The historical report and packaged protocols are primary project records for the reported scientific claims, but their full results were not independently reproduced here. Publisher preservation and licensing records were checked for internal identities and consistency; unavailable upstream material remains unverified. The supplied GitHub URLs are unresolved external evidence in this review. Microsoft's documentation is a primary technical reference for PowerShell behavior only.

This review applies the project's ID_3 inspection posture: findings are traceable observations and draft recommendations. Integrity, completeness and a successful startup do not establish scientific replication, certification, legal sufficiency or operational readiness. No supplied asset, repository file or release state was changed.
