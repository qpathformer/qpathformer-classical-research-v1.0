#!/usr/bin/env python3
"""Verify declared current content identities and recorded revision before-images."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

RECORDS = (
    "RESEARCH_V1_CONTENT_LICENSE_SCOPE.json",
    "RESEARCH_V1_LICENSE_ADOPTION.json",
    "RESEARCH_V1_SCOPE_REVISION.json",
    "docs/RESEARCH_APPROACH_CURRENT_SCOPE.json",
    "TRADEMARK_POLICY_ADOPTION.json",
)


def check(root, records=RECORDS):
    root = root.resolve()
    tracked = set(subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z"]
    ).decode("utf-8").split("\0")) - {""}
    checked = 0

    def visit(value, previous_commit=None, historical=False):
        nonlocal checked
        if isinstance(value, list):
            for item in value:
                visit(item, previous_commit, historical)
        elif isinstance(value, dict):
            if {"path", "bytes", "sha256"} <= value.keys():
                name = value["path"]
                if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                        or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts):
                    raise ValueError(f"unsafe identity path: {name!r}")
                if historical:
                    if not isinstance(previous_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", previous_commit):
                        raise ValueError("before identity requires a full historical source commit")
                    data = subprocess.check_output(
                        ["git", "-C", str(root), "show", f"{previous_commit}:{name}"],
                        stderr=subprocess.PIPE,
                    )
                else:
                    path = root / name
                    if name not in tracked or not path.resolve().is_relative_to(root):
                        raise ValueError(f"identity target is untracked, differently cased or outside repository: {name}")
                    data = path.read_bytes()
                if len(data) != value["bytes"] or hashlib.sha256(data).hexdigest() != value["sha256"]:
                    source = previous_commit if historical else "current files"
                    raise ValueError(f"identity mismatch: {name} ({source})")
                checked += 1
            else:
                for key, item in value.items():
                    visit(item, previous_commit, historical or key == "before")

    for name in records:
        if name not in tracked:
            raise ValueError(f"required current record is untracked or missing: {name}")
        value = json.loads((root / name).read_bytes())
        if not isinstance(value, dict):
            raise ValueError(f"record must be a JSON object: {name}")
        before = checked
        visit(value, value.get("previous_source_commit"))
        if checked == before:
            raise ValueError(f"record contains no byte-bound identities: {name}")
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        count = check(args.root)
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"Content scope check failed: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {count} declared identities in {len(RECORDS)} current records; no scientific or legal validation implied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
