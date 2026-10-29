# Q-Pathformer Study v0.1 — Local Benchmark and IBM Readiness

**Draft for review · Private repository · Study · Documentation · Code**

This draft brings the completed v0.1 study into **Q-Pathformer Classical Research, repository edition v1.0**. It is available for owner review; [study-v0.9.5](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.9.5) remains the latest published study release.

The study explored input-dependent computation in two separate settings: small simulated quantum circuits and a classical text classifier with shared or content-routed adapters. These comparisons established baselines for later work on depth and routing.

## Downloads

Download the three ZIPs and their matching `.seal.json` files from this release’s Assets section. Extract each ZIP once and open `START_HERE.md`. The seals record file integrity; they are not digital signatures.

| Package | What it contains |
| --- | --- |
| `QPathformer_v0.1_Study.zip` | Review editions of the report in PDF and Word, with updated author metadata, an edition note and the report-content rights proposal. |
| `QPathformer_v0.1_Documentation.zip` | Study overview, research guide, reproduction boundaries and source evidence. |
| `QPathformer_v0.1_Code.zip` | Selected circuit, classical neural-network, text-routing and offline-readiness code, with dependency details and a startup guide. |

## What the study found

The original v0.1 work includes a prototype capsule and a later full benchmark. The completed benchmark contains **45 synthetic training runs**, **ten AG News method results across five paired seeds**, and local readiness checks of **30 trained circuit checkpoints**. The two text methods reused the same warm-up within each seed. This study selection contains **no ETEL component**.

On the radial classification task, the scheduled circuit underperformed both a classical neural network given the same input information and the fixed four-layer circuit. The neural-network comparison matched available input information, not parameter count or computational cost. Shared and content-routed text adapters produced similar AG News results; uncertainty intervals for their paired difference included zero. These findings do not establish equivalence or quantum advantage.

“IBM readiness” refers to the study’s local circuit-translation and simulator checks. The trained-checkpoint readiness audit used **3,686,400 simulated shots**, with **zero physical shots or hardware jobs**. These historical checks do not establish qualification for a currently selected IBM device.

[Study summary and limitations](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/dd21b848be5e9adac371379a0deb1f70e9307357/release_preparation/study-v0.1/documentation/release_notes/study-v0.1.md)

## Report and rights review

The report candidate preserves the study’s scientific content and results, updates presentation labels and author metadata, and explains the original report’s historical publication recommendation in an edition note.

The v0.1 review proposes **CC BY 4.0** for identified original report content and selected new explanatory prose, and the unchanged **Q-Pathformer Platform License 1.0** for the selected Python files. **These proposals are not adopted.** Earlier grants remain in force within their existing scopes, including already-licensed expression wherever reused. No dataset, dependency, model, architecture-document or whole-archive grant is implied.

[Exact scope proposals and supporting records](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/dd21b848be5e9adac371379a0deb1f70e9307357/release_preparation/study-v0.1/README.md#rights-decisions-for-review)

## Verification and reproduction

All three ZIPs passed seal, inventory and fresh-extraction checks. The recorded Windows startup check covers imports, CLI entry points, selected non-training tests and a local circuit compilation/matrix comparison. These package-startup checks did not run training, optimizer updates, shot sampling, dependency installation or QPU submission. They do not establish full study reproduction or fresh-install portability.

The separately retained benchmark archive totals approximately **9.18 GB of logical file content**, including its delivery manifest, according to the retained source-verification record. These downloads exclude raw datasets, trained checkpoints, installed environments and the full archive. Storage accounting is not a hardware or RAM minimum.

[Startup receipt](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/dd21b848be5e9adac371379a0deb1f70e9307357/release_preparation/study-v0.1/QPathformer_v0.1_Code.startup.json) · [Package verification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/dd21b848be5e9adac371379a0deb1f70e9307357/release_preparation/study-v0.1/FRESH_PACKAGE_VERIFICATION.json) · [Original draft upload record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/dd21b848be5e9adac371379a0deb1f70e9307357/release_preparation/study-v0.1/DRAFT_RELEASE.json) · [Retained archive verification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/dd21b848be5e9adac371379a0deb1f70e9307357/release_preparation/study-v0.1/FROZEN_SOURCE_VERIFICATION.json)

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.
