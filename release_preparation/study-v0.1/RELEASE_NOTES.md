# Q-Pathformer Study v0.1 — Local Benchmark and IBM Readiness

**Draft for review · Private repository · Study · Documentation · Code**

This draft brings the completed v0.1 study into **Q-Pathformer Classical Research, repository edition v1.0**. It is available for owner review; the published `study-v0.9.5` release remains unchanged.

## Review downloads

Download the three ZIPs and their matching `.seal.json` files from this draft's Assets section. Extract each ZIP once and open `START_HERE.md`.

| Package | Review contents |
| --- | --- |
| `QPathformer_v0.1_Study.zip` | Report PDF and Word candidate with Anthony's metadata, edition changes and report-content rights proposal. |
| `QPathformer_v0.1_Documentation.zip` | Study overview, research guide, reproduction boundaries and source evidence. |
| `QPathformer_v0.1_Code.zip` | Selected circuit/MLP, text-routing and offline readiness implementation; dependency inventory, quickstart and bounded startup tools. |

The original v0.1 work includes a prototype capsule and a later full benchmark. The completed benchmark contains **45 synthetic training runs**, **ten AG News method runs**, and local readiness checks of **30 trained circuit checkpoints**. The trained-readiness audit used 3,686,400 simulated shots and zero physical shots or hardware jobs. This v0.1 selection has no ETEL component.

The scheduled circuit underperformed the matched-information MLP and fixed four-layer control on the radial task. Shared and content-routed text adapters produced very similar AG News endpoints, with uncertainty intervals that include zero. These results do not establish equivalence or quantum advantage. See the [study summary](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/review-study-v0.1/release_preparation/study-v0.1/documentation/release_notes/study-v0.1.md).

## Report and rights review

The report candidate preserves all scientific prose, 15 tables and three figures. It updates presentation labels and author metadata and adds an edition note explaining the original report's historical publication recommendation.

The review proposes **CC BY 4.0** for identified original report content and new explanatory prose, and the unchanged **Q-Pathformer Platform License 1.0** for the exact **24 Python files**. These v0.1 proposals are **not adopted**. Earlier grants remain in force for their existing scopes. No dataset, dependency, model, architecture-document or whole-archive grant is implied.

[Review guide and exact scope proposals](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/review-study-v0.1/release_preparation/study-v0.1/README.md).

## Verification and reproduction

All three ZIPs passed seal, internal inventory and fresh-extraction checks. The final Code ZIP passed Windows startup checks covering imports, four CLI help paths, 15 selected non-training tests and one local circuit compilation/matrix comparison. No training, optimizer updates, shot sampling, dependency installation or QPU submission ran.

The separately retained benchmark archive has a **9.18 GB logical file boundary** including its delivery manifest. All 2,081 manifest payload files passed SHA-256 verification. These small downloads exclude raw datasets, trained checkpoints, installed environments and the full archive; storage accounting is not a hardware minimum.

[Startup receipt](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/review-study-v0.1/release_preparation/study-v0.1/QPathformer_v0.1_Code.startup.json) · [ZIP/seal/startup binding](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/review-study-v0.1/release_preparation/study-v0.1/FRESH_PACKAGE_VERIFICATION.json) · [Draft upload record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/review-study-v0.1/release_preparation/study-v0.1/DRAFT_RELEASE.json).

Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative.
