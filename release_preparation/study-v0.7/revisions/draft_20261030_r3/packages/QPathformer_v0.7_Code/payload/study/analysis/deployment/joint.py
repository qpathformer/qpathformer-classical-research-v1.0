"""Logical ideal joint-probability and equal-total-shot producer kernels.

Outcome order is |q0 q1> = 00,01,10,11. Counts within each setting remain joint;
therefore X0/X1 or Z0/Z1/Z0Z1 covariance is retained.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'quantum'))
import circuits
from models import sigmoid

OUTCOMES=('00','01','10','11')
SIGNS=np.asarray([[1.,1.,-1.,-1.],[1.,-1.,1.,-1.],[1.,-1.,-1.,1.]])
H=np.asarray([[1.,1.],[1.,-1.]])/np.sqrt(2.)
HX=np.kron(H,H)

def joint_probabilities(x,core):
    state=circuits.core_state(x,core)
    xx=np.abs(state@HX.T)**2;zz=np.abs(state)**2
    # Numerical normalization is explicit; no count-dependent adaptation.
    xx=np.maximum(xx,0.);zz=np.maximum(zz,0.)
    xx/=xx.sum(axis=1,keepdims=True);zz/=zz.sum(axis=1,keepdims=True)
    return {'XX':xx,'ZZ':zz}

def model_joint(model,x,route):
    if model.method not in ('qscalar_kmeans','qmulti_kmeans','qmulti_hash'):raise ValueError('Circuit model required')
    settings=('XX',) if model.moment_count==1 else ('XX','ZZ')
    result={s:np.empty((len(x),4),dtype=np.float64) for s in settings}
    heads=np.empty((len(x),model.moment_count+1),dtype=np.float64)
    for ids,bank,sl in model.components(x,route):
        theta=model.parameters[sl];value=joint_probabilities(np.asarray(x)[ids],theta[:8].reshape(2,2,2))
        for setting in settings:result[setting][ids]=value[setting]
        heads[ids]=theta[8:]
    return result,heads

def moments_from_joint(joints,moment_count):
    xx=np.asarray(joints['XX'],dtype=np.float64)@SIGNS.T
    if moment_count==1:return xx[:,:1]
    if moment_count!=5 or 'ZZ' not in joints:raise ValueError('Five moments need joint XX and ZZ')
    zz=np.asarray(joints['ZZ'],dtype=np.float64)@SIGNS.T
    return np.column_stack((xx[:,0],xx[:,1],zz[:,0],zz[:,1],zz[:,2]))

def predict_from_joint(joints,heads):
    heads=np.asarray(heads,dtype=np.float64)
    if heads.ndim!=2 or heads.shape[1] not in (2,6):raise ValueError('Head shape')
    moments=moments_from_joint(joints,heads.shape[1]-1)
    logits=np.einsum('ni,ni->n',moments,heads[:,:-1])+heads[:,-1]
    return sigmoid(logits),logits,moments

def technical_stream(run_id,total_budget,setting,technical_seed_id):
    if total_budget not in (1024,8192) or setting not in ('XX','ZZ') or technical_seed_id not in range(20):
        raise ValueError('Unregistered shot stream')
    namespace=f'QPATH-v0.7-shots-v1|{run_id}|{total_budget}|{setting}|{technical_seed_id}'
    value=int.from_bytes(hashlib.sha256(namespace.encode('ascii')).digest()[:16],'little')
    return {'namespace':namespace,'uint128_decimal':str(value)}

def draw_counts(probabilities,total_budget,setting,repeat,run_id,scalar):
    probabilities=np.asarray(probabilities,dtype=np.float64)
    if probabilities.ndim!=2 or probabilities.shape[1]!=4 or not np.isfinite(probabilities).all() or np.any(probabilities<0):
        raise ValueError('Invalid joint probabilities')
    if not np.allclose(probabilities.sum(axis=1),1,atol=2e-14,rtol=0):raise ValueError('Joint normalization')
    if scalar and setting!='XX':raise ValueError('Scalar has one XX setting')
    shots=total_budget if scalar else total_budget//2
    stream=technical_stream(run_id,total_budget,setting,repeat)
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(int(stream['uint128_decimal']))))
    counts=np.asarray([rng.multinomial(shots,row) for row in probabilities],dtype=np.int64)
    if not np.all(counts.sum(axis=1)==shots):raise RuntimeError('Count conservation')
    return counts,shots,stream

def conditional_diagnostics(draws,ideal):
    draws=np.asarray(draws,dtype=np.float64);ideal=np.asarray(ideal,dtype=np.float64)
    if draws.shape!=(20,len(ideal)) or not np.isfinite(draws).all():raise ValueError('Expected 20 fixed technical repeats')
    error=draws-ideal[None,:]
    bias=error.mean(axis=0);variance=draws.var(axis=0,ddof=0)
    return {'records':len(ideal),'technical_repeats':20,
        'mean_probability_absolute_error':float(np.mean(np.abs(error))),
        'mean_probability_squared_error':float(np.mean(error**2)),
        'mean_signed_probability_error':float(error.mean()),
        'mean_per_record_squared_bias':float(np.mean(bias**2)),
        'mean_per_record_technical_variance_population_ddof0':float(np.mean(variance)),
        'decision_disagreements':int(np.sum((draws>=.5)!=(ideal[None,:]>=.5))),
        'bias_per_record':bias.tolist(),'variance_per_record':variance.tolist(),
        'mse_per_record':np.mean(error**2,axis=0).tolist(),
        'scope':'Conditional technical sampling around each own ideal checkpoint; repeats and records are not independent learned-model replicates.'}
