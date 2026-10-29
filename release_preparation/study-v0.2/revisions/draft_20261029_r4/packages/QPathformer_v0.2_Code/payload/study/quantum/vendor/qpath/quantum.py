"""NumPy production circuit, logical basis |q0 q1>, complex128.

No network or hardware calls. The shared prefix bank has [layer, qubit, RY/RZ]
axes; each layer applies encoding RY, trainable RY/RZ, then CX(0, 1).
"""
from __future__ import annotations

import numpy as np

DTYPE = np.complex128
CLIP = 1e-7


def class_depth(classes):
    c = np.asarray(classes)
    if np.any((c < 1) | (c > 8)) or np.any(c != c.astype(int)):
        raise ValueError("Synthetic classes must be integers 1..8")
    return 5 - (c.astype(int) + 1) // 2


def _inputs(x, bank, depth):
    x = np.asarray(x, dtype=np.float64)
    bank = np.asarray(bank, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError("x must be finite [N,2]")
    if bank.ndim != 3 or bank.shape[1:] != (2, 2) or not 1 <= len(bank) <= 4:
        raise ValueError("bank must have shape [1..4,2,2]")
    if not np.isfinite(bank).all():
        raise ValueError("bank contains non-finite values")
    raw = np.broadcast_to(np.asarray(depth), (len(x),))
    d = raw.astype(int)
    if np.any(raw != d) or np.any(d < 1) or np.any(d > len(bank)):
        raise ValueError("depth must be integer, 1..number of bank layers")
    return x, bank, d


def _ry(state, theta, qubit):
    theta = np.broadcast_to(np.asarray(theta), (len(state),))
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    pairs = ((0, 2), (1, 3)) if qubit == 0 else ((0, 1), (2, 3))
    for i, j in pairs:
        a, b = state[:, i].copy(), state[:, j].copy()
        state[:, i], state[:, j] = c * a - s * b, s * a + c * b


def _rz(state, theta, qubit):
    minus = np.exp(-0.5j * theta)
    plus = np.exp(0.5j * theta)
    zero, one = ((0, 1), (2, 3)) if qubit == 0 else ((0, 2), (1, 3))
    state[:, zero] *= minus
    state[:, one] *= plus


def _evolve(x, bank, d, state):
    for layer in range(len(bank)):
        active = np.flatnonzero(d > layer)
        if not len(active):
            break
        a = state[active].copy()
        for qubit in (0, 1):
            _ry(a, np.pi * x[active, qubit], qubit)
            _ry(a, bank[layer, qubit, 0], qubit)
            _rz(a, bank[layer, qubit, 1], qubit)
        a = a[:, [0, 1, 3, 2]]  # CX(q0, q1)
        state[active] = a
    _ry(state, np.pi / 2, 0)
    return state


def predict_proba(x, bank, depth):
    """Return P(q0=1) for each row; depth is a scalar or [N] array."""
    x, bank, d = _inputs(x, bank, depth)
    state = np.zeros((len(x), 4), dtype=DTYPE)
    state[:, 0] = 1
    state = _evolve(x, bank, d, state)
    return np.clip(np.sum(np.abs(state[:, 2:]) ** 2, axis=1), 0.0, 1.0)


def unitary(x, bank, d):
    """Return the complete 4x4 unitary, with input basis states as columns."""
    x = np.asarray(x, dtype=float)
    if x.shape != (2,):
        raise ValueError("x must be [2]")
    xx, bank, depth = _inputs(np.repeat(x[None], 4, axis=0), bank, d)
    return _evolve(xx, bank, depth, np.eye(4, dtype=DTYPE)).T


def probability_gradient(x, bank, depth):
    """Exact parameter-shift gradient of probability (not finite differences).

    Each angle appears once per circuit. Inactive prefix parameters have an
    exactly zero derivative. Returns [N,layers,2,2] and evaluated circuit count.
    """
    x, bank, d = _inputs(x, bank, depth)
    gradient = np.zeros((len(x),) + bank.shape, dtype=np.float64)
    count = 0
    for layer in range(len(bank)):
        active = np.flatnonzero(d > layer)
        for q in (0, 1):
            for axis in (0, 1):
                plus, minus = bank.copy(), bank.copy()
                plus[layer, q, axis] += np.pi / 2
                minus[layer, q, axis] -= np.pi / 2
                if len(active):
                    gradient[active, layer, q, axis] = 0.5 * (
                        predict_proba(x[active], plus, d[active])
                        - predict_proba(x[active], minus, d[active])
                    )
                    count += 2 * len(active)
    return gradient, count


def binary_cross_entropy(y, p):
    y, p = np.asarray(y), np.asarray(p)
    pc = np.clip(p, CLIP, 1 - CLIP)
    return float(-np.mean(y * np.log(pc) + (1 - y) * np.log1p(-pc)))


def loss_gradient(x, y, bank, depth):
    p = predict_proba(x, bank, depth)
    dp, count = probability_gradient(x, bank, depth)
    pc = np.clip(p, CLIP, 1 - CLIP)
    chain = (pc - y) / (pc * (1 - pc))
    # Differentiate the declared clipped loss, not an unclipped surrogate.
    chain[(p < CLIP) | (p > 1 - CLIP)] = 0
    grad = np.mean(dp * chain[:, None, None, None], axis=0)
    return binary_cross_entropy(y, p), grad, p, count + len(p)


class Adam:
    """Explicit float64 Adam, constant LR, zero weight decay."""
    def __init__(self, shape, lr=0.01):
        self.m = np.zeros(shape, dtype=np.float64)
        self.v = np.zeros(shape, dtype=np.float64)
        self.t, self.lr = 0, lr

    def step(self, parameters, gradient):
        self.t += 1
        self.m = 0.9 * self.m + 0.1 * gradient
        self.v = 0.999 * self.v + 0.001 * gradient ** 2
        parameters -= self.lr * (self.m / (1 - 0.9 ** self.t)) / (
            np.sqrt(self.v / (1 - 0.999 ** self.t)) + 1e-8
        )

