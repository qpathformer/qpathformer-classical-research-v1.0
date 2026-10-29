# Using the study-v0.9.5 release

[Main README](../README.md) · [License scope](../LICENSE_SCOPE.md) · [Verification](../VERIFY.md)

**Repository edition v1.0; release study-v0.9.5.** The repository edition identifies the collection. Each release retains its study identifier; this first study release contains the completed allocation study **v0.9.5** and **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**. Further completed study results will be added as versioned releases in this repository after review.

| Package | What to open after one extraction |
| --- | --- |
| `QPathformer_v0.9.5_Study.zip` | START_HERE.md, then the final report PDF or Word file in its unchanged payload tree. |
| `QPathformer_v0.9.5_Documentation.zip` | START_HERE.md, then this project README and the research/reproduction guides. |
| `QPathformer_v0.9.5_Code.zip` | START_HERE.md, then the unchanged code payload's QUICKSTART.md and review tools. |

Keep each ZIP with the matching `.seal.json`. The seal is an integrity record for those exact compressed bytes. If the package changes, it needs a new seal. The external seal is not inside its own ZIP.

The Study and Code payloads preserve their original paths, bytes, licenses and internal checksums. Older publication/startup records are retained as provenance. The new outer manifest and seal describe this new wrapper; older seals describe the retained original ZIPs. Verification records identify which package and checks they apply to.

This study release does not supply datasets, trained models, runtime bundles or complete experiment archives. The research collection can grow in reviewed stages with identified source material and appropriate terms. Full reproduction and physical-QPU experiments have separate requirements.

The clean repository entry tree contains final selected documents and concise provenance. Internal review history, old captures, private working notes and development checkouts are not imported as Git history. Source version labels inside unchanged payloads remain accurate historical identifiers.

[Release downloads](https://github.com/qpathformer/qpathformer-classical-research-v1.0/releases/tag/study-v0.9.5), the [startup receipt](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/QPathformer_v0.9.5_Code.startup.json) and [package verification record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/FRESH_PACKAGE_VERIFICATION.json) identify the delivered packages and the checks performed. The [repository mapping](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/REPOSITORY_MAPPING.json) connects historical staging identities to this clean distribution. The [publication record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/PUBLICATION.json) records the later release event. These records are kept outside the sealed downloads; the publication event is recorded after the study release tag.
