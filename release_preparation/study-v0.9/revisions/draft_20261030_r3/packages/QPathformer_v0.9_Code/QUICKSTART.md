# Bounded offline startup

Extract the Code ZIP into a new folder after checking its external seal and safe extraction paths. Use a compatible existing Python environment with the dependencies described in [DEPENDENCY_INVENTORY.json](DEPENDENCY_INVENTORY.json); no install or download step is performed by the helper. From the single package root run the following block. It stops before startup if internal verification fails:

```powershell
& {
    & $Python -B tools/verify_package.py
    if ($LASTEXITCODE -ne 0) {
        throw "Package verification failed; startup was not run."
    }

    & $Python -B tools/startup_check.py --output ..\QPathformer_v0.9_Code.startup.json
    if ($LASTEXITCODE -ne 0) {
        throw "Bounded startup failed; inspect the output and any receipt."
    }
}
```

Set `$Python` to your compatible interpreter path. The receipt must use a new pathname outside the entire extracted package. The helper reserves it exclusively, verifies package integrity before and after startup, and parses every selected Python file. Its numerical smoke check imports NumPy, SciPy and the selected modules, evaluates two inputs through a zero-angle circuit, checks moment shape/range and compares sigmoid values. Three required CLI paths (`quantum/study.py`, `execution/launcher.py`, `execution/bind_stage.py`) must return successful `--help` output. The receipt records 57 parsed Python files, actual numerical versions, two input records and three completed help paths. No full model-family or independent-matrix test suite is claimed. Network connections are disabled inside these test subprocesses. These checks do not launch ETEL fits or recovery tests, train, score official data, sample shots, rerun deployment timing or submit QPU jobs.

Read the resulting JSON and return code. An internal verifier's `PASS` is not publisher authentication and does not replace the external ZIP/seal or safe-extraction checks. Successful startup is not full scientific reproduction, relocation verification or a clean-room installation. Do not run historical launch/evaluation scripts merely to verify the download. Full replay needs the omitted retained evidence and appropriate fresh workspace gates.

Complete historical replay also needs separately retained accepted recovery entrypoints, supporting protocols, qualification sources and operational bindings. Some selected entrypoints preserve earlier historical implementations. This curated ZIP supports source inspection and bounded startup; it is not the complete final accepted replay distribution. See the companion Documentation reproduction boundaries.
