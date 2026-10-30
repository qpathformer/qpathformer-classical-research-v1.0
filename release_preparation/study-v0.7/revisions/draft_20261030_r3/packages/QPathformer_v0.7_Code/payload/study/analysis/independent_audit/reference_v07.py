"""Independent v0.7 numerical oracle, adapted from the preserved v0.5 source. Never imports a producer/model module.

The vector reference composes adjacent RY rotations and forms full 4x4 tensor
matrices; the scalar reference multiplies the separate feature/train gates.
Frozen core angles must be supplied explicitly, never inferred from outcomes.
"""
import math
import numpy as np

METHODS=('qscalar_kmeans','qmulti_kmeans','qmulti_hash','trig_kmeans','trig_hash','trig_global','trig121_global','mlp_global')
PARAMETERS=dict(zip(METHODS,(50,70,70,125,125,25,121,129)))
CLIP=1e-7
I=np.eye(2,dtype=complex)
X=np.array([[0,1],[1,0]],complex)
Z=np.array([[1,0],[0,-1]],complex)
OBSERVABLES=np.asarray([np.kron(X,I),np.kron(I,X),np.kron(Z,I),np.kron(I,Z),np.kron(Z,Z)])
CX=np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]],complex)

def ry(angle):
    c,s=math.cos(float(angle)/2),math.sin(float(angle)/2)
    return np.array([[c,-s],[s,c]],complex)

def rz(angle):
    c,s=math.cos(float(angle)/2),math.sin(float(angle)/2)
    return np.array([[complex(c,-s),0],[0,complex(c,s)]],complex)

FINAL=np.kron(ry(math.pi/2),I)

def scalar_state(x,angles):
    state=np.array([1,0,0,0],complex)
    for layer in range(2):
        u=[rz(angles[layer,q,1])@ry(angles[layer,q,0])@ry(math.pi*float(x[q])) for q in (0,1)]
        state=CX@np.kron(u[0],u[1])@state
    return state

def scalar_observables(x,angles):
    state=scalar_state(x,angles)
    return np.asarray([float(np.vdot(state,operator@state).real) for operator in OBSERVABLES])

def scalar_circuit(x,angles):
    state=FINAL@scalar_state(x,angles)
    return float(np.sum(abs(state[2:])**2))

def trig_features(x,frequency=2):
    x=np.asarray(x,dtype=np.float64);phase=np.pi*x
    pieces=[np.ones_like(x)]
    for harmonic in range(1,frequency+1):
        pieces.extend([np.cos(harmonic*phase),np.sin(harmonic*phase)])
    f=np.stack(pieces,axis=-1)
    width=2*frequency+1
    return np.einsum('ni,nj->nij',f[:,0],f[:,1]).reshape(len(x),width*width)

def inputs(method,parameters,x,route):
    if method not in METHODS:raise ValueError('Unknown method')
    x=np.asarray(x,dtype=np.float64);theta=np.asarray(parameters,dtype=np.float64)
    if theta.ndim==1:theta=theta[None,:]
    if x.ndim!=2 or x.shape[1]!=2 or len(x)==0 or not np.isfinite(x).all():raise ValueError('Finite N-by-2 inputs required')
    if theta.ndim!=2 or len(theta)==0 or theta.shape[1]!=PARAMETERS[method] or not np.isfinite(theta).all():raise ValueError('Parameter shape or values differ')
    if method.endswith('_global'):
        if route is not None:raise ValueError('Global model cannot receive routes')
        banks=1;idx=np.zeros(len(x),int)
    else:
        idx=np.asarray(route);banks=5
        if idx.shape!=(len(x),) or idx.dtype.kind not in 'iu' or np.any(idx<0) or np.any(idx>=5):raise ValueError('Integer route0..4 required')
    return theta,x,banks,idx

def frozen_angles(core):
    value=np.asarray(core,dtype=np.float64)
    if value.shape!=(5,2,2,2) or not np.isfinite(value).all():raise ValueError('Explicit frozen core[5,2,2,2] required')
    return value

def _state_many(theta,x):
    """theta[round,record,layer,qubit,axis], output[round,record,state]."""
    state=np.zeros((len(theta),len(x),4),complex);state[:,:,0]=1
    for layer in range(2):
        local=[]
        for q in (0,1):
            a=(np.pi*x[None,:,q]+theta[:,:,layer,q,0])/2;b=theta[:,:,layer,q,1]/2
            c,s=np.cos(a),np.sin(a);minus,plus=np.exp(-1j*b),np.exp(1j*b)
            u=np.empty((*a.shape,2,2),complex)
            u[:,:,0,0]=minus*c;u[:,:,0,1]=-minus*s;u[:,:,1,0]=plus*s;u[:,:,1,1]=plus*c
            local.append(u)
        tensor=np.einsum('rnab,rncd->rnacbd',local[0],local[1]).reshape(len(theta),len(x),4,4)
        state=np.einsum('rnij,rnj->rni',tensor,state)[:,:,[0,1,3,2]]
    return state

