"""Prepare fresh v0.5 coordinates, labels, fixed splits and input-only routers.

No model is imported or evaluated. Historical files are read for exact input
exclusion only. Existing data are never replaced; failed preparation is retained.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import platform
import time
import traceback
import numpy as np

from routers import canonical_features, feature_keys, fit_route_policy, route

ROOT = Path(__file__).resolve().parent
DATASETS = {
    "engineering_circle": (1430017, 1430023, 1430029),
    "engineering_ellipse": (1440017, 1440023, 1440029),
    "development_circle": (1530017, 1530023, 1530029),
    "development_ellipse": (1540017, 1540023, 1540029),
    "confirmation_circle_1": (1630017, 1630023, 1630029),
    "confirmation_circle_2": (1640017, 1640023, 1640029),
    "confirmation_ellipse": (1650017, 1650023, 1650029),
}
POPULATION_N = 8000
SPLIT_COUNTS = {"train": 4800, "validation": 1600, "test": 1600}
EXPECTED_NUMPY = "2.5.4"
STUDY_ID = "QPATH-READOUT-v0.5"
HISTORICAL_UNIQUE_EXPECTED = 112000
HISTORICAL_SOURCES_EXPECTED = 44
NEW_UNIQUE_EXPECTED = 56000
V01 = Path(r"C:\Q2\Full_Local_Benchmark_v0.1\quantum")
HISTORICAL = {
    "v0.2": (Path(r"C:\Anthony Siljeg\Q2_improvement_study_v02\quantum\data"),
             "3f64622469ee967812f4ef88f0a4d33430a605c78b9185a9cf5fe27bff7e6f0f"),
    "v0.3": (Path(r"C:\Anthony Siljeg\Q2_improvement_study_v03\quantum\data"),
             "94a1cd56e61c8c803910b9dc08803d7e524ae4ed5231fb8bc028fd86fd54048f"),
    "v0.4": (Path(r"C:\Q2\Improvement_Study_v0.4\quantum\data"),
             "e5c650ececca5f59703078ea3ff4b03fb39192cee00153853b739f365b8ece60"),
}
V01_FEATURES_SHA256 = "6a817018a15f5b4f439c4d868310bf420978880d634ba71f699a580c48634b63"
ROUTER_SOURCE = Path(r"C:\Q2\Improvement_Study_v0.4\quantum\routers.py")
ROUTER_SOURCE_SHA256 = "0b62c0bcca42ab93551dab88e0e20828158f8a3d529253db6f0c1a5cf67a2c68"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_hash(value):
    array = np.ascontiguousarray(value)
    result = hashlib.sha256()
    result.update(str(array.dtype).encode())
    result.update(str(array.shape).encode())
    result.update(array.tobytes())
    return result.hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _allocate(counts, fraction, target):
    exact = np.asarray(counts) * fraction
    result = np.floor(exact).astype(np.int64)
    remaining = target - int(result.sum())
    require(0 <= remaining <= len(counts), "Invalid largest-remainder allocation")
    order = sorted(range(len(counts)), key=lambda k: (-(exact[k] - result[k]), k))
    for index in order[:remaining]:
        result[index] += 1
    require(int(result.sum()) == target, "Stratified allocation failed")
    return result


def labels_for(x, task):
    """Frozen analytic labels; no fitted boundary or outcome-dependent parameters."""
    x = canonical_features(x)
    if task == "circle":
        positive = np.sum(x * x, axis=1) < 2 / np.pi
    elif task == "ellipse":
        u = (x[:, 0] + x[:, 1]) / np.sqrt(2.0)
        v = (-x[:, 0] + x[:, 1]) / np.sqrt(2.0)
        a = np.sqrt(2 / np.pi) * np.sqrt(1.5)
        b = np.sqrt(2 / np.pi) / np.sqrt(1.5)
        positive = (u / a) ** 2 + (v / b) ** 2 < 1.0
    else:
        raise ValueError("Task must be circle or ellipse")
    return positive.astype(np.int64)


def task_for(name):
    require(name in DATASETS, "Unregistered population")
    return "ellipse" if "ellipse" in name else "circle"


def historical_expected_names(version):
    """Explicit version-specific inventory; v0.4 introduced seven populations."""
    require(version in HISTORICAL, "Unregistered historical version")
    populations = tuple(DATASETS) if version == "v0.4" else ("development", "confirmation", "engineering")
    return {f"{population}_{split}.npz" for population in populations
            for split in ("train", "validation", "SEALED_test")}


def validate_registration(registration):
    """Bind root-approved seeds and fixed data semantics before any generation."""
    require(registration.get("study_id") == STUDY_ID
            and registration.get("status") == "ROOT_APPROVED_DATA_DESIGN_BEFORE_GENERATION",
            "Root-approved data registration required")
    require(registration["populations"] == {name: list(seeds) for name, seeds in DATASETS.items()},
            "Registered population seeds differ")
    require(registration["population_n"] == POPULATION_N
            and registration["split_counts"] == SPLIT_COUNTS,
            "Registered population/split counts differ")
    require(registration["historical_unique_features"] == HISTORICAL_UNIQUE_EXPECTED
            and registration["historical_npz_sources"] == HISTORICAL_SOURCES_EXPECTED
            and registration["new_unique_features"] == NEW_UNIQUE_EXPECTED,
            "Registered historical/new coverage differs")
    require(registration["numpy_version"] == EXPECTED_NUMPY
            and registration["router_source_sha256"] == ROUTER_SOURCE_SHA256,
            "Registered runtime/router identity differs")
    require(registration["task_semantics"] == {
        "coordinates": "Independent uniform[-1,1]^2",
        "circle_threshold_squared": "2/pi", "ellipse_rotation_degrees": 45,
        "ellipse_axis_ratio": 1.5, "ellipse_area": 2.0, "strict_boundary": True},
        "Registered task geometry differs")
    require(len({seed for seeds in DATASETS.values() for seed in seeds}) == 3 * len(DATASETS),
            "Population seed identities overlap")


def historical_features():
    """Load x only; verify historical source bytes and arrays against fixed seals."""
    excluded, sources = set(), []
    v03_folder, expected_v03 = HISTORICAL["v0.3"]
    v03_seal_path = v03_folder / "DATA_SEAL.json"
    require(digest(v03_seal_path) == expected_v03, "Historical v0.3 seal changed")
    v03_seal = json.loads(v03_seal_path.read_text(encoding="utf-8"))
    v01_provenance = {row["path"]: row for row in v03_seal["historical_sources"] if row["version"] == "v0.1"}
    for seed in range(201, 206):
        path = V01 / "runs" / f"seed_{seed}" / "frozen_dataset.npz"
        manifest_path = path.with_name("data_manifest.json")
        require(str(path) in v01_provenance, "v0.1 source absent from fixed v0.3 provenance")
        identity = v01_provenance[str(path)]
        require(digest(path) == identity["sha256"] and digest(manifest_path) == identity["manifest_sha256"],
                "Historical v0.1 payload or manifest changed")
        meta = json.loads(manifest_path.read_text(encoding="utf-8"))
        with np.load(path, allow_pickle=False) as payload:
            x = payload["x"]
        require(array_hash(x) == meta["hashes"]["x"] == V01_FEATURES_SHA256,
                "Historical v0.1 feature array changed")
        excluded.update(feature_keys(x))
        sources.append({"version": "v0.1", "path": str(path), "sha256": digest(path),
                        "manifest_path": str(manifest_path), "manifest_sha256": digest(manifest_path),
                        "feature_array_sha256": array_hash(x), "records": len(x),
                        "read_scope": "x only; no saved model outcomes"})
    for version, (folder, expected_seal) in HISTORICAL.items():
        expected_names = historical_expected_names(version)
        seal_path = folder / "DATA_SEAL.json"
        require(digest(seal_path) == expected_seal, "Historical data seal changed: " + version)
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        require(set(seal["files"]) == expected_names, "Unexpected historical data inventory")
        for name in sorted(expected_names):
            info = seal["files"][name]
            path = folder / name
            require(digest(path) == info["sha256"], "Historical payload changed: " + str(path))
            with np.load(path, allow_pickle=False) as payload:
                x = payload["x"]
            require(array_hash(x) == info["arrays"]["x"] and len(x) == info["n"],
                    "Historical feature array changed: " + str(path))
            excluded.update(feature_keys(x))
            sources.append({"version": version, "path": str(path), "sha256": digest(path),
                            "manifest_path": str(seal_path), "manifest_sha256": digest(seal_path),
                            "feature_array_sha256": array_hash(x), "records": len(x),
                            "read_scope": "x only; no saved model outcomes"})
    require(len(sources) == HISTORICAL_SOURCES_EXPECTED, "Historical source count differs")
    require(len(excluded) == HISTORICAL_UNIQUE_EXPECTED, "Historical unique feature count differs")
    return excluded, sources


def generate(seeds, excluded, task):
    """Generate one population without modifying caller exclusion membership."""
    feature_seed, metadata_seed, split_seed = seeds
    require(all(isinstance(value, (int, np.integer)) and value >= 0 for value in seeds), "Invalid seeds")
    require(feature_seed * 1000000 + POPULATION_N < np.iinfo(np.int64).max, "Record-ID range overflow")
    rng = np.random.Generator(np.random.PCG64(feature_seed))
    accepted, draw_ids, rejected = [], [], []
    seen, consumed = set(), 0
    while len(accepted) < POPULATION_N:
        candidates = canonical_features(rng.uniform(-1, 1, (POPULATION_N - len(accepted), 2)))
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
    y = labels_for(x, task)
    ids = (feature_seed * 1000000 + np.random.Generator(np.random.PCG64(metadata_seed)).permutation(POPULATION_N)).astype(np.int64)
    draw_ids = np.asarray(draw_ids, dtype=np.int64)
    rng = np.random.Generator(np.random.PCG64(split_seed))
    groups = [rng.permutation(np.flatnonzero(y == label)) for label in (0, 1)]
    counts = [len(group) for group in groups]
    train_n = _allocate(counts, 0.6, SPLIT_COUNTS["train"])
    val_n = _allocate(counts, 0.2, SPLIT_COUNTS["validation"])
    splits = {name: [] for name in SPLIT_COUNTS}
    for group, n, m in zip(groups, train_n, val_n):
        require(n + m <= len(group), "Stratum allocations overlap")
        splits["train"].extend(group[:n])
        splits["validation"].extend(group[n:n + m])
        splits["test"].extend(group[n + m:])
    result = {}
    for name, membership in splits.items():
        selected = rng.permutation(np.asarray(membership, dtype=np.int64))
        require(len(selected) == SPLIT_COUNTS[name], "Split count differs")
        result[name] = {"x": x[selected], "y": y[selected], "ids": ids[selected],
                        "source_draw_ids": draw_ids[selected]}
    return result, {"draws_consumed": consumed, "accepted": POPULATION_N, "rejected": rejected,
                    "stratum_order": [0, 1], "stratum_counts": counts,
                    "train_stratum_counts": train_n.tolist(), "validation_stratum_counts": val_n.tolist()}, seen


def check_prepared_population(parts, policy, keys, excluded_ids):
    """Schema and provenance validation only; no predictive or semantic audit."""
    all_ids = []
    all_keys = []
    for split, part in parts.items():
        n = SPLIT_COUNTS[split]
        require(part["x"].shape == (n, 2) and part["x"].dtype == np.float64, "Feature schema differs")
        require(np.isfinite(part["x"]).all() and (np.abs(part["x"]) <= 1).all(), "Feature range differs")
        for name in ("y", "ids", "source_draw_ids", "hash_route", "kmeans_route"):
            require(part[name].shape == (n,) and part[name].dtype == np.int64, "Integer schema differs")
        require(set(part["y"]) <= {0, 1}, "Label range differs")
        for kind in ("hash", "kmeans"):
            require(set(part[kind + "_route"]) <= set(range(5)), "Route range differs")
            require(np.array_equal(part[kind + "_route"], route(part["x"], policy, kind)), "Route cache differs")
        all_ids.extend(part["ids"].tolist())
        all_keys.extend(feature_keys(part["x"]))
    require(len(set(all_ids)) == POPULATION_N and set(all_ids).isdisjoint(excluded_ids), "Record IDs overlap")
    require(len(set(all_keys)) == POPULATION_N and set(all_keys) == keys, "Feature split integrity failed")
    return set(all_ids)


def main():
    started = time.perf_counter()
    folder = ROOT / "data"
    if folder.exists():
        raise FileExistsError("Preserve existing data; official preparation is one-time")
    require(np.__version__ == EXPECTED_NUMPY, "Use the registered NumPy runtime")
    source_names = ("prepare_data.py", "routers.py", "tests/test_routers_data.py")
    source_hashes = {name: digest(ROOT / name) for name in source_names}
    require(source_hashes["routers.py"] == digest(ROUTER_SOURCE) == ROUTER_SOURCE_SHA256,
            "Router reuse is not byte-identical to the reviewed v0.3/v0.4 algorithm")
    registration_path = ROOT.parent / "governance" / "DATA_REGISTRATION.json"
    registration_raw = registration_path.read_bytes()
    registration = json.loads(registration_raw)
    validate_registration(registration)
    excluded, sources = historical_features()
    historical_count = len(excluded)
    source_seconds = time.perf_counter() - started
    folder.mkdir()
    seal = {
        "schema": "qpath-v05-data-seal-1", "study_id": STUDY_ID, "created_utc": now(), "status": "sealed before official training",
        "visibility": "INTERNAL NOT FOR PUBLICATION", "outcomes_evaluated": False,
        "generator": "NumPy PCG64", "numpy_version": np.__version__, "python_version": platform.python_version(),
        "source_sha256": source_hashes,
        "design_reference": {"path": str(registration_path), "sha256": hashlib.sha256(registration_raw).hexdigest(),
                             "status_when_read": registration["status"], "data_contract": registration},
        "rule": {"coordinates": "Independent uniform[-1,1]^2; finite little-endian float64 x0,x1; signed zero normalized",
                 "circle": "y=1 iff sum(x*x)<2/pi; strict inequality",
                 "ellipse": "u=(x0+x1)/sqrt(2); v=(-x0+x1)/sqrt(2); a=sqrt(2/pi)*sqrt(1.5); b=sqrt(2/pi)/sqrt(1.5); y=1 iff (u/a)^2+(v/b)^2<1; strict inequality",
                 "ellipse_constants": {"rotation_degrees": 45, "axis_ratio": 1.5,
                                       "a": float(np.sqrt(2 / np.pi) * np.sqrt(1.5)),
                                       "b": float(np.sqrt(2 / np.pi) / np.sqrt(1.5))},
                 "labels": "Analytic generator labels only; no manual semantic-label verification claim"},
        "record_ids": "int64 feature_seed*1000000 + PCG64(metadata_seed).permutation(8000), paired with accepted draw order; globally unique and never a model/router input",
        "split": "Binary-label-only largest-remainder 4800/1600/1600; train fraction0.6 and validation fraction0.2 allocated independently with exact remainder ties label0 first; test gets remainder. PCG64(split_seed) permutes indices within label0 then label1, then permutes each full split in train/validation/test order. No outcome filtering or class rebalancing.",
        "exclusion": "Exact canonical float64 coordinate bytes against all historical inputs and prior new populations; signed zero normalized. Reject in original draw order then draw exactly remaining count from same PCG64 stream; no alternate seed search; maximum1000000 draws.",
        "population_order": list(DATASETS), "historical_unique_features": historical_count,
        "historical_sources_expected": HISTORICAL_SOURCES_EXPECTED,
        "combined_unique_features_expected": HISTORICAL_UNIQUE_EXPECTED + NEW_UNIQUE_EXPECTED,
        "historical_sources": sources, "historical_source_verification_seconds": source_seconds,
        "router_implementation": {"path": str(ROUTER_SOURCE), "sha256": ROUTER_SOURCE_SHA256,
            "byte_identical_reuse": True, "retained_identifiers": "qpath-v03-input-route-1 schema, QPATH-V03-HASH5 domain and qpath-v03 salt prefix identify the unchanged algorithm, not reused fitted policies or data",
            "fit_seed": "feature_seed + 70000", "fit_inputs": "Training raw x only; no labels, record IDs, split indicators or task geometry. Kmeans5 raw Euclidean,20 kmeans++ restarts,max500 Lloyd iterations; unchanged v0.3 tie/empty/selection rules recorded in each policy",
            "hash_matching": "Canonical feature SHA256 with salt from router seed; four training-only quantile cutpoints match canonical kmeans bank training counts. Fixed heldout cuts; no heldout rebalance"},
        "datasets": {}, "files": {}, "routers": {},
        "model_input_contract": "Only x0,x1; route caches select a fixed bank. No depth/classes/noise allocation fields exist.",
        "seal_limitation": "Procedural loader/hash seal, not encryption. Test labels and fixed routes computed for generation/provenance only; no model or test model outcome evaluated.",
        "interpretation_limit": "Fresh populations with the same circle/ellipse task semantics as v0.4, not a paired version-improvement estimate or real-world transfer. Exact exclusion does not rule out nearby points or encoded-state similarity. Train-only routers are fitted on training membership; label stratification helps assign membership but router fit has no label input.",
    }
    try:
        observed_ids = set()
        for name, seeds in DATASETS.items():
            population_started = time.perf_counter()
            parts, redraw, new_keys = generate(seeds, excluded, task_for(name))
            require(new_keys.isdisjoint(excluded), "New population overlaps earlier input")
            excluded.update(new_keys)
            generation_seconds = time.perf_counter() - population_started
            fit_started = time.perf_counter()
            router_seed = seeds[0] + 70000
            policy = fit_route_policy(parts["train"]["x"], router_seed)
            fit_seconds = time.perf_counter() - fit_started
            policy["population"] = name
            policy["training_ids_array_sha256"] = array_hash(parts["train"]["ids"])
            policy_path = folder / f"{name}_router.json"
            write_json(policy_path, policy)
            policy_sha = digest(policy_path)
            seal["routers"][name] = {"file": policy_path.name, "sha256": policy_sha, "seed": router_seed,
                                     "training_n": SPLIT_COUNTS["train"], "fit_seconds": fit_seconds,
                                     "fit_scope": "Training-only kmeans plus occupancy-matched hash cuts; shared frozen policies across all methods/seeds"}
            cache_times, cache_counts = {}, {}
            for split, part in parts.items():
                cache_times[split], cache_counts[split] = {}, {}
                for kind in ("kmeans", "hash"):
                    apply_started = time.perf_counter()
                    values = route(part["x"], policy, kind)
                    cache_times[split][kind] = time.perf_counter() - apply_started
                    part[kind + "_route"] = values
                    cache_counts[split][kind] = np.bincount(values, minlength=5).tolist()
            observed_ids.update(check_prepared_population(parts, policy, new_keys, observed_ids))
            require(cache_counts["train"]["kmeans"] == cache_counts["train"]["hash"], "Unmatched training bank counts")
            for split, part in parts.items():
                filename = f"{name}_{'SEALED_test' if split == 'test' else split}.npz"
                path = folder / filename
                with path.open("xb") as handle:
                    np.savez(handle, **part)
                seal["files"][filename] = {"sha256": digest(path), "arrays": {k: array_hash(v) for k, v in part.items()},
                    "n": len(part["y"]), "dataset": name, "task": task_for(name), "split": split,
                    "router_policy_sha256": policy_sha}
            seal["datasets"][name] = {"task": task_for(name),
                "seeds": dict(zip(("features", "metadata", "split"), seeds)),
                "counts": {split: len(part["y"]) for split, part in parts.items()},
                "label_counts": {split: np.bincount(part["y"], minlength=2).tolist() for split, part in parts.items()},
                "redraw": redraw, "route_counts": cache_counts,
                "generation_seconds": generation_seconds, "router_fit_seconds": fit_seconds,
                "route_application_seconds_by_split": cache_times,
                "total_population_preparation_seconds": time.perf_counter() - population_started}
            print(json.dumps({"population": name, "records": POPULATION_N, "rejected_exact_duplicates": len(redraw["rejected"]),
                              "training_route_counts": cache_counts["train"], "router_fit_seconds": fit_seconds}), flush=True)
        require(source_hashes == {name: digest(ROOT / name) for name in source_names}, "Preparation source changed during generation")
        require(len(observed_ids) == NEW_UNIQUE_EXPECTED and len(excluded) == historical_count + NEW_UNIQUE_EXPECTED, "Global novelty/ID count differs")
        # Recheck historical source bytes after all fitting without opening any outcome.
        for source in sources:
            require(digest(source["path"]) == source["sha256"] and digest(source["manifest_path"]) == source["manifest_sha256"],
                    "Historical data changed during generation")
        require(registration_path.read_bytes() == registration_raw, "Data registration changed during generation")
        seal["total_preparation_seconds"] = time.perf_counter() - started
        seal["post_generation_total_unique_features"] = len(excluded)
        seal["new_unique_record_ids"] = len(observed_ids)
        write_json(folder / "DATA_SEAL.json", seal)
        print(json.dumps({"status": "PREPARED_SEALED_NO_MODEL_OUTCOMES", "seal_sha256": digest(folder / "DATA_SEAL.json"),
                          "records": NEW_UNIQUE_EXPECTED, "historical_unique_features": historical_count,
                          "data_payloads": len(seal["files"]), "router_policies": len(seal["routers"])}), flush=True)
    except BaseException as error:
        write_json(folder / "PREPARATION_FAILURE.json", {"status": "FAIL", "created_utc": now(),
                   "error": str(error), "traceback": traceback.format_exc(), "partial_seal": seal,
                   "model_outcomes_evaluated": False, "partial_files_preserved": True})
        raise


if __name__ == "__main__":
    main()
