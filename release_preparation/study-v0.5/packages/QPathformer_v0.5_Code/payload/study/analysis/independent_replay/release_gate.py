"""Independent v0.5 metadata gate; never loads a sealed array or test report.

This verifies complete training endpoint inventories, source/protocol bindings,
root release and actual official completion metadata. The returned official
payload inventory must only be read after the adapter writes ACCESS_EVENT.
"""
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from evidence_io import contained, digest, inventory, map_original_absolute, read_bound, recheck, require, safe_relative

STUDY_ID = "QPATH-READOUT-v0.5"
from statistics_reference import METHODS, POPULATIONS, SEEDS, validate_protocol


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "Timezone-aware evidence time required")
    return parsed.astimezone(timezone.utc)


def expected_output_paths():
    paths = {"ACCESS_EVENT.json", "summary.json"}
    for population in POPULATIONS:
        paths.update(f"{population}/statistics/{name}" for name in ("bootstrap_counts.npy", "population_summary.json"))
        paths.update(f"{population}/seed_{seed}/{method}/{name}" for seed in SEEDS for method in METHODS
                     for name in ("predictions.csv", "report.json"))
    return paths


def training_hashes(quantum):
    names = ["models.py", "study.py", "circuits.py", "reference_v03.py", "prepare_data.py", "routers.py", "launch_stage.py"]
    paths = [quantum / name for name in names] + sorted((quantum / "tests").glob("test*.py"))
    return {path.relative_to(quantum).as_posix(): digest(path) for path in paths}


