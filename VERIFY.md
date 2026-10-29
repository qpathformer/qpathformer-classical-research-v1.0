# Verify the study release packages

For v0.1, use its [package identities and adopted scopes](release_records/study-v0.1/README.md), [final ZIP/seal/startup binding](release_records/study-v0.1/FRESH_PACKAGE_VERIFICATION.json) and [startup receipt](release_records/study-v0.1/QPathformer_v0.1_Code.startup.json). Its tools run from the outer Code package root. The layout-specific instructions below describe the preserved v0.9.5 packages.

## Study v0.9.5

Keep each ZIP beside its matching `.seal.json`. First compare the ZIP filename, byte size and SHA-256 with that seal. The seal identifies the expected outer root and the outer manifest/checksum identities. A SHA-256 seal is an integrity record, not a digital signature or a license grant.

After extraction, check exact file membership and every digest against the outer MANIFEST.json and CHECKSUMS.sha256. The manifest excludes itself and CHECKSUMS.sha256; the checksum list includes the manifest and excludes only itself. Reject duplicate names, unsafe paths or unexpected files. The matching seal stays outside the ZIP to avoid circular hashes.

Study and Code preserve their complete original package trees beneath payload/. Their original internal manifests/checksums remain valid within those roots. Source maps identify original-to-current paths and unchanged bytes. Historical external seals and receipts in provenance/prior-release describe the original ZIPs. Verifying those original compressed bytes still requires the retained original archives; the new outer seal verifies the new download.

The Documentation package is a new selected edition with its own outer inventory. Source license records identify earlier editions and their adopted content; the source map distinguishes retained and adapted files. An old source hash is not the expected hash of an edited current file.

The Code package's original verifier and startup tools must run from their intact payload root using the compatible runtime described in QUICKSTART.md. A fresh distribution startup check uses the newly extracted final Code ZIP and writes its receipt outside the package. Read the [study-v0.9.5 startup receipt](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/QPathformer_v0.9.5_Code.startup.json) and [package verification record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/FRESH_PACKAGE_VERIFICATION.json) for the exact ZIP and seal identity, environment, commands, outcome and limits. Historical startup receipts do not establish that a new wrapper was checked.

Package verification and bounded startup checks do not establish full study reproduction, fresh-install portability or physical-QPU execution. Full reproduction needs the separately retained study artifacts and environment. See [reproducibility](docs/REPRODUCIBILITY.md).

The [repository mapping](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/REPOSITORY_MAPPING.json) identifies the original staging repository and the current repository by their stable IDs and naming history. The [publication record](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/main/provenance/publication-study-v0.9.5/PUBLICATION.json) binds the actual release event and delivered asset identities. These external records accompany the sealed downloads without changing their bytes. The study release tag identifies the selected tree and startup records; the subsequent publication record is retained in the repository history.
