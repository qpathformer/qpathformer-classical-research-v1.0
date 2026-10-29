"""Canonical official-output checks without importing official computations."""
import numpy as np
from evidence_io import compare_structure, require
from statistics_reference import class_metrics, metrics
from threshold_reference import CASES


def check_metrics(actual, recorded, tolerance=2e-12):
    required = ("bce", "macro_f1", "accuracy", "n", "clipped", "confusion")
    return compare_structure({key: actual[key] for key in required},
                             {key: recorded[key] for key in required}, tolerance)


def check_population_summary(independent, official, protocol_sha256, statistics_sha256):
    require(official["protocol_sha256"] == protocol_sha256, "Official analysis protocol differs")
    require(official["statistics_source_sha256"] == statistics_sha256, "Official statistics source differs")
    require(official["numpy_version"] == "2.5.4", "Official bootstrap runtime differs")
    fields = ("population", "n", "seeds", "methods", "bootstrap_replicates", "primary_family_size",
              "bootstrap_counts_sha256", "aggregate", "contrasts", "limits")
    return compare_structure({key: independent[key] for key in fields}, {key: official[key] for key in fields})


def check_official_numerical(y, canonical, ids, routes, official, independent, numerical):
    """Check canonical facts fully, plus disclosed author-reference consistency.

    The separate author oracle does not publish every reference probability.
    Its raw class metrics can be rebuilt from the exhaustive disagreement list.
    Reference-near counts and raw-reference BCE receive bounded consistency
    checks, whereas our own complete oracle probabilities are fully replayed.
    """
    y, p, ids = np.asarray(y), np.asarray(canonical), np.asarray(ids)
    n = len(y)
    require(official["band_half_width"] == numerical["band"], "Official numerical band differs")
    for key, tolerance in (("maximum_probability_error", numerical["probability_abs_tolerance"]),
                           ("independent_bce_error", numerical["independent_aggregate_bce_abs_tolerance"])):
        require(np.isfinite(official[key]) and 0 <= official[key] <= tolerance, "Official numerical tolerance failed")
    canonical_metrics = metrics(y, p)
    check_metrics(canonical_metrics, official["canonical_metrics"])
    compare_structure(independent["sensitivity"], official["sensitivity"])
    require(set(official["sensitivity"]) == set(CASES), "Official sensitivity cases differ")
    actual_near = np.abs(p - .5) <= numerical["band"]
    counts = official["counts"]
    require(counts["n"] == n and counts["canonical_near_band"] == int(actual_near.sum()), "Canonical numerical counts differ")
    require(counts["outside_band_class_disagreements"] == 0, "Official outside-band disagreement")
    records = official["disagreements"]
    require(counts["class_disagreements"] == len(records)
            and counts["exact_class_agreement"] == (len(records) == 0), "Official disagreement counts differ")
    positions = {int(record_id): index for index, record_id in enumerate(ids)}
    seen = set()
    reconstructed_raw = (p >= .5).astype(np.int64)
    for row in records:
        identity = row["record_id"]
        require(type(identity) is int and identity in positions and identity not in seen, "Unknown/duplicate disagreement ID")
        seen.add(identity)
        index = positions[identity]
        require(row["label"] == int(y[index]) and row["hash_route"] == int(routes["hash"][index])
                and row["kmeans_route"] == int(routes["kmeans"][index]), "Disagreement metadata differs")
        cp, rp = row["canonical_probability"], row["reference_probability"]
        require(cp == float(p[index]) and np.isfinite(rp) and 0 <= rp <= 1,
                "Disclosed canonical probability differs or invalid raw probability")
        require(abs(cp - rp) <= numerical["probability_abs_tolerance"]
                and abs(cp - .5) <= numerical["band"] and abs(rp - .5) <= numerical["band"],
                "Disclosed difference violates numerical band/tolerance")
        require(row["canonical_prediction"] == int(cp >= .5) and row["reference_prediction"] == int(rp >= .5)
                and row["canonical_prediction"] != row["reference_prediction"], "Disclosed classes inconsistent")
        reconstructed_raw[index] = row["reference_prediction"]
    raw_classes = class_metrics(y, reconstructed_raw)
    compare_structure(raw_classes, {key: official["raw_reference_metrics"][key] for key in raw_classes})
    raw_bce = official["raw_reference_metrics"]["bce"]
    require(np.isfinite(raw_bce) and raw_bce >= 0
            and abs(raw_bce - canonical_metrics["bce"]) <= numerical["independent_aggregate_bce_abs_tolerance"],
            "Disclosed raw-reference BCE inconsistent")
    require(abs(abs(raw_bce - official["canonical_metrics"]["bce"]) - official["independent_bce_error"]) <= 2e-12,
            "Official BCE error field inconsistent")
    reference_count, union_count = counts["reference_near_band"], counts["union_near_band"]
    require(type(reference_count) is int and type(union_count) is int
            and len(records) <= reference_count <= n
            and max(counts["canonical_near_band"], reference_count) <= union_count
            <= min(n, counts["canonical_near_band"] + reference_count - len(records)),
            "Undisclosed author reference-near counts violate set bounds")
    require(type(official["raw_reference_metrics"]["clipped"]) is int
            and 0 <= official["raw_reference_metrics"]["clipped"] <= n, "Invalid raw clipped count")
    return {"status": "PASS", "canonical_metrics_and_sensitivities_reconstructed": True,
            "author_raw_class_metrics_reconstructed_from_disagreement_rows": True,
            "author_disagreements": len(records), "independent_disagreements": independent["counts"]["class_disagreements"],
            "limitation": "Author-reference full probabilities are not stored; reference-near count membership, raw clipped count and raw BCE receive consistency/tolerance checks. Independent oracle full probabilities and diagnostics are separately reconstructed."}
