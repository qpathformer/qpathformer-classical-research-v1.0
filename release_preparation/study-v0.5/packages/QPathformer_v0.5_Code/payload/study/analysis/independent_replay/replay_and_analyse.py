"""Run once after root release and completed official v0.5 evaluation.

All165 selected checkpoints and every test record are replayed with the
independent model oracle. No official evaluator/model/statistics helper imports.
Failures remain preserved, and a full payload commit is written only on PASS.
"""
import sys
sys.dont_write_bytecode = True
import argparse
from bisect import bisect_left
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import traceback
import numpy as np

from evidence_io import (compare_structure, contained, digest, inventory, read_bound,
                         recheck, require)
from official_comparison import (check_metrics, check_official_numerical, check_population_summary,
    metric_shape, check_native, objective, forward_work)
from release_gate import METHODS, POPULATIONS, SEEDS, expected_output_paths, timestamp, validate_gate
from statistics_reference import interval, metrics, summarise_population
from threshold_reference import CASES, diagnostics
from prediction_reference import replay_checkpoint

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def array_hash(array):
    value = np.ascontiguousarray(array)
    result = hashlib.sha256(str(value.dtype).encode() + str(value.shape).encode() + value.tobytes())
    return result.hexdigest()


def independent_routes(x, policy):
    """Direct geometry and coordinate SHA replay, with no production router."""
    require(policy["schema"] == "qpath-v03-input-route-1" and policy["banks"] == 5,
            "Unexpected retained router algorithm identity")
    centers = np.asarray(policy["centroids"], dtype=np.float64)
    require(centers.shape == (5, 2) and np.isfinite(centers).all()
            and np.array_equal(np.lexsort((centers[:, 1], centers[:, 0])), np.arange(5)), "Router centroids differ")
    geometric = np.array([min(range(5), key=lambda j: (float(point[0]) - float(centers[j, 0])) ** 2
                             + (float(point[1]) - float(centers[j, 1])) ** 2) for point in x], dtype=np.int64)
    coordinates = np.array(x, dtype="<f8", order="C", copy=True)
    coordinates[coordinates == 0] = 0.
    salt = policy["hash_salt"]
    require(isinstance(salt, str) and salt.isascii() and salt, "Invalid coordinate-hash salt")
    prefix = b"QPATH-V03-HASH5\x00" + salt.encode("ascii") + b"\x00"
    cuts = policy["hash_cutpoints_hex"]
    require(len(cuts) == 4 and cuts == sorted(set(cuts))
            and all(len(value) == 64 and all(c in "0123456789abcdef" for c in value) for value in cuts), "Invalid hash cuts")
    hashed = np.array([bisect_left(cuts, hashlib.sha256(prefix + point.tobytes()).hexdigest())
                       for point in coordinates], dtype=np.int64)
    return {"hash": hashed, "kmeans": geometric}


def load_population(context, population, expected_records):
    """Called only after gate PASS and durable ACCESS_EVENT."""
    filename = population + "_SEALED_test.npz"
    metadata = context["seal"]["files"][filename]
    path = context["quantum"] / "data" / filename
    require(digest(path) == metadata["sha256"], "Released sealed data hash differs")
    context["watched"][str(path.resolve())] = metadata["sha256"]
    with np.load(path, allow_pickle=False) as payload:
        data = {key: payload[key] for key in payload.files}
    require(set(data) == {"x", "y", "ids", "source_draw_ids", "hash_route", "kmeans_route"}, "Data field contract differs")
    require(metadata["n"] == len(data["y"]) == expected_records
            and metadata["dataset"] == population and metadata["split"] == "test", "Released split identity/count differs")
    require(data["x"].shape == (expected_records, 2) and data["x"].dtype == np.float64
            and np.isfinite(data["x"]).all() and (np.abs(data["x"]) <= 1).all(), "Invalid raw coordinate matrix")
    for name in ("y", "ids", "source_draw_ids", "hash_route", "kmeans_route"):
        require(data[name].shape == (expected_records,) and data[name].dtype == np.int64, "Invalid integer data field")
    require(np.isin(data["y"], (0, 1)).all() and len(set(data["ids"].tolist())) == expected_records, "Invalid labels/record IDs")
    require(metadata["arrays"] == {key: array_hash(value) for key, value in data.items()}, "Released array identities differ")
    policy_path = context["quantum"] / "data" / (population + "_router.json")
    policy = read_bound(policy_path, context["watched"])
    require(context["watched"][str(policy_path.resolve())] == context["seal"]["routers"][population]["sha256"]
            == metadata["router_policy_sha256"], "Released router policy differs")
    reconstructed = independent_routes(data["x"], policy)
    for kind in ("hash", "kmeans"):
        require(np.array_equal(data[kind + "_route"], reconstructed[kind]), "Released route cache differs from independent routing")
    return data


