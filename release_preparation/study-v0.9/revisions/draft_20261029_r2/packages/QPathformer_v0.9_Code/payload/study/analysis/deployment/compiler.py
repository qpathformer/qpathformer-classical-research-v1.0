"""Exact two-layer core compilation; geometric mixtures and residuals remain."""
from pathlib import Path
import sys
import numpy as np
from scipy.special import logsumexp
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'quantum'))
import circuits
from models import sigmoid,trig_features,residual_features
from routers import preprocess

CIRCUIT_ARMS=('C_H','C_S','C_L','C_R')
NODES=-1+2*np.arange(5,dtype=np.float64)/5
GRID=np.stack(np.meshgrid(NODES,NODES,indexing='ij'),axis=-1).reshape(25,2)
NORMS=np.array([1.,.5,.5,.5,.5])
def basis(x):return np.stack([np.ones_like(x),np.cos(np.pi*x),np.sin(np.pi*x),np.cos(2*np.pi*x),np.sin(2*np.pi*x)],axis=-1)
def compile_bank(theta):
    theta=np.asarray(theta,dtype=np.float64)
    if theta.shape!=(14,) or not np.isfinite(theta).all():raise ValueError('Finite circuit bank14 required')
    z=circuits.moments(GRID,theta[:8].reshape(2,2,2),5)@theta[8:13]+theta[13]
    B=basis(NODES);c=(B.T@z.reshape(5,5)@B)/25/NORMS[:,None]/NORMS[None,:]
    return c.ravel(),z
def compile_parameters(arm,parameters):
    p=np.asarray(parameters,dtype=np.float64)
    if arm not in CIRCUIT_ARMS or p.shape!=((82,) if arm[-1] in 'LR' else (70,)) or not np.isfinite(p).all():raise ValueError('Invalid registered circuit checkpoint')
    pairs=[compile_bank(bank) for bank in p[:70].reshape(5,14)]
    return np.array([x[0] for x in pairs]),p[70:].copy(),np.array([x[1] for x in pairs])
class Compiled:
    def __init__(self,arm,coefficients,extra,policy):
        if arm not in CIRCUIT_ARMS:raise ValueError('Unregistered circuit arm')
        self.arm=arm;self.coefficients=np.asarray(coefficients,dtype=np.float64).copy();self.extra=np.asarray(extra,dtype=np.float64).copy();self.policy=policy
        if self.coefficients.shape!=(5,25) or self.extra.shape!=((12,) if arm[-1] in 'LR' else (0,)):raise ValueError('Wrong compiled dimensions')
        if not np.isfinite(self.coefficients).all() or not np.isfinite(self.extra).all():raise ValueError('Nonfinite compiled payload')
        self.centers=np.array(policy['centroids']);self.tau=float(policy['tau']);self.scale=np.array(policy['residual_scale'])
    def core_logits(self,x):return trig_features(x,2)@self.coefficients.T
    def predict_with_logits(self,x):
        x=np.asarray(x,dtype=np.float64)
        if x.ndim!=2 or x.shape[1]!=2 or not len(x) or not np.isfinite(x).all():raise ValueError('Finite [N,2] input required')
        d=((x[:,None,:]-self.centers[None,:,:])**2).sum(2);phi=trig_features(x,2)
        if self.arm=='C_H':z=np.einsum('ni,ni->n',phi,self.coefficients[d.argmin(1)])
        else:
            expert=phi@self.coefficients.T;scores=-d/self.tau
            if self.arm=='C_L':scores[:,:4]+=np.column_stack((x,np.ones(len(x))))@self.extra.reshape(4,3).T
            logq=scores-logsumexp(scores,axis=1,keepdims=True)
            z=logsumexp(logq-np.logaddexp(0,-expert),axis=1)-logsumexp(logq-np.logaddexp(0,expert),axis=1)
            if self.arm=='C_R' and np.any(self.extra!=0):z+=residual_features(x,self.scale)@self.extra
        return sigmoid(z),z
    def predict_raw(self,raw):return self.predict_with_logits(preprocess(raw,self.policy,2))
def original_raw(model,raw,policy):
    return model.predict_with_logits(preprocess(raw,policy,4 if model.method=='MLP4' else 2))
def probes(policy,stream):
    gen=np.random.Generator(np.random.PCG64(int(stream)));points=gen.uniform(-1,1,(257,2));c=np.array(policy['centroids']);boundary=[]
    for i in range(5):
        for j in range(i+1,5):
            delta=c[j]-c[i];norm=np.linalg.norm(delta)
            if norm==0:raise ValueError('Duplicate centroids')
            for offset in (-1e-7,0,1e-7):boundary.append(np.clip((c[i]+c[j])/2+offset*delta/norm,-1,1))
    return points,np.array(boundary)
def parity(p,z,rp,rz):
    p,z,rp,rz=map(np.asarray,(p,z,rp,rz));error=float(abs(p-rp).max());classes=int(np.sum((p>=.5)!=(rp>=.5)))
    if error>1e-10 or classes or not all(np.isfinite(a).all() for a in (p,z,rp,rz)):raise RuntimeError('Frozen conversion probability/class parity failed')
    return {'records':len(p),'max_abs_probability_error':error,'max_abs_logit_error':float(abs(z-rz).max()),'class_disagreements':classes}
