"""Standalone priority/importance reference; imports no scientific producer."""
import math
import numpy as np

WARMUP_ROUNDS=10
UNIFORM_MIXTURE=.5
LOSS_CAP=5.
EPSILON=.001
EXPONENT=.5

def require(condition,message):
    if not condition:raise ValueError(message)

def native_losses(labels,logits):
    y=np.asarray(labels);z=np.asarray(logits,dtype=np.float64)
    require(y.shape==z.shape and z.ndim==1 and len(z)>0,'Matching nonempty vectors required')
    require(np.isfinite(z).all() and np.isin(y,[0,1]).all(),'Finite logits/binary observed labels required')
    return np.where(y==1,np.logaddexp(0.,-z),np.logaddexp(0.,z))

def proposal(losses):
    loss=np.asarray(losses,dtype=np.float64)
    require(loss.ndim==1 and len(loss)>0 and np.isfinite(loss).all() and np.all(loss>=0),'Finite nonnegative native losses required')
    scores=np.sqrt(np.minimum(loss,LOSS_CAP)+EPSILON)
    # Independent compensated scalar normalization, rather than producer array reduction.
    total=math.fsum(map(float,scores))
    p=UNIFORM_MIXTURE/len(loss)+(1-UNIFORM_MIXTURE)*scores/total
    require(np.all(p>=UNIFORM_MIXTURE/len(loss)),'Uniform floor violated')
    require(abs(math.fsum(map(float,p))-1)<1e-13,'Probability normalization differs')
    return scores,p

def effective_probabilities(mode,round_number,n,refresh_losses=None):
    require(mode in ('U','P'),'Unknown sampling mode')
    require(isinstance(round_number,int) and round_number>=1,'One-based positive round required')
    require(isinstance(n,int) and n>=1,'Positive population size required')
    uniform=np.full(n,1./n,dtype=np.float64)
    if round_number<=WARMUP_ROUNDS:
        require(refresh_losses is None,'Warm-up cannot consume refreshed loss priorities')
        return {'refreshed':False,'scores':None,'proposed_priority_probabilities':None,'probabilities':uniform}
    require(refresh_losses is not None,'Post-warm-up requires loss refresh in both U/P arms')
    require(np.asarray(refresh_losses).shape==(n,),'Refresh population differs')
    scores,proposed=proposal(refresh_losses)
    return {'refreshed':True,'scores':scores,'proposed_priority_probabilities':proposed,
            'probabilities':uniform if mode=='U' else proposed}

def replay_draws(probabilities,uniforms):
    p=np.asarray(probabilities,dtype=np.float64)
    u=np.asarray(uniforms,dtype=np.float64)
    require(p.ndim==1 and len(p)>0 and np.isfinite(p).all() and np.all(p>0),'Strictly positive finite probabilities required')
    require(abs(math.fsum(map(float,p))-1)<1e-12,'Probabilities must sum to one')
    require(np.isfinite(u).all() and np.all((u>=0)&(u<1)),'Uniform draws must lie in [0,1)')
    edges=np.cumsum(p);edges[-1]=1.
    index=np.searchsorted(edges,u,side='right')
    require(np.all(index<len(p)),'Inverse CDF escaped population')
    weights=1/(len(p)*p[index])
    return index,weights

def expected_uniform_stream(stream,n):
    require(isinstance(stream,int) and stream>=0,'Explicit nonnegative stream seed required')
    require(isinstance(n,int) and n>=0,'Nonnegative draw count required')
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(stream))).random(n)

def importance_diagnostics(probabilities,index,weights,labels,route=None):
    p=np.asarray(probabilities,float);idx=np.asarray(index);w=np.asarray(weights,float);y=np.asarray(labels)
    require(idx.shape==w.shape and idx.dtype.kind in 'iu','Matching indices/weights required')
    require(y.shape==p.shape and np.isin(y,[0,1]).all(),'Observed training labels must align')
    require(np.all((idx>=0)&(idx<len(p))),'Index outside training population')
    require(np.array_equal(w,1/(len(p)*p[idx])),'Raw importance weights changed or normalized')
    require(np.all(w<=2+1e-14),'Weight exceeds registered uniform-mixture bound')
    result={'sampling_effective_support':float(1/np.sum(p*p)),
            'unique_records':int(np.unique(idx).size),'draws':int(idx.size),
            'positive_record_visits':int(np.sum(y[idx])),
            'minimum_weight':float(w.min()),'maximum_weight':float(w.max()),
            'weight_sum':float(w.sum()),'weight_square_sum':float(np.sum(w*w))}
    if route is not None:
        routes=np.asarray(route)
        require(routes.shape==p.shape and routes.dtype.kind in 'iu' and np.all((routes>=0)&(routes<5)),'Five-bank route required')
        result['bank_record_visits']=np.bincount(routes[idx.ravel()],minlength=5).tolist()
    return result
