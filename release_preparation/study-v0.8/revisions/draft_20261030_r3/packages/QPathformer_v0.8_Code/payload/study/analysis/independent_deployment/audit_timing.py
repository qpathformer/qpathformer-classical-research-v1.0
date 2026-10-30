"""Released-only audit of three committed isolated sessions; never times model calls."""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import traceback

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_name] = "1"
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/"analysis/official_evaluation"))
import gate
from statistics_timing import (BATCHES, CIRCUIT_ARMS, across_sessions, condition_statistics,
                               expected_trials, finite, matched_statistics, ordered_jobs, require, same)

SOURCES = ("audit_timing.py", "statistics_timing.py", "release_chains.py", "test_timing.py", "run_synthetic_tests.py")
PROTOCOLS = ("RUN_MATRIX.json", "DEPLOYMENT_PROTOCOL.json", "RESOURCE_ACCOUNTING_NOTES.json", "REPRODUCTION_PROTOCOL.json")


def now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "Timezone-qualified timestamp required")
    return parsed.timestamp()


def source_hashes():
    return {name: gate.sha(HERE/name) for name in SOURCES}


def snapshot():
    return {"schema": "qpath-v08-independent-timing-source-freeze-1", "created_utc": now(),
            "official_timing_access_authorized": False, "sources": source_hashes(),
            "protocols": {name: gate.binding(ROOT/"governance"/name) for name in PROTOCOLS}}


def committed(binding, kind):
    path = gate.verify_binding(binding, ROOT)
    folder, record = path.parent, gate.read(path)
    require(path.name == kind.upper().replace("-", "_")+"_COMMIT.json" and
            record.get("schema") == "qpath-v08-"+kind+"-commit-1" and
            record.get("status") == "completed", "Invalid successful commit")
    require(not (folder/"FAILURE.json").exists(), "Failure record prohibits successful audit")
    for relative, info in record["files"].items():
        file = (folder/relative).resolve()
        require(file.is_relative_to(folder) and file != path and file.is_file(),
                "Committed payload path invalid")
        require(file.stat().st_size == info["bytes"] and gate.sha(file) == info["sha256"],
                "Committed timing/derived payload changed")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    require(actual == set(record["files"]) | {path.name}, "Committed output inventory differs")
    require(gate.read(folder/"summary.json").get("status") == "PASS", "Summary is not PASS")
    return record, folder


def validate_header(release, output):
    require(release.get("schema") == "qpath-v08-independent-timing-release-1" and
            release.get("review_status") == "approved_by_root" and
            release.get("phase") == "timing_evidence" and release.get("max_parallel_tasks") == 1 and
            release.get("required_blas_threads") == 1 and release.get("timing_evidence_access_authorized") is True,
            "Root independent timing authorization missing")
    require(Path(release["output"]).resolve() == Path(output).resolve(), "Unauthorized audit output")
    require(len(release.get("session_commits", [])) == 3 and
            len({v["sha256"] for v in release["session_commits"]}) == 3,
            "All three distinct successful session commits must be bound")


def process_key(identity):
    require(set(identity) == {"pid", "creation_token", "identity_source"} and
            type(identity["pid"]) is int and identity["pid"] > 0 and
            type(identity["creation_token"]) is str and identity["creation_token"].isdigit() and
            identity["identity_source"] == "Win32_GetProcessTimes",
            "Exact Win32 PID/creation-token identity required")
    return identity["pid"], identity["creation_token"]


def distinct_processes(identities):
    keys = [process_key(identity) for identity in identities]
    require(len(keys) == 3 and len(set(keys)) == 3, "Timing processes were not distinct")


