"""v0.7 fresh populations and train-only routing; never imports a model.

--preflight reads only historical coordinate arrays and declared input metadata.
--register records exact proposed data/source/runtime bindings.
--generate requires a separate hash-bound root DATA_GENERATION_APPROVAL.
All official data directories are exclusive, and every failure is preserved.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time
import traceback
import zipfile
import numpy as np
from routers import (canonical_features, feature_keys, feature_hashes,
                     fit_route_policy, route, fit_margin_bins, margin_bins)

ROOT = Path(__file__).resolve().parent
GOV = ROOT.parent / "governance"
EXPECTED_NUMPY = "2.5.4"
POPULATION_N = 8000
SPLIT_COUNTS = {"train": 4800, "validation": 1600, "test": 1600}
HISTORICAL_REGISTERED_EXPECTED = 264000
SOURCE_NAMES = ("prepare_data.py", "routers.py", "tests/test_routers_data.py")
OLD_ROUTER = Path(r"C:\Q2\Improvement_Study_v0.6\quantum\routers.py")
OLD_ROUTER_SHA = "0b62c0bcca42ab93551dab88e0e20828158f8a3d529253db6f0c1a5cf67a2c68"
TASK_SEMANTICS = {
    "coordinates": "Independent Uniform[-1,1]^2; no geometry or class balancing",
    "checkerboard": "sin(3*pi*x0+pi/7)*sin(3*pi*x1+pi/5)>0",
    "spiral": "sin(2*atan2(x1,x0)+4*pi*sqrt(x0*x0+x1*x1))>0",
    "annulus": "0.25<x0*x0+x1*x1<0.85; independent Bernoulli(0.10) flips on accepted-coordinate order",
    "disks": "min squared distance to(-.55,-.45),(.5,-.35),(0,.55)<.22**2",
    "boundaries": "NumPy float64 and strict inequalities; no tolerance or relabeling"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


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
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def active_inputs():
    protocol_path, matrix_path = GOV/"STUDY_PLAN.json", GOV/"RUN_MATRIX.json"
    return read_json(protocol_path), read_json(matrix_path), {
        "STUDY_PLAN.json": digest(protocol_path), "RUN_MATRIX.json": digest(matrix_path)}


def stream_value(stream):
    value = int(stream["uint128_decimal"])
    expected = int.from_bytes(hashlib.sha256(stream["namespace"].encode("ascii")).digest()[:16], "little")
    require(value == expected, "RNG namespace derivation mismatch")
    return value


def all_matrix_streams(matrix):
    out = {}
    def visit(v):
        if isinstance(v, dict):
            if "namespace" in v and "uint128_decimal" in v:
                value = stream_value(v)
                require(v["namespace"] not in out or out[v["namespace"]] == value, "Namespace changed")
                out[v["namespace"]] = value
            else:
                for x in v.values():
                    visit(x)
        elif isinstance(v, list):
            for x in v:
                visit(x)
    visit(matrix)
    require(len(out) == len(set(out.values())) == 664, "Unexpected proposed stream count/collision")
    return out


def historical_roots():
    q2 = Path(r"C:\Q2")
    roots = [("v0.1", q2/"Full_Local_Benchmark_v0.1"),
             ("v0.1_implementation", q2/"Implementation_v0.1"/"results")]
    for version in range(2, 7):
        roots.append((f"v0.{version}", q2/f"Improvement_Study_v0.{version}"))
    # Working copies may retain a population not copied into a final package.
    working = Path(r"C:\Anthony Siljeg")
    for name in ("Q2_full_benchmark_v01", *[f"Q2_improvement_study_v0{i}" for i in range(2, 7)]):
        path = working/name
        if path.exists():
            roots.append(("working_"+name, path))
    return [(version, path) for version, path in roots if path.exists()]


def _numeric_leaves(v):
    if isinstance(v, bool):
        return []
    if isinstance(v, int) and v >= 0:
        return [v]
    if isinstance(v, str) and v.isdecimal():
        return [int(v)]
    if isinstance(v, (list, tuple)):
        return [n for item in v for n in _numeric_leaves(item)]
    if isinstance(v, dict):
        return [n for item in v.values() for n in _numeric_leaves(item)]
    return []


def declared_seeds(obj):
    found = []
    def visit(v, path="", seed_context=False):
        if isinstance(v, dict):
            for key, value in v.items():
                visit(value, f"{path}/{key}", seed_context or "seed" in key.lower() or key == "proposed_streams")
        elif isinstance(v, list):
            for i, value in enumerate(v):
                visit(value, f"{path}/{i}", seed_context)
        elif seed_context:
            for n in _numeric_leaves(v):
                found.append((path, n))
    visit(obj)
    return found


def historical_inventory():
    """Read only x arrays and declared input/RNG metadata, never checkpoint arrays."""
    excluded, sources, seed_sources, seed_values = set(), [], [], set()
    registered_keys = set()
    registered_payloads = set()
    for version in range(2, 7):
        folder = Path(r"C:\Q2")/f"Improvement_Study_v0.{version}"
        seal_path = folder/"quantum/data/DATA_SEAL.json"
        seal = read_json(seal_path)
        delivery = read_json(folder/"DELIVERY_MANIFEST.json")
        inventory = {x["relative_path"].replace("\\", "/"): x for x in delivery["files"]}
        relative = "quantum/data/DATA_SEAL.json"
        require(digest(seal_path) == inventory[relative]["sha256"], f"Historical seal changed: {version}")
        for name, item in seal["files"].items():
            p = seal_path.parent/name
            require(digest(p) == item["sha256"], f"Historical payload changed: {p}")
            with np.load(p, allow_pickle=False) as payload:
                x = payload["x"]
            require(array_hash(x) == item["arrays"]["x"], "Historical coordinate-array digest changed")
            registered_keys.update(feature_keys(x))
            registered_payloads.add(str(p.resolve()).lower())
    v01 = Path(r"C:\Q2\Full_Local_Benchmark_v0.1\quantum\runs")
    for seed in range(201, 206):
        p = v01/f"seed_{seed}"/"frozen_dataset.npz"
        meta = read_json(p.with_name("data_manifest.json"))
        with np.load(p, allow_pickle=False) as payload:
            x = payload["x"]
        require(array_hash(x) == meta["hashes"]["x"], "v0.1 coordinate digest changed")
        registered_keys.update(feature_keys(x))
        registered_payloads.add(str(p.resolve()).lower())
    require(len(registered_keys) == HISTORICAL_REGISTERED_EXPECTED, "Registered historical264000 count differs")
    # Scan NPZ member names only; extract only x.npy when present and two-dimensional.
    # Output/checkpoint members are never loaded.
    npz_scanned = 0
    unreadable_npz = []
    seed_json_names = {"DATA_SEAL.json", "DATA_REGISTRATION.json", "STUDY_PLAN.json",
                       "PROTOCOL_FREEZE.json", "ANALYSIS_PROTOCOL.json", "LOCAL_READINESS_PROTOCOL.json",
                       "READINESS_PROTOCOL.json", "DEPLOYMENT_PROTOCOL.json", "STAGE_A_FREEZE.json",
                       "STAGE_B_FREEZE.json", "STAGE_A_FREEZE_PRE_RECOVERY_01.json",
                       "STAGE_B_FREEZE_PRE_RECOVERY_01.json", "data_manifest.json",
                       "PROPOSED_PROTOCOL.json", "ENGINEERING_FREEZE.json"}
    loaded_paths = set()
    for version, folder in historical_roots():
        for p in sorted(folder.rglob("*.npz")):
            if ".venv" in p.parts or "site-packages" in p.parts:
                continue
            path_key = str(p.resolve()).lower()
            if path_key in loaded_paths:
                continue
            loaded_paths.add(path_key)
            npz_scanned += 1
            try:
                with zipfile.ZipFile(p) as z:
                    has_x = "x.npy" in z.namelist()
            except zipfile.BadZipFile:
                unreadable_npz.append({"path": str(p), "bytes": p.stat().st_size,
                                       "sha256": digest(p), "reason": "not_a_valid_npz_zip",
                                       "coordinate_membership": "unreadable; requires explicit root review"})
                continue
            if not has_x:
                continue
            with np.load(p, allow_pickle=False) as payload:
                x = payload["x"]
            if x.ndim != 2 or x.shape[1] != 2:
                continue
            keys = set(feature_keys(x))
            extra = keys-registered_keys
            new_to_inventory = keys-excluded
            excluded.update(keys)
            sources.append({"version": version, "path": str(p), "sha256": digest(p),
                            "x_array_sha256": array_hash(x), "records": len(x),
                            "distinct_coordinates": len(keys), "additional_vs_registered": len(extra),
                            "new_to_inventory_in_scan_order": len(new_to_inventory),
                            "registered_payload": path_key in registered_payloads,
                            "read_scope": "x only; no labels or saved model outcomes"})
        for p in sorted(folder.rglob("*.json")):
            if p.name not in seed_json_names or ".venv" in p.parts or "site-packages" in p.parts:
                continue
            entries = declared_seeds(read_json(p))
            if entries:
                seed_values.update(n for _, n in entries)
                seed_sources.append({"path": str(p), "sha256": digest(p),
                                     "declarations": [{"json_path": key, "value": str(n)} for key, n in entries]})
        # Source constants and literal RNG calls augment declarations, including smoke/test seeds.
        for p in sorted(folder.rglob("*.py")):
            if ".venv" in p.parts or "site-packages" in p.parts:
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8-sig"))
            except (SyntaxError, UnicodeError):
                continue
            entries = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    names = [n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name)]
                    if any("seed" in name.lower() or name == "DATASETS" for name in names):
                        try:
                            value = ast.literal_eval(node.value)
                        except (ValueError, TypeError, SyntaxError):
                            continue
                        entries.extend((node.lineno, n) for n in _numeric_leaves(value))
                elif isinstance(node, ast.Call):
                    name = (node.func.attr if isinstance(node.func, ast.Attribute)
                            else node.func.id if isinstance(node.func, ast.Name) else "")
                    if name in ("PCG64", "SeedSequence", "default_rng", "seed", "manual_seed", "Random"):
                        for arg in node.args:
                            try:
                                value = ast.literal_eval(arg)
                            except (ValueError, TypeError, SyntaxError):
                                continue
                            entries.extend((node.lineno, n) for n in _numeric_leaves(value))
            if entries:
                seed_values.update(n for _, n in entries)
                seed_sources.append({"path": str(p), "sha256": digest(p),
                                     "source_literals": [{"line": line, "value": str(n)} for line, n in entries]})
    require(registered_keys.issubset(excluded), "Registered coordinates absent from complete scan")
    return excluded, {
        "schema": "qpath-v07-historical-freshness-inventory-1",
        "created_utc": now(), "source_roots": [{"version": v, "path": str(p)} for v, p in historical_roots()],
        "npz_member_inventories_scanned": npz_scanned,
        "unreadable_npz": unreadable_npz,
        "coordinate_payloads": len(sources), "coordinate_sources": sources,
        "registered_historical_unique_expected": HISTORICAL_REGISTERED_EXPECTED,
        "registered_historical_unique_observed": len(registered_keys),
        "all_available_coordinate_unique_observed": len(excluded),
        "additional_coordinates_outside_registered_inventory": len(excluded-registered_keys),
        "declared_historical_seed_value_count": len(seed_values),
        "declared_historical_seed_values": [str(n) for n in sorted(seed_values)],
        "seed_sources": seed_sources,
        "scope": "All x.npy coordinate arrays in retained v0.1-v0.6 packages, implementation results and existing study working copies; all declarations from allowlisted input/protocol files and statically literal seed/RNG arguments. Duplicate copies counted once by coordinate. NPZ checkpoint/output arrays not read.",
        "seed_scope_limit": "Not a reconstruction of every generator's internal state or arbitrary dynamically computed seed expression. Declared source seeds and retained input metadata are inventoried; new128bit namespace streams additionally have new role/population identities.",
        "outcomes_read": False
    }


def _allocate(counts, fraction, target):
    exact = np.asarray(counts)*fraction
    result = np.floor(exact).astype(np.int64)
    remainder = target-int(result.sum())
    require(0 <= remainder <= len(counts), "Invalid largest-remainder allocation")
    order = sorted(range(len(counts)), key=lambda k: (-(exact[k]-result[k]), k))
    for k in order[:remainder]:
        result[k] += 1
    require(int(result.sum()) == target, "Allocation target mismatch")
    return result


def labels_for(x, task):
    x = canonical_features(x)
    if task == "checkerboard":
        p = np.sin(3*np.pi*x[:, 0]+np.pi/7)*np.sin(3*np.pi*x[:, 1]+np.pi/5) > 0
    elif task == "spiral":
        p = np.sin(2*np.arctan2(x[:, 1], x[:, 0])+4*np.pi*np.sqrt(x[:, 0]**2+x[:, 1]**2)) > 0
    elif task == "annulus":
        r2 = x[:, 0]**2+x[:, 1]**2
        p = (r2 > .25) & (r2 < .85)
    elif task == "disks":
        centers = np.asarray([[-.55, -.45], [.5, -.35], [0., .55]])
        p = np.sum((x[:, None, :]-centers[None, :, :])**2, axis=2).min(axis=1) < .22**2
    else:
        raise ValueError("Unregistered family")
    return p.astype(np.int64)


def generate(population, excluded, record_base, *, n=POPULATION_N, counts=None):
    """Same-stream exact exclusion; no model or official-directory writes."""
    counts = SPLIT_COUNTS if counts is None else counts
    require(sum(counts.values()) == n and set(counts) == {"train", "validation", "test"}, "Split schema mismatch")
    streams = population["proposed_streams"]
    seed = lambda role: stream_value(streams[role])
    require(record_base >= 0 and record_base+n < 2**63, "Record-ID overflow")
    rng = np.random.Generator(np.random.PCG64(seed("coordinates")))
    accepted, draw_ids, rejected, seen = [], [], [], set()
    consumed = 0
    while len(accepted) < n:
        candidates = canonical_features(rng.uniform(-1, 1, (n-len(accepted), 2)))
        for candidate in candidates:
            key = candidate.tobytes()
            if key in excluded or key in seen:
                rejected.append({"draw_index": consumed, "feature_sha256": hashlib.sha256(key).hexdigest(),
                                 "reason": "historical_or_earlier_population" if key in excluded else "within_population"})
            else:
                accepted.append(candidate)
                draw_ids.append(consumed)
                seen.add(key)
            consumed += 1
        require(consumed <= 1000000, "Exact-exclusion maximumdraw limit; no replacement seed")
    x = canonical_features(accepted)
    clean = labels_for(x, population["family"])
    flips = (np.random.Generator(np.random.PCG64(seed("annulus_noise"))).random(n) < .1
             if population["family"] == "annulus" else np.zeros(n, dtype=np.bool_))
    y = clean ^ flips.astype(np.int64)
    ids = record_base+np.random.Generator(np.random.PCG64(seed("record_ids"))).permutation(n).astype(np.int64)
    draws = np.asarray(draw_ids, dtype=np.int64)
    split_rng = np.random.Generator(np.random.PCG64(seed("split")))
    groups = [split_rng.permutation(np.flatnonzero(y == value)) for value in (0, 1)]
    class_counts = [len(group) for group in groups]
    train_n = _allocate(class_counts, counts["train"]/n, counts["train"])
    val_n = _allocate(class_counts, counts["validation"]/n, counts["validation"])
    member = {name: [] for name in counts}
    for group, a, b in zip(groups, train_n, val_n):
        require(a+b <= len(group), "Strata overlap")
        member["train"].extend(group[:a]); member["validation"].extend(group[a:a+b])
        member["test"].extend(group[a+b:])
    parts, latent = {}, {}
    for split in ("train", "validation", "test"):
        idx = split_rng.permutation(np.asarray(member[split], dtype=np.int64))
        require(len(idx) == counts[split], "Split count mismatch")
        parts[split] = {"x": x[idx], "y": y[idx], "ids": ids[idx], "source_draw_ids": draws[idx]}
        latent[split] = {"ids": ids[idx], "clean_y": clean[idx], "label_flip": flips[idx]}
    return parts, latent, {"draws_consumed": consumed, "accepted": n, "rejected": rejected,
                          "stratum_counts": class_counts, "train_stratum_counts": train_n.tolist(),
                          "validation_stratum_counts": val_n.tolist()}, seen


def validate_registration(registration, protocol, matrix, protocol_hashes):
    require(registration["status"] == "SOURCE_REVIEW_READY_REQUIRES_ROOT_GENERATION_APPROVAL", "Registration status")
    require(registration["active_input_sha256"] == protocol_hashes, "Active study inputs changed")
    require(registration["population_order"] == [p["population_id"] for p in matrix["populations"]], "Population order changed")
    require(registration["source_sha256"] == {name: digest(ROOT/name) for name in SOURCE_NAMES}, "Data source changed")
    require(registration["numpy_version"] == np.__version__ == EXPECTED_NUMPY, "Numerical runtime differs")
    require(registration["population_n"] == POPULATION_N and registration["split_counts"] == SPLIT_COUNTS, "Data budget differs")
    require(registration["task_semantics"] == TASK_SEMANTICS, "Task semantics differ")
    require(registration["record_id_base"] == 7000000000000000000, "Record-ID base differs")
    require(len(matrix["populations"]) == 40 and len(matrix["runs"]) == 608, "Matrix extent differs")
    all_matrix_streams(matrix)


def validate_generation_approval(approval, registration_hash, active_hashes, source_hashes, unreadable=()):
    require(approval.get("status") == "approved_by_root", "Separate root generation approval required")
    require(approval.get("registration_sha256") == registration_hash, "Approval registration changed")
    require(approval.get("source_sha256") == source_hashes, "Approval source changed")
    require(approval.get("active_input_sha256") == active_hashes, "Approval study protocol/matrix changed")
    require(approval.get("freshness_preflight_sha256") == digest(GOV/"HISTORICAL_FRESHNESS_PREFLIGHT.json"), "Approval freshness changed")
    if unreadable:
        required = sorted({item["sha256"] for item in unreadable})
        require(approval.get("historical_nondata_stub_hashes") == required,
                "Root must explicitly classify all unreadable historical NPZ byte identities as non-data stubs")


def preflight():
    require(np.__version__ == EXPECTED_NUMPY, "Use historical scientific NumPy runtime")
    protocol, matrix, hashes = active_inputs()
    streams = all_matrix_streams(matrix)
    _, inventory = historical_inventory()
    historical_values = {int(v) for v in inventory["declared_historical_seed_values"]}
    collisions = [{"namespace": name, "value": str(value)} for name, value in streams.items() if value in historical_values]
    require(not collisions, "Proposed stream collides with declared historical value")
    inventory.update({"status": "PASS_READ_ONLY_FRESHNESS_PREFLIGHT_NO_DATA_GENERATED",
                      "active_input_sha256": hashes, "numpy_version": np.__version__,
                      "new_stream_count": len(streams), "historical_stream_value_collisions": collisions,
                      "all_new_coordinates_must_be_excluded_against": inventory["all_available_coordinate_unique_observed"]})
    if inventory["unreadable_npz"]:
        inventory["status"] = "REVIEW_REQUIRED_UNREADABLE_HISTORICAL_NPZ_NO_DATA_GENERATED"
    write_json(GOV/"HISTORICAL_FRESHNESS_PREFLIGHT.json", inventory)
    print(json.dumps({k: inventory[k] for k in ("status", "coordinate_payloads", "registered_historical_unique_observed",
                                             "all_available_coordinate_unique_observed", "additional_coordinates_outside_registered_inventory",
                                             "declared_historical_seed_value_count")}))


def registration():
    protocol, matrix, hashes = active_inputs()
    inventory = read_json(GOV/"HISTORICAL_FRESHNESS_PREFLIGHT.json")
    require(inventory["active_input_sha256"] == hashes, "Preflight active inputs changed")
    require(digest(OLD_ROUTER) == OLD_ROUTER_SHA, "Historical router source changed")
    record = {
        "schema": "qpath-v07-data-registration-1", "created_utc": now(),
        "status": "SOURCE_REVIEW_READY_REQUIRES_ROOT_GENERATION_APPROVAL",
        "active_input_sha256": hashes, "source_sha256": {n: digest(ROOT/n) for n in SOURCE_NAMES},
        "freshness_preflight_sha256": digest(GOV/"HISTORICAL_FRESHNESS_PREFLIGHT.json"),
        "numpy_version": EXPECTED_NUMPY, "python_version": platform.python_version(),
        "population_n": POPULATION_N, "split_counts": SPLIT_COUNTS, "new_coordinate_count": 320000,
        "population_order": [p["population_id"] for p in matrix["populations"]],
        "record_id_base": 7000000000000000000,
        "record_id_rule": "base7000000000000000000 + population_ordinal_zero_based*1000000 + PCG64(record_ids stream).permutation(8000), int64",
        "task_semantics": TASK_SEMANTICS,
        "historical_unique_observed": inventory["all_available_coordinate_unique_observed"],
        "registered_history_expected_and_observed": HISTORICAL_REGISTERED_EXPECTED,
        "historical_additional_coordinates": inventory["additional_coordinates_outside_registered_inventory"],
        "unreadable_historical_npz": inventory["unreadable_npz"],
        "historical_router": {"path": str(OLD_ROUTER), "sha256": OLD_ROUTER_SHA,
                             "kmeans_algorithm": "unchanged source functions _distance,_canonical_order,_initial_centers,_lloyd;20restarts500iterations; minimum eligible inertia/canonicalcentroids/restart"},
        "router_changes": "Explicit independent kmeans/hash streams; v07 domain salt; training-only margin quantiles. No labels or record IDs enter router.",
        "hash_salt_rule": "ASCII qpath-v07-population-hash- followed by decimal value of matrix hash_salt stream",
        "margin_rule": "dsecond^2-dnearest^2; training linear quantiles[0,.1,.25,.5,1], unique edges, side=right interior cutpoints, outer bins cover beyond training range",
        "split_rule": "Observed-label largest remainder, train.6/validation.2 independently with ties label0; test remainder; split-stream label0,label1 then train,validation,test shuffles.",
        "latent_rule": "clean_y/label_flip held only in separate SEALED_diagnostics.npz; training files contain observed y only. Diagnostics access forbidden until root evaluation release.",
        "exclusion_rule": "Same coordinate PCG64 stream; exact historical/new duplicate rejection in draw order, draw only remaining count;1000000draw abort; no alternative seed search.",
        "collision_rule": "Distinct-coordinate SHA256 hash collision anywhere within population aborts preparation, no salt replacement; duplicatecoordinates rejected upstream; ambiguous cutpoints abort.",
        "failure_rule": "Exclusive new data directory, preserve partial files and PREPARATION_FAILURE.json; no auto retry, replacement population, overwritten outcomes or silent reselection."
    }
    validate_registration(record, protocol, matrix, hashes)
    write_json(GOV/"DATA_REGISTRATION.json", record)
    print(json.dumps({"status": record["status"], "registration_sha256": digest(GOV/"DATA_REGISTRATION.json"),
                      "source_sha256": record["source_sha256"]}))


def validate_historical_rescan(historical, previous, registration, unique_count):
    require(unique_count == registration["historical_unique_observed"], "Historical coordinate universe changed after preflight")
    require(historical["coordinate_sources"] == previous["coordinate_sources"], "Historical payload identities changed")
    require(historical["seed_sources"] == previous["seed_sources"], "Historical declared RNG sources changed")
    require(historical["unreadable_npz"] == previous["unreadable_npz"] == registration["unreadable_historical_npz"],
            "Historical non-data stub inventory changed after explicit root review")


def official_generation():
    started = time.perf_counter()
    folder = ROOT/"data"
    require(not folder.exists(), "Official data directory already exists; preserve and reconcile, do not rerun")
    protocol, matrix, active_hashes = active_inputs()
    reg_path, approval_path = GOV/"DATA_REGISTRATION.json", GOV/"DATA_GENERATION_APPROVAL.json"
    reg_raw, approval_raw = reg_path.read_bytes(), approval_path.read_bytes()
    reg = json.loads(reg_raw)
    validate_registration(reg, protocol, matrix, active_hashes)
    source_hashes = {n: digest(ROOT/n) for n in SOURCE_NAMES}
    validate_generation_approval(json.loads(approval_raw), digest(reg_path), active_hashes, source_hashes,
                                 reg["unreadable_historical_npz"])
    excluded, historical = historical_inventory()
    previous = read_json(GOV/"HISTORICAL_FRESHNESS_PREFLIGHT.json")
    validate_historical_rescan(historical, previous, reg, len(excluded))
    folder.mkdir()
    seal = {"schema": "qpath-v07-data-seal-1", "created_utc": now(), "status": "sealed before training",
            "study_id": protocol["study_id"], "outcomes_evaluated": False, "numpy_version": np.__version__,
            "source_sha256": source_hashes, "active_input_sha256": active_hashes,
            "registration_sha256": digest(reg_path), "generation_approval_sha256": digest(approval_path),
            "freshness_preflight_sha256": digest(GOV/"HISTORICAL_FRESHNESS_PREFLIGHT.json"),
            "historical_unique_features": len(excluded), "historical_sources": historical["coordinate_sources"],
            "historical_source_verification_seconds": time.perf_counter()-started,
            "record_id_rule": reg["record_id_rule"], "latent_rule": reg["latent_rule"],
            "population_order": reg["population_order"], "datasets": {}, "files": {}, "routers": {}, "diagnostics": {}}
    all_ids = set()
    try:
        for ordinal, pop in enumerate(matrix["populations"]):
            name = pop["population_id"]
            t0 = time.perf_counter()
            parts, latent, redraw, keys = generate(pop, excluded, reg["record_id_base"]+ordinal*1000000)
            require(keys.isdisjoint(excluded), "Freshness breach")
            excluded.update(keys)
            gen_seconds = time.perf_counter()-t0
            all_x = np.concatenate([parts[s]["x"] for s in ("train", "validation", "test")])
            salt = "qpath-v07-population-hash-"+str(stream_value(pop["proposed_streams"]["hash_salt"]))
            hashes = feature_hashes(all_x, salt)
            require(len(set(hashes)) == len(hashes), "Population feature hash collision; preserve failure")
            fit0 = time.perf_counter()
            kmeans_seed = stream_value(pop["proposed_streams"]["kmeans_initialization"])
            policy = fit_route_policy(parts["train"]["x"], kmeans_seed, salt)
            fit_seconds = time.perf_counter()-fit0
            policy["population"] = name
            policy["training_ids_array_sha256"] = array_hash(parts["train"]["ids"])
            policy["margin_bins"] = fit_margin_bins(parts["train"]["x"], policy)
            router_path = folder/f"{name}_router.json"
            write_json(router_path, policy)
            router_sha = digest(router_path)
            seal["routers"][name] = {"file": router_path.name, "sha256": router_sha, "seed": kmeans_seed,
                                    "training_n": SPLIT_COUNTS["train"], "fit_seconds": fit_seconds,
                                    "fit_scope": "Training rawx only; all methods/seeds share geometric/hash policy"}
            cache_times, cache_counts = {}, {}
            latent_payload = {}
            for split, part in parts.items():
                require(set(part).isdisjoint({"clean_y", "label_flip"}), "Latent data leaked into training")
                require(set(part["ids"]).isdisjoint(all_ids), "New record IDs overlap")
                all_ids.update(part["ids"].tolist())
                cache_times[split], cache_counts[split] = {}, {}
                for kind in ("hash", "kmeans"):
                    tc = time.perf_counter()
                    part[kind+"_route"] = route(part["x"], policy, kind)
                    cache_times[split][kind] = time.perf_counter()-tc
                    cache_counts[split][kind] = np.bincount(part[kind+"_route"], minlength=5).tolist()
                part["margin_bin"] = margin_bins(part["x"], policy, policy["margin_bins"])
                for key, value in latent[split].items():
                    latent_payload[f"{split}_{key}"] = value
                fn = f"{name}_{'SEALED_test' if split == 'test' else split}.npz"
                path = folder/fn
                with path.open("xb") as f:
                    np.savez(f, **part)
                seal["files"][fn] = {"sha256": digest(path), "arrays": {k: array_hash(v) for k, v in part.items()},
                                    "n": len(part["x"]), "dataset": name, "task": pop["family"],
                                    "split": split, "router_policy_sha256": router_sha}
            require(cache_counts["train"]["hash"] == cache_counts["train"]["kmeans"], "Hash trainingoccupancy differs")
            diagnostic_path = folder/f"{name}_SEALED_diagnostics.npz"
            with diagnostic_path.open("xb") as f:
                np.savez(f, **latent_payload)
            seal["diagnostics"][name] = {"file": diagnostic_path.name, "sha256": digest(diagnostic_path),
                                         "arrays": {k: array_hash(v) for k, v in latent_payload.items()},
                                         "access": "FORBIDDEN_UNTIL_ROOT_TEST_RELEASE"}
            seal["datasets"][name] = {"task": pop["family"], "stage": pop["stage"],
                                     "population_index": pop["population_index"],
                                     "proposed_streams": pop["proposed_streams"],
                                     "counts": dict(SPLIT_COUNTS),
                                     "label_counts": {s: np.bincount(p["y"], minlength=2).tolist() for s, p in parts.items()},
                                     "redraw": redraw, "route_counts": cache_counts,
                                     "generation_seconds": gen_seconds, "router_fit_seconds": fit_seconds,
                                     "route_application_seconds_by_split": cache_times,
                                     "total_population_preparation_seconds": time.perf_counter()-t0}
            print(json.dumps({"population": name, "records": 8000, "rejected": len(redraw["rejected"]),
                              "router_seconds": fit_seconds}), flush=True)
        require(len(all_ids) == 320000 and len(excluded) == reg["historical_unique_observed"]+320000, "Freshness/ID finalcount")
        require(source_hashes == {n: digest(ROOT/n) for n in SOURCE_NAMES}, "Data source changed during generation")
        require(reg_path.read_bytes() == reg_raw and approval_path.read_bytes() == approval_raw, "Generation authority changed")
        require(active_inputs()[2] == active_hashes, "Active study inputs changed during generation")
        for item in historical["coordinate_sources"]:
            require(digest(item["path"]) == item["sha256"], "Historical coordinate payload changed")
        seal["new_unique_record_ids"] = len(all_ids)
        seal["post_generation_total_unique_features"] = len(excluded)
        seal["total_preparation_seconds"] = time.perf_counter()-started
        write_json(folder/"DATA_SEAL.json", seal)
        print(json.dumps({"status": "PREPARED_SEALED_NO_MODEL_OUTCOMES", "seal_sha256": digest(folder/"DATA_SEAL.json"),
                          "populations": 40, "records": 320000, "files": len(seal["files"]),
                          "diagnostics": len(seal["diagnostics"])}), flush=True)
    except BaseException as error:
        write_json(folder/"PREPARATION_FAILURE.json", {"created_utc": now(), "error": repr(error),
                   "traceback": traceback.format_exc(), "partial_seal": seal, "partial_files_preserved": True})
        raise


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--register", action="store_true")
    mode.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        preflight()
    elif args.register:
        registration()
    else:
        official_generation()


if __name__ == "__main__":
    main()
