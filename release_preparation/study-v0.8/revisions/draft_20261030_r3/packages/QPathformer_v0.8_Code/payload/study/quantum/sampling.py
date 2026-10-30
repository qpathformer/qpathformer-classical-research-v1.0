"""Frozen v0.8 sampling law and importance weights; no data loader or RNG globals."""
from __future__ import annotations
import numpy as np

WARMUP_ROUNDS=10
LOSS_CAP=5.0
EPSILON=0.001
UNIFORM_MIXTURE=0.5


def priority_distribution(losses):
    losses=np.asarray(losses,dtype=np.float64)
    if losses.ndim!=1 or not len(losses) or not np.isfinite(losses).all() or np.any(losses<0):
        raise ValueError('Finite nonnegative native BCE vector required')
    scores=np.sqrt(np.minimum(losses,LOSS_CAP)+EPSILON)
    probabilities=UNIFORM_MIXTURE/len(losses)+(1-UNIFORM_MIXTURE)*scores/scores.sum()
    if np.any(probabilities<0.5/len(losses)) or abs(probabilities.sum()-1)>2e-14:
        raise RuntimeError('Priority distribution violates registered bounds')
    return scores,probabilities


def selected_distribution(n,current_round,policy,proposed=None):
    if n<1 or current_round<1 or policy not in ('U','P'):
        raise ValueError('Invalid sample policy/round/count')
    if current_round<=WARMUP_ROUNDS or policy=='U':
        return np.full(n,1.0/n,dtype=np.float64)
    p=np.asarray(proposed,dtype=np.float64)
    if p.shape!=(n,) or not np.isfinite(p).all() or np.any(p<0.5/n) or abs(p.sum()-1)>2e-14:
        raise ValueError('Missing/invalid refreshed priority probabilities')
    return p.copy()


def inverse_cdf_draws(probabilities,uniforms):
    p=np.asarray(probabilities,dtype=np.float64);u=np.asarray(uniforms,dtype=np.float64)
    if p.ndim!=1 or not len(p) or not np.isfinite(p).all() or np.any(p<=0) or abs(p.sum()-1)>2e-14:
        raise ValueError('Positive normalized probability vector required')
    if u.ndim!=1 or not np.isfinite(u).all() or np.any(u<0) or np.any(u>=1):
        raise ValueError('One-dimensional uniforms must be in [0,1)')
    cdf=np.cumsum(p,dtype=np.float64)
    cdf[-1]=1.0
    positions=np.searchsorted(cdf,u,side='right').astype(np.int64)
    weights=1.0/(len(p)*p[positions])
    if np.any(positions>=len(p)) or not np.isfinite(weights).all():
        raise RuntimeError('Invalid inverse-CDF result')
    return positions,weights


def diagnostics(p,weights,counts):
    p=np.asarray(p,dtype=np.float64);weights=np.asarray(weights,dtype=np.float64)
    counts=np.asarray(counts)
    return {'minimum_probability':float(p.min()),'maximum_probability':float(p.max()),
            'probability_entropy_nats':float(-np.sum(p*np.log(p))),
            'distribution_effective_records':float(1.0/np.sum(p*p)),
            'minimum_sampled_weight':float(weights.min()),'maximum_sampled_weight':float(weights.max()),
            'mean_sampled_weight':float(weights.mean()),
            'sampled_weight_effective_count':float(weights.sum()**2/np.sum(weights*weights)),
            'unique_records_drawn':int(np.count_nonzero(counts)),
            'maximum_record_multiplicity':int(counts.max()),
            'draws_with_replacement':int(counts.sum()),
            'weight_rule':'1/(N*p_i), raw per-record gradient then arithmetic batch mean; no normalization or clipping'}
