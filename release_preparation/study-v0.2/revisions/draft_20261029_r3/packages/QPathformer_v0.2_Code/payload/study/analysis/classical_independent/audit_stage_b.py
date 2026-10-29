"""Independent CPU-only confirmation-training completion audit.

Run only after all registered Stage B training has ended. This script never
loads the sealed test payload, constructs a model, performs a forward pass,
uses CUDA, authorizes evaluation, or changes frozen study artifacts.
"""
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time
import unicodedata

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CLASSICAL = ROOT / "classical"
RESULTS = CLASSICAL / "results" / "stage_b"
OWN = Path(__file__).resolve().parent
METHODS = ["shared", "current_content", "hash18"]
SEEDS = [401, 402, 403, 404, 405]
EXPECTED = {
    "protocol_b": "8acef77f0f1893fab6c3a8c79aa02f5219e8fe56d9094aae6bddd7d38d621d4c",
    "protocol_a": "bdd5179589646e956d89e80bedc74f395a0aafa9bc50cf38ea90e1f2b534ca78",
    "root_approval": "b2505eff718bac101415209d58be1cf43bd8c39b1d420d2db7c8f9e58d34d60b",
    "selection": "b6d249f72c8fd274966177dc7a038cf2fdc81ae53854d7cef8641ccb8a589c17",
    "review_a": "90517e69419f8919ac7a4fb5d5046b27c952ee2ad266dcd0f0dd62b2337020fa",
    "manifest": "b4cd9800206d6380c1f8ab0c4d7a6927076560b7168df38ecf55cb694a1a014c",
    "analysis_protocol": "9b409934d07e8eb7a6380a02fe93780cab3323401d595c846da1b2ce7ba1e414",
    "replay_script": "dca77d8c05ed1c6ef53adfe7ae88d1be12aca673a08dbc91fc384eb6ed574f6d",
    "replay_ready": "f757fafffbe1dd9d718c39b5f00ec04f4cda79d45703359509c428d3eedd8cc5",
}


def require(condition, message):
    # Explicit checks remain active even if Python is accidentally run with -O.
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def utc(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "Timestamp must have a timezone")
    return result


def metrics(truth, predicted):
    require(truth.shape == predicted.shape, "Prediction dimensions")
    require(np.all((predicted >= 0) & (predicted < 14)), "Prediction label range")
    matrix = np.bincount(truth*14 + predicted, minlength=196).reshape(14, 14)
    denominator = matrix.sum(0) + matrix.sum(1)
    f1 = np.divide(2*matrix.diagonal(), denominator, out=np.zeros(14), where=denominator > 0)
    return {"macro_f1": float(f1.mean()), "accuracy": float(matrix.trace()/matrix.sum()),
            "confusion_matrix": matrix.tolist(), "per_label_f1": f1.tolist(), "support": matrix.sum(1).tolist()}


def expected_work(seed, warmup, lengths):
    rng = np.random.Generator(np.random.PCG64(seed + (10000 if warmup else 20000)))
    horizon, ramp = (1000, 100) if warmup else (10000, 1000)
    positions, ledger = 0, {}
    for update in range(1, horizon+1):
        indices = rng.integers(0, len(lengths), size=64)
        positions += int(64 * lengths[indices].max())
        if update % 100 == 0:
            lr = .0003*update/ramp if update <= ramp else .0003*(1+math.cos(math.pi*(update-ramp)/(horizon-ramp)))/2
            ledger[update] = {"training_padded_token_positions": positions, "lr": lr}
    return positions, rng.bit_generator.state, ledger


