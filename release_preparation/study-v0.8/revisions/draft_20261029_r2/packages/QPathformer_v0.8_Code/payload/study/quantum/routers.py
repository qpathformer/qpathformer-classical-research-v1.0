"""v0.8 train-only routers; unchanged v0.6 k-means, explicitly bound hash salt.

No labels, allocation classes, record IDs or held-out samples enter fitting.
The fitted hash cutpoints match training occupancy, not held-out occupancy.
"""
from __future__ import annotations

from bisect import bisect_left
import hashlib
import numpy as np

K = 5
RESTARTS = 20
MAX_ITER = 500
DOMAIN = b"QPATH-V08-HASH5\x00"


def canonical_features(x):
    a = np.asarray(x, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 2 or not np.isfinite(a).all():
        raise ValueError("Expected finite [N,2] numeric input features")
    a = np.array(a, dtype="<f8", order="C", copy=True)
    a[a == 0] = 0.0
    return a


def feature_keys(x):
    return [row.tobytes() for row in canonical_features(x)]


def feature_hashes(x, salt):
    if not isinstance(salt, str) or not salt or not salt.isascii():
        raise ValueError("Hash salt must be nonempty ASCII")
    prefix = DOMAIN + salt.encode("ascii") + b"\x00"
    return [hashlib.sha256(prefix + key).hexdigest() for key in feature_keys(x)]


def _distance(x, centers):
    distance = np.sum((x[:, None, :] - centers[None, :, :]) ** 2, axis=2)
    if not np.isfinite(distance).all():
        raise ValueError("Feature magnitude overflows squared Euclidean distance")
    return distance


def _canonical_order(centers):
    return np.lexsort((centers[:, 1], centers[:, 0]))


def _initial_centers(x, rng):
    chosen = [int(rng.integers(len(x)))]
    nearest = _distance(x, x[chosen])[:, 0]
    for _ in range(1, K):
        total = float(nearest.sum())
        if total <= 0:
            raise ValueError("Insufficient distinct coordinates for k-means++")
        cumulative = np.cumsum(nearest)
        index = min(int(np.searchsorted(cumulative, float(rng.random()) * total, side="right")), len(x) - 1)
        if index in chosen:
            positive = np.flatnonzero(nearest > 0)
            index = int(positive[0])
        chosen.append(index)
        nearest = np.minimum(nearest, _distance(x, x[[index]])[:, 0])
    return x[chosen].copy()


def _lloyd(x, initial, max_iter=MAX_ITER):
    centers = initial[_canonical_order(initial)].copy()
    for iteration in range(1, max_iter + 1):
        distances = _distance(x, centers)
        labels = distances.argmin(axis=1)
        counts = np.bincount(labels, minlength=K)
        updated = centers.copy()
        for bank in range(K):
            if counts[bank]:
                updated[bank] = x[labels == bank].mean(axis=0)
        # Sorted x makes the first index a lexicographic coordinate tie break.
        residual = distances[np.arange(len(x)), labels]
        candidates = np.argsort(-residual, kind="stable")
        used = set()
        for bank in np.flatnonzero(counts == 0):
            index = next(int(i) for i in candidates if int(i) not in used)
            used.add(index)
            updated[bank] = x[index]
        updated = updated[_canonical_order(updated)]
        new_labels = _distance(x, updated).argmin(axis=1)
        centers = updated
        if np.array_equal(new_labels, labels) and np.all(counts > 0):
            centers = centers[_canonical_order(centers)]
            labels = _distance(x, centers).argmin(axis=1)
            return centers, labels, iteration, True
    centers = centers[_canonical_order(centers)]
    labels = _distance(x, centers).argmin(axis=1)
    return centers, labels, max_iter, False


def fit_route_policy(x, seed, hash_salt):
    """Fit once on training x; returns JSON-safe, timing-independent policy."""
    a = canonical_features(x)
    if not isinstance(seed, (int, np.integer)) or int(seed) < 0:
        raise ValueError("Router seed must be a nonnegative integer")
    if len(a) < K or len(set(feature_keys(a))) != len(a):
        raise ValueError("Router fitting requires at least five unique training inputs")
    ordered = a[np.lexsort((a[:, 1], a[:, 0]))]
    candidates, records = [], []
    for restart in range(RESTARTS):
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([int(seed), restart])))
        centers, labels, iterations, converged = _lloyd(ordered, _initial_centers(ordered, rng))
        inertia = float(np.sum((ordered - centers[labels]) ** 2))
        counts = np.bincount(labels, minlength=K)
        eligible = bool(converged and np.all(counts > 0))
        records.append({"restart": restart, "iterations": iterations, "converged": converged,
                        "eligible": eligible, "inertia": inertia, "counts": counts.tolist()})
        if eligible:
            candidates.append((inertia, tuple(centers.ravel()), restart, centers, counts))
    if not candidates:
        raise RuntimeError("No nonempty converged k-means solution within registered restarts")
    inertia, _, restart, centers, counts = min(candidates, key=lambda item: item[:3])
    salt = hash_salt
    hashes = sorted(feature_hashes(ordered, salt))
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("Training feature-hash collision; no outcome-dependent retry is allowed")
    cuts = [hashes[int(cumulative) - 1] for cumulative in np.cumsum(counts)[:-1]]
    policy = {
        "schema": "qpath-v08-input-route-1", "banks": K, "seed": int(seed),
        "input": "Raw x0,x1 only, known common scale; no labels/classes/IDs/split metadata",
        "canonical_features": "float64 IEEE754 little-endian x0 then x1; signed zero normalized to +0; finite only",
        "training_n": len(a), "training_ordered_features_sha256": hashlib.sha256(a.tobytes()).hexdigest(),
        "training_feature_set_sha256": hashlib.sha256(ordered.tobytes()).hexdigest(),
        "centroids": centers.tolist(), "centroid_order": "lexicographic x0 then x1",
        "kmeans": {"distance": "squared Euclidean raw x", "initialization": "k-means++",
                   "restarts": RESTARTS, "max_iterations": MAX_ITER,
                   "rng": "NumPy PCG64 SeedSequence([seed,restart]); canonical-sorted training inputs",
                   "distance_ties": "lowest lexicographically ordered centroid index at every assignment",
                   "empty_cluster": "move empty center to farthest assigned input; ties canonical input order; distinct repair inputs",
                   "selection": "minimum inertia among converged nonempty restarts; exact tie centroid tuple then restart",
                   "selected_restart": restart, "selected_inertia": inertia, "restart_records": records},
        "kmeans_training_counts": counts.tolist(), "hash_salt": salt,
        "hash_definition": "SHA256(QPATH-V08-HASH5 + NUL + ASCII salt + NUL + canonical coordinate bytes)",
        "hash_cutpoints_hex": cuts, "hash_cut_rule": "four ascending 256-bit cutpoints inclusive in lower bank (bisect_left)",
        "hash_training_counts": counts.tolist(),
        "hash_target_scope": "Counts copied from canonical k-means banks on training only; joint fit cost includes k-means",
        "heldout_policy": "Apply fixed centroids/cutpoints; no refit or held-out count rebalance",
    }
    if not np.array_equal(np.bincount(route(a, policy, "hash"), minlength=K), counts):
        raise RuntimeError("Hash training occupancy does not match k-means")
    return policy


