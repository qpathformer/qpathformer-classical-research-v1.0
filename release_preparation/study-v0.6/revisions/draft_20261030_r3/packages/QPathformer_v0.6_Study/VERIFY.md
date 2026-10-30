# Package integrity

Keep the external `.seal.json` beside its ZIP. Before extracting or running package code, verify the expected ZIP name, byte size, SHA-256 and safe single-root membership. Reject duplicate or case-colliding paths, traversal, absolute paths, ambiguous path forms, encrypted entries and nonregular members. A seal records integrity; it is not a digital signature or proof of publisher identity by itself.

`MANIFEST.json` covers every regular file except itself and `CHECKSUMS.sha256`; checksums cover every regular file except themselves, including the manifest. Check raw inventory structure and uniqueness before constructing lookup maps, then exact membership, sizes and hashes. The selected origins are recorded in [provenance/SOURCE_MAP.json](provenance/SOURCE_MAP.json).

The companion Code package's quickstart stops on verification failure. Its helper checks exact package integrity before scientific imports and after startup, using unconditional checks that do not disappear under Python optimization. Keep output outside the entire extracted package and preserve existing receipts. The publisher's external receipt binds the actual startup output to the selected ZIP and seal. Successful bounded startup is not full scientific reproduction.
