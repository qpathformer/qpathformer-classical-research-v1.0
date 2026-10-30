"""Verify exact extracted-package membership, sizes and SHA-256 checksums."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[1]
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
CHECKSUM_LINE = re.compile(r"([0-9a-f]{64})  (.+)\Z")
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
RESERVED_NAMES.update("COM" + str(n) for n in range(1, 10))
RESERVED_NAMES.update("LPT" + str(n) for n in range(1, 10))


def safe_path(name):
    """Require one unambiguous, portable, package-relative file path."""
    if not isinstance(name, str) or not name:
        raise ValueError("Package path must be a nonempty string")
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError("Control character in package path: " + repr(name))
    if any(c in name for c in '\\:*?"<>|'):
        raise ValueError("Unsafe package path: " + repr(name))
    for component in name.split("/"):
        if component in ("", ".", "..") or component.endswith((" ", ".")):
            raise ValueError("Unsafe package path: " + repr(name))
        if component.split(".", 1)[0].upper() in RESERVED_NAMES:
            raise ValueError("Reserved package path: " + repr(name))
    return name


def remember_path(name, seen, label):
    safe_path(name)
    folded = name.casefold()
    if folded in seen:
        raise ValueError(label + " has duplicate or case-colliding paths: " + name)
    seen[folded] = name


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON member: " + key)
        result[key] = value
    return result


def package_files(root):
    """Do not follow links, junctions or other reparse points in the package."""
    files, seen, directories = {}, {}, set()

    def walk(directory):
        for entry in sorted(os.scandir(directory), key=lambda e: e.name):
            path = Path(entry.path)
            name = path.relative_to(root).as_posix()
            remember_path(name, seen, "Package")
            metadata = entry.stat(follow_symlinks=False)
            if entry.is_symlink() or getattr(metadata, "st_file_attributes", 0) & 0x400:
                raise ValueError("Link or reparse point in package: " + name)
            if stat.S_ISDIR(metadata.st_mode):
                directories.add(name)
                walk(path)
            elif stat.S_ISREG(metadata.st_mode):
                files[name] = path
            else:
                raise ValueError("Nonregular entry in package: " + name)

    metadata = root.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
        raise ValueError("Package root must be a regular directory")
    walk(root)
    required_directories = {"/".join(name.split("/")[:part]) for name in files for part in range(1, len(name.split("/")))}
    if directories != required_directories:
        raise ValueError("Unexpected empty directory in package")
    return files


def file_identity(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


def verify(root=ROOT):
    root = Path(root)
    actual = package_files(root)
    if not {"MANIFEST.json", "CHECKSUMS.sha256"}.issubset(actual):
        raise ValueError("Package inventory files are missing")
    manifest = json.loads(actual["MANIFEST.json"].read_text("utf-8"), object_pairs_hook=unique_object)
    if not isinstance(manifest, dict) or manifest.get("schema") != "qpath-package-manifest-1":
        raise ValueError("Unrecognized package manifest")
    if manifest.get("package") != root.name or not isinstance(manifest.get("files"), list):
        raise ValueError("Invalid manifest package or files")
    expected, manifest_paths = {}, {}
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise ValueError("Malformed manifest file record")
        name = entry["path"]
        remember_path(name, manifest_paths, "Manifest")
        if type(entry["bytes"]) is not int or entry["bytes"] < 0:
            raise ValueError("Invalid manifest size: " + name)
        if not isinstance(entry["sha256"], str) or not HEX_SHA256.fullmatch(entry["sha256"]):
            raise ValueError("Invalid manifest digest: " + name)
        expected[name] = entry
    if set(expected) != set(actual) - {"MANIFEST.json", "CHECKSUMS.sha256"}:
        raise ValueError("Manifest membership differs")

    checks, checksum_paths = {}, {}
    for line in actual["CHECKSUMS.sha256"].read_text("utf-8").splitlines():
        match = CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise ValueError("Malformed checksum line")
        digest, name = match.groups()
        remember_path(name, checksum_paths, "Checksums")
        checks[name] = digest
    if set(checks) != set(actual) - {"CHECKSUMS.sha256"}:
        raise ValueError("Checksum membership differs")

    identities = {name: file_identity(path) for name, path in actual.items()}
    for name, entry in expected.items():
        if any(identities[name][key] != entry[key] for key in ("bytes", "sha256")):
            raise ValueError("Manifest differs: " + name)
    for name, digest in checks.items():
        if identities[name]["sha256"] != digest:
            raise ValueError("Checksum differs: " + name)
    fingerprint = hashlib.sha256(json.dumps(identities, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"status": "PASS", "files": len(actual), "package_fingerprint_sha256": fingerprint}


def main():
    print(json.dumps(verify()))


if __name__ == "__main__":
    main()
