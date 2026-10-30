"""Bounded offline package startup. No training, scoring, shots or QPU submission."""
import argparse
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def exception_record(error):
    return {"type": type(error).__name__, "message": str(error)}


def captured_text(value):
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else (value or "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    requested = Path(args.output).absolute()
    out = requested.parent.resolve() / requested.name
    if out.is_relative_to(ROOT.resolve()):
        raise ValueError("Receipt must be outside the entire package")
    out.parent.mkdir(parents=True, exist_ok=True)

    # Reserve the path before doing any work. Never reopen it by pathname to write.
    # A pre-existing file, including a dangling symlink, makes this fail atomically.
    with out.open("x", encoding="utf-8", newline="\n") as receipt:
        checks, errors = [], []
        before, after = None, None
        interrupted = False
        parsed_python_files = 0
        numpy_version = None
        scipy_version = None
        methods = []
        tests_run = 0
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
        env.pop("PYTHONOPTIMIZE", None)

        def run(label, arguments, cwd):
            command = [sys.executable, "-B", *arguments]
            record = {"label": label, "command": command, "cwd": str(cwd)}
            try:
                child = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=90)
                record.update(status="PASS" if child.returncode == 0 else "FAIL", returncode=child.returncode, stdout=child.stdout, stderr=child.stderr)
            except subprocess.TimeoutExpired as error:
                record.update(status="TIMEOUT", returncode=None, stdout=captured_text(error.stdout), stderr=captured_text(error.stderr), error=exception_record(error))
            except Exception as error:
                record.update(status="ERROR", returncode=None, stdout="", stderr="", error=exception_record(error))
            checks.append(record)
            return record["status"] == "PASS"

        verify = None
        try:
            # Importing the adjacent verifier must not add a __pycache__ to the package.
            sys.dont_write_bytecode = True
            from verify_package import verify

            before = verify(ROOT)
            for source in ROOT.rglob("*.py"):
                ast.parse(source.read_text("utf-8-sig"), filename=str(source))
                parsed_python_files += 1
            quantum = ROOT / "payload/study/quantum"
            selected = (
                ("model shapes and paired initial predictions", "test_shapes_and_paired_initial_predictions"),
                ("independent circuit-state and moment agreement", "test_moments_and_state_against_independent_matrices"),
            )
            for label, test_name in selected:
                program = "\n".join([
                    "import json, socket, sys, unittest",
                    "def denied(*args, **kwargs): raise RuntimeError('Network disabled during bounded startup')",
                    "socket.create_connection = denied",
                    "socket.socket.connect = denied",
                    "socket.socket.connect_ex = denied",
                    "sys.path.insert(0, '..')",
                    "import numpy, scipy, circuits, models, routers, study, verification, test_models",
                    "suite = unittest.TestSuite([test_models.ModelTests(" + repr(test_name) + ")])",
                    "result = unittest.TextTestRunner(verbosity=2).run(suite)",
                    "print(json.dumps({'numpy_version': numpy.__version__, 'scipy_version': scipy.__version__, 'methods': list(models.METHODS), 'tests_run': result.testsRun}))",
                    "raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 1 else 1)",
                ])
                run(label, ["-c", program], quantum / "tests")
                if checks[-1]["status"] == "PASS":
                    observations = json.loads(checks[-1]["stdout"])
                    if observations["tests_run"] != 1:
                        raise ValueError("Selected child did not run exactly one test")
                    observed = (observations["numpy_version"], observations["scipy_version"], observations["methods"])
                    if tests_run and observed != (numpy_version, scipy_version, methods):
                        raise ValueError("Runtime or model inventory changed between checks")
                    numpy_version, scipy_version, methods = observed
                    tests_run += observations["tests_run"]
        except KeyboardInterrupt as error:
            interrupted = True
            errors.append({"phase": "startup", **exception_record(error)})
        except Exception as error:
            errors.append({"phase": "startup", **exception_record(error)})
        finally:
            if verify is not None:
                try:
                    after = verify(ROOT)
                except Exception as error:
                    errors.append({"phase": "integrity_after", **exception_record(error)})

        unchanged = before is not None and after is not None and before["package_fingerprint_sha256"] == after["package_fingerprint_sha256"]
        if before is not None and after is not None and not unchanged:
            errors.append({"phase": "integrity_after", "type": "ValueError", "message": "Package bytes changed during startup"})
        ok = unchanged and len(checks) == 2 and tests_run == 2 and not errors and all(check["status"] == "PASS" for check in checks)
        result = dict(status="PASS" if ok else "FAIL", recorded_at_utc=datetime.now(timezone.utc).isoformat(), python=sys.executable, python_version=sys.version, platform=platform.platform(), parsed_python_files=parsed_python_files, numpy_version=numpy_version, scipy_version=scipy_version, methods=methods, model_methods_checked=len(methods), tests_run=tests_run, integrity_before=before, integrity_after=after, package_bytes_unchanged=unchanged, checks=checks, errors=errors, scope="Exact package integrity before and after startup; all selected Python parsed; v0.5 numerical imports and exactly two selected tests: model parameter shapes/paired initial predictions and independent circuit-state/moment agreement. Network disabled in test subprocesses. No official input files used.", not_verified=["Clean-room dependency installation", "Full training or official scoring", "Datasets and selected checkpoints", "Full-archive relocation", "Shot sampling or noise experiments", "Hardware or QPU execution"])

        # Do not overwrite foreign content if another writer disregarded our reservation.
        owned = os.fstat(receipt.fileno())
        try:
            current = out.lstat()
            retained = not out.is_symlink() and not (getattr(current, "st_file_attributes", 0) & 0x400) and (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino) and owned.st_size == 0
        except OSError:
            retained = False
        if not retained:
            print(json.dumps({"status": "FAIL", "error": "Reserved receipt path or content changed; foreign content preserved", "checks": len(checks)}))
            return 1
        receipt.write(json.dumps(result, indent=2) + "\n")
        receipt.flush()
        print(json.dumps({"status": result["status"], "checks": len(checks)}))
        return 130 if interrupted else (0 if ok else 1)


if __name__ == "__main__":
    raise SystemExit(main())
