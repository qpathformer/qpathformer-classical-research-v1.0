"""Independent numerical oracle. No production model, trainer or router imports.

The circuit uses full tensor matrices and combines adjacent RY rotations. The
producer applies gates separately to statevector slices. Mixture derivatives are
formed from log-space conditional derivatives, independently of producer caches.
"""
import math
import numpy as np

ARMS=('C_H','C_S','C_L','C_R','T_H','T_S','T_L','T_R','G121','MLP2','MLP4','LR2')
COUNTS=dict(zip(ARMS,(70,70,82,82,125,125,137,137,121,65,97,3)))
CLIP=1e-7
I=np.eye(2,dtype=complex);X=np.array([[0,1],[1,0]],complex);Z=np.diag([1.,-1.])
OBS=np.array([np.kron(X,I),np.kron(I,X),np.kron(Z,I),np.kron(I,Z),np.kron(Z,Z)])

def need(c,m):
    if not c:raise RuntimeError(m)

def sigmoid(z):return np.exp(-np.logaddexp(0.,-np.asarray(z)))

def lse(a,axis=-1):
    m=np.max(a,axis=axis,keepdims=True)
    return np.squeeze(m+np.log(np.sum(np.exp(a-m),axis=axis,keepdims=True)),axis=axis)

def features(x,k=2):
    one=[np.ones_like(x)]
    for j in range(1,k+1):one.extend([np.cos(j*np.pi*x),np.sin(j*np.pi*x)])
    p=np.stack(one,axis=-1)
    return np.einsum('ni,nj->nij',p[:,0],p[:,1]).reshape(len(x),-1)

def residual(x,policy):
    return np.stack([x[:,0]**(degree-j)*x[:,1]**j for degree in (2,3,4)
                     for j in range(degree+1)],axis=1)/np.asarray(policy['residual_scale'])

def moments(theta,x):
    """theta [models,8], returns [models,records,5]."""
    theta=np.asarray(theta).reshape(-1,2,2,2);x=np.asarray(x)
    n,m=len(theta),len(x);state=np.zeros((n,m,4),complex);state[:,:,0]=1
    for layer in range(2):
        local=[]
        for q in (0,1):
            angle=(np.pi*x[None,:,q]+theta[:,None,layer,q,0])/2
            phase=np.exp(-.5j*theta[:,None,layer,q,1]);c=np.cos(angle);s=np.sin(angle)
            u=np.empty((n,m,2,2),complex)
            u[:,:,0,0]=phase*c;u[:,:,0,1]=-phase*s
            u[:,:,1,0]=phase.conj()*s;u[:,:,1,1]=phase.conj()*c;local.append(u)
        u=np.einsum('mnij,mnkl->mnikjl',*local).reshape(n,m,4,4)
        state=np.einsum('mnij,mnj->mni',u,state)[:,:,[0,1,3,2]]
    return np.einsum('mni,kij,mnj->mnk',state.conj(),OBS,state).real

def scalar_moments(theta,x):
    state=np.array([1.,0.,0.,0.],complex);theta=np.asarray(theta).reshape(2,2,2)
    def ry(a):
        c,s=math.cos(a/2),math.sin(a/2)
        return np.array([[c,-s],[s,c]],complex)
    def rz(a):return np.diag([np.exp(-.5j*a),np.exp(.5j*a)])
    for l in (0,1):
        gates=[rz(theta[l,q,1])@ry(theta[l,q,0])@ry(math.pi*x[q]) for q in (0,1)]
        state=(np.kron(*gates)@state)[[0,1,3,2]]
    return np.array([np.vdot(state,o@state).real for o in OBS])

def sizes(arm):
    need(arm in ARMS,'Unknown reference arm')
    expert=70 if arm.startswith('C_') else 125 if arm.startswith('T_') else COUNTS[arm]
    return expert,COUNTS[arm]-expert

