# Q-Pathformer Research v1.0 — Routed States and Three-State Architecture

**Private release draft for owner check.** Research edition **v1.0**; distinct release tag `research-v1.0-20261031`. The earlier `research-v1.0` remains published and Latest during this preparation.

Q-Pathformer investigates how learning systems choose where to spend their effort: which examples receive training, how specialist models are selected or combined, and how a limited training budget is shared among competing models. This research edition connects the original architectural idea, the evidence from completed component studies, and a separate specification for the next experiments.

## Why we created this collection

We created this collection to make the research path easier to inspect and extend. An architectural proposal becomes more useful when its mechanisms can be tested separately and its results can be compared with credible alternatives.

For AI and quantum-circuit research, an improvement needs an explanation: did it come from routing, a more flexible predictor, different input information or a larger resource allowance? Q-Pathformer explores these questions through defined text tasks and small classical and simulated quantum-circuit models. The aim is to understand which choices justify their cost, where simpler alternatives remain preferable, and what further evidence would support extending the architecture.

## Our research approach

The research separates three decisions:

- **Training-example selection:** which examples receive attention during learning.
- **Model routing:** which specialist components contribute to a prediction, and how their outputs are combined.
- **Training-budget allocation:** which candidate models receive more work under a limited budget.

Each study identifies its question, controls, evaluation rules and resource boundaries. Classical baselines and numerical references help examine alternative explanations for a result. Predictive quality and execution cost are reported separately, with uncertainty appropriate to the comparison. Negative and inconclusive findings remain part of the evidence.

The completed studies show task-dependent benefits from readout and routing changes, while strong classical controls remain better in important comparisons. Selected fitted circuit predictors also support faster equivalent classical inference under the measured conditions. The tested allocation policy of the Elastic Task Execution Layer (ETEL) did not establish its registered practical quality gain; capped successive halving used less mean CPU across the four tested tasks.

These findings inform further research. They do not establish physical-QPU performance, general quantum advantage or validation of the full integrated architecture.

## Start reading

| Document | What you will find |
| --- | --- |
| **Q-Pathformer Routed States: Classical Models and Quantum Circuit Simulation** | The main findings paper: circuit readouts, routing, classical inference conversion, training allocation and the limits of the evidence |
| **Q-Pathformer Three-State Architecture and Experimental Specification** | The proposed software responsibilities, experimental controls and decisions to settle before future runs |
| **Research Approach** | A separate guide to the research questions, comparison method, contribution opportunities and future research cycle |

The supporting study reports retain their individual methods, results and reproduction boundaries. The original architecture is preserved separately with its source history and notices.

## Choose a download

| Package | Use it for |
| --- | --- |
| `QPathformer_All_Papers_v1.0.zip` | The papers, original architecture, reading guide and rights indexes |
| `QPathformer_Consolidated_Release_v1.0.zip` | The Papers package plus Research Approach, collection guidance, licence/trademark records and the identified repository source snapshot |

**Choose one ZIP and its matching `.seal.json`.** Consolidated already contains Papers. Extract the archive and open its README or `START_HERE.md`. Research Approach is included in Consolidated at `repository/docs/RESEARCH_APPROACH.md`.

GitHub's automatic [source archives](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) reflect the repository at the release tag. The curated research collection is in the ZIPs listed above.

Both papers include page labels and bookmarks. If your PDF reader does not follow a local cross-document link, open the adjacent PDF directly or use the README links. Use the matching seals and `QPathformer_Research_v1.0_Delivery_Receipt.json` to check artifact identities. Seals establish integrity; they are not digital signatures.

## Explore, reproduce and contribute

Useful contributions include independent reproductions, stronger controls, numerical checks, clearer resource measurements, corrections and documented negative findings. The contribution and governance guides explain how work is reviewed and how qualifying contributions can establish eligibility for owner review of private Lab access.

Individual studies retain separate **Study, Documentation and Code** assets. These research downloads bring the papers and guidance together; they do not introduce a unified software implementation or a new experiment. Consult each study's guide for its selected code and reproduction requirements.

## Changes in this replacement

Both papers retain v1.0 without a Draft for review or Final label. Their title-page status lines, running headers/footers, cross-paper status descriptions and metadata have been updated. The scientific claims, limitations, numerical results, equations, figures and reference identities are preserved. Main paper: 43 pages; architecture companion: 27 pages. The original architecture and all ten supporting study report pairs are unchanged.

The owner adopted CC BY 4.0 for the identified controlled original content in the papers, covers, current Research Approach and named README/helper/policy prose on 31 October 2026. Existing code/report/source grants and third-party notices remain intact. The adopted trademark policy identifies ALNOTREA PTY LTD, the registered Australian word mark and the separately pending application; Anthony Siljeg (asiljeg@alnotrea.com) is the authorised respondent. The new Platform reference PDF reproduces the research canonical TXT without changing its terms.

## Publication status and rights

The repository remains private. This replacement is prepared for release approval; no public visibility change is performed. On approved publication, designate this replacement Latest and mark the earlier research-v1.0 release superseded while preserving its tag and assets. Both releases use the scientific edition v1.0; the dated tag and file digests distinguish their distributions.

Consolidated includes the exact repository source snapshot identified by the delivery receipt, the rebuilt Papers ZIP and its exact seal. Research Approach remains separate release documentation at repository/docs/RESEARCH_APPROACH.md. Owner Planning and preparation inputs are excluded from release downloads.

See repository/RESEARCH_V1_CONTENT_LICENSE_SCOPE.json and RESEARCH_V1_LICENSE_ADOPTION.json for the new content grant and exclusions, LICENSE_SCOPE.md for existing software/report scopes, and TRADEMARKS.md for branding. This is not a whole-repository or whole-ZIP licence. The original architecture retains its notices; font software and other third-party material retain their terms. Lab access does not grant a commercial software agreement or trademark permission.

Public-distribution review of the retained historical disclosures and repository surfaces remains separate. The Dataset Lifecycle historical TXT/PDF discrepancy and software-contracting authority are not settled by this research packaging update. Operational repository rules remain deferred. No new experiment, independent replication or peer-review claim is introduced.
