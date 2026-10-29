"""Independent checkpoint replay arithmetic; no production imports or data reads.

The future release-gated adapter supplies the independently reviewed oracle,
checkpoint arrays and canonical probabilities/logits. This module has no CLI
and cannot discover or open a study endpoint or test file on its own.
"""
import math
import numpy as np
from statistics_reference import METHODS, calibration, metrics, native_logit_bce, require, validate
from threshold_reference import diagnostics


def stable_sigmoid(logits):
    z = np.asarray(logits, dtype=np.float64)
    require(np.isfinite(z).all(), "Finite native logits required")
    values = [1 / (1 + math.exp(-float(value))) if value >= 0 else
              math.exp(float(value)) / (1 + math.exp(float(value))) for value in z.ravel()]
    return np.asarray(values, dtype=np.float64).reshape(z.shape)


def native_diagnostics(method, y, canonical_p, canonical_z, reference_p, reference_z, numerical):
    y, p = validate(y, canonical_p)
    _, q = validate(y, reference_p)
    require(method in METHODS, "Unregistered model method")
    require(canonical_z is not None and reference_z is not None, "Both canonical and reference logits required")
    z, w = np.asarray(canonical_z, dtype=np.float64), np.asarray(reference_z, dtype=np.float64)
    require(z.shape == y.shape and w.shape == y.shape and np.isfinite(z).all() and np.isfinite(w).all(),
            "Aligned finite native logits required")
    require(np.max(np.abs(stable_sigmoid(z) - p)) <= numerical["probability_abs_tolerance"],
            "Canonical logits contradict canonical probabilities")
    require(np.max(np.abs(stable_sigmoid(w) - q)) <= numerical["probability_abs_tolerance"],
            "Reference logits contradict reference probabilities")
    maximum_logit_error = float(np.max(np.abs(z - w)))
    require(maximum_logit_error <= numerical["independent_native_logit_abs_tolerance"],
            "Independent native logit tolerance exceeded")
    canonical_loss, reference_loss = native_logit_bce(y, z), native_logit_bce(y, w)
    error = abs(canonical_loss - reference_loss)
    require(error <= numerical["independent_native_aggregate_loss_abs_tolerance"], "Independent native aggregate loss tolerance exceeded")
    return {"has_native_logits": True, "canonical_native_bce": canonical_loss,
            "reference_native_bce": reference_loss, "maximum_native_logit_error": maximum_logit_error,
            "independent_native_loss_error": error,
            "minimum_native_logit": None if canonical_z is None else float(np.min(canonical_z)),
            "maximum_native_logit": None if canonical_z is None else float(np.max(canonical_z)),
            "clipped_wrong_prediction_count": int(np.sum(((p < 1e-7) | (p > 1 - 1e-7)) & ((p >= .5) != y))),
            "scope": "All six arms use unbounded native logit BCE. The reported common comparison BCE is clipped separately."}


def replay_checkpoint(oracle, method, parameters, core_parameters, x, y, ids, routes,
                      canonical_p, canonical_z, numerical):
    """Replay one released checkpoint using independently constructed gates/MLPs."""
    require(method in METHODS and tuple(oracle.METHODS) == METHODS, "Independent oracle method contract differs")
    x = np.asarray(x, dtype=np.float64)
    require(x.shape == (len(y), 2) and np.isfinite(x).all() and (np.abs(x) <= 1).all(),
            "Registered raw coordinate inputs required")
    require(set(routes) == {"hash", "kmeans"}, "Both bound route arrays required")
    route = None if method.endswith("_global") else routes["kmeans"]
    require(core_parameters is None or np.asarray(core_parameters).size == 0, "Unexpected separate frozen core")
    core = None
    reference_p, reference_z = oracle.predict_with_logits(method, parameters, x, route, core)
    threshold = diagnostics(y, canonical_p, reference_p, ids, routes, numerical)
    native = native_diagnostics(method, y, canonical_p, canonical_z, reference_p, reference_z, numerical)
    return reference_p, reference_z, {"status": "PASS", "method": method,
        "numerical_verification": threshold, "native_verification": native,
        "canonical_calibration": calibration(y, canonical_p),
        "reference_calibration": calibration(y, reference_p)}