def validate_conversion_authorizations(release, conversion, conversion_folder, conversion_release,
                                       independent, independent_folder, independent_summary, independent_release):
    require(conversion_release.get("schema") == "qpath-v08-deployment-release-1" and
            conversion_release.get("review_status") == "approved_by_root" and
            conversion_release.get("phase") == "conversion" and
            conversion_release.get("test_access_authorized") is True and
            conversion_release.get("max_parallel_tasks") == conversion_release.get("required_blas_threads") == 1,
            "Conversion root approval missing")
    require(Path(conversion_release["output"]).resolve() == conversion_folder and
            conversion_release["registration"] == conversion["registration"], "Conversion output/source authority differs")
    for name in ("evaluation_release", "evaluation_commit"):
        require(conversion_release[name] == release[name] and independent_release[name] == release[name],
                "Conversion evaluation authority differs")
    require(independent.get("phase") == "conversion" and
            independent["authorization"] == independent_summary["authorization"] and
            independent_summary["producer_commit"] == release["conversion_commit"],
            "Independent conversion commit/summary authority differs")
    require(independent_release.get("schema") == "qpath-v08-independent-deployment-release-1" and
            independent_release.get("review_status") == "approved_by_root" and
            independent_release.get("phase") == "conversion" and
            independent_release.get("test_access_authorized") is True and
            independent_release.get("max_parallel_tasks") == independent_release.get("required_blas_threads") == 1 and
            independent_release["producer_commit"] == release["conversion_commit"] and
            Path(independent_release["output"]).resolve() == independent_folder,
            "Independent conversion root approval differs")


