# Bounded offline startup

Extract the Code ZIP into a new folder after checking its external seal and safe extraction paths. Use a compatible existing Python environment with the dependencies described in [DEPENDENCY_INVENTORY.json](DEPENDENCY_INVENTORY.json); no install or download step is performed by the helper. From the single package root run the following block. It stops before startup if internal verification fails:

```powershell
& {
    & $Python -B tools/verify_package.py
    if ($LASTEXITCODE -ne 0) {
        throw "Package verification failed; startup was not run."
    }

    & $Python -B tools/startup_check.py --output ..\QPathformer_v0.5_Code.startup.json
    if ($LASTEXITCODE -ne 0) {
        throw "Bounded startup failed; inspect the output and any receipt."
    }
}
```

Set `$Python` to your compatible interpreter path. The receipt must use a new pathname outside the entire extracted package. The helper reserves it exclusively, verifies package integrity before and after startup, and parses every selected Python file. Its two v0.5 checks import the selected numerical modules and run the original tests for model parameter shapes/paired initial predictions and independent circuit-state/moment agreement. The receipt records the parsed-file count, actual model inventory, test count and imported NumPy/SciPy versions. Network connections are disabled inside these test subprocesses. During release packaging these checks do not train, score official data, sample shots, run device-noise studies or submit QPU jobs.

Read the resulting JSON and return code. An internal verifier's `PASS` is not publisher authentication and does not replace the external ZIP/seal or safe-extraction checks. Successful startup is not full scientific reproduction, relocation verification or a clean-room installation. Do not run historical launch/evaluation scripts merely to verify the download. Full replay needs the omitted retained evidence and appropriate fresh workspace gates.
