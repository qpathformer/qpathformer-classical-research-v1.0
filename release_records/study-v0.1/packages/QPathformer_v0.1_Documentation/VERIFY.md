# Verify this package

Keep `QPathformer_v0.1_Documentation.seal.json` beside `QPathformer_v0.1_Documentation.zip`. Compare its recorded ZIP filename, byte size and SHA-256 before extraction. The external seal binds the internal manifest, checksum list and source map. It is an integrity record, not a digital signature or a license grant.

MANIFEST.json lists every regular file except itself and CHECKSUMS.sha256. CHECKSUMS.sha256 covers all other files, including the manifest, and excludes only itself. Verify exact membership, every hash, the single expected root folder, and the absence of duplicate, unsafe or non-regular entries.

Verification receipts belong outside the entire extracted package. The [fresh extraction and startup binding](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/FRESH_PACKAGE_VERIFICATION.json) identifies these final ZIPs, matching seals and the external [Code startup receipt](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/QPathformer_v0.1_Code.startup.json). The [package index](https://github.com/qpathformer/qpathformer-classical-research-v1.0/blob/study-v0.1/release_records/study-v0.1/PACKAGE_INDEX.json) records all six delivered asset identities. These records are retained at the fixed study-v0.1 release tag; the subsequent publication event is recorded separately in the repository.

Any subsequent change to packaged content requires new inventories, ZIP bytes and seals. A changed final Code ZIP requires a fresh bounded startup check. The reviewed draft editions and their receipts remain historical evidence, with different package identities.
