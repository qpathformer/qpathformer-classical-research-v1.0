"""Independent dense-state/Laurent oracle; no producer, trainer or data imports."""
from __future__ import annotations
import bisect
import hashlib
import numpy as np

I = np.eye(2, dtype=np.complex128)
X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
Z = np.diag([1., -1.]).astype(np.complex128)
H = np.array([[1, 1], [1, -1]], dtype=np.complex128)/np.sqrt(2.)
CX = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]],
              dtype=np.complex128)
OBSERVABLES = (np.kron(X, I), np.kron(I, X), np.kron(Z, I), np.kron(I, Z), np.kron(Z, Z))
SIGNS = np.array([[1, 1, -1, -1], [1, -1, 1, -1], [1, -1, -1, 1]], dtype=np.int64)


def rotation_y(angle):
    c, s = np.cos(angle/2), np.sin(angle/2)
    return np.array([[c, -s], [s, c]], dtype=np.complex128)


def rotation_z(angle):
    return np.diag(np.exp(np.array([-.5j, .5j])*angle))


def local(gate, qubit):
    return np.kron(gate, I) if qubit == 0 else np.kron(I, gate)


def core_checked(core):
    core = np.asarray(core, dtype=np.float64)
    if core.shape != (2, 2, 2) or not np.isfinite(core).all():
        raise ValueError("Independent oracle requires a finite two-layer core")
    return core


def dense_states(inputs, core):
    """Explicit Kronecker matrices, no vectorized producer gate operations."""
    x = np.asarray(inputs, dtype=np.float64)
    core = core_checked(core)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError("Finite two-coordinate inputs required")
    output = []
    for point in x:
        state = np.array([1, 0, 0, 0], dtype=np.complex128)
        for layer in range(2):
            for qubit in range(2):
                unitary = rotation_z(core[layer, qubit, 1]) @ rotation_y(core[layer, qubit, 0]) @ rotation_y(np.pi*point[qubit])
                state = local(unitary, qubit) @ state
            state = CX @ state
        output.append(state)
    return np.asarray(output).reshape(len(x), 4)


def dense_moments(inputs, core):
    state = dense_states(inputs, core)
    return np.column_stack([np.einsum("ni,ij,nj->n", state.conj(), observable, state).real
                            for observable in OBSERVABLES])


def amplitude_laurent(core):
    """State coefficients at exp(i*pi/2*(k0*x0+k1*x1)); no sampling/projection."""
    core = core_checked(core)
    polynomial = {(0, 0): np.array([1, 0, 0, 0], dtype=np.complex128)}
    # RY(feature) = plus*exp(i*pi*x/2) + minus*exp(-i*pi*x/2).
    plus = np.array([[.5, .5j], [-.5j, .5]], dtype=np.complex128)
    minus = plus.conj()
    for layer in range(2):
        for qubit in range(2):
            next_poly = {}
            for powers, amplitude in polynomial.items():
                for shift, gate in ((1, plus), (-1, minus)):
                    key = list(powers)
                    key[qubit] += shift
                    key = tuple(key)
                    next_poly.setdefault(key, np.zeros(4, dtype=np.complex128))
                    next_poly[key] += local(gate, qubit) @ amplitude
            fixed = local(rotation_z(core[layer, qubit, 1]) @ rotation_y(core[layer, qubit, 0]), qubit)
            polynomial = {key: fixed @ value for key, value in next_poly.items()}
        polynomial = {key: CX @ value for key, value in polynomial.items()}
    return polynomial


def laurent_logits(core, head):
    """Bra/ket polynomial convolution produces integer Fourier frequencies -2..2."""
    head = np.asarray(head, dtype=np.float64)
    if head.shape not in ((2,), (6,)) or not np.isfinite(head).all():
        raise ValueError("Scalar or five-moment affine head required")
    count = len(head)-1
    polynomial = amplitude_laurent(core)
    observable = sum(weight*op for weight, op in zip(head[:-1], OBSERVABLES[:count]))
    coefficients = np.zeros((5, 5), dtype=np.complex128)
    for left_powers, left in polynomial.items():
        for right_powers, right in polynomial.items():
            difference = np.asarray(right_powers)-left_powers
            if np.any(difference % 2):
                raise RuntimeError("Unexpected half-integer observable frequency")
            frequency = difference//2
            if np.any(abs(frequency) > 2):
                raise RuntimeError("Unexpected support outside declared25-term basis")
            coefficients[frequency[0]+2, frequency[1]+2] += np.vdot(left, observable @ right)
    coefficients[2, 2] += head[-1]
    return coefficients


