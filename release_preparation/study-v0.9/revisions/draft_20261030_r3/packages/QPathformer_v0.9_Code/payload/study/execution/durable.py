"""Durable, bounded whole-fit orchestration for Q-Path Multiplier (ETEL).

This module contains no numerical model code and no test-data evaluator.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor"))
from etel.core import Config, Task, run_tasks
from process_identity import alive, identity

TERMINAL = {"succeeded", "failed", "timed_out", "interrupted", "invalid_commit", "orphaned"}
PHASE_COUNTS = {"engineering": 48, "A": 72, "B": 636}
MANIFEST_SCHEMA = "qpath.v09.etel.bound-stage.v1"
AUTHORIZATION_SCHEMA = "qpath-v09-stage-authorization-1"
ENDPOINT_SCHEMA = "qpath-v09-endpoint-1"
THREAD_ENV = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                               "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}

def physical_stage(stage):
    return {"engineering": "engineering", "development": "A", "confirmation": "B", "A": "A", "B": "B"}[stage]


def stage_jobs(matrix, stage):
    return [x for x in matrix["runs"] if physical_stage(x["stage"]) == stage]


def now():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def value_sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_new(path, value):
    path = Path(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def binding(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def verify_binding(item):
    path = Path(item["path"])
    require(path.is_absolute() and path.is_file(), f"Missing bound file: {path}")
    require(sha(path) == item["sha256"] and path.stat().st_size == item["bytes"],
            f"Bound file changed: {path}")
    return path


def inside(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    require(path.is_relative_to(root), f"Path escapes study root: {path}")
    return path


@contextmanager
def exclusive_lock(root):
    """Kernel-backed lock automatically releases if an orchestrator dies."""
    state = Path(root) / "execution" / "state"
    state.mkdir(parents=True, exist_ok=True)
    path = state / "compute.lock"
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError("Another execution/timing coordinator holds the compute lease") from error
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError("Another execution/timing coordinator holds the compute lease") from error
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def connect(root):
    folder = Path(root) / "execution" / "state"
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder / "ledger.sqlite3", timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("PRAGMA busy_timeout=30000")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS jobs(
        job_id TEXT PRIMARY KEY, recipe_sha TEXT NOT NULL, manifest_sha TEXT NOT NULL,
        phase TEXT NOT NULL, current_attempt TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS attempts(
        attempt_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, metadata_dir TEXT NOT NULL,
        endpoint TEXT NOT NULL, status TEXT NOT NULL, identity_json TEXT,
        started_utc TEXT, finished_utc TEXT, commit_sha TEXT, failure_json TEXT,
        cancel_requested INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS journal(
        sequence INTEGER PRIMARY KEY AUTOINCREMENT, utc TEXT NOT NULL,
        job_id TEXT, attempt_id TEXT, event TEXT NOT NULL, details_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS controls(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
    """)
    return db


@contextmanager
def transaction(root):
    db = connect(root)
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def event(db, job_id, attempt_id, name, details):
    db.execute("INSERT INTO journal(utc,job_id,attempt_id,event,details_json) VALUES(?,?,?,?,?)",
               (now(), job_id, attempt_id, name, json.dumps(details, allow_nan=False)))


def get_attempt(root, attempt_id):
    db = connect(root)
    try:
        row = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        require(row is not None, "Unknown attempt")
        return dict(row)
    finally:
        db.close()


def current_attempts(root):
    db = connect(root)
    try:
        return [dict(x) for x in db.execute(
            "SELECT a.*,j.phase,j.recipe_sha,j.manifest_sha FROM attempts a JOIN jobs j "
            "ON j.current_attempt=a.attempt_id ORDER BY j.job_id")]
    finally:
        db.close()


def drain_control(db):
    row = db.execute("SELECT value_json FROM controls WHERE key='drain'").fetchone()
    return None if row is None else json.loads(row["value_json"])


def current_drain(root):
    db = connect(root)
    try:
        return drain_control(db)
    finally:
        db.close()