def initial(arm,streams):
    expert,extra=sizes(arm)
    def seed(k):
        v=streams[k]
        return int(v['uint128_decimal']) if isinstance(v,dict) else int(v)
    if arm.startswith('C_'):
        g=np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed('paired_circuit_core_initialization'))))
        master=g.uniform(-.1,.1,(5,4,2,2));banks=np.zeros((5,14));banks[:,:8]=master[:,:2].reshape(5,8);banks[:,8]=2.
        theta=banks.ravel()
    elif arm.startswith('MLP'):
        d=4 if arm=='MLP4' else 2;h=16
        g=np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed('mlp_initialization'))))
        theta=np.r_[g.uniform(-math.sqrt(6/(d+h)),math.sqrt(6/(d+h)),d*h),np.zeros(h),
                    g.uniform(-math.sqrt(6/(h+1)),math.sqrt(6/(h+1)),h),0.]
        master=theta.copy()
    else:theta=np.zeros(expert);master=theta.copy()
    return np.r_[theta,np.zeros(extra)],master

def preprocessing(raw,policy,dimension):
    p=policy['preprocessing'];raw=np.asarray(raw)
    z=(raw-np.asarray(p['mean4']))/np.asarray(p['scale4'])
    if dimension==2:
        z=np.einsum('ni,ji->nj',z-np.asarray(p['pca_center4']),np.asarray(p['components2x4']))
        z=(z-np.asarray(p['pc_mean2']))/np.asarray(p['pc_scale2'])
    return np.arctan(z)*(2/np.pi)

def forward(arm,theta,x,policy):
    theta=np.asarray(theta);x=np.asarray(x);expert,extra=sizes(arm)
    need(theta.shape==(COUNTS[arm],) and np.isfinite(theta).all() and len(x)>0,'Invalid reference inputs')
    routed=arm.startswith(('C_','T_'));mode=arm[-1] if routed else 'global'
    if routed:
        d=np.sum((x[:,None,:]-np.asarray(policy['centroids'])[None,:,:])**2,axis=2)
        route=np.argmin(d,axis=1);score=-d/float(policy['tau'])
        if mode=='L':score[:,:4]+=np.einsum('ni,ji->nj',np.c_[x,np.ones(len(x))],theta[expert:].reshape(4,3))
        logq=score-lse(score,axis=1)[:,None]
        if arm.startswith('C_'):
            banks=theta[:expert].reshape(5,14);f=moments(banks[:,:8],x)
            zs=np.einsum('bnm,bm->nb',f,banks[:,8:13])+banks[:,13]
        else:
            f=features(x);zs=f@theta[:expert].reshape(5,25).T
        if mode=='H':
            z=zs[np.arange(len(x)),route];lp=-np.logaddexp(0,-z);ln=-np.logaddexp(0,z)
        else:
            elp=-np.logaddexp(0,-zs);eln=-np.logaddexp(0,zs)
            mlp=lse(logq+elp,axis=1);mln=lse(logq+eln,axis=1)
            z=mlp-mln
            if mode=='R':z+=residual(x,policy)@theta[expert:]
            lp=-np.logaddexp(0,-z);ln=-np.logaddexp(0,z)
        return {'p':sigmoid(z),'z':z,'lp':lp,'ln':ln,'f':f,'zs':zs,'logq':logq,'route':route,
                **({} if mode=='H' else {'mlp':mlp,'mln':mln,'elp':elp,'eln':eln})}
    if arm=='G121':f=features(x,5);z=f@theta
    elif arm=='LR2':f=x;z=x@theta[:2]+theta[2]
    else:
        d=x.shape[1];w=theta[:d*16].reshape(d,16);b=theta[d*16:(d+1)*16];v=theta[(d+1)*16:-1]
        f=np.tanh(x@w+b);z=f@v+theta[-1]
    return {'p':sigmoid(z),'z':z,'lp':-np.logaddexp(0,-z),'ln':-np.logaddexp(0,z),'f':f}

def predict(arm,theta,x,policy):
    f=forward(arm,theta,x,policy);return f['p'],f['z']

def objective(arm,theta,x,y,policy):
    f=forward(arm,theta,x,policy)
    loss=float(-np.mean(np.where(y==1,f['lp'],f['ln'])))
    return loss+(.0005*float(theta[:2]@theta[:2]) if arm=='LR2' else 0.)

