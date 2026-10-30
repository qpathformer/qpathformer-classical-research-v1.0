"""One same-process leased synthetic suite; never runs an official phase."""
from pathlib import Path
from datetime import datetime, timezone
from contextlib import redirect_stdout, redirect_stderr
import argparse
import hashlib
import json
import os
import sys
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")
SUITES = {"conversion": (HERE, "test_reference"),
          "timing": (HERE, "test_timing"),
          "reproduction": (ROOT/"analysis/independent_reproduction", "test_reproduction_audit")}


def binding(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def verify_registration(path):
    item = binding(path)
    registered = read(path)
    require(registered["schema"] == "qpath-v08-independent-fixture-registration-1" and
            registered["official_phase_authorized"] is False, "Wrong synthetic-only registration")
    require(registered["runner"] == binding(__file__), "Synthetic runner source changed")
    for expected in registered["sources"] + registered["protocols"]:
        require(Path(expected["path"]).resolve().is_relative_to(ROOT) and
                binding(expected["path"]) == expected, "Registered source or protocol changed")
    require(registered["suite_modules"] == {key: value[1] for key, value in SUITES.items()},
            "Synthetic suite selection changed")
    return item, registered


def run(args):
    for key in THREADS:
        os.environ[key] = "1"
    require(sys.dont_write_bytecode and sys.flags.utf8_mode == 1, "Use scientific Python -B -X utf8")
    for path in (args.receipt, args.log):
        require(path.resolve().parent == (HERE/"preflight").resolve() and not path.exists(),
                "Fresh independent-preflight receipt and log required")
    require(args.receipt.resolve() != args.log.resolve(), "Receipt and log must be distinct")
    sys.path.insert(0, str(ROOT/"execution"))
    import durable
    import resource_probe
    import process_identity
    with durable.auxiliary_lease(ROOT, "audit"):
        registration_binding, registration = verify_registration(args.registration)
        identity = process_identity.identity()
        require(identity is not None and identity["pid"] == os.getpid(), "Live lease owner identity missing")
        started = datetime.now(timezone.utc).isoformat()
        wall, cpu = time.perf_counter(), time.process_time()
        state = {"status": "ERROR", "tests": 0}
        observed = None
        with args.log.open("x", encoding="utf-8") as log:
            with redirect_stdout(log), redirect_stderr(log):
                try:
                    observed = resource_probe.inspect()
                    expected = read(ROOT/"governance/NUMERICAL_ENVIRONMENT.json")
                    for key in ("python", "interpreter", "numpy_version", "openblas_dll_sha256",
                                "openblas_config", "effective_blas_threads", "gpu_used"):
                        require(observed[key] == expected[key], "Scientific runtime differs: "+key)
                    require(observed["effective_blas_threads"] == 1 and observed["gpu_used"] is False,
                            "One-thread CPU fixture execution required")
                    directory, module = SUITES[args.suite]
                    sys.path.insert(0, str(directory))
                    tests = unittest.defaultTestLoader.loadTestsFromName(module)
                    result = unittest.TextTestRunner(stream=log, verbosity=2).run(tests)
                    verify_registration(args.registration)
                    require(binding(args.registration) == registration_binding, "Fixture registration drift")
                    require(process_identity.identity() == identity, "Lease owner identity changed")
                    require(resource_probe.inspect() == observed, "Numerical runtime changed during fixture checks")
                    state = {"status": "PASS" if result.wasSuccessful() else "FAIL",
                             "tests": result.testsRun, "failures": len(result.failures),
                             "errors": len(result.errors), "skipped": len(result.skipped)}
                    require(result.testsRun > 0 and not result.skipped, "Missing or skipped registered fixture cases")
                except BaseException as error:
                    state.update(status="ERROR", error=repr(error), traceback=traceback.format_exc())
                    traceback.print_exc()
                log.flush()
        receipt = {"schema": "qpath-v08-independent-fixture-receipt-1", **state,
                   "suite": args.suite, "started_utc": started,
                   "finished_utc": datetime.now(timezone.utc).isoformat(),
                   "wall_seconds": time.perf_counter()-wall,
                   "process_cpu_seconds": time.process_time()-cpu,
                   "process_identity": identity, "same_process_lease_and_tests": True,
                   "registration": registration_binding, "sources": registration["sources"],
                   "protocols": registration["protocols"], "log": binding(args.log),
                   "runtime_observed": observed,
                   "process_resources": {**resource_probe.process_resources(),
                       "scope": "Whole independent synthetic fixture process through sampling; phase counters include runtime probe and fixture imports/execution after source registration."},
                   "scope": "Synthetic arrays, inert temporary commits and active protocol/source metadata only. No official data arrays, checkpoints, model outcomes, timing sessions or numerical study phases.",
                   "official_arrays_or_outcomes_accessed": False, "official_phase_executed": False}
        write_new(args.receipt, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=tuple(SUITES), required=True)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps({key: result[key] for key in ("suite", "status", "tests", "wall_seconds", "process_cpu_seconds")}))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
