"""Independent CPU-only Stage A completion and selection audit.

Only training/validation artifacts are opened. No test payload, model forward,
CUDA operation, Stage B freeze or training launch is performed.
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
RESULTS = CLASSICAL / "results" / "stage_a"
METHODS = ["shared", "current_content", "frozen_content", "hash18"]
SEEDS = [301, 302, 303]
EXPECTED_MANIFEST = "b4cd9800206d6380c1f8ab0c4d7a6927076560b7168df38ecf55cb694a1a014c"
EXPECTED_PROTOCOL = "bdd5179589646e956d89e80bedc74f395a0aafa9bc50cf38ea90e1f2b534ca78"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def metrics(truth, predicted):
    assert truth.shape == predicted.shape and np.all((predicted >= 0) & (predicted < 14))
    matrix = np.bincount(truth*14 + predicted, minlength=196).reshape(14, 14)
    denominator = matrix.sum(0) + matrix.sum(1)
    f1 = np.divide(2*matrix.diagonal(), denominator, out=np.zeros(14), where=denominator > 0)
    return {"macro_f1": float(f1.mean()), "accuracy": float(matrix.trace()/matrix.sum()), "confusion_matrix": matrix.tolist()}


def expected_work(seed, warmup, lengths):
    rng = np.random.Generator(np.random.PCG64(seed + (10000 if warmup else 20000)))
    horizon, ramp = (1000, 100) if warmup else (3000, 300)
    work, ledger = 0, {}
    for update in range(1, horizon+1):
        indices = rng.integers(0, len(lengths), size=64)
        work += int(64 * lengths[indices].max())
        if update % 100 == 0:
            lr = .0003*update/ramp if update <= ramp else .0003*(1+math.cos(math.pi*(update-ramp)/(horizon-ramp)))/2
            ledger[update] = {"training_padded_token_positions": work, "lr": lr}
    return work, rng.bit_generator.state, ledger


def canonical(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def reconstruct_hash_routes(texts, seed):
    # Same declared probabilities, independent integer-CDF implementation.
    ratio = Fraction.from_float(1/18)
    denominator = ratio.numerator * (1 << 256)
    prefix = str(seed + 60000).encode("ascii") + b"\x00"
    routes = []
    for text in texts:
        value = int.from_bytes(hashlib.sha256(prefix + text.encode("utf-8")).digest(), "big")
        routes.append(min(17, value * ratio.denominator // denominator))
    return np.array(routes, dtype=np.int64)


def main():
    started = time.perf_counter()
    output = Path(__file__).with_name("CLASSICAL_STAGE_A_INDEPENDENT_REVIEW.json")
    assert not output.exists(), "Preserve earlier audit; do not overwrite"
    protocol_path = CLASSICAL / "protocol_stage_a_frozen.json"
    protocol = read(protocol_path)
    protocol_hash = sha(protocol_path)
    assert protocol_hash == EXPECTED_PROTOCOL
    assert protocol["seeds"] == SEEDS and protocol["methods"] == METHODS
    assert protocol["schedules"]["main_updates"] == 3000 and protocol["schedules"]["warmup_updates"] == 1000
    assert protocol["schedules"]["batch"] == 64 and protocol["schedules"]["evaluation_interval"] == 100
    assert protocol["configuration"]["labels"] == 14
    assert protocol["selection"]["candidates"] == ["frozen_content", "hash18"]
    freeze_event = read(CLASSICAL / "freeze_stage_a_event.json")
    assert freeze_event["sha256"] == protocol_hash
    for name, expected in protocol["code_sha256"].items():
        assert sha(CLASSICAL / name) == expected, name
    # Do not start expensive audits until all12 development endpoints finish.
    for seed in SEEDS:
        for method in METHODS:
            state = read(RESULTS / f"seed_{seed}" / method / "status.json")
            assert state["status"] == "completed" and state["phase_update"] == state["latest_eligible_update"] == 3000
    selection_path = CLASSICAL / "selection_frozen.json"
    selection = read(selection_path)
    assert selection["stage_a_protocol_sha256"] == protocol_hash and selection["test_accessed"] is False
    expected_identities = {(seed, method) for seed in SEEDS for method in METHODS}
    assert len(selection["seed_rows"]) == 12
    assert {(r["seed"], r["method"]) for r in selection["seed_rows"]} == expected_identities
    actual_phase_identities = set()
    phase_status_paths = list(RESULTS.glob("seed_*/*/status.json"))
    assert len(phase_status_paths) == 15
    for state_path in phase_status_paths:
        phase_state = read(state_path)
        actual_phase_identities.add((phase_state["seed"], phase_state["method"]))
    assert actual_phase_identities == expected_identities | {(seed, "common_warmup") for seed in SEEDS}
    manifest_path = CLASSICAL / "data" / "manifest.json"
    assert sha(manifest_path) == protocol["data_manifest_sha256"] == EXPECTED_MANIFEST
    manifest = read(manifest_path)
    checked_data = {}
    for name in ["train.jsonl", "validation.jsonl", "train_encoded.npz", "validation_encoded.npz", "tokenizer.json", "tokenizer_provenance.json"]:
        actual = sha(CLASSICAL / "data" / name)
        assert actual == manifest["file_sha256"][name], name
        checked_data[name] = actual
    with np.load(CLASSICAL / "data" / "train_encoded.npz", allow_pickle=False) as z:
        lengths = z["mask"].sum(1)
        train_ids = z["record_ids"].copy()
        train_labels = z["labels"].copy()
    with np.load(CLASSICAL / "data" / "validation_encoded.npz", allow_pickle=False) as z:
        validation_labels, validation_ids = z["labels"].copy(), z["record_ids"].copy()
    assert len(lengths) == 100800 and len(validation_labels) == 11200
    assert Counter(train_labels) == Counter({i: 7200 for i in range(14)})
    assert Counter(validation_labels) == Counter({i: 800 for i in range(14)})
    texts = {}
    for split in ["train", "validation"]:
        with (CLASSICAL / "data" / f"{split}.jsonl").open(encoding="utf-8") as f:
            records = [json.loads(line) for line in f]
        texts[split] = [canonical(r["text"]) for r in records]
    import torch
    torch.set_num_threads(1)
    rows, warmups, provenance = [], [], {}
    prediction_records_checked = 0
    incident_count = 0
    for seed_index, seed in enumerate(SEEDS):
        registered = read(RESULTS / f"seed_{seed}" / "registration.json")
        offset = seed_index % 4
        order = METHODS[offset:] + METHODS[:offset]
        if seed_index % 2:
            order = list(reversed(order))
        assert registered == {"seed": seed, "methods": order, "protocol_sha256": protocol_hash}
        warm_model = None
        centroids = None
        probe_indices = np.random.default_rng(seed+50000).choice(len(lengths), 1000, replace=False)
        for method in ["common_warmup"] + METHODS:
            warmup = method == "common_warmup"
            horizon = 1000 if warmup else 3000
            folder = RESULTS / f"seed_{seed}" / method
            state, commit = read(folder / "status.json"), read(folder / "checkpoint_commit.json")
            assert state["status"] == "completed" and state["phase_update"] == state["horizon"] == horizon
            assert state["latest_eligible_update"] == horizon and state["seed"] == seed and state["method"] == method
            assert state["protocol_sha256"] == commit["state"]["protocol_sha256"] == protocol_hash
            assert commit["state"]["phase_update"] == horizon
            assert state["latest_eligible_in_common_warmup"] == warmup
            checkpoint = (RESULTS / state["latest_eligible_checkpoint"]).resolve()
            assert checkpoint.is_relative_to(folder.resolve()) and checkpoint.name == commit["checkpoint"]
            checkpoint_hash = sha(checkpoint)
            assert checkpoint_hash == commit["sha256"]
            assert state["latest_eligible_checkpoint"] == commit["state"]["latest_eligible_checkpoint"]
            total = sum(state[k] for k in ["elapsed_seconds", "warmup_charged_seconds", "data_preparation_charged_seconds", "method_preparation_seconds"])
            assert abs(total - state["charged_total_seconds"]) < 1e-8
            assert state["data_preparation_charged_seconds"] == manifest["preparation_seconds"]
            assert state["charged_total_seconds"] <= protocol["resource_cap_seconds_per_method"]
            expected_positions, rng_state, expected_ledger = expected_work(seed, warmup, lengths)
            assert state["training_padded_token_positions"] == expected_positions
            payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
            assert payload["numpy_rng"] == rng_state
            assert payload["run_state"]["phase_update"] == horizon and payload["run_state"]["protocol_sha256"] == protocol_hash
            assert payload["run_state"]["training_padded_token_positions"] == expected_positions
            assert payload["data_manifest_sha256"] == EXPECTED_MANIFEST
            assert payload["tokenizer_sha256"] == manifest["file_sha256"]["tokenizer.json"]
            expected_config = dict(protocol["configuration"])
            if method == "shared":
                expected_config["adapters"] = 1
            assert payload["model_config"] == expected_config
            expected_mode = {"common_warmup": "shared", "shared": "shared", "current_content": "content", "frozen_content": "frozen_content", "hash18": "hash18"}[method]
            assert payload["route_mode"] == expected_mode
            if not warmup:
                assert payload["route_seed"] == seed+60000
            if warmup:
                warm_model = {k: v.clone() for k, v in payload["model"].items()}
                warm_state = state
            else:
                assert abs(state["warmup_charged_seconds"] - warm_state["elapsed_seconds"] - warm_state["method_preparation_seconds"]) < 1e-8
            if method in ["current_content", "frozen_content"]:
                assert payload["centroids_fitted"] and list(payload["centroid_training_ids"]) == train_ids.tolist()
                fit = read(folder / "centroid_fit.json")
                assert fit["training_ids"] == train_ids.tolist() and fit["seed"] == seed+40000
                if centroids is None:
                    centroids = payload["model"]["centroids"].clone()
                else:
                    assert torch.equal(centroids, payload["model"]["centroids"])
            if method == "frozen_content":
                for key, value in payload["model"].items():
                    if key.startswith("frozen_router."):
                        original = key[len("frozen_router."):]
                        expected = centroids if original == "centroids" else warm_model[original]
                        assert torch.equal(value, expected), original
            del payload
            cache = None
            if method in ["frozen_content", "hash18"]:
                with np.load(folder / "routing_cache.npz", allow_pickle=False) as z:
                    cache = {k: z[k].copy() for k in z.files}
                np.testing.assert_array_equal(cache["train_ids"], train_ids)
                np.testing.assert_array_equal(cache["validation_ids"], validation_ids)
                assert cache["train_routes"].shape == (100800,) and cache["validation_routes"].shape == (11200,)
                assert np.all((cache["train_routes"] >= 0) & (cache["train_routes"] < 18))
                assert np.all((cache["validation_routes"] >= 0) & (cache["validation_routes"] < 18))
                np.testing.assert_array_equal(cache["train_routes"][probe_indices], state["initial_probe_routes"])
                np.testing.assert_array_equal(cache["train_routes"][probe_indices], state["prior_probe_routes"])
                if method == "hash18":
                    for split in ["train", "validation"]:
                        np.testing.assert_array_equal(cache[split+"_routes"], reconstruct_hash_routes(texts[split], seed))
            ledger_path = folder / "ledger.jsonl"
            ledger = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
            assert [r["phase_update"] for r in ledger] == list(range(100, horizon+1, 100))
            for entry in ledger:
                update = entry["phase_update"]
                assert entry["global_update"] == update + (0 if warmup else 1000)
                assert entry["eligible"] is True
                assert entry["training_padded_token_positions"] == expected_ledger[update]["training_padded_token_positions"]
                assert abs(entry["lr"] - expected_ledger[update]["lr"]) < 1e-15
                with np.load(folder / f"validation_{update:05d}.npz", allow_pickle=False) as z:
                    np.testing.assert_array_equal(z["labels"], validation_labels)
                    np.testing.assert_array_equal(z["record_ids"], validation_ids)
                    measured = metrics(validation_labels, z["predictions"])
                    if cache is not None:
                        np.testing.assert_array_equal(z["routes"], cache["validation_routes"])
                    elif method == "shared":
                        assert np.all(z["routes"] == 0)
                    elif warmup:
                        assert np.all(z["routes"] == -1)
                for metric in ["macro_f1", "accuracy"]:
                    assert abs(measured[metric] - entry["validation"][metric]) < 1e-12
                assert measured["confusion_matrix"] == entry["validation"]["confusion_matrix"]
                prediction_records_checked += len(validation_labels)
                if cache is not None:
                    assert entry["drift"]["from_warmup"] == entry["drift"]["from_previous"] == 0
                    assert entry["drift"]["counts"] == np.bincount(cache["train_routes"][probe_indices], minlength=18).tolist()
            assert ledger[-1]["checkpoint_sha256"] == checkpoint_hash
            assert ledger[-1]["validation"] == state["latest_validation"]
            incidents_path = folder / "incidents.jsonl"
            incidents = [json.loads(line) for line in incidents_path.read_text().splitlines()] if incidents_path.exists() else []
            incident_count += len(incidents)
            row = {"seed": seed, "method": method, "macro_f1": state["latest_validation"]["macro_f1"],
                   "accuracy": state["latest_validation"]["accuracy"], "charged_seconds": state["charged_total_seconds"],
                   "main_or_warmup_updates": horizon, "registered_record_visits": horizon*64,
                   "reconstructed_padded_token_positions": expected_positions, "resumed_segments": state["resumed_segments"],
                   "incidents": incidents, "checkpoint_sha256": checkpoint_hash,
                   "status_sha256": sha(folder / "status.json"), "ledger_sha256": sha(ledger_path),
                   "commit_sha256": sha(folder / "checkpoint_commit.json")}
            (warmups if warmup else rows).append(row)
            provenance[f"{seed}/{method}"] = {"checkpoint": str(checkpoint.relative_to(CLASSICAL)), "sha256": checkpoint_hash}
    means = {method: {"macro_f1": float(np.mean([r["macro_f1"] for r in rows if r["method"] == method])),
                      "charged_seconds": float(np.mean([r["charged_seconds"] for r in rows if r["method"] == method]))} for method in METHODS}
    best = max(means[m]["macro_f1"] for m in ["frozen_content", "hash18"])
    near_ties = [m for m in ["frozen_content", "hash18"] if means[m]["macro_f1"] >= best-.001]
    selected = min(near_ties, key=lambda m: (means[m]["charged_seconds"], m))
    deltas = [next(r["macro_f1"] for r in rows if r["seed"] == seed and r["method"] == selected)
              - next(r["macro_f1"] for r in rows if r["seed"] == seed and r["method"] == "shared") for seed in SEEDS]
    gate = means[selected]["macro_f1"] >= max(means[m]["macro_f1"] for m in METHODS[:2])-.002 and min(deltas) >= -.005
    assert selection["selected_candidate"] == selected and bool(selection["promising_gate"]) == bool(gate)
    assert selection["rule"] == protocol["selection"]
    for method in METHODS:
        assert selection["averages"][method] == {"f1": means[method]["macro_f1"], "seconds": means[method]["charged_seconds"]}
    for row in rows:
        original = next(r for r in selection["seed_rows"] if r["seed"] == row["seed"] and r["method"] == row["method"])
        assert original["f1"] == row["macro_f1"] and original["seconds"] == row["charged_seconds"]
        assert original["checkpoint_sha256"] == row["checkpoint_sha256"] and original["status_sha256"] == row["status_sha256"]
    event = read(CLASSICAL / "selection_freeze_event.json")
    assert event["sha256"] == sha(selection_path)
    result = {"status": "PASS", "reviewer": "fresh_data agent; independent of classical runner author",
              "created_utc": datetime.now(timezone.utc).isoformat(), "audit_script_sha256": sha(Path(__file__)),
              "stage_a_protocol_sha256": protocol_hash, "selection_sha256": sha(selection_path),
              "data_manifest_sha256": EXPECTED_MANIFEST, "verified_data_files": checked_data,
              "verified_frozen_code_files": protocol["code_sha256"], "completed_main_endpoints": 12, "completed_warmups": 3,
              "verified_main_identity_set": [[seed, method] for seed, method in sorted(expected_identities)],
              "verified_validation_prediction_records": prediction_records_checked, "registered_main_updates": 36000,
              "registered_warmup_updates": 3000, "registered_main_record_visits": 2304000,
              "registered_warmup_record_visits": 192000, "incident_count": incident_count,
              "per_seed": rows, "common_warmups": warmups, "means": means,
              "candidate_near_tie_set_within_0_001_f1": near_ties, "selected_candidate": selected,
              "selected_minus_shared_f1_by_seed": deltas, "promising_gate": bool(gate),
              "promising_gate_components": {"selected_mean_f1": means[selected]["macro_f1"],
                  "best_anchor_mean_f1": max(means[m]["macro_f1"] for m in METHODS[:2]),
                  "allowed_mean_shortfall_f1": 0.002, "minimum_paired_selected_minus_shared_f1": min(deltas),
                  "allowed_seed_shortfall_f1": 0.005},
              "stage_b_review_readiness": "Ready for independent root approval; no Stage B freeze or launch performed",
              "test_payload_read": False, "test_outcomes_read": False, "test_outcomes_accessed": False, "gpu_inference_used": False,
              "checkpoint_provenance": provenance, "seconds": time.perf_counter()-started,
              "checks": ["All15 phase endpoints fully completed, uncensored and committed at registered horizons",
                         "All390 validation ledgers/saved predictions recomputed independently for F1, accuracy and confusion",
                         "Registered replacement-sampling RNG and every100-update padded-token totals reconstructed per seed",
                         "Paired sample work identical across four arms; endpoint PCG64 state matches reconstruction",
                         "Frozen routing encoder parameters exactly match common warmup; current/frozen centroids match",
                         "All immutable cache IDs/validation routes/probe snapshots align; all hash routes independently reconstructed from canonical input only",
                         "Stage A near-tie time selection and promising gate independently reconstructed"],
              "limits": ["Training/validation only; Stage A rankings are not confirmation-test evidence",
                         "No Transformer forward replay was performed during active training",
                         "Exact record sampling is reconstructed from frozen code/RNG and token-work records; per-step original sampled IDs were not separately logged",
                         "Charged arm times include shared preparation costs repeatedly and do not sum to actual project elapsed",
                         "Any repeated unsaved work following incidents is separate from registered work counts"]}
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": "PASS", "selected_candidate": selected, "promising_gate": bool(gate), "means": means,
                      "verified_validation_prediction_records": prediction_records_checked, "output": str(output)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
