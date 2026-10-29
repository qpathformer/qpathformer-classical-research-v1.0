# Verify this repository snapshot

`CHECKSUMS.sha256` covers the selected repository files at this revision, including `MANIFEST.json`, `SOURCE_RECORD.json` and `VALIDATION.json`, excluding only itself. `MANIFEST.json` inventories every selected file except itself and the checksum file. The `.git` directory and unrelated untracked local files are outside the selection. The next edit requires regenerated records for that next snapshot.

`SOURCE_RECORD.json` records the previous repository commit, preserved source identities, current editorial changes and the pinned GitHub source of QPATH-ARCH-001. The architecture PDF bytes and metadata are unchanged. `VALIDATION.json` records the bounded checks made for this snapshot. File verification does not demonstrate scientific reproduction or itself grant a license. The actual owner decisions are recorded in the adopted code/report scope records.

The original `QPathformer_Repository.zip` remains an immutable preparation snapshot. Its 37 original files and integrity records are preserved in [import commit `1db1d15`](https://github.com/qpathformer/qpathformer-classical-research/tree/1db1d15c00785ea14a74dca7e37eb5f3560b055b). Its ZIP SHA-256 remains `49d5e989d9b6ad328af0b356e4d367fa8a466e200435f9ee94e6b5747f2877e3`.

The later `QPathformer_study-v0.9.5_documentation.zip` preserves all 41 tracked files at documentation commit `f9f4723e31b4944ccea16541cb0efc4c74cda841`. It retains 39 internal-manifest entries and 40 checksum entries; its SHA-256 remains `f5415147411c53f6a96f51a6a90a65c0f6ec31a89e540d0182c73cdbd2e3457f`. Use each historical ZIP's own external manifest and seal. Current Git-tree records do not replace them.

The separately attached report and code packages have independent manifests, checksums and seals. Scope paths in [CODE_LICENSE_SCOPE.json](CODE_LICENSE_SCOPE.json) and [REPORT_LICENSE_SCOPE.json](REPORT_LICENSE_SCOPE.json) refer to files in those release selections, not source/report files in this Git tree. Preparation-state fields in those exact copied scope records remain historical; actual release asset IDs, URLs and uploaded-file checks are recorded by the publication receipts.

The code package's post-seal startup and regression receipts identify the exact ZIP tested. Their bounded checks do not establish official study reproduction, fresh installation or QPU execution. SHA-256 seals are integrity records, not digital signatures.

No new downloadable main-repository ZIP is claimed for this Git-tree update. See the [release](https://github.com/qpathformer/qpathformer-classical-research/releases/tag/study-v0.9.5), [repository status](REPOSITORY_STATUS.md) and [architecture provenance](docs/architecture/README.md).

The unchanged documentation proposal in `cc_scope_proposal.json` identifies candidates at historical commit `461ea2383f0e333247ddfe664e187265a444b931`. Verify those candidate hashes against that commit, not against later revised files. Current root manifests describe this revision; the historical proposal is not an integrity manifest for the current tree. A later documentation decision requires its own exact scope record.
