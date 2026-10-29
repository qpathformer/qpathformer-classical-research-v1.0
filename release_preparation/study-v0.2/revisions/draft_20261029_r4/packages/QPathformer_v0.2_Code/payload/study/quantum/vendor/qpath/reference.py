"""Independent explicit 4x4 circuit reference; no production gate imports."""
from __future__ import annotations

import numpy as np


def unitary(x, bank, d):
    """Column-state multiplication, basis |q0 q1>; later gates on the left."""
    def ry(angle):
        c, s = np.cos(angle / 2), np.sin(angle / 2)
        return np.array([[c, -s], [s, c]], dtype=np.complex128)

    def rz(angle):
        return np.array([[np.exp(-1j * angle / 2), 0],
                         [0, np.exp(1j * angle / 2)]], dtype=np.complex128)

    ident = np.eye(2, dtype=np.complex128)
    cx = np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                   [0, 0, 0, 1], [0, 0, 1, 0]], dtype=np.complex128)
    result = np.eye(4, dtype=np.complex128)
    for layer in range(int(d)):
        for q in (0, 1):
            for gate in (ry(np.pi * x[q]), ry(bank[layer, q, 0]), rz(bank[layer, q, 1])):
                expanded = np.kron(gate, ident) if q == 0 else np.kron(ident, gate)
                result = expanded @ result
        result = cx @ result
    return np.kron(ry(np.pi / 2), ident) @ result


def align_and_error(reference, candidate):
    z = np.trace(reference.conj().T @ candidate)
    if abs(z) <= 1e-12:
        raise ValueError("Global phase alignment failed: near-zero overlap")
    return float(np.max(np.abs(reference - candidate * np.conj(z) / abs(z))))


def analytic_one_layer(x, bank):
    a0, a1 = np.pi * x[0] + bank[0, 0, 0], np.pi * x[1] + bank[0, 1, 0]
    b0, b1 = bank[0, 0, 1], bank[0, 1, 1]
    return float((1 + np.sin(a0) * np.cos(b0) * np.sin(a1) * np.cos(b1)) / 2)


def bounded_checks():
    """3240 grid/class/seed checks, plus analytic and paired-class invariants."""
    from . import quantum  # used only by verifier; reference unitary is independent

    grid = np.linspace(-1, 1, 9)
    count, analytic_count, pair_count = 0, 0, 0
    max_unitary, max_probability, max_analytic, max_pair = 0.0, 0.0, 0.0, 0.0
    banks = {}
    for seed in range(301, 306):
        bank = np.random.Generator(np.random.PCG64(seed)).uniform(-np.pi, np.pi, (4, 2, 2))
        banks[str(seed)] = bank.tolist()
        for a in grid:
            for b in grid:
                x = np.array([a, b])
                predictions = []
                for c in range(1, 9):
                    d = 5 - (c + 1) // 2
                    ref = unitary(x, bank, d)
                    candidate = quantum.unitary(x, bank, d)
                    max_unitary = max(max_unitary, align_and_error(ref, candidate))
                    expected = float(np.sum(np.abs(ref[2:, 0]) ** 2))
                    actual = float(quantum.predict_proba(x[None], bank, d)[0])
                    max_probability = max(max_probability, abs(expected - actual))
                    predictions.append(actual)
                    count += 1
                max_analytic = max(max_analytic, abs(predictions[-1] - analytic_one_layer(x, bank)))
                analytic_count += 1
                for k in (0, 2, 4, 6):
                    max_pair = max(max_pair, abs(predictions[k] - predictions[k + 1]))
                    pair_count += 1
    errors = [max_unitary, max_probability, max_analytic, max_pair]
    return {"status": "pass" if max(errors) <= 1e-10 else "fail",
            "bounded_comparisons": count, "analytic_checks": analytic_count,
            "pair_checks": pair_count, "max_unitary_error": max_unitary,
            "max_probability_error": max_probability, "max_analytic_error": max_analytic,
            "max_pair_error": max_pair, "tolerance": 1e-10,
            "bank_seeds": list(range(301, 306)), "angle_banks": banks,
            "claim": "Finite numerical coverage, not a proof over continuous inputs."}

