"""Offline IBM/Qiskit adapter. This module never creates a cloud service.

Logical matrices use |q0 q1>; Qiskit arrays use |q1 q0>. Compilation
may also permute wires. Both input and output mappings are resolved explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class CompilerOptions:
    optimization_level: int = 1
    seed_transpiler: int = 311
    initial_layout: tuple[int, int] = (0, 1)


def build_circuit(x, bank, depth: int, *, measure: bool = False):
    """Build the v0.3.1 two-qubit circuit with q0 read into classical bit 0."""
    from qiskit import QuantumCircuit

    x = np.asarray(x, dtype=np.float64)
    bank = np.asarray(bank, dtype=np.float64)
    if x.shape != (2,) or not np.all(np.isfinite(x)):
        raise ValueError("x must contain two finite features")
    if bank.shape != (4, 2, 2) or not np.all(np.isfinite(bank)):
        raise ValueError("bank must be a finite [4,2,2] array")
    if isinstance(depth, bool) or int(depth) != depth or not 1 <= depth <= 4:
        raise ValueError("depth must be an integer in 1..4")
    circuit = QuantumCircuit(2, 1 if measure else 0)
    for layer in range(int(depth)):
        for q in range(2):
            circuit.ry(math.pi * float(x[q]), q)
        for q in range(2):
            circuit.ry(float(bank[layer, q, 0]), q)
            circuit.rz(float(bank[layer, q, 1]), q)
        circuit.cx(0, 1)
    circuit.ry(math.pi / 2, 0)
    if measure:
        circuit.measure(0, 0)
    return circuit


def compile_local(circuits, options: CompilerOptions = CompilerOptions()):
    """Compile locally to RY/RZ/CX; this is not a hardware ISA compile."""
    from qiskit import transpile

    if sorted(options.initial_layout) != [0, 1]:
        raise ValueError("initial_layout must be a permutation of two wires")
    if options.optimization_level not in range(4):
        raise ValueError("optimization_level must be 0..3")
    return transpile(
        circuits, basis_gates=["ry", "rz", "cx"],
        coupling_map=[[0, 1], [1, 0]],
        initial_layout=list(options.initial_layout),
        optimization_level=options.optimization_level,
        seed_transpiler=options.seed_transpiler, num_processes=1,
    )


def wire_mappings(circuit) -> dict:
    """Return logical-to-physical wire maps for both ends of the circuit."""
    if circuit.num_qubits != 2:
        raise ValueError("This capsule supports exactly two wires")
    if circuit.layout is None:
        initial, final = [0, 1], [0, 1]
    else:
        initial = list(circuit.layout.initial_index_layout(filter_ancillas=True))
        final = list(circuit.layout.final_index_layout(filter_ancillas=True))
    if sorted(initial) != [0, 1] or sorted(final) != [0, 1]:
        raise ValueError("Unexpected wire/ancilla mapping")
    return {"initial_logical_to_physical": initial,
            "final_logical_to_physical": final,
            "logical_basis": "|q0 q1>",
            "qiskit_array_basis": "|physical1 physical0>"}


def _logical_indices(mapping: Sequence[int]) -> list[int]:
    # Logical index bits are (q0, q1), whereas Qiskit bit p has weight 2**p.
    return [((j >> 1) & 1) * (1 << mapping[0])
            + (j & 1) * (1 << mapping[1]) for j in range(4)]


def logical_unitary(circuit) -> np.ndarray:
    """Resolve endianness and compiler input/output wire permutations."""
    from qiskit.quantum_info import Operator

    if circuit.num_clbits or any(i.operation.name in {"measure", "reset"}
                                 for i in circuit.data):
        raise ValueError("Unitary checks exclude measurement and reset")
    mapping = wire_mappings(circuit)
    raw = np.asarray(Operator(circuit).data, dtype=np.complex128)
    rows = _logical_indices(mapping["final_logical_to_physical"])
    columns = _logical_indices(mapping["initial_logical_to_physical"])
    return raw[np.ix_(rows, columns)]


def aligned_error(reference: np.ndarray, candidate: np.ndarray) -> float:
    z = np.trace(reference.conj().T @ candidate)
    if abs(z) <= 1e-12:
        raise ValueError("Global phase alignment failed")
    return float(np.max(np.abs(reference - candidate * z.conjugate() / abs(z))))


def probability_one(unitary: np.ndarray) -> float:
    return float(np.sum(np.abs(unitary[2:4, 0]) ** 2))


def local_counts(circuits, shots: int, seed: int):
    """Ideal, offline Aer sampling; measurement of logical q0 must map to c0."""
    from qiskit_aer import AerSimulator

    if isinstance(shots, bool) or not isinstance(shots, int) or not 1 <= shots <= 4096:
        raise ValueError("Local shot count must be an integer in 1..4096")
    circuits = list(circuits)
    if not circuits or len(circuits) > 64:
        raise ValueError("A local batch must contain 1..64 circuits")
    for circuit in circuits:
        if circuit.num_qubits != 2 or circuit.num_clbits != 1:
            raise ValueError("Expected two qubits and one measured classical bit")
    backend = AerSimulator(method="statevector", device="CPU", precision="double",
                           max_parallel_threads=1, max_parallel_experiments=1)
    result = backend.run(circuits, shots=shots, seed_simulator=int(seed)).result()
    if not result.success:
        raise RuntimeError("Aer failed")
    counts = [dict(result.get_counts(i)) for i in range(len(circuits))]
    for item in counts:
        if sum(item.values()) != shots or set(item) - {"0", "1"}:
            raise RuntimeError("Unexpected readout counts")
    return counts


def hardware_draft(circuit_count: int) -> dict:
    """Prepare an inert planning record, without credential or network access."""
    if not 1 <= circuit_count <= 8:
        raise ValueError("Initial hardware pilot is limited to 1..8 circuits")
    return {
        "status": "DRAFT_NOT_SUBMITTED", "provider": "IBM Quantum",
        "cloud_submission_enabled": False, "backend": None,
        "credential_accessed": False, "network_requests": 0,
        "limits_proposed": {"max_jobs": 1, "max_circuits": 8,
                            "shots_per_circuit": 1024, "max_total_shots": 8192},
        "requested_circuit_count": circuit_count,
        "remaining_before_hardware": [
            "Choose an available IBM backend and approved account/instance.",
            "Record backend calibration/target and pricing or allocation.",
            "Compile to that backend ISA and verify logical-to-physical mapping.",
            "Review the exact circuit payload, budget and data release.",
            "Implement and test a separate explicit submission command.",
        ],
    }
