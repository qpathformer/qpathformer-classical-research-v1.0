"""Internal DBpedia14 staged routing study. Training never opens sealed test data."""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import time
import engine as E
import numpy as np
import torch
from qpath.classical import (ModelConfig, QPathTextModel, FrozenRoutingEncoder,
                            TextTokenizer, adamw_optimizer, spherical_kmeans,
                            train_update, parameter_counts)
from qpath.policies import learning_rate, stable_text_route

ROOT = Path(__file__).resolve().parent
CONFIG = replace(ModelConfig(), labels=14)
ARMS = ["shared", "current_content", "frozen_content", "hash18"]
NEW_ARMS = ["frozen_content", "hash18"]
CODE = ["study.py", "engine.py", "evaluate_sealed.py", "qpath/classical.py", "qpath/policies.py",
        "tests/test_v02.py", "tests/test_classical.py", "tests/test_policies.py"]


def activate(stage):
    E.RESULTS = ROOT / "results" / stage
    E.RESULTS.mkdir(parents=True, exist_ok=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def protocol_document(stage):
    selected = None
    if stage == "stage_b":
        selected = read_json(ROOT / "selection_frozen.json")
    return {
        "id": "QPATH-DBPEDIA14-ROUTING-v0.2-" + stage,
        "internal_only": True, "stage": stage,
        "seeds": [301, 302, 303] if stage == "stage_a" else list(range(401, 406)),
        "methods": ARMS if stage == "stage_a" else ["shared", "current_content", selected["selected_candidate"]],
        "configuration": asdict(CONFIG), "shared_adapters": 1,
        "data_manifest_sha256": E.digest(E.DATA / "manifest.json"),
        "code_sha256": {name: E.digest(ROOT / name) for name in CODE},
        "selection_sha256": None if selected is None else E.digest(ROOT / "selection_frozen.json"),
        "schedules": {"warmup_updates": 1000, "warmup_ramp": 100,
                      "main_updates": 3000 if stage == "stage_a" else 10000,
                      "main_ramp": 300 if stage == "stage_a" else 1000,
                      "batch": 64, "evaluation_interval": 100, "peak_lr": 0.0003},
        "precision": "float32; TF32 and AMP disabled; deterministic torch algorithms",
        "optimizer": "AdamW betas .9/.999, eps1e-8, decay .01 excluding biases/norms; grad clip1; cosine LR endpoint0",
        "resource_cap_seconds_per_method": 1800 if stage == "stage_a" else 5400,
        "selection": {"candidates": NEW_ARMS,
                      "rule": "Highest mean endpoint validation macro-F1; any candidate within0.001 of best may win by lower mean charged time; exact time tie lexicographic name",
                      "promising_gate": "Selected mean >= best anchor mean minus0.002, and every paired selected-minus-shared seed difference >=-0.005",
                      "gate_failure": "Still compare selected candidate in Stage B; explicitly diagnostic, not evidence of improvement",
                      "development_horizon_caveat": "Stage A uses independently scheduled3000 main updates; early ranking may differ at10000"},
        "primary": "Stage B paired selected-minus-current_content macro-F1 at completed main update10000 (latest eligible scheduled endpoint); selected-minus-shared secondary. Reduced/censored endpoints never count as full runs.",
        "test_policy": "No test reads during training or selection. Separate evaluation only after all15 Stage B endpoints and selection are frozen and root release manifest exists.",
        "time_comparisons": "Descriptive unless matched quality is established; no arbitrary0.85 target on the new task",
        "method_order": "Cyclic rotation by seed index, reversing alternate seeds; order frozen in per-seed registration",
        "routing": {"current_content": "Frozen training-only warmup centroids; current trainable encoder pooled representation chooses adapter",
                    "frozen_content": "Frozen eval-only warmup encoder and centroids; immutable input-derived train/validation route cache; backbone for classification still trains",
                    "hash18": "Uniform18-bin SHA256(seed+60000 || NUL || NFKC/casefold/collapsed-space full input text), via exactCDF; no labels or record IDs",
                    "degenerate": "Content uses routing representation norm fallback0; frozen/hash cached routing stays immutable if classifier encoder changes"},
        "costs": {"training": "Charge data preparation, common warmup and all method preparation/cache build; cached train/validation routes avoid repeated frozen-encoder inference",
                  "deployment": "Separately measure uncached frozen encoder or text hashing on fixed heldout inputs; report full frozen encoder parameter/storage overhead",
                  "project_total": "Execution segment wall time; common warmup is physically executed once perseed but charged to each arm",
                  "cap_end": "Scheduled checkpoint tensor file save and hash completion; ledger/commit overhead remains charged before next update"},
        "rng": {"warmup_init": "seed", "warmup_samples": "seed+10000", "main_samples": "seed+20000",
                "main_dropout": "seed+30000", "kmeans": "seed+40000", "probe": "seed+50000", "hash": "seed+60000"},
        "initialization": "All arms share each seed's warmup backbone/head and initial18-bank; shared receives adapter0; main optimizer starts fresh",
        "dispatch": "Grouped batched matrix multiply over active independent Parameter modules; same for all arms; inactive adapters gradNone; tested against original loop",
        "tokenization": "Train-only8192BPE; structural PAD0,BOS2,EOS3 excluded from pooling; UNK1 retained; BOS/EOS attention-valid; max256; trim right padding perbatch",
        "resume": "Atomic complete checkpoint generations plus committed decision metadata; optimizer/RNG restored; cache regenerated deterministically and charged; all incidents retained",
        "environment": {"torch": str(torch.__version__), "cuda": torch.version.cuda,
                        "gpu": torch.cuda.get_device_name(), "threads": 4},
        "pending": ["semantic priority", "adaptation", "quantum hardware", "broad tuning"],
    }


def freeze(stage):
    manifest = read_json(E.DATA / "manifest.json")
    for name in ["train_encoded.npz", "validation_encoded.npz", "train.jsonl", "validation.jsonl",
                 "tokenizer.json", "tokenizer_provenance.json"]:
        if E.digest(E.DATA / name) != manifest["file_sha256"][name]:
            raise ValueError("Training/validation/tokenizer payload changed: " + name)
    protocol = protocol_document(stage)
    path = ROOT / f"protocol_{stage}_frozen.json"
    if path.exists():
        if read_json(path) != protocol:
            raise ValueError("Frozen code/data/protocol changed; preserve this experiment and create a new version")
    else:
        E.write_json(path, protocol)
        E.write_json(ROOT / f"freeze_{stage}_event.json", {"utc": E.now(), "sha256": E.digest(path)})
    return protocol, E.digest(path)


def ordered_methods(methods, seed_index):
    offset = seed_index % len(methods)
    result = methods[offset:] + methods[:offset]
    return list(reversed(result)) if seed_index % 2 else result


def load_texts(split):
    path = E.DATA / f"{split}.jsonl"
    if E.digest(path) != read_json(E.DATA / "manifest.json")["file_sha256"][path.name]:
        raise ValueError("Text source hash mismatch")
    return [json.loads(line)["text"] for line in path.read_text(encoding="utf-8").splitlines()]


def feature_cache(model, data, texts=None):
    started = time.perf_counter()
    if model.route_mode == "hash18":
        if texts is None or len(texts) != len(data["labels"]):
            raise ValueError("Hash cache requires aligned original texts")
        features = torch.tensor([stable_text_route(text, model.route_seed, [1 / 18] * 18) for text in texts])
    elif model.route_mode == "frozen_content":
        features = []
        for start in range(0, len(data["labels"]), 64):
            tokens, mask, _, _ = E.device_batch(data, slice(start, start + 64))
            features.append(model.frozen_router(tokens, mask).cpu())
        features = torch.cat(features)
    else:
        raise ValueError("Only immutable input-derived routes can be cached")
    result = dict(data)
    result["routing_features"] = features
    return result, time.perf_counter() - started


def fit_centroids(model, train, seed, folder):
    start = time.perf_counter()
    _, _, _, vectors = E.evaluate(model, train, use_adapters=False, embeddings=True)
    centers, manifest = spherical_kmeans(vectors, train["record_ids"].tolist(), 18, seed + 40000)
    model.set_centroids(centers.to("cuda"), train["record_ids"].tolist())
    manifest["seconds"] = time.perf_counter() - start
    routes, _ = model.select_routes(vectors.to("cuda"))
    manifest["counts"] = torch.bincount(routes, minlength=18).cpu().tolist()
    E.write_json(folder / "centroid_fit.json", manifest)
    return manifest["seconds"]


def charged(state):
    return sum(state[key] for key in ("elapsed_seconds", "warmup_charged_seconds", "data_preparation_charged_seconds", "method_preparation_seconds"))


def run_phase(seed, method, model, train, validation, probe, warm_meta, protocol, protocol_hash):
    entry = time.perf_counter()
    warmup = method == "common_warmup"
    schedule = protocol["schedules"]
    horizon = schedule["warmup_updates" if warmup else "main_updates"]
    ramp = schedule["warmup_ramp" if warmup else "main_ramp"]
    folder = E.RESULTS / f"seed_{seed}" / method
    folder.mkdir(parents=True, exist_ok=True)
    status_path = folder / "status.json"
    if status_path.exists() and read_json(status_path)["status"] == "completed":
        return read_json(status_path)
    optimizer = adamw_optimizer(model)
    rng = np.random.Generator(np.random.PCG64(seed + (10000 if warmup else 20000)))
    state = {"seed": seed, "method": method, "phase_update": 0, "horizon": horizon,
             "status": "running", "started_utc": E.now(), "elapsed_seconds": 0.0,
             "protocol_sha256": protocol_hash, "resumed_segments": 0,
             "warmup_charged_seconds": 0.0 if warmup else warm_meta["elapsed_seconds"] + warm_meta["method_preparation_seconds"],
             "data_preparation_charged_seconds": read_json(E.DATA / "manifest.json")["preparation_seconds"],
             "method_preparation_seconds": warm_meta.get("current_preparation_seconds", 0.0),
             "preparation_breakdown": warm_meta.get("preparation_breakdown", {}),
             "latest_eligible_checkpoint": None if warmup else warm_meta["latest_eligible_checkpoint"],
             "latest_eligible_in_common_warmup": not warmup,
             "training_padded_token_positions": 0, "initial_probe_routes": None, "prior_probe_routes": None,
             "ramp": ramp, "peak_lr": 0.0003,
             "parameter_counts": {"total": sum(p.numel() for p in model.parameters()),
                                  "trainable": sum(p.numel() for p in model.parameters() if p.requires_grad)}}
    if (folder / "checkpoint_commit.json").exists():
        state = E.restore_committed_checkpoint(folder, model, optimizer, rng)
        state["method_preparation_seconds"] += warm_meta.get("current_preparation_seconds", 0.0)
        if state["protocol_sha256"] != protocol_hash:
            raise ValueError("Resume protocol mismatch")
        heartbeat = read_json(status_path) if status_path.exists() else state
        state["elapsed_seconds"] = max(state["elapsed_seconds"], heartbeat.get("elapsed_seconds", 0))
        state["resumed_segments"] += 1
        E.append_json(folder / "incidents.jsonl", {"utc": E.now(), "kind": "resume", "checkpoint_update": state["phase_update"],
                      "last_heartbeat_update": heartbeat.get("phase_update"),
                      "unmeasured": "Crash-to-last-heartbeat tail; repeated unsaved updates and regeneration charged"})
    elif status_path.exists() or (folder / "ledger.jsonl").exists() or any(folder.glob("checkpoint_*.pt")):
        # A first-save crash has no committed model to restore. Preserve its
        # evidence, restart deterministically, and retain measured consumed cost.
        previous = read_json(status_path) if status_path.exists() else {}
        if previous and previous.get("protocol_sha256") != protocol_hash:
            raise ValueError("Pre-commit restart protocol mismatch")
        E.append_json(folder / "prior_attempts.jsonl", previous)
        E.reconcile_uncommitted_artifacts(folder, 0)
        state["elapsed_seconds"] = previous.get("elapsed_seconds", 0.0)
        state["method_preparation_seconds"] += previous.get("method_preparation_seconds", 0.0)
        state["resumed_segments"] = previous.get("resumed_segments", 0) + 1
        E.append_json(folder / "incidents.jsonl", {"utc": E.now(), "kind": "restart_before_first_commit",
                      "last_heartbeat_update": previous.get("phase_update"),
                      "measured_elapsed_retained": state["elapsed_seconds"],
                      "unmeasured": "Crash-to-last-heartbeat tail; no committed model existed, so restart from paired initial state"})
    offset = state["elapsed_seconds"]
    cap = protocol["resource_cap_seconds_per_method"]
    torch.cuda.reset_peak_memory_stats()
    try:
        if not warmup and state["initial_probe_routes"] is None:
            _, _, routes, _ = E.evaluate(model, probe)
            state["initial_probe_routes"] = routes.tolist()
            state["prior_probe_routes"] = routes.tolist()
        for update in range(state["phase_update"] + 1, horizon + 1):
            state["elapsed_seconds"] = offset + time.perf_counter() - entry
            if charged(state) >= cap:
                state["status"] = "resource_censored"
                break
            lr = learning_rate(update, horizon, ramp)
            for group in optimizer.param_groups:
                group["lr"] = lr
            indices = rng.integers(0, len(train["labels"]), size=64)
            tokens, mask, labels, width = E.device_batch(train, indices)
            cached = train.get("routing_features")
            cached = cached[indices].to("cuda") if cached is not None and not warmup else None
            loss, routes = train_update(model, optimizer, tokens, mask, labels,
                                        use_adapters=not warmup, routing_features=cached)
            state["phase_update"] = update
            state["training_padded_token_positions"] += 64 * width
            state["elapsed_seconds"] = offset + time.perf_counter() - entry
            state["training_loss_last"] = loss
            if update % 10 == 0:
                E.write_json(status_path, state)
            if update % schedule["evaluation_interval"] == 0:
                validation_start = time.perf_counter()
                metric, predictions, validation_routes, _ = E.evaluate(model, validation, use_adapters=not warmup)
                drift = None
                if not warmup:
                    _, _, probe_routes, _ = E.evaluate(model, probe)
                    drift = {"from_warmup": float(np.mean(probe_routes != state["initial_probe_routes"])),
                             "from_previous": float(np.mean(probe_routes != state["prior_probe_routes"])),
                             "counts": np.bincount(probe_routes, minlength=model.config.adapters).tolist()}
                    state["prior_probe_routes"] = probe_routes.tolist()
                validation_seconds = time.perf_counter() - validation_start
                state["latest_validation"] = metric
                np.savez(folder / f"validation_{update:05d}.npz", predictions=predictions,
                         labels=validation["labels"].numpy(), record_ids=validation["record_ids"], routes=validation_routes)
                state["elapsed_seconds"] = offset + time.perf_counter() - entry
                generation = folder / f"checkpoint_{update:05d}.pt"
                save_start = time.perf_counter()
                E.save_checkpoint(generation, E.checkpoint_state(model, optimizer, rng, state))
                generation_hash = E.digest(generation)
                save_seconds = time.perf_counter() - save_start
                state["elapsed_seconds"] = offset + time.perf_counter() - entry
                eligible = charged(state) <= cap
                if eligible:
                    state["latest_eligible_checkpoint"] = str(generation.relative_to(E.RESULTS))
                    state["latest_eligible_in_common_warmup"] = warmup
                    state["latest_eligible_update"] = update
                record = {"utc": E.now(), "phase_update": update, "global_update": update if warmup else update + 1000,
                          "lr": lr, "validation": metric, "validation_seconds": validation_seconds,
                          "checkpoint_save_hash_seconds": save_seconds, "charged_elapsed_seconds": charged(state),
                          "eligible": eligible, "drift": drift, "checkpoint_sha256": generation_hash,
                          "training_padded_token_positions": state["training_padded_token_positions"]}
                E.append_json(folder / "ledger.jsonl", record)
                state["elapsed_seconds"] = offset + time.perf_counter() - entry
                E.commit_checkpoint(folder, generation, state)
                state["elapsed_seconds"] = offset + time.perf_counter() - entry
                E.write_json(status_path, state)
                print(json.dumps({"stage": protocol["stage"], "seed": seed, "method": method, "update": update,
                                  "validation_f1": metric["macro_f1"], "charged_seconds": charged(state)}), flush=True)
        else:
            state["status"] = "completed"
        state["elapsed_seconds"] = offset + time.perf_counter() - entry
        state["finished_utc"] = E.now()
        state["phase_peak_gpu_allocated_bytes"] = torch.cuda.max_memory_allocated()
        state["charged_total_seconds"] = charged(state)
        E.write_json(status_path, state)
        return state
    except BaseException as error:
        state["status"] = "failed_or_interrupted"
        state["elapsed_seconds"] = offset + time.perf_counter() - entry
        state["failure"] = {"utc": E.now(), "type": type(error).__name__, "message": str(error)}
        E.write_json(status_path, state)
        E.append_json(folder / "incidents.jsonl", state["failure"])
        raise


def prepare_method(method, common, train, validation, seed, folder):
    start = time.perf_counter()
    model = QPathTextModel(replace(CONFIG, adapters=1) if method == "shared" else CONFIG).to("cuda")
    initial = model.state_dict()
    initial.update({key: value for key, value in common.items() if key in initial and value.shape == initial[key].shape})
    model.load_state_dict(initial)
    model.route_mode = "shared" if method == "shared" else "content"
    model.route_seed = seed + 60000
    breakdown = {}
    if method in ("current_content", "frozen_content"):
        breakdown["centroid_fit_seconds"] = fit_centroids(model, train, seed, folder)
    model.route_mode = method if method in NEW_ARMS else model.route_mode
    if method == "frozen_content":
        model.frozen_router = FrozenRoutingEncoder(model)
    if method in NEW_ARMS:
        texts_train = load_texts("train") if method == "hash18" else None
        texts_val = load_texts("validation") if method == "hash18" else None
        train, breakdown["training_route_cache_seconds"] = feature_cache(model, train, texts_train)
        validation, breakdown["validation_route_cache_seconds"] = feature_cache(model, validation, texts_val)
        np.savez(folder / "routing_cache.npz", train_routes=train["routing_features"].numpy(),
                 validation_routes=validation["routing_features"].numpy(), train_ids=train["record_ids"], validation_ids=validation["record_ids"])
    breakdown["total_preparation_seconds"] = time.perf_counter() - start
    E.write_json(folder / "preparation.json", breakdown)
    return model, train, validation, breakdown


def run(stage, seeds=None):
    E.enable_local_only()
    activate(stage)
    protocol, protocol_hash = freeze(stage)
    seeds = protocol["seeds"] if seeds is None else seeds
    if any(seed not in protocol["seeds"] for seed in seeds):
        raise ValueError("Seed outside frozen protocol")
    train, validation = E.load_data("train"), E.load_data("validation")
    for seed in seeds:
        E.configure(seed)
        seed_folder = E.RESULTS / f"seed_{seed}"
        seed_folder.mkdir(exist_ok=True)
        methods = ordered_methods(protocol["methods"], protocol["seeds"].index(seed))
        registration = {"seed": seed, "methods": methods, "protocol_sha256": protocol_hash}
        registration_path = seed_folder / "registration.json"
        if registration_path.exists() and read_json(registration_path) != registration:
            raise ValueError("Seed registration changed")
        E.write_json(registration_path, registration)
        warm_start = time.perf_counter()
        warm = QPathTextModel(CONFIG).to("cuda")
        warm.route_mode = "shared"
        probe_indices = np.random.default_rng(seed + 50000).choice(len(train["labels"]), 1000, replace=False)
        warm_meta = run_phase(seed, "common_warmup", warm, train, validation, E.subset(train, probe_indices),
                             {"current_preparation_seconds": time.perf_counter() - warm_start}, protocol, protocol_hash)
        del warm
        if warm_meta["status"] != "completed":
            raise RuntimeError("Warmup incomplete; preserve and stop")
        warm = E.model_from_checkpoint(E.RESULTS / warm_meta["latest_eligible_checkpoint"])
        common = deepcopy(warm.state_dict())
        del warm
        for method in methods:
            folder = seed_folder / method
            folder.mkdir(exist_ok=True)
            if (folder / "status.json").exists() and read_json(folder / "status.json")["status"] == "completed":
                continue
            model, local_train, local_validation, prep = prepare_method(method, common, train, validation, seed, folder)
            prepared = dict(warm_meta, current_preparation_seconds=prep["total_preparation_seconds"], preparation_breakdown=prep)
            E.configure(seed + 30000)
            run_phase(seed, method, model, local_train, local_validation, E.subset(local_train, probe_indices), prepared, protocol, protocol_hash)
            del model, local_train, local_validation
            torch.cuda.empty_cache()
    E.write_json(E.RESULTS / "training_completed.json", {"utc": E.now(), "protocol_sha256": protocol_hash,
                  "seeds_requested": seeds, "test_accessed": False})


def select_candidate():
    protocol, protocol_hash = freeze("stage_a")
    activate("stage_a")
    rows = []
    for seed in protocol["seeds"]:
        for method in ARMS:
            path = E.RESULTS / f"seed_{seed}" / method / "status.json"
            state = read_json(path)
            if state["status"] != "completed" or state["latest_eligible_update"] != 3000:
                raise ValueError("Selection requires all12 complete development endpoints")
            rows.append({"seed": seed, "method": method, "f1": state["latest_validation"]["macro_f1"],
                         "seconds": state["charged_total_seconds"], "status_sha256": E.digest(path),
                         "checkpoint_sha256": E.digest(E.RESULTS / state["latest_eligible_checkpoint"])})
    averages = {method: {"f1": float(np.mean([r["f1"] for r in rows if r["method"] == method])),
                         "seconds": float(np.mean([r["seconds"] for r in rows if r["method"] == method]))} for method in ARMS}
    best_new = max(averages[m]["f1"] for m in NEW_ARMS)
    eligible = [m for m in NEW_ARMS if averages[m]["f1"] >= best_new - 0.001]
    chosen = min(eligible, key=lambda m: (averages[m]["seconds"], m))
    deltas = [next(r["f1"] for r in rows if r["seed"] == s and r["method"] == chosen)
              - next(r["f1"] for r in rows if r["seed"] == s and r["method"] == "shared") for s in protocol["seeds"]]
    promising = averages[chosen]["f1"] >= max(averages[m]["f1"] for m in ARMS[:2]) - 0.002 and min(deltas) >= -0.005
    selection = {"selected_candidate": chosen, "promising_gate": bool(promising),
                 "interpretation": "promising for confirmation" if promising else "diagnostic confirmation; improvement gate failed",
                 "stage_a_protocol_sha256": protocol_hash, "averages": averages, "seed_rows": rows,
                 "test_accessed": False, "rule": protocol["selection"]}
    path = ROOT / "selection_frozen.json"
    if path.exists() and read_json(path) != selection:
        raise ValueError("Attempt to change frozen selection")
    E.write_json(path, selection)
    E.write_json(ROOT / "selection_freeze_event.json", {"utc": E.now(), "sha256": E.digest(path)})
    print(json.dumps(selection, indent=2))


def preflight():
    E.enable_local_only()
    E.configure(191)
    train, validation = E.load_data("train"), E.load_data("validation")
    result = {"purpose": "Readiness only; random parameters/seed191, not an official study outcome", "methods": {}}
    timing_indices = np.random.default_rng(1191).integers(0, len(train["labels"]), size=(25, 64))
    result["sampling"] = "Same label-independent PCG64seed1191 random training minibatches for every method"
    for method in ARMS:
        model = QPathTextModel(replace(CONFIG, adapters=1) if method == "shared" else CONFIG).to("cuda")
        model.route_mode = "shared" if method == "shared" else "content"
        if method != "shared":
            centers = torch.nn.functional.normalize(torch.randn(18, 256, device="cuda"), dim=1)
            model.set_centroids(centers, ["readiness-only"])
        if method == "frozen_content":
            model.frozen_router = FrozenRoutingEncoder(model)
        model.route_mode = method if method in NEW_ARMS else model.route_mode
        optimizer = adamw_optimizer(model)
        timings = []
        # Representative mixed route load; synthetic cached route choice only in timing.
        for update in range(25):
            indices = timing_indices[update]
            tokens, mask, labels, _ = E.device_batch(train, indices)
            cached = torch.arange(64, device="cuda") % 18 if method in NEW_ARMS else None
            E.synchronize()
            start = time.perf_counter()
            train_update(model, optimizer, tokens, mask, labels, routing_features=cached)
            E.synchronize()
            if update >= 5:
                timings.append(time.perf_counter() - start)
        eval_data = dict(validation)
        if method in NEW_ARMS:
            eval_data["routing_features"] = torch.arange(len(validation["labels"])) % 18
        start = time.perf_counter()
        E.evaluate(model, eval_data)
        E.synchronize()
        result["methods"][method] = {"mean_update_seconds": float(np.mean(timings)), "update_seconds": timings,
                                       "validation_seconds": time.perf_counter() - start}
        del model, optimizer
        torch.cuda.empty_cache()
    per = result["methods"]
    warm = per["shared"]["mean_update_seconds"] * 1000 + per["shared"]["validation_seconds"] * 10
    result["projected_stage_a_training_validation_hours"] = (3 * warm + 3 * sum(per[m]["mean_update_seconds"] * 3000 + per[m]["validation_seconds"] * 30 for m in ARMS)) / 3600
    result["projected_stage_b_training_validation_hours"] = {candidate: (5 * warm + 5 * sum(per[m]["mean_update_seconds"] * 10000 + per[m]["validation_seconds"] * 100 for m in ["shared", "current_content", candidate])) / 3600 for candidate in NEW_ARMS}
    result["excluded_costs"] = ["centroid fits", "input-derived cache builds", "drift probes", "checkpoint IO", "final sealed evaluation", "thermal drift"]
    E.write_json(ROOT / "readiness" / "pilot.json", result)
    print(json.dumps(result, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["preflight", "freeze", "train", "select"])
    parser.add_argument("--stage", choices=["stage_a", "stage_b"], default="stage_a")
    parser.add_argument("--seeds", nargs="+", type=int)
    args = parser.parse_args()
    if args.action == "preflight":
        preflight()
    elif args.action == "freeze":
        print(freeze(args.stage)[1])
    elif args.action == "select":
        select_candidate()
    else:
        import ctypes
        start = time.perf_counter()
        guard = ctypes.windll.kernel32.SetThreadExecutionState(0x80000001) if os.name == "nt" else 0
        E.append_json(ROOT / "execution_segments.jsonl", {"event": "start", "utc": E.now(), "stage": args.stage, "sleep_guard": bool(guard)})
        status = "completed"
        try:
            run(args.stage, args.seeds)
        except BaseException:
            status = "failed_or_interrupted"
            raise
        finally:
            if guard:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            E.append_json(ROOT / "execution_segments.jsonl", {"event": "end", "utc": E.now(), "stage": args.stage,
                          "status": status, "actual_seconds": time.perf_counter() - start})


if __name__ == "__main__":
    main()