def observables_many(theta,x):
    state=_state_many(theta,np.asarray(x,float))
    return np.einsum('rni,kij,rnj->rnk',state.conj(),OBSERVABLES,state).real

def frozen_features(x,route,core):
    _,x,_,idx=inputs('qfrozen_kmeans',np.zeros(30),x,route)
    return observables_many(frozen_angles(core)[None,idx],x)[0]

def _mlp_logits(theta,x,banks,idx,method):
    h=32 if method=='mlp_global' else int(method[3])
    p=theta.reshape(len(theta),banks,4*h+1)[:,idx]
    z=np.einsum('ni,rnih->rnh',x,p[:,:,:2*h].reshape(len(theta),len(x),2,h))+p[:,:,2*h:3*h]
    hidden=np.tanh(z) if 'tanh' in method else np.maximum(z,0.)
    return np.sum(hidden*p[:,:,3*h:4*h],axis=-1)+p[:,:,-1]

def predict_many_with_logits(method,parameters,x,route=None,core_parameters=None,chunk_rounds=8):
    theta,x,banks,idx=inputs(method,parameters,x,route)
    if not isinstance(chunk_rounds,int) or chunk_rounds<=0:raise ValueError('Positive chunk required')
    if method=='qfrozen_kmeans':fixed=frozen_features(x,route,core_parameters)
    else:
        if core_parameters is not None:raise ValueError('Separate core is valid only for frozen arm')
        fixed=None
    phi=trig_features(x,5 if method=='trig121_global' else 2) if method.startswith('trig') else None
    probabilities=[];logits=[]
    for first in range(0,len(theta),chunk_rounds):
        p=theta[first:first+chunk_rounds];packed=p.reshape(len(p),banks,-1)[:,idx]
        if method=='q2_kmeans':
            state=_state_many(packed.reshape(len(p),len(x),2,2,2),x)
            final=np.einsum('ij,rnj->rni',FINAL,state)
            prob=np.sum(abs(final[:,:,2:])**2,axis=-1);z=None
        elif method.startswith('q'):
            if method=='qfrozen_kmeans':features=fixed[None,:,:];head=packed
            else:features=observables_many(packed[:,:,:8].reshape(len(p),len(x),2,2,2),x);head=packed[:,:,8:]
            if method=='qscalar_kmeans':features=features[:,:,:1]
            z=np.sum(features*head[:,:,:-1],axis=-1)+head[:,:,-1]
            prob=np.exp(-np.logaddexp(0.,-z))
        elif method.startswith('mlp'):
            z=_mlp_logits(p,x,banks,idx,method);prob=np.exp(-np.logaddexp(0.,-z))
        else:
            z=np.einsum('nk,rnk->rn',phi,packed);prob=np.exp(-np.logaddexp(0.,-z))
        if not np.isfinite(prob).all() or np.any(prob < -1e-12) or np.any(prob > 1+1e-12):raise ValueError('Invalid probability')
        probabilities.append(np.clip(prob,0,1))
        if z is not None:
            if not np.isfinite(z).all():raise ValueError('Nonfinite logit')
            logits.append(z)
    return np.concatenate(probabilities),np.concatenate(logits) if logits else None

def predict_many(method,parameters,x,route=None,core_parameters=None,chunk_rounds=8):
    return predict_many_with_logits(method,parameters,x,route,core_parameters,chunk_rounds)[0]

def predict_with_logits(method,parameters,x,route=None,core_parameters=None):
    if np.asarray(parameters).ndim!=1:raise ValueError('One parameter vector required')
    p,z=predict_many_with_logits(method,parameters,x,route,core_parameters)
    return p[0],None if z is None else z[0]

def predict(method,parameters,x,route=None,core_parameters=None):
    return predict_with_logits(method,parameters,x,route,core_parameters)[0]

