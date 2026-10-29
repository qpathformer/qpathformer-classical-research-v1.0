"""Disposable helper probes. Mocked startup results are not genuine startup evidence."""
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SOURCE = Path(r"C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.2\draft_20261029_r3\qa\fresh_extraction\QPathformer_v0.2_Code")
LABEL = "MOCKED_CONTROL_FLOW_ONLY_NOT_STARTUP_VERIFICATION"
sys.dont_write_bytecode = True


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


VERIFIER = module(HERE / "verify_package.py", "probe_verifier")


def rebuild(root):
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in ("MANIFEST.json", "CHECKSUMS.sha256"):
            data = path.read_bytes()
            files.append(dict(path=path.relative_to(root).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    manifest = dict(schema="qpath-package-manifest-1", package=root.name, files=files)
    (root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    checks = [f["sha256"] + "  " + f["path"] for f in files]
    checks.append(hashlib.sha256((root / "MANIFEST.json").read_bytes()).hexdigest() + "  MANIFEST.json")
    (root / "CHECKSUMS.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="helper-probes-", dir=HERE) as temporary:
        base = Path(temporary)

        def fixture(label):
            root = base / label / SOURCE.name
            shutil.copytree(SOURCE, root)
            for name in ("verify_package.py", "startup_check.py"):
                shutil.copyfile(HERE / name, root / "tools" / name)
            rebuild(root)
            return root

        def reject(label, mutate):
            root = fixture(label)
            mutate(root)
            try:
                VERIFIER.verify(root)
            except (ValueError, OSError) as error:
                results.append(dict(probe=label, status="PASS", rejected_with=type(error).__name__ + ": " + str(error)))
            else:
                raise AssertionError(label + " incorrectly accepted")

        original = VERIFIER.verify(SOURCE)
        assert original["status"] == "PASS"
        results.append(dict(probe="unchanged_r3_package", status="PASS", files=original["files"]))
        assert VERIFIER.verify(fixture("baseline"))["status"] == "PASS"
        results.append(dict(probe="revised_helpers_in_valid_disposable_inventory", status="PASS"))

        def duplicate_checks(root):
            path = root / "CHECKSUMS.sha256"
            path.write_text(path.read_text("utf-8") + path.read_text("utf-8").splitlines()[0] + "\n", encoding="utf-8")

        def mutate_manifest(root, change):
            path = root / "MANIFEST.json"
            value = json.loads(path.read_text("utf-8"))
            change(value)
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")
            checks = root / "CHECKSUMS.sha256"
            lines = checks.read_text("utf-8").splitlines()
            lines = [(hashlib.sha256(path.read_bytes()).hexdigest() + "  MANIFEST.json") if line.endswith("  MANIFEST.json") else line for line in lines]
            checks.write_text("\n".join(lines) + "\n", encoding="utf-8")

        reject("duplicate_checksum_path", duplicate_checks)
        reject("duplicate_manifest_path", lambda r: mutate_manifest(r, lambda d: d["files"].append(dict(d["files"][0]))))
        reject("manifest_case_collision", lambda r: mutate_manifest(r, lambda d: d["files"].append({**d["files"][0], "path": d["files"][0]["path"].lower()})))
        reject("unsafe_manifest_path", lambda r: mutate_manifest(r, lambda d: d["files"][0].update(path="../escape.py")))
        reject("malformed_manifest_size", lambda r: mutate_manifest(r, lambda d: d["files"][0].update(bytes=True)))
        reject("changed_source", lambda r: (r / "payload/study/quantum/qstudy.py").write_text("# modified\n", encoding="utf-8"))
        reject("extra_file", lambda r: (r / "unexpected.txt").write_text("extra\n", encoding="utf-8"))
        reject("extra_empty_directory", lambda r: (r / "unexpected-directory").mkdir())

        link_root = fixture("directory_junction")
        junction = link_root / "linked"
        outside = base / "outside"
        outside.mkdir()
        # Native PowerShell creates the link; no destructive command crosses shells.
        command = f"New-Item -ItemType Junction -Path '{junction}' -Target '{outside}' | Out-Null"
        linked = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
        if linked.returncode == 0:
            try:
                VERIFIER.verify(link_root)
            except ValueError as error:
                assert "reparse" in str(error)
                results.append(dict(probe="directory_reparse_point", status="PASS", rejected_with=str(error)))
            else:
                raise AssertionError("junction accepted")
            # Remove only the junction itself; never recursively follow its target.
            junction.rmdir()
        else:
            results.append(dict(probe="directory_reparse_point", status="NOT_RUN", reason=linked.stderr))

        def startup(label, behavior=None, before=None):
            root = fixture(label)
            out = root.parent / "receipt.json"
            helper = module(root / "tools/startup_check.py", "probe_startup_" + label)
            if before:
                before(root, out)
            calls = []

            def fake(command, **kwargs):
                calls.append(command)
                assert kwargs["env"].get("PYTHONOPTIMIZE") is None
                assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
                if behavior:
                    value = behavior(root, out, len(calls), command, kwargs)
                    if value is not None:
                        return value
                return subprocess.CompletedProcess(command, 0, LABEL, "")

            stdout = io.StringIO()
            error = None
            with patch.dict(sys.modules, {"verify_package": VERIFIER}), patch.object(sys, "argv", [str(root / "tools/startup_check.py"), "--output", str(out)]), patch.object(helper.subprocess, "run", side_effect=fake), patch.dict("os.environ", {"PYTHONOPTIMIZE": "2"}), contextlib.redirect_stdout(stdout):
                try:
                    code = helper.main()
                except Exception as exception:
                    error = exception
                    code = None
            receipt = None
            if out.exists():
                try:
                    receipt = json.loads(out.read_text("utf-8"))
                except json.JSONDecodeError:
                    pass
            # Never retain mock-created PASS receipts as apparent startup evidence.
            if receipt is not None:
                out.write_text(json.dumps({"classification": LABEL, "observed_result": receipt}, indent=2), encoding="utf-8")
            return code, receipt, error, calls, out, stdout.getvalue()

        code, receipt, error, calls, _, _ = startup("mock_baseline")
        assert code == 0 and error is None and receipt["status"] == "PASS" and len(calls) == 4
        assert receipt["package_bytes_unchanged"] and receipt["integrity_before"] == receipt["integrity_after"]
        results.append(dict(probe="mock_unchanged_control_flow", status="PASS", classification=LABEL))

        code, receipt, error, calls, out, _ = startup("existing_receipt", before=lambda r, o: o.write_text("existing-sentinel", encoding="utf-8"))
        assert isinstance(error, FileExistsError) and not calls and out.read_text("utf-8") == "existing-sentinel"
        results.append(dict(probe="preexisting_receipt_preserved", status="PASS", classification=LABEL))

        def contender(root, out, count, command, kwargs):
            if count == 1:
                try:
                    with out.open("x") as handle:
                        handle.write("contender")
                except FileExistsError:
                    return None
                raise AssertionError("receipt was not reserved before child checks")

        code, receipt, _, _, _, _ = startup("concurrent_exclusive_receipt", behavior=contender)
        assert code == 0 and receipt["status"] == "PASS"
        results.append(dict(probe="receipt_reserved_before_child_checks", status="PASS", classification=LABEL))

        def clobber(root, out, count, command, kwargs):
            if count == 1:
                out.write_text("foreign-sentinel", encoding="utf-8")

        code, receipt, _, _, out, stdout = startup("foreign_receipt_content", behavior=clobber)
        assert code == 1 and receipt is None and out.read_text("utf-8") == "foreign-sentinel" and '"status": "FAIL"' in stdout
        results.append(dict(probe="foreign_receipt_content_preserved", status="PASS", classification=LABEL))

        code, receipt, _, calls, _, _ = startup("changed_before_startup", before=lambda r, o: (r / "payload/study/quantum/qstudy.py").write_text("# changed\n", encoding="utf-8"))
        assert code == 1 and receipt["status"] == "FAIL" and not calls
        results.append(dict(probe="prestartup_integrity_failure_stops_checks", status="PASS", classification=LABEL))

        def mutate_during(root, out, count, command, kwargs):
            if count == 1:
                with (root / "payload/study/quantum/qstudy.py").open("a", encoding="utf-8") as handle:
                    handle.write("\n# changed during mocked child\n")

        code, receipt, _, _, _, _ = startup("changed_during_startup", behavior=mutate_during)
        assert code == 1 and receipt["status"] == "FAIL" and not receipt["package_bytes_unchanged"]
        results.append(dict(probe="midstartup_integrity_failure", status="PASS", classification=LABEL))

        def mutate_and_rebind(root, out, count, command, kwargs):
            if count == 1:
                mutate_during(root, out, count, command, kwargs)
                rebuild(root)

        code, receipt, _, _, _, _ = startup("changed_and_rebound_during_startup", behavior=mutate_and_rebind)
        assert code == 1 and receipt["status"] == "FAIL" and receipt["integrity_after"]["status"] == "PASS" and not receipt["package_bytes_unchanged"]
        results.append(dict(probe="rebound_inventories_do_not_hide_midstartup_change", status="PASS", classification=LABEL))

        def timeout(root, out, count, command, kwargs):
            if count == 1:
                raise subprocess.TimeoutExpired(command, 90, output=b"partial output", stderr=b"partial error")

        code, receipt, _, _, _, _ = startup("child_timeout", behavior=timeout)
        assert code == 1 and receipt["status"] == "FAIL" and receipt["checks"][0]["status"] == "TIMEOUT"
        assert receipt["checks"][0]["stdout"] == "partial output"
        results.append(dict(probe="child_timeout_recorded_as_failure", status="PASS", classification=LABEL))

        def nonzero(root, out, count, command, kwargs):
            if count == 1:
                return subprocess.CompletedProcess(command, 7, "", "controlled error")

        code, receipt, _, _, _, _ = startup("child_nonzero", behavior=nonzero)
        assert code == 1 and receipt["status"] == "FAIL" and receipt["checks"][0]["returncode"] == 7
        results.append(dict(probe="child_nonzero_recorded_as_failure", status="PASS", classification=LABEL))

        def child_exception(root, out, count, command, kwargs):
            if count == 1:
                raise OSError("controlled launch failure")

        code, receipt, _, _, _, _ = startup("child_exception", behavior=child_exception)
        assert code == 1 and receipt["status"] == "FAIL" and receipt["checks"][0]["status"] == "ERROR"
        results.append(dict(probe="child_launch_error_recorded_as_failure", status="PASS", classification=LABEL))

    tested_files = []
    for name in ("verify_package.py", "startup_check.py", "test_helpers.py"):
        path = HERE / name
        data = path.read_bytes()
        tested_files.append(dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    report = dict(status="PASS_HELPER_REGRESSION_PROBES", recorded_at_utc=datetime.now(timezone.utc).isoformat(), classification="Actual validator checks and mocked startup control-flow checks only; not genuine numerical startup evidence", invocation=[sys.executable, "-B", str(Path(__file__).resolve())], python_version=sys.version, tested_files=tested_files, probes=results, genuine_startup_required_after_final_sealing=True)
    (HERE / "HELPER_TEST_RESULTS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