def verify_release(authorization, output):
    release = gate.read(authorization)
    validate_header(release, output)
    require(Path(authorization).resolve().is_relative_to(ROOT), "Authorization outside study")
    output = Path(output).resolve()
    require(output.is_relative_to(ROOT/"analysis") and not output.exists(), "Fresh audit output required")
    freeze = gate.read(gate.verify_binding(release["source_freeze"], ROOT))
    require(freeze.get("schema") == "qpath-v08-independent-timing-source-freeze-1" and
            freeze.get("official_timing_access_authorized") is False and
            freeze["sources"] == source_hashes() and set(freeze["protocols"]) == set(PROTOCOLS),
            "Independent timing source freeze changed")
    for name, binding in freeze["protocols"].items():
        require(gate.verify_binding(binding, ROOT) == ROOT/"governance"/name, "Frozen protocol mismatch")
    evaluation_release = gate.verify_binding(release["evaluation_release"], ROOT)
    verified = gate.verify_completed_evaluation(ROOT, evaluation_release, release["evaluation_commit"])
    from release_chains import verify_score_replay, verify_reproduction
    verify_score_replay(release, verified)
    reproduction = verify_reproduction(release, verified)
    conversion, conversion_folder = committed(release["conversion_commit"], "conversion")
    independent, independent_folder = committed(release["independent_conversion_commit"], "independent-deployment")
    audit_path = gate.verify_binding(release["independent_conversion_audit"], ROOT)
    require(audit_path == independent_folder/"summary.json" and
            independent["files"]["summary.json"] == {k: release["independent_conversion_audit"][k] for k in ("bytes", "sha256")},
            "Independent conversion summary not in bound commit")
    independent_summary = gate.read(audit_path)
    require(independent_summary.get("phase") == "conversion" and independent_summary.get("status") == "PASS" and
            independent_summary.get("representations_replayed") == 640 and
            independent_summary.get("circuit_endpoints") == 256 and
            independent_summary.get("learned_trig_exact_repacks") == 384 and
            independent_summary.get("conversion_commit") == release["conversion_commit"],
            "Full independent conversion replay missing")
    ids = [j["run_id"] for j in verified["jobs"]]
    replay_rows = gate.read(independent_folder/"conversion_replay.json")
    require(len(replay_rows) == 640 and [row["job_id"] for row in replay_rows] == ids and
            all(set(row["splits"]) == {"validation", "test"} for row in replay_rows),
            "Independent conversion replay identity/split inventory differs")
    reference_names = {"predictions/"+identity+"/"+split+"_reference.npz"
                       for identity in ids for split in ("validation", "test")}
    require({name for name in independent["files"] if name.startswith("predictions/")} == reference_names and
            len(reference_names) == 1280, "Independent conversion reference inventory differs")
    require(conversion["evaluation_commit"] == verified["evaluation_commit"], "Conversion evaluation differs")
    conversion_release = gate.read(gate.verify_binding(conversion["authorization"], ROOT))
    independent_release = gate.read(gate.verify_binding(independent["authorization"], ROOT))
    validate_conversion_authorizations(release, conversion, conversion_folder, conversion_release,
                                       independent, independent_folder, independent_summary, independent_release)
    for authority in (conversion_release, independent_release):
        require(authority["independent_score_replay_commit"] == release["independent_score_replay_commit"],
                "Conversion score-replay authority differs from timing")
    independent_start = gate.read(independent_folder/"START.json")
    require(independent_start.get("phase") == "conversion" and
            independent_start["authorization"] == independent["authorization"],
            "Independent conversion start authority differs")
    conversion_freeze = gate.read(gate.verify_binding(independent_release["source_freeze"], ROOT))
    require(conversion_freeze.get("schema") == "qpath-v08-independent-deployment-source-freeze-1" and
            conversion_freeze.get("test_access_authorized") is False and
            set(conversion_freeze["sources"]) == {"reference.py", "verify_arrays.py", "audit_artifacts.py", "release_chains.py", "test_reference.py"} and
            set(conversion_freeze["protocols"]) ==
            {"RUN_MATRIX.json", "DEPLOYMENT_PROTOCOL.json", "LOCAL_READINESS_PROTOCOL.json"},
            "Independent conversion source freeze inventory differs")
    for relative, digest in conversion_freeze["sources"].items():
        file = ROOT/"analysis/independent_deployment"/relative
        require(gate.sha(file) == digest, "Independent conversion frozen source changed")
    for name, binding in conversion_freeze["protocols"].items():
        require(gate.verify_binding(binding, ROOT) == ROOT/"governance"/name, "Independent conversion protocol changed")
    registration = gate.read(gate.verify_binding(conversion["registration"], ROOT))
    require(registration.get("schema") == "qpath-v08-deployment-registration-1" and
            registration.get("test_access_authorized") is False, "Deployment registration missing")
    for relative, digest in registration["sources"].items():
        file = (ROOT/relative).resolve()
        require(file.is_relative_to(ROOT) and file.is_file() and gate.sha(file) == digest,
                "Registered deployment source changed")
    for key, name in (("deployment_protocol", "DEPLOYMENT_PROTOCOL.json"), ("run_matrix", "RUN_MATRIX.json"),
                      ("readiness_protocol", "LOCAL_READINESS_PROTOCOL.json")):
        require(gate.verify_binding(registration[key], ROOT) == ROOT/"governance"/name, "Producer protocol differs")
    sessions = []
    for number, binding in enumerate(release["session_commits"], 1):
        commit, folder = committed(binding, "timing")
        require(commit["evaluation_commit"] == verified["evaluation_commit"] and
                commit["registration"] == conversion["registration"], "Timing provenance differs")
        session_release = gate.read(gate.verify_binding(commit["authorization"], ROOT))
        require(session_release.get("schema") == "qpath-v08-deployment-release-1" and
                session_release.get("review_status") == "approved_by_root" and
                session_release.get("phase") == session_release.get("stage") == "timing" and
                session_release.get("session") == number and
                session_release.get("test_access_authorized") is True and
                session_release.get("max_parallel_tasks") == session_release.get("required_blas_threads") == 1,
                "Timing session root approval differs")
        require(Path(session_release["output"]).resolve() == folder and
                session_release["registration"] == conversion["registration"] and
                session_release["previous_session_commits"] == release["session_commits"][:number-1],
                "Timing session chain differs")
        for name in ("evaluation_release", "evaluation_commit", "conversion_commit",
                     "independent_conversion_audit", "independent_conversion_commit",
                     "independent_score_replay_commit", "reproduction_commit",
                     "independent_reproduction_commit", "independent_reproduction_audit"):
            require(session_release[name] == release[name], "Timing "+name+" differs")
        confirmation = gate.read(gate.verify_binding(session_release["confirmation_audit"], ROOT))
        require(confirmation.get("status") == "PASS" and confirmation.get("stage") == "B" and
                confirmation.get("verified_endpoints") == 640, "Timing B audit gate missing")
        sessions.append((commit, folder, session_release))
    matrix = gate.read(ROOT/"governance/RUN_MATRIX.json")
    jobs = [job for job in matrix["runs"] if job["stage"] == "B"]
    populations = [pop for pop in matrix["populations"] if pop["stage"] == "B"]
    require(len(jobs) == 640 and len(populations) == 32 and
            sum(j["arm"] in CIRCUIT_ARMS for j in jobs) == 256, "Registered timing inventory changed")
    require([j["run_id"] for j in jobs] == [j["run_id"] for j in verified["jobs"]], "Released B identities differ")
    return {"release": release, "authorization": gate.binding(authorization), "freeze": freeze,
            "verified": verified, "sessions": sessions, "conversion": conversion,
            "conversion_folder": conversion_folder, "jobs": ordered_jobs(jobs, populations),
            "populations": populations, "reproduction": reproduction}