def read_predictions(path, population, method):
    columns = ["record_id", "hash_route", "kmeans_route", "label", "probability", "prediction", "native_logit"]
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == columns, "Prediction CSV columns differ")
        rows = list(reader)
    require(len(rows) == len(population["y"]), "Prediction CSV record count differs")
    probability = np.empty(len(rows), dtype=np.float64)
    logits = None if method == 'q2_kmeans' else np.empty(len(rows),dtype=np.float64)
    for index, row in enumerate(rows):
        for field, key in (("record_id", "ids"), ("hash_route", "hash_route"), ("kmeans_route", "kmeans_route"), ("label", "y")):
            require(int(row[field]) == int(population[key][index]), "Prediction identity/order/label differs")
        probability[index] = float(row["probability"])
        require(np.isfinite(probability[index]) and 0 <= probability[index] <= 1
                and int(row["prediction"]) == int(probability[index] >= .5), "Invalid canonical prediction")
        if logits is None: require(row['native_logit']=='', 'Legacy CSV native logit must be blank')
        else:
            logits[index]=float(row['native_logit'])
            require(np.isfinite(logits[index]), 'Finite native CSV logit required')
    return probability, logits


def numerical_summary(reports):
    fields = ("n", "canonical_near_band", "reference_near_band", "union_near_band", "class_disagreements", "outside_band_class_disagreements")
    totals = {field: sum(row["numerical_verification"]["counts"][field] for row in reports) for field in fields}
    methods = {}
    for method in METHODS:
        chosen = [next(row for row in reports if row["method"] == method and row["seed"] == seed) for seed in SEEDS]
        sensitivity = {}
        for case in CASES:
            sensitivity[case] = {}
            for metric in ("macro_f1", "accuracy"):
                values = [row["numerical_verification"]["sensitivity"][case][metric] for row in chosen]
                result = interval(values)
                sensitivity[case][metric] = {"seed_values": values, "mean": result["mean"], "sample_sd": result["sample_sd"]}
        methods[method] = {"per_seed_counts": [{"seed": row["seed"], **row["numerical_verification"]["counts"]} for row in chosen],
                           "sensitivity": sensitivity}
    return {"counts": totals, "exact_class_agreement": totals["class_disagreements"] == 0, "methods": methods}


def expected_replay_paths():
    expected = {"ACCESS_EVENT.json", "summary.json"}
    for population in POPULATIONS:
        expected.update(f"{population}/{filename}" for filename in
                        ("population_summary.json", "probabilities_replayed.npz", "bootstrap_counts.npy", "bootstrap_values.npy"))
        expected.update(f"{population}/seed_{seed}/{method}/report.json" for seed in SEEDS for method in METHODS)
    return expected


