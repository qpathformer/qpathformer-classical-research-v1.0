# v0.4 r3 revision summary

The two helpers now enforce strict path/inventory validation, reserve receipts exclusively and verify package identity before and after startup. The PowerShell quickstart stops after verification failure and contains only the three v0.4 checks. Current explanations define Q2, lead with primary BCE, retain stronger classical controls and distinguish historical readiness from new packaging checks. Publisher review is clarified in current guidance; historical edition records remain unchanged.

All 48 scientific Python files and full scientific payload, report PDF/DOCX, historical records, canonical licence texts and adoption records retain their reviewed bytes. Current wrapper/helper changes require new ZIPs and seals for all three packages. Earlier sealed evidence is preserved. Optional historical Word metadata cleanup is deferred because no report error warrants changing its bytes.

The genuine final Code startup passed three checks: 50 Python files parsed, nine methods exercised, NumPy 2.5.4. Mock regression controls, real PowerShell checks and final sealed-ZIP startup are separately recorded. No full training, official-data scoring, dependency installation or QPU execution was performed.

## Asset identities

| Asset | Previous bytes / SHA-256 | Current bytes / SHA-256 |
| --- | --- | --- |
| QPathformer_v0.4_Code.seal.json | 1366 / `03bd49549266c0f6eac77628061a2b83ac1ed6de2b9aa5c7a476c4aa59dcf5e0` | 1366 / `84dadbef12bfa5a989048235fd476561765924d66bd030a756c6e80fe7de9da2` |
| QPathformer_v0.4_Code.zip | 224507 / `94c2cbe8c79bd09640f2bdb44f1e2d96318d8192e08cb4c9abf7b3f6a9b03912` | 228843 / `f1e4cd43174f7bf1183d7d6b2a8e274eddfe0d7806d378586cffd09b6990c29e` |
| QPathformer_v0.4_Documentation.seal.json | 1429 / `4c497dcc9833bf43ca8f374efb4c2a5cb7d80f1679613ea62ca740fb97a30a13` | 1436 / `448e7879c9e4d350e5e79081c18c7ca0e245b871df0933d3b8d0030c4011a912` |
| QPathformer_v0.4_Documentation.zip | 34928 / `c9501ddd0f9bdca31dbcf069ec37261f6abcac9dab9642d1ab00e7ef7e126a7e` | 38523 / `0f4df9d5855668c413d470834a84f9e5e3ea067d37f5fdce1aa0dfd5a0376a16` |
| QPathformer_v0.4_Study.seal.json | 1367 / `87bda71531713e97617e8045f723df4a02216652a42902913b54e51900ca77b6` | 1373 / `7ec9faa593ae355d255c844b7521f45119e4c29d82af7e171bdac75e14a1da3d` |
| QPathformer_v0.4_Study.zip | 1791206 / `772483cd5575998473a6383959d39fa6edc89ae143d3770a8feee174a63d249b` | 1791984 / `a2ba6edce95c8ae85259b61db85ab30ad525ee7280a897a7a45348ce33f31beb` |

[Review disposition](receipts/REVIEW_DISPOSITION.json) · [Helper probes](receipts/HELPER_TEST_RESULTS.json) · [PowerShell checks](receipts/POWERSHELL_TEST_RESULTS.json) · [Final startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json).

This is an updated private draft. Publication remains a separate action; v0.9.5 remains Latest.