def request_drain(root, reason):
    """Stop admitting new fits; running fits retain their full budgets."""
    require(isinstance(reason, str) and reason.strip(), "A drain reason is required")
    with transaction(root) as db:
        existing = drain_control(db)
        if existing is not None:
            verify_binding(existing)
            return {"status": "already_draining", "request": existing}
        folder = Path(root)/"execution"/"control_history"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder/("drain_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")+".json")
        write_new(path, {"schema": "qpath.v09.etel.drain-request.v1", "utc": now(),
                        "reason": reason, "running_fits": "finish full registered budget",
                        "pending_fits": "remain unstarted", "automatic_resume": False})
        item = binding(path)
        db.execute("INSERT INTO controls VALUES('drain',?)", (json.dumps(item),))
        event(db, None, None, "drain_requested", item)
    return {"status": "drain_requested", "request": item}


def clear_drain(root, approval_path):
    """Root must explicitly bind the drain and a renewed budget/usage review."""
    approval_path = inside(root, approval_path)
    approval = read(approval_path)
    require(approval.get("review_status") == "approved_by_root" and
            approval.get("action") == "resume_after_drain", "Root resume approval required")
    verify_binding(approval["usage_review"])
    with transaction(root) as db:
        active = drain_control(db)
        require(active is not None and approval.get("drain_request") == active,
                "Resume approval must bind the active drain request")
        verify_binding(active)
        db.execute("DELETE FROM controls WHERE key='drain'")
        event(db, None, None, "drain_cleared_by_root", {"drain_request": active,
                                                       "approval": binding(approval_path)})
    return {"status": "drain_cleared", "approval": binding(approval_path)}


def status_summary(root):
    """Cheap read-only ledger snapshot; does not reconcile, launch or score."""
    path = Path(root).resolve()/"execution/state/ledger.sqlite3"
    if not path.is_file():
        return {"status": "not_initialized", "utc": now(), "phases": {}, "drain": None}
    db = sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        groups = [dict(row) for row in db.execute("SELECT j.phase,a.status,COUNT(*) AS count FROM jobs j "
            "JOIN attempts a ON a.attempt_id=j.current_attempt GROUP BY j.phase,a.status ORDER BY j.phase,a.status")]
        return {"status": "ledger_snapshot_only", "utc": now(), "groups": groups,
                "total_attempts": db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
                "drain": drain_control(db), "process_liveness_checked": False,
                "test_outcomes_read": False}
    finally:
        db.close()


def record_process_closure(root, row, observed=None, child_exit_code=None):
    """Retain native evidence before the OS can reuse an exited worker's PID."""
    require(row["status"] in TERMINAL and row["identity_json"], "Terminal owned process required")
    expected = json.loads(row["identity_json"])
    require(observed is None or (observed["pid"] == expected["pid"] and
            observed["creation_token"] != expected["creation_token"]), "Original process is still live")
    path = Path(row["metadata_dir"])/"PROCESS_CLOSED.json"
    if path.exists():
        return binding(path)
    terminal = Path(row["metadata_dir"])/"TERMINAL.json"
    require(terminal.is_file(), "Terminal evidence must precede native closure")
    record = {"schema": "qpath.v09.etel.native-process-closure.v1", "utc": now(),
              "job_id": row["job_id"], "attempt_id": row["attempt_id"], "expected": expected,
              "observed": observed, "same_live_identity": False, "terminal": binding(terminal),
              "native_basis": "Popen native child handle wait" if child_exit_code is not None else
                              "native identity absent or distinct creation token",
              "child_exit_code": child_exit_code}
    with transaction(root) as db:
        if not path.exists():
            write_new(path, record)
            event(db, row["job_id"], row["attempt_id"], "native_process_closed", binding(path))
    return binding(path)


