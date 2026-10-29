# Package integrity

Keep the external .seal.json next to its ZIP. Verify ZIP name, byte size, SHA-256 and expected single root before extracting. MANIFEST.json covers every regular file except itself and CHECKSUMS.sha256; checksums cover every regular file except themselves, including the manifest. SOURCE_MAP.json records selected origins. The seal is an integrity record, not a digital signature.

Run Code tools with outputs outside the entire extracted package. Startup evidence is retained outside the ZIP and bound to the delivered ZIP and seal in the preparation records. No full scientific reproduction is claimed.