def memory_sample(record, first, last):
    require(record.get("source") == "Win32_GlobalMemoryStatusEx" and
            first <= timestamp(record["sampled_utc"]) <= last, "Memory telemetry source/time differs")
    require(type(record["memory_load_percent"]) is int and 0 <= record["memory_load_percent"] <= 100,
            "Invalid memory load")
    for name in ("physical", "pagefile", "virtual"):
        total, available = record["total_"+name+"_bytes"], record["available_"+name+"_bytes"]
        require(type(total) is int and type(available) is int and 0 <= available <= total and total > 0,
                "Invalid memory availability")


def validate_csv_rows(rows, jobs, session, start_utc, finish_utc):
    values = defaultdict(list)
    previous = start_utc
    expected = list(expected_trials(jobs, session))
    require(len(rows) == len(expected), "Timed trial inventory differs")
    for row, identity in zip(rows, expected):
        actual = (int(row["sequence"]), row["job_id"], row["representation"], int(row["batch_size"]), int(row["trial"]))
        require(actual == identity, "Registered block/trial/paired alternation differs")
        elapsed = int(row["elapsed_ns"])
        require(str(elapsed) == row["elapsed_ns"] and elapsed > 0, "Elapsed timer must be positive integer")
        require(finite(float(row["probability_sum"])) and finite(float(row["logit_sum"])) and
                0 <= float(row["probability_sum"]) <= actual[3], "Invalid retained output checksum")
        measured = timestamp(row["measured_utc"])
        require(previous <= measured <= finish_utc, "Trial wall clock order differs")
        previous = measured
        values[(actual[1], actual[2], actual[3])].append(elapsed)
    require(all(len(v) == 15 for v in values.values()), "Condition misses a trial")
    return dict(values)


def index_records(records, names):
    result = {tuple(row[name] for name in names): row for row in records}
    require(len(result) == len(records), "Duplicate summary identity")
    return result