def process_is_closed(root, row, record=True):
    """Unknown liveness fails closed; exact retained proof only covers error 5."""
    if not row["identity_json"]:
        return True
    expected = json.loads(row["identity_json"])
    try:
        observed = identity(expected["pid"])
    except OSError as error:
        code = getattr(error, "winerror", None) or error.errno
        path = Path(row["metadata_dir"])/"PROCESS_CLOSED.json"
        require(code == 5 and row["status"] in TERMINAL and path.is_file(),
                "Native identity unavailable without exact prior closure; fail closed")
        proof = read(path)
        require(proof.get("schema") == "qpath.v09.etel.native-process-closure.v1" and
                proof.get("job_id") == row["job_id"] and proof.get("attempt_id") == row["attempt_id"] and
                proof.get("expected") == expected and proof.get("same_live_identity") is False,
                "Prior process closure identity differs")
        terminal = read(verify_binding(proof["terminal"]))
        require(terminal["attempt_id"] == row["attempt_id"] and terminal["status"] == row["status"] and
                terminal["job_id"] == row["job_id"] and
                datetime.fromisoformat(terminal["utc"]) <= datetime.fromisoformat(proof["utc"]),
                "Prior process closure terminal differs")
        observed = proof["observed"]
        require(observed is None or (observed["pid"] == expected["pid"] and
                observed["creation_token"] != expected["creation_token"]), "Prior native observation invalid")
        db = connect(root)
        try:
            events = [json.loads(x[0]) for x in db.execute(
                "SELECT details_json FROM journal WHERE attempt_id=? AND event='native_process_closed'",
                (row["attempt_id"],))]
            require(binding(path) in events, "Prior native closure lacks its durable hash binding")
        finally:
            db.close()
        return True
    if observed == expected:
        return False
    if record and row["status"] in TERMINAL:
        record_process_closure(root, row, observed=observed)
    return True


def await_process_closure(root, row, timeout=10):
    started = time.monotonic()
    while not process_is_closed(root, row):
        require(time.monotonic() - started <= timeout,
                "Terminal scientific process has not exited; preserve state and fail closed")
        time.sleep(0.05)


