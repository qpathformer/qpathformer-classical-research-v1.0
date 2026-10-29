"""Independent reconstruction audit; never imports preparation or model code."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import unicodedata

import numpy as np
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORK = ROOT / "data_work"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while block := f.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def key(title, body):
    joined = title + "\n" + body
    normalized = " ".join(unicodedata.normalize("NFKC", joined).casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def raw_rows(path, name, labels=True):
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for i, fields in enumerate(csv.reader(f)):
            assert len(fields) == 3
            h = key(fields[1], fields[2])
            if labels:
                label = int(fields[0]) - 1
                assert 0 <= label < 14
                rows.append((h, i, label, f"dbpedia-official-{name}-{i:06d}", fields[1] + "\n" + fields[2]))
            else:
                rows.append(h)
    return rows


def pool(records, excluded):
    groups = defaultdict(list)
    rejected = []
    for record in records:
        if record[0] in excluded:
            rejected.append(record[3])
        else:
            groups[record[0]].append(record)
    accepted = []
    for members in groups.values():
        if len({row[2] for row in members}) != 1:
            rejected.extend(row[3] for row in members)
        else:
            ranked = sorted(members, key=lambda r: r[1])
            accepted.append(ranked[0])
            rejected.extend(row[3] for row in ranked[1:])
    return accepted, rejected


def selection(pool_rows, seed, counts):
    generator = np.random.Generator(np.random.PCG64(seed))
    results = {name: [] for name, _ in counts}
    for label in range(14):
        ordered = sorted([row for row in pool_rows if row[2] == label], key=lambda row: row[0])
        indices = generator.permutation(len(ordered))
        start = 0
        for name, count in counts:
            results[name].extend(ordered[int(index)] for index in indices[start:start+count])
            start += count
    return {name: sorted(rows, key=lambda row: row[3]) for name, rows in results.items()}


def main():
    start = time.perf_counter()
    manifest = json.loads((DATA / "manifest.json").read_text())
    protocol = json.loads((WORK / "DATA_PROTOCOL.json").read_text())
    assert sha(WORK / "DATA_PROTOCOL.json") == manifest["data_protocol_sha256"]
    assert sha(WORK / "prepare_dbpedia.py") == protocol["preparation_script_sha256"] == manifest["preparation_script_sha256"]
    for name, expected in manifest["file_sha256"].items():
        assert sha(DATA / name) == expected, name
    seal = json.loads((DATA / "TEST_SEAL.json").read_text())
    for name, expected in seal["file_sha256"].items():
        assert sha(DATA / "sealed" / name) == expected
    old = Path(r"C:\Anthony Siljeg\Q2_full_benchmark_v01\classical\data\official")
    old_keys = set()
    for filename, expected in manifest["v01_freshness_audit"]["old_official_files"].items():
        assert sha(old / filename) == expected
        old_keys.update(raw_rows(old / filename, "", labels=False))
    raw = DATA / "source" / "official"
    train = raw_rows(raw / "train.csv", "train")
    test = raw_rows(raw / "test.csv", "test")
    assert len(train) == 560000 and len(test) == 70000
    assert Counter(r[2] for r in train) == Counter({i: 40000 for i in range(14)})
    assert Counter(r[2] for r in test) == Counter({i: 5000 for i in range(14)})
    test_keys = {row[0] for row in test}
    train_pool, train_rejected = pool(train, test_keys | old_keys)
    test_pool, test_rejected = pool(test, old_keys)
    expected = selection(train_pool, 173, [("train", 7200), ("validation", 800)])
    expected.update(selection(test_pool, 174, [("test", 1000)]))
    quarantine = json.loads((DATA / "quarantine.json").read_text())
    assert {row["id"] for row in quarantine} == set(train_rejected + test_rejected)
    tokenizer = Tokenizer.from_file(str(DATA / "tokenizer.json"))
    provenance = json.loads((DATA / "tokenizer_provenance.json").read_text())
    assert provenance["training_ids"] == [r[3] for r in expected["train"]]
    assert provenance["fit_splits"] == ["train"] and provenance["actual_vocab"] == tokenizer.get_vocab_size() == 8192
    assert tokenizer.truncation["max_length"] == 256
    assert tokenizer.padding["length"] == 256
    assert tokenizer.get_vocab()["[PAD]"] == 0
    assert tokenizer.get_vocab()["[UNK]"] == 1
    assert tokenizer.get_vocab()["[BOS]"] == 2
    assert tokenizer.get_vocab()["[EOS]"] == 3
    split_hashes = {}
    counts = {}
    for name, selected in expected.items():
        directory = DATA / "sealed" if name == "test" else DATA
        with (directory / f"{name}.jsonl").open(encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        assert len(rows) == len(selected)
        for actual, wanted in zip(rows, selected):
            assert (actual["duplicate_hash"], actual["source_row"], actual["label"], actual["id"], actual["text"]) == wanted
            assert actual["split"] == name
        with np.load(directory / f"{name}_encoded.npz", allow_pickle=False) as arr:
            assert arr["tokens"].shape == (len(rows), 256)
            assert arr["mask"].shape == (len(rows), 256)
            assert arr["tokens"].dtype == np.int32 and arr["mask"].dtype == bool
            np.testing.assert_array_equal(arr["record_ids"], [r["id"] for r in rows])
            np.testing.assert_array_equal(arr["labels"], [r["label"] for r in rows])
            np.testing.assert_array_equal(arr["canonical_text_hashes"], [r["duplicate_hash"] for r in rows])
            assert arr["tokens"].min() >= 0 and arr["tokens"].max() < 8192
            for offset in range(0, len(rows), 1024):
                batch = tokenizer.encode_batch([r["text"] for r in rows[offset:offset+1024]])
                np.testing.assert_array_equal(arr["tokens"][offset:offset+len(batch)], [v.ids for v in batch])
                np.testing.assert_array_equal(arr["mask"][offset:offset+len(batch)], [v.attention_mask for v in batch])
            assert np.all(arr["tokens"][:, 0] == 2)
            lengths = arr["mask"].sum(1)
            assert np.all(arr["tokens"][np.arange(len(rows)), lengths-1] == 3)
        split_hashes[name] = {r["duplicate_hash"] for r in rows}
        assert len(split_hashes[name]) == len(rows)
        assert not split_hashes[name] & old_keys
        counts[name] = len(rows)
    assert not split_hashes["train"] & split_hashes["validation"]
    assert not split_hashes["train"] & test_keys
    assert not split_hashes["validation"] & test_keys
    selected_test_ids = "\n".join(r[3] for r in expected["test"])
    assert hashlib.sha256(selected_test_ids.encode()).hexdigest() == seal["selected_record_ids_sha256"]
    result = {
        "status": "PASS", "audit_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Independent raw-source reconstruction; does not import preparation/model code; no model/test outcomes inspected",
        "auditor_script_sha256": sha(Path(__file__)), "manifest_sha256": sha(DATA / "manifest.json"),
        "data_protocol_sha256": sha(WORK / "DATA_PROTOCOL.json"),
        "verified_manifest_payload_files": len(manifest["file_sha256"]),
        "source_rows_checked": len(train) + len(test), "encoded_records_replayed": sum(counts.values()),
        "selected_counts": counts, "all_selected_canonical_groups_unique": True,
        "train_validation_test_exact_overlap": 0, "training_validation_vs_all_official_test_overlap": 0,
        "selected_vs_all_v01_agnews_exact_overlap": 0,
        "quarantined_record_ids": train_rejected + test_rejected,
        "label_validation": "Range/counts/selection/duplicate consistency; no manual semantic label verification",
        "limitations": "Canonical exact duplicates only; no near-duplicate or semantic overlap audit. Procedural test seal, not encrypted.",
        "seconds": time.perf_counter() - start,
    }
    (WORK / "DATA_AUDIT.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
