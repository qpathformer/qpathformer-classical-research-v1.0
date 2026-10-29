# Bounded offline startup

Extract the Code ZIP into a new folder and first verify the external seal and internal inventories. Use a compatible existing Python environment with the dependencies below; no install or download step is performed by the helper. From the single package root run the verifier first, then startup:

```powershell
& $Python -B tools/verify_package.py
& $Python -B tools/startup_check.py --output ..\QPathformer_v0.2_Code.startup.json
```

Set `$Python` to your compatible interpreter path. The output must be new and outside the entire extracted package. The helper parses every selected Python file and checks source-specific imports, in-memory predictions, training CLI help and one explicit nontraining invariant. v0.2 also checks a small CPU text forward. It does not train, score the official data, sample shots, run device noise studies or submit QPU jobs.

Read the resulting JSON and return code. Successful startup is not full scientific reproduction, relocation verification or a clean-room installation. Do not run historical launch/evaluation scripts merely to verify the download. Full replay needs the omitted retained evidence and appropriate fresh workspace gates.