def validate_manifest(path, release_path):
    path, release_path = Path(path).resolve(), Path(release_path).resolve()
    manifest, release = read(path), read(release_path)
    require(manifest.get("schema") == MANIFEST_SCHEMA, "Wrong execution schema")
    require(release.get("review_status") == "approved_by_root", "Root execution release missing")
    require(release.get("manifest_sha256") == sha(path), "Execution release does not bind this manifest")
    root = Path(manifest["study_root"]).resolve()
    inside(root, path)
    inside(root, release_path)
    phase = manifest["stage"]
    require(phase in PHASE_COUNTS and release.get("stage") == phase, "Stage mismatch")
    require(type(manifest["max_parallel_tasks"]) is int and 1 <= manifest["max_parallel_tasks"] <= 5,
            "Training concurrency must be 1..5")
    require(type(manifest["deadline_seconds"]) in (int, float) and 0 < manifest["deadline_seconds"] <= 86400,
            "Explicit positive bounded deadline required")
    for item in manifest["bindings"]:
        verify_binding(item)
    for item in (manifest["interpreter"], manifest["trainer"], manifest["authorization"],
                 manifest["matrix"], manifest["protocol"]):
        verify_binding(item)
    inside(root, manifest["trainer"]["path"])
    inside(root, manifest["authorization"]["path"])
    matrix = read(manifest["matrix"]["path"])
    jobs = stage_jobs(matrix, phase)
    require(manifest["jobs"] == jobs, "Bound jobs differ from exact matrix stage or order")
    require(len({x["run_id"] for x in jobs}) == len(jobs), "Duplicate canonical run IDs")
    fixture = manifest.get("mode") == "EXECUTION_TEST_FIXTURE_ONLY"
    if fixture:
        require("execution_test_" in root.name, "Fixture mode requires a dedicated test root")
        require(Path(manifest["trainer"]["path"]).name == "synthetic_trainer.py", "Fixture runner mismatch")
    else:
        require(manifest.get("mode") == "OFFICIAL_STUDY", "Explicit official/fixture mode required")
        require(root == HERE.parent, "Official execution root differs from this v0.9 execution copy")
        require(Path(manifest["matrix"]["path"]).resolve() == root/"governance/RUN_MATRIX.json" and
                Path(manifest["protocol"]["path"]).resolve() == root/"governance/STUDY_PLAN.json",
                "Official authority must be this study's active matrix and plan")
        active_protocol = read(manifest["protocol"]["path"])
        require(manifest["deadline_seconds"] == active_protocol["execution_layer"]["deadline_per_fit_seconds"],
                "Official deadline differs from approved study plan")
        ceiling = active_protocol["execution_layer"]["resource_ceiling"]
        require(isinstance(ceiling, dict) and all(type(ceiling.get(k)) is int for k in
                ("max_parallel", "max_workers", "blas_threads_per_worker")),
                "Resource ceiling requires explicit integer parallel, worker and BLAS limits")
        require(1 <= ceiling["max_parallel"] <= ceiling["max_workers"] <= 5 and
                ceiling["blas_threads_per_worker"] == 1,
                "Resource ceiling violates five-worker single-BLAS-thread study limit")
        require(manifest["max_parallel_tasks"] <= ceiling["max_parallel"],
                "Concurrency exceeds approved resource ceiling")
        require(Path(manifest["interpreter"]["path"]).resolve() ==
                Path(active_protocol["runtime"]["scientific_python"]).resolve(), "Official interpreter differs from study plan")
        numerical = manifest["numerical_environment"]
        require(numerical["python"] == active_protocol["runtime"]["python"] and
                numerical["numpy_version"] == active_protocol["runtime"]["numpy"] and
                numerical["effective_blas_threads"] == ceiling["blas_threads_per_worker"] ==
                active_protocol["runtime"]["blas_threads"], "Numerical preflight differs from approved runtime")
        require(len(jobs) == PHASE_COUNTS[phase], "Incomplete official stage inventory")
        require(Path(manifest["trainer"]["path"]).resolve() == root/"quantum"/"study.py",
                "Official scientific runner must be quantum/study.py")
        from bind_stage import EXECUTION_FILES
        bound_paths = {Path(x["path"]).resolve() for x in manifest["bindings"]}
        require(all((HERE/name).resolve() in bound_paths for name in EXECUTION_FILES),
                "Execution source is not completely bound")
    authorization = read(manifest["authorization"]["path"])
    require(authorization.get("schema") == AUTHORIZATION_SCHEMA and
            authorization.get("review_status") == "approved_by_root" and
            authorization.get("stage") == phase, "Scientific stage authorization missing")
    require(authorization.get("run_ids") == [x["run_id"] for x in jobs], "Scientific authorization IDs changed")
    require(authorization.get("matrix_sha256") == manifest["matrix"]["sha256"], "Matrix freeze mismatch")
    require(authorization.get("protocol_sha256") == manifest["protocol"]["sha256"], "Protocol freeze mismatch")
    if not fixture:
        require(authorization["data_seal_sha256"] == sha(root/"quantum/data/DATA_SEAL.json"), "Data seal mismatch")
        for name, expected in authorization["scientific_source_hashes"].items():
            require(sha(inside(root/"quantum", root/"quantum"/name)) == expected, "Scientific source mismatch")
        required = {"engineering": None, "A": ("engineering", 48), "B": ("A", 72)}[phase]
        if required:
            gate = release.get("predecessor_audit")
            require(isinstance(gate, dict), "Independent predecessor audit required")
            audit = read(verify_binding(gate))
            require(audit.get("status") == "PASS" and audit.get("stage") == required[0] and
                    audit.get("verified_endpoints") == required[1], "Predecessor audit incomplete")
            verify_receipt_endpoints(root, audit, required[0], required[1])
    return manifest, release


