"""Scalar matrix and separately packed MLP endpoint oracle; no production models.

This is the author's audit oracle. A second reviewer implements a separate
oracle under analysis/independent_replay. Neither is a general correctness proof.
"""
import numpy as np
from reference_v03 import probability


def predict(method,parameters,x,depth,hash_route,kmeans_route):
    p=np.asarray(parameters,float)
    if method in ('mlp41','mlp129'):
        hidden=5 if method=='mlp41' else 16
        f=np.concatenate([x,np.eye(4)[depth-1]],axis=1)
        w=p[:6*hidden].reshape(6,hidden);b=p[6*hidden:7*hidden]
        out=p[7*hidden:8*hidden];bias=p[-1]
        z=np.maximum(f.dot(w)+b,0).dot(out)+bias
        result=np.empty(len(z));positive=z>=0
        result[positive]=1/(1+np.exp(-z[positive]));e=np.exp(z[~positive]);result[~positive]=e/(1+e)
        return result
    offsets=[0,4,12,24,40];result=[]
    for i,row in enumerate(x):
        original=int(depth[i]);encoding=method=='encoding1';beta=float(p[-1]) if method=='readout1' else np.pi/2
        if method=='ensemble40':
            result.append(sum(probability(row,p[k*8:(k+1)*8].reshape(2,2,2),2) for k in range(5))/5);continue
        if method in ('hash40','kmeans40'):
            bank=int(hash_route[i] if method=='hash40' else kmeans_route[i]);d=2;theta=p[bank*8:(bank+1)*8].reshape(2,2,2)
        elif method=='untied_assigned':
            d=original;theta=p[offsets[d-1]:offsets[d]].reshape(d,2,2)
        else:
            d={'fixed1':1,'fixed2':2,'fixed4':4,'encoding1':1,'readout1':1}.get(method,max(original,2) if method=='min_depth2' else original)
            theta=p[:4*d].reshape(d,2,2)
        result.append(probability(row,theta,d,encoding,beta))
    return np.asarray(result)


def metrics(y,p):
    pred=np.asarray(p)>=.5;y=np.asarray(y);c=np.zeros((2,2),dtype=np.int64)
    for a,b in zip(y,pred):c[int(a),int(b)]+=1
    f=[]
    for i in range(2):
        denominator=int(c[i,:].sum()+c[:,i].sum());f.append(2*c[i,i]/denominator if denominator else 0.)
    q=np.maximum(1e-7,np.minimum(1-1e-7,p))
    return {'bce':float(np.mean(np.where(y==1,-np.log(q),-np.log(1-q)))),
            'macro_f1':float(sum(f)/2),'accuracy':float(np.trace(c)/len(y)),'n':len(y),
            'clipped':int(np.sum((p<1e-7)|(p>1-1e-7))),'confusion':c.tolist()}
