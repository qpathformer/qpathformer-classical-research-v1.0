# Q-Pathformer Study v0.1 — Local Benchmark and QPU Readiness

**Study · Documentation · Code**

This release brings the completed v0.1 study into **Q-Pathformer Classical Research, repository edition v1.0**. It publishes an earlier study in the series; [study-v0.9.5](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.9.5) remains the latest published study release.

The study explored input-dependent computation in two separate settings: small simulated quantum circuits and a classical text classifier with shared or content-routed adapters. “QPU readiness” means historical local circuit-translation and simulator checks, with no physical-QPU results or qualification for a currently selected device. The retained report uses the historical title “Local Benchmark and IBM Readiness”.

## Downloads

Download the three ZIPs and their matching `.seal.json` files from this release’s Assets section. Extract each ZIP once and open `START_HERE.md`. Seals record file integrity; they are not digital signatures. GitHub’s automatic source-code archives contain the tagged repository tree and are separate from these curated downloads.

| Package | What it contains |
| --- | --- |
| `QPathformer_v0.1_Study.zip` | Final report editions in PDF and Word, author metadata, edition changes and the adopted report-content license scope. |
| `QPathformer_v0.1_Documentation.zip` | Study overview, research guide, reproduction boundaries and source evidence. |
| `QPathformer_v0.1_Code.zip` | Selected circuit, classical neural-network, text-routing and offline-readiness code, with dependency details and a startup guide. |

## What the study found

The original v0.1 work includes a prototype capsule and a later full benchmark. The completed benchmark contains **45 synthetic training runs**, **ten AG News method results across five paired seeds**, and local readiness checks of **30 trained circuit checkpoints**. The two text methods reused the same warm-up within each seed. This study selection contains **no ETEL component**.

On the radial classification task, the scheduled circuit underperformed both a classical neural network given the same input information and the fixed four-layer circuit. The neural-network comparison matched available input information, not parameter count or computational cost. Shared and content-routed text adapters produced similar AG News results; uncertainty intervals for their paired difference included zero. These findings do not establish equivalence or quantum advantage.

The trained-checkpoint readiness audit used **3,686,400 simulated shots**, with **zero physical shots or hardware jobs**. [Study summary and limitations](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/packages/QPathformer_v0.1_Documentation/payload/project/release_notes/study-v0.1.md).

## Report and licensing

The final report edition preserves the study’s scientific content and results, updates presentation labels and author metadata, and explains the original report’s historical publication recommendation in an edition note.

Identified original report content and selected explanatory prose are licensed under **CC BY 4.0**. The selected Python files are source available under the unchanged **Q-Pathformer Platform License 1.0**. Anthony Siljeg adopted these scoped grants on **29 October 2026**. Earlier grants remain in force within their existing scopes, including already-licensed expression wherever reused. No dataset, dependency, model, architecture-document or whole-archive grant is implied.

[Exact adopted scopes and boundaries](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/README.md#licensed-content-and-boundaries) · [Adoption record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/LICENSE_ADOPTION.json).

## Verification and reproduction

All three final ZIPs passed seal, inventory and fresh-extraction checks. The final Code package passed a new Windows startup check covering imports, CLI entry points, selected non-training tests and a local circuit compilation/matrix comparison. These package-startup checks did not run training, optimizer updates, shot sampling, dependency installation or QPU submission. They do not establish full study reproduction or fresh-install portability.

The separately retained benchmark archive totals approximately **9.18 GB of logical file content**, including its delivery manifest, according to the retained source-verification record. These downloads exclude raw datasets, trained checkpoints, installed environments and the full archive. Storage accounting is not a hardware or RAM minimum.

[Startup receipt](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/QPathformer_v0.1_Code.startup.json) · [Final package verification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/FRESH_PACKAGE_VERIFICATION.json) · [Package identities](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/PACKAGE_INDEX.json) · [Retained archive verification](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/FROZEN_SOURCE_VERIFICATION.json).

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.
