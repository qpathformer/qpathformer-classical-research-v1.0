# Verify this package

Keep `QPathformer_v0.3_Documentation.seal.json` beside `QPathformer_v0.3_Documentation.zip`. Verify the ZIP name, size and SHA-256, then the expected single root and safe file paths. The seal identifies MANIFEST.json, CHECKSUMS.sha256 and SOURCE_MAP.json by size and hash. It is an integrity record, not a digital signature.

MANIFEST.json covers every regular file except itself and CHECKSUMS.sha256. CHECKSUMS.sha256 covers every other regular file, including the manifest. Reject duplicate paths, unexpected files, missing files, unsafe ZIP paths and mismatching hashes.

Startup outputs and receipts must be outside the entire package. Publisher verification and download receipts are retained beside the distribution folder in the release preparation records; they bind these exact ZIP and seal identities. Changes require new sealed bytes and fresh Code startup verification.
