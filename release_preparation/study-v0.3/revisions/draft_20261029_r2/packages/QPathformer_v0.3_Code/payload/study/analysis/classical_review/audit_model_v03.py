"""Independent numerical review of v0.3 model source using generated fixtures only."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib
import json
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode = True
import numpy as np
import analytic_circuit_checks as A

ROOT = Path(__file__).resolve().parents[2]
QUANTUM = ROOT / "quantum"
sys.path.insert(0, str(QUANTUM))
S = importlib.import_module("qstudy")
C = importlib.import_module("circuits")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    names = ["quantum/qstudy.py", "quantum/circuits.py", "quantum/reference_v03.py",
             "quantum/vendor/qpath/quantum.py", "analysis/classical_review/analytic_circuit_checks.py",
             "analysis/classical_review/audit_model_v03.py"]
    return {name: digest(ROOT / name) for name in names}


def dense_unitary(x, bank, depth, encoding=False, beta=np.pi / 2):
    """Independent standard dense matrices, including the approved half-frequency RZ."""
    ident = np.eye(2, dtype=complex)
    cx = np.eye(4, dtype=complex)[[0, 1, 3, 2]]
    result = np.eye(4, dtype=complex)
    for layer in range(int(depth)):
        for q in range(2):
            gates = [A.rotation_y(np.pi * x[q])]
            if encoding:
                gates.append(A.rotation_z(np.pi * x[q] / 2))
            gates += [A.rotation_y(bank[layer, q, 0]), A.rotation_z(bank[layer, q, 1])]
            for gate in gates:
                result = (np.kron(gate, ident) if q == 0 else np.kron(ident, gate)) @ result
        result = cx @ result
    return np.kron(A.rotation_y(beta), ident) @ result


def dense_probability(x, bank, depth, encoding=False, beta=np.pi / 2):
    state = dense_unitary(x, bank, depth, encoding, beta)[:, 0]
    return float(np.vdot(state[2:], state[2:]).real)


def encoded_analytic_half(x, p):
    p = np.asarray(p).reshape(2, 2)
    factors = []
    for q in range(2):
        t = np.pi * x[:, q]
        a, b = p[q]
        factors.append(np.cos(b) * (np.cos(a) * np.sin(t) * np.cos(t / 2) + np.sin(a) * np.cos(t))
                       - np.sin(b) * np.sin(t) * np.sin(t / 2))
    return (1 + factors[0] * factors[1]) / 2


def independent_predictions(method, parameters, x, depth, route):
    p = np.asarray(parameters)
    output = []
    for index, row in enumerate(x):
        if method in ("hash40", "kmeans40", "ensemble40"):
            banks = p.reshape(5, 2, 2, 2)
            selected = list(range(5)) if method == "ensemble40" else [int(route[index])]
            output.append(sum(dense_probability(row, banks[k], 2) for k in selected) / len(selected))
        elif method == "untied_assigned":
            d = int(depth[index])
            offset = 2 * d * (d - 1)
            output.append(dense_probability(row, p[offset:offset + 4 * d].reshape(d, 2, 2), d))
        else:
            d = {"fixed1": 1, "encoding1": 1, "readout1": 1, "fixed2": 2,
                 "fixed4": 4}.get(method, int(depth[index]))
            if method == "min_depth2":
                d = max(d, 2)
            beta = p[-1] if method == "readout1" else np.pi / 2
            angles = p[:-1] if method == "readout1" else p
            output.append(dense_probability(row, angles.reshape(-1, 2, 2), d, method == "encoding1", beta))
    return np.asarray(output)


def independent_mlp(method, p, x, depth):
    width, inputs = (5, 6) if method == "mlp41" else (16, 6)
    features = x if inputs == 2 else np.column_stack((x, np.eye(4)[depth - 1]))
    count = inputs * width
    hidden = np.maximum(features @ p[:count].reshape(inputs, width) + p[count:count + width], 0)
    logits = hidden @ p[count + width:count + 2 * width] + p[-1]
    return 1 / (1 + np.exp(-logits))


def bce(y, p):
    pc = np.clip(p, 1e-7, 1 - 1e-7)
    return float(np.mean(-(y * np.log(pc) + (1 - y) * np.log1p(-pc))))


def finite_loss_gradient(function, parameters, h=1e-6):
    gradient = np.empty_like(parameters)
    for i in range(len(parameters)):
        delta = np.zeros_like(parameters)
        delta[i] = h
        gradient[i] = (function(parameters + delta) - function(parameters - delta)) / (2 * h)
    return gradient


def measured_work(model, x, y, depth, route):
    calls = []
    original = C.predict

    def traced(inputs, bank, depths, encoding=False, beta=np.pi / 2):
        ds = np.broadcast_to(np.asarray(depths), (len(inputs),))
        calls.append((len(inputs), int(ds.sum()), bool(encoding)))
        return original(inputs, bank, depths, encoding=encoding, beta=beta)

    C.predict = traced
    try:
        _, _, _, declared = model.gradient(x, y, depth, route)
    finally:
        C.predict = original
    measured = {"circuit_examples": sum(z[0] for z in calls),
                "layer_applications": sum(z[1] for z in calls),
                "feature_rz_gates": sum(2 * z[1] for z in calls if z[2]),
                "readout_ry_gates": sum(z[0] for z in calls)}
    for key, value in measured.items():
        assert declared[key] == value, (model.method, key, declared[key], value)
    return {"observed_forward_function_calls": len(calls), "measured": measured, "declared": declared}


def main(output):
    before = source_hashes()
    rng = np.random.default_rng(730031)
    x = rng.uniform(-0.93, 0.96, (11, 2))
    y = rng.integers(0, 2, len(x))
    depth = np.array([1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 4])
    routes = {"all_banks": np.arange(len(x)) % 5,
              "imbalanced_with_empty_bank": np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3]),
              "one_bank_only": np.zeros(len(x), dtype=int)}
    checks = []
    expected_counts = dict(scheduled=16, min_depth2=16, untied_assigned=40, fixed1=4, fixed2=8,
                           fixed4=16, encoding1=4, readout1=5, hash40=40, kmeans40=40,
                           ensemble40=40, mlp41=41, mlp129=129)
    for method in S.METHODS:
        model = S.Model(method, 7301)
        assert len(model.parameters) == expected_counts[method]
        for state in ("registered_initialization", "generic_parameters"):
            if state == "generic_parameters":
                model.parameters = rng.uniform(-1.2, 1.2, model.parameters.shape)
                if method == "readout1":
                    model.parameters[-1] = 0.79
            parameters = model.parameters.copy()
            route = routes["all_banks"]
            oracle = (lambda z: independent_mlp(method, z, x, depth)) if model.is_mlp else (
                lambda z: independent_predictions(method, z, x, depth, route))
            expected = oracle(parameters)
            actual = model.predict(x, depth, route)
            probability_error = float(np.max(np.abs(expected - actual)))
            assert probability_error < 3e-12, (method, state, probability_error)
            assert np.min(expected) > 1e-5 and np.max(expected) < 1 - 1e-5
            loss, gradient, _, _ = model.gradient(x, y, depth, route)
            expected_gradient = finite_loss_gradient(lambda z: bce(y, oracle(z)), parameters)
            gradient_error = float(np.max(np.abs(gradient - expected_gradient)))
            assert gradient_error < 3e-7, (method, state, gradient_error)
            assert abs(loss - bce(y, expected)) < 3e-12
            checks.append({"method": method, "state": state, "parameters": len(parameters),
                           "maximum_probability_error": probability_error,
                           "maximum_loss_gradient_error": gradient_error})
    routing_checks = []
    for method in ("hash40", "kmeans40"):
        model = S.Model(method, 7301)
        for name, route in routes.items():
            oracle = lambda z: independent_predictions(method, z, x, depth, route)
            _, gradient, _, _ = model.gradient(x, y, depth, route)
            finite = finite_loss_gradient(lambda z: bce(y, oracle(z)), model.parameters)
            error = float(np.max(np.abs(gradient - finite)))
            assert error < 3e-7
            absent = [k for k in range(5) if k not in route]
            assert all(np.array_equal(gradient[k * 8:(k + 1) * 8], np.zeros(8)) for k in absent)
            routing_checks.append({"method": method, "fixture": name, "maximum_gradient_error": error,
                                   "absent_banks_with_exact_zero_gradient": absent})
    initial = {name: S.Model(name, 7301) for name in ("hash40", "kmeans40", "ensemble40", "fixed1", "readout1")}
    assert np.array_equal(initial["hash40"].parameters, initial["kmeans40"].parameters)
    assert np.array_equal(initial["hash40"].parameters, initial["ensemble40"].parameters)
    banks = initial["hash40"].parameters.reshape(5, 8)
    assert all(not np.array_equal(banks[i], banks[j]) for i in range(5) for j in range(i))
    assert initial["readout1"].parameters[-1] == np.pi / 2
    assert np.allclose(initial["readout1"].predict(x, depth), initial["fixed1"].predict(x, depth), atol=1e-14, rtol=0)
    work = {method: measured_work(S.Model(method, 7301), x, y, depth, routes["all_banks"])
            for method in S.METHODS}
    assert work["ensemble40"]["declared"]["circuit_examples"] == 5 * work["fixed2"]["declared"]["circuit_examples"]
    assert work["hash40"]["declared"]["circuit_examples"] == work["kmeans40"]["declared"]["circuit_examples"]
    grid = np.array([(a, b) for a in np.linspace(-1, 1, 9) for b in np.linspace(-1, 1, 9)])
    sensitivity = {}
    for name, p in {"zero": np.zeros(4), "small": np.array([.07, -.04, .08, .03]),
                    "broad": np.array([.37, -.52, .71, .43])}.items():
        bank = p.reshape(1, 2, 2)
        for variant, encoding, readout in (("fixed1", False, False), ("encoding1", True, False),
                                           ("readout1", False, True)):
            jac = C.jacobian(grid, bank, 1, encoding=encoding, train_readout=readout)
            actual = C.predict(grid, bank, 1, encoding=encoding)
            expected = encoded_analytic_half(grid, p) if encoding else A.analytic_d1(grid, p)
            assert np.max(np.abs(actual - expected)) < 3e-12
            analytic_jac = A.central_jacobian(lambda z: encoded_analytic_half(grid, z), p) if encoding else (
                A.analytic_d1_jacobian(grid, p, trainable_readout=readout))
            assert np.max(np.abs(jac - analytic_jac)) < 2e-8
            sensitivity[f"{name}/{variant}"] = A.jacobian_summary(jac)
    assert sensitivity["broad/fixed1"]["numerical_rank"] == 3
    assert sensitivity["broad/encoding1"]["numerical_rank"] == 4
    assert sensitivity["broad/readout1"]["numerical_rank"] == 4
    after = source_hashes()
    assert before == after, "Production source changed during review; preserve attempt and retry"
    result = {"status": "PASS", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "source_sha256": before, "scope": "Generated engineering fixtures only; no official population or model outcomes",
              "official_training_executed": False, "official_test_data_read": False,
              "model_cases": checks, "routing_normalization_cases": routing_checks,
              "initialization_checks": "PASS: common distinct five banks and readout pi/2 initial equivalence",
              "observed_work_checks": work, "label_independent_sensitivity": sensitivity,
              "maximum_probability_error": max(z["maximum_probability_error"] for z in checks),
              "maximum_loss_gradient_error": max(z["maximum_loss_gradient_error"] for z in checks),
              "numpy": np.__version__, "interpretation_limit": "Local numeric coverage is not a proof of global expressivity, trainability, quality or causal capacity isolation"}
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "models": len(S.METHODS), "cases": len(checks),
                      "maximum_probability_error": result["maximum_probability_error"],
                      "maximum_loss_gradient_error": result["maximum_loss_gradient_error"],
                      "output": str(output)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite previous audit evidence")
    attempt_source_hashes = source_hashes()
    try:
        main(args.output)
    except BaseException:
        failure = {"status": "FAIL", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "source_sha256_at_start": attempt_source_hashes,
                   "source_sha256_at_end": source_hashes(), "traceback": traceback.format_exc(),
                   "official_training_executed": False, "official_test_data_read": False}
        if not args.output.exists():
            args.output.write_text(json.dumps(failure, indent=2), encoding="utf-8")
        raise