def run_replay(study, release_path, ready_path, output, *, expected_records=1600):
    """Synthetic tests can use smaller arrays; CLI always enforces1600 records."""
    output = Path(output).resolve()
    require(not output.exists(), "Preserve previous replay output; no retry in place")
    context = validate_gate(study, release_path, ready_path)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    access = {"event": "Independent replay starts after root release and actual official completion",
              "created_utc": now(), "release_id": context["release"]["release_id"],
              "release_sha256": digest(release_path), "official_commit_sha256": digest(context["paths"]["commit"]),
              "registration_sha256": digest(context["paths"]["registration"]),
              "ready_sha256": digest(ready_path), "relocation": context["relocation"]}
    write_json(output / "ACCESS_EVENT.json", access)
    try:
        official_output = context["quantum"] / "confirmation_evaluation"
        complete_inventory = inventory(official_output, context["commit"]["files"],
                                       exclude=("EVALUATION_COMMIT.json",), expected=expected_output_paths())
        for name, info in context["commit"]["files"].items():
            context["watched"][str(contained(official_output, name).resolve())] = info["sha256"]
        official_summary = read_bound(official_output / "summary.json", context["watched"])
        official_access = read_bound(official_output / "ACCESS_EVENT.json", context["watched"])
        require(official_summary["status"] == "completed" and official_summary["study_id"] == "QPATH-READOUT-v0.5"
                and official_summary["report_count"] == 165 and official_summary["population_order"] == list(POPULATIONS)
                and official_summary["method_order"] == list(METHODS) and official_summary["training_seeds"] == list(SEEDS),
                "Official summary completion identity differs")
        for key, path in (("registration_sha256", context["paths"]["registration"]),
                          ("endpoint_lock_sha256", context["paths"]["lock"]),
                          ("analysis_protocol_sha256", context["paths"]["analysis"])):
            require(official_summary[key] == digest(path), "Official summary binding differs: " + key)
        require(official_summary["release_id"] == official_access["release_id"] == context["release"]["release_id"], "Official access/release differs")
        require(official_access["registration_sha256"] == digest(context["paths"]["registration"])
                and official_access["endpoint_lock_sha256"] == digest(context["paths"]["lock"])
                and official_access["populations"] == list(POPULATIONS), "Official access identities differ")
        require(timestamp(context["release"]["created_utc"]) <= timestamp(official_access["created_utc"])
                <= timestamp(official_summary["completed_utc"]) <= timestamp(context["commit"]["completed_utc"])
                <= timestamp(access["created_utc"]), "Release/access/completion chronology differs")
        specification = importlib.util.spec_from_file_location("registered_independent_v05_oracle", context["oracle_path"])
        oracle = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(oracle)
        populations, all_reports, comparisons, all_ids = {}, [], [], set()
        max_probability_error, max_bce_error, max_logit_error, max_native_loss_error = 0., 0., 0., 0.
        for name in POPULATIONS:
            population = load_population(context, name, expected_records)
            require(all_ids.isdisjoint(population["ids"].tolist()), "Record identities overlap across confirmation populations")
            all_ids.update(population["ids"].tolist())
            p_all = np.empty((5, 11, expected_records), dtype=np.float64)
            q_all = np.empty_like(p_all)
            z_all = np.full_like(p_all, np.nan)
            w_all = np.full_like(p_all, np.nan)
            reports, official_reports = [], []
            destination = output / name
            destination.mkdir(exist_ok=False)
            for si, seed in enumerate(SEEDS):
                for mi, method in enumerate(METHODS):
                    endpoint = context["endpoints"][(name, seed, method)]
                    endpoint_folder = context["quantum"] / "stage_B" / name / f"seed_{seed}" / method
                    checkpoint_path = endpoint_folder / "selected_checkpoint.npz"
                    with np.load(checkpoint_path, allow_pickle=False) as checkpoint:
                        theta = checkpoint["parameters"]
                        core = checkpoint['core_parameters']
                        require(core.dtype==np.float64 and np.isfinite(core).all(), 'Invalid fixed core payload')
                        if method=='qfrozen_kmeans':
                            expected_core=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1]))).uniform(-.1,.1,(5,4,2,2))[:,:2]
                            require(core.shape==(5,2,2,2) and np.array_equal(core,expected_core), 'Frozen core initialization identity differs')
                        else: require(core.shape==(0,), 'Unexpected separate core parameters')
                        require(bool(checkpoint['has_native_logits'])==(method!='q2_kmeans')
                                and bool(checkpoint['validation_evidence_present']), 'Checkpoint native/evidence flags differ')
                        require(theta.shape == (oracle.PARAMETERS[method],) and theta.dtype == np.float64
                                and np.isfinite(theta).all(), "Selected parameter schema differs")
                        require(int(checkpoint["current_round"]) == int(checkpoint["completed_rounds"]) == endpoint["selected_round"]
                                and int(checkpoint["adam_t"]) == 75 * endpoint["selected_round"], "Selected checkpoint horizon differs")
                    original = official_output / name / f"seed_{seed}" / method
                    recorded = read_bound(original / "report.json", context["watched"])
                    require((recorded["population"], recorded["seed"], recorded["method"], recorded["selected_round"])
                            == (name, seed, method, endpoint["selected_round"]), "Official report identity differs")
                    require(recorded["checkpoint_sha256"] == digest(checkpoint_path)
                            and recorded["prediction_sha256"] == digest(original / "predictions.csv"), "Official report payload links differ")
                    p, z = read_predictions(original / "predictions.csv", population, method)
                    q = w = None
                    endpoint_output = destination / f"seed_{seed}" / method
                    endpoint_output.mkdir(parents=True, exist_ok=False)
                    try:
                        q,w,replayed = replay_checkpoint(oracle,method,theta,core,population['x'],population['y'],population['ids'],
                            {kind:population[kind+'_route'] for kind in ('hash','kmeans')},p,z,context['protocol']['numerical'])
                        numerical=replayed['numerical_verification'];native=replayed['native_verification']
                        canonical_check = check_metrics(metric_shape(population['y'],p), recorded["metrics"])
                        numerical_check = check_official_numerical(population["y"], p, population["ids"],
                            {kind: population[kind + "_route"] for kind in ("hash", "kmeans")},
                            recorded["numerical_verification"], numerical, context["protocol"]["numerical"])
                        native_check=check_native(population['y'],p,z,recorded['native_diagnostics'],
                            recorded['numerical_verification']['native'],context['protocol']['numerical'])
                        require(recorded['training_objective']==objective(method), 'Reported training objective differs')
                        compare_structure(forward_work(method,expected_records),recorded['work'])
                    except BaseException:
                        np.savez(endpoint_output / "FAILED_COMPARISON.npz", parameters=theta,core_parameters=core,canonical=p,
                                 reference=np.array([]) if q is None else q,canonical_logits=np.array([]) if z is None else z,
                                 reference_logits=np.array([]) if w is None else w,
                                 ids=population["ids"], y=population["y"], hash_route=population["hash_route"],
                                 kmeans_route=population["kmeans_route"])
                        raise
                    expected_by_route = {}
                    for kind in ("hash", "kmeans"):
                        values = population[kind + "_route"]
                        require(recorded["route_counts"][kind] == np.bincount(values, minlength=5).tolist(), "Official route counts differ")
                        expected_by_route[kind] = {str(bank): metric_shape(population["y"][values == bank], p[values == bank])
                                                   for bank in range(5) if np.any(values == bank)}
                    compare_structure(expected_by_route, recorded["by_route"])
                    report = {"status": "PASS", "population": name, "seed": seed, "method": method,
                              "selected_round": endpoint["selected_round"], "checkpoint_sha256": digest(checkpoint_path),
                              "official_report_sha256": digest(original / "report.json"),
                              "prediction_sha256": digest(original / "predictions.csv"),
                              "numerical_verification": numerical, "canonical_metric_check": canonical_check,
                              "native_verification":native,"official_native_consistency":native_check,
                              "canonical_calibration":replayed['canonical_calibration'],"reference_calibration":replayed['reference_calibration'],
                              "training_objective":objective(method),"verified_uncached_forward_work":forward_work(method,expected_records),
                              "official_numerical_consistency": numerical_check}
                    write_json(endpoint_output / "report.json", report)
                    p_all[si, mi], q_all[si, mi] = p, q
                    if z is not None: z_all[si,mi],w_all[si,mi]=z,w
                    reports.append(report); all_reports.append(report); official_reports.append(recorded)
                    max_probability_error = max(max_probability_error, numerical["maximum_probability_error"])
                    max_bce_error = max(max_bce_error, numerical["independent_bce_error"])
                    max_logit_error=max(max_logit_error,native['maximum_native_logit_error'] or 0.)
                    max_native_loss_error=max(max_native_loss_error,native['independent_native_loss_error'])
            own_summary, counts, bootstrap = summarise_population(name, population["y"], p_all, context["protocol"])
            official_statistics_path = official_output / name / "statistics" / "population_summary.json"
            recorded_statistics = read_bound(official_statistics_path, context["watched"])
            compare_structure(official_summary["populations"][name]["statistics"], recorded_statistics)
            statistical_check = check_population_summary(own_summary, recorded_statistics,
                digest(context["paths"]["analysis"]), context["registration"]["source_hashes"]["analysis/statistics_v05.py"])
            with (official_output / name / "statistics" / "bootstrap_counts.npy").open("rb") as handle:
                original_counts = np.load(handle, allow_pickle=False)
            require(original_counts.dtype == np.uint16 and np.array_equal(original_counts, counts)
                    and digest(official_output / name / "statistics" / "bootstrap_counts.npy") == own_summary["bootstrap_counts_sha256"],
                    "Exact registered bootstrap count matrix/hash differs")
            reconstructed_official_numerical = numerical_summary(official_reports)
            official_numeric = official_summary["populations"][name]["numerical_verification"]
            compare_structure(reconstructed_official_numerical, {key: official_numeric[key] for key in reconstructed_official_numerical})
            own_numerical = numerical_summary(reports)
            populations[name] = {"statistics": own_summary, "numerical_verification": own_numerical,
                                 "official_statistics_check": statistical_check, "records": expected_records,
                                 "official_author_numerical_summary_consistent": True}
            write_json(destination / "population_summary.json", populations[name])
            np.save(destination / "bootstrap_counts.npy", counts, allow_pickle=False)
            np.save(destination / "bootstrap_values.npy", bootstrap, allow_pickle=False)
            np.savez(destination / "probabilities_replayed.npz", canonical=p_all, independent_reference=q_all,
                     canonical_native_logits=z_all,independent_reference_native_logits=w_all,
                     has_native_logits=np.array([method!='q2_kmeans' for method in METHODS]),
                     record_ids=population["ids"], labels=population["y"], hash_route=population["hash_route"],
                     kmeans_route=population["kmeans_route"])
            comparisons.append(statistical_check)
            print(json.dumps({"population": name, "status": "PASS", "endpoints": 55,
                              "bootstrap_counts_sha256": own_summary["bootstrap_counts_sha256"]}), flush=True)
        require(len(all_reports) == 165, "Incomplete replay")
        recheck(context["watched"])
        totals = {key: sum(populations[name]["numerical_verification"]["counts"][key] for name in POPULATIONS)
                  for key in ("n", "canonical_near_band", "reference_near_band", "union_near_band",
                              "class_disagreements", "outside_band_class_disagreements")}
        summary = {"status": "PASS", "study_id": "QPATH-READOUT-v0.5", "endpoint_count": 165,
                   "prediction_pairs_replayed": 165 * expected_records, "population_count": 3,
                   "population_order": list(POPULATIONS), "methods": list(METHODS), "training_seeds": list(SEEDS),
                   "maximum_probability_error": max_probability_error, "maximum_aggregate_bce_error": max_bce_error,
                   "maximum_native_logit_error":max_logit_error,"maximum_native_aggregate_loss_error":max_native_loss_error,
                   "numerical_totals": totals, "exact_class_agreement": totals["class_disagreements"] == 0,
                   "populations": populations, "official_committed_inventory": complete_inventory,
                   "release_sha256": access["release_sha256"], "official_commit_sha256": access["official_commit_sha256"],
                   "ready_sha256": access["ready_sha256"], "registration_sha256": access["registration_sha256"],
                   "analysis_protocol_sha256": digest(context["paths"]["analysis"]),
                   "source_hashes": context["ready"]["source_hashes"], "relocation": context["relocation"],
                   "elapsed_seconds": time.perf_counter() - started, "completed_utc": now(),
                   "interpretation": f"165 checkpoints on three separate {expected_records}-record populations; repeated checkpoint-record pairs are not independent task replications. Canonical metrics remain authoritative. Independent probabilities, native logits/loss, Brier/calibration, raw classes, numerical-band sensitivities, paired-five-seed intervals and conditional 10000-replicate paired-record bootstrap are disclosed separately. Legacy Born-probability clipped loss and native logit training losses differ. NaN entries in saved logit arrays represent the explicitly masked legacy method only. No equivalence or universal quantum-advantage inference."}
        write_json(output / "summary.json", summary)
        payloads = {path.relative_to(output).as_posix(): {"sha256": digest(path), "bytes": path.stat().st_size}
                    for path in output.rglob("*") if path.is_file()}
        require(set(payloads) == expected_replay_paths(), "Replay exact output inventory differs")
        recheck(context["watched"])
        write_json(output / "REPLAY_COMMIT.json", {"status": "completed", "study_id": "QPATH-READOUT-v0.5",
                   "endpoint_count": 165, "population_count": 3, "payload_count": len(payloads), "files": payloads,
                   "release_sha256": access["release_sha256"], "official_commit_sha256": access["official_commit_sha256"],
                   "ready_sha256": access["ready_sha256"], "analysis_protocol_sha256": summary["analysis_protocol_sha256"],
                   "completed_utc": now()})
        print(json.dumps({"status": "PASS", "output": str(output), "summary_sha256": digest(output / "summary.json"),
                          "replay_commit_sha256": digest(output / "REPLAY_COMMIT.json")}), flush=True)
        return summary
    except BaseException as error:
        write_json(output / "FAILURE.json", {"status": "FAIL", "created_utc": now(), "error": str(error),
                   "traceback": traceback.format_exc(), "recovery": "Preserve all partial outputs. No automatic retry, overwrite or model changes."})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(args.output.resolve().parent == HERE, "Replay output must be a new direct child of the independent replay folder")
    run_replay(STUDY, args.release, HERE / "ANALYSIS_READY.json", args.output, expected_records=1600)


if __name__ == "__main__":
    main()
