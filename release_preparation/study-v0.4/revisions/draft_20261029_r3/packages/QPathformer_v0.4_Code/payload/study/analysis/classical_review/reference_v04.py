"""Independent v0.4 numerical reference; never imports training/model modules.

The fast circuit oracle composes each pair of adjacent RY rotations and forms
the full local tensor-product matrices. The scalar oracle instead multiplies
all gates separately using Python math, so it also checks that simplification.
"""
import math
import numpy as np

METHODS=tuple(f'{family}_{route}' for family in ('q2','mlp','trig') for route in ('global','hash','kmeans'))
PARAMETERS={'q2_global':8,'q2_hash':40,'q2_kmeans':40,'mlp_global':129,'mlp_hash':45,'mlp_kmeans':45,
            'trig_global':25,'trig_hash':125,'trig_kmeans':125}
CLIP=1e-7
CX=np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]],complex)

def ry(angle):
    c,s=math.cos(float(angle)/2),math.sin(float(angle)/2)
    return np.array([[c,-s],[s,c]],complex)

def rz(angle):
    c,s=math.cos(float(angle)/2),math.sin(float(angle)/2)
    return np.array([[complex(c,-s),0],[0,complex(c,s)]],complex)

FINAL=np.kron(ry(math.pi/2),np.eye(2))

def scalar_circuit(x,angles):
    state=np.array([1,0,0,0],complex)
    for layer in range(2):
        u=[]
        for q in (0,1):
            u.append(rz(angles[layer,q,1])@ry(angles[layer,q,0])@ry(math.pi*float(x[q])))
        state=CX@np.kron(u[0],u[1])@state
    state=FINAL@state
    p=float((state[2].conjugate()*state[2]+state[3].conjugate()*state[3]).real)
    if not -1e-12<=p<=1+1e-12:raise ValueError('Unphysical scalar probability')
    return min(1.,max(0.,p))

def trig_features(x):
    x=np.asarray(x,float);phase=np.pi*x
    f=np.stack((np.ones_like(x),np.cos(phase),np.sin(phase),np.cos(2*phase),np.sin(2*phase)),axis=-1)
    return np.einsum('ni,nj->nij',f[:,0],f[:,1]).reshape(len(x),25)

def inputs(method,parameters,x,route):
    if method not in METHODS:raise ValueError('Unknown method')
    x=np.asarray(x,dtype=np.float64);p=np.asarray(parameters,dtype=np.float64)
    if p.ndim==1:p=p[None,:]
    if x.ndim!=2 or x.shape[1]!=2 or len(x)==0 or not np.isfinite(x).all():raise ValueError('Finite two-coordinate records required')
    if p.ndim!=2 or p.shape[1]!=PARAMETERS[method] or not np.isfinite(p).all():raise ValueError('Parameter shape/values')
    if method.endswith('_global'):banks=1;idx=np.zeros(len(x),int)
    else:
        idx=np.asarray(route)
        if idx.shape!=(len(x),) or idx.dtype.kind not in 'iu' or np.any(idx<0) or np.any(idx>=5):raise ValueError('Integer route0..4 required')
        banks=5
    return p,x,banks,idx

def _circuit_many(p,x,banks,idx):
    theta=p.reshape(len(p),banks,2,2,2)[:,idx]
    state=np.zeros((len(p),len(x),4),complex);state[:,:,0]=1
    for layer in range(2):
        local=[]
        for q in (0,1):
            alpha=(np.pi*x[None,:,q]+theta[:,:,layer,q,0])/2
            beta=theta[:,:,layer,q,1]/2
            c,s=np.cos(alpha),np.sin(alpha);minus=np.exp(-1j*beta);plus=np.exp(1j*beta)
            matrix=np.empty((len(p),len(x),2,2),complex)
            matrix[:,:,0,0]=minus*c;matrix[:,:,0,1]=-minus*s
            matrix[:,:,1,0]=plus*s;matrix[:,:,1,1]=plus*c
            local.append(matrix)
        tensor=np.einsum('rnab,rncd->rnacbd',local[0],local[1]).reshape(len(p),len(x),4,4)
        state=np.einsum('rnij,rnj->rni',tensor,state)[:,:,[0,1,3,2]]
    state=np.einsum('ij,rnj->rni',FINAL,state)
    probability=np.sum(abs(state[:,:,2:])**2,axis=-1)
    if not np.isfinite(probability).all() or np.any(probability < -1e-12) or np.any(probability>1+1e-12):raise ValueError('Unphysical vector probability')
    return np.clip(probability,0.,1.)

