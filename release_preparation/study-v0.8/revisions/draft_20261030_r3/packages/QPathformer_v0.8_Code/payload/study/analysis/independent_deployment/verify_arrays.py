"""Independent conversion array checks; no filesystem or producer imports."""
from __future__ import annotations
import numpy as np
import reference as ref

COEFFICIENT_TOLERANCE = 2e-11
LOGIT_TOLERANCE = 1e-9
PROBABILITY_TOLERANCE = 2e-12
THRESHOLD_BAND = 32*np.finfo(np.float64).eps


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def near(actual, expected, tolerance, message):
    actual, expected = np.asarray(actual), np.asarray(expected)
    need(actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(), message+" shape/finite")
    error = float(np.max(abs(actual-expected), initial=0))
    need(error <= tolerance, message)
    return error


def threshold_parity(left, right, message):
    """Retain every crossing and allow it only when both values are in the fixed band."""
    left, right = np.asarray(left), np.asarray(right)
    need(left.shape == right.shape and np.isfinite(left).all() and np.isfinite(right).all(),
         message+" shape/finite")
    crossing = (left >= .5) != (right >= .5)
    both_near = (abs(left-.5) <= THRESHOLD_BAND) & (abs(right-.5) <= THRESHOLD_BAND)
    need(not np.any(crossing & ~both_near), message+" outside registered roundoff band")
    indices = np.flatnonzero(crossing)
    return {"disagreement_flat_indices": indices.tolist(),
            "disagreement_probability_pairs": np.column_stack(
                (left.reshape(-1)[indices], right.reshape(-1)[indices])).tolist(),
            "threshold_band": float(THRESHOLD_BAND)}


def parameter_blocks(method, parameters):
    need(method in ("qmulti_kmeans", "qmulti_hash"), "Unsupported independent conversion method")
    count = 5
    values = np.asarray(parameters, dtype=np.float64)
    need(values.shape == (5*(count+9),) and np.isfinite(values).all(), "Invalid registered parameter vector")
    blocks = values.reshape(5, count+9)
    return blocks[:, :8].reshape(5, 2, 2, 2), blocks[:, 8:]


def verify_conversion(method, parameters, coefficients, inputs, route, saved_p=None, saved_z=None):
    cores, heads = parameter_blocks(method, parameters)
    coefficients = np.asarray(coefficients)
    expected_coefficients = np.array([ref.real_coefficients(core, head) for core, head in zip(cores, heads)])
    coefficient_error = near(coefficients, expected_coefficients, COEFFICIENT_TOLERANCE, "Laurent coefficients differ")
    inputs, route = np.asarray(inputs), np.asarray(route)
    need(inputs.ndim == 2 and inputs.shape[1] == 2 and route.shape == (len(inputs),)
         and np.isin(route, np.arange(5)).all(), "Invalid independent prediction inputs/routes")
    direct = np.empty(len(inputs), dtype=np.float64)
    for bank in range(5):
        use = route == bank
        if use.any():
            direct[use] = ref.dense_moments(inputs[use], cores[bank])[:, :heads.shape[1]-1] @ heads[bank, :-1]+heads[bank, -1]
    converted = np.sum(ref.feature_matrix(inputs)*coefficients[route], axis=1)
    logit_error = near(converted, direct, LOGIT_TOLERANCE, "Converted and dense logits differ")
    probability = ref.sigmoid(direct)
    dense_compiled_parity = threshold_parity(probability, ref.sigmoid(converted),
                                             "Dense versus converted threshold disagreement")
    result = {"coefficient_max_abs_error": coefficient_error,
              "converted_dense_logit_max_abs_error": logit_error,
              "coefficient_bytes": int(coefficients.nbytes), "records": len(inputs),
              "raw_threshold_disagreements_dense_vs_converted": int(np.sum((direct >= 0) != (converted >= 0))),
              "dense_vs_converted_probability_threshold_parity": dense_compiled_parity,
              "threshold_band_records": int(np.sum(abs(probability-.5) <= THRESHOLD_BAND))}
    if saved_p is not None:
        result["saved_probability_max_abs_error"] = near(saved_p, probability, PROBABILITY_TOLERANCE, "Saved probability differs")
        parity = threshold_parity(saved_p, probability, "Saved versus dense threshold disagreement")
        result["saved_threshold_parity"] = parity
        result["saved_threshold_disagreement_indices"] = parity["disagreement_flat_indices"]
    if saved_z is not None:
        result["saved_logit_max_abs_error"] = near(saved_z, direct, LOGIT_TOLERANCE, "Saved native logits differ")
    return result, expected_coefficients, probability, direct








