"""Independent sealed text checkpoint replay and registered v0.2 statistics.

Run only after the root-issued test release AND completion of its evaluation.
No test reads or CUDA work occur before those identities are checked. This
script does not import the runner's metric, evaluation, or checkpoint helpers.
It uses the frozen model definition with original loop adapter dispatch.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import sys
import time
import unicodedata

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "4"
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
import numpy as np

TASK = Path(__file__).resolve().parents[2]
CLASSICAL = TASK / "classical"
LABELS = 14
T95_DF4 = 2.7764451051977987
REGISTERED_ANALYSIS_PROTOCOL_SHA256 = "9b409934d07e8eb7a6380a02fe93780cab3323401d595c846da1b2ce7ba1e414"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")


def canonical_hash(text):
    text = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def metrics(labels, predictions, weights=None):
    n = len(labels)
    assert predictions.shape == labels.shape and np.all((predictions >= 0) & (predictions < LABELS))
    matrix = np.bincount(labels * LABELS + predictions, weights=weights, minlength=LABELS ** 2).reshape(LABELS, LABELS)
    denominator = matrix.sum(axis=0) + matrix.sum(axis=1)
    f1 = np.divide(2 * matrix.diagonal(), denominator, out=np.zeros(LABELS), where=denominator != 0)
    return {"macro_f1": float(f1.mean()), "accuracy": float(matrix.trace() / matrix.sum()),
            "per_label_f1": f1.tolist(), "confusion_matrix": matrix.tolist(), "records": n}


def describe(values, interval=True):
    values = np.asarray(values, dtype=float)
    result = {"n": len(values), "mean": float(values.mean()), "sample_sd": float(values.std(ddof=1)),
              "minimum": float(values.min()), "maximum": float(values.max()), "values": values.tolist()}
    if interval:
        assert len(values) == 5
        half = T95_DF4 * result["sample_sd"] / math.sqrt(5)
        result["descriptive_t95_interval"] = [result["mean"] - half, result["mean"] + half]
    return result


def occupancy(routes, count):
    counts = np.bincount(routes, minlength=count)
    probabilities = counts / counts.sum()
    nonzero = probabilities[probabilities > 0]
    entropy = -float(np.sum(nonzero * np.log(nonzero)))
    return {"records": len(routes), "adapter_counts": counts.tolist(), "active_adapters": int((counts > 0).sum()),
            "maximum_adapter_fraction": float(probabilities.max()), "entropy_nats": entropy,
            "normalized_entropy": entropy / math.log(count) if count > 1 else 0.0,
            "effective_adapters": math.exp(entropy)}


def validate_gate(release_path):
    """Inspect metadata/checkpoint hashes only; never open sealed test payloads."""
    release = read(release_path)
    protocol_path = CLASSICAL / "protocol_stage_b_frozen.json"
    protocol = read(protocol_path)
    protocol_hash = sha(protocol_path)
    selection_path = CLASSICAL / "selection_frozen.json"
    selection = read(selection_path)
    selected = selection["selected_candidate"]
    assert selected in ("frozen_content", "hash18")
    methods = ["shared", "current_content", selected]
    assert protocol["seeds"] == [401, 402, 403, 404, 405] and protocol["methods"] == methods
    assert protocol["configuration"]["labels"] == LABELS
    assert protocol["schedules"]["main_updates"] == 10000 and protocol["schedules"]["warmup_updates"] == 1000
    assert release["authorized"] is True and release["release_type"] == "independent_evaluation_after_all_training"
    assert release["stage_b_protocol_sha256"] == protocol_hash
    assert release["selection_sha256"] == sha(selection_path) == protocol["selection_sha256"]
    assert release["data_manifest_sha256"] == sha(CLASSICAL / "data" / "manifest.json") == protocol["data_manifest_sha256"]
    assert release["test_seal_sha256"] == sha(CLASSICAL / "data" / "TEST_SEAL.json")
    assert release["expected_test_rows"] == 14000 and release["created_utc"]
    for name, expected in protocol["code_sha256"].items():
        assert sha(CLASSICAL / name) == expected, name
    identities = {(s, m) for s in protocol["seeds"] for m in methods}
    assert len(release["endpoints"]) == 15
    assert {(r["seed"], r["method"]) for r in release["endpoints"]} == identities
    sources = {"release": {"path": str(release_path), "sha256": sha(release_path)},
               "protocol": {"path": str(protocol_path), "sha256": protocol_hash},
               "selection": {"path": str(selection_path), "sha256": sha(selection_path)}}
    endpoint_map = {}
    for row in release["endpoints"]:
        folder = CLASSICAL / "results" / "stage_b" / f"seed_{row['seed']}" / row["method"]
        state, commit = read(folder / "status.json"), read(folder / "checkpoint_commit.json")
        checkpoint = (CLASSICAL / "results" / "stage_b" / row["checkpoint_relative_path"]).resolve()
        assert checkpoint.is_relative_to(folder.resolve())
        assert state["status"] == "completed" and state["phase_update"] == state["latest_eligible_update"] == 10000
        assert not state["latest_eligible_in_common_warmup"] and state["protocol_sha256"] == protocol_hash
        assert commit["state"]["protocol_sha256"] == protocol_hash and commit["state"]["phase_update"] == 10000
        assert row["committed_main_update"] == 10000
        assert state["latest_eligible_checkpoint"] == row["checkpoint_relative_path"]
        assert checkpoint.name == commit["checkpoint"] and sha(checkpoint) == row["sha256"] == commit["sha256"]
        endpoint_map[(row["seed"], row["method"])] = dict(row, checkpoint=str(checkpoint), folder=str(folder), status=state)
        sources[f"endpoint_{row['seed']}_{row['method']}"] = {"path": str(checkpoint), "sha256": row["sha256"],
            "status_sha256": sha(folder / "status.json"), "commit_sha256": sha(folder / "checkpoint_commit.json")}
    evaluation = Path(release["output_directorynew"]).resolve()
    assert evaluation.is_relative_to(CLASSICAL.resolve())
    summary = read(evaluation / "summary.json")
    assert summary["status"] == "completed" and summary["release_sha256"] == sha(release_path)
    assert len(summary["reports"]) == 15
    assert {(r["seed"], r["method"]) for r in summary["reports"]} == identities
    sources["original_evaluation_summary"] = {"path": str(evaluation / "summary.json"), "sha256": sha(evaluation / "summary.json")}
    return release, protocol, selection, methods, endpoint_map, evaluation, sources


def stage_a_reconstruction(selection):
    protocol_path = CLASSICAL / "protocol_stage_a_frozen.json"
    protocol = read(protocol_path)
    assert sha(protocol_path) == selection["stage_a_protocol_sha256"]
    rows = []
    for seed in [301, 302, 303]:
        for method in ["shared", "current_content", "frozen_content", "hash18"]:
            folder = CLASSICAL / "results" / "stage_a" / f"seed_{seed}" / method
            state = read(folder / "status.json")
            assert state["status"] == "completed" and state["phase_update"] == state["latest_eligible_update"] == 3000
            assert state["protocol_sha256"] == sha(protocol_path)
            original = next(row for row in selection["seed_rows"] if row["seed"] == seed and row["method"] == method)
            assert sha(folder / "status.json") == original["status_sha256"]
            assert sha(CLASSICAL / "results" / "stage_a" / state["latest_eligible_checkpoint"]) == original["checkpoint_sha256"]
            assert original["f1"] == state["latest_validation"]["macro_f1"] and original["seconds"] == state["charged_total_seconds"]
            rows.append(original)
    averages = {m: {"macro_f1": float(np.mean([r["f1"] for r in rows if r["method"] == m])),
                    "charged_seconds": float(np.mean([r["seconds"] for r in rows if r["method"] == m]))}
                for m in protocol["methods"]}
    best = max(averages[m]["macro_f1"] for m in ["frozen_content", "hash18"])
    tied = [m for m in ["frozen_content", "hash18"] if averages[m]["macro_f1"] >= best - .001]
    winner = min(tied, key=lambda m: (averages[m]["charged_seconds"], m))
    assert winner == selection["selected_candidate"]
    delta = [next(r["f1"] for r in rows if r["seed"] == s and r["method"] == winner)
             - next(r["f1"] for r in rows if r["seed"] == s and r["method"] == "shared") for s in [301, 302, 303]]
    promising = averages[winner]["macro_f1"] >= max(averages[m]["macro_f1"] for m in ["shared", "current_content"]) - .002 and min(delta) >= -.005
    assert bool(promising) == selection["promising_gate"]
    return {"status": "PASS", "selected": winner, "promising_gate": bool(promising), "averages": averages, "per_seed": rows,
            "scope": "Development validation only; independently reconstructed frozen selection rule, not test evidence"}


def load_test_after_gate(protocol):
    data = CLASSICAL / "data"
    manifest, seal = read(data / "manifest.json"), read(data / "TEST_SEAL.json")
    for name in ["sealed/test.jsonl", "sealed/test_encoded.npz", "tokenizer.json", "tokenizer_provenance.json"]:
        assert sha(data / name) == manifest["file_sha256"][name]
    for name, expected in seal["file_sha256"].items():
        assert sha(data / "sealed" / name) == expected
    with (data / "sealed" / "test.jsonl").open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    assert len(records) == 14000
    labels = np.array([r["label"] for r in records], dtype=np.int64)
    assert Counter(labels) == Counter({label: 1000 for label in range(LABELS)})
    ids = np.array([r["id"] for r in records])
    hashes = np.array([canonical_hash(r["text"]) for r in records])
    assert len(set(ids)) == len(set(hashes)) == 14000
    assert np.array_equal(hashes, [r["duplicate_hash"] for r in records])
    assert hashlib.sha256("\n".join(ids).encode()).hexdigest() == seal["selected_record_ids_sha256"]
    with np.load(data / "sealed" / "test_encoded.npz", allow_pickle=False) as z:
        for field, expected in [("labels", labels), ("record_ids", ids), ("canonical_text_hashes", hashes)]:
            np.testing.assert_array_equal(z[field], expected)
        tokens, mask = z["tokens"].copy(), z["mask"].copy()
    assert tokens.shape == mask.shape == (14000, 256)
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(data / "tokenizer.json"))
    for start in range(0, 14000, 1024):
        encoded = tokenizer.encode_batch([r["text"] for r in records[start:start+1024]])
        np.testing.assert_array_equal(tokens[start:start+len(encoded)], [v.ids for v in encoded])
        np.testing.assert_array_equal(mask[start:start+len(encoded)], [v.attention_mask for v in encoded])
    return records, labels, ids, hashes, tokens, mask


def replay(endpoint, protocol, tokens, mask, records):
    import torch
    from qpath.classical import ModelConfig, QPathTextModel, FrozenRoutingEncoder
    payload = torch.load(endpoint["checkpoint"], map_location="cpu", weights_only=True)
    config = dict(protocol["configuration"])
    if endpoint["method"] == "shared":
        config["adapters"] = 1
    assert payload["model_config"] == config
    expected_mode = {"shared": "shared", "current_content": "content", "frozen_content": "frozen_content", "hash18": "hash18"}[endpoint["method"]]
    assert payload["route_mode"] == expected_mode
    assert payload["data_manifest_sha256"] == protocol["data_manifest_sha256"]
    assert payload["tokenizer_sha256"] == sha(CLASSICAL / "data" / "tokenizer.json")
    assert payload["run_state"]["protocol_sha256"] == sha(CLASSICAL / "protocol_stage_b_frozen.json")
    assert payload["run_state"]["phase_update"] == 10000
    model = QPathTextModel(ModelConfig(**config))
    if expected_mode == "frozen_content":
        model.frozen_router = FrozenRoutingEncoder(model)
    model.load_state_dict(payload["model"])
    model.centroids_fitted = payload["centroids_fitted"]
    model.centroid_training_ids = tuple(payload["centroid_training_ids"])
    model.route_mode, model.route_seed = payload["route_mode"], payload["route_seed"]
    model.dispatch_mode = "loop"
    model.cuda().eval()
    predictions, routes, nlls = [], [], []
    with torch.no_grad():
        for start in range(0, len(records), 64):
            stop = min(start + 64, len(records))
            width = int(mask[start:stop].sum(1).max())
            token_batch = torch.from_numpy(tokens[start:stop, :width].astype(np.int64)).cuda()
            mask_batch = torch.from_numpy(mask[start:stop, :width]).cuda()
            output = model(token_batch, mask_batch, texts=[r["text"] for r in records[start:stop]])
            logits = output["logits"].cpu().numpy().astype(np.float64)
            assert np.isfinite(logits).all()
            predictions.extend(logits.argmax(1).tolist())
            routes.extend(output["routes"].cpu().tolist())
            maximum = logits.max(1)
            logsumexp = maximum + np.log(np.exp(logits - maximum[:, None]).sum(1))
            nlls.extend((logsumexp - logits[np.arange(stop-start), [r["label"] for r in records[start:stop]]]).tolist())
    parameters = {"total": sum(p.numel() for p in model.parameters()), "trainable": sum(p.numel() for p in model.parameters() if p.requires_grad)}
    del model, payload
    torch.cuda.empty_cache()
    return np.array(predictions, dtype=np.int64), np.array(routes, dtype=np.int64), np.array(nlls), parameters


def training_summary(endpoint):
    folder = Path(endpoint["folder"])
    rows = [json.loads(line) for line in (folder / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["phase_update"] for r in rows] == list(range(100, 10001, 100))
    assert all(r["eligible"] for r in rows)
    state = endpoint["status"]
    assert rows[-1]["validation"] == state["latest_validation"]
    assert rows[-1]["checkpoint_sha256"] == endpoint["sha256"]
    assert rows[-1]["drift"]["counts"] == np.bincount(state["prior_probe_routes"], minlength=1 if endpoint["method"] == "shared" else 18).tolist()
    result = {"charged_total_seconds": state["charged_total_seconds"], "elapsed_seconds": state["elapsed_seconds"],
              "warmup_charged_seconds": state["warmup_charged_seconds"], "data_preparation_charged_seconds": state["data_preparation_charged_seconds"],
              "method_preparation_seconds": state["method_preparation_seconds"], "preparation_breakdown": state["preparation_breakdown"],
              "phase_peak_gpu_allocated_bytes": state["phase_peak_gpu_allocated_bytes"],
              "resumed_segments": state["resumed_segments"], "training_padded_token_positions": state["training_padded_token_positions"],
              "final_probe": {"occupancy": occupancy(np.array(state["prior_probe_routes"]), 1 if endpoint["method"] == "shared" else 18),
                              "fraction_changed_from_warmup": rows[-1]["drift"]["from_warmup"],
                              "fraction_changed_from_previous_check": rows[-1]["drift"]["from_previous"],
                              "scope": "Fixed1000 training records for this seed; evaluation-mode route snapshots"},
              "curve": [{"main_update": r["phase_update"], "validation_macro_f1": r["validation"]["macro_f1"],
                         "validation_cross_entropy": r["validation"]["cross_entropy"], "charged_seconds": r["charged_elapsed_seconds"],
                         "route_change_from_warmup": r["drift"]["from_warmup"]} for r in rows]}
    if (folder / "routing_cache.npz").exists():
        with np.load(folder / "routing_cache.npz", allow_pickle=False) as z:
            assert len(z["train_routes"]) == 100800 and len(z["validation_routes"]) == 11200
            result["immutable_cache_occupancy"] = {"train": occupancy(z["train_routes"], 18), "validation": occupancy(z["validation_routes"], 18),
                                                   "cache_sha256": sha(folder / "routing_cache.npz")}
    return result


def bootstrap(labels, predictions, losses, methods):
    """2000 paired unique-group resamples, fixed across all15 checkpoints."""
    rng = np.random.Generator(np.random.PCG64(88002))
    n = len(labels)
    codes = labels[None, :] * LABELS + predictions
    output = np.empty((2000, len(methods), 3), dtype=np.float64)
    # Metric order: macro F1, accuracy, NLL. Averaged over five fixed seeds.
    for iteration in range(2000):
        weights = rng.multinomial(n, np.full(n, 1 / n))
        matrices = np.stack([np.bincount(code, weights=weights, minlength=LABELS ** 2).reshape(LABELS, LABELS) for code in codes])
        diagonal = np.diagonal(matrices, axis1=1, axis2=2)
        denominator = matrices.sum(1) + matrices.sum(2)
        f1 = np.divide(2 * diagonal, denominator, out=np.zeros_like(diagonal, dtype=float), where=denominator != 0).mean(1)
        accuracy = diagonal.sum(1) / n
        nll = (losses @ weights) / n
        output[iteration] = np.stack([f1, accuracy, nll], axis=1).reshape(5, len(methods), 3).mean(0)
    return output


def self_test():
    truth = np.array([0, 0, 1, 1])
    pred = np.array([0, 1, 1, 1])
    calculated = metrics(truth, pred)
    assert math.isclose(calculated["macro_f1"], (2/3 + 4/5)/14)
    assert calculated["accuracy"] == .75
    weights = np.array([2, 0, 1, 1])
    indices = np.repeat(np.arange(4), weights)
    weighted = metrics(truth, pred, weights)
    expanded = metrics(truth[indices], pred[indices])
    assert weighted["confusion_matrix"] == expanded["confusion_matrix"]
    assert weighted["macro_f1"] == expanded["macro_f1"]
    assert describe([1, 1, 1, 1, 1])["descriptive_t95_interval"] == [1, 1]
    assert occupancy(np.array([0, 1, 0, 1]), 2)["normalized_entropy"] == 1.0
    toy_truth = np.arange(14)
    toy_predictions = np.tile(np.stack([(toy_truth + 1) % 14, toy_truth, toy_truth]), (5, 1))
    toy_losses = np.tile(np.stack([np.full(14, 2.), np.ones(14), np.ones(14)]), (5, 1))
    draws = bootstrap(toy_truth, toy_predictions, toy_losses, ["shared", "current", "selected"])
    assert draws.shape == (2000, 3, 3)
    np.testing.assert_array_equal(draws[:, 1], draws[:, 2])
    np.testing.assert_array_equal(draws[:, 0, 1], np.zeros(2000))
    np.testing.assert_array_equal(draws[:, 1, 1], np.ones(2000))
    np.testing.assert_array_equal(draws[:, :, 2], np.tile([2., 1., 1.], (2000, 1)))
    print("SELF_TEST_PASS: fixed14-class metric, weighted-resampling equivalence, paired interval, occupancy, full2000 paired15-model bootstrap; no study data read")


def main(args):
    started = time.perf_counter()
    assert not args.output.exists(), "Preserve earlier analyses; choose a new output directory"
    release, protocol, selection, methods, endpoints, evaluation, sources = validate_gate(args.release)
    analysis_protocol_path = TASK / "governance" / "ANALYSIS_PROTOCOL.json"
    assert sha(analysis_protocol_path) == REGISTERED_ANALYSIS_PROTOCOL_SHA256
    analysis_protocol = read(analysis_protocol_path)
    assert analysis_protocol["estimation"]["bootstrap_rng"] == "NumPy PCG64 seed 88002 for classical and 88003 for quantum"
    stage_a = stage_a_reconstruction(selection)
    args.output.mkdir(parents=True)
    save(args.output / "analysis_access_event.json", {"utc": datetime.now(timezone.utc).isoformat(), "release_sha256": sha(args.release),
         "gate": "All15 endpoints and original evaluation complete; root release identities verified before sealed data/CUDA access"})
    # All test access and CUDA initialization follow the complete release gate.
    records, labels, ids, hashes, tokens, mask = load_test_after_gate(protocol)
    import torch
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    sys.path.insert(0, str(CLASSICAL))
    def reject_network(*_, **__):
        raise RuntimeError("Independent analysis is local-only")
    socket.socket.connect = reject_network
    socket.socket.connect_ex = reject_network
    socket.create_connection = reject_network
    rows, all_predictions, all_losses = [], [], []
    differences = []
    for seed in range(401, 406):
        for method in methods:
            endpoint = endpoints[(seed, method)]
            name = f"seed_{seed}_{method}"
            prediction_path = evaluation / f"{name}_predictions.npz"
            report_path = evaluation / f"{name}_report.json"
            report = read(report_path)
            assert report["sha256"] == endpoint["sha256"] and report["seed"] == seed and report["method"] == method
            with np.load(prediction_path, allow_pickle=False) as z:
                np.testing.assert_array_equal(z["labels"], labels)
                np.testing.assert_array_equal(z["record_ids"], ids)
                np.testing.assert_array_equal(z["canonical_text_hashes"], hashes)
                saved_predictions, saved_routes = z["predictions"].copy(), z["routes"].copy()
            computed = metrics(labels, saved_predictions)
            for key in ["macro_f1", "accuracy"]:
                assert abs(computed[key] - report["metrics"][key]) < 1e-12
            assert computed["confusion_matrix"] == report["metrics"]["confusion_matrix"]
            replayed, routes, losses, parameters = replay(endpoint, protocol, tokens, mask, records)
            assert parameters == endpoint["status"]["parameter_counts"]
            mismatch = np.flatnonzero(replayed != saved_predictions)
            route_mismatch = np.flatnonzero(routes != saved_routes)
            nll_error = abs(float(losses.mean()) - report["metrics"]["cross_entropy"])
            difference = {"seed": seed, "method": method, "prediction_disagreements": len(mismatch),
                          "route_disagreements": len(route_mismatch), "cross_entropy_absolute_error": nll_error,
                          "disagreement_record_ids": ids[mismatch].tolist(), "route_disagreement_record_ids": ids[route_mismatch].tolist()}
            differences.append(difference)
            # Never hide numerical argmax changes: save an actionable mismatch
            # artifact and stop summary production for independent review.
            if len(mismatch) or len(route_mismatch) or nll_error > 1e-5:
                save(args.output / "REPLAY_REQUIRES_REVIEW.json", difference)
                np.savez(args.output / f"{name}_replay_disagreement.npz", predictions=replayed, saved_predictions=saved_predictions,
                         routes=routes, saved_routes=saved_routes, labels=labels, record_ids=ids, nll=losses)
                raise RuntimeError("Independent loop replay differs; preserve outputs and investigate before a PASS report")
            training = training_summary(endpoint)
            row = {"seed": seed, "method": method, "metrics": dict(computed, cross_entropy=float(losses.mean())),
                   "training": training, "deployment": report["deployment"], "parameter_counts": parameters,
                   "test_route_occupancy": occupancy(routes, 1 if method == "shared" else 18), "checkpoint_sha256": endpoint["sha256"]}
            rows.append(row)
            all_predictions.append(saved_predictions)
            all_losses.append(losses)
            sources[name] = {"predictions_sha256": sha(prediction_path), "report_sha256": sha(report_path), "ledger_sha256": sha(Path(endpoint["folder"]) / "ledger.jsonl")}
            print(json.dumps({"verified_seed": seed, "method": method, "records": 14000, "prediction_disagreements": 0}), flush=True)
    predictions, losses = np.stack(all_predictions), np.stack(all_losses)
    aggregate = {}
    for method in methods:
        selected = [r for r in rows if r["method"] == method]
        aggregate[method] = {
            "metrics": {metric: describe([r["metrics"][metric] for r in selected]) for metric in ["macro_f1", "accuracy", "cross_entropy"]},
            "charged_training_seconds": describe([r["training"]["charged_total_seconds"] for r in selected], interval=False),
            "uncached_inference_seconds_per_record": describe([r["deployment"]["mean_seconds_per_record"] for r in selected], interval=False),
            "test_active_adapters": describe([r["test_route_occupancy"]["active_adapters"] for r in selected], interval=False),
            "test_maximum_adapter_fraction": describe([r["test_route_occupancy"]["maximum_adapter_fraction"] for r in selected], interval=False),
            "probe_route_change_from_warmup": describe([r["training"]["final_probe"]["fraction_changed_from_warmup"] for r in selected], interval=False),
            "parameters": selected[0]["parameter_counts"],
        }
    contrast_indices = {"selected_minus_current_content": (2, 1), "selected_minus_shared": (2, 0), "current_content_minus_shared": (1, 0)}
    contrasts = {}
    for name, (a, b) in contrast_indices.items():
        contrasts[name] = {metric: describe([rows[seed*3+a]["metrics"][metric] - rows[seed*3+b]["metrics"][metric] for seed in range(5)])
                           for metric in ["macro_f1", "accuracy", "cross_entropy"]}
    draws = bootstrap(labels, predictions, losses, methods)
    metric_names = ["macro_f1", "accuracy", "cross_entropy"]
    conditional = {"replicates": 2000, "rng": "NumPy PCG64 seed88002", "groups": 14000, "records": 14000,
                   "scheme": "Multinomial multiplicities of14000 unique canonical groups; same resample across all15 models; average metrics/differences over fixedfive seeds",
                   "scope": analysis_protocol["estimation"]["bootstrap_scope"],
                   "method_intervals": {method: {metric: np.quantile(draws[:, i, j], [.025, .975], method="linear").tolist()
                                                   for j, metric in enumerate(metric_names)} for i, method in enumerate(methods)},
                   "contrast_intervals": {name: {metric: np.quantile(draws[:, a, j] - draws[:, b, j], [.025, .975], method="linear").tolist()
                                                   for j, metric in enumerate(metric_names)} for name, (a, b) in contrast_indices.items()}}
    study_timing = {}
    segments_path = CLASSICAL / "execution_segments.jsonl"
    if segments_path.exists():
        segments = [json.loads(line) for line in segments_path.read_text().splitlines()]
        study_timing = {"segments": segments, "summed_closed_execution_seconds": sum(r.get("actual_seconds", 0) for r in segments if r["event"] == "end"),
                        "scope": "Physical classical execution segments; not summed charged arm times. Excludes quantum, authoring and time between segments."}
    result = {
        "status": "PASS", "created_utc": datetime.now(timezone.utc).isoformat(), "internal_only": True,
        "analysis_script_sha256": sha(Path(__file__)), "analysis_protocol_sha256": sha(analysis_protocol_path),
        "data_manifest_sha256": protocol["data_manifest_sha256"], "stage_b_protocol_sha256": sha(CLASSICAL / "protocol_stage_b_frozen.json"),
        "selected_candidate": selection["selected_candidate"], "registered_seeds": list(range(401, 406)), "methods": methods,
        "verified_models": 15, "verified_prediction_records": 210000, "test_records": 14000,
        "checkpoint_replay": {"dispatch": "Original per-active-adapter loop; same frozen architecture definition", "all_prediction_and_route_disagreements": 0,
                              "maximum_cross_entropy_error": max(r["cross_entropy_absolute_error"] for r in differences), "per_model": differences,
                              "independence_limit": "Independent checkpoint loading, batching, adapter dispatch, NLL/F1 and statistics; shared frozen encoder/model definitions are not a second independently implemented Transformer"},
        "stage_a_selection_audit": stage_a, "per_seed": rows, "aggregate": aggregate,
        "primary_contrast": "selected_minus_current_content.macro_f1", "paired_contrasts": contrasts,
        "conditional_record_bootstrap": conditional, "sources": sources, "classical_execution_timing": study_timing,
        "analysis_seconds": time.perf_counter() - started,
        "limitations": ["Fresh DBpedia subset replication; old AG News scores cannot be directly differenced",
            "One task and one fixed split; exact canonical deduplication only; no manual semantic label verification",
            "Five-seed t interval and conditional test bootstrap address different uncertainty; neither includes all selection/task uncertainty",
            "Secondary contrasts and routing diagnostics exploratory; no multiplicity-adjusted broad superiority claim",
            "Timing includes concurrent-host effects; cached routing training costs differ from full uncached deployment costs",
            "Fixed1000 training-probe routing snapshots are not all-step activity measurements",
            "No quantum hardware, energy, dollar cost or cloud-compute measurement"],
    }
    save(args.output / "summary.json", result)
    np.save(args.output / "conditional_bootstrap_method_metrics.npy", draws)
    np.savez(args.output / "independent_replay_arrays.npz", predictions=predictions, per_record_nll=losses, labels=labels,
             record_ids=ids, canonical_text_hashes=hashes, model_seeds=np.repeat(np.arange(401, 406), 3), model_methods=np.tile(methods, 5))
    with (args.output / "per_seed_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "method", "macro_f1", "accuracy", "cross_entropy", "charged_training_seconds", "uncached_inference_seconds_per_record", "active_test_adapters", "max_test_adapter_fraction", "probe_route_change_from_warmup"])
        for row in rows:
            writer.writerow([row["seed"], row["method"], *[row["metrics"][m] for m in metric_names], row["training"]["charged_total_seconds"],
                             row["deployment"]["mean_seconds_per_record"], row["test_route_occupancy"]["active_adapters"],
                             row["test_route_occupancy"]["maximum_adapter_fraction"], row["training"]["final_probe"]["fraction_changed_from_warmup"]])
    with (args.output / "learning_and_routing_curves.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["seed", "method", "main_update", "validation_macro_f1", "validation_cross_entropy", "charged_seconds", "route_change_from_warmup"])
        writer.writeheader()
        for row in rows:
            for point in row["training"]["curve"]:
                writer.writerow(dict(seed=row["seed"], method=row["method"], **point))
    print(json.dumps({"status": "PASS", "models": 15, "verified_prediction_records": 210000, "output": str(args.output),
                      "primary": contrasts["selected_minus_current_content"]["macro_f1"], "bootstrap_primary_f1": conditional["contrast_intervals"]["selected_minus_current_content"]["macro_f1"]}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        if args.release is None or args.output is None:
            parser.error("--release and a new --output directory are required")
        main(args)