def _mlp_many(p,x,banks,idx):
    h=32 if banks==1 else 2;theta=p.reshape(len(p),banks,4*h+1)[:,idx]
    w=theta[:,:,:2*h].reshape(len(p),len(x),2,h)
    hidden=np.maximum(np.einsum('ni,rnih->rnh',x,w)+theta[:,:,2*h:3*h],0.)
    logits=np.sum(hidden*theta[:,:,3*h:4*h],axis=-1)+theta[:,:,-1]
    return np.exp(-np.logaddexp(0.,-logits))

def predict_many(method,parameters,x,route=None,chunk_rounds=8):
    """Parameters are [round,parameter]; output [round,record], bounded workspace."""
    p,x,banks,idx=inputs(method,parameters,x,route)
    if not isinstance(chunk_rounds,int) or chunk_rounds<=0:raise ValueError('Positive chunk required')
    out=[];phi=trig_features(x) if method.startswith('trig_') else None
    for begin in range(0,len(p),chunk_rounds):
        block=p[begin:begin+chunk_rounds]
        if method.startswith('q2_'):value=_circuit_many(block,x,banks,idx)
        elif method.startswith('mlp_'):value=_mlp_many(block,x,banks,idx)
        else:
            theta=block.reshape(len(block),banks,25)[:,idx]
            logits=np.einsum('nk,rnk->rn',phi,theta)
            value=np.exp(-np.logaddexp(0.,-logits))
        out.append(value)
    return np.concatenate(out,axis=0)

def predict(method,parameters,x,route=None):
    if np.asarray(parameters).ndim!=1:raise ValueError('One parameter vector required')
    return predict_many(method,parameters,x,route)[0]

def scalar_predict(method,parameters,x,route=None):
    p,x,banks,idx=inputs(method,parameters,x,route)
    if len(p)!=1:raise ValueError('One scalar-reference parameter vector required')
    p=p[0].reshape(banks,-1);out=[]
    for row,bank in zip(x,idx):
        theta=p[bank]
        if method.startswith('q2_'):out.append(scalar_circuit(row,theta.reshape(2,2,2)));continue
        if method.startswith('mlp_'):
            h=32 if banks==1 else 2
            z=[max(0.,sum(float(row[i])*float(theta[i*h+j]) for i in (0,1))+float(theta[2*h+j])) for j in range(h)]
            logit=sum(z[j]*float(theta[3*h+j]) for j in range(h))+float(theta[-1])
        else:
            a=[[1.,math.cos(math.pi*t),math.sin(math.pi*t),math.cos(2*math.pi*t),math.sin(2*math.pi*t)] for t in row]
            logit=sum(float(theta[5*i+j])*a[0][i]*a[1][j] for i in range(5) for j in range(5))
        out.append(1/(1+math.exp(-logit)) if logit>=0 else math.exp(logit)/(1+math.exp(logit)))
    return np.asarray(out)

def bce(y,p):
    y=np.asarray(y);p=np.clip(np.asarray(p,float),CLIP,1-CLIP)
    return float(np.mean(np.where(y==1,-np.log(p),-np.log1p(-p))))

def metrics(y,p):
    y=np.asarray(y);p=np.asarray(p,float);pred=p>=.5
    cm=np.array([[np.sum((y==a)&(pred==b)) for b in (0,1)] for a in (0,1)],int)
    f=[]
    for k in (0,1):
        den=cm[k].sum()+cm[:,k].sum();f.append(float(2*cm[k,k]/den) if den else 0.)
    return {'n':len(y),'bce':bce(y,p),'macro_f1':float(np.mean(f)),'accuracy':float(np.mean(pred==y)),
            'confusion':cm.tolist(),'clipped':int(np.sum((p<CLIP)|(p>1-CLIP)))}

def central_gradient(method,parameters,x,y,route=None,step=1e-5):
    """Five-point independent clipped-loss finite differences; engineering only."""
    theta=np.asarray(parameters,float);out=np.empty_like(theta)
    for j in range(len(theta)):
        loss=[]
        for multiple in (-2,-1,1,2):
            moved=theta.copy();moved[j]+=multiple*step
            loss.append(bce(y,predict(method,moved,x,route)))
        out[j]=(loss[0]-8*loss[1]+8*loss[2]-loss[3])/(12*step)
    return out
