"""One separately authorized sealed evaluation, after every confirmation endpoint."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import engine as E
import numpy as np
import torch
import study as S


def validate_release(path):
    release = S.read_json(path)
    protocol, protocol_hash = S.freeze("stage_b")
    S.activate("stage_b")
    required = {"authorized": True, "release_type": "independent_evaluation_after_all_training",
                "stage_b_protocol_sha256": protocol_hash,
                "selection_sha256": E.digest(S.ROOT / "selection_frozen.json"),
                "data_manifest_sha256": E.digest(E.DATA / "manifest.json"),
                "test_seal_sha256": E.digest(E.DATA / "TEST_SEAL.json"), "expected_test_rows": 14000}
    if any(release.get(key) != value for key, value in required.items()) or not release.get("created_utc"):
        raise ValueError("Evaluation release identities/authorization mismatch")
    expected = {(seed, method) for seed in protocol["seeds"] for method in protocol["methods"]}
    endpoints = release.get("endpoints", [])
    if len(endpoints) != 15 or {(r["seed"], r["method"]) for r in endpoints} != expected:
        raise ValueError("Release must bind exactly15 registered endpoints")
    for row in endpoints:
        folder = E.RESULTS / f"seed_{row['seed']}" / row["method"]
        status = S.read_json(folder / "status.json")
        committed = S.read_json(folder / "checkpoint_commit.json")
        checkpoint = (E.RESULTS / row["checkpoint_relative_path"]).resolve()
        if not checkpoint.is_relative_to(folder.resolve()):
            raise ValueError("Endpoint checkpoint path outside registered arm")
        if (status["status"] != "completed" or status["phase_update"] != 10000
                or status["protocol_sha256"] != protocol_hash
                or committed["state"]["protocol_sha256"] != protocol_hash
                or status["latest_eligible_update"] != 10000 or status["latest_eligible_in_common_warmup"]
                or row["committed_main_update"] != 10000
                or committed["state"]["phase_update"] != 10000
                or status["latest_eligible_checkpoint"] != row["checkpoint_relative_path"]
                or E.digest(checkpoint) != row["sha256"]
                or committed["sha256"] != row["sha256"]):
            raise ValueError("Endpoint incomplete, changed, or not latest eligible")
        payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        expected_config = S.asdict(S.replace(S.CONFIG, adapters=1) if row["method"] == "shared" else S.CONFIG)
        expected_mode = {"shared": "shared", "current_content": "content", "frozen_content": "frozen_content", "hash18": "hash18"}[row["method"]]
        if (payload["data_manifest_sha256"] != release["data_manifest_sha256"]
                or payload["tokenizer_sha256"] != E.digest(E.DATA / "tokenizer.json")
                or payload["run_state"]["protocol_sha256"] != protocol_hash
                or payload["run_state"]["phase_update"] != 10000
                or payload["model_config"] != expected_config or payload["route_mode"] != expected_mode):
            raise ValueError("Checkpoint payload provenance mismatch")
    return release, protocol


def read_sealed_data():
    manifest = S.read_json(E.DATA / "manifest.json")
    for name in ["sealed/test.jsonl", "sealed/test_encoded.npz"]:
        if E.digest(E.DATA / name) != manifest["file_sha256"][name]:
            raise ValueError("Sealed test artifact hash mismatch")
    data = E.load_data("test", E.DATA / "sealed")
    records = [json.loads(line) for line in (E.DATA / "sealed" / "test.jsonl").read_text(encoding="utf-8").splitlines()]
    if [r["id"] for r in records] != data["record_ids"].tolist():
        raise ValueError("Sealed raw/encoded record alignment mismatch")
    data["texts"] = np.array([r["text"] for r in records])
    if len(records) != 14000 or torch.bincount(data["labels"], minlength=14).tolist() != [1000] * 14:
        raise ValueError("Sealed population mismatch")
    # Disk tokenizer provenance/hash reload; verify a fixed subset of encodings.
    tokenizer = S.TextTokenizer.load(E.DATA / "tokenizer.json")
    tokens, masks = tokenizer.encode(data["texts"][:64].tolist())
    if not torch.equal(tokens, data["tokens"][:64]) or not torch.equal(masks, data["mask"][:64]):
        raise ValueError("Saved tokenizer does not reproduce sealed encoded inputs")
    return data


@torch.no_grad()
def deployment_timing(model, data):
    """Uncached forward on fixed label-independent random1024 test inputs."""
    model.eval()
    indices = np.random.default_rng(96301).choice(len(data["labels"]), 1024, replace=False)
    data = E.subset(data, indices)
    elapsed = []
    for repeat in range(4):
        E.synchronize()
        start_time = time.perf_counter()
        for start in range(0, 1024, 64):
            tokens, mask, _, _ = E.device_batch(data, slice(start, start + 64))
            model(tokens, mask, texts=data["texts"][start:start + 64].tolist())
        E.synchronize()
        if repeat:
            elapsed.append(time.perf_counter() - start_time)
    return {"records_per_repeat": 1024, "batch_size": 64, "repeats_after_one_warmup": 3,
            "record_sample": "Label-independent PCG64seed96301; same1024 rows for every model",
            "record_ids_sha256": E.hashlib.sha256("\n".join(data["record_ids"].tolist()).encode()).hexdigest(),
            "seconds": elapsed, "mean_seconds_per_record": float(np.mean(elapsed)) / 1024,
            "boundary": "CPU batch indexing/host-device transfer/text slice/full classifier+uncached router forward; no tokenizer/modelload; GPU synchronized"}


def run(release_path):
    E.enable_local_only()
    release, protocol = validate_release(release_path)
    output = Path(release["output_directorynew"]).resolve()
    if not output.is_relative_to(S.ROOT.resolve()) or output.exists():
        raise ValueError("Evaluation requires a new output directory within this experiment")
    output.mkdir(parents=True)
    E.write_json(output / "access_event.json", {"utc": E.now(), "release_sha256": E.digest(release_path),
                  "scope": "All frozen endpoints evaluated; no subsequent selection"})
    started = time.perf_counter()
    data = read_sealed_data()
    preparation_seconds = time.perf_counter() - started
    reports = []
    for row in release["endpoints"]:
        E.configure(row["seed"])
        arm_started = time.perf_counter()
        checkpoint = E.RESULTS / row["checkpoint_relative_path"]
        model = E.model_from_checkpoint(checkpoint)
        # No cached routes: this is full inference including frozen router or hashing.
        metric, predictions, routes, _ = E.evaluate(model, data)
        timing = deployment_timing(model, data)
        name = f"seed_{row['seed']}_{row['method']}"
        np.savez(output / f"{name}_predictions.npz", predictions=predictions, labels=data["labels"].numpy(),
                 record_ids=data["record_ids"], routes=routes, canonical_text_hashes=data["canonical_text_hashes"])
        report = dict(row, metrics=metric, deployment=timing, separately_charged_evaluation_seconds=time.perf_counter() - arm_started)
        E.write_json(output / f"{name}_report.json", report)
        reports.append(report)
        print(json.dumps({"seed": row["seed"], "method": row["method"], "test_macro_f1": metric["macro_f1"]}), flush=True)
        del model
        torch.cuda.empty_cache()
    E.write_json(output / "summary.json", {"status": "completed", "utc": E.now(), "reports": reports,
                  "release_sha256": E.digest(release_path), "data_preparation_seconds": preparation_seconds,
                  "evaluation_total_seconds": time.perf_counter() - started,
                  "primary": protocol["primary"], "test_never_selected_configuration_or_checkpoint": True})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    run(parser.parse_args().release)