def session_audit(checked, number):
    commit, folder, release = checked["sessions"][number-1]
    jobs = checked["jobs"]
    start, summary = gate.read(folder/"START.json"), gate.read(folder/"summary.json")
    require(start.get("status") == "RUNNING" and start["session"] == summary["session"] == number and
            start["process_identity"] == summary["process_identity"], "Session/process identities differ")
    identity = start["process_identity"]
    process_key(identity)
    require(start["authorization"] == commit["authorization"] and start["registration"] == commit["registration"],
            "Session start provenance differs")
    for name in ("conversion_commit", "independent_conversion_commit", "independent_conversion_audit"):
        require(start[name] == release[name], "Start conversion gate differs")
    require([summary[k] for k in ("conditions", "representations", "selected_models", "timed_trials",
                                  "warmup_trials", "forward_calls_per_trial")] == [2688, 896, 640, 40320, 5376, 1],
            "Session coverage counters differ")
    require(summary["hardware_used"] is False and summary["external_os_scheduling_controlled"] is False,
            "Session scope differs")
    clock = start["clock"]
    require(clock["monotonic"] is True and clock["adjustable"] is False and
            finite(clock["resolution"]) and clock["resolution"] > 0 and bool(clock["implementation"]),
            "Timing clock metadata differs")
    environment = gate.read(checked["verified"]["release"]["runtime_environment"]["path"])
    for actual in (start["environment"], summary["environment_after"]):
        for name in ("python", "interpreter", "numpy_version", "openblas_dll_sha256",
                     "openblas_config", "effective_blas_threads", "gpu_used"):
            require(actual[name] == environment[name], "Timing runtime mismatch: "+name)
        require(actual["effective_blas_threads"] == 1 and actual["gpu_used"] is False, "BLAS1 CPU evidence absent")
    first, last = timestamp(start["started_utc"]), timestamp(summary["finished_utc"])
    require(first > timestamp(checked["reproduction"]["summary"]["finished_utc"]),
            "Timing began before independent reproduction finished")
    require(last > first and finite(summary["elapsed_seconds"]) and summary["elapsed_seconds"] > 0 and
            finite(summary["process_cpu_seconds"]) and summary["process_cpu_seconds"] >= 0,
            "Invalid session duration")
    memory_sample(start["available_memory"], first, last)
    end_sample = timestamp(summary["available_memory_after"]["sampled_utc"])
    require(end_sample >= last, "End memory sampling predates recorded finish")
    memory_sample(summary["available_memory_after"], first, end_sample)
    for resource in (start["process_resources"], summary["process_resources"]):
        require(resource["pid"] == identity["pid"] and finite(resource["process_cpu_seconds"]) and
                resource["process_cpu_seconds"] >= 0 and resource["peak_working_set_bytes"] > 0 and
                0 < resource["working_set_bytes_at_sample"] <= resource["peak_working_set_bytes"] and
                resource["private_usage_bytes_at_sample"] >= 0 and
                resource["memory_source"] == "Win32_GetProcessMemoryInfo", "Process resource telemetry invalid")
    require(summary["process_resources"]["process_cpu_seconds"] >= start["process_resources"]["process_cpu_seconds"],
            "Process CPU counter moved backwards")
    with (folder/"trials.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == ["sequence", "job_id", "representation", "batch_size", "trial",
                                      "elapsed_ns", "probability_sum", "logit_sum", "measured_utc"],
                "Raw timing CSV schema differs")
        rows = list(reader)
    values = validate_csv_rows(rows, jobs, number, first, last)
    require(len(values) == 2688, "Exactly2688 conditions required")
    conditions = index_records(gate.read(folder/"conditions.json"), ("job_id", "representation", "batch_size"))
    require(set(conditions) == set(values), "Condition summary inventory differs")
    drift = []
    for key, series in values.items():
        record = condition_statistics(series)
        for name, expected in record.items():
            same(conditions[key].get(name), expected, "Condition "+name)
        drift.append({"job_id": key[0], "representation": key[1], "batch_size": key[2],
                      "last5_over_first5_median_ratio": record["last5_median_ns"]/record["first5_median_ns"],
                      "last5_minus_first5_median_ns": record["last5_median_ns"]-record["first5_median_ns"]})
    matched_saved = index_records(gate.read(folder/"matched_ratios.json"), ("job_id", "batch_size"))
    expected_pairs = {(j["run_id"], b) for j in jobs if j["arm"] in CIRCUIT_ARMS for b in BATCHES}
    require(set(matched_saved) == expected_pairs and len(expected_pairs) == 768, "Paired summary inventory differs")
    matched = {}
    for key in sorted(expected_pairs):
        construction = gate.read(checked["conversion_folder"]/"endpoints"/key[0]/"conversion.json")["construction_ns"]
        recomputed = matched_statistics(values[(key[0], "original", key[1])],
                                        values[(key[0], "converted", key[1])], construction)
        for name, expected in recomputed.items():
            same(matched_saved[key].get(name), expected, "Matched "+name)
        matched[key] = recomputed
    models = gate.read(folder/"models_and_loading.json")
    require([r["job_id"] for r in models] == [j["run_id"] for j in jobs], "Model loading inventory/order differs")
    for row, job in zip(models, jobs):
        require((row["arm"], row["family"], row["population"], row["seed"]) ==
                (job["arm"], job["family"], job["population_id"], job["training_seed_id"]),
                "Model loading identity differs")
        require(row["representation_labels"] ==
                (["original", "converted"] if job["arm"] in CIRCUIT_ARMS else ["original"]),
                "Model representation inventory differs")
        require(row["load"]["endpoint_commit"] == checked["verified"]["endpoint_commits"][job["run_id"]],
                "Timed model is not audited selected checkpoint")
        checkpoint = gate.verify_binding(row["load"]["checkpoint"], ROOT)
        endpoint = gate.verify_binding(row["load"]["endpoint_commit"], ROOT).parent
        require(checkpoint == endpoint/"selected_checkpoint.npz", "Wrong checkpoint loading record")
        for val in (row["load"]["model_construction_and_checkpoint_loading_ns"],
                    row["representation_file_hash_check_and_load_ns"]):
            require(type(val) is int and val >= 0, "Invalid instrumented loading counter")
        require(row["load"]["parameter_bytes"] > 0, "Missing parameter size")
        data_path = gate.verify_binding(row["data"]["data"], ROOT)
        router_path = gate.verify_binding(row["data"]["router"], ROOT)
        require(data_path == ROOT/"quantum/data"/(job["population_id"]+"_validation.npz") and
                router_path == ROOT/"quantum/data"/(job["population_id"]+"_router.json"),
                "Timing raw input provenance differs")
    components = index_records(gate.read(folder/"components.json"), ("job_id", "representation", "batch_size"))
    require(set(components) == set(values), "Component instrument inventory differs")
    for component in components.values():
        for key in ("routing_ns", "feature_or_core_ns", "head_ns", "sigmoid_ns"):
            require(type(component["costs"][key]) is int and component["costs"][key] >= 0,
                    "Invalid component timer")
    blocks = gate.read(folder/"population_memory_snapshots.json")
    first_jobs = {}
    for job in jobs:
        first_jobs.setdefault(job["population_id"], job["run_id"])
    require([(b["population"], b["next_job_id"]) for b in blocks] == list(first_jobs.items()) and len(blocks) == 32,
            "32 interleaved population memory snapshots required")
    for block in blocks:
        memory_sample(block["available_memory"], first, last)
    return {"condition_values": values, "matched": matched, "drift": drift,
            "summary": {"session": number, "process_identity": identity, "start_utc": start["started_utc"],
                        "finish_utc": summary["finished_utc"], "last_telemetry_utc": summary["available_memory_after"]["sampled_utc"], "conditions": 2688,
                        "timed_trials_replayed": len(rows), "warmups_reported": 5376,
                        "warmup_provenance": "Only committed counters and reviewed producer loop are retained; no individual warmup timing/call records exist. Warmup execution was not independently observed.",
                        "process_cpu_seconds": summary["process_cpu_seconds"], "wall_seconds": summary["elapsed_seconds"],
                        "start_memory": start["available_memory"], "end_memory": summary["available_memory_after"],
                        "population_memory_snapshots": blocks,
                        "loading_component_scope": "Single instrumented observations are checked for provenance/coverage, not independently remeasured. Components are not additive primary latencies."}}


