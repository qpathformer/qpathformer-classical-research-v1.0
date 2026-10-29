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
            quantum = ROOT / "payload/study/quantum"
            run("numeric imports and in-memory predictions", ["-c", 'import json, numpy as np; import qstudy as s\nx=np.array([[0.,0.],[.1,-.3],[-.6,.7],[.9,.9]]); d=np.array([1,2,3,4]); route=np.array([0,1,2,3]); counts={}\nfor method in s.METHODS:\n m=s.Model(method,902); p=m.predict(x,d); assert p.shape==(4,) and np.isfinite(p).all() and ((p>=0)&(p<=1)).all(); counts[method]=len(m.parameters)\nprint(json.dumps({"model_parameter_counts":counts,"finite_in_memory_predictions":True}))'], quantum)
            run("training CLI argument help", ["qstudy.py", "--help"], quantum)
            run("independent matrix or initialization invariant", ["-m", "unittest", "test_v02.MechanismChecks.test_untied_initialization_matches_original_prefix"], quantum / "tests")
            if (ROOT / "payload/study/classical").exists():
                code = "import json, torch; from dataclasses import replace; from qpath.classical import ModelConfig,QPathTextModel; torch.set_num_threads(1); c=replace(ModelConfig.smoke(),dropout=0.,labels=14); m=QPathTextModel(c).eval(); m.route_mode='shared'; x=torch.tensor([[8,9,0],[10,11,12]]); mask=x!=0; result=m(x,mask)['logits']; assert result.shape==(2,14) and torch.isfinite(result).all(); print(json.dumps({'torch':torch.__version__,'shape':list(result.shape),'training_updates':0}))"
                run("classical CPU forward without updates", ["-c", code], ROOT / "payload/study/classical")
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
        ok = unchanged and bool(checks) and not errors and all(check["status"] == "PASS" for check in checks)
        result = dict(status="PASS" if ok else "FAIL", recorded_at_utc=datetime.now(timezone.utc).isoformat(), python=sys.executable, python_version=sys.version, platform=platform.platform(), integrity_before=before, integrity_after=after, package_bytes_unchanged=unchanged, checks=checks, errors=errors, scope="Exact package integrity before and after startup; all selected Python parsed; source-specific imports and deterministic in-memory predictions, CLI help and one explicit nontraining invariant; v0.2 additionally a CPU text forward. No official input files used.", not_verified=["Clean-room dependency installation", "Full training or official scoring", "Datasets and selected checkpoints", "Full-archive relocation", "Shot sampling or noise experiments", "Hardware or QPU execution"])

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
