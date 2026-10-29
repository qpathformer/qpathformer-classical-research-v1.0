"""Internal full-shape, fixed-update DBpedia comparison; local GPU execution only.

This runs the uniform shared-adapter and uniform content-routed methods. It is
not the semantic-priority factorial study or the development-qualified primary
efficiency comparison. The official test is scored only at frozen checkpoints.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import re
import socket
import sys
import time

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OPENBLAS_NUM_THREADS"] = "4"
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
import numpy as np
import psutil
import torch
from torch.nn import functional as F
from qpath.classical import (ModelConfig, QPathTextModel, TextTokenizer, adamw_optimizer,
                            parameter_counts, spherical_kmeans, train_update, FrozenRoutingEncoder)
from qpath.policies import learning_rate

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)

def append_json(path, value):
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")

def now():
    return datetime.now(timezone.utc).isoformat()

def synchronize():
    torch.cuda.synchronize()

def no_network(*args, **kwargs):
    raise RuntimeError("Network is disabled during internal training/evaluation")

def enable_local_only():
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network

def configure(seed, threads=4):
    torch.set_num_threads(threads)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

def load_data(split, folder=None):
    path = (Path(folder) if folder else DATA) / f"{split}_encoded.npz"
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    name = path.relative_to(DATA).as_posix()
    if digest(path) != manifest["file_sha256"][name]:
        raise ValueError("Encoded data payload hash mismatch")
    with np.load(path, allow_pickle=False) as archive:
        result = {key: archive[key].copy() for key in archive.files}
    result["tokens"] = torch.from_numpy(result["tokens"].astype(np.int64))
    result["mask"] = torch.from_numpy(result["mask"])
    result["labels"] = torch.from_numpy(result["labels"])
    return result

def device_batch(data, indexer):
    """Trim only right-padding, preserving every valid token and maxT=256."""
    mask = data["mask"][indexer]
    width = int(mask.sum(dim=1).max())
    return (data["tokens"][indexer, :width].to("cuda"), mask[:, :width].to("cuda"),
            data["labels"][indexer].to("cuda"), width)

def metrics_from_predictions(predictions, labels, count=14):
    matrix = np.zeros((count, count), dtype=np.int64)
    for truth, prediction in zip(labels, predictions):
        matrix[int(truth), int(prediction)] += 1
    per_label = []
    for label in range(count):
        true_positive = int(matrix[label, label])
        support = int(matrix[label].sum())
        false_negative = support - true_positive
        false_positive = int(matrix[:, label].sum()) - true_positive
        denominator = 2 * true_positive + false_negative + false_positive
        per_label.append({"label": label, "support": support,
                          "f1": 2 * true_positive / denominator if denominator else 0.0})
    return {"macro_f1": sum(row["f1"] for row in per_label) / count,
            "accuracy": float(np.trace(matrix) / len(labels)), "per_label": per_label,
            "confusion_matrix": matrix.tolist()}

@torch.no_grad()
def evaluate(model, data, use_adapters=True, embeddings=False):
    model.eval()
    predicted, routed, vectors = [], [], []
    total_loss = 0.0
    zero_norm = 0
    padded_positions = 0
    for start in range(0, len(data["labels"]), 64):
        tokens, mask, labels, width = device_batch(data, slice(start, start + 64))
        padded_positions += tokens.shape[0] * width
        cached = data.get("routing_features")
        cached = cached[start:start + 64].to("cuda") if cached is not None and use_adapters else None
        texts = data.get("texts")
        texts = texts[start:start + 64].tolist() if texts is not None else None
        output = model(tokens, mask, texts=texts, use_adapters=use_adapters, routing_features=cached)
        total_loss += float(F.cross_entropy(output["logits"], labels, reduction="sum"))
        predicted.extend(output["logits"].argmax(1).cpu().tolist())
        routed.extend(output["routes"].cpu().tolist())
        zero_norm += int(output["zero_norm"].sum())
        if embeddings:
            vectors.append(output["raw_pooled"].cpu())
    labels = data["labels"].tolist()
    result = metrics_from_predictions(predicted, labels, model.config.labels)
    result.update(cross_entropy=total_loss / len(labels), zero_norm_count=zero_norm,
                  actual_padded_token_positions=padded_positions)
    return result, np.array(predicted, dtype=np.int64), np.array(routed, dtype=np.int64), torch.cat(vectors) if vectors else None

def subset(data, indices):
    return {key: value[indices] for key, value in data.items()}

def checkpoint_state(model, optimizer, rng, state):
    return {"model": model.state_dict(), "optimizer": optimizer.state_dict(), "run_state": deepcopy(state),
            "model_config": asdict(model.config), "centroids_fitted": model.centroids_fitted,
            "centroid_training_ids": list(model.centroid_training_ids), "route_mode": model.route_mode,
            "route_seed": model.route_seed, "dispatch_mode": model.dispatch_mode, "torch_rng": torch.get_rng_state(),
            "cuda_rng": torch.cuda.get_rng_state_all(), "numpy_rng": rng.bit_generator.state,
            "python_rng": random.getstate(), "tokenizer_sha256": digest(DATA / "tokenizer.json"),
            "data_manifest_sha256": digest(DATA / "manifest.json")}

def save_checkpoint(path, payload):
    temporary = path.with_suffix(".tmp.pt")
    torch.save(payload, temporary)
    os.replace(temporary, path)

def restore_checkpoint(path, model, optimizer, rng):
    payload = torch.load(path, map_location="cuda", weights_only=True)
    if payload["tokenizer_sha256"] != digest(DATA / "tokenizer.json") or payload["data_manifest_sha256"] != digest(DATA / "manifest.json"):
        raise ValueError("Checkpoint data/tokenizer identity mismatch")
    if payload["route_mode"] == "frozen_content" and model.frozen_router is None:
        model.frozen_router = FrozenRoutingEncoder(model)
    model.load_state_dict(payload["model"])
    model.centroids_fitted = payload["centroids_fitted"]
    model.centroid_training_ids = tuple(payload["centroid_training_ids"])
    model.route_mode, model.route_seed = payload["route_mode"], payload["route_seed"]
    model.dispatch_mode = payload.get("dispatch_mode", "grouped")
    optimizer.load_state_dict(payload["optimizer"])
    torch.set_rng_state(payload["torch_rng"].cpu())
    torch.cuda.set_rng_state_all([value.cpu() for value in payload["cuda_rng"]])
    rng.bit_generator.state = payload["numpy_rng"]
    random.setstate(payload["python_rng"])
    return payload["run_state"]

def commit_checkpoint(folder, checkpoint, state):
    """Atomically bind a complete generation to its post-validation decisions.

    The previous committed generation is retained until the pointer commits.
    A crash during an uncommitted save cannot replace the resumable state.
    """
    checkpoint_hash = digest(checkpoint)
    committed = {"checkpoint": checkpoint.name, "sha256": checkpoint_hash,
                 "state": deepcopy(state), "committed_utc": now()}
    write_json(folder / "checkpoint_commit.json", committed)
    # Convenience aliases are published only after the pointer commits. Resume
    # and reporting use generation identities in the pointer, never these aliases.
    references = {"latest.pt": checkpoint}
    for key, alias in (("latest_eligible_checkpoint", "latest_eligible.pt"), ("target_checkpoint", "target.pt")):
        if state.get(key):
            references[alias] = RESULTS / state[key]
    for alias, source in references.items():
        temporary = folder / (alias + ".link.tmp")
        if temporary.exists():
            temporary.unlink()
        os.link(source, temporary)
        os.replace(temporary, folder / alias)
    # Prior generation files are rolling recovery artifacts, not distinct runs.
    # Target/latest-eligible hardlinks retain their content independently.
    retained = {source.resolve() for source in references.values()}
    for previous in folder.glob("checkpoint_*.pt"):
        if previous.resolve() not in retained:
            previous.unlink()
    return checkpoint_hash

def restore_committed_checkpoint(folder, model, optimizer, rng):
    committed = json.loads((folder / "checkpoint_commit.json").read_text(encoding="utf-8"))
    path = folder / committed["checkpoint"]
    if path.parent.resolve() != folder.resolve() or digest(path) != committed["sha256"]:
        raise ValueError("Committed checkpoint path/hash mismatch")
    payload_state = restore_checkpoint(path, model, optimizer, rng)
    if payload_state["phase_update"] != committed["state"]["phase_update"]:
        raise ValueError("Committed decision metadata does not match its model update")
    reconcile_uncommitted_artifacts(folder, committed["state"]["phase_update"])
    return committed["state"]


def reconcile_uncommitted_artifacts(folder, committed_update):
    """Preserve crash-tail evidence and restore a unique committed ledger prefix."""
    ledger = folder / "ledger.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines() if ledger.exists() else []
    keep, discarded = [], []
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            discarded.append(line)
            continue
        (keep if row["phase_update"] <= committed_update else discarded).append(line)
    updates = [json.loads(line)["phase_update"] for line in keep]
    if updates != sorted(set(updates)):
        raise ValueError("Committed ledger prefix contains duplicate or unordered updates")
    future_artifacts = []
    for pattern in ("validation_*.npz", "checkpoint_*.pt"):
        for artifact in folder.glob(pattern):
            match = re.fullmatch(r"(?:validation|checkpoint)_(\d+)(\.tmp)?\.(?:npz|pt)", artifact.name)
            if match and (int(match.group(1)) > committed_update or match.group(2)):
                future_artifacts.append(artifact)
    if discarded or future_artifacts:
        archive = folder / ("uncommitted_resume_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        archive.mkdir()
        (archive / "ledger_tail.jsonl").write_text("\n".join(discarded) + "\n", encoding="utf-8")
        for artifact in future_artifacts:
            os.replace(artifact, archive / artifact.name)
        temporary = folder / "ledger.reconciled.tmp"
        temporary.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
        os.replace(temporary, ledger)
        append_json(folder / "incidents.jsonl", {"utc": now(), "kind": "preserved_uncommitted_tail",
                    "committed_update": committed_update, "archive": archive.name, "discarded_ledger_rows": len(discarded)})

def model_from_checkpoint(path):
    payload = torch.load(path, map_location="cuda", weights_only=True)
    if payload["tokenizer_sha256"] != digest(DATA / "tokenizer.json") or payload["data_manifest_sha256"] != digest(DATA / "manifest.json"):
        raise ValueError("Inference checkpoint data/tokenizer identity mismatch")
    model = QPathTextModel(ModelConfig(**payload["model_config"])).to("cuda")
    if payload["route_mode"] == "frozen_content" and model.frozen_router is None:
        model.frozen_router = FrozenRoutingEncoder(model)
    model.load_state_dict(payload["model"])
    model.centroids_fitted = payload["centroids_fitted"]
    model.centroid_training_ids = tuple(payload["centroid_training_ids"])
    model.route_mode = payload["route_mode"]
    model.route_seed = payload["route_seed"]
    model.dispatch_mode = payload.get("dispatch_mode", "grouped")
    return model

