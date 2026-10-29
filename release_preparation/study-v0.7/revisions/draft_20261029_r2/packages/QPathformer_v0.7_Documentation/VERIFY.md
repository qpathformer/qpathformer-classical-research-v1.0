# Verify the package

Keep `QPathformer_v0.7_Documentation.seal.json` beside `QPathformer_v0.7_Documentation.zip`. Check the external seal for ZIP filename, byte size and SHA-256 before extraction. The seal also binds the single expected root, internal manifest, checksum list and source map to their exact identities and actual Q2 build location. It is an integrity record, not a digital signature.

MANIFEST.json covers every regular file except itself and CHECKSUMS.sha256. The checksum list covers every other regular file, including the manifest. Reject unexpected members, duplicate names, absolute paths, traversal paths, symlinks and special files. Keep verification outputs outside the entire extracted package. Any changed content requires a new ZIP, seal and relevant startup verification.

The Code package provides read-only verification and bounded offline startup helpers. Post-sealing and upload receipts are maintained outside all three packages.