def validate_gate(study, release_path, ready_path):
    """Read metadata/training evidence only; no test payload content or arrays."""
    study = Path(study).resolve()
    quantum = study / "quantum"
    require(np.__version__ == "2.5.4", "Registered NumPy2.5.4 required")
    require(Path(release_path).resolve() == quantum / "EVALUATION_RELEASE.json", "Unexpected release location")
    require(Path(ready_path).resolve() == study / "analysis/independent_replay/ANALYSIS_READY.json", "Unexpected READY location")
    paths = {
        "release": quantum / "EVALUATION_RELEASE.json", "ready": Path(ready_path),
        "registration": quantum / "EVALUATION_REGISTRATION.json",
        "lock": quantum / "CONFIRMATION_ENDPOINT_LOCK.json",
        "review": quantum / "CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json",
        "freeze": quantum / "STAGE_B_FREEZE.json", "seal": quantum / "data/DATA_SEAL.json",
        "analysis": study / "governance/ANALYSIS_PROTOCOL.json",
        "readiness": study / "governance/LOCAL_READINESS_PROTOCOL.json",
        "stage_status": quantum / "stage_B/stage_status.json",
        "commit": quantum / "confirmation_evaluation/EVALUATION_COMMIT.json",
    }
    # Missing actual completion must fail before even looking for outcome files.
    require(paths["commit"].is_file(), "Actual official evaluation completion commit required")
    watched = {}
    release = read_bound(paths["release"], watched)
    require(release.get("status") == "released_by_root" and release.get("study_id") == STUDY_ID,
            "Explicit root release required")
    require(release.get("scope") == "all_165_registered_confirmation_endpoints_once"
            and isinstance(release.get("release_id"), str) and release["release_id"], "Release scope/identity differs")
    objects = {key: read_bound(path, watched) for key, path in paths.items() if key != "release"}
    reg, ready, lock, review = (objects[key] for key in ("registration", "ready", "lock", "review"))
    freeze, seal, protocol, commit = (objects[key] for key in ("freeze", "seal", "analysis", "commit"))
    binding_names = {"registration_sha256": "registration", "independent_replay_ready_sha256": "ready",
                     "endpoint_lock_sha256": "lock", "independent_endpoint_review_sha256": "review",
                     "stage_freeze_sha256": "freeze", "data_seal_sha256": "seal",
                     "analysis_protocol_sha256": "analysis", "readiness_protocol_sha256": "readiness"}
    for key, name in binding_names.items():
        require(release.get(key) == watched[str(paths[name].resolve())], "Root release binding differs: " + key)
    require(reg.get("status") == "REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS", "Evaluation is not registered")
    original_root = reg["original_working_root"]
    # Registered original identities remain intact after a package is copied.
    map_original_absolute(original_root + "/quantum", original_root, study)
    require(reg["methods"] == list(METHODS) and reg["training_seeds"] == list(SEEDS)
            and reg["populations"] == list(POPULATIONS), "Registered evaluation scope differs")
    require(reg["expected_output_paths"] == sorted(expected_output_paths()), "Registered338-file output contract differs")
    require(protocol["methods"] == list(METHODS) and protocol["training_seeds"] == list(SEEDS)
            and protocol["population_order"] == list(POPULATIONS), "Registered analysis scope differs")
    validate_protocol(protocol)
    for key, name in (("analysis_protocol_sha256", "analysis"), ("readiness_protocol_sha256", "readiness"),
                      ("data_seal_sha256", "seal")):
        require(reg[key] == watched[str(paths[name].resolve())], "Registry data/protocol binding differs")
    require(ready.get("status") == "READY_BEFORE_CONFIRMATION_TEST_ACCESS" and ready.get("study_id") == STUDY_ID,
            "Independent replay not ready before test access")
    require(ready["registration_sha256"] == watched[str(paths["registration"].resolve())]
            and ready["analysis_protocol_sha256"] == watched[str(paths["analysis"].resolve())], "READY binding differs")
    actual_training = training_hashes(quantum)
    require(reg["training_source_hashes"] == actual_training == freeze["source_hashes"] == lock["source_hashes"],
            "Frozen/registered training sources differ")
    for name, expected in actual_training.items():
        watched[str(contained(quantum, name).resolve())] = expected
    for inventory_name, hashes in (("registry sources", reg["source_hashes"]),
                                   ("replay sources", ready["source_hashes"]),
                                   ("replay evidence", ready["evidence_hashes"])):
        require(isinstance(hashes, dict) and hashes, "Missing " + inventory_name)
        for name, expected in hashes.items():
            path = contained(study, name)
            require(digest(path) == expected, inventory_name + " changed: " + name)
            watched[str(path.resolve())] = expected
    own_folder = study / "analysis/independent_replay"
    own_sources = {path.relative_to(study).as_posix() for path in own_folder.glob("*.py")}
    require(own_sources <= set(ready["source_hashes"]), "READY omits independent source")
    oracle_path = contained(study, ready["independent_oracle_path"])
    require(digest(oracle_path) == ready["independent_oracle_sha256"]
            == ready["source_hashes"][ready["independent_oracle_path"]], "Independent oracle changed")
    require(freeze.get("review_status") == "approved_by_root" and freeze.get("methods") == list(METHODS)
            and freeze.get("populations") == list(POPULATIONS) and freeze.get("training_seeds") == list(SEEDS),
            "Root full-matrix B approval missing")
    settings = freeze["settings"]
    require(settings["rounds"] == 200 and settings["batch_size"] == 64 and settings["training_records"] == 4800
            and settings["validation_records"] == 1600 and settings["optimizer_updates"] == 15000, "Frozen full horizon differs")
    require(freeze["data_seal_sha256"] == watched[str(paths["seal"].resolve())], "Freeze data differs")
    require(lock.get("status") == "PASS" and lock.get("stage") == "B" and lock.get("endpoint_count") == 165
            and lock.get("engineering") is False and lock.get("test_accessed") is False, "Author endpoint audit incomplete")
    require(lock["data_seal_sha256"] == watched[str(paths["seal"].resolve())]
            and lock["stage_freeze_sha256"] == watched[str(paths["freeze"].resolve())]
            and lock["analysis_protocol_sha256"] == watched[str(paths["analysis"].resolve())], "Author lock binding differs")
    for name, expected in lock["audit_source_hashes"].items():
        path = map_original_absolute(name, original_root, study).resolve()
        require(digest(path) == expected, "Author auditor source changed")
        watched[str(path)] = expected
    require(review.get("status") == "PASS" and review.get("stage") == "B" and review.get("endpoint_count") == 165
            and review.get("endpoint_lock_sha256") == watched[str(paths["lock"].resolve())], "Canonical independent review incomplete")
    audit_path = contained(study, review["independent_audit_path"])
    audit = read_bound(audit_path, watched)
    require(watched[str(audit_path.resolve())] == review["independent_audit_sha256"], "Independent audit changed")
    require(audit.get("status") == "PASS" and audit.get("stage") == "B" and audit.get("endpoint_count") == 165
            and audit.get("validation_rounds_replayed") == 33000
            and audit.get("validation_predictions_replayed") == 52800000 and audit.get("engineering") is False
            and audit.get("model_test_outcomes_accessed") is False, "Independent round-validation audit incomplete")
    require(audit.get("endpoint_lock_sha256") == watched[str(paths["lock"].resolve())]
            and audit.get("analysis_protocol_sha256") == watched[str(paths["analysis"].resolve())]
            and audit.get("data_seal_sha256") == watched[str(paths["seal"].resolve())], "Independent audit bindings differ")
    auditor = contained(study, reg["independent_auditor_path"])
    require(digest(auditor) == audit["auditor_sha256"] == reg["source_hashes"][reg["independent_auditor_path"]],
            "Independent auditor changed")
    for name, expected in audit["independent_source_sha256"].items():
        require(Path(name).name == name, "Independent auditor source name must be local")
        path = auditor.parent / name
        relative = path.relative_to(study).as_posix()
        require(digest(path) == expected == reg["source_hashes"][relative], "Independent audit reference source changed")
        watched[str(path.resolve())] = expected
    stage = objects["stage_status"]
    require(stage.get("status") == "completed" and stage.get("stage") == "B"
            and stage.get("expected_endpoints") == stage.get("committed_endpoints") == 165
            and sorted((row["seed"], row["exit_code"]) for row in stage["exits"]) == [(seed, 0) for seed in SEEDS],
            "StageB processes not completed")
    identities = {(population, seed, method) for population in POPULATIONS for seed in SEEDS for method in METHODS}
    require(len(lock["endpoints"]) == 165 and {(row["population"], row["seed"], row["method"]) for row in lock["endpoints"]} == identities,
            "Exact165 endpoint identity set missing/duplicated")
    require(len(audit["endpoints"]) == 165 and {(row["population"], row["seed"], row["method"]) for row in audit["endpoints"]} == identities,
            "Exact165 independent audit identity set missing/duplicated")
    independently_audited = {(row["population"], row["seed"], row["method"]): row for row in audit["endpoints"]}
    endpoints = {}
    for row in lock["endpoints"]:
        identity = row["population"], row["seed"], row["method"]
        population, seed, method = identity
        audited = independently_audited[identity]
        require(audited["endpoint_commit_sha256"] == row["endpoint_commit_sha256"]
                and audited["rounds_verified"] == 200 and audited["validation_predictions_replayed"] == 320000
                and audited["selected_round"] == row["selected_round"]
                and audited["selected_checkpoint_sha256"] == row["files"]["selected_checkpoint.npz"]["sha256"],
                "Independent endpoint commit/selected state/full horizon differs")
        folder = quantum / "stage_B" / population / f"seed_{seed}" / method
        require(map_original_absolute(row["path"], original_root, study).resolve() == folder.resolve()
                and not (folder / "failure.json").exists(), "Endpoint original identity/path/failure differs")
        endpoint_commit = read_bound(folder / "endpoint_commit.json", watched)
        require(watched[str((folder / "endpoint_commit.json").resolve())] == row["endpoint_commit_sha256"], "Endpoint commit changed")
        require(endpoint_commit["status"] == "completed" and endpoint_commit["test_accessed"] is False
                and endpoint_commit["source_hashes"] == actual_training and endpoint_commit["files"] == row["files"], "Endpoint commit contents differ")
        require((endpoint_commit["population"], endpoint_commit["seed"], endpoint_commit["method"]) == identity, "Endpoint commit identity differs")
        required_payloads = {"config.json", "result.json", "status.json", "selected_checkpoint.npz", "last_checkpoint.npz",
                             "initial_state.npz", "round_parameters.npy", "validation_probabilities.npy", "record_orders.npy",
                             "population_identity.npz", "ledger.jsonl", "round_gradient_means.npz", "validation_predictions.csv",
                             "selected_training_gradient.npz", f"selected_round_{row['selected_round']:04d}.npz"}
        required_payloads.add("validation_native_losses.npy")
        if method != "q2_kmeans": required_payloads.add("validation_logits.npy")
        if method == "qfrozen_kmeans":
            required_payloads.update(("frozen_cache.json", "frozen_train_moments.npy", "frozen_validation_moments.npy"))
        require(required_payloads <= set(row["files"]), "Endpoint commit omits required full-run evidence")
        require(all(Path(name).name == name for name in row["files"]), "Nested endpoint payload forbidden")
        inventory(folder, row["files"], exclude=("endpoint_commit.json",))
        for name, metadata in row["files"].items():
            watched[str((folder / name).resolve())] = metadata["sha256"]
        config = read_bound(folder / "config.json", watched)
        result = read_bound(folder / "result.json", watched)
        status = read_bound(folder / "status.json", watched)
        for object_ in (config, result):
            require((object_["population"], object_["seed"], object_["method"], object_["stage"], object_["engineering"])
                    == (*identity, "B", False) and object_["test_accessed"] is False, "Endpoint identity or test boundary differs")
            require(object_["data_seal_sha256"] == watched[str(paths["seal"].resolve())]
                    and object_["stage_freeze_sha256"] == watched[str(paths["freeze"].resolve())], "Endpoint data/freeze differs")
        require(config["settings"] == settings and config["source_hashes"] == actual_training
                and config["rounds"] == 200 and config["train_records"] == 4800 and config["validation_records"] == 1600,
                "Endpoint training settings differ")
        require(result["status"] == "completed" and result["completed_rounds"] == 200 and result["optimizer_global_updates"] == 15000
                and status["status"] == "completed" and status["round"] == 200, "Incomplete full endpoint")
        require(type(row["selected_round"]) is int and 1 <= row["selected_round"] <= 200
                and row["selected_round"] == result["selected_round"], "Selected checkpoint identity differs")
        endpoints[identity] = row
    require(commit.get("status") == "completed" and commit.get("study_id") == STUDY_ID
            and commit.get("report_count") == 165 and commit.get("prediction_file_count") == 165
            and commit.get("population_count") == 3 and commit.get("payload_count") == 338, "Actual official completion incomplete")
    require(commit["release_id"] == release["release_id"] and commit["release_sha256"] == watched[str(paths["release"].resolve())]
            and commit["registration_sha256"] == watched[str(paths["registration"].resolve())]
            and commit["endpoint_lock_sha256"] == watched[str(paths["lock"].resolve())], "Official commit bindings differ")
    require(set(commit["files"]) == expected_output_paths(), "Official completion inventory differs")
    release_time = timestamp(release["created_utc"])
    require(release_time >= timestamp(lock["created_utc"]) and release_time >= timestamp(audit["created_utc"]), "Release predates audits")
    require(timestamp(commit["completed_utc"]) >= release_time and datetime.now(timezone.utc) >= timestamp(commit["completed_utc"]),
            "Official completion chronology differs")
    recheck(watched)
    return {"study": study, "quantum": quantum, "paths": paths, "watched": watched, "release": release,
            "registration": reg, "ready": ready, "lock": lock, "seal": seal, "protocol": protocol,
            "commit": commit, "endpoints": endpoints, "oracle_path": oracle_path,
            "relocation": {"original_working_root": original_root, "current_package_root": str(study),
                           "mapping": "Recorded absolute identities validated under registered original root; reads derived under current package root. Sealed metadata not rewritten; no original-tree reads required."}}
