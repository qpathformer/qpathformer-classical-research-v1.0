**Draft for owner review · Private repository · Study · Documentation · Code**

Q-Pathformer v0.5 examines how learned output heads change shallow circuit classifiers when compared with strong classical controls. Eleven recipes were evaluated on two independently generated circle populations and a rotated ellipse, using five paired training seeds and one fixed split per confirmation population. All circuit execution used classical compute.

This completed study is presented in **Q-Pathformer Classical Research, repository edition v1.0**. Study v0.5 and repository edition v1.0 are separate identifiers. All **66 development and 165 confirmation endpoints** completed **200 rounds and 15,000 optimizer updates per endpoint**, following 22 short engineering endpoints.

### Historical findings

**Common clipped binary cross-entropy (BCE) was the primary endpoint; lower is better.** These are means over five confirmation training seeds. Macro-F1 is secondary.

| Recipe | Mean common clipped BCE: circle 1 | Circle 2 | Rotated ellipse |
| --- | ---: | ---: | ---: |
| Legacy | 0.22279 | 0.17937 | 0.21335 |
| Scalar | 0.01362 | 0.01676 | 0.02599 |
| Multi | 0.01315 | 0.01298 | 0.02096 |
| Trig25 routed | 0.01054 | 0.01201 | 0.01399 |

The learned-readout recipes substantially improved on the same-study Legacy recipe. Scalar changes the probability link, head parameters, capacity and native training loss together, so this comparison does not isolate the readout's contribution. Five-moment Multi adds a smaller, task-dependent benefit over Scalar: both circle adjusted seed intervals include zero; the ellipse loss reduction is below the registered 0.01 practical reference. The random frozen-core control performed substantially worse.

Scalar reached mean macro-F1 of **99.06–99.54%**, and Multi reached **99.29–99.55%** across these populations. Those small F1 differences do not establish general superiority of five moments.

**Strong classical controls remain central to the result.** Routed Trig25 had the lowest mean common clipped BCE on all three confirmation populations. Its advantage over Multi was unresolved by the adjusted seed intervals on the circles and resolved on the ellipse. Trig25 controls combined high mean accuracy with much lower measured local execution time than the circuit recipes. These are measurements of the retained CPU implementations, not general hardware-efficiency or monetary-cost claims.

The twelve registered primary contrasts use **99.5833% Bonferroni-adjusted paired-seed intervals**. The separate 10,000-resample record bootstrap conditions on the trained models; it does not add training replications. These uncertainty sources remain separate.

### Historical verification and limitations

Historical independent replay checked saved states, predictions, selected checkpoints and statistics; it did not repeat every optimizer update. Local readiness covered **60 selected circuit checkpoints** and **1,474,560 simulated Aer measurement shots**. Separate conditional multinomial diagnostics are documented in the report. No physical shots or hardware jobs are reported; illustrative noise is not device calibration.

These results concern small synthetic classifiers, fixed routers and unequal capacities. The ellipse changes the label boundary under the same uniform input distribution; it is not an out-of-distribution benchmark. Five training seeds and one fixed split per population do not establish broad task or real-world generalization. Historical scores from earlier studies provide context, not paired improvement evidence. No physical-QPU result, quantum advantage, ETEL implementation or full language-model benchmark is supplied.

Reported training-loop times are elapsed wall times under concurrent CPU workers, including validation and evidence writes. They are not process CPU seconds, isolated hardware benchmarks, energy estimates or cloud costs. The 97% validation milestone was diagnostic; all runs completed their full budgets, so no early-stopping saving was measured. The report's exact learned-logit representation is a historical research direction, not deployment benchmarking of a newly compiled evaluator.

### Downloads and release-packaging checks

Download each ZIP with its matching `.seal.json`, verify the external seal and safe extraction, then open `START_HERE.md`.

| Download | Contents |
| --- | --- |
| `QPathformer_v0.5_Study.zip` | The preserved report in PDF and Word, edition note, rights scope and provenance |
| `QPathformer_v0.5_Documentation.zip` | Research guide, original guidance, historical findings and reproduction boundaries |
| `QPathformer_v0.5_Code.zip` | Selected scientific sources, dependency inventory and bounded verification/startup helpers |

[Exact package identities](PACKAGE_INDEX.json) identify the selected ZIP/seal pairs and actual build origins. Current helper and guidance corrections require refreshed package records; the scientific source, report and historical records are preserved.

**Release-packaging verification is separate from the historical study.** The bounded startup helper checks package integrity before scientific imports and after its checks, parses all 52 selected Python files, imports the selected numerical modules and runs two selected tests: model parameter shapes/paired initialization, and independent circuit-state/moment agreement. It does not run training, official scoring, shot sampling, noise experiments or QPU jobs. Success does not establish a clean installation, every optional dependency or full historical reproduction. Consult the final receipts for the checks performed against the selected assets.

Datasets, checkpoints, installed environments and the complete retained archive are excluded. Full replay needs the separately retained inputs and recorded environment/path bindings. Historical full-archive commands are evidence, not a batch to run in these curated downloads. Seals are integrity records, not digital signatures.

[Fresh extraction and startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Independent package verification](receipts/ROOT_PACKAGE_VERIFICATION.json) · [Report review](report/REPORT_REVIEW.json) · [Source inventory](receipts/SOURCE_INVENTORY.json).

### Scoped licensing

The identified original report content and explanatory prose are licensed under **CC BY 4.0**. Selected Python source and package helpers are **source available under the unchanged Q-Pathformer Platform License 1.0**. Each package includes its adopted scope; applicable earlier grants remain in force and excluded material retains its separate terms. Third-party dependencies, datasets, model artifacts, architecture documents and full archives retain their separate terms; neither licence is a blanket grant for the package. [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative. Anthony remains the licensor; company affiliation does not transfer ownership.

This release remains a draft in the private repository. Scoped licensing is adopted separately from publication. **Study v0.9.5 remains Latest.**