def verify_receipt_endpoints(root, receipt, stage, count):
    """Gate receipts must enumerate actual commit bindings, not just an integer."""
    records = receipt.get("endpoints", [])
    require(len(records) == count, "Audit must enumerate every endpoint")
    require(len({r["job_id"] for r in records}) == count, "Audit endpoint IDs are not unique")
    matrix = Path(root)/"governance/RUN_MATRIX.json"
    require(matrix.is_file(), "Audited endpoint gate requires authoritative run matrix")
    expected_ids = {j["run_id"] for j in stage_jobs(read(matrix), stage)}
    require({r["job_id"] for r in records} == expected_ids, "Audit endpoints do not match exact matrix stage")
    for item in records:
        commit_path = verify_binding(item["commit"])
        inside(root, commit_path)
        commit = read(commit_path)
        require(commit.get("job_id") == item["job_id"] and commit.get("stage") == stage and
                commit.get("status") == "completed" and commit.get("test_accessed") is False,
                "Audit endpoint commit identity mismatch")
        request_path = commit_path.parent.parent/"REQUEST.json"
        require(request_path.is_file(), "Audited endpoint lacks its durable attempt binding")
        request = read(request_path)
        exact_job = next(j for j in stage_jobs(read(matrix), stage) if j["run_id"] == item["job_id"])
        require(request["job"] == exact_job, "Audited attempt recipe differs from authoritative matrix")
        require(Path(request["endpoint"]).resolve() == commit_path.parent.resolve(), "Audit request endpoint differs")
        require(verify_endpoint(request) == item["commit"]["sha256"], "Audited payloads differ from committed evidence")


def verify_endpoint(request):
    manifest = read(request["manifest_path"])
    require(sha(request["manifest_path"]) == request["manifest_sha256"], "Attempt manifest changed")
    job = request["job"]
    endpoint = Path(request["endpoint"])
    commit_path = endpoint/"endpoint_commit.json"
    commit = read(commit_path)
    require(commit.get("status") == "completed" and commit.get("job_id") == job["run_id"] and
            commit.get("stage") == physical_stage(job["stage"]) and commit.get("test_accessed") is False,
            "Endpoint commit identity/status mismatch")
    require(commit.get("authorization_sha256") == manifest["authorization"]["sha256"],
            "Endpoint authorization mismatch")
    require(commit.get("arm") == job["arm"] and commit.get("seed") == job["training_seed_id"] and
            commit.get("population") == job["population_id"], "Endpoint recipe mismatch")
    expected_files = commit.get("files", {})
    require("result.json" in expected_files and "config.json" in expected_files, "Missing required committed evidence")
    for name, info in expected_files.items():
        file = inside(endpoint, endpoint/name)
        require(file.is_file() and sha(file) == info["sha256"] and file.stat().st_size == info["bytes"],
                f"Endpoint evidence changed: {name}")
    actual = {p.relative_to(endpoint).as_posix() for p in endpoint.rglob("*") if p.is_file()}
    require(actual == set(expected_files) | {"endpoint_commit.json"}, "Uncommitted endpoint files present")
    result, config = read(endpoint/"result.json"), read(endpoint/"config.json")
    require(result.get("status") == "completed" and result.get("completed_rounds") == job["rounds"] and
            result.get("optimizer_global_updates") == job["updates"] and
            result.get("test_accessed") is False, "Endpoint budget/test invariant failed")
    require(config.get("test_accessed") is False, "Configuration reports test access")
    auth = read(manifest["authorization"]["path"])
    if manifest["mode"] == "OFFICIAL_STUDY":
        require(commit.get("schema") == ENDPOINT_SCHEMA, "Committed endpoint schema mismatch")
        require(commit.get("source_hashes") == auth["scientific_source_hashes"], "Committed source mismatch")
        require(commit.get("data_seal_sha256") == auth["data_seal_sha256"], "Committed data seal mismatch")
        require(commit.get("matrix_sha256") == auth["matrix_sha256"] and
                commit.get("protocol_sha256") == auth["protocol_sha256"], "Committed protocol/matrix mismatch")
    return sha(commit_path)


def finish(root, attempt_id, status, details=None, commit_sha=None):
    details = {} if details is None else details
    with transaction(root) as db:
        row = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        require(row is not None, "Attempt missing")
        if row["status"] in TERMINAL:
            require(row["status"] == status, "Attempt already terminal with a different outcome")
            return
        db.execute("UPDATE attempts SET status=?,finished_utc=?,commit_sha=?,failure_json=? WHERE attempt_id=?",
                   (status, now(), commit_sha, json.dumps(details), attempt_id))
        event(db, row["job_id"], attempt_id, status, details | {"commit_sha256": commit_sha})
    record = Path(row["metadata_dir"])/"TERMINAL.json"
    if not record.exists():
        write_new(record, {"status": status, "attempt_id": attempt_id, "job_id": row["job_id"],
                           "utc": now(), "commit_sha256": commit_sha, "details": details})