def route(x, policy, kind="kmeans"):
    a = canonical_features(x)
    if policy.get("schema") != "qpath-v08-input-route-1" or policy.get("banks") != K:
        raise ValueError("Unsupported fixed route policy")
    if kind == "kmeans":
        centers = canonical_features(policy["centroids"])
        if centers.shape != (K, 2) or not np.array_equal(_canonical_order(centers), np.arange(K)):
            raise ValueError("Centroids must have canonical five-bank ordering")
        return _distance(a, centers).argmin(axis=1).astype(np.int64)
    if kind == "hash":
        cuts = policy["hash_cutpoints_hex"]
        if (len(cuts) != K - 1 or any(not isinstance(v, str) or len(v) != 64 or
                                   any(c not in "0123456789abcdef" for c in v) for v in cuts)
                or cuts != sorted(set(cuts))):
            raise ValueError("Invalid immutable hash cutpoints")
        return np.asarray([bisect_left(cuts, value) for value in feature_hashes(a, policy["hash_salt"])], dtype=np.int64)
    raise ValueError("Route kind must be kmeans or hash")


def geometric_margin(x, policy):
    """Difference of second-nearest and nearest squared centroid distances."""
    a = canonical_features(x)
    # Reuse route validation, without fitting or reading labels.
    route(a, policy, "kmeans")
    distances = np.sort(_distance(a, canonical_features(policy["centroids"])), axis=1)
    return distances[:, 1] - distances[:, 0]


def fit_margin_bins(training_x, policy):
    """Training-only linear quantiles; deterministic removal of duplicate edges."""
    margins = geometric_margin(training_x, policy)
    if not len(margins):
        raise ValueError("Margin fitting requires training inputs")
    raw = np.quantile(margins, [0., .1, .25, .5, 1.], method="linear")
    edges = np.unique(raw)
    # If every margin equals one value, retain a single all-values bin.
    return {"schema": "qpath-v08-fixed-margin-bins-1",
            "quantiles": [0., .1, .25, .5, 1.],
            "quantile_method": "linear",
            "raw_edges": raw.tolist(), "unique_edges": edges.tolist(),
            "bins": max(1, len(edges)-1),
            "assignment": "searchsorted(interior unique edges, margin, side=right); extremes included in outer bins",
            "fit_scope": "training raw coordinates and frozen geometric router only"}


def margin_bins(x, policy, bins):
    if bins.get("schema") != "qpath-v08-fixed-margin-bins-1":
        raise ValueError("Unsupported margin bins")
    edges = np.asarray(bins["unique_edges"], dtype=np.float64)
    if edges.ndim != 1 or not len(edges) or not np.isfinite(edges).all() or (np.diff(edges) <= 0).any():
        raise ValueError("Invalid fixed margin edges")
    if bins["bins"] != max(1, len(edges)-1):
        raise ValueError("Invalid fixed margin-bin count")
    return np.searchsorted(edges[1:-1], geometric_margin(x, policy), side="right").astype(np.int64)
