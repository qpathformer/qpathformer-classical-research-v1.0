"""Independent v0.3 inference: scalar tensor-product matrices and explicit MLP.

This module never imports the trainer, its circuit code, or its matrix oracle.
Logical basis is |q0 q1>; tensor products act on column state vectors.
"""
import hashlib
import math
import struct
import numpy as np

METHODS = ('scheduled', 'min_depth2', 'untied_assigned', 'fixed1', 'fixed2',
           'fixed4', 'encoding1', 'readout1', 'hash40', 'kmeans40',
           'ensemble40', 'mlp41', 'mlp129')
PARAMETERS = dict(zip(METHODS, (16, 16, 40, 4, 8, 16, 4, 5, 40, 40, 40, 41, 129)))
CONTROLLED_X = np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                         [0, 0, 0, 1], [0, 0, 1, 0]], dtype=np.complex128)


def rotation_y(angle):
    c, s = math.cos(float(angle) / 2), math.sin(float(angle) / 2)
    return np.array([[c, -s], [s, c]], dtype=np.complex128)


def rotation_z(angle):
    c, s = math.cos(float(angle) / 2), math.sin(float(angle) / 2)
    return np.array([[complex(c, -s), 0], [0, complex(c, s)]], dtype=np.complex128)


def circuit_probability(features, angles, depth, encoding=False, beta=math.pi / 2):
    """Construct separate local matrices, then tensor them before each CX."""
    state = np.array([1, 0, 0, 0], dtype=np.complex128)
    for layer in range(int(depth)):
        local = []
        for qubit in (0, 1):
            feature = rotation_y(math.pi * float(features[qubit]))
            if encoding:
                feature = rotation_z(math.pi * float(features[qubit]) / 2) @ feature
            local.append(rotation_z(angles[layer, qubit, 1]) @
                         rotation_y(angles[layer, qubit, 0]) @ feature)
        state = CONTROLLED_X @ (np.kron(local[0], local[1]) @ state)
    state = np.kron(rotation_y(beta), np.eye(2)) @ state
    probability = float((state.conj() * np.array([0, 0, 1, 1]) @ state).real)
    if not math.isfinite(probability) or not -1e-12 <= probability <= 1 + 1e-12:
        raise ValueError('Matrix probability outside numerical physical bounds')
    return min(1., max(0., probability))


def routes_from_policy(features, policy):
    """Independent application of immutable train-fitted centroids/hash cuts."""
    x = np.asarray(features, dtype=np.float64)
    centers = np.asarray(policy['centroids'], dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Finite two-feature records required')
    if centers.shape != (5, 2) or not np.isfinite(centers).all():
        raise ValueError('Five finite two-feature centroids required')
    if centers.tolist() != sorted(centers.tolist()):
        raise ValueError('Centroids are not lexicographically ordered')
    cuts = policy['hash_cutpoints_hex']
    if len(cuts) != 4 or cuts != sorted(set(cuts)) or any(len(c) != 64 for c in cuts):
        raise ValueError('Four unique ascending SHA256 cutpoints required')
    prefix = b'QPATH-V03-HASH5\0' + policy['hash_salt'].encode('ascii') + b'\0'
    geographic, hashed = [], []
    for row in x:
        distances = [float(np.dot(row - c, row - c)) for c in centers]
        geographic.append(min(range(5), key=lambda k: (distances[k], k)))
        key = struct.pack('<dd', *(0. if v == 0 else float(v) for v in row))
        digest = hashlib.sha256(prefix + key).hexdigest()
        hashed.append(sum(digest > cutoff for cutoff in cuts))
    return {'kmeans_route': np.asarray(geographic, dtype=np.int64),
            'hash_route': np.asarray(hashed, dtype=np.int64)}


def _mlp(parameters, features, depth, hidden):
    w1 = parameters[:6 * hidden].reshape(6, hidden)
    b1 = parameters[6 * hidden:7 * hidden]
    w2 = parameters[7 * hidden:8 * hidden]
    b2 = parameters[-1]
    probabilities = []
    for row, d in zip(features, depth):
        inputs = [float(row[0]), float(row[1])] + [float(k == int(d)) for k in (1, 2, 3, 4)]
        activated = [max(0., sum(inputs[i] * w1[i, j] for i in range(6)) + b1[j])
                     for j in range(hidden)]
        logit = float(sum(activated[j] * w2[j] for j in range(hidden)) + b2)
        # Stable logistic is algebraically the same as the trainer's sigmoid.
        probabilities.append(1 / (1 + math.exp(-logit)) if logit >= 0
                             else math.exp(logit) / (1 + math.exp(logit)))
    return np.asarray(probabilities)


def predict(method, parameters, features, original_depth, routes=None):
    if method not in METHODS:
        raise ValueError('Unregistered method')
    parameters = np.asarray(parameters, dtype=np.float64)
    x = np.asarray(features, dtype=np.float64)
    raw_depth = np.asarray(original_depth)
    if parameters.shape != (PARAMETERS[method],) or not np.isfinite(parameters).all():
        raise ValueError('Invalid parameter vector')
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Invalid features')
    if raw_depth.shape != (len(x),) or not np.isin(raw_depth, [1, 2, 3, 4]).all():
        raise ValueError('Invalid original depth')
    depth = raw_depth.astype(np.int64)
    if method.startswith('mlp'):
        return _mlp(parameters, x, depth, 5 if method == 'mlp41' else 16)
    if method in ('hash40', 'kmeans40'):
        route = np.asarray(routes[method[:-2] + '_route'])
        if route.shape != (len(x),) or not np.isin(route, range(5)).all():
            raise ValueError('Invalid fixed route')
    else:
        route = None
    result = []
    offsets = (0, 4, 12, 24, 40)
    for index, (row, d) in enumerate(zip(x, depth)):
        if method == 'ensemble40':
            values = [circuit_probability(row, parameters[k * 8:(k + 1) * 8].reshape(2, 2, 2), 2)
                      for k in range(5)]
            result.append(sum(values) / 5)
            continue
        if route is not None:
            k = int(route[index]); d = 2
            bank = parameters[k * 8:(k + 1) * 8].reshape(2, 2, 2)
        elif method == 'untied_assigned':
            bank = parameters[offsets[d - 1]:offsets[d]].reshape(d, 2, 2)
        else:
            angles = parameters[:4] if method == 'readout1' else parameters
            bank = angles.reshape(-1, 2, 2)
            if method in ('fixed1', 'encoding1', 'readout1'): d = 1
            elif method == 'fixed2': d = 2
            elif method == 'fixed4': d = 4
            elif method == 'min_depth2': d = max(2, d)
        result.append(circuit_probability(row, bank, d, method == 'encoding1',
                                         parameters[-1] if method == 'readout1' else math.pi / 2))
    return np.asarray(result, dtype=np.float64)
