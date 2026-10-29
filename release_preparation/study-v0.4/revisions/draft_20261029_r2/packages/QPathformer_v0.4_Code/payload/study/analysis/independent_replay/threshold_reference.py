"""Independent registered threshold diagnostics; canonical probabilities unchanged."""
import numpy as np
from statistics_reference import class_metrics, metrics, require, validate

CASES = ("all_ambiguous_to0", "all_ambiguous_to1", "label_assisted_all_incorrect", "label_assisted_all_correct")


def diagnostics(y, canonical, reference, ids, routes, numerical):
    y, p = validate(y, canonical)
    _, q = validate(y, reference)
    ids = np.asarray(ids)
    require(ids.shape == y.shape and ids.dtype.kind in "iu" and len(set(ids.tolist())) == len(ids), "Invalid unique record IDs")
    require(set(routes) == {"hash", "kmeans"} and all(np.asarray(v).shape == y.shape
            and np.asarray(v).dtype.kind in "iu" and np.isin(v, range(5)).all() for v in routes.values()), "Invalid route arrays")
    band = numerical["band"]
    require(band == 32 * np.finfo(np.float64).eps and numerical["canonical_threshold"] == .5,
            "Unregistered numerical band/threshold")
    maximum_error = float(np.max(np.abs(p - q)))
    require(maximum_error <= numerical["probability_abs_tolerance"], "Independent probability tolerance exceeded")
    canonical_metrics, reference_metrics = metrics(y, p), metrics(y, q)
    bce_error = abs(canonical_metrics["bce"] - reference_metrics["bce"])
    require(bce_error <= numerical["independent_aggregate_bce_abs_tolerance"], "Independent aggregate BCE tolerance exceeded")
    saved_classes, raw_classes = p >= .5, q >= .5
    saved_near, reference_near = np.abs(p - .5) <= band, np.abs(q - .5) <= band
    different = saved_classes != raw_classes
    outside = different & ~(saved_near & reference_near)
    require(not outside.any(), "Class disagreement outside both-probability numerical band")

    def counts(mask):
        return {"n": int(mask.sum()), "canonical_near_band": int((mask & saved_near).sum()),
                "reference_near_band": int((mask & reference_near).sum()),
                "union_near_band": int((mask & (saved_near | reference_near)).sum()),
                "class_disagreements": int((mask & different).sum()),
                "outside_band_class_disagreements": int((mask & outside).sum()),
                "exact_class_agreement": not bool((mask & different).any())}

    sensitivity = {}
    for name, values in zip(CASES, (np.zeros(len(y), dtype=np.int64), np.ones(len(y), dtype=np.int64), 1 - y, y)):
        changed = saved_classes.astype(np.int64).copy()
        changed[saved_near] = values[saved_near]
        sensitivity[name] = class_metrics(y, changed)
    disagreements = [{"record_id": int(ids[index]), "label": int(y[index]),
                      "hash_route": int(routes["hash"][index]), "kmeans_route": int(routes["kmeans"][index]),
                      "canonical_probability": float(p[index]), "reference_probability": float(q[index]),
                      "canonical_prediction": int(saved_classes[index]), "reference_prediction": int(raw_classes[index])}
                     for index in np.flatnonzero(different)]
    return {"status": "PASS", "band_half_width": band, "maximum_probability_error": maximum_error,
            "independent_bce_error": bce_error, "counts": counts(np.ones(len(y), dtype=bool)),
            "by_route": {kind: {str(bank): counts(np.asarray(values) == bank) for bank in range(5)}
                         for kind, values in routes.items()},
            "by_label": {str(label): counts(y == label) for label in (0, 1)},
            "canonical_metrics": canonical_metrics, "raw_reference_metrics": reference_metrics,
            "raw_reference_minus_canonical": {name: reference_metrics[name] - canonical_metrics[name]
                                               for name in ("bce", "macro_f1", "accuracy")},
            "sensitivity": sensitivity, "disagreements": disagreements,
            "scope": "Canonical saved probabilities define predictions and ambiguity mask. Raw reference classes are disclosed separately. The32eps convention is not a proven forward-error bound. Label-assisted extrema are class-sensitivity diagnostics, not trained predictions or confidence intervals; no synthetic BCE is assigned to them."}
