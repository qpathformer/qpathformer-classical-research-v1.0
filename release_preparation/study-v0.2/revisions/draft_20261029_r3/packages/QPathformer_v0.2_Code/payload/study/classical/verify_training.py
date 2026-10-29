"""Post-run structural audit. Does not read sealed test inputs or outcomes."""
import argparse
import json
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(stage):
    protocol_path = ROOT / f"protocol_{stage}_frozen.json"
    protocol, protocol_hash = read(protocol_path), digest(protocol_path)
    assert digest(ROOT / "data/manifest.json") == protocol["data_manifest_sha256"]
    for name, expected in protocol["code_sha256"].items():
        assert digest(ROOT / name) == expected, name
    horizon = protocol["schedules"]["main_updates"]
    rows, physical_updates, incident_paths = [], 0, []
    for seed in protocol["seeds"]:
        paired_work = []
        for method in ["common_warmup"] + protocol["methods"]:
            folder = ROOT / "results" / stage / f"seed_{seed}" / method
            status = read(folder / "status.json")
            commit = read(folder / "checkpoint_commit.json")
            expected_updates = 1000 if method == "common_warmup" else horizon
            assert status["status"] == "completed", (seed, method, status["status"])
            assert status["phase_update"] == status["latest_eligible_update"] == expected_updates
            assert commit["state"]["phase_update"] == expected_updates
            assert status["protocol_sha256"] == commit["state"]["protocol_sha256"] == protocol_hash
            assert status["latest_eligible_in_common_warmup"] == (method == "common_warmup")
            checkpoint = ROOT / "results" / stage / status["latest_eligible_checkpoint"]
            assert checkpoint.resolve() == (folder / commit["checkpoint"]).resolve()
            assert digest(checkpoint) == commit["sha256"]
            ledger = [json.loads(line) for line in (folder / "ledger.jsonl").read_text().splitlines()]
            assert [row["phase_update"] for row in ledger] == list(range(100, expected_updates + 1, 100))
            assert all(row["eligible"] for row in ledger)
            assert status["charged_total_seconds"] <= protocol["resource_cap_seconds_per_method"]
            if (folder / "incidents.jsonl").exists():
                incident_paths.append(str((folder / "incidents.jsonl").relative_to(ROOT)))
            physical_updates += expected_updates
            if method != "common_warmup":
                paired_work.append(status["training_padded_token_positions"])
                rows.append({"seed": seed, "method": method, "phase_update": expected_updates,
                             "validation_macro_f1": status["latest_validation"]["macro_f1"],
                             "charged_total_seconds": status["charged_total_seconds"],
                             "checkpoint_relative_path": status["latest_eligible_checkpoint"],
                             "checkpoint_sha256": commit["sha256"],
                             "resumed_segments": status["resumed_segments"]})
        assert len(set(paired_work)) == 1, (seed, "paired token work differs")
    result = {"status": "PASS", "stage": stage, "protocol_sha256": protocol_hash,
              "physical_optimizer_updates": physical_updates, "method_endpoints": rows,
              "incident_paths": incident_paths, "test_read": False,
              "checks": ["frozen code/data manifest", "all complete horizons and scheduled validation checkpoints",
                         "atomic committed endpoint hashes", "paired padded token work", "within resource caps"]}
    output = ROOT / "readiness" / f"{stage}_completion_audit.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["stage_a", "stage_b"])
    run(parser.parse_args().stage)
