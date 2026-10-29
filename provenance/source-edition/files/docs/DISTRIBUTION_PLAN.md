# Planned private v2.0 distribution

This is a plan. The current repository and study-v0.9.5 release remain private staging. The future repository will also start **private**. Repository/distribution **v2.0** will identify a curated collection; the included allocation study remains **v0.9.5**, and the execution component remains **Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1**.

The intended new repository will bring the research materials together in stages. Start with the cleared study, documentation and selected code. Inventory additional reports, studies, code, datasets and model artifacts before each later stage, recording availability, provenance, size and applicable rights. The initial three-package selection does not yet include trained models, frozen datasets or complete reproduction archives. “All materials” is a staged collection objective, not a blanket license or a claim that all files are already distributed.

## Stage 1: finish this staging revision

Clarify Study · Documentation · Code navigation, preserve the original tag and all existing release assets, distinguish the version identifiers, and resolve the exact current documentation licensing selection. Keep the old proposal and scope records as historical evidence. A new documentation grant requires its own owner decision; company attribution alone does not change ownership.

## Stage 2: select and assemble the new distribution

Prepare the reviewed export and all package inputs, assembly, final outputs and verification receipts under `C:\Q2`. The proposed build root is `C:\Q2\Release_Preparation\QPathformer_Classical_Research\v2.0`; record the actual paths when built. Export selected files explicitly, without copying the entire private Git history, internal review folders or development tree. Start the new repository with a clean Git history and only final selected files. Use the clean package names below without internal revision, review or draft suffixes. Retain true study/component/distribution identifiers and concise source provenance; keep preparatory drafts and revision history in the private staging records. Clean presentation does not require rewriting original sealed payload bytes or their embedded provenance.

| Route | Proposed package | External integrity record |
| --- | --- | --- |
| Study | `QPathformer_v2.0_Study.zip` | `QPathformer_v2.0_Study.seal.json` |
| Documentation | `QPathformer_v2.0_Documentation.zip` | `QPathformer_v2.0_Documentation.seal.json` |
| Code | `QPathformer_v2.0_Code.zip` | `QPathformer_v2.0_Code.seal.json` |

The Study package will contain the unchanged final v0.9.5 report edition and its scope/rights. The Code package will contain the complete unchanged final selected implementation package, including corrected review tools, ETEL, scope and Platform license. Verify each original ZIP, then extract its complete package tree intact beneath a new `payload/` directory. After one unzip, the original PDF/DOCX and code paths will be directly available; do not nest another ZIP as the only usable payload.

Documentation will be a newly selected edition of the reviewed guides, summaries and illustrations. If QPATH-ARCH-001 is retained, preserve its bytes and separate notices. Do not imply that the new documentation edition is byte-identical to the historical ZIP. Newly authored START_HERE instructions and other wrapper prose must be explicitly included in a later documentation decision; they are not covered merely by being adjacent to licensed files.

Every wrapper will include START_HERE.md, an outer MANIFEST.json, CHECKSUMS.sha256 and provenance/SOURCE_MAP.json. The source map will identify original ZIP hashes, source commits where relevant, extraction prefixes, original-to-new paths and added wrapper files. Preserve original internal manifests and checksums within each intact payload. Store selected old external seals and receipts under provenance/prior-release, labelled as records for the original ZIP, not the new wrapper. Verification of those old compressed archive bytes still requires the retained original ZIP.

The new outer manifest covers all regular files except itself and CHECKSUMS.sha256. The outer checksums cover all regular files except themselves, including the manifest. The external seal binds the actual ZIP filename, bytes and SHA-256 plus the outer manifest/checksum identities and schema version. Check exact membership, a single expected prefix, duplicate or unsafe paths and every recorded digest. The seal stays outside its own ZIP and is an integrity record, not a digital signature. No separate outer external manifest is planned unless the validated tooling requires one.

Extract the final Code ZIP into a fresh directory under C:\Q2 and run its original verifier and bounded startup check from the intact payload root. Save the fresh receipt outside the sealed ZIP. Historical startup receipts do not prove a new wrapper was tested. Post-seal verification and publication records can be added at a later identified repository commit; preserve the distribution tag at its selected source commit.

## Stage 3: create the new private repository

The requested owner/name is currently occupied by this staging repository. A later migration can rename staging to `qpathformer-classical-research-staging`, subject to availability, then create a clean private repository at `qpathformer/qpathformer-classical-research`. Alternatively choose a different new name and retain current URLs. Decide and execute this migration at the later stage.

If the old name is reused, GitHub's rename redirects stop working. Record repository IDs and old/new URLs, update remotes and maintained links, and provide explicit mappings for historical commits and release assets. Preserve original historical URLs inside old receipts. A fresh repository will not automatically contain staging's old commit objects or release assets. Evidence needed by readers must be included in the selected new distribution; a private staging URL cannot be its only support. See [GitHub's rename guidance](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).

Stage the three package/seal pairs in a draft v2.0 release. These are six authored assets; GitHub also supplies generated source archives. Verify final links, payload identities, rights and visibility before publication. A release published within a private repository remains access-limited. Any later public visibility change is a separate decision.

## Later stages and evidence boundaries

Add other materials through identified selections and review their rights independently. Preserve study identifiers and keep code, report, documentation and artifact-specific terms distinct. Full study reproduction needs the retained frozen data, protocols, environments and archives. Package checks do not establish fresh-install portability, a new scientific result or physical-QPU success.

[Current status](../REPOSITORY_STATUS.md) · [License scope](../LICENSE_SCOPE.md) · [Reproducibility](REPRODUCIBILITY.md) · [QPU preparation](QPU_RELEASE_PLAN.md)