def reconcile(root, row):
    request = read(Path(row["metadata_dir"])/"REQUEST.json")
    if row["status"] == "succeeded":
        require(verify_endpoint(request) == row["commit_sha"], "Completed endpoint changed; do not rerun")
    elif row["status"] == "running":
        pid = json.loads(row["identity_json"])
        if not alive(pid):
            if (Path(row["endpoint"])/"endpoint_commit.json").exists():
                try:
                    digest = verify_endpoint(request)
                except Exception as error:
                    finish(root, row["attempt_id"], "invalid_commit", {"error": repr(error)})
                else:
                    finish(root, row["attempt_id"], "succeeded", {"reconciled_after_process_exit": True}, digest)
            else:
                finish(root, row["attempt_id"], "orphaned",
                       {"reason": "Recorded process identity is no longer live and endpoint is incomplete",
                        "automatic_retry": False})
    return get_attempt(root, row["attempt_id"])


def new_attempt(root, manifest_path, release_path, job, recovery=None):
    manifest = read(manifest_path)
    manifest_digest, recipe = sha(manifest_path), value_sha(job)
    job_id = job["run_id"]
    with transaction(root) as db:
        existing = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if existing:
            require(existing["recipe_sha"] == recipe and existing["manifest_sha"] == manifest_digest,
                    "Existing job binding differs; refuse identity reuse")
            prior = dict(db.execute("SELECT * FROM attempts WHERE attempt_id=?", (existing["current_attempt"],)).fetchone())
            if recovery is None:
                return prior
            require(prior["status"] in TERMINAL - {"succeeded"}, "Recovery requires a preserved unsuccessful terminal attempt")
            require(process_is_closed(root, prior, record=False), "Prior process is still live")
            approval = read(recovery)
            require(approval.get("review_status") == "approved_by_root" and
                    approval.get("job_id") == job_id and approval.get("previous_attempt_id") == prior["attempt_id"] and
                    approval.get("manifest_sha256") == manifest_digest and approval.get("recipe_sha256") == recipe and
                    approval.get("recovery_action") == "fresh_same_recipe_attempt", "Recovery approval mismatch")
        else:
            require(recovery is None, "No prior attempt to recover")
        key = hashlib.sha256(job_id.encode()).hexdigest()[:24]
        parent = Path(root)/"execution"/"attempts"/key
        parent.mkdir(parents=True, exist_ok=True)
        number = 1
        while (parent/f"attempt_{number:04d}").exists():
            number += 1
        directory = parent/f"attempt_{number:04d}"
        directory.mkdir()
        attempt_id = f"{key}-{number:04d}"
        endpoint = directory/"endpoint"
        request = {"schema": "qpath.v09.etel.attempt.v1", "job": job, "recipe_sha256": recipe,
                   "attempt_id": attempt_id, "study_root": str(root), "manifest_path": str(Path(manifest_path).resolve()),
                   "manifest_sha256": manifest_digest, "release_path": str(Path(release_path).resolve()),
                   "release_sha256": sha(release_path), "metadata_dir": str(directory),
                   "endpoint": str(endpoint), "created_utc": now(),
                   "recovery_approval": None if recovery is None else binding(recovery)}
        write_new(directory/"REQUEST.json", request)
        db.execute("INSERT INTO attempts(attempt_id,job_id,metadata_dir,endpoint,status) VALUES(?,?,?,?,?)",
                   (attempt_id, job_id, str(directory), str(endpoint), "launch_pending"))
        if existing:
            db.execute("UPDATE jobs SET current_attempt=? WHERE job_id=?", (attempt_id, job_id))
        else:
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", (job_id, recipe, manifest_digest, physical_stage(job["stage"]), attempt_id))
        event(db, job_id, attempt_id, "claimed", {"request_sha256": sha(directory/"REQUEST.json"),
              "recovery_approval": request["recovery_approval"]})
    return get_attempt(root, attempt_id)