def canonical(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def reconstruct_hash_routes(texts, seed):
    # Independent integer CDF equivalent to the registered float-probability CDF.
    ratio = Fraction.from_float(1/18)
    denominator = ratio.numerator * (1 << 256)
    prefix = str(seed + 60000).encode("ascii") + b"\x00"
    return np.array([min(17, int.from_bytes(hashlib.sha256(prefix + text.encode("utf-8")).digest(), "big")
                         * ratio.denominator // denominator) for text in texts], dtype=np.int64)


def completion_guard(protocol, approval):
    """Only training metadata is opened here; all gates precede tensor/data loads."""
    expected_main = {(seed, method) for seed in SEEDS for method in METHODS}
    expected_all = expected_main | {(seed, "common_warmup") for seed in SEEDS}
    paths = list(RESULTS.glob("seed_*/*/status.json"))
    require(len(paths) == 20, "Require exactly 15 main endpoints and five common warmups")
    states = {}
    for path in paths:
        state = read(path)
        identity = (state["seed"], state["method"])
        require(identity in expected_all and identity not in states, "Unexpected/duplicate phase identity")
        require(path.parent == RESULTS / f"seed_{identity[0]}" / identity[1], "Phase identity/path mismatch")
        horizon = 1000 if identity[1] == "common_warmup" else 10000
        require(state["status"] == "completed", "Stage B still active or incomplete")
        require(state["phase_update"] == state["horizon"] == state["latest_eligible_update"] == horizon,
                "Only full registered endpoints qualify; no censoring or earlier checkpoint substitution")
        require(state["protocol_sha256"] == EXPECTED["protocol_b"], "Endpoint protocol mismatch")
        states[identity] = state
    require(set(states) == expected_all, "Incomplete Stage B identity set")
    segments_path = CLASSICAL / "execution_segments.jsonl"
    segments = [json.loads(line) for line in segments_path.read_text(encoding="utf-8").splitlines()]
    stage_segments = [r for r in segments if r["stage"] == "stage_b"]
    require(bool(stage_segments), "Stage B execution segment missing")
    active, spans = None, []
    for segment in stage_segments:
        if segment["event"] == "start":
            require(active is None, "Unclosed/overlapping Stage B process; root review required")
            require(not spans or utc(spans[-1]["end"]["utc"]) <= utc(segment["utc"]), "Execution segments out of chronological order")
            active = segment
        else:
            require(segment["event"] == "end" and active is not None, "Unpaired execution segment")
            require(utc(active["utc"]) <= utc(segment["utc"]), "Invalid execution timestamps")
            require(math.isfinite(segment["actual_seconds"]) and segment["actual_seconds"] >= 0, "Invalid execution cost")
            require(segment["status"] in ("completed", "failed_or_interrupted"), "Unknown execution outcome")
            spans.append({"start": active, "end": segment})
            active = None
    require(active is None and bool(spans), "Stage B training process has not ended")
    require(spans[-1]["end"]["status"] == "completed", "Latest Stage B execution did not complete")
    require(utc(approval["approved_utc"]) <= utc(spans[0]["start"]["utc"]), "Training preceded root approval")
    for state in states.values():
        require(utc(spans[0]["start"]["utc"]) <= utc(state["started_utc"]) <= utc(state["finished_utc"])
                <= utc(spans[-1]["end"]["utc"]), "Phase outside completed execution window")
    completed_path = RESULTS / "training_completed.json"
    completed = read(completed_path)
    require(completed["protocol_sha256"] == EXPECTED["protocol_b"] and completed["test_accessed"] is False,
            "Training completion identity/test boundary")
    requested = completed["seeds_requested"]
    require(bool(requested) and len(requested) == len(set(requested)) and set(requested) <= set(SEEDS),
            "Invalid latest execution seed request")
    require(max(utc(s["finished_utc"]) for s in states.values()) <= utc(completed["utc"])
            <= utc(spans[-1]["end"]["utc"]), "Completion marker does not cover all endpoints")
    return states, {"execution_segments_sha256": sha(segments_path), "completed_stage_b_segments": spans,
                    "training_completed_sha256": sha(completed_path), "training_completed": completed}, expected_main


def main():
    started = time.perf_counter()
    output = OWN / "CLASSICAL_STAGE_B_INDEPENDENT_REVIEW.json"
    require(not output.exists(), "Preserve prior Stage B audit; this output is one-time")
    paths = {"protocol_b": CLASSICAL / "protocol_stage_b_frozen.json",
             "protocol_a": CLASSICAL / "protocol_stage_a_frozen.json",
             "root_approval": CLASSICAL / "readiness" / "ROOT_STAGE_B_APPROVAL.json",
             "selection": CLASSICAL / "selection_frozen.json",
             "review_a": OWN / "CLASSICAL_STAGE_A_INDEPENDENT_REVIEW.json",
             "manifest": CLASSICAL / "data" / "manifest.json",
             "analysis_protocol": ROOT / "governance" / "ANALYSIS_PROTOCOL.json",
             "replay_script": OWN / "replay_and_analyse.py", "replay_ready": OWN / "ANALYSIS_READY.json"}
    for name, path in paths.items():
        require(sha(path) == EXPECTED[name], "Bound artifact changed: " + name)
    protocol, approval, selection, review_a = [read(paths[name]) for name in ["protocol_b", "root_approval", "selection", "review_a"]]
    require(protocol["seeds"] == SEEDS and protocol["methods"] == METHODS and protocol["stage"] == "stage_b", "Registered arms/seeds")
    require(protocol["schedules"] == {"warmup_updates": 1000, "warmup_ramp": 100, "main_updates": 10000,
            "main_ramp": 1000, "batch": 64, "evaluation_interval": 100, "peak_lr": .0003}, "Registered schedule")
    require(protocol["configuration"]["labels"] == 14 and protocol["resource_cap_seconds_per_method"] == 5400, "Configuration/cap")
    require(protocol["data_manifest_sha256"] == EXPECTED["manifest"] and protocol["selection_sha256"] == EXPECTED["selection"], "Protocol bindings")
    require(approval["review_status"] == "approved_by_root" and approval["test_outcomes_accessed"] is False, "Root approval status")
    for key, expected_name in [("stage_b_protocol_sha256", "protocol_b"), ("stage_a_protocol_sha256", "protocol_a"),
                               ("selection_sha256", "selection"), ("independent_review_sha256", "review_a")]:
        require(approval[key] == EXPECTED[expected_name], "Root approval binding: " + key)
    require(approval["root_approval_script_sha256"] == sha(ROOT / "governance" / "approve_classical_stage_b.py"), "Root approval source")
    require(approval["registered_confirmation_endpoints"] == 15 and approval["training_seeds"] == SEEDS
            and approval["methods"] == METHODS and approval["schedules"] == protocol["schedules"], "Root-approved execution scope")
    require(selection["selected_candidate"] == approval["selected_candidate"] == review_a["selected_candidate"] == "hash18", "Selected candidate")
    require(selection["promising_gate"] is approval["promising_gate"] is review_a["promising_gate"] is True, "Development gate identity")
    require(review_a["status"] == "PASS" and review_a["test_outcomes_accessed"] is False and selection["test_accessed"] is False,
            "Stage A review/test boundary")
    require(review_a["audit_script_sha256"] == sha(OWN / "audit_stage_a.py"), "Completed Stage A audit source changed")
    freeze_path = CLASSICAL / "freeze_stage_b_event.json"
    freeze = read(freeze_path)
    require(freeze["sha256"] == EXPECTED["protocol_b"] and utc(freeze["utc"]) <= utc(approval["approved_utc"]), "Freeze/approval sequence")
    replay_ready = read(paths["replay_ready"])
    require(replay_ready["script_sha256"] == EXPECTED["replay_script"]
            and replay_ready["registered_analysis_protocol_sha256"] == EXPECTED["analysis_protocol"]
            and replay_ready["official_test_outcomes_read"] is False and replay_ready["gpu_checkpoint_replay_executed"] is False,
            "Independent replay registration")
    for name, expected in protocol["code_sha256"].items():
        require(sha(CLASSICAL / name) == expected, "Frozen training/evaluation source changed: " + name)
    states, execution, main_identities = completion_guard(protocol, approval)
    # All full endpoints and completed execution segments have passed before
    # opening any NPZ, importing torch, or loading a CPU checkpoint.
    manifest, checked_data = read(paths["manifest"]), {}
    for name in ["train.jsonl", "validation.jsonl", "train_encoded.npz", "validation_encoded.npz", "tokenizer.json", "tokenizer_provenance.json"]:
        checked_data[name] = sha(CLASSICAL / "data" / name)
        require(checked_data[name] == manifest["file_sha256"][name], "Development payload changed: " + name)
    with np.load(CLASSICAL / "data" / "train_encoded.npz", allow_pickle=False) as z:
        lengths, train_ids, train_labels = z["mask"].sum(1), z["record_ids"].copy(), z["labels"].copy()
    with np.load(CLASSICAL / "data" / "validation_encoded.npz", allow_pickle=False) as z:
        validation_labels, validation_ids = z["labels"].copy(), z["record_ids"].copy()
    require(Counter(train_labels) == Counter({i: 7200 for i in range(14)}) and len(lengths) == 100800, "Training sampling dimensions")
    require(Counter(validation_labels) == Counter({i: 800 for i in range(14)}) and len(validation_labels) == 11200, "Validation sampling dimensions")
    texts = {}
    for split, ids, labels in [("train", train_ids, train_labels), ("validation", validation_ids, validation_labels)]:
        records = [json.loads(line) for line in (CLASSICAL / "data" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
        np.testing.assert_array_equal([r["id"] for r in records], ids)
        np.testing.assert_array_equal([r["label"] for r in records], labels)
        texts[split] = [canonical(r["text"]) for r in records]
    import torch
    torch.set_num_threads(1)
    rows, warmups, provenance, prediction_hashes = [], [], {}, {}
    prediction_records_checked, incident_count = 0, 0
    for seed_index, seed in enumerate(SEEDS):
        registered = read(RESULTS / f"seed_{seed}" / "registration.json")
        offset = seed_index % 3
        order = METHODS[offset:] + METHODS[:offset]
        if seed_index % 2:
            order = list(reversed(order))
        require(registered == {"seed": seed, "methods": order, "protocol_sha256": EXPECTED["protocol_b"]}, "Method order registration")
        probe_indices = np.random.default_rng(seed+50000).choice(len(lengths), 1000, replace=False)
        expected_by_phase = {warm: expected_work(seed, warm, lengths) for warm in [True, False]}
        for method in ["common_warmup"] + METHODS:
            warmup, horizon = method == "common_warmup", 1000 if method == "common_warmup" else 10000
            folder = RESULTS / f"seed_{seed}" / method
            state, commit = states[(seed, method)], read(folder / "checkpoint_commit.json")
            require(state["latest_eligible_in_common_warmup"] is warmup, "Wrong checkpoint phase")
            for key in ["seed", "method", "phase_update", "horizon", "protocol_sha256", "training_padded_token_positions", "latest_eligible_checkpoint", "latest_eligible_update"]:
                require(commit["state"][key] == state[key], "Committed state mismatch: " + key)
            checkpoint = (RESULTS / state["latest_eligible_checkpoint"]).resolve()
            require(checkpoint.is_relative_to(folder.resolve()) and checkpoint == (folder / commit["checkpoint"]).resolve(), "Checkpoint path boundary")
            require(checkpoint.name == f"checkpoint_{horizon:05d}.pt", "Endpoint checkpoint generation")
            checkpoint_hash = sha(checkpoint)
            require(checkpoint_hash == commit["sha256"], "Committed checkpoint hash")
            charges = [state[k] for k in ["elapsed_seconds", "warmup_charged_seconds", "data_preparation_charged_seconds", "method_preparation_seconds"]]
            require(all(math.isfinite(x) and x >= 0 for x in charges), "Nonfinite/negative charged cost")
            require(abs(sum(charges)-state["charged_total_seconds"]) < 1e-8, "Charged total arithmetic")
            require(state["data_preparation_charged_seconds"] == manifest["preparation_seconds"], "Data preparation charge")
            require(state["charged_total_seconds"] <= protocol["resource_cap_seconds_per_method"], "Resource cap exceeded")
            positions, rng_state, expected_ledger = expected_by_phase[warmup]
            require(state["training_padded_token_positions"] == positions, "Paired sample/token work")
            payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
            require(payload["numpy_rng"] == rng_state, "Final sampler RNG state")
            for key in ["seed", "method", "phase_update", "horizon", "protocol_sha256", "training_padded_token_positions", "latest_validation"]:
                require(payload["run_state"][key] == state[key], "Checkpoint payload state: " + key)
            require(payload["data_manifest_sha256"] == EXPECTED["manifest"]
                    and payload["tokenizer_sha256"] == checked_data["tokenizer.json"], "Checkpoint data/tokenizer identity")
            config = dict(protocol["configuration"])
            if method == "shared":
                config["adapters"] = 1
            require(payload["model_config"] == config and payload["dispatch_mode"] == "grouped", "Checkpoint model/dispatch configuration")
            require(payload["route_mode"] == ("shared" if warmup or method == "shared" else "content" if method == "current_content" else "hash18"), "Checkpoint routing mode")
            require(warmup or payload["route_seed"] == seed+60000, "Input hash seed")
            require(payload["torch_rng"].dtype == torch.uint8 and payload["torch_rng"].numel() > 0
                    and len(payload["cuda_rng"]) > 0 and all(x.dtype == torch.uint8 and x.numel() > 0 for x in payload["cuda_rng"])
                    and isinstance(payload["python_rng"], tuple), "Recovery RNG states missing")
            for tensor in payload["model"].values():
                require(bool(torch.isfinite(tensor).all()), "Nonfinite model checkpoint tensor")
            optimizer = payload["optimizer"]
            require(len(optimizer["param_groups"]) == 2 and len(optimizer["state"]) > 0, "Optimizer recovery state missing")
            for group in optimizer["param_groups"]:
                require(group["lr"] == 0 and group["betas"] == (0.9, 0.999) and group["eps"] == 1e-8, "Optimizer endpoint/schedule")
            for item in optimizer["state"].values():
                require(1 <= float(item["step"]) <= horizon and float(item["step"]).is_integer(), "Optimizer step outside phase")
                require(bool(torch.isfinite(item["exp_avg"]).all()) and bool(torch.isfinite(item["exp_avg_sq"]).all()), "Nonfinite optimizer moments")
            if warmup:
                warm_state = state
                require(state["warmup_charged_seconds"] == 0, "Common warmup double charge")
            else:
                require(abs(state["warmup_charged_seconds"]-warm_state["elapsed_seconds"]-warm_state["method_preparation_seconds"]) < 1e-8,
                        "Paired common warmup charge")
            if method == "current_content":
                require(payload["centroids_fitted"] and payload["centroid_training_ids"] == train_ids.tolist(), "Training-only centroids")
                fit = read(folder / "centroid_fit.json")
                excluded = fit["excluded_zero_norm_ids"]
                require(len(excluded) == len(set(excluded)) and set(excluded) <= set(train_ids.tolist()), "Centroid excluded-ID provenance")
                require(fit["training_ids"] == sorted(set(train_ids.tolist())-set(excluded))
                        and len(fit["training_ids"]) >= 18 and fit["seed"] == seed+40000, "Centroid fit identity")
            if not warmup:
                initial_probe, final_probe = np.array(state["initial_probe_routes"]), np.array(state["prior_probe_routes"])
                route_count = 1 if method == "shared" else 18
                require(initial_probe.shape == final_probe.shape == (1000,)
                        and np.all((initial_probe >= 0) & (initial_probe < route_count))
                        and np.all((final_probe >= 0) & (final_probe < route_count)), "Fixed probe routing dimensions/range")
            del payload, optimizer
            cache = None
            if method == "hash18":
                with np.load(folder / "routing_cache.npz", allow_pickle=False) as z:
                    cache = {key: z[key].copy() for key in z.files}
                np.testing.assert_array_equal(cache["train_ids"], train_ids)
                np.testing.assert_array_equal(cache["validation_ids"], validation_ids)
                for split in ["train", "validation"]:
                    np.testing.assert_array_equal(cache[split+"_routes"], reconstruct_hash_routes(texts[split], seed))
                np.testing.assert_array_equal(cache["train_routes"][probe_indices], state["initial_probe_routes"])
                np.testing.assert_array_equal(cache["train_routes"][probe_indices], state["prior_probe_routes"])
            ledger_path = folder / "ledger.jsonl"
            ledger = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
            require([r["phase_update"] for r in ledger] == list(range(100, horizon+1, 100)), "Full unique scheduled validation ledger")
            for entry in ledger:
                update = entry["phase_update"]
                require(entry["global_update"] == update+(0 if warmup else 1000) and entry["eligible"] is True, "Ledger phase/eligibility")
                require(entry["training_padded_token_positions"] == expected_ledger[update]["training_padded_token_positions"], "Ledger sampled token work")
                require(abs(entry["lr"]-expected_ledger[update]["lr"]) < 1e-15, "Full-horizon learning-rate schedule")
                require(math.isfinite(entry["charged_elapsed_seconds"]) and 0 <= entry["charged_elapsed_seconds"] <= 5400, "Ledger resource cap")
                prediction_path = folder / f"validation_{update:05d}.npz"
                prediction_hashes[str(prediction_path.relative_to(RESULTS))] = sha(prediction_path)
                with np.load(prediction_path, allow_pickle=False) as z:
                    np.testing.assert_array_equal(z["labels"], validation_labels)
                    np.testing.assert_array_equal(z["record_ids"], validation_ids)
                    measured = metrics(validation_labels, z["predictions"])
                    require(z["routes"].shape == validation_labels.shape, "Saved validation routing dimensions")
                    if cache is not None:
                        np.testing.assert_array_equal(z["routes"], cache["validation_routes"])
                    else:
                        require(np.all(z["routes"] == -1) if warmup else np.all(z["routes"] == 0) if method == "shared"
                                else np.all((z["routes"] >= 0) & (z["routes"] < 18)), "Validation route range/phase")
                for key in ["macro_f1", "accuracy"]:
                    require(abs(measured[key]-entry["validation"][key]) < 1e-12, "Independent validation metric: " + key)
                require(measured["confusion_matrix"] == entry["validation"]["confusion_matrix"], "Validation confusion matrix")
                require(len(entry["validation"]["per_label"]) == 14, "Per-label metric count")
                for label, item in enumerate(entry["validation"]["per_label"]):
                    require(item["label"] == label and item["support"] == measured["support"][label]
                            and abs(item["f1"]-measured["per_label_f1"][label]) < 1e-12, "Per-label validation metric")
                prediction_records_checked += len(validation_labels)
                if warmup:
                    require(entry["drift"] is None, "Warmup has no adapter routing probe")
                else:
                    require(len(entry["drift"]["counts"]) == route_count and sum(entry["drift"]["counts"]) == 1000
                            and all(isinstance(n, int) and n >= 0 for n in entry["drift"]["counts"]), "Fixed probe counts")
                    require(all(math.isfinite(entry["drift"][key]) and 0 <= entry["drift"][key] <= 1
                                for key in ["from_warmup", "from_previous"]), "Probe drift range")
                    if method == "shared":
                        require(entry["drift"]["from_warmup"] == entry["drift"]["from_previous"] == 0, "Shared route drift")
                if cache is not None:
                    require(entry["drift"]["from_warmup"] == entry["drift"]["from_previous"] == 0, "Immutable hash route drift")
                    require(entry["drift"]["counts"] == np.bincount(cache["train_routes"][probe_indices], minlength=18).tolist(), "Fixed 1000-record probe occupancy")
            require(ledger[-1]["checkpoint_sha256"] == checkpoint_hash and ledger[-1]["validation"] == state["latest_validation"], "Final ledger/checkpoint/status binding")
            if not warmup:
                require(ledger[-1]["drift"]["counts"] == np.bincount(final_probe, minlength=route_count).tolist()
                        and abs(ledger[-1]["drift"]["from_warmup"]-float(np.mean(final_probe != initial_probe))) < 1e-12,
                        "Endpoint probe identity/occupancy/drift")
            incidents_path = folder / "incidents.jsonl"
            incidents = [json.loads(line) for line in incidents_path.read_text(encoding="utf-8").splitlines()] if incidents_path.exists() else []
            incident_count += len(incidents)
            row = {"seed": seed, "method": method, "macro_f1": state["latest_validation"]["macro_f1"],
                   "accuracy": state["latest_validation"]["accuracy"], "charged_seconds": state["charged_total_seconds"],
                   "main_or_warmup_updates": horizon, "registered_record_visits": horizon*64,
                   "reconstructed_padded_token_positions": positions, "resumed_segments": state["resumed_segments"],
                   "incidents": incidents, "checkpoint_sha256": checkpoint_hash,
                   "status_sha256": sha(folder / "status.json"), "ledger_sha256": sha(ledger_path),
                   "commit_sha256": sha(folder / "checkpoint_commit.json")}
            if cache is not None:
                row["routing_cache_sha256"] = sha(folder / "routing_cache.npz")
            if method == "current_content":
                row["centroid_fit_sha256"] = sha(folder / "centroid_fit.json")
                row["centroid_fit_excluded_zero_norm_training_records"] = len(excluded)
            (warmups if warmup else rows).append(row)
            provenance[f"{seed}/{method}"] = {"checkpoint": str(checkpoint.relative_to(CLASSICAL)), "sha256": checkpoint_hash}
    require(len(rows) == 15 and len(warmups) == 5 and len(prediction_hashes) == 1550
            and prediction_records_checked == 17360000, "Audit coverage totals")
    result = {"status": "PASS", "reviewer": "fresh_data agent; independent of classical runner author",
              "created_utc": datetime.now(timezone.utc).isoformat(), "audit_script_sha256": sha(Path(__file__)),
              "stage_b_protocol_sha256": EXPECTED["protocol_b"], "stage_a_protocol_sha256": EXPECTED["protocol_a"],
              "root_approval_sha256": EXPECTED["root_approval"], "selection_sha256": EXPECTED["selection"],
              "stage_a_independent_review_sha256": EXPECTED["review_a"], "stage_b_freeze_event_sha256": sha(freeze_path),
              "data_manifest_sha256": EXPECTED["manifest"], "verified_data_files": checked_data,
              "registered_analysis_protocol_sha256": EXPECTED["analysis_protocol"],
              "independent_replay_script_sha256": EXPECTED["replay_script"], "independent_replay_readiness_sha256": EXPECTED["replay_ready"],
              "verified_frozen_code_files": protocol["code_sha256"], "completed_main_endpoints": 15, "completed_warmups": 5,
              "verified_main_identity_set": [[seed, method] for seed, method in sorted(main_identities)],
              "verified_validation_snapshots": len(prediction_hashes), "verified_validation_prediction_records": prediction_records_checked,
              "registered_main_updates": 150000, "registered_warmup_updates": 5000,
              "registered_main_record_visits": 9600000, "registered_warmup_record_visits": 320000,
              "incident_count": incident_count, "per_seed": rows, "common_warmups": warmups,
              "selected_candidate": "hash18", "promising_gate": True, "execution_completion": execution,
              "test_payload_read": False, "test_outcomes_read": False, "test_outcomes_accessed": False,
              "gpu_inference_used": False, "test_release_authorized": False,
              "evaluation_readiness": "Full training audit passed; a separate root release is still required before any test read",
              "checkpoint_provenance": provenance, "validation_prediction_sha256": prediction_hashes,
              "seconds": time.perf_counter()-started,
              "checks": ["Approved protocol, selection, exact 15 main and five warmup identities and completed execution bound",
                         "All endpoints fully completed, uncensored and committed at 10000/1000 registered horizons",
                         "All 1550 saved validation predictions independently recomputed for macro-F1, accuracy and per-class confusion/support/F1",
                         "Per-seed replacement-sampling RNG, every100-update padded-token work and full-horizon LR reconstructed",
                         "All hash routes independently reconstructed from canonical input only; caches/probes remain immutable",
                         "CPU checkpoint optimizer/model finiteness, recovery RNG and source/data/configuration identities verified"],
              "limits": ["Training and validation evidence only; confirmation test outcomes remain sealed",
                         "No model forward replay or GPU operation performed; saved validation cross-entropy was not independently replayed",
                         "Sample work reconstructed from frozen code/RNG/token records; original per-step sampled IDs were not separately logged",
                         "Charged arm times repeat shared preparation/warmup charges and do not sum to physical project elapsed",
                         "Any resumed unsaved work is additional to registered update/record-visit totals",
                         "This PASS does not authorize test access or assert an architectural improvement"]}
    # Recheck bound inputs and endpoint metadata before emitting a one-time PASS.
    for name, path in paths.items():
        require(sha(path) == EXPECTED[name], "Artifact changed during audit: " + name)
    require(sha(CLASSICAL / "execution_segments.jsonl") == execution["execution_segments_sha256"], "Execution changed during audit")
    for row in rows+warmups:
        folder = RESULTS / f"seed_{row['seed']}" / row["method"]
        for name, field in [("status.json", "status_sha256"), ("checkpoint_commit.json", "commit_sha256"), ("ledger.jsonl", "ledger_sha256")]:
            require(sha(folder / name) == row[field], "Endpoint changed during audit")
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    print(json.dumps({"status": "PASS", "completed_main_endpoints": 15, "completed_warmups": 5,
                      "verified_validation_prediction_records": prediction_records_checked,
                      "test_outcomes_accessed": False, "output": str(output)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
