"""Prepare v0.3 independent circle populations and training-only route policies.

This program computes labels for stratified sampling/provenance only. It never
loads a model or evaluates an outcome. Existing data folders are never replaced.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import time
import numpy as np

from routers import canonical_features, feature_keys, fit_route_policy, route

ROOT = Path(__file__).resolve().parent
DATASETS = {"development": (130017, 130023, 130029),
            "confirmation": (230017, 230023, 230029),
            "engineering": (330017, 330023, 330029)}
V01 = Path(r"C:\Q2\Full_Local_Benchmark_v0.1\quantum")
V02 = Path(r"C:\Anthony Siljeg\Q2_improvement_study_v02\quantum\data")
V02_SEAL_SHA256 = "3f64622469ee967812f4ef88f0a4d33430a605c78b9185a9cf5fe27bff7e6f0f"
V01_FEATURES_SHA256 = "6a817018a15f5b4f439c4d868310bf420978880d634ba71f699a580c48634b63"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_hash(value):
    a = np.ascontiguousarray(value)
    h = hashlib.sha256()
    h.update(str(a.dtype).encode())
    h.update(str(a.shape).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _allocate(counts, fraction, target):
    exact = np.asarray(counts) * fraction
    result = np.floor(exact).astype(np.int64)
    order = sorted(range(len(counts)), key=lambda k: (-(exact[k] - result[k]), k))
    for index in order[:target - int(result.sum())]:
        result[index] += 1
    if int(result.sum()) != target:
        raise ValueError("Stratified allocation failed")
    return result


def historical_features():
    """Read original data arrays and manifests only; never import old sources."""
    excluded, sources = set(), []
    for seed in range(201, 206):
        path = V01 / "runs" / f"seed_{seed}" / "frozen_dataset.npz"
        manifest_path = path.with_name("data_manifest.json")
        meta = json.loads(manifest_path.read_text(encoding="utf-8"))
        with np.load(path, allow_pickle=False) as payload:
            x = payload["x"]
        if array_hash(x) != meta["hashes"]["x"] or array_hash(x) != V01_FEATURES_SHA256:
            raise ValueError("Historical v0.1 feature identity changed")
        excluded.update(feature_keys(x))
        sources.append({"version": "v0.1", "path": str(path), "sha256": digest(path),
                        "manifest_path": str(manifest_path), "manifest_sha256": digest(manifest_path),
                        "feature_array_sha256": array_hash(x), "records": len(x)})
    old_seal = V02 / "DATA_SEAL.json"
    if digest(old_seal) != V02_SEAL_SHA256:
        raise ValueError("Historical v0.2 seal identity changed")
    seal = json.loads(old_seal.read_text(encoding="utf-8"))
    for name in sorted(seal["files"]):
        info = seal["files"][name]
        path = V02 / name
        if digest(path) != info["sha256"]:
            raise ValueError("Historical v0.2 payload identity changed")
        with np.load(path, allow_pickle=False) as payload:
            x = payload["x"]
        if array_hash(x) != info["arrays"]["x"]:
            raise ValueError("Historical v0.2 feature array changed")
        excluded.update(feature_keys(x))
        sources.append({"version": "v0.2", "path": str(path), "sha256": digest(path),
                        "manifest_path": str(old_seal), "manifest_sha256": digest(old_seal),
                        "feature_array_sha256": array_hash(x), "records": len(x)})
    return excluded, sources


def generate(seeds, excluded):
    """Return fixed splits and redraw evidence; do not mutate caller exclusions."""
    feature_seed, classes_seed, split_seed = seeds
    rng = np.random.Generator(np.random.PCG64(feature_seed))
    accepted, draw_ids, rejected = [], [], []
    seen, consumed = set(), 0
    while len(accepted) < 8000:
        candidates = canonical_features(rng.uniform(-1, 1, (8000 - len(accepted), 2)))
        for candidate in candidates:
            key = candidate.tobytes()
            if key in excluded or key in seen:
                rejected.append({"draw_index": consumed, "feature_sha256": hashlib.sha256(key).hexdigest(),
                                 "reason": "prior_population_exact_match" if key in excluded else "within_population_duplicate"})
            else:
                accepted.append(candidate)
                draw_ids.append(consumed)
                seen.add(key)
            consumed += 1
        if consumed > 1000000:
            raise RuntimeError("Exclusion redraw limit exceeded; no alternate seed search")
    x = canonical_features(accepted)
    y = (np.sum(x * x, axis=1) < 2 / np.pi).astype(np.int64)
    classes = np.random.Generator(np.random.PCG64(classes_seed)).integers(1, 9, 8000, dtype=np.int64)
    depth = 5 - (classes + 1) // 2
    draw_ids = np.asarray(draw_ids, dtype=np.int64)
    rng = np.random.Generator(np.random.PCG64(split_seed))
    groups = [rng.permutation(np.flatnonzero((y == label) & (classes == category)))
              for label in (0, 1) for category in range(1, 9)]
    counts = [len(group) for group in groups]
    train_n, val_n = _allocate(counts, 0.6, 4800), _allocate(counts, 0.2, 1600)
    splits = {name: [] for name in ("train", "validation", "test")}
    for group, n, m in zip(groups, train_n, val_n):
        if n + m > len(group):
            raise ValueError("Stratum allocations overlap")
        splits["train"].extend(group[:n]); splits["validation"].extend(group[n:n + m]); splits["test"].extend(group[n + m:])
    result = {}
    for name, membership in splits.items():
        ids = rng.permutation(np.asarray(membership, dtype=np.int64))
        result[name] = {"x": x[ids], "y": y[ids], "classes": classes[ids], "depth": depth[ids],
                        "ids": ids, "source_draw_ids": draw_ids[ids]}
    return result, {"draws_consumed": consumed, "accepted": 8000, "rejected": rejected,
                    "stratum_counts": counts}, seen


def main():
    started = time.perf_counter()
    source_hashes = {name: digest(ROOT / name) for name in ("prepare_data.py", "routers.py")}
    folder = ROOT / "data"
    if folder.exists():
        raise FileExistsError("Preserve existing data; official preparation is one-time")
    excluded, sources = historical_features()
    historical_count = len(excluded)
    source_seconds = time.perf_counter() - started
    folder.mkdir()
    seal = {"schema": "qpath-v03-data-seal-1", "created_utc": now(), "status": "sealed before official training",
            "visibility": "INTERNAL NOT FOR PUBLICATION", "outcomes_evaluated": False,
            "generator": "NumPy PCG64", "numpy_version": np.__version__, "source_sha256": source_hashes,
            "rule": "x uniform[-1,1]^2; y=sum(x*x)<2/pi; independent C1..8; depths4,4,3,3,2,2,1,1",
            "split": "label-by-class stratified largest-remainder 4800/1600/1600; fraction ties use stratum index",
            "exclusion": "Exact canonical float64 x0,x1 byte equality against all historical inputs and prior new populations; signed zero normalized. Population order development,confirmation,engineering. Reject in draw order then draw exactly the remaining count from the same stream; no seed search.",
            "historical_unique_features": historical_count, "historical_sources": sources,
            "historical_source_verification_seconds": source_seconds,
            "datasets": {}, "files": {}, "routers": {},
            "seal_limitation": "Procedural loader/hash seal, not encryption. Test labels/routes are computed only for generation/provenance; no model or test outcome is evaluated.",
            "interpretation_limit": "New independent populations of the same circle mechanism, not a new task; exact exclusions do not rule out nearby points or encoded-state similarity."}
    for name, seeds in DATASETS.items():
        population_started = time.perf_counter()
        populations, redraw, new_keys = generate(seeds, excluded)
        excluded.update(new_keys)
        generation_seconds = time.perf_counter() - population_started
        fit_started = time.perf_counter()
        router_seed = seeds[0] + 70000
        policy = fit_route_policy(populations["train"]["x"], router_seed)
        fit_seconds = time.perf_counter() - fit_started
        policy["population"] = name
        policy["training_ids_array_sha256"] = array_hash(populations["train"]["ids"])
        policy_path = folder / f"{name}_router.json"
        write_json(policy_path, policy)
        seal["routers"][name] = {"file": policy_path.name, "sha256": digest(policy_path), "seed": router_seed,
                                  "training_n": 4800, "fit_seconds": fit_seconds,
                                  "fit_scope": "Joint training-only k-means plus occupancy-matched hash cuts; same fixed policy for all model seeds"}
        cache_times, cache_counts = {}, {}
        for split, data in populations.items():
            cache_times[split], cache_counts[split] = {}, {}
            for kind in ("kmeans", "hash"):
                apply_started = time.perf_counter()
                values = route(data["x"], policy, kind)
                cache_times[split][kind] = time.perf_counter() - apply_started
                data[kind + "_route"] = values
                cache_counts[split][kind] = np.bincount(values, minlength=5).tolist()
            filename = f"{name}_{'SEALED_test' if split == 'test' else split}.npz"
            path = folder / filename
            with path.open("xb") as handle:
                np.savez(handle, **data)
            seal["files"][filename] = {"sha256": digest(path), "arrays": {k: array_hash(v) for k, v in data.items()},
                                        "n": len(data["y"]), "dataset": name, "split": split,
                                        "router_policy_sha256": digest(policy_path)}
        if cache_counts["train"]["kmeans"] != cache_counts["train"]["hash"]:
            raise ValueError("Unmatched training route occupancy")
        seal["datasets"][name] = {"seeds": dict(zip(("features", "classes", "split"), seeds)),
                                   "counts": {key: len(value["y"]) for key, value in populations.items()},
                                   "redraw": redraw, "route_counts": cache_counts,
                                   "generation_seconds": generation_seconds, "router_fit_seconds": fit_seconds,
                                   "route_application_seconds_by_split": cache_times,
                                   "total_population_preparation_seconds": time.perf_counter() - population_started}
    if source_hashes != {name: digest(ROOT / name) for name in source_hashes}:
        raise RuntimeError("Preparation source changed during generation")
    seal["total_preparation_seconds"] = time.perf_counter() - started
    seal["post_generation_total_unique_features"] = len(excluded)
    write_json(folder / "DATA_SEAL.json", seal)
    print(json.dumps({"status": "PREPARED_SEALED_NO_MODEL_OUTCOMES", "seal_sha256": digest(folder / 'DATA_SEAL.json'),
                      "records": 24000, "historical_unique_features": historical_count,
                      "training_counts": {name: value["route_counts"]["train"] for name, value in seal["datasets"].items()}}, indent=2), flush=True)


if __name__ == "__main__":
    main()
