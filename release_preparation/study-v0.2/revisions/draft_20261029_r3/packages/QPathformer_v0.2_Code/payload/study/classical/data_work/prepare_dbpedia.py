"""Frozen-data preparation for the internal Q-Pathformer v0.2 study.

No model, checkpoint, prediction, or outcome is read. Test labels are used only
for the predeclared stratified sample. Test payloads are procedurally sealed.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import time
import unicodedata

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qpath.classical import TextTokenizer

DATA = ROOT / "data"
SOURCE = DATA / "source"
SEALED = DATA / "sealed"
WORK = ROOT / "data_work"
ARCHIVE_SHA256 = "cad5773f85d7501bb2783833768bc624641cdddf7056000a06f12bcd0239a310"
SOURCE_URL = "https://drive.google.com/uc?export=download&id=0Bz8a_Dbh9QhbQ2Vic1kxMmZZQ1k"
OLD_DATA = Path(r"C:\Anthony Siljeg\Q2_full_benchmark_v01\classical\data\official")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")


def canonical(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def text_hash(text):
    return hashlib.sha256(canonical(text).encode("utf-8")).hexdigest()


def load_rows(path, split):
    records = []
    with path.open(newline="", encoding="utf-8") as f:
        for index, row in enumerate(csv.reader(f)):
            if len(row) != 3:
                raise ValueError(f"Unexpected CSV columns at {split}/{index}")
            text = row[1] + "\n" + row[2]
            label = int(row[0]) - 1
            if label not in range(14) or not canonical(text):
                raise ValueError("Invalid DBpedia source row")
            records.append({"id": f"dbpedia-official-{split}-{index:06d}",
                            "text": text, "label": label,
                            "duplicate_hash": text_hash(text),
                            "source_row": index, "source_split": split})
    return records


def old_hashes():
    hashes = set()
    files = {}
    for name in ("train.csv", "test.csv"):
        path = OLD_DATA / name
        if not path.is_file():
            raise FileNotFoundError("Existing v0.1 official data required for freshness audit")
        files[name] = digest(path)
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) != 3:
                    raise ValueError("Unexpected AG News column count")
                hashes.add(text_hash(row[1] + "\n" + row[2]))
    return hashes, files


def unique_eligible(rows, excluded_hashes, quarantine, split):
    grouped = defaultdict(list)
    for row in rows:
        reason = excluded_hashes.get(row["duplicate_hash"])
        if reason:
            quarantine.append({"id": row["id"], "source_split": split, "reason": reason})
        else:
            grouped[row["duplicate_hash"]].append(row)
    eligible = []
    for key in sorted(grouped):
        group = sorted(grouped[key], key=lambda r: r["source_row"])
        if len({r["label"] for r in group}) != 1:
            quarantine.extend({"id": r["id"], "source_split": split,
                               "reason": "conflicting_canonical_duplicate_labels"} for r in group)
        else:
            eligible.append(group[0])
            quarantine.extend({"id": r["id"], "source_split": split,
                               "reason": "redundant_same_label_canonical_duplicate"} for r in group[1:])
    return eligible


def stratified_selection(rows, per_label_counts, seed):
    """Sample unique content groups; sorted hashes then one PCG64 stream."""
    rng = np.random.Generator(np.random.PCG64(seed))
    result = {name: [] for name in per_label_counts}
    for label in range(14):
        members = sorted((r for r in rows if r["label"] == label), key=lambda r: r["duplicate_hash"])
        needed = sum(per_label_counts.values())
        if len(members) < needed:
            raise ValueError(f"Insufficient class {label}: {len(members)} vs {needed}")
        order = rng.permutation(len(members))
        offset = 0
        for split, count in per_label_counts.items():
            for idx in order[offset:offset + count]:
                record = dict(members[int(idx)])
                record["split"] = split
                result[split].append(record)
            offset += count
    for split in result:
        result[split].sort(key=lambda r: r["id"])
    return result


def save_records(path, records):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def encode(tokenizer, path, records):
    token_batches, masks = [], []
    for start in range(0, len(records), 2048):
        batch = records[start:start + 2048]
        token, mask = tokenizer.encode([r["text"] for r in batch])
        token_batches.append(token.numpy().astype(np.int32))
        masks.append(mask.numpy())
    np.savez(path, tokens=np.concatenate(token_batches), mask=np.concatenate(masks),
             labels=np.array([r["label"] for r in records], dtype=np.int64),
             record_ids=np.array([r["id"] for r in records]),
             canonical_text_hashes=np.array([r["duplicate_hash"] for r in records]))


def main():
    started = time.perf_counter()
    protocol_path = WORK / "DATA_PROTOCOL.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if digest(Path(__file__)) != protocol["preparation_script_sha256"]:
        raise ValueError("Preparation script changed after data protocol freeze")
    if (DATA / "manifest.json").exists():
        raise FileExistsError("Refusing to overwrite frozen data preparation")
    archive = SOURCE / "dbpedia_csv.tar.gz"
    if digest(archive) != ARCHIVE_SHA256:
        raise ValueError("Author archive hash mismatch")
    raw = SOURCE / "official"
    raw.mkdir(exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        for name in ("train.csv", "test.csv", "readme.txt", "classes.txt"):
            member = tar.getmember("dbpedia_csv/" + name)
            if not member.isfile():
                raise ValueError("Expected regular archive member")
            with tar.extractfile(member) as f:
                (raw / name).write_bytes(f.read())
    train = load_rows(raw / "train.csv", "train")
    test = load_rows(raw / "test.csv", "test")
    if len(train) != 560000 or len(test) != 70000:
        raise ValueError("Unexpected author release row counts")
    if Counter(r["label"] for r in train) != Counter({i: 40000 for i in range(14)}):
        raise ValueError("Unexpected author training class counts")
    if Counter(r["label"] for r in test) != Counter({i: 5000 for i in range(14)}):
        raise ValueError("Unexpected author test class counts")
    old_keys, old_files = old_hashes()
    official_test_keys = {r["duplicate_hash"] for r in test}
    excluded_train = {k: "matches_v01_agnews_content" for k in old_keys}
    excluded_train.update({k: "matches_any_official_dbpedia_test_content" for k in official_test_keys})
    excluded_test = {k: "matches_v01_agnews_content" for k in old_keys}
    quarantine = []
    train_pool = unique_eligible(train, excluded_train, quarantine, "train")
    test_pool = unique_eligible(test, excluded_test, quarantine, "test")
    splits = stratified_selection(train_pool, {"train": 7200, "validation": 800}, seed=173)
    splits.update(stratified_selection(test_pool, {"test": 1000}, seed=174))
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if {r["duplicate_hash"] for r in splits[a]} & {r["duplicate_hash"] for r in splits[b]}:
            raise AssertionError("Content overlap across study splits")
    if any(r["duplicate_hash"] in old_keys for rows in splits.values() for r in rows):
        raise AssertionError("v0.1 exact text contamination")
    SEALED.mkdir(exist_ok=True)
    for split, records in splits.items():
        destination = SEALED if split == "test" else DATA
        save_records(destination / f"{split}.jsonl", records)
    write(DATA / "quarantine.json", quarantine)
    fit_started = time.perf_counter()
    tokenizer = TextTokenizer.fit(splits["train"], vocab_size=8192, max_length=256)
    tokenizer.save(DATA / "tokenizer.json")
    fit_seconds = time.perf_counter() - fit_started
    write(DATA / "tokenizer_provenance.json", {
        "training_ids": list(tokenizer.training_ids), "requested_vocab": 8192,
        "actual_vocab": tokenizer.vocab_size, "maximum_length": 256,
        "maximum_content_tokens": 254, "fit_splits": ["train"],
        "tokenizer_sha256": digest(DATA / "tokenizer.json"),
        "special_token_ids": {"PAD": 0, "UNK": 1, "BOS": 2, "EOS": 3},
        "pooling": "Valid content tokens excluding PAD0/BOS2/EOS3; UNK1 represents content",
        "normalizer": "NFKC", "pretokenizer": "Whitespace",
        "implementation_sha256_at_preparation": digest(ROOT / "qpath" / "classical.py"),
    })
    for split, records in splits.items():
        destination = SEALED if split == "test" else DATA
        encode(tokenizer, destination / f"{split}_encoded.npz", records)
    seal = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SEALED_FOR_STAGE_B_CONFIRMATION",
        "seal_type": "Procedural separation and immutable content hashes, not cryptographic encryption",
        "release_condition": "Stage A winner and all Stage B fixed-budget checkpoints committed; root authorizes evaluation-only command",
        "test_selection_seed": 174, "test_rows": 14000, "test_class_counts": {str(i): 1000 for i in range(14)},
        "test_labels_used_for": "Fixed stratified sampling and encoding only; not fitting, tuning, checkpoint selection, or model outcomes",
        "file_sha256": {p.name: digest(p) for p in sorted(SEALED.iterdir()) if p.is_file()},
        "selected_record_ids_sha256": hashlib.sha256("\n".join(r["id"] for r in splits["test"]).encode()).hexdigest(),
    }
    write(DATA / "TEST_SEAL.json", seal)
    classes = (raw / "classes.txt").read_text(encoding="utf-8").splitlines()
    manifest = {
        "dataset": "DBpedia14 author CSV Version2, updated09/09/2015; fixed balanced subset",
        "source_url": SOURCE_URL, "archive_sha256": ARCHIVE_SHA256,
        "source_provenance": ["https://github.com/zhangxiangxiao/Crepe",
            "https://huggingface.co/datasets/fancyzhx/dbpedia_14",
            "https://www.dbpedia.org/about/"],
        "access_terms": "Author archive readme: Creative Commons Attribution-ShareAlike and GNU Free Documentation License; DBpedia primary site identifies CC-BY-SA3.0. Notices retained.",
        "label_map": {str(i): name for i, name in enumerate(classes)},
        "official_train_rows": len(train), "official_test_rows": len(test),
        "duplicate_key": "SHA256(NFKC+casefold+whitespace-collapse(title + newline + content))",
        "deduplication": "Exclude all official test-content matches from training pool, exclude v0.1 AG News exact matches, quarantine conflicting-label groups, retain lowest source-row representative for same-label groups; choose independent unique content groups.",
        "split_method": "Sorted unique content hashes within class; PCG64(seed173) permutation, first7200train then800validation perclass; independent PCG64(seed174) test permutation first1000perclass; store selected rows in original ID order.",
        "split_seed": 173, "test_selection_seed": 174, "split_rng": "NumPy PCG64",
        "counts": {split: len(records) for split, records in splits.items()},
        "label_counts": {split: dict(Counter(r["label"] for r in records)) for split, records in splits.items()},
        "eligible_unique_pool_counts": {"train": len(train_pool), "test": len(test_pool)},
        "quarantine_reasons": dict(Counter(q["reason"] for q in quarantine)),
        "v01_freshness_audit": {"old_official_files": old_files, "old_canonical_groups": len(old_keys),
            "new_all_official_text_matches_old": len(({r["duplicate_hash"] for r in train + test}) & old_keys),
            "selected_overlap": 0, "near_duplicates": "Not screened; exact canonical content only"},
        "test_policy": "14,000 stratified official-test subset sealed under data/sealed; labels used for declared sampling/encoding only; no test outcomes until all selected Stage B checkpoints frozen. Original70,000test is retained under source/official but never read by model training.",
        "comparison_scope": "Fresh dataset replication: retrain all baselines and variants on same DBpedia subset. AG News v0.1 metrics are historical context, not a directly comparable improvement estimate.",
        "semantic_priority": "Uniform sampling; no semantic-priority ratings or weighting",
        "tokenizer_fit_seconds": fit_seconds,
        "preparation_seconds": time.perf_counter() - started,
        "preparation_boundary": "Extraction through split, train-only tokenizer, and encoding; excludes download, manifest hashing and write",
        "data_protocol_sha256": digest(protocol_path), "preparation_script_sha256": digest(Path(__file__)),
        "file_sha256": {str(p.relative_to(DATA)).replace("\\", "/"): digest(p) for p in sorted(DATA.rglob("*")) if p.is_file() and p.name != "manifest.json"},
    }
    write(DATA / "manifest.json", manifest)
    print(json.dumps({k: manifest[k] for k in ("counts", "eligible_unique_pool_counts", "quarantine_reasons", "v01_freshness_audit", "tokenizer_fit_seconds", "preparation_seconds")}, indent=2), flush=True)
    print("manifest_sha256=" + digest(DATA / "manifest.json"), flush=True)


if __name__ == "__main__":
    main()