def scalar_predict_with_logits(method,parameters,x,route=None,core_parameters=None):
    theta,x,banks,idx=inputs(method,parameters,x,route)
    if len(theta)!=1:raise ValueError('One scalar-reference vector required')
    params=theta[0].reshape(banks,-1);core=frozen_angles(core_parameters) if method=='qfrozen_kmeans' else None
    probabilities=[];logits=[]
    for row,bank in zip(x,idx):
        p=params[bank]
        if method=='q2_kmeans':probabilities.append(scalar_circuit(row,p.reshape(2,2,2)));continue
        if method.startswith('q'):
            if core is not None:features=scalar_observables(row,core[bank]);head=p
            else:features=scalar_observables(row,p[:8].reshape(2,2,2));head=p[8:]
            count=1 if method=='qscalar_kmeans' else 5
            z=sum(float(head[j])*features[j] for j in range(count))+float(head[-1])
        elif method.startswith('mlp'):
            h=32 if method=='mlp_global' else int(method[3])
            hidden=[sum(float(row[i])*float(p[i*h+j]) for i in (0,1))+float(p[2*h+j]) for j in range(h)]
            hidden=[math.tanh(v) if 'tanh' in method else max(0.,v) for v in hidden]
            z=sum(hidden[j]*float(p[3*h+j]) for j in range(h))+float(p[-1])
        else:
            frequency=5 if method=='trig121_global' else 2
            width=2*frequency+1
            f=[[1.]+[v for k in range(1,frequency+1) for v in (math.cos(k*math.pi*t),math.sin(k*math.pi*t))] for t in row]
            z=sum(float(p[width*i+j])*f[0][i]*f[1][j] for i in range(width) for j in range(width))
        logits.append(z);probabilities.append(1/(1+math.exp(-z)) if z>=0 else math.exp(z)/(1+math.exp(z)))
    return np.asarray(probabilities),np.asarray(logits) if logits else None

def scalar_predict(method,parameters,x,route=None,core_parameters=None):
    return scalar_predict_with_logits(method,parameters,x,route,core_parameters)[0]

def bce(y,p):
    y=np.asarray(y);p=np.clip(np.asarray(p,float),CLIP,1-CLIP)
    return float(np.mean(np.where(y==1,-np.log(p),-np.log1p(-p))))

def stable_logit_bce(y,z):
    y=np.asarray(y);z=np.asarray(z,float)
    if y.shape!=z.shape or z.ndim!=1 or not len(z) or not np.isfinite(z).all() or not np.isin(y,[0,1]).all():raise ValueError('Invalid finite logits/labels')
    # Separate label branches avoid cancellation of softplus(z)-z at large positive z.
    return float(np.mean(np.where(y==1,np.logaddexp(0.,-z),np.logaddexp(0.,z))))

def native_loss(method,parameters,x,y,route=None,core_parameters=None):
    p,z=predict_with_logits(method,parameters,x,route,core_parameters)
    return bce(y,p) if z is None else stable_logit_bce(y,z)

def metrics(y,p):
    y=np.asarray(y);p=np.asarray(p,float);pred=p>=.5
    if y.shape!=p.shape or p.ndim!=1 or not len(p) or not np.isfinite(p).all() or np.any(p<0) or np.any(p>1) or not np.isin(y,[0,1]).all():raise ValueError('Invalid metric inputs')
    cm=np.array([[np.sum((y==a)&(pred==b)) for b in (0,1)] for a in (0,1)],int)
    f=[]
    for k in (0,1):
        den=cm[k].sum()+cm[:,k].sum();f.append(float(2*cm[k,k]/den) if den else 0.)
    bins=np.minimum(np.searchsorted(np.linspace(0.,1.,11),p,side='right')-1,9);ece=0.;reliability=[]
    for k in range(10):
        mask=bins==k;n=int(mask.sum())
        pm=float(p[mask].mean()) if n else None;rate=float(y[mask].mean()) if n else None
        if n:ece+=n/len(p)*abs(pm-rate)
        reliability.append({'bin':k,'n':n,'mean_probability':pm,'positive_fraction':rate})
    return {'n':len(y),'bce':bce(y,p),'macro_f1':float(np.mean(f)),'accuracy':float(np.mean(pred==y)),
      'brier':float(np.mean((p-y)**2)),'ece10':float(ece),'reliability10':reliability,
      'confusion':cm.tolist(),'clipped':int(np.sum((p<CLIP)|(p>1-CLIP)))}

def central_gradient(method,parameters,x,y,route=None,core_parameters=None,step=1e-5):
    """Independent five-point finite difference of the actual native objective."""
    theta=np.asarray(parameters,float);out=np.empty_like(theta)
    for j in range(len(theta)):
        losses=[]
        for multiple in (-2,-1,1,2):
            moved=theta.copy();moved[j]+=multiple*step
            losses.append(native_loss(method,moved,x,y,route,core_parameters))
        out[j]=(losses[0]-8*losses[1]+8*losses[2]-losses[3])/(12*step)
    return out
