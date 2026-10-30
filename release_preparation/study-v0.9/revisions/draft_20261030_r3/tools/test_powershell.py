"""Test the literal v0.9 quickstart block in PowerShell on disposable fixtures."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
from test_helpers import HERE, SOURCE, rebuild

POWERSHELL = Path(r"C:\Program Files\PowerShell\7\pwsh.exe")
PYTHON = Path(r"C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe")


def identity(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def snapshot(root):
    return {p.relative_to(root).as_posix(): identity(p)["sha256"] for p in root.rglob("*") if p.is_file()}


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    quickstart = (HERE / "QUICKSTART.md").read_text("utf-8")
    blocks = re.findall(r"```powershell\n(.*?)\n```", quickstart, re.DOTALL)
    assert len(blocks) == 1
    snippet = blocks[0]
    version = subprocess.run([str(POWERSHELL), "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"], capture_output=True, text=True, check=True).stdout.strip()
    source_before = snapshot(SOURCE)
    outputs = []
    with tempfile.TemporaryDirectory(prefix="powershell-probes-", dir=HERE) as temporary:
        base = Path(temporary)
        assert base.resolve().is_relative_to(HERE.resolve())
        for name in ("invalid_missing", "invalid_changed_same_size", "invalid_unexpected", "valid"):
            root = base / name / SOURCE.name
            shutil.copytree(SOURCE, root)
            for helper in ("verify_package.py", "startup_check.py"):
                shutil.copyfile(HERE / helper, root / "tools" / helper)
            shutil.copyfile(HERE / "QUICKSTART.md", root / "QUICKSTART.md")
            rebuild(root)
            if name == "invalid_missing":
                (root / "START_HERE.md").unlink()
            elif name == "invalid_changed_same_size":
                p = root / "START_HERE.md"
                data = p.read_bytes()
                p.write_bytes(bytes([data[0] ^ 1]) + data[1:])
            elif name == "invalid_unexpected":
                (root / "unexpected.txt").write_text("extra\n", encoding="utf-8")
            before = snapshot(root)
            script = root.parent / "quickstart.ps1"
            script.write_text("$ErrorActionPreference = 'Continue'\n$PSNativeCommandUseErrorActionPreference = $false\n$Python = " + quote(PYTHON) + "\nSet-Location -LiteralPath " + quote(root) + "\n" + snippet + "\n", encoding="utf-8", newline="\n")
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
            command = [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)]
            process = subprocess.run(command, env=env, capture_output=True, text=True, timeout=500)
            receipt = root.parent / "QPathformer_v0.9_Code.startup.json"
            unchanged = before == snapshot(root)
            assert unchanged
            entry = dict(probe=name, status="PASS", command=command, returncode=process.returncode, stdout=process.stdout, stderr=process.stderr, startup_receipt_created=receipt.exists(), package_bytes_unchanged=unchanged)
            if name != "valid":
                assert process.returncode != 0 and not receipt.exists()
                assert "Package verification failed; startup was not run." in process.stderr
                entry["classification"] = "ACTUAL_POWERSHELL_STOP_BEFORE_STARTUP"
            else:
                result = json.loads(receipt.read_text("utf-8"))
                assert process.returncode == 0 and result["status"] == "PASS"
                assert len(result["checks"]) == 4 and result["parsed_python_files"] == 57
                assert result["cli_help_checks"] == 3 and result["numerical_input_records"] == 2 and result["scipy_version"] and result["numpy_version"]
                entry["classification"] = "GENUINE_BOUNDED_STARTUP_ON_UNSEALED_DISPOSABLE_HELPER_FIXTURE_NOT_FINAL_ZIP"
                entry["startup_result"] = result
            outputs.append(entry)
    source_after = snapshot(SOURCE)
    assert source_before == source_after
    tested = [identity(HERE / name) for name in ("verify_package.py", "startup_check.py", "QUICKSTART.md", "test_helpers.py", "test_powershell.py")]
    result = dict(status="PASS_POWERSHELL_QUICKSTART_CHECKS", recorded_at_utc=datetime.now(timezone.utc).isoformat(), powershell=str(POWERSHELL), powershell_version=version, invocation=[sys.executable, "-B", str(Path(__file__).resolve())], harness_python_version=sys.version, platform=platform.platform(), python_runtime=str(PYTHON), source_package=str(SOURCE), source_package_unchanged=True, source_package_fingerprint_sha256=hashlib.sha256(json.dumps(source_before, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), literal_quickstart_block_sha256=hashlib.sha256(snippet.encode()).hexdigest(), tested_files=tested, probes=outputs, boundary="Three actual invalid-fixture shell checks and one genuine bounded startup on an unsealed disposable fixture. This does not substitute for final sealed-ZIP startup or scientific replication.", final_zip_startup_still_required=True)
    (HERE / "POWERSHELL_TEST_RESULTS.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(dict(status=result["status"], powershell_version=version, probes=len(outputs), genuine_startup_checks=4, parsed_python_files=57, cli_help_paths=3)))


if __name__ == "__main__":
    main()
