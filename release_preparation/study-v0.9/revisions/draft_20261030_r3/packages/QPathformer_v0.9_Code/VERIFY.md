# Package integrity and bounded verification

Keep each external seal beside its ZIP. Check exact size/hash and safe single-root membership before extraction: reject duplicate/case-colliding, absolute, traversal, ambiguous, encrypted and nonregular entries. Seals are integrity records, not signatures or publisher authentication.

MANIFEST.json covers every file except itself and CHECKSUMS.sha256. Checksums cover every file except themselves. Validate raw record syntax, types and uniqueness before constructing maps; verify complete membership, sizes and hashes. The [source map](SOURCE_MAP.json) identifies selected origins and current wrappers.

The companion Code quickstart guards both return codes and writes a new external receipt exclusively. Its unconditional verifier works under Python optimization. Startup checks exact integrity before imports and after its numerical smoke check and three required CLI help paths. Failures cannot produce PASS. This is not a whole-study replay, clean installation, ETEL recovery test or conversion-parity suite.

Bounded startup does not test Banknote preprocessing or complete accepted recovery replay. Consult the companion Documentation reproduction boundaries for omitted prerequisites.
