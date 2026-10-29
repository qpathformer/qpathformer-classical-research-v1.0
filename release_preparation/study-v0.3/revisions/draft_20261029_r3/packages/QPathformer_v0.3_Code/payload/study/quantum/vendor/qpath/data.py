"""Deterministic, local-only synthetic quantum benchmark and frozen splits."""
from __future__ import annotations

import hashlib
import numpy as np

DATA_SEEDS = {"features": 17, "classes": 23, "split": 29,
              "shuffle_train": 401, "shuffle_validation": 402, "shuffle_test": 403}


def array_hash(array):
    a = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(a.dtype).encode())
    digest.update(str(a.shape).encode())
    digest.update(a.tobytes())
    return digest.hexdigest()


def _allocate(counts, fraction, target):
    exact = np.asarray(counts) * fraction
    result = np.floor(exact).astype(int)
    # Largest remainder; stratum number breaks ties. Exact global split sizes.
    order = sorted(range(len(counts)), key=lambda k: (-(exact[k] - result[k]), k))
    for k in order[:target - int(result.sum())]:
        result[k] += 1
    return result


def make_dataset():
    x = np.random.Generator(np.random.PCG64(17)).uniform(-1, 1, (8000, 2))
    y = (np.sum(x * x, axis=1) < 2 / np.pi).astype(np.int64)
    classes = np.random.Generator(np.random.PCG64(23)).integers(1, 9, 8000)
    depth = 5 - (classes + 1) // 2
    strata = [np.flatnonzero((y == label) & (classes == c))
              for label in (0, 1) for c in range(1, 9)]
    rng = np.random.Generator(np.random.PCG64(29))
    strata = [rng.permutation(ids) for ids in strata]
    counts = [len(ids) for ids in strata]
    train_n, val_n = _allocate(counts, 0.6, 4800), _allocate(counts, 0.2, 1600)
    splits = {name: [] for name in ("train", "validation", "test")}
    for ids, n, m in zip(strata, train_n, val_n):
        splits["train"].extend(ids[:n])
        splits["validation"].extend(ids[n:n + m])
        splits["test"].extend(ids[n + m:])
    result = {"x": x, "y": y, "classes": classes, "depth": depth,
              "record_ids": np.arange(8000, dtype=np.int64)}
    for name, seed in zip(splits, (401, 402, 403)):
        ids = rng.permutation(np.asarray(splits[name], dtype=np.int64))
        result[name + "_ids"] = ids
        result[name + "_shuffled_depth"] = np.random.Generator(np.random.PCG64(seed)).permutation(depth[ids])
    return result


def manifest(data):
    result = {"generator": "NumPy PCG64", "numpy_version": np.__version__, "seeds": DATA_SEEDS,
              "n": 8000, "label_rule": "sum(x**2) < 2/pi",
              "split_rule": "60/20/20 label-by-class strata; largest remainders; ties by stratum",
              "hashes": {key: array_hash(value) for key, value in data.items()}, "splits": {}}
    for name in ("train", "validation", "test"):
        ids = data[name + "_ids"]
        result["splits"][name] = {"n": len(ids),
            "class_histogram": np.bincount(data["classes"][ids], minlength=9)[1:].tolist(),
            "label_histogram": np.bincount(data["y"][ids], minlength=2).tolist(),
            "depth_histogram": np.bincount(data["depth"][ids], minlength=5)[1:].tolist(),
            "shuffled_depth_histogram": np.bincount(data[name + "_shuffled_depth"], minlength=5)[1:].tolist()}
    return result
