"""Independent, label-free circuit checks for the v0.3 review.

Only generated engineering inputs are used. No study data, training, cloud,
or official test outcomes are read. Production source is imported read-only
for the optional legacy comparison; the matrix and analytic functions below
do not import production gate primitives.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
LEGACY = Path(r"C:\Anthony Siljeg\Q2_improvement_study_v02\quantum\vendor\qpath\quantum.py")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rotation_y(angle):
    c, s = np.cos(angle / 2), np.sin(angle / 2)
    return np.array([[c, -s], [s, c]], dtype=np.complex128)


def rotation_z(angle):
    return np.diag(np.exp(np.array([-0.5j, 0.5j]) * angle))


def matrix_unitary(x, bank, depth, extra_encoding_rz=False, readout=np.pi / 2):
    """Declared reference: optional RZ(pi*x) after encoding RY, before trainable RY."""
    identity = np.eye(2, dtype=np.complex128)
    cnot = np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                     [0, 0, 0, 1], [0, 0, 1, 0]], dtype=np.complex128)
    result = np.eye(4, dtype=np.complex128)
    for layer in range(depth):
        for qubit in range(2):
            gates = [rotation_y(np.pi * x[qubit])]
            if extra_encoding_rz:
                gates.append(rotation_z(np.pi * x[qubit]))
            gates.extend([rotation_y(bank[layer, qubit, 0]),
                          rotation_z(bank[layer, qubit, 1])])
            for gate in gates:
                full = np.kron(gate, identity) if qubit == 0 else np.kron(identity, gate)
                result = full @ result
        result = cnot @ result
    return np.kron(rotation_y(readout), identity) @ result


def matrix_probability(x, bank, depth, **kwargs):
    return np.array([np.sum(np.abs(matrix_unitary(row, bank, depth, **kwargs)[2:, 0]) ** 2)
                     for row in np.asarray(x)])


def analytic_d1(x, parameters, readout=np.pi / 2):
    """p=(1-cos(gamma)cos(t0)+sin(gamma)A sin(t0)sin(t1))/2."""
    x = np.asarray(x)
    a0, b0, a1, b1 = np.asarray(parameters).ravel()
    t0, t1 = np.pi * x[:, 0] + a0, np.pi * x[:, 1] + a1
    amplitude = np.cos(b0) * np.cos(b1)
    return (1 - np.cos(readout) * np.cos(t0)
            + np.sin(readout) * amplitude * np.sin(t0) * np.sin(t1)) / 2


def analytic_d1_jacobian(x, parameters, readout=np.pi / 2, trainable_readout=False):
    x = np.asarray(x)
    a0, b0, a1, b1 = np.asarray(parameters).ravel()
    t0, t1 = np.pi * x[:, 0] + a0, np.pi * x[:, 1] + a1
    common = np.sin(readout) * np.sin(t0) * np.sin(t1) / 2
    columns = [
        (np.cos(readout) * np.sin(t0) + np.sin(readout) * np.cos(b0) * np.cos(b1)
         * np.cos(t0) * np.sin(t1)) / 2,
        -common * np.sin(b0) * np.cos(b1),
        np.sin(readout) * np.cos(b0) * np.cos(b1) * np.sin(t0) * np.cos(t1) / 2,
        -common * np.cos(b0) * np.sin(b1),
    ]
    if trainable_readout:
        columns.append((np.sin(readout) * np.cos(t0)
                        + np.cos(readout) * np.cos(b0) * np.cos(b1)
                        * np.sin(t0) * np.sin(t1)) / 2)
    return np.column_stack(columns)


def analytic_encoded_d1(x, parameters):
    """Bloch reference for RY(t), RZ(t), RY(a), RZ(b), then CX and X readout."""
    parameters = np.asarray(parameters).reshape(2, 2)
    factors = []
    for qubit in range(2):
        t = np.pi * np.asarray(x)[:, qubit]
        a, b = parameters[qubit]
        factors.append(np.cos(b) * (np.cos(a) * np.sin(t) * np.cos(t)
                                   + np.sin(a) * np.cos(t))
                       - np.sin(b) * np.sin(t) ** 2)
    return (1 + factors[0] * factors[1]) / 2


def central_jacobian(function, parameters, step=1e-6):
    p = np.asarray(parameters, dtype=float)
    columns = []
    for index in range(p.size):
        delta = np.zeros_like(p)
        delta.flat[index] = step
        columns.append((function(p + delta) - function(p - delta)) / (2 * step))
    return np.column_stack(columns)


def jacobian_summary(jacobian):
    singular = np.linalg.svd(jacobian, compute_uv=False)
    # Absolute and relative thresholds are stated; generic-rank evidence is
    # numerical and local, not a global expressivity or predictive-quality proof.
    cutoff = max(1e-8, float(singular[0]) * 1e-7)
    return {"singular_values": singular.tolist(), "rank_threshold": cutoff,
            "numerical_rank": int(np.sum(singular > cutoff)),
            "column_l2_norms": np.linalg.norm(jacobian, axis=0).tolist()}


def run_legacy_and_reference_checks():
    module = load_module(LEGACY, "legacy_quantum_read_only_review")
    rng = np.random.default_rng(730019)
    grid = np.array([(a, b) for a in np.linspace(-1, 1, 7) for b in np.linspace(-1, 1, 7)])
    x = np.vstack([grid, rng.uniform(-1, 1, (37, 2))])
    errors = {"matrix_probability": 0.0, "d1_analytic_probability": 0.0,
              "production_probability_gradient": 0.0, "d1_analytic_gradient": 0.0,
              "readout_formula_vs_matrix": 0.0, "readout_analytic_gradient": 0.0,
              "extra_encoding_formula_vs_matrix": 0.0}
    comparisons = 0
    for scale in (0.1, np.pi):
        bank = rng.uniform(-scale, scale, (4, 2, 2))
        for depth in range(1, 5):
            actual = module.predict_proba(x, bank, depth)
            expected = matrix_probability(x, bank, depth)
            errors["matrix_probability"] = max(errors["matrix_probability"], float(np.max(np.abs(actual - expected))))
            gradient, _ = module.probability_gradient(x[:13], bank, depth)
            finite = central_jacobian(lambda z: matrix_probability(x[:13], z, depth), bank)
            errors["production_probability_gradient"] = max(errors["production_probability_gradient"],
                float(np.max(np.abs(gradient.reshape(13, -1) - finite))))
            comparisons += len(x)
        p = bank[:1].copy()
        errors["d1_analytic_probability"] = max(errors["d1_analytic_probability"],
            float(np.max(np.abs(analytic_d1(x, p) - module.predict_proba(x, p, 1)))))
        finite = central_jacobian(lambda z: analytic_d1(x, z), p)
        errors["d1_analytic_gradient"] = max(errors["d1_analytic_gradient"],
            float(np.max(np.abs(analytic_d1_jacobian(x, p) - finite))))
        gamma = 0.73
        q = np.r_[p.ravel(), gamma]
        finite_readout = central_jacobian(lambda z: analytic_d1(x, z[:4], z[4]), q)
        errors["readout_analytic_gradient"] = max(errors["readout_analytic_gradient"],
            float(np.max(np.abs(finite_readout - analytic_d1_jacobian(x, p, gamma, True)))))
        errors["readout_formula_vs_matrix"] = max(errors["readout_formula_vs_matrix"],
            float(np.max(np.abs(analytic_d1(x, p, gamma) - matrix_probability(x, p, 1, readout=gamma)))))
        errors["extra_encoding_formula_vs_matrix"] = max(errors["extra_encoding_formula_vs_matrix"],
            float(np.max(np.abs(analytic_encoded_d1(x, p) - matrix_probability(x, p, 1, extra_encoding_rz=True)))))
    for error in errors.values():
        assert error < 2e-8, errors
    sensitivity = {}
    for name, parameters in {"zero_initialization": np.zeros(4),
                             "generic_small_angles": np.array([0.07, -0.04, 0.08, 0.03]),
                             "generic_broad_angles": np.array([0.37, -0.52, 0.71, 0.43])}.items():
        base_jac = analytic_d1_jacobian(x, parameters)
        readout_jac = analytic_d1_jacobian(x, parameters, trainable_readout=True)
        encoded_jac = central_jacobian(lambda z: analytic_encoded_d1(x, z), parameters)
        sensitivity[name] = {"baseline_d1": jacobian_summary(base_jac),
                             "trainable_readout_d1": jacobian_summary(readout_jac),
                             "extra_input_rz_d1": jacobian_summary(encoded_jac)}
    assert sensitivity["generic_broad_angles"]["baseline_d1"]["numerical_rank"] == 3
    assert sensitivity["generic_broad_angles"]["trainable_readout_d1"]["numerical_rank"] == 4
    assert sensitivity["generic_broad_angles"]["extra_input_rz_d1"]["numerical_rank"] == 4
    return {"status": "PASS", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "scope": "Legacy source and independent proposed-circuit algebra only; not v0.3 production approval",
            "generated_input_records": len(x), "label_independent_inputs": True,
            "official_study_data_read": False, "training_performed": False,
            "legacy_source_sha256": digest(LEGACY), "review_script_sha256": digest(__file__),
            "numpy_version": np.__version__, "matrix_probability_comparisons": comparisons,
            "maximum_errors": errors, "sensitivity": sensitivity,
            "interpretation": [
                "Baseline D1 has a0, a1 and amplitude cos(b0)cos(b1): at most three generic functional directions despite four allocated angles.",
                "The two proposed interventions each exhibit four local functional directions on the generated input grid at generic parameters.",
                "At zero/small angles sensitivities differ; numerical rank does not prove trainability, global capacity, predictive quality or causal attribution.",
                "Encoding variant assumes RZ(pi*x) immediately after each RY(pi*x), before trainable gates; validate the actual v0.3 implementation separately.",
            ]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite a previous review attempt")
    report = run_legacy_and_reference_checks()
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "maximum_errors": report["maximum_errors"]}, indent=2))
