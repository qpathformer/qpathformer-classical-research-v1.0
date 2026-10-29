"""Artificial adapter fixtures only; never creates a real approval or result.

Metadata mimic a closed165-endpoint study to test the guarded I/O contract.
No optimizer run is represented as scientific evidence. Dummy training payloads
are clearly marked, all data/model parameters are newly synthetic, and paths
remain under synthetic_fixture_work. These fixtures are not deliverable results.
"""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import numpy as np

from evidence_io import digest
from release_gate import METHODS, POPULATIONS, SEEDS, expected_output_paths, training_hashes
from replay_and_analyse import array_hash, independent_routes, numerical_summary
from statistics_reference import metrics, summarise_population
from official_comparison import metric_shape, native_shape, forward_work, objective
from prediction_reference import native_diagnostics
from threshold_reference import diagnostics

HERE = Path(__file__).resolve().parent
REAL_STUDY = HERE.parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def module(path, name):
    specification = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(loaded)
    return loaded


def metadata(path):
    return {"sha256": digest(path), "bytes": path.stat().st_size}


def make_fixture(records=12):
    fixture_home = HERE / "synthetic_fixture_work"
    fixture_home.mkdir(exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="adapter_synthetic_", dir=fixture_home))
    root = attempt / "original_package"
    quantum = root / "quantum"
    replay = root / "analysis/independent_replay"
    replay.mkdir(parents=True)
    (root / "SYNTHETIC_ONLY.txt").write_text("ARTIFICIAL GATE/REPLAY FIXTURE. NO REAL TRAINING OR STUDY FINDINGS. NOT FOR DELIVERY.\n")
    for path in HERE.glob("*.py"):
        shutil.copyfile(path, replay / path.name)
    oracle_source = REAL_STUDY / "analysis/classical_review/reference_v05.py"
    oracle_path = root / "analysis/classical_review/reference_v05.py"
    oracle_path.parent.mkdir(parents=True)
    shutil.copyfile(oracle_source, oracle_path)
    auditor = root / "analysis/classical_review/audit_endpoints_v05.py"
    auditor.write_text("# SYNTHETIC AUDIT SOURCE PLACEHOLDER; NOT AN ACTUAL AUDIT.\n")
    author_audit = quantum / "audit_endpoints.py"
    quantum.mkdir(parents=True)
    author_audit.write_text("# SYNTHETIC AUTHOR AUDIT PLACEHOLDER.\n")
    for name in ("models.py", "study.py", "circuits.py", "reference_v03.py", "prepare_data.py", "routers.py", "launch_stage.py"):
        (quantum / name).write_text("# SYNTHETIC TRAINING SOURCE PLACEHOLDER: " + name + "\n")
    (quantum / "tests").mkdir()
    (quantum / "tests/test_synthetic.py").write_text("# SYNTHETIC TRAINING TEST PLACEHOLDER.\n")
    protocol = json.loads((REAL_STUDY / "governance/ANALYSIS_PROTOCOL.json").read_text())
    write(root / "governance/ANALYSIS_PROTOCOL.json", protocol)
    write(root / "governance/LOCAL_READINESS_PROTOCOL.json", {"synthetic_only": True})
    stats_path = root / "analysis/statistics_v05.py"
    stats_path.write_text("# SYNTHETIC OFFICIAL STATISTICS SOURCE IDENTITY ONLY; not imported.\n")
    oracle = module(oracle_path, "independent_synthetic_oracle_" + attempt.name)
    # Scalar and vector independent oracle variants exercise the adapter I/O.
    # Statistics agreement with the real official implementation is separately
    # covered by the peer-reviewed independent statistical-core tests.
    data = quantum / "data"
    data.mkdir()
    populations = {}
    seal = {"schema": "SYNTHETIC_FIXTURE_NOT_STUDY_DATA", "files": {}, "routers": {}}
    for pi, name in enumerate(POPULATIONS):
        rng = np.random.Generator(np.random.PCG64(492000 + pi))
        x = rng.uniform(-1, 1, (records, 2)).astype(np.float64)
        policy = {"schema": "qpath-v03-input-route-1", "banks": 5,
                  "centroids": [[-.8, -.2], [-.4, .3], [0., 0.], [.4, -.3], [.8, .2]],
                  "hash_salt": f"SYNTHETIC-{pi}",
                  "hash_cutpoints_hex": [format((1 << 256) * numerator // 5, "064x") for numerator in (1, 2, 3, 4)]}
        routes = independent_routes(x, policy)
        population = {"x": x, "y": rng.integers(0, 2, records, dtype=np.int64),
                      "ids": 9000000000 + pi * 100000 + np.arange(records, dtype=np.int64),
                      "source_draw_ids": np.arange(records, dtype=np.int64),
                      "hash_route": routes["hash"], "kmeans_route": routes["kmeans"]}
        policy_path = data / (name + "_router.json")
        write(policy_path, policy)
        file = data / (name + "_SEALED_test.npz")
        np.savez(file, **population)
        seal["routers"][name] = {"sha256": digest(policy_path)}
        seal["files"][file.name] = {"sha256": digest(file), "n": records, "dataset": name, "split": "test",
                                   "router_policy_sha256": digest(policy_path),
                                   "arrays": {key: array_hash(value) for key, value in population.items()}}
        populations[name] = population
    seal_path = data / "DATA_SEAL.json"
    write(seal_path, seal)
    train_hashes = training_hashes(quantum)
    settings = {"rounds": 200, "batch_size": 64, "training_records": 4800, "validation_records": 1600, "optimizer_updates": 15000}
    freeze_path = quantum / "STAGE_B_FREEZE.json"
    write(freeze_path, {"review_status": "approved_by_root", "synthetic_only": True, "methods": list(METHODS),
                       "populations": list(POPULATIONS), "training_seeds": list(SEEDS), "settings": settings,
                       "source_hashes": train_hashes, "data_seal_sha256": digest(seal_path)})
    base_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    times = [(base_time + timedelta(minutes=i)).isoformat() for i in range(8)]
    endpoint_rows, independent_rows, canonical, reference, logits, reference_logits = [], [], {}, {}, {}, {}
    for pi, population in enumerate(POPULATIONS):
        pop = populations[population]
        for seed in SEEDS:
            for mi, method in enumerate(METHODS):
                folder = quantum / "stage_B" / population / f"seed_{seed}" / method
                folder.mkdir(parents=True)
                theta = np.random.Generator(np.random.PCG64([seed, mi, 419])).uniform(-.3, .3, oracle.PARAMETERS[method]).astype(np.float64)
                core=(np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1]))).uniform(-.1,.1,(5,4,2,2))[:,:2].copy()
                      if method=='qfrozen_kmeans' else np.empty((0,),dtype=np.float64))
                selected = 137
                checkpoint = {"parameters": theta, "core_parameters":core, "has_native_logits":method!="q2_kmeans",
                              "validation_evidence_present":True, "adam_m": np.zeros_like(theta), "adam_v": np.zeros_like(theta),
                              "adam_t": 75 * selected, "current_round": selected, "completed_rounds": selected}
                np.savez(folder / "selected_checkpoint.npz", **checkpoint)
                shutil.copyfile(folder / "selected_checkpoint.npz", folder / f"selected_round_{selected:04d}.npz")
                for filename in ("last_checkpoint.npz", "initial_state.npz", "round_parameters.npy", "validation_probabilities.npy",
                                 "record_orders.npy", "population_identity.npz", "ledger.jsonl", "round_gradient_means.npz",
                                 "validation_predictions.csv", "selected_training_gradient.npz"):
                    (folder / filename).write_bytes(b"SYNTHETIC STUB; NO ACTUAL TRAINING CLAIM\n")
                for filename in (["validation_native_losses.npy"]+(["validation_logits.npy"] if method!='q2_kmeans' else [])
                                 +(["frozen_cache.json","frozen_train_moments.npy","frozen_validation_moments.npy"] if method=='qfrozen_kmeans' else [])):
                    (folder/filename).write_bytes(b"SYNTHETIC STUB; NO ACTUAL TRAINING CLAIM\n")
                identity = {"population": population, "seed": seed, "method": method, "stage": "B", "engineering": False,
                            "test_accessed": False, "data_seal_sha256": digest(seal_path), "stage_freeze_sha256": digest(freeze_path)}
                config = {**identity, "source_hashes": train_hashes, "settings": settings, "rounds": 200,
                          "train_records": 4800, "validation_records": 1600}
                result = {**identity, "status": "completed", "completed_rounds": 200, "optimizer_global_updates": 15000,
                          "selected_round": selected}
                write(folder / "config.json", config)
                write(folder / "result.json", result)
                write(folder / "status.json", {"status": "completed", "round": 200})
                files = {path.name: metadata(path) for path in folder.iterdir() if path.is_file()}
                write(folder / "endpoint_commit.json", {"status": "completed", "test_accessed": False,
                      "population": population, "seed": seed, "method": method, "source_hashes": train_hashes, "files": files})
                endpoint_rows.append({"population": population, "seed": seed, "method": method, "selected_round": selected,
                                      "path": str(folder), "endpoint_commit_sha256": digest(folder / "endpoint_commit.json"), "files": files})
                independent_rows.append({"population": population, "seed": seed, "method": method, "selected_round": selected,
                                         "endpoint_commit_sha256": digest(folder / "endpoint_commit.json"), "rounds_verified": 200,
                                         "validation_predictions_replayed": 320000, "selected_checkpoint_sha256": digest(folder / "selected_checkpoint.npz")})
                route=None if method.endswith('_global') else pop['kmeans_route']
                cp,cz=oracle.scalar_predict_with_logits(method,theta,pop['x'],route,core if core.size else None)
                rp,rz=oracle.predict_with_logits(method,theta,pop['x'],route,core if core.size else None)
                canonical[(population,seed,method)]=cp;logits[(population,seed,method)]=cz
                reference[(population,seed,method)]=rp;reference_logits[(population,seed,method)]=rz
    write(quantum / "stage_B/stage_status.json", {"status": "completed", "stage": "B", "expected_endpoints": 165,
          "committed_endpoints": 165, "exits": [{"seed": seed, "exit_code": 0} for seed in SEEDS]})
    protocol_path = root / "governance/ANALYSIS_PROTOCOL.json"
    lock_path = quantum / "CONFIRMATION_ENDPOINT_LOCK.json"
    write(lock_path, {"status": "PASS", "stage": "B", "endpoint_count": 165, "engineering": False,
          "source_hashes": train_hashes, "data_seal_sha256": digest(seal_path), "stage_freeze_sha256": digest(freeze_path),
          "analysis_protocol_sha256": digest(protocol_path), "audit_source_hashes": {str(author_audit): digest(author_audit)},
          "created_utc": times[0], "test_accessed":False, "endpoints": endpoint_rows, "synthetic_only": True})
    independent_audit = root / "analysis/classical_review/SYNTHETIC_AUDIT.json"
    write(independent_audit, {"status": "PASS", "stage": "B", "endpoint_count": 165, "engineering": False,
          "model_test_outcomes_accessed": False, "validation_rounds_replayed": 33000, "validation_predictions_replayed":52800000, "endpoint_lock_sha256": digest(lock_path),
          "analysis_protocol_sha256": digest(protocol_path), "data_seal_sha256": digest(seal_path), "auditor_sha256": digest(auditor),
          "independent_source_sha256": {path.name: digest(path) for path in (auditor, oracle_path)},
          "created_utc": times[1], "endpoints": independent_rows, "synthetic_only": True})
    review = quantum / "CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json"
    write(review, {"status": "PASS", "stage": "B", "endpoint_count": 165, "endpoint_lock_sha256": digest(lock_path),
          "independent_audit_path": independent_audit.relative_to(root).as_posix(), "independent_audit_sha256": digest(independent_audit)})
    registry = quantum / "EVALUATION_REGISTRATION.json"
    write(registry, {"status": "REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS", "original_working_root": str(root),
          "methods": list(METHODS), "training_seeds": list(SEEDS), "populations": list(POPULATIONS),
          "expected_output_paths": sorted(expected_output_paths()), "training_source_hashes": train_hashes,
          "source_hashes": {path.relative_to(root).as_posix(): digest(path) for path in (stats_path, auditor, oracle_path, author_audit)},
          "independent_auditor_path": auditor.relative_to(root).as_posix(), "analysis_protocol_sha256": digest(protocol_path),
          "readiness_protocol_sha256": digest(root / "governance/LOCAL_READINESS_PROTOCOL.json"), "data_seal_sha256": digest(seal_path),
          "synthetic_only": True})
    ready = replay / "ANALYSIS_READY.json"
    evidence = replay / "SYNTHETIC_EVIDENCE.txt"
    evidence.write_text("Synthetic metadata contract only; not a real peer approval.\n")
    source_files = list(replay.glob("*.py")) + [oracle_path]
    write(ready, {"status": "READY_BEFORE_CONFIRMATION_TEST_ACCESS", "study_id": "QPATH-READOUT-v0.5",
          "registration_sha256": digest(registry), "analysis_protocol_sha256": digest(protocol_path),
          "source_hashes": {path.relative_to(root).as_posix(): digest(path) for path in source_files},
          "evidence_hashes": {evidence.relative_to(root).as_posix(): digest(evidence)},
          "independent_oracle_path": oracle_path.relative_to(root).as_posix(), "independent_oracle_sha256": digest(oracle_path), "synthetic_only": True})
    release = quantum / "EVALUATION_RELEASE.json"
    bindings = {"registration_sha256": registry, "independent_replay_ready_sha256": ready, "endpoint_lock_sha256": lock_path,
                "independent_endpoint_review_sha256": review, "stage_freeze_sha256": freeze_path, "data_seal_sha256": seal_path,
                "analysis_protocol_sha256": protocol_path, "readiness_protocol_sha256": root / "governance/LOCAL_READINESS_PROTOCOL.json"}
    write(release, {"status": "released_by_root", "study_id": "QPATH-READOUT-v0.5",
          "scope": "all_165_registered_confirmation_endpoints_once", "release_id": "SYNTHETIC_ONLY_NO_REAL_AUTHORITY",
          "created_utc": times[2], **{key: digest(path) for key, path in bindings.items()}, "synthetic_only": True})
    output = quantum / "confirmation_evaluation"
    output.mkdir()
    write(output / "ACCESS_EVENT.json", {"release_id": "SYNTHETIC_ONLY_NO_REAL_AUTHORITY", "created_utc": times[3],
          "registration_sha256": digest(registry), "endpoint_lock_sha256": digest(lock_path), "populations": list(POPULATIONS)})
    summaries = {}
    for population in POPULATIONS:
        pop = populations[population]
        p_all = np.empty((5, 11, records))
        reports = []
        for si, seed in enumerate(SEEDS):
            for mi, method in enumerate(METHODS):
                p = canonical[(population, seed, method)]; q = reference[(population, seed, method)]
                p_all[si, mi] = p
                z=logits[(population,seed,method)];w=reference_logits[(population,seed,method)]
                destination = output / population / f"seed_{seed}" / method
                destination.mkdir(parents=True)
                predictions = destination / "predictions.csv"
                with predictions.open("x", newline="", encoding="utf-8") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(["record_id", "hash_route", "kmeans_route", "label", "probability", "prediction", "native_logit"])
                    writer.writerows(zip(pop["ids"], pop["hash_route"], pop["kmeans_route"], pop["y"], p, (p >= .5).astype(int), [""]*len(p) if z is None else z))
                numeric = diagnostics(pop["y"], p, q, pop["ids"], {kind: pop[kind + "_route"] for kind in ("hash", "kmeans")}, protocol["numerical"])
                numeric['canonical_metrics']=metric_shape(pop['y'],p)
                numeric['raw_reference_metrics']=metric_shape(pop['y'],q)
                native=native_diagnostics(method,pop['y'],p,z,q,w,protocol['numerical'])
                numeric['native']={'has_native_logits':False} if z is None else {
                    'has_native_logits':True,'maximum_logit_error':native['maximum_native_logit_error'],
                    'independent_native_loss':native['reference_native_bce'],'native_loss_error':native['independent_native_loss_error']}
                report = {"population": population, "seed": seed, "method": method, "selected_round": 137,
                          "checkpoint_sha256": digest(quantum / "stage_B" / population / f"seed_{seed}" / method / "selected_checkpoint.npz"),
                          "metrics": metric_shape(pop["y"], p), "native_diagnostics":native_shape(pop["y"],p,z),
                          "training_objective":objective(method),"work":forward_work(method,records), "prediction_sha256": digest(predictions), "numerical_verification": numeric,
                          "route_counts": {kind: np.bincount(pop[kind + "_route"], minlength=5).tolist() for kind in ("hash", "kmeans")},
                          "by_route": {kind: {str(bank): metric_shape(pop["y"][pop[kind + "_route"] == bank], p[pop[kind + "_route"] == bank])
                                               for bank in range(5) if np.any(pop[kind + "_route"] == bank)} for kind in ("hash", "kmeans")}}
                write(destination / "report.json", report)
                reports.append(report)
        statistics,counts,_=summarise_population(population,pop['y'],p_all,protocol)
        statistics.update(protocol_sha256=digest(protocol_path),statistics_source_sha256=digest(stats_path),numpy_version=np.__version__)
        stats_folder=output/population/'statistics';stats_folder.mkdir()
        np.save(stats_folder/'bootstrap_counts.npy',counts,allow_pickle=False)
        write(stats_folder/'population_summary.json',statistics)
        summaries[population] = {"statistics": statistics, "numerical_verification": numerical_summary(reports)}
    write(output / "summary.json", {"status": "completed", "study_id": "QPATH-READOUT-v0.5", "report_count": 165,
          "population_order": list(POPULATIONS), "method_order": list(METHODS), "training_seeds": list(SEEDS),
          "populations": summaries, "release_id": "SYNTHETIC_ONLY_NO_REAL_AUTHORITY", "registration_sha256": digest(registry),
          "endpoint_lock_sha256": digest(lock_path), "analysis_protocol_sha256": digest(protocol_path), "completed_utc": times[4]})
    files = {path.relative_to(output).as_posix(): metadata(path) for path in output.rglob("*") if path.is_file()}
    if set(files) != expected_output_paths():
        raise AssertionError("Synthetic official payload contract differs")
    write(output / "EVALUATION_COMMIT.json", {"status": "completed", "study_id": "QPATH-READOUT-v0.5",
          "report_count": 165, "prediction_file_count": 165, "population_count": 3, "payload_count": 338,
          "release_id": "SYNTHETIC_ONLY_NO_REAL_AUTHORITY", "release_sha256": digest(release), "registration_sha256": digest(registry),
          "endpoint_lock_sha256": digest(lock_path), "files": files, "completed_utc": times[5]})
    return {"attempt": attempt, "root": root, "release": release, "ready": ready, "records": records,
            "source_hashes": {path.name: digest(path) for path in HERE.glob("*.py")}}
