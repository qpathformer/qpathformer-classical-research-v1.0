"""Read-only bound metadata and complete immutable payload checks.

This module does not decide when outcomes may be read. The adapter must first
validate release/commit metadata and write its access event before invoking
payload hashing. No training, official evaluator or statistics helpers imported.
"""
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    path = Path(path)
    before = path.stat()
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    after = path.stat()
    require(before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns,
            "File changed during hash: " + str(path))
    return result.hexdigest()


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, "Duplicate JSON key: " + name)
        result[name] = value
    return result


def reject_nonfinite(value):
    raise ValueError("Nonfinite JSON number: " + value)


def read_bound(path, watched):
    path = Path(path).resolve()
    before = digest(path)
    raw = path.read_bytes()
    after = digest(path)
    require(before == hashlib.sha256(raw).hexdigest() == after, "Metadata changed while reading: " + str(path))
    if str(path) in watched:
        require(watched[str(path)] == before, "Previously bound metadata changed: " + str(path))
    watched[str(path)] = before
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object, parse_constant=reject_nonfinite)


def recheck(watched):
    for path, expected in watched.items():
        require(digest(path) == expected, "Bound evidence changed: " + path)


def safe_relative(name):
    require(isinstance(name, str) and name and "\\" not in name and "\x00" not in name,
            "Invalid relative path")
    windows = PureWindowsPath(name)
    parts = name.split("/")
    require(not windows.drive and not windows.root and all(part not in ("", ".", "..")
            and ":" not in part and part == part.strip() and not part.endswith(".") for part in parts),
            "Unsafe relative path: " + name)
    return name


def contained(root, name):
    root = Path(root).resolve()
    target = root / safe_relative(name)
    require(target.resolve().is_relative_to(root), "Path escapes evidence root")
    for part in (target, *target.parents):
        if part == root:
            break
        require(not part.is_symlink() and not (hasattr(part, "is_junction") and part.is_junction()),
                "Evidence link/junction forbidden: " + str(part))
    return target


def map_original_absolute(recorded, original_root, current_root):
    """Validate original Windows provenance, then remap without reading it."""
    require(isinstance(recorded, str) and isinstance(original_root, str), "Original provenance paths must be strings")
    original, value = PureWindowsPath(original_root), PureWindowsPath(recorded)
    require(original.is_absolute() and value.is_absolute() and value.is_relative_to(original),
            "Recorded absolute identity is outside declared original root")
    relative = value.relative_to(original).as_posix()
    return contained(current_root, safe_relative(relative))


def inventory(root, files, *, size_key="bytes", exclude=(), expected=None):
    """Hash every declared payload and reject unlisted files or unsafe paths.

    files is {relative_name:{sha256,bytes}}. Call only after outcome access has
    been authorized by the adapter's metadata gates and recorded durably.
    """
    root = Path(root).resolve()
    require(isinstance(files, dict) and files, "Nonempty declared inventory required")
    normalized = set()
    for name, info in files.items():
        safe_relative(name)
        require(name.casefold() not in normalized, "Duplicate normalized inventory path")
        normalized.add(name.casefold())
        require(isinstance(info, dict) and type(info[size_key]) is int and info[size_key] >= 0,
                "Invalid inventory byte size")
        require(isinstance(info["sha256"], str) and len(info["sha256"]) == 64
                and all(c in "0123456789abcdef" for c in info["sha256"]), "Invalid inventory hash")
    if expected is not None:
        require(set(files) == set(expected), "Expected complete inventory differs")
    excluded = {safe_relative(name) for name in exclude}
    observed = set()
    for path in root.rglob("*"):
        require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction()), "Inventory link forbidden")
        if path.is_file():
            name = safe_relative(path.relative_to(root).as_posix())
            if name not in excluded:
                require(name.casefold() not in {item.casefold() for item in observed}, "Duplicate normalized physical path")
                observed.add(name)
    require(observed == set(files), "Physical and committed payload inventories differ")
    total = 0
    for name, info in files.items():
        path = contained(root, name)
        require(path.is_file() and path.stat().st_size == info[size_key], "Committed payload size differs: " + name)
        require(digest(path) == info["sha256"], "Committed payload hash differs: " + name)
        total += info[size_key]
    return {"status": "PASS", "files": len(files), "bytes": total, "exact_inventory": True}


def compare_structure(actual, expected, tolerance=2e-12, path="root", statistics=None):
    """Expected structure exact; finite numerical leaves within fixed tolerance."""
    if statistics is None:
        statistics = {"numeric_checks": 0, "exact_checks": 0, "maximum_absolute_error": 0.}
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), "Object keys differ at " + path)
        for key, value in expected.items():
            compare_structure(actual[key], value, tolerance, path + "/" + key, statistics)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), "List shape differs at " + path)
        for index, value in enumerate(expected):
            compare_structure(actual[index], value, tolerance, path + "/" + str(index), statistics)
    elif isinstance(expected, float):
        require(type(actual) in (float, int) and math.isfinite(actual) and math.isfinite(expected), "Nonfinite/non-numeric value at " + path)
        error = abs(actual - expected)
        require(error <= tolerance, f"Numeric mismatch at {path}: {actual} versus {expected}")
        statistics["numeric_checks"] += 1
        statistics["maximum_absolute_error"] = max(error, statistics["maximum_absolute_error"], 0.)
    else:
        require(type(actual) is type(expected) and actual == expected, "Exact mismatch at " + path)
        statistics["exact_checks"] += 1
    return statistics