def request_cancel(root, attempt_id, reason):
    with transaction(root) as db:
        row = db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        require(row is not None, "Unknown attempt")
        if row["status"] not in TERMINAL:
            db.execute("UPDATE attempts SET cancel_requested=1 WHERE attempt_id=?", (attempt_id,))
            event(db, row["job_id"], attempt_id, "cancel_requested", {"reason": reason})


def supervise(root, row, manifest):
    import subprocess
    row = reconcile(root, row)
    process = None
    if row["status"] == "launch_pending":
        if current_drain(root) is not None:
            return {"job_id": row["job_id"], "attempt_id": row["attempt_id"], "status": "deferred_by_drain"}
        # Multiple pre-bootstrap candidates are safe: worker CAS wins before any trainer code.
        request_path = Path(row["metadata_dir"])/"REQUEST.json"
        command = [manifest["interpreter"]["path"], "-B", "-X", "utf8", str(HERE/"worker.py"),
                   "--request", str(request_path)]
        environment = os.environ.copy()
        environment.update(THREAD_ENV)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["QPATH_ETEL_WHOLE_FIT"] = "1"
        # Append preserves launch observations if a parent died before a pending bootstrap began.
        with (Path(row["metadata_dir"])/"stdout.log").open("a", encoding="utf-8") as out, (
              Path(row["metadata_dir"])/"stderr.log").open("a", encoding="utf-8") as err:
            process = subprocess.Popen(command, cwd=Path(manifest["trainer"]["path"]).parent,
                env=environment, stdout=out, stderr=err, shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        with transaction(root) as db:
            event(db, row["job_id"], row["attempt_id"], "bootstrap_launched",
                  {"candidate_pid": process.pid, "command": command, "identity_registered_by_child_before_science": True})
    pending_started = time.monotonic()
    while True:
        row = reconcile(root, get_attempt(root, row["attempt_id"]))
        if row["status"] in TERMINAL:
            if process is not None:
                exit_code = process.wait(timeout=10)
                if row["identity_json"]:
                    if json.loads(row["identity_json"])["pid"] == process.pid:
                        record_process_closure(root, row, child_exit_code=exit_code)
                    else:
                        # Windows venv redirectors may own a different bootstrap PID.
                        # Its exit is not proof about the registered scientific identity.
                        await_process_closure(root, row)
            elif row["identity_json"]:
                # Adopted workers may commit before exiting; wait for exact native absence.
                await_process_closure(root, row)
            return {"job_id": row["job_id"], "status": row["status"], "attempt_id": row["attempt_id"],
                    "endpoint": row["endpoint"], "commit_sha256": row["commit_sha"]}
        if row["status"] == "launch_pending" and process is not None and process.poll() is not None:
            if process.returncode == 75 and current_drain(root) is not None:
                return {"job_id": row["job_id"], "attempt_id": row["attempt_id"], "status": "deferred_by_drain"}
            finish(root, row["attempt_id"], "failed", {"reason": "Bootstrap exited before claiming",
                   "exit_code": process.returncode, "automatic_retry": False})
        elif row["status"] == "launch_pending" and time.monotonic() - pending_started > 60:
            raise RuntimeError("Bootstrap pending >60 seconds; do not automatically retry")
        time.sleep(0.1)


def run_stage(manifest_path, release_path):
    manifest, release = validate_manifest(manifest_path, release_path)
    root = Path(manifest["study_root"])
    with exclusive_lock(root):
        # A different phase cannot race live workers retained after orchestrator loss.
        for row in current_attempts(root):
            row = reconcile(root, row)
            if row["status"] not in TERMINAL:
                request = read(Path(row["metadata_dir"])/"REQUEST.json")
                require(request["manifest_sha256"] == sha(manifest_path), "Another stage has pending/live work")
            else:
                require(process_is_closed(root, row), "A terminal worker is still exiting; do not admit another stage")
        rows = [reconcile(root, new_attempt(root, manifest_path, release_path, job)) for job in manifest["jobs"]]
        terminal_failures = [r for r in rows if r["status"] in TERMINAL - {"succeeded"}]
        require(not terminal_failures, "Preserved unsuccessful attempts require root-reviewed recovery before continuation")
        # Adopt all surviving scientific processes before admitting any new ones.
        rows.sort(key=lambda r: {"running": 0, "launch_pending": 1, "succeeded": 2}[r["status"]])
        with transaction(root) as db:
            event(db, None, None, "stage_supervision_started", {"stage": manifest["stage"], "manifest_sha256": sha(manifest_path)})
        import signal
        import threading
        prior_signal = None
        if threading.current_thread() is threading.main_thread():
            prior_signal = signal.getsignal(signal.SIGINT)
            def interrupt(signum, frame):
                for item in current_attempts(root):
                    if item["status"] not in TERMINAL:
                        request_cancel(root, item["attempt_id"], "orchestrator_keyboard_interrupt")
                raise KeyboardInterrupt
            signal.signal(signal.SIGINT, interrupt)
        try:
            result = run_tasks([Task(row["job_id"], {"attempt_id": row["attempt_id"]}) for row in rows],
                 lambda task: supervise(root, get_attempt(root, task.payload["attempt_id"]), manifest),
                 Config(min_blocks=1, max_blocks=3, max_parallel_tasks=manifest["max_parallel_tasks"]))
        except BaseException:
            for row in current_attempts(root):
                if row["status"] not in TERMINAL:
                    request_cancel(root, row["attempt_id"], "orchestrator_interrupted")
            raise
        finally:
            if prior_signal is not None:
                signal.signal(signal.SIGINT, prior_signal)
        outcomes = [r.get("output", {}).get("status") for r in result["results"]]
        success = all(x == "succeeded" for x in outcomes)
        drained = not success and all(x in ("succeeded", "deferred_by_drain") for x in outcomes)
        final_status = "completed" if success else "drained" if drained else "failures_present"
        with transaction(root) as db:
            event(db, None, None, "stage_supervision_finished",
                  {"stage": manifest["stage"], "succeeded": success, "total": len(rows), "etel_summary": result["summary"]})
        # Durable detailed export complements the transactional journal.
        report_dir = root/"execution"/"stage_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir/(manifest["stage"]+"_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")+".json")
        write_new(report_path, {"schema": "qpath.v09.etel.stage-observation.v1", "stage": manifest["stage"],
                  "manifest_sha256": sha(manifest_path), "execution_release_sha256": sha(release_path),
                  "status": final_status, "drain_request": current_drain(root), "etel": result, "utc": now()})
        return {"status": final_status, "stage": manifest["stage"],
                "manifest_sha256": sha(manifest_path), "outcomes": result, "observation_path": str(report_path), "utc": now()}


@contextmanager
def auxiliary_lease(root, purpose):
    """Wrap complete audit/conversion/reproduction invocations for timing exclusion."""
    require(purpose in ("audit", "conversion", "reproduction"), "Unregistered auxiliary compute purpose")
    with exclusive_lock(root):
        for row in current_attempts(root):
            row = reconcile(root, row)
            require(row["status"] in TERMINAL, "Numerical training is pending/running")
            require(process_is_closed(root, row), "Scientific child is still live")
        yield


@contextmanager
def timing_lease(root, release_path):
    """Call around the complete isolated timing session, not just a preflight check."""
    with exclusive_lock(root):
        release = read(release_path)
        require(release.get("review_status") == "approved_by_root" and release.get("stage") == "timing",
                "Root timing release required")
        for row in current_attempts(root):
            row = reconcile(root, row)
            require(row["status"] in TERMINAL, "Training/audit work not stopped")
            require(process_is_closed(root, row), "A scientific child is still live")
        audit = read(verify_binding(release["confirmation_audit"]))
        require(audit.get("status") == "PASS" and audit.get("stage") == "B" and
                audit.get("verified_endpoints") == PHASE_COUNTS["B"], "All confirmation endpoints must be audited")
        verify_receipt_endpoints(root, audit, "B", PHASE_COUNTS["B"])
        require(release.get("max_parallel_tasks") == 1 and release.get("required_blas_threads") == 1,
                "Timing must be serial and one BLAS thread")
        yield