def gradient(arm,theta,x,y,policy):
    theta=np.asarray(theta);y=np.asarray(y);n=len(y);f=forward(arm,theta,x,policy)
    g=np.zeros_like(theta);expert,extra=sizes(arm);routed=arm.startswith(('C_','T_'))
    if routed:
        mode=arm[-1]
        if mode=='H':chain=np.eye(5)[f['route']]*(f['p']-y)[:,None]/n
        else:
            joint=f['logq']+f['elp']+f['eln']
            if mode=='R':chain=(f['p']-y)[:,None]*np.exp(joint-f['mlp'][:,None]-f['mln'][:,None])/n
            else:chain=np.where(y[:,None]==1,-np.exp(joint-f['mlp'][:,None]),np.exp(joint-f['mln'][:,None]))/n
            if mode=='L':
                conditional=np.where(y[:,None]==1,f['elp']-f['mlp'][:,None],f['eln']-f['mln'][:,None])
                dq=(np.exp(f['logq'])-np.exp(f['logq']+conditional))/n
                g[expert:]=np.einsum('ni,nj->ij',dq[:,:4],np.c_[x,np.ones(n)]).ravel()
            if mode=='R':g[expert:]=residual(x,policy).T@(f['p']-y)/n
        if arm.startswith('T_'):g[:expert]=(chain.T@f['f']).ravel()
        else:
            banks=theta[:expert].reshape(5,14);out=g[:expert].reshape(5,14)
            out[:,8:13]=np.einsum('nb,bnm->bm',chain,f['f']);out[:,13]=np.sum(chain,axis=0)
            shifted=np.repeat(banks[:,:8],16,axis=0)
            for b in range(5):
                for j in range(8):shifted[b*16+2*j,j]+=np.pi/2;shifted[b*16+2*j+1,j]-=np.pi/2
            pairs=moments(shifted,x).reshape(5,8,2,n,5)
            derivatives=(pairs[:,:,0]-pairs[:,:,1])/2
            out[:,:8]=np.einsum('nb,bjnm,bm->bj',chain,derivatives,banks[:,8:13])
    else:
        delta=(f['p']-y)/n
        if arm=='G121':g=f['f'].T@delta
        elif arm=='LR2':g[:2]=x.T@delta+.001*theta[:2];g[2]=delta.sum()
        else:
            d=x.shape[1];v=theta[(d+1)*16:-1];dh=delta[:,None]*v*(1-f['f']**2)
            g=np.r_[(x.T@dh).ravel(),dh.sum(0),f['f'].T@delta,delta.sum()]
    need(np.isfinite(g).all(),'Nonfinite independent gradient')
    return g

def native_bce(y,z):return float(np.mean(np.logaddexp(0.,z)-np.asarray(y)*z))

def metrics(y,p):
    y=np.asarray(y);p=np.asarray(p);q=np.clip(p,CLIP,1-CLIP);prediction=p>=.5
    cm=np.array([[np.count_nonzero((y==a)&(prediction==b)) for b in (0,1)] for a in (0,1)])
    f1=[2*cm[k,k]/(cm[k].sum()+cm[:,k].sum()) if cm[k].sum()+cm[:,k].sum() else 0. for k in (0,1)]
    edges=np.linspace(0.,1.,11);rel=[];ece=0.
    for k in range(10):
        mask=(p>=edges[k])&((p<edges[k+1]) if k<9 else (p<=edges[k+1]))
        n=int(mask.sum());mean=float(p[mask].mean()) if n else None;rate=float(y[mask].mean()) if n else None
        if n:ece+=n/len(y)*abs(mean-rate)
        rel.append({'bin':k,'lower':float(edges[k]),'upper':float(edges[k+1]),'count':n,'mean_probability':mean,'fraction_positive':rate})
    return {'bce':float(np.mean(-np.where(y==1,np.log(q),np.log1p(-q)))),'macro_f1':float(np.mean(f1)),
            'accuracy':float(np.mean(y==prediction)),'brier':float(np.mean((p-y)**2)), 'ece10':float(ece),
            'confusion':cm.tolist(),'n':len(y),'clipped':int(np.sum((p<CLIP)|(p>1-CLIP))),'reliability10':rel}

def adam(theta,g,m,v,t,lr):
    m=.9*m+.1*g;v=.999*v+.001*g*g
    theta=theta-lr*(m/(1-.9**t))/(np.sqrt(v/(1-.999**t))+1e-8)
    return theta,m,v
