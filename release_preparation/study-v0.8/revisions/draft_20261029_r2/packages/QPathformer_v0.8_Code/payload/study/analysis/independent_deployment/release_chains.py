"""Read-only full payload/authority gates for independent derived audits."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"analysis/official_evaluation"))
import gate

SCORE_SOURCES = {
    "replay_evaluation_v08.py", "replay_metrics_v08.py", "statistics_v08.py",
    "reference_v08.py", "audit_endpoints_v08.py", "AUDIT_NUMERICAL_PROTOCOL.json",
    "sampler_reference.py", "audit_sampling_trace.py", "replay_priority_v08.py",
    "test_statistics_v08.py", "test_replay_metrics_v08.py", "test_replay_priority_v08.py",
    "test_replay_evaluation_v08.py", "run_replay_leased.py", "run_replay_preflight.py",
    "test_replay_wrapper_v08.py"}


def committed(item, filename, schema, root=ROOT):
    path = gate.verify_binding(item, root)
    folder, record = path.parent, gate.read(path)
    gate.require(path.name == filename and record.get("schema") == schema and
                 record.get("status") == "completed", "Successful bound derived commit required")
    gate.require(not any((folder/name).exists() for name in ("FAILURE.json", "REPLAY_FAILURE.json")),
                 "Failed derived evidence cannot satisfy readiness")
    for relative, info in record["files"].items():
        file = (folder/relative).resolve()
        gate.require(file.is_relative_to(folder) and file != path and file.is_file() and
                     file.stat().st_size == info["bytes"] and gate.sha(file) == info["sha256"],
                     "Derived payload changed or escapes folder")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    gate.require(actual == set(record["files"]) | {filename}, "Derived commit inventory differs")
    gate.require(gate.read(folder/"summary.json").get("status") == "PASS", "Derived summary is not PASS")
    return record, folder


def validate_score_coverage(record, summary, reports, ids, evaluated, source_freeze):
    gate.require(len(ids) == len(set(ids)) == 640, "Full unique score replay target matrix required")
    gate.require(record.get("count") == 640 and record.get("run_ids") == summary.get("ordered_run_ids") == ids,
                 "Score replay commit/summary exact identities differ")
    for item in (record, summary):
        gate.require(item.get("official_evaluation_commit") == evaluated and
                     item.get("independent_replay_freeze") == source_freeze,
                     "Score replay evaluation/source binding differs")
    for name, value in (("replayed_endpoints", 640), ("primary_comparisons_replayed", 20),
                        ("reference_prediction_files", 1280), ("priority_endpoint_diagnostics_replayed", 640),
                        ("priority_round_diagnostics_replayed", 128000),
                        ("priority_training_draws_reconstructed", 614400000),
                        ("priority_family_arm_summaries_replayed", 40),
                        ("descriptive_priority_effects_replayed", 20)):
        gate.require(summary.get(name) == value, "Incomplete independent replay: "+name)
    gate.require(len(reports) == 640 and [r["job_id"] for r in reports] == ids and
                 all(set(r["splits"]) == {"validation", "test"} for r in reports),
                 "Score replay endpoint/split identities differ")
    expected = {"predictions/"+identity+"/"+split+"_reference.npz" for identity in ids
                for split in ("validation", "test")}
    actual = {name for name in record["files"] if name.startswith("predictions/")}
    gate.require(actual == expected and len(expected) == 1280, "Score replay reference inventory differs")


def verify_score_replay(release, verified):
    """Require the complete separately implemented score/priority replay contract."""
    record, folder = committed(release["independent_score_replay_commit"], "REPLAY_COMMIT.json",
                               "qpath-v08-independent-replay-commit-1")
    gate.require(record["release"] == verified["release_binding"] and
                 record["official_evaluation_commit"] == verified["evaluation_commit"],
                 "Score replay belongs to a different evaluation")
    frozen_item = verified["release"]["independent_replay_freeze"]
    gate.require(record["independent_replay_freeze"] == frozen_item, "Score replay source authority differs")
    freeze = gate.read(gate.verify_binding(frozen_item, ROOT))
    gate.require(freeze.get("schema") == "qpath-v08-independent-replay-source-freeze-1" and
                 set(freeze["sources"]) == SCORE_SOURCES and
                 set(freeze["protocols"]) == {"STUDY_PLAN.json", "RUN_MATRIX.json", "ANALYSIS_PROTOCOL.json"},
                 "Independent score source freeze inventory differs")
    for relative, item in freeze["sources"].items():
        gate.require(gate.verify_binding(item, ROOT) == ROOT/"analysis/independent_audit"/relative,
                     "Score replay source identity differs")
    for name in ("STUDY_PLAN.json", "RUN_MATRIX.json", "ANALYSIS_PROTOCOL.json"):
        gate.require(gate.verify_binding(freeze["protocols"][name], ROOT) == ROOT/"governance"/name,
                     "Score replay protocol differs")
    gate.require(Path(verified["release"]["independent_replay_output"]).resolve() == folder,
                 "Score replay output not root-bound")
    summary = gate.read(folder/"summary.json")
    gate.require(summary.get("replayed_endpoints") == 640 and summary.get("primary_comparisons_replayed") == 20 and
                 summary.get("release") == verified["release_binding"] and
                 summary.get("official_evaluation_commit") == verified["evaluation_commit"] and
                 summary.get("independent_replay_freeze") == frozen_item and
                 summary.get("reference_prediction_files") == 1280,
                 "Incomplete score replay summary")
    ids = [j["run_id"] for j in verified["jobs"]]
    reports = gate.read(folder/"endpoint_replay.json")
    validate_score_coverage(record, summary, reports, ids, verified["evaluation_commit"], frozen_item)
    for report in reports:
        gate.require(set(report["splits"]) == {"validation", "test"}, "Score replay misses a heldout split")
        for split, item in report["splits"].items():
            path = gate.verify_binding(item["prediction_binding"], ROOT)
            gate.require(path == folder/"predictions"/report["job_id"]/(split+"_reference.npz"),
                         "Score replay prediction binding differs")
    return {"commit": record, "folder": folder, "summary": summary}


def verify_reproduction(release, verified):
    producer_item = release["reproduction_commit"]
    independent, folder = committed(release["independent_reproduction_commit"],
                                    "INDEPENDENT_REPRODUCTION_COMMIT.json",
                                    "qpath-v08-independent-reproduction-commit-1")
    summary_path = gate.verify_binding(release["independent_reproduction_audit"], ROOT)
    gate.require(summary_path == folder/"summary.json" and
                 independent["files"]["summary.json"] == {k: release["independent_reproduction_audit"][k]
                                                          for k in ("sha256", "bytes")},
                 "Independent reproduction summary is not the committed receipt")
    summary = gate.read(summary_path)
    protocol = gate.read(ROOT/"governance/REPRODUCTION_PROTOCOL.json")
    ids = protocol["endpoints"]
    for record in (summary, independent):
        gate.require(record.get("phase") == "reproduction" and record.get("count") == 4 and
                     record.get("run_ids") == ids and record.get("producer_commit") == producer_item and
                     record.get("evaluation_commit") == verified["evaluation_commit"], "Reproduction evidence chain differs")
    gate.require(summary.get("full_rounds") == 800 and summary.get("full_updates") == 60000 and
                 summary.get("original_checkpoints_copied") is False, "Full clean-reproduction proof missing")
    authority = gate.read(gate.verify_binding(independent["authorization"], ROOT))
    gate.require(authority.get("schema") == "qpath-v08-independent-reproduction-release-1" and
                 authority.get("review_status") == "approved_by_root" and authority.get("phase") == "reproduction" and
                 authority.get("test_access_authorized") is True and
                 authority.get("max_parallel_tasks") == authority.get("required_blas_threads") == 1 and
                 authority.get("run_ids") == ids and Path(authority["output"]).resolve() == folder and
                 authority["producer_commit"] == producer_item and
                 authority["evaluation_release"] == release["evaluation_release"] and
                 authority["evaluation_commit"] == release["evaluation_commit"],
                 "Independent reproduction root approval differs")
    gate.require(summary["authorization"] == independent["authorization"] and
                 authority["source_freeze"] == independent["source_freeze"] == summary["source_freeze"],
                 "Independent reproduction receipt source/approval differs")
    freeze = gate.read(gate.verify_binding(independent["source_freeze"], ROOT))
    expected_sources = {"audit_reproduction.py", "compare_reference.py", "test_reproduction_audit.py"}
    gate.require(freeze.get("schema") == "qpath-v08-independent-reproduction-source-freeze-1" and
                 freeze.get("test_access_authorized") is False and set(freeze["sources"]) == expected_sources,
                 "Independent reproduction source freeze differs")
    for relative, digest in freeze["sources"].items():
        gate.require(gate.sha(ROOT/"analysis/independent_reproduction"/relative) == digest,
                     "Independent reproduction source drift")
    for name in ("REPRODUCTION_PROTOCOL.json", "STUDY_PLAN.json", "RUN_MATRIX.json"):
        gate.require(gate.verify_binding(freeze["protocols"][name], ROOT) == ROOT/"governance"/name,
                     "Independent reproduction protocol changed")
    sys.path.insert(0, str(ROOT/"analysis/independent_reproduction"))
    import audit_reproduction as reference
    jobs = reference.registered_jobs(gate.read(ROOT/"governance/RUN_MATRIX.json"), protocol)
    producer = reference.verify_producer({**release, "producer_commit": producer_item}, verified, jobs)
    records = gate.read(folder/"endpoint_comparisons.json")
    gate.require(len(records) == 4 and [r["job_id"] for r in records] == ids, "Independent reproduction endpoint inventory differs")
    for row, job, saved in zip(records, jobs, producer["index"]):
        gate.require(row.get("status") == "PASS" and row.get("full_rounds") == 200 and row.get("full_updates") == 15000 and
                     row["original_commit"] == verified["endpoint_commits"][job["run_id"]] and
                     row["reproduced_commit"] == saved["endpoint_commit"], "Reproduction comparison identity differs")
    gate.require(gate.read(folder/"clean_provenance_review.json").get("status") == "PASS",
                 "Independent clean-source/data review missing")
    return {"commit": independent, "folder": folder, "summary": summary, "producer": producer}
