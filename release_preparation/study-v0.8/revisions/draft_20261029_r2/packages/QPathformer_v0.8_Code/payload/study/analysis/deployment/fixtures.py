"""Label-free, preregistered conversion probes; never select by outcomes."""
from __future__ import annotations
import numpy as np


def parity_inputs(policy, boundary_stream):
    """128 deterministic off-grid points plus true clipped Voronoi edges."""
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(int(boundary_stream))))
    offgrid = rng.uniform(-1, 1, (128, 2))
    centers = np.asarray(policy["centroids"], dtype=np.float64)
    if centers.shape != (5, 2):
        raise ValueError("Five frozen centroids required")
    points, records = [], []
    for i in range(5):
        for j in range(i + 1, 5):
            delta = centers[j] - centers[i]
            norm = float(np.linalg.norm(delta))
            if norm <= 0:
                raise ValueError("Distinct centroids required")
            direction = np.array([-delta[1], delta[0]]) / norm
            mid = (centers[i] + centers[j]) / 2
            constraints = []
            for axis in range(2):
                unit = np.eye(2)[axis]
                constraints.extend(((unit, 1.), (-unit, 1.)))
            for k in range(5):
                if k not in (i, j):
                    constraints.append((2 * (centers[k] - centers[i]),
                                        float(centers[k] @ centers[k] - centers[i] @ centers[i])))
            lo, hi, valid = -float("inf"), float("inf"), True
            for a, b in constraints:
                slope, remaining = float(a @ direction), float(b - a @ mid)
                if abs(slope) < 1e-14:
                    if remaining < -1e-12:
                        valid = False
                        break
                elif slope > 0:
                    hi = min(hi, remaining / slope)
                else:
                    lo = max(lo, remaining / slope)
            if not valid or not np.isfinite([lo, hi]).all() or hi - lo <= 1e-12:
                continue
            edge = mid + ((lo + hi) / 2) * direction
            for side in (-1, 0, 1):
                points.append(edge + side * 1e-10 * delta / norm)
                records.append({"centroid_pair": [i, j], "side": side, "normal_offset": side * 1e-10})
    return offgrid, np.asarray(points, dtype=np.float64).reshape(-1, 2), records


def parity(probability, logits, reference_probability, reference_logits, ids=None):
    """Report every class disagreement; accept only floating-point tie bands."""
    p, z, rp, rz = [np.asarray(v) for v in
                     (probability, logits, reference_probability, reference_logits)]
    if p.shape != z.shape or p.shape != rp.shape or p.shape != rz.shape or not p.size:
        raise ValueError("Nonempty matching parity arrays required")
    if not all(np.isfinite(v).all() for v in (p, z, rp, rz)):
        raise ValueError("Nonfinite parity arrays")
    pe, ze = float(np.max(abs(p - rp))), float(np.max(abs(z - rz)))
    if pe > 2e-12 or ze > 1e-9:
        raise RuntimeError("Coefficient transform exceeds frozen parity tolerances")
    different = (p >= .5) != (rp >= .5)
    tie_band = 32 * np.finfo(np.float64).eps
    band = (abs(p - .5) <= tie_band) & (abs(rp - .5) <= tie_band)
    if np.any(different & ~band):
        raise RuntimeError("Class disagreement outside joint floating-point tie band")
    ids = np.arange(len(p)) if ids is None else np.asarray(ids)
    return {"records": len(p), "maximum_probability_error": pe, "maximum_logit_error": ze,
            "class_disagreements": int(different.sum()),
            "decision_tie_band": float(tie_band),
            "canonical_near_band": int(np.sum(abs(rp - .5) <= tie_band)),
            "transformed_near_band": int(np.sum(abs(p - .5) <= tie_band)),
            "disagreements": [{"record_id": int(ids[i]), "canonical_probability": float(rp[i]),
                               "transformed_probability": float(p[i])}
                              for i in np.flatnonzero(different)]}