def run(authorization, output):
    sys.path.insert(0, str(ROOT/"execution"))
    import durable
    with durable.auxiliary_lease(ROOT, "audit"):
        checked = verify_release(authorization, output)
        import resource_probe
        current_environment = resource_probe.inspect()
        expected_environment = gate.read(checked["verified"]["release"]["runtime_environment"]["path"])
        for name in ("python", "interpreter", "numpy_version", "openblas_dll_sha256",
                     "openblas_config", "effective_blas_threads", "gpu_used"):
            require(current_environment[name] == expected_environment[name], "Audit runtime mismatch: "+name)
        require(current_environment["effective_blas_threads"] == 1, "Audit requires effective BLAS1")
        output = Path(output).resolve()
        output.mkdir(parents=True, exist_ok=False)
        start, wall, cpu = now(), time.perf_counter(), time.process_time()
        try:
            sessions = [session_audit(checked, number) for number in (1, 2, 3)]
            distinct_processes([s["summary"]["process_identity"] for s in sessions])
            for earlier, later in zip(sessions, sessions[1:]):
                require(timestamp(earlier["summary"]["finish_utc"]) <
                        timestamp(later["summary"]["start_utc"]) and
                        timestamp(earlier["summary"]["last_telemetry_utc"]) <
                        timestamp(later["summary"]["start_utc"]), "Timing sessions overlap")
            merged = across_sessions(sessions, checked["jobs"])
            gate.write_new(output/"cross_session_descriptive.json", merged)
            for number, session in enumerate(sessions, 1):
                gate.write_new(output/f"session{number}_replay.json",
                               {"summary": session["summary"], "drift": session["drift"],
                                "conditions": [{"job_id": k[0], "representation": k[1], "batch_size": k[2],
                                                **condition_statistics(v)} for k, v in session["condition_values"].items()],
                                "matched": [{"job_id": k[0], "batch_size": k[1], **v} for k, v in session["matched"].items()]})
            require(source_hashes() == checked["freeze"]["sources"], "Timing audit source changed")
            gate.verify_binding(checked["authorization"], ROOT)
            for binding in checked["release"]["session_commits"]:
                committed(binding, "timing")
            summary = {"status": "PASS", "phase": "timing_evidence", "sessions_replayed": 3,
                       "selected_models_per_session": 640, "converted_circuits_per_session": 256,
                       "conditions_per_session": 2688, "timed_trials_replayed": 120960,
                       "warmup_counters_sum": 16128, "warmup_records_retained": False,
                       "session_commits": checked["release"]["session_commits"],
                       "started_utc": start, "finished_utc": now(),
                       "wall_seconds": time.perf_counter()-wall, "process_cpu_seconds": time.process_time()-cpu,
                       "scope": "Archived timing/statistics/provenance audit, no new model calls or speed measurement. Technical trials and sessions do not increase independent model/population counts. Warmups are reported counters, not independently observed raw calls; construction-only break-even excludes loading, storage and hardware."}
            gate.write_new(output/"summary.json", summary)
            files = {p.relative_to(output).as_posix(): {"sha256": gate.sha(p), "bytes": p.stat().st_size}
                     for p in sorted(output.rglob("*")) if p.is_file()}
            gate.write_new(output/"INDEPENDENT_TIMING_COMMIT.json",
                           {"schema": "qpath-v08-independent-timing-commit-1", "status": "completed",
                            "authorization": checked["authorization"], "source_freeze": checked["release"]["source_freeze"],
                            "session_commits": checked["release"]["session_commits"], "files": files})
            return summary
        except BaseException as error:
            gate.write_new(output/"FAILURE.json", {"status": "FAILED_PRESERVED", "error": repr(error),
                                                  "traceback": traceback.format_exc(), "utc": now()})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization")
    parser.add_argument("--output", required=True)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        gate.write_new(Path(args.output), snapshot())
    else:
        require(args.authorization is not None, "Root authorization required")
        print(json.dumps(run(args.authorization, args.output), allow_nan=False))