def real_coefficients(core, head):
    """Algebraic Laurent-to-real change of basis, rowmajor x0 then x1."""
    fourier = laurent_logits(core, head)
    inverse = np.zeros((5, 5), dtype=np.complex128)
    inverse[0, 2] = 1.
    for n in (1, 2):
        inverse[2*n-1, 2+n] = inverse[2*n-1, 2-n] = 1.
        inverse[2*n, 2+n], inverse[2*n, 2-n] = 1j, -1j
    coefficients = inverse @ fourier @ inverse.T
    if np.max(abs(coefficients.imag)) > 2e-12:
        raise RuntimeError("Real-logit polynomial has an imaginary coefficient residual")
    return coefficients.real.reshape(25)


def feature_matrix(inputs):
    x = np.asarray(inputs, dtype=np.float64)
    axes = [np.column_stack((np.ones(len(x)), np.cos(np.pi*x[:, q]), np.sin(np.pi*x[:, q]),
                             np.cos(2*np.pi*x[:, q]), np.sin(2*np.pi*x[:, q]))) for q in range(2)]
    return np.einsum("ni,nj->nij", axes[0], axes[1]).reshape(len(x), 25)


def sigmoid(logits):
    z = np.asarray(logits, dtype=np.float64)
    # tanh expression is algebraically independent of producer's branchwise exp.
    return .5*(1+np.tanh(z/2))










def route(inputs, policy, kind):
    """Separately implemented immutable geometric/hash routing."""
    x = np.asarray(inputs, dtype="<f8").copy()
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError("Finite two-coordinate inputs required")
    x[x == 0] = 0.
    if kind == "kmeans":
        centers = np.asarray(policy["centroids"], dtype=np.float64)
        return np.array([min(range(5), key=lambda k: float(np.sum((point-centers[k])**2))) for point in x], dtype=np.int64)
    if kind == "hash":
        prefix = b"QPATH-V08-HASH5\x00" + policy["hash_salt"].encode("ascii") + b"\x00"
        cutpoints = policy["hash_cutpoints_hex"]
        digests = [hashlib.sha256(prefix+point.tobytes()).hexdigest() for point in x]
        return np.asarray([bisect.bisect_left(cutpoints, value) for value in digests], dtype=np.int64)
    raise ValueError("Unknown route policy")


def registered_parity_inputs(policy, boundary_stream):
    """Independent polygon-vertex reconstruction of clipped Voronoi edge probes."""
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(int(boundary_stream))))
    offgrid = rng.uniform(-1, 1, (128, 2))
    centers = np.asarray(policy["centroids"], dtype=np.float64)
    points, metadata = [], []
    for i in range(5):
        for j in range(i+1, 5):
            normal = centers[j]-centers[i]
            norm = np.sqrt(np.dot(normal, normal))
            if norm <= 0:
                raise ValueError("Distinct centroids required")
            direction = np.array([-normal[1], normal[0]])/norm
            equality = 2*normal
            target = np.dot(centers[j], centers[j])-np.dot(centers[i], centers[i])
            other_lines = [(np.array([1., 0]), -1.), (np.array([1., 0]), 1.),
                           (np.array([0., 1]), -1.), (np.array([0., 1]), 1.)]
            other_lines.extend((2*(centers[k]-centers[i]),
                                np.dot(centers[k], centers[k])-np.dot(centers[i], centers[i]))
                               for k in range(5) if k not in (i, j))
            vertices = []
            for line, rhs in other_lines:
                determinant = equality[0]*line[1]-equality[1]*line[0]
                if abs(determinant) < 1e-14:
                    continue
                x = np.array([(target*line[1]-equality[1]*rhs)/determinant,
                              (equality[0]*rhs-target*line[0])/determinant])
                distances = np.sum((centers-x)**2, axis=1)
                if np.max(abs(x)) <= 1+1e-12 and np.all(distances[i] <= distances+1e-12):
                    vertices.append(x)
            if len(vertices) < 2:
                continue
            ordered = sorted(vertices, key=lambda point: float(point@direction))
            if float((ordered[-1]-ordered[0])@direction) <= 1e-12:
                continue
            midpoint = (ordered[0]+ordered[-1])/2
            for side in (-1, 0, 1):
                points.append(midpoint+side*1e-10*normal/norm)
                metadata.append({"centroid_pair": [i, j], "side": side, "normal_offset": side*1e-10})
    return offgrid, np.asarray(points).reshape(-1, 2), metadata
