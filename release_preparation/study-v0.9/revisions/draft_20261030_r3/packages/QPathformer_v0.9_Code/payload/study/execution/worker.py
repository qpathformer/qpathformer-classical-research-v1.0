"""One registered fit per process; durable ownership precedes scientific execution."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import runpy
import sys
import threading
import time
import traceback
from durable import (finish, get_attempt, now, read, require, sha, transaction, validate_manifest,
                     event, verify_endpoint, value_sha, write_new, TERMINAL, drain_control)
from process_identity import identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    request = read(args.request)
    root, attempt = Path(request["study_root"]), request["attempt_id"]
    require(sha(request["manifest_path"]) == request["manifest_sha256"], "Manifest changed")
    require(sha(request["release_path"]) == request["release_sha256"], "Release changed")
    manifest, release = validate_manifest(request["manifest_path"], request["release_path"])
    require(request["job"] in manifest["jobs"] and value_sha(request["job"]) == request["recipe_sha256"],
            "Attempt recipe changed")
    require(Path(request["metadata_dir"])/"REQUEST.json" == Path(args.request).resolve(), "Request identity mismatch")
    require(Path(sys.executable).resolve() == Path(manifest["interpreter"]["path"]).resolve(), "Interpreter mismatch")
    process_identity = identity()
    with transaction(root) as db:
        row = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt,)).fetchone()
        require(row is not None, "Unregistered attempt")
        if row["status"] != "launch_pending":
            # A competing/restarted bootstrap never executes the numerical trainer.
            return 73
        if drain_control(db) is not None:
            # This transaction orders admission against a drain, closing the parent/child race.
            event(db, row["job_id"], attempt, "bootstrap_deferred_by_drain", {})
            return 75
        require(row["job_id"] == request["job"]["run_id"] and row["endpoint"] == request["endpoint"], "Claim mismatch")
        require(not Path(request["endpoint"]).exists(), "Endpoint already exists")
        db.execute("UPDATE attempts SET status='running',identity_json=?,started_utc=? WHERE attempt_id=?",
                   (json.dumps(process_identity), now(), attempt))
        event(db, row["job_id"], attempt, "scientific_process_owned",
              {"process_identity": process_identity, "source": "same process loads trainer only after commit"})
    started = time.monotonic()
    stop = threading.Event()
    resource_lock = threading.Lock()

    def record_resources():
        with resource_lock:
            path = Path(request["metadata_dir"])/"PROCESS_RESOURCES.json"
            if path.exists():
                return read(path)
            from resource_probe import process_resources
            result = process_resources()
            result["seconds_since_durable_ownership"] = time.monotonic() - started
            write_new(path, result)
            return result

    def watchdog():
        while not stop.wait(0.1):
            try:
                state = get_attempt(root, attempt)
                if state["status"] in TERMINAL:
                    return
                if state["cancel_requested"] or time.monotonic() - started > manifest["deadline_seconds"]:
                    status = "interrupted" if state["cancel_requested"] else "timed_out"
                    finish(root, attempt, status, {"deadline_seconds": manifest["deadline_seconds"],
                        "elapsed_seconds": time.monotonic() - started, "process_identity": process_identity,
                        "partial_artifacts_preserved": True, "automatic_retry": False,
                        "process_resources": record_resources()})
                    os._exit(125 if status == "interrupted" else 124)
            except Exception:
                # A broken evidence channel cannot justify unbounded unattended computation.
                traceback.print_exc()
                os._exit(126)

    thread = threading.Thread(target=watchdog, name="qpath-deadline", daemon=True)
    thread.start()
    trainer = Path(manifest["trainer"]["path"])
    sys.path.insert(0, str(trainer.parent))
    sys.argv = [str(trainer), "--job-id", request["job"]["run_id"], "--output", request["endpoint"],
                "--authorization", manifest["authorization"]["path"]]
    try:
        if manifest["mode"] == "OFFICIAL_STUDY":
            from resource_probe import inspect
            actual = inspect()
            expected = manifest["numerical_environment"]
            for key in ("python", "numpy_version", "numpy_file", "openblas_dll",
                        "openblas_dll_sha256", "openblas_config", "effective_blas_threads"):
                require(actual[key] == expected[key], f"Effective numerical environment mismatch: {key}")
            require(actual["effective_blas_threads"] == 1, "Effective BLAS thread count is not one")
            write_new(Path(request["metadata_dir"])/"NUMERICAL_ENVIRONMENT.json", actual)
            with transaction(root) as db:
                event(db, request["job"]["run_id"], attempt, "effective_environment_verified", actual)
        try:
            runpy.run_path(str(trainer), run_name="__main__")
        except SystemExit as exc:
            require(exc.code in (None, 0), f"Trainer exited nonzero: {exc.code}")
        commit = verify_endpoint(request)
        finish(root, attempt, "succeeded", {"process_identity": process_identity,
               "process_resources": record_resources()}, commit)
        return 0
    except BaseException as error:
        traceback.print_exc()
        current = get_attempt(root, attempt)
        if current["status"] not in TERMINAL:
            finish(root, attempt, "failed", {"error_type": type(error).__name__, "error": str(error),
                   "partial_artifacts_preserved": True, "automatic_retry": False,
                   "process_resources": record_resources()})
        return 1
    finally:
        stop.set()
        thread.join(timeout=1)


if __name__ == "__main__":
    raise SystemExit(main())
