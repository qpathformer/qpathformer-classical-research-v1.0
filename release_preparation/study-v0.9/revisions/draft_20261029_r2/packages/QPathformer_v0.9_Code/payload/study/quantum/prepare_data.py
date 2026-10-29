"""v0.9 fresh populations and train-only routing; never imports a model.

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
import os
import sys
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[_key]='1'
import numpy as np
from routers import (canonical_features, feature_keys, preprocess, fit_preprocessing,
                     fit_route_policy, route, fit_margin_bins, margin_bins)

ROOT = Path(__file__).resolve().parent
GOV = ROOT.parent / "governance"
EXPECTED_NUMPY = "2.5.4"
POPULATION_N = 8000
SPLIT_COUNTS = {"train": 4800, "validation": 1600, "test": 1600}
HISTORICAL_REGISTERED_EXPECTED = 904000
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
    require(len(out) == len(set(out.values())) == matrix["unique_proposed_stream_count"], "Unexpected proposed stream count/collision")
    return out


def historical_roots():
    q2 = Path(r"C:\Q2")
    roots = [("v0.1", q2/"Full_Local_Benchmark_v0.1"),
             ("v0.1_implementation", q2/"Implementation_v0.1"/"results")]
    for version in range(2, 9):
        roots.append((f"v0.{version}", q2/f"Improvement_Study_v0.{version}"))
    # Working copies may retain a population not copied into a final package.
    working = Path(r"C:\Anthony Siljeg")
    for name in ("Q2_full_benchmark_v01", *[f"Q2_improvement_study_v0{i}" for i in range(2, 9)]):
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
                visit(value, f"{path}/{key}", seed_context or "seed" in key.lower() or key in ("proposed_streams", "paired_streams"))
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
    for version in range(2, 9):
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
    require(len(registered_keys) == HISTORICAL_REGISTERED_EXPECTED, "Registered historical904000 count differs")
    # Scan NPZ member names only; extract only x.npy when present and two-dimensional.
    # Output/checkpoint members are never loaded.
    npz_scanned = 0
    unreadable_npz = []
    seed_json_names = {"DATA_SEAL.json", "DATA_REGISTRATION.json", "STUDY_PLAN.json",
                       "PROTOCOL_FREEZE.json", "ANALYSIS_PROTOCOL.json", "LOCAL_READINESS_PROTOCOL.json",
                       "READINESS_PROTOCOL.json", "DEPLOYMENT_PROTOCOL.json", "STAGE_A_FREEZE.json",
                       "STAGE_B_FREEZE.json", "STAGE_A_FREEZE_PRE_RECOVERY_01.json",
                       "STAGE_B_FREEZE_PRE_RECOVERY_01.json", "data_manifest.json",
                       "PROPOSED_PROTOCOL.json", "ENGINEERING_FREEZE.json", "RUN_MATRIX.json"}
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
        "schema": "qpath-v09-historical-freshness-inventory-1",
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
        "scope": "All x.npy coordinate arrays in retained v0.1-v0.8 packages, implementation results and existing study working copies; all declarations from allowlisted input/protocol files and statically literal seed/RNG arguments. Duplicate copies counted once by coordinate. NPZ checkpoint/output arrays not read.",
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


RAW_NAME='data_banknote_authentication.txt'
RAW_SHA='d0539aaed2139ba7a587b3e34fb345ce503ff7d5d33dbf9912d8e195ce425cb9'
RECORD_BASE=9000000000000000000
GROUP_SPLIT_RULE=('Group identical canonical little-endian float64 four-feature vectors irrespective of label. '
 'Sort keys lexicographically, PCG64(split stream) permute groups, stable sort decreasing group size. '
 'Assign each whole group to split minimizing marginal sum over classes of (observed-target)^2/target, '
 'with targets .6/.2/.2 times global class counts; ties train,validation,test. '
 'Shuffle record order within each split using the continued split RNG. No split search or outcome selection.')


def raw4_keys(x):
    a=np.array(x,dtype='<f8',order='C',copy=True)
    require(a.ndim==2 and a.shape[1]==4 and np.isfinite(a).all(),'Expected raw four-feature coordinates')
    a[a==0]=0.
    return [r.tobytes() for r in a]


def load_banknote():
    path=ROOT/'raw'/RAW_NAME
    require(digest(path)==RAW_SHA,'Banknote raw source changed')
    a=np.loadtxt(path,delimiter=',',dtype=np.float64)
    require(a.shape==(1372,5) and np.isfinite(a).all(),'Banknote source schema differs')
    require(set(a[:,4])=={0.,1.},'Banknote labels differ')
    return a[:,:4],a[:,4].astype(np.int64)


def grouped_split(raw_x,y,seed):
    """One outcome-independent grouped stratified split; no model or directory I/O."""
    keys=raw4_keys(raw_x);y=np.asarray(y,dtype=np.int64)
    require(len(keys)==len(y) and set(y)<= {0,1},'Invalid grouping labels')
    groups={}
    for i,key in enumerate(keys):groups.setdefault(key,[]).append(i)
    rng=np.random.Generator(np.random.PCG64(seed))
    canonical=sorted(groups);ordered=[canonical[i] for i in rng.permutation(len(canonical))]
    ordered.sort(key=lambda k:-len(groups[k]))
    totals=np.bincount(y,minlength=2)
    require(np.all(totals>0),'Both classes required')
    targets=np.array([.6,.2,.2])[:,None]*totals[None,:]
    current=np.zeros((3,2),dtype=np.int64);members=[[],[],[]]
    for key in ordered:
        idx=groups[key];g=np.bincount(y[idx],minlength=2)
        delta=np.sum((2*(current-targets)*g+g*g)/targets,axis=1)
        split=int(np.argmin(delta));members[split].extend(idx);current[split]+=g
    indices={name:rng.permutation(np.asarray(idx,dtype=np.int64)) for name,idx in zip(SPLIT_COUNTS,members)}
    require(all(len(idx)>0 for idx in indices.values()),'Empty group split')
    seen=set()
    for idx in indices.values():
        splitkeys={keys[i] for i in idx};require(seen.isdisjoint(splitkeys),'Feature group crosses splits');seen.update(splitkeys)
    conflicts=[{'feature_sha256':hashlib.sha256(k).hexdigest(),'rows':v,'label_counts':np.bincount(y[v],minlength=2).tolist()} for k,v in sorted(groups.items()) if len(set(y[v]))>1]
    return indices,{'rule':GROUP_SPLIT_RULE,'raw_rows':len(y),'unique_feature_groups':len(groups),'duplicate_groups':sum(len(v)>1 for v in groups.values()),'duplicate_extra_rows':sum(len(v)-1 for v in groups.values()),'conflicting_groups':conflicts,'counts':{k:len(v) for k,v in indices.items()},'label_counts':{k:np.bincount(y[v],minlength=2).tolist() for k,v in indices.items()},'indices_sha256':{k:array_hash(v) for k,v in indices.items()},'source_row_index_base':0,'known_limit':'No specimen/capture-session IDs; identical-vector grouping does not establish source independence.'}


def historical_banknote_inventory():
    """Check retained input paths/raw four-feature rows only, not model outcomes."""
    raw,_=load_banknote();newkeys=set(raw4_keys(raw));sources=[];named=[];overlap=set();seen=set();excluded_headers=[]
    for version,folder in historical_roots():
        for p in sorted(folder.rglob('*banknote*')):
            if p.is_file():named.append({'path':str(p),'sha256':digest(p),'bytes':p.stat().st_size})
        for p in sorted(folder.rglob('*.npz')):
            if str(p).lower() in seen:continue
            seen.add(str(p).lower())
            try:
                with zipfile.ZipFile(p) as z:members=set(z.namelist())
            except zipfile.BadZipFile:continue
            for name in ['x','raw_x']:
                if name+'.npy' not in members:continue
                with zipfile.ZipFile(p) as z:
                    with z.open(name+'.npy') as member:
                        version=np.lib.format.read_magic(member)
                        require(version in [(1,0),(2,0)],'Unsupported historical NPY header version; review explicitly')
                        reader=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
                        shape,fortran,dtype=reader(member)
                if len(shape)!=2 or shape[1]!=4:continue
                if dtype.hasobject or not np.issubdtype(dtype,np.number):
                    excluded_headers.append({'path':str(p),'array':name,'shape':list(shape),'dtype':str(dtype),'sha256':digest(p),'reason':'Non-numeric/object input field cannot be a retained finite float64 four-feature Banknote array; values not loaded.'})
                    continue
                with np.load(p,allow_pickle=False) as f:a=f[name]
                if a.ndim==2 and a.shape[1]==4:
                    keys=set(raw4_keys(a));matches=newkeys&keys;overlap.update(matches)
                    sources.append({'path':str(p),'array':name,'sha256':digest(p),'array_sha256':array_hash(a),'n':len(a),'matching_unique_raw_feature_rows':len(matches)})
    return {'schema':'qpath-v09-banknote-history-1','created_utc':now(),'named_files':named,'four_feature_input_arrays':sources,'excluded_non_numeric_four_column_headers':excluded_headers,'matching_unique_raw_feature_rows':len(overlap),'scope':'Retained study roots v0.1-v0.8; paths containing banknote and numeric input x/raw_x arrays with four columns. Object fields were not loaded. No unknown encodings/inaccessible historical sources claimed.','status':'PASS_NO_RETAINED_PRIOR_BANKNOTE_INPUT_FOUND' if not named and not overlap else 'REVIEW_REQUIRED_PRIOR_POSSIBLE_BANKNOTE','outcomes_read':False}


def preflight():
    require(np.__version__==EXPECTED_NUMPY,'Use retained scientific runtime')
    _,matrix,hashes=active_inputs();streams=all_matrix_streams(matrix)
    _,inventory=historical_inventory()
    old={int(v) for v in inventory['declared_historical_seed_values']}
    collisions=[n for n,v in streams.items() if v in old]
    require(not collisions,'New streams overlap declared old values')
    inventory.update({'status':'REVIEW_REQUIRED_UNREADABLE_HISTORICAL_NPZ_NO_DATA_GENERATED' if inventory['unreadable_npz'] else 'PASS_READ_ONLY_FRESHNESS_PREFLIGHT_NO_DATA_GENERATED','active_input_sha256':hashes,'new_stream_count':len(streams),'historical_stream_value_collisions':collisions,'numpy_version':np.__version__})
    write_json(GOV/'HISTORICAL_FRESHNESS_PREFLIGHT.json',inventory)
    banknote=historical_banknote_inventory();write_json(GOV/'BANKNOTE_HISTORICAL_PRESENCE.json',banknote)
    print(json.dumps({'status':inventory['status'],'registered_unique':inventory['registered_historical_unique_observed'],'all_available_unique':inventory['all_available_coordinate_unique_observed'],'banknote':banknote['status']}))


def data_source_hashes():
    return {name:digest(ROOT/name) for name in (*SOURCE_NAMES,'raw/'+RAW_NAME,'raw/SOURCE.json')}


def registration():
    _,matrix,hashes=active_inputs();inventory=read_json(GOV/'HISTORICAL_FRESHNESS_PREFLIGHT.json')
    require(inventory['active_input_sha256']==hashes,'Preflight authority changed')
    require(digest(OLD_ROUTER)==OLD_ROUTER_SHA,'Historical inherited router changed')
    record={'schema':'qpath-v09-data-registration-1','created_utc':now(),'status':'SOURCE_REVIEW_READY_REQUIRES_ROOT_GENERATION_APPROVAL','active_input_sha256':hashes,'source_sha256':data_source_hashes(),'freshness_preflight_sha256':digest(GOV/'HISTORICAL_FRESHNESS_PREFLIGHT.json'),'banknote_history_sha256':digest(GOV/'BANKNOTE_HISTORICAL_PRESENCE.json'),'numpy_version':EXPECTED_NUMPY,'python_version':platform.python_version(),'population_n':8000,'split_counts':SPLIT_COUNTS,'new_synthetic_coordinate_count':320000,'population_order':[p['population_id'] for p in matrix['populations']],'record_id_base':RECORD_BASE,'record_id_rule':'base9e18 + populationOrdinal*1000000 + independentPCG64(record_ids).permutation(n),int64; Banknote uniqueIDs same across E/B','task_semantics':TASK_SEMANTICS,'historical_unique_observed':inventory['all_available_coordinate_unique_observed'],'registered_history_expected_and_observed':HISTORICAL_REGISTERED_EXPECTED,'unreadable_historical_npz':inventory['unreadable_npz'],'synthetic_split_rule':'Observed-label largest-remainder train.6 and val.2, testremainder; label0tie; same splitRNG permutations.','banknote_source_sha256':RAW_SHA,'banknote_split_rule':GROUP_SPLIT_RULE,'banknote_preprocessing':'Train-only populationSTD4(ddof0,constant1),centerstandardized4,SVDtop2,largestabsloadingpositive(lowestindex tie),standardizePC2(ddof0,constant1),2/pi arctan; MLP4standardize4/arctan noPCA.','router':'Inheritedkmeans20restart500iter,trainonly; tau=max(.001,medianmargin); residualmonomialscale=max(1,maxabs(train))','margin_rule':'Traininglinearquantiles[0,.1,.25,.5,1],uniqueedges,side=right;commonfixedbinsallarms','exclusion_rule':'Exactcanonicalcoordinate rejectionagainstoldandearliernew,continue sameRNGdrawstream;1milliondrawabort;nofavourableseedsearch','latent_rule':'clean_y/fliponlyseparateSEALED_diagnostics;nosuchfieldsintrain/validation','failure_rule':'Exclusiveoutputcreation,preservepartialdata/PREPARATION_FAILURE,noautomaticrerun'}
    validate_registration(record,matrix,hashes);write_json(GOV/'DATA_REGISTRATION.json',record)
    print(json.dumps({'status':record['status'],'sha256':digest(GOV/'DATA_REGISTRATION.json')}))


def validate_registration(reg,matrix,hashes):
    require(reg['status']=='SOURCE_REVIEW_READY_REQUIRES_ROOT_GENERATION_APPROVAL','Invalid registration status')
    require(reg['source_sha256']==data_source_hashes(),'Data source bindings changed')
    require(reg['active_input_sha256']==hashes,'Protocol or matrix changed')
    require(reg['population_order']==[p['population_id'] for p in matrix['populations']],'Population order changed')
    require(reg['record_id_base']==RECORD_BASE and reg['population_n']==8000 and reg['split_counts']==SPLIT_COUNTS,'Data budget/identity changed')
    require(len(matrix['populations'])==41 and len(matrix['runs'])==756,'Matrix extent changed')
    require(reg['numpy_version']==np.__version__==EXPECTED_NUMPY,'Runtime changed')
    require(reg['task_semantics']==TASK_SEMANTICS and reg['banknote_split_rule']==GROUP_SPLIT_RULE,'Data semantics changed')
    all_matrix_streams(matrix)


def validate_generation_approval(a,reg,hashes):
    require(a.get('status')=='approved_by_root','Root generation approval required')
    require(a.get('registration_sha256')==digest(GOV/'DATA_REGISTRATION.json'),'Registration approval mismatch')
    require(a.get('source_sha256')==data_source_hashes() and a.get('active_input_sha256')==hashes,'Source/active approval mismatch')
    require(a.get('freshness_preflight_sha256')==reg['freshness_preflight_sha256']==digest(GOV/'HISTORICAL_FRESHNESS_PREFLIGHT.json'),'Freshness approval mismatch')
    require(a.get('banknote_history_sha256')==reg['banknote_history_sha256']==digest(GOV/'BANKNOTE_HISTORICAL_PRESENCE.json'),'Banknote history approval mismatch')
    require(read_json(GOV/'BANKNOTE_HISTORICAL_PRESENCE.json')['status']=='PASS_NO_RETAINED_PRIOR_BANKNOTE_INPUT_FOUND','Banknote previously used or presence unresolved')
    required=sorted({x['sha256'] for x in reg['unreadable_historical_npz']})
    require(a.get('historical_nondata_stub_hashes',[])==required,'Unreadable historical stubs need exact root classification')


def official_generation():
    started=time.perf_counter();folder=ROOT/'data'
    require(not folder.exists(),'Official data already exists; preserve/reconcile, never rerun')
    protocol,matrix,hashes=active_inputs();reg=read_json(GOV/'DATA_REGISTRATION.json')
    validate_registration(reg,matrix,hashes);approval=read_json(GOV/'DATA_GENERATION_APPROVAL.json');validate_generation_approval(approval,reg,hashes)
    excluded,historical=historical_inventory();previous=read_json(GOV/'HISTORICAL_FRESHNESS_PREFLIGHT.json')
    require(historical['coordinate_sources']==previous['coordinate_sources'] and historical['seed_sources']==previous['seed_sources'] and historical['unreadable_npz']==previous['unreadable_npz'],'Historical inventory changed')
    require(len(excluded)==reg['historical_unique_observed'],'Historical coordinate universe changed')
    source_hashes=data_source_hashes();authority={n:digest(GOV/n) for n in ['DATA_REGISTRATION.json','DATA_GENERATION_APPROVAL.json']}
    folder.mkdir();allids=set();synthetic_count=0
    seal={'schema':'qpath-v09-data-seal-1','created_utc':now(),'status':'sealed before training','study_id':protocol['study_id'],'outcomes_evaluated':False,'numpy_version':np.__version__,'source_sha256':source_hashes,'active_input_sha256':hashes,'registration_sha256':authority['DATA_REGISTRATION.json'],'generation_approval_sha256':authority['DATA_GENERATION_APPROVAL.json'],'freshness_preflight_sha256':reg['freshness_preflight_sha256'],'historical_unique_features':len(excluded),'historical_sources':historical['coordinate_sources'],'datasets':{},'files':{},'routers':{},'diagnostics':{}}
    try:
        for ordinal,pop in enumerate(matrix['populations']):
            t0=time.perf_counter();name=pop['population_id'];base=RECORD_BASE+ordinal*1000000
            if pop['family']=='banknote':
                raw,y=load_banknote();indices,metadata=grouped_split(raw,y,stream_value(pop['proposed_streams']['split']))
                ids=base+np.random.Generator(np.random.PCG64(stream_value(pop['proposed_streams']['record_ids']))).permutation(len(y)).astype(np.int64)
                prep=fit_preprocessing(raw[indices['train']]);parts={};latent={}
                for split,idx in indices.items():parts[split]={'raw_x':raw[idx],'x':preprocess(raw[idx],prep,2),'x4':preprocess(raw[idx],prep,4),'y':y[idx],'ids':ids[idx],'source_row_indices':idx}
            else:
                parts,latent,metadata,keys=generate(pop,excluded,base)
                require(keys.isdisjoint(excluded),'Freshness breach');excluded.update(keys);synthetic_count+=len(keys)
                prep={'kind':'identity2'}
            fit0=time.perf_counter();policy=fit_route_policy(parts['train']['x'],stream_value(pop['proposed_streams']['kmeans_initialization']));fitseconds=time.perf_counter()-fit0
            policy['population']=name;policy['training_ids_array_sha256']=array_hash(parts['train']['ids']);policy['preprocessing']=prep
            rpath=folder/f'{name}_router.json';write_json(rpath,policy);rsha=digest(rpath)
            seal['routers'][name]={'file':rpath.name,'sha256':rsha,'seed':policy['seed'],'training_n':len(parts['train']['x']),'fit_seconds':fitseconds,'fit_scope':'training inputs only; preprocessing,centres,tau,residualscale,marginbins frozen'}
            for split,part in parts.items():
                require(set(part).isdisjoint({'clean_y','label_flip'}),'Latent label leakage')
                require(set(part['ids']).isdisjoint(allids),'RecordIDcollision');allids.update(part['ids'].tolist())
                part['kmeans_route']=route(part['x'],policy);part['margin_bin']=margin_bins(part['x'],policy)
                fn=f"{name}_{'SEALED_test' if split=='test' else split}.npz";path=folder/fn
                with path.open('xb') as f:np.savez(f,**part)
                seal['files'][fn]={'sha256':digest(path),'arrays':{k:array_hash(v) for k,v in part.items()},'n':len(part['x']),'dataset':name,'task':pop['family'],'split':split,'router_policy_sha256':rsha}
            if latent:
                path=folder/f'{name}_SEALED_diagnostics.npz';payload={f'{s}_{k}':v for s,p in latent.items() for k,v in p.items()}
                with path.open('xb') as f:np.savez(f,**payload)
                seal['diagnostics'][name]={'file':path.name,'sha256':digest(path),'arrays':{k:array_hash(v) for k,v in payload.items()},'access':'FORBIDDEN_UNTIL_ROOT_TEST_RELEASE'}
            seal['datasets'][name]={'task':pop['family'],'stage':pop['stage'],'population_index':pop['population_index'],'proposed_streams':pop['proposed_streams'],'counts':{s:len(p['x']) for s,p in parts.items()},'label_counts':{s:np.bincount(p['y'],minlength=2).tolist() for s,p in parts.items()},'preparation_metadata':metadata,'router_fit_seconds':fitseconds,'total_population_preparation_seconds':time.perf_counter()-t0}
            print(json.dumps({'population':name,'records':sum(len(p['x']) for p in parts.values()),'router_seconds':fitseconds}),flush=True)
        require(synthetic_count==320000 and len(allids)==321372,'Data extent mismatch')
        require(source_hashes==data_source_hashes() and hashes==active_inputs()[2],'Source/protocol changed during generation')
        require(authority=={n:digest(GOV/n) for n in authority},'Authority changed during generation')
        seal.update({'new_unique_record_ids':len(allids),'synthetic_unique_new_coordinates':synthetic_count,'post_generation_total_synthetic_unique_features':len(excluded),'total_preparation_seconds':time.perf_counter()-started})
        write_json(folder/'DATA_SEAL.json',seal)
        print(json.dumps({'status':'PREPARED_SEALED_NO_MODEL_OUTCOMES','seal_sha256':digest(folder/'DATA_SEAL.json'),'populations':41,'files':len(seal['files'])}),flush=True)
    except BaseException as error:
        write_json(folder/'PREPARATION_FAILURE.json',{'created_utc':now(),'error':repr(error),'traceback':traceback.format_exc(),'partial_seal':seal,'partial_files_preserved':True});raise


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--preflight',action='store_true');g.add_argument('--banknote-preflight',action='store_true');g.add_argument('--register',action='store_true');g.add_argument('--generate',action='store_true')
    a=p.parse_args()
    if a.preflight:preflight()
    elif a.banknote_preflight:
        require(read_json(GOV/'HISTORICAL_FRESHNESS_PREFLIGHT.json')['active_input_sha256']==active_inputs()[2],'Completed historical preflight authority changed')
        result=historical_banknote_inventory();write_json(GOV/'BANKNOTE_HISTORICAL_PRESENCE.json',result);print(json.dumps({'status':result['status']}))
    elif a.register:registration()
    else:official_generation()

if __name__=='__main__':main()


