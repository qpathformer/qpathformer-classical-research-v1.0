# Code quickstart

Use a separate Python environment. Historical numerical dependencies are listed in DEPENDENCY_INVENTORY.json and payload/study/governance. No environment or third-party dependency is bundled. NumPy and SciPy are needed for the bounded check. The earlier local environment is a validation environment, not a recommended universal minimum.

From the extracted package root:

```console
python -B tools/verify_package.py
python -B tools/startup_check.py
python -B tools/verify_package.py
```

Keep redirected logs and receipts outside the entire extracted package. The startup tool disables network connection methods, parses selected Python, imports numerical modules, checks all 6 model shapes and independent state/moment parity and tests coefficient conversion. It does not train, score official data, sample shots or use a QPU.

Selected source paths are preserved under payload/study. Original scripts include guarded training, evaluation and local-readiness entry points for reproducibility; do not execute those merely to verify this download. Many require separately held data, frozen protocols, registered paths and checkpoint artifacts. Read the original reproduction guide before attempting a separately authorized replay in fresh writable directories. No ETEL is present.
