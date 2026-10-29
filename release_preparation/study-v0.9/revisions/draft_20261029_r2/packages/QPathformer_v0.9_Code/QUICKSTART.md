# Study v0.9 code quickstart

This curated code preserves the study-specific scientific models, trainer, audits, circuit conversion and ETEL execution adapter. ETEL is included because this source study supplies it. Source files remain byte-identical; absolute-path recipes and release bindings are historical. Raw data, generated populations, checkpoints, predictions, ledgers and installed environments are excluded.

From the extracted package root, using a compatible existing environment:

```powershell
python -B tools/verify_package.py
python -B tools/startup_check.py > ../QPathformer_v0.9_Code.startup.json
```

Keep receipts outside the entire extracted package. The startup helper imports numerical modules, checks two in-memory circuit inputs and constructs three CLI help screens. It launches no fits, scoring, shot sampling or network jobs. The verification helper checks exact file membership and hashes.

Historical environment: Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1 with one OpenBLAS thread per worker. The retained ETEL process/resource integration targets Windows. The requirements file is an inventory, not a complete environment lock or proof of portable installation. No dependency install is performed by these tools.

For full reproduction, obtain separately authorized retained inputs, create a new unsealed working root and review environment/path mappings and new execution authority. The original execution README retains original commands for context; do not rerun them against completed archives. The official full archive and external baseline inputs are not silently bundled.
