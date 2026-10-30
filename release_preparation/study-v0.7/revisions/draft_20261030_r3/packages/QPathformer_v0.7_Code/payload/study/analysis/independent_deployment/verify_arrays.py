"""Independent conversion and shot array checks; no filesystem or producer imports."""
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
    need(method in ("qscalar_kmeans", "qmulti_kmeans", "qmulti_hash"), "Unsupported independent conversion method")
    count = 1 if method == "qscalar_kmeans" else 5
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


def verify_joint_inputs(method, parameters, inputs, route, saved_joint, saved_heads, saved_ideal):
    cores, heads = parameter_blocks(method, parameters)
    inputs, route = np.asarray(inputs), np.asarray(route)
    need(route.shape == (len(inputs),) and np.isin(route, np.arange(5)).all(), "Invalid shot route")
    settings = ("XX",) if heads.shape[1] == 2 else ("XX", "ZZ")
    need(set(saved_joint) == set(settings), "Unexpected shot settings")
    expected = {setting: np.empty((len(inputs), 4)) for setting in settings}
    for bank in range(5):
        use = route == bank
        if use.any():
            probabilities = ref.joint_probabilities(inputs[use], cores[bank])
            for setting in settings:
                expected[setting][use] = probabilities[setting]
    errors = {setting: near(saved_joint[setting], expected[setting], 2e-12, "Joint-state probabilities differ") for setting in settings}
    near(saved_heads, heads[route], 0., "Saved per-input heads differ")
    # Weighted joint outcomes are independent of producer moment aggregation.
    x = expected["XX"] @ ref.SIGNS[:2].T
    moments = x[:, :1] if len(settings) == 1 else np.column_stack((x, expected["ZZ"] @ ref.SIGNS.T))
    z = np.sum(moments*heads[route, :-1], axis=1)+heads[route, -1]
    p = ref.sigmoid(z)
    error = near(saved_ideal, p, PROBABILITY_TOLERANCE, "Own ideal shot checkpoint differs")
    return {"maximum_joint_probability_errors": errors, "ideal_probability_max_abs_error": error}, expected


def head_logit_variance(joints, heads, total_budget):
    """Exact conditional finite-shot logit variance including within-setting covariance."""
    heads = np.asarray(heads)
    need(total_budget in (1024, 8192) and heads.ndim == 2 and heads.shape[1] in (2, 6), "Invalid variance inputs")
    scalar = heads.shape[1] == 2
    weights = {"XX": heads[:, :1] if scalar else heads[:, :2]}
    signs = {"XX": ref.SIGNS[:1] if scalar else ref.SIGNS[:2]}
    if not scalar:
        weights["ZZ"], signs["ZZ"] = heads[:, 2:5], ref.SIGNS
    variance = np.zeros(len(heads))
    for setting in weights:
        probabilities = np.asarray(joints[setting])
        outcomes = weights[setting] @ signs[setting]
        mean = (probabilities*outcomes).sum(axis=1)
        second = (probabilities*outcomes**2).sum(axis=1)
        variance += np.maximum(second-mean**2, 0)/(total_budget if scalar else total_budget//2)
    return variance


def verify_shot_draw(run_id, total, repeat, heads, joint_probabilities, saved_counts, saved_predictions):
    scalar = np.asarray(heads).shape[1] == 2
    settings = ("XX",) if scalar else ("XX", "ZZ")
    need(set(saved_counts) == set(settings), "Shot count settings differ")
    for setting in settings:
        # Replay from the retained normalized producer probabilities after the separate
        # dense-state comparison, avoiding random count shifts from harmless rounding.
        counts = ref.replay_counts(joint_probabilities[setting], run_id, total, setting, repeat, not scalar)
        near(saved_counts[setting], counts, 0., "Registered shot stream/count array differs")
    moments = ref.moments_from_counts(saved_counts["XX"], None if scalar else saved_counts["ZZ"])
    logits = np.sum(moments*np.asarray(heads)[:, :-1], axis=1)+np.asarray(heads)[:, -1]
    predictions = ref.sigmoid(logits)
    error = near(saved_predictions, predictions, PROBABILITY_TOLERANCE, "Shot prediction differs from joint counts")
    return {"probability_max_abs_error": error, "represented_measurement_outcomes": len(predictions)*total,
            "joint_count_vectors": len(predictions)*len(settings)}, predictions


def conditional_statistics(predictions, ideal):
    values, ideal = np.asarray(predictions), np.asarray(ideal)
    need(values.shape == (20, len(ideal)) and np.isfinite(values).all(), "All 20 technical repeats required")
    error = values-ideal[None, :]
    bias = np.sum(error, axis=0)/20
    mean = np.sum(values, axis=0)/20
    variance = np.sum((values-mean)**2, axis=0)/20
    return {"mean_probability_absolute_error": float(np.sum(abs(error))/error.size),
            "mean_probability_squared_error": float(np.sum(error**2)/error.size),
            "mean_signed_probability_error": float(np.sum(error)/error.size),
            "mean_per_record_squared_bias": float(np.mean(bias*bias)),
            "mean_per_record_technical_variance_population_ddof0": float(np.mean(variance)),
            "decision_disagreements": int(np.count_nonzero((values >= .5) != (ideal[None, :] >= .5))),
            "bias_per_record": bias.tolist(), "variance_per_record": variance.tolist(),
            "mse_per_record": (np.sum(error**2, axis=0)/20).tolist()}
