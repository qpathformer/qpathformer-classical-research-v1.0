"""Post-release trace diagnostics; never train, select, or reconstruct new checkpoints."""
from pathlib import Path
import numpy as np
from gate import read, sha, require, binding


def describe_trace(counts, probabilities, labels, flips, routes, refresh_losses=None):
    """Pure exhaustive exposure calculations for labelled synthetic/unit fixtures."""
    counts = np.asarray(counts)
    probabilities = np.asarray(probabilities, dtype=np.float64)
    labels, flips = np.asarray(labels), np.asarray(flips)
    require(counts.ndim == 2 and probabilities.shape == counts.shape and counts.shape[1] == len(labels),
            "Trace shape mismatch")
    rounds, n = counts.shape
    require(rounds > 10 and n > 0, "Post-warmup rounds and nonempty training records required")
    require(labels.shape == flips.shape == (n,) and np.isin(labels, (0, 1)).all() and
            np.isin(flips, (0, 1)).all(), "Invalid labels/latent alignment")
    flips = flips.astype(bool)
    require(np.issubdtype(counts.dtype, np.integer) and (counts >= 0).all() and
            np.all(counts.sum(axis=1) == n), "Invalid replacement draw counts")
    require(np.isfinite(probabilities).all() and (probabilities > 0).all() and
            np.allclose(probabilities.sum(axis=1), 1, rtol=0, atol=2e-14), "Invalid actual round laws")
    for route in routes.values():
        require(np.asarray(route).shape == (n,) and np.isin(route, np.arange(5)).all(), "Invalid exposure route")
    if refresh_losses is not None:
        refresh_losses = np.asarray(refresh_losses, dtype=np.float64)
        require(refresh_losses.shape == (rounds-10, n) and np.isfinite(refresh_losses).all(),
                "Registered post-warmup refresh shape differs")
    rows = []
    for r in range(rounds):
        c, p = counts[r].astype(np.int64), probabilities[r]
        high = None if refresh_losses is None or r < 10 else np.asarray(refresh_losses[r-10]) > 5.
        rows.append({
            "round": r+1, "draws": n, "unique_records": int(np.count_nonzero(c)),
            "repeat_visits_after_first": int(n-np.count_nonzero(c)),
            "maximum_record_multiplicity": int(c.max()),
            "distribution_effective_records": float(1/np.sum(p*p)),
            "positive_draws": int(c[labels == 1].sum()),
            "flipped_label_draws": int(c[flips].sum()),
            "flipped_label_draw_fraction": float(c[flips].sum()/n),
            "flipped_label_probability_mass": float(p[flips].sum()),
            "high_loss_record_count": None if high is None else int(high.sum()),
            "high_loss_draws": None if high is None else int(c[high].sum()),
            "high_loss_probability_mass": None if high is None else float(p[high].sum()),
            "bank_draws": {kind: [int(c[np.asarray(route) == k].sum()) for k in range(5)]
                           for kind, route in routes.items()},
        })
    exposure = counts.astype(np.int64).sum(axis=0)
    total, noisy = int(exposure.sum()), int(exposure[flips].sum())
    return {"rounds": rows, "total_draws": total, "unique_records_over_horizon": int(np.count_nonzero(exposure)),
            "record_count": n, "flipped_training_record_count": int(flips.sum()),
            "flipped_training_record_fraction": float(flips.mean()),
            "flipped_label_draws": noisy, "flipped_label_draw_fraction": noisy/total,
            "noise_draw_fraction_minus_record_fraction": float(noisy/total-flips.mean()),
            "mean_post_warmup_effective_records": float(np.mean([row["distribution_effective_records"] for row in rows[10:]])),
            "mean_unique_records_per_round": float(np.mean([row["unique_records"] for row in rows])),
            "maximum_record_total_visits": int(exposure.max()),
            "scope": "Exhaustive descriptive training exposure after root test release. Flip flags never affect training or selection. Repeats are not independent examples."}, exposure


def load_released_training_diagnostics(root, population, seal):
    """Call only inside the release-verified evaluation body."""
    folder = Path(root)/"quantum/data"
    train = folder/f"{population}_train.npz"
    latent = folder/seal["diagnostics"][population]["file"]
    require(sha(train) == seal["files"][train.name]["sha256"], "Training exposure identity changed")
    require(sha(latent) == seal["diagnostics"][population]["sha256"], "Released latent payload changed")
    with np.load(train, allow_pickle=False) as arrays:
        data = {key: arrays[key].copy() for key in ("ids", "y", "hash_route", "kmeans_route")}
    with np.load(latent, allow_pickle=False) as arrays:
        require(np.array_equal(data["ids"], arrays["train_ids"]), "Latent training IDs do not align")
        flips, clean = arrays["train_label_flip"].copy(), arrays["train_clean_y"].copy()
    require(data["ids"].shape == (4800,) and np.isin(flips, (0, 1)).all() and
            np.isin(clean, (0, 1)).all() and np.array_equal(data["y"], np.logical_xor(clean, flips)),
            "Observed/latent labels disagree")
    data["label_flip"] = flips.astype(bool)
    data["bindings"] = {"training": binding(train), "sealed_latent": binding(latent)}
    return data


def endpoint_diagnostics(endpoint, commit, training, ledger):
    endpoint = Path(endpoint)
    names = ("sampling_counts.npy", "sampling_probabilities.npy", "refresh_native_losses.npy",
             "training_record_exposure.npy", "population_identity.npz")
    for name in names:
        require(sha(endpoint/name) == commit["files"][name]["sha256"], "Consumed priority evidence changed")
    with np.load(endpoint/"population_identity.npz", allow_pickle=False) as identity:
        require(np.array_equal(identity["train_ids"], training["ids"]), "Endpoint training IDs changed")
    counts = np.load(endpoint/"sampling_counts.npy", mmap_mode="r", allow_pickle=False)
    probabilities = np.load(endpoint/"sampling_probabilities.npy", mmap_mode="r", allow_pickle=False)
    losses = np.load(endpoint/"refresh_native_losses.npy", mmap_mode="r", allow_pickle=False)
    require(counts.shape == probabilities.shape == (200, 4800) and losses.shape == (190, 4800),
            "Incomplete full-horizon priority trace")
    result, exposure = describe_trace(counts, probabilities, training["y"], training["label_flip"],
        {"hash": training["hash_route"], "kmeans": training["kmeans_route"]}, losses)
    retained = np.load(endpoint/"training_record_exposure.npy", allow_pickle=False)
    require(np.array_equal(exposure, retained), "Cumulative exposure disagrees with round counts")
    for row, logged in zip(result["rounds"], ledger):
        sampling = logged["sampling"]
        require(row["round"] == logged["round"] and row["unique_records"] == sampling["unique_records_drawn"] and
                row["high_loss_draws"] == sampling["high_loss_draws"] and
                row["positive_draws"] == sampling["class_draws"][1] and
                abs(row["distribution_effective_records"]-sampling["distribution_effective_records"]) <= 1e-9,
                "Saved round diagnostics disagree with replayed exposure")
        row["logged_sampler"] = sampling
    result["data_evidence"] = training["bindings"]
    result["trace_evidence"] = {name: binding(endpoint/name) for name in names}
    evidence = {"training_record_ids": training["ids"], "observed_labels": training["y"],
                "label_flip": training["label_flip"], "record_exposure": exposure,
                "mean_actual_round_probability": np.asarray(probabilities).mean(axis=0),
                "hash_route": training["hash_route"], "kmeans_route": training["kmeans_route"]}
    return result, evidence
