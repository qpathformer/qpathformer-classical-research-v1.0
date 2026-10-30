"""Extract historical delivered v0.4 aggregates/costs without model execution.

Only selected immutable evidence is rehashed against the pinned delivery
manifest. This is not a fresh complete-package verification. Output is
exclusive; v0.4 is opened read-only and no v0.5 outcome is read.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path, PureWindowsPath
import statistics

MANIFEST_SHA256 = "5d823ea5605670bb069e6874ddd74b4f495e3f3ff58cb91a1afcda29a367aca8"
METHODS = tuple(f"{family}_{route}" for family in ("q2", "mlp", "trig") for route in ("global", "hash", "kmeans"))
POPULATIONS = ("confirmation_circle_1", "confirmation_circle_2", "confirmation_ellipse")
SEEDS = (801, 802, 803, 804, 805)
TIMES = ("training_loop_seconds", "charged_training_loop_seconds", "endpoint_timer_seconds", "inference_seconds_per_record")


def require(value, message):
    if not value:
        raise ValueError(message)


def read_stable(path):
    path = Path(path)
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino),
            "Source changed during read: " + str(path))
    return raw, hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "Duplicate JSON key")
        out[key] = value
    return out


def parse(raw):
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON: " + value)))


def safe_path(root, relative):
    windows = PureWindowsPath(relative)
    require(isinstance(relative, str) and relative and not windows.is_absolute() and not windows.drive
            and "\\" not in relative and all(part not in ("", ".", "..") and ":" not in part
                                               for part in relative.split("/")), "Unsafe relative path")
    path = root / relative
    require(path.resolve().is_relative_to(root), "Source path escapes package")
    for part in (path, *path.parents):
        if part == root:
            break
        require(not part.is_symlink() and not (hasattr(part, "is_junction") and part.is_junction()), "Source link forbidden")
    return path


class Source:
    def __init__(self, root):
        self.root = Path(root).resolve()
        raw, value = read_stable(self.root / "DELIVERY_MANIFEST.json")
        require(value == MANIFEST_SHA256, "Unexpected v0.4 delivery manifest")
        manifest = parse(raw)
        require(manifest["schema"] == "qpath-delivery-1" and manifest["file_count"] == 19263
                and manifest["total_size_bytes"] == 1204159807, "Historical inventory identity differs")
        self.entries = {row["relative_path"]: row for row in manifest["files"]}
        require(len(self.entries) == len(manifest["files"]), "Repeated manifest names")
        self.sources = {"DELIVERY_MANIFEST.json": {"sha256": value, "bytes": len(raw)}}

    def raw(self, relative, expected=None, metadata=False):
        path = safe_path(self.root, relative)
        raw, value = read_stable(path)
        if metadata:
            require(relative in ("DELIVERY_VERIFICATION.json", "DELIVERY_VERIFICATION_INDEPENDENT.json"), "Unbound metadata")
        else:
            row = self.entries[relative]
            require(row["sha256"] == value and row["size_bytes"] == len(raw), "Manifest payload mismatch: " + relative)
        if expected is not None:
            require(value == expected, "Evidence link mismatch: " + relative)
        self.sources[relative] = {"sha256": value, "bytes": len(raw)}
        return raw

    def json(self, relative, expected=None, metadata=False):
        return parse(self.raw(relative, expected, metadata))

    def commit_payload(self, folder, commit, name):
        entry = commit["files"][name]
        raw = self.raw(folder + "/" + name, entry["sha256"])
        require(len(raw) == entry["bytes"], "Commit payload size mismatch")
        return raw

    def recheck(self):
        for relative, item in self.sources.items():
            raw, value = read_stable(safe_path(self.root, relative))
            require(value == item["sha256"] and len(raw) == item["bytes"], "Source changed during extraction")


def extract(root):
    source = Source(root)
    for name in ("DELIVERY_VERIFICATION.json", "DELIVERY_VERIFICATION_INDEPENDENT.json"):
        record = source.json(name, metadata=True)
        require(record["status"] == "PASS" and record["manifest_sha256"] == MANIFEST_SHA256
                and record["verified_files"] == 19263, "Historical delivery check differs")
    plan = source.json("governance/STUDY_PLAN.json")
    protocol = source.json("governance/ANALYSIS_PROTOCOL.json")
    resource = source.json("governance/RESOURCE_ACCOUNTING_NOTES.json")
    source.raw("quantum/models.py")
    source.raw("quantum/study.py")
    source.raw("analysis/learning_resources_v04.py")
    require(plan["study_id"] == "QPATH-ROUTING-v0.4" and tuple(plan["methods"]) == METHODS, "Historical design differs")
    official_folder = "quantum/confirmation_evaluation"
    official_commit = source.json(official_folder + "/EVALUATION_COMMIT.json")
    require(official_commit["status"] == "completed" and official_commit["report_count"] == 135, "Official evaluation incomplete")
    official = parse(source.commit_payload(official_folder, official_commit, "summary.json"))
    require(official["status"] == "completed" and official["report_count"] == 135
            and tuple(official["population_order"]) == POPULATIONS and tuple(official["method_order"]) == METHODS
            and tuple(official["training_seeds"]) == SEEDS, "Official aggregate identities differ")
    learning = {}
    for stage, count in (("A", 54), ("B", 135)):
        folder = f"analysis/learning_resources/stage_{stage}_v01"
        commit = source.json(folder + "/ANALYSIS_COMMIT.json")
        require(commit["status"] == "PASS" and commit["stage"] == stage and commit["endpoint_count"] == count,
                "Learning commit incomplete")
        learning[stage] = parse(source.commit_payload(folder, commit, "summary.json"))
        require(learning[stage]["status"] == "PASS" and learning[stage]["endpoint_count"] == count, "Learning summary incomplete")
        if stage == "B":
            csv_raw = source.commit_payload(folder, commit, "endpoint_metrics.csv")
    rows = list(csv.DictReader(io.StringIO(csv_raw.decode("utf-8-sig"))))
    keyed = {(row["population"], int(row["seed"]), row["method"]): row for row in rows}
    expected = {(pop, seed, method) for pop in POPULATIONS for seed in SEEDS for method in METHODS}
    require(len(rows) == len(keyed) == 135 and set(keyed) == expected, "Historical cost rows incomplete")
    outcomes = {}
    for pop in POPULATIONS:
        stats = official["populations"][pop]["statistics"]
        require(tuple(stats["seeds"]) == SEEDS and stats["n"] == 1600 and tuple(stats["methods"]) == METHODS,
                "Population aggregate contract differs")
        outcomes[pop] = {"test_records": 1600, "training_seeds": list(SEEDS), "methods": {},
                         "registered_primary_bce_contrasts": [{"name": item["name"], **item["metrics"]["bce"]}
                             for item in stats["contrasts"] if item["primary"]]}
        for method in METHODS:
            aggregate = stats["aggregate"][method]
            cost = learning["B"]["populations"][pop][method]
            values = [keyed[(pop, seed, method)] for seed in SEEDS]
            metrics = {name: aggregate[name] for name in ("bce", "macro_f1", "accuracy")}
            metrics["brier"] = aggregate.get("brier")
            for name, item in metrics.items():
                if item is None:
                    continue
                require(len(item["seed_values"]) == 5, "Five-seed metric values required")
                require(abs(statistics.mean(item["seed_values"]) - item["mean"]) < 2e-12
                        and abs(statistics.stdev(item["seed_values"]) - item["sample_sd"]) < 2e-12,
                        "Historical metric summary inconsistent")
            timing = {}
            for name in TIMES:
                actual = [float(row[name]) for row in values]
                require(all(math.isfinite(v) and v >= 0 for v in actual), "Invalid recorded timing")
                require(abs(statistics.mean(actual) - cost["timing"][name]["mean"]) < 1e-9
                        and abs(statistics.stdev(actual) - cost["timing"][name]["sample_sd"]) < 1e-9,
                        "Cost CSV/aggregate mismatch")
                timing[name] = {**cost["timing"][name], "seed_values": actual}
            parameters = {int(row["parameter_count"]) for row in values}
            banks = {int(row["bank_count"]) for row in values}
            require(len(parameters) == len(banks) == 1, "Architecture differs within method")
            outcomes[pop]["methods"][method] = {"metrics": metrics, "timing": timing,
                "parameter_count": parameters.pop(), "bank_count": banks.pop(),
                "selected_rounds": [int(row["selected_round"]) for row in values],
                "selected_checkpoint_sha256": [row["selected_checkpoint_sha256"] for row in values],
                "training_clipped_probability_visits": [int(row["training_clipped_probability_visits"]) for row in values]}
    qa = source.json("report_work/FINAL_QA.json")
    require(qa["status"] == "PASS", "Final report QA not PASS")
    report_name = "docs/" + qa["report_filename"]
    source.raw(report_name, qa["report_sha256"])
    source.raw("report_work/report_content.json", qa["report_content_sha256"])
    source.raw("report_work/ROOT_REPORT_INPUTS.json", qa["input_manifest_sha256"])
    source.raw("report_work/ROOT_VISUAL_REVIEW.json", qa["root_visual_review_sha256"])
    candidates = [name for name, row in source.entries.items() if row["sha256"] == qa["scientific_review_sha256"]
                  and name.startswith("analysis/classical_review/FINAL_REPORT_CONTENT_SCIENTIFIC_REVIEW")]
    require(len(candidates) == 1, "Ambiguous final scientific review identity")
    review = source.json(candidates[0], qa["scientific_review_sha256"])
    require(review["status"] == "PASS" and review["reviewed_content_sha256"] == qa["report_content_sha256"],
            "Scientific review content differs")
    content = source.json("report_work/CONTENT_PROVENANCE.json")
    require(content["report_content_sha256"] == qa["report_content_sha256"]
            and content["input_manifest_sha256"] == qa["input_manifest_sha256"], "Report provenance mismatch")
    for relative, value in content["source_sha256"].items():
        source.raw("report_work/" + relative, value)
    # Link the actual selected evidence to the final scientific review without
    # treating excluded earlier rendering intermediates as required payloads.
    for relative in (official_folder + "/summary.json", official_folder + "/EVALUATION_COMMIT.json",
                     "analysis/learning_resources/stage_A_v01/summary.json", "analysis/learning_resources/stage_B_v01/summary.json",
                     "report_work/CONTENT_PROVENANCE.json", "report_work/report_content.json"):
        require(review["evidence_sha256"][relative] == source.sources[relative]["sha256"], "Scientific evidence link differs")
    physical_stages = {stage: {key: learning[stage][key] for key in (
        "endpoint_count", "stage_execution_observed_wall_seconds", "sum_endpoint_training_loop_seconds",
        "sum_endpoint_charged_training_loop_seconds", "sum_endpoint_timer_seconds")} for stage in ("A", "B")}
    source.recheck()
    return {"schema": "qpath-v04-historical-context-for-v05-1", "status": "PASS_EXTRACTED_VERIFIED_SOURCES",
        "classification": "INTERNAL_RESEARCH", "historical_study_id": "QPATH-ROUTING-v0.4",
        "source_root": str(source.root), "delivery_manifest_sha256": MANIFEST_SHA256,
        "source_files": source.sources, "training_seeds": list(SEEDS), "methods": list(METHODS),
        "populations": outcomes, "stage_costs": physical_stages,
        "summed_stage_execution_wall_seconds": sum(row["stage_execution_observed_wall_seconds"] for row in physical_stages.values()),
        "architecture": plan["models"], "training_recipe": plan["training"],
        "task_semantics": plan["data"]["tasks"], "primary_uncertainty": plan["primary"],
        "brier_availability": {"available_in_official_aggregates": any(row["metrics"]["brier"] is not None
             for pop in outcomes.values() for row in pop["methods"].values()),
             "scope": "Brier was not registered or retained in the v0.4 aggregate schema. Null means unavailable, not zero. No historical predictions were rescored to add it."},
        "loss_context_relevant_to_v05": [
            "v0.4 all arms used clipped probability BCE with clip[1e-7,1-1e-7]; raw training gradient contributions were hard-zeroed outside the interval, including MLP/trigonometric logit arms.",
            "The v0.4 quantum head was fixed Born probability after its final RY readout; no trainable scalar or multivariate logistic readout was tested.",
            "v0.4 routed MLP banks had width2 and ReLU, 45 total trainable parameters; the global MLP had width32 and129 parameters. Routed trigonometric controls had125 parameters, so capacity was not matched.",
            "These results motivate separating readout/link flexibility, native logit optimization and stronger classical controls in a new registered study; the historical study itself does not isolate those mechanisms."],
        "timing_scope": {"units": {"training": "seconds per full endpoint", "inference": "seconds per record"},
            "training": "All200rounds/15000updates; loop includes batch training, full validation and within-loop evidence/checkpoint work. Setup excluded.",
            "charged_training": "Loop plus reused generation, applicable joint-router fit and train/validation route-cache accounting charges. Repeated charges do not mean preparation was repeatedly executed.",
            "endpoint_timer": "Adds post-training diagnostics; stops before final result/commit writes.",
            "inference": "Lowest1024 validation record IDs, one uncached warmup plus three timed raw-coordinate route+forward repeats. Excludes I/O/model loading/fit; fifth cached consistency forward is outside timed repeats.",
            "parallelism": "Concurrent CPU process wall durations are descriptive. Endpoint seconds overlap and must not be called project elapsed time. Summed stage launcher wall time excludes audits, evaluation and reporting.",
            "resource_note": resource},
        "final_report_provenance": {"relative_path": report_name, "report_sha256": qa["report_sha256"],
            "final_qa_sha256": source.sources["report_work/FINAL_QA.json"]["sha256"],
            "scientific_review_path": candidates[0], "scientific_review_sha256": qa["scientific_review_sha256"],
            "report_content_sha256": qa["report_content_sha256"], "content_provenance_sha256": source.sources["report_work/CONTENT_PROVENANCE.json"]["sha256"],
            "input_manifest_sha256": qa["input_manifest_sha256"], "pages": qa["render"]["pages"]},
        "limits": ["Historical context only: v0.5 uses fresh data, seeds and fitted routers. These are not paired cross-version improvement estimates.",
            "Each population retains its own five seeds and uncertainty; no pooling as independent real-world tasks.",
            "BCE uses natural logs; F1/accuracy values here are fractions, not percentages. Timing ratios do not prove hardware or quantum advantage.",
            "Extraction rehashed the named sources and report provenance against the pinned delivered manifest, not all19263 payloads anew.",
            "No training, model evaluation, raw prediction rescoring, cloud call, baseline mutation or v0.5 model outcome access."],
        "model_executions": 0, "v05_test_outcomes_accessed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(r"C:\Q2\Improvement_Study_v0.4"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "v04_context.json")
    args = parser.parse_args()
    require(not args.output.exists(), "Preserve previous context; output already exists")
    require(not args.output.resolve().is_relative_to(args.source_root.resolve()), "Never write into the historical package")
    before = read_stable(__file__)[1]
    result = extract(args.source_root)
    require(read_stable(__file__)[1] == before, "Extraction helper changed")
    result["extractor_sha256"] = before
    result["created_utc"] = datetime.now(timezone.utc).isoformat()
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": result["status"], "output": str(args.output),
        "sha256": read_stable(args.output)[1], "population_method_rows": 27,
        "bound_source_files": len(result["source_files"]), "model_executions": 0}))


if __name__ == "__main__":
    main()
