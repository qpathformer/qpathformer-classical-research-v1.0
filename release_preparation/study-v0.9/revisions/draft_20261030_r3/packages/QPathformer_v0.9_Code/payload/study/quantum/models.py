"""Q-Pathformer v0.9 Plan B: stable dense mixtures, geometric routing and controls.

All inference takes numeric inputs and a frozen training-fitted policy. No labels
enter a router. The inherited two-qubit moment circuit is unchanged.
"""
from __future__ import annotations
import numpy as np
from scipy.special import logsumexp
import circuits

METHODS=('C_H','C_S','C_L','C_R','T_H','T_S','T_L','T_R','G121','MLP2','MLP4','LR2')
ARM_METHODS={k:k for k in METHODS}
PARAMETER_COUNTS=dict(zip(METHODS,(70,70,82,82,125,125,137,137,121,65,97,3)))
MOMENT_ORDER=('X0','X1','Z0','Z1','Z0Z1')
CLIP=1e-7
RESIDUAL_POWERS=tuple((degree-j,j) for degree in (2,3,4) for j in range(degree+1))

def sigmoid(z):
    z=np.asarray(z,dtype=np.float64);out=np.empty_like(z);positive=z>=0
    out[positive]=1/(1+np.exp(-z[positive]));e=np.exp(z[~positive]);out[~positive]=e/(1+e)
    return out

def check_labels(y,shape):
    y=np.asarray(y)
    if y.shape!=shape or y.ndim!=1 or not len(y) or not np.isin(y,[0,1]).all():
        raise ValueError('Nonempty matching binary labels required')
    return y

def binary_cross_entropy(y,p):
    p=np.asarray(p,dtype=np.float64);y=check_labels(y,p.shape)
    if not np.isfinite(p).all() or np.any(p<0) or np.any(p>1):raise ValueError('Invalid probabilities')
    q=np.clip(p,CLIP,1-CLIP)
    return float(np.mean(-y*np.log(q)-(1-y)*np.log1p(-q)))

def native_losses(y,z):
    z=np.asarray(z,dtype=np.float64);y=check_labels(y,z.shape)
    if not np.isfinite(z).all():raise ValueError('Finite logits required')
    return np.maximum(z,0)-y*z+np.log1p(np.exp(-np.abs(z)))

def trig_features(x,max_frequency=2):
    if max_frequency not in (2,5):raise ValueError('Registered frequencies are 2 and 5')
    x=np.asarray(x,dtype=np.float64);u=np.pi*x;columns=[np.ones_like(u)]
    for k in range(1,max_frequency+1):columns.extend((np.cos(k*u),np.sin(k*u)))
    phi=np.stack(columns,axis=2)
    return (phi[:,0,:,None]*phi[:,1,None,:]).reshape(len(x),(2*max_frequency+1)**2)

def residual_features(x,scale):
    return np.column_stack([x[:,0]**a*x[:,1]**b for a,b in RESIDUAL_POWERS])/scale

class Adam:
    def __init__(self,shape,lr=.01):
        self.m=np.zeros(shape,dtype=np.float64);self.v=np.zeros(shape,dtype=np.float64);self.t=0;self.lr=lr
    def step(self,parameters,gradient):
        self.t+=1;self.m=.9*self.m+.1*gradient;self.v=.999*self.v+.001*gradient**2
        parameters-=self.lr*(self.m/(1-.9**self.t))/(np.sqrt(self.v/(1-.999**self.t))+1e-8)

def add_work(target,part):
    for key,value in part.items():target[key]=target.get(key,0)+int(value)
    return target

class Model:
    def __init__(self,method,seed,initialization_streams,policy=None):
        if method not in METHODS:raise ValueError('Unregistered method')
        self.method=method;self.seed=int(seed);self.policy=policy
        self.quantum=method.startswith('C_');self.routed=method.startswith(('C_','T_'))
        self.routing=method[-1] if self.routed else 'global';self.banks=5 if self.routed else 1
        self.bank_width=14 if self.quantum else 25 if self.routed else PARAMETER_COUNTS[method]
        self.expert_size=self.bank_width*self.banks
        self.extra_size=12 if self.routing in ('L','R') else 0
        self.input_dim=4 if method=='MLP4' else 2;self.hidden=16 if method.startswith('MLP') else 0
        self.native_logits=True;self.frozen=False;self.core_parameters=np.empty(0,dtype=np.float64)
        self.initialization_streams={k:int(v) for k,v in initialization_streams.items()}
        if self.routed:
            if policy is None:raise ValueError('Training-fitted policy required')
            self.centres=np.asarray(policy.get('centroids',policy.get('centres')),dtype=np.float64)
            self.tau=float(policy['tau']);self.residual_scale=np.asarray(policy['residual_scale'],dtype=np.float64)
            if self.centres.shape!=(5,2) or not np.isfinite(self.centres).all() or self.tau<.001 or not np.isfinite(self.tau):raise ValueError('Invalid geometric policy')
            if self.residual_scale.shape!=(12,) or not np.isfinite(self.residual_scale).all() or np.any(self.residual_scale<1):raise ValueError('Invalid residual scales')
        if self.quantum:
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(self.initialization_streams['paired_circuit_core_initialization'])))
            self.master_initial=rng.uniform(-.1,.1,(5,4,2,2))
            core=self.master_initial[:,:2].reshape(5,8).copy();head=np.zeros((5,6));head[:,0]=2.
            theta=np.column_stack((core,head)).ravel()
            self.initialization='Paired PCG64 master[5,4,2,2] uniform[-.1,.1], first2layers; head2X0+bias0'
        elif method.startswith('MLP'):
            d=self.input_dim;h=self.hidden
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(self.initialization_streams['mlp_initialization'])))
            a=np.sqrt(6/(d+h));b=np.sqrt(6/(h+1))
            theta=np.r_[rng.uniform(-a,a,d*h),np.zeros(h),rng.uniform(-b,b,h),0.]
            self.master_initial=theta.copy();self.initialization='PCG64 registered mlp_initialization; Xavier weights,zero biases; tanh16'
        else:
            theta=np.zeros(self.expert_size);self.master_initial=theta.copy();self.initialization='Zero coefficients including intercept'
        self.parameters=np.r_[theta,np.zeros(self.extra_size)]
        if len(self.parameters)!=PARAMETER_COUNTS[method]:raise RuntimeError('Parameter inventory mismatch')
        self.core_mask=np.zeros(len(self.parameters),dtype=bool)
        if self.quantum:
            for b in range(5):self.core_mask[14*b:14*b+8]=True
        self.head_mask=np.zeros_like(self.core_mask);self.head_mask[:self.expert_size]=True;self.head_mask&=~self.core_mask
        self.extra_mask=np.zeros_like(self.core_mask);self.extra_mask[self.expert_size:]=True
        self.training_objective='Stable native Bernoulli negative log likelihood'
        if method=='LR2':self.training_objective+=' plus0.0005*squared_weight_norm (intercept exempt)'

    def _inputs(self,x):
        x=np.asarray(x,dtype=np.float64)
        if x.ndim!=2 or x.shape[1]!=self.input_dim or not len(x) or not np.isfinite(x).all():raise ValueError('Invalid finite input matrix')
        if not np.isfinite(self.parameters).all():raise ValueError('Nonfinite parameters')
        return x

    def input_for(self,pop):return pop['x4'] if self.method=='MLP4' else pop['x']
    def route_for(self,pop):return None

    def gate(self,x):
        d=np.sum((x[:,None,:]-self.centres[None,:,:])**2,axis=2)
        scores=-d/self.tau
        if self.routing=='L':scores[:,:4]+=np.column_stack((x,np.ones(len(x))))@self.parameters[self.expert_size:].reshape(4,3).T
        logq=scores-logsumexp(scores,axis=1,keepdims=True)
        return logq,np.exp(logq),np.argmin(d,axis=1)

    def unpack_mlp(self,theta):
        d=self.input_dim;h=self.hidden
        return theta[:d*h].reshape(d,h),theta[d*h:(d+1)*h],theta[(d+1)*h:(d+2)*h],theta[-1]

    def _expert(self,x,theta):
        if self.quantum:
            f=circuits.moments(x,theta[:8].reshape(2,2,2),5);return f@theta[8:13]+theta[13],f
        if self.routed or self.method=='G121':
            f=trig_features(x,2 if self.routed else 5);return f@theta,f
        if self.method=='LR2':return x@theta[:2]+theta[2],x
        W,b,v,c=self.unpack_mlp(theta);f=np.tanh(x@W+b);return f@v+c,f

    def _forward(self,x):
        x=self._inputs(x);n=len(x);cache=[]
        if not self.routed or self.routing=='H':
            route=np.argmin(np.sum((x[:,None,:]-self.centres[None,:,:])**2,axis=2),axis=1) if self.routed else np.zeros(n,dtype=int)
            z=np.empty(n)
            for b in range(self.banks):
                ids=np.flatnonzero(route==b)
                if not len(ids):continue
                sl=slice(b*self.bank_width,(b+1)*self.bank_width);zb,f=self._expert(x[ids],self.parameters[sl]);z[ids]=zb;cache.append((ids,b,sl,f))
            lp=-np.logaddexp(0,-z);ln=-np.logaddexp(0,z)
            return {'p':sigmoid(z),'z':z,'lp':lp,'ln':ln,'cache':cache,'route':route}
        zs=np.empty((n,5))
        for b in range(5):
            sl=slice(b*self.bank_width,(b+1)*self.bank_width);zs[:,b],f=self._expert(x,self.parameters[sl]);cache.append((np.arange(n),b,sl,f))
        logq,q,route=self.gate(x);expert_lp=-np.logaddexp(0,-zs);expert_ln=-np.logaddexp(0,zs)
        mix_lp=logsumexp(logq+expert_lp,axis=1);mix_ln=logsumexp(logq+expert_ln,axis=1)
        z=mix_lp-mix_ln;lp=mix_lp;ln=mix_ln;phi=None
        extra_nonzero=self.routing=='R' and bool(np.any(self.parameters[self.expert_size:]!=0))
        if self.routing=='R':
            phi=residual_features(x,self.residual_scale)
            if extra_nonzero:
                z=z+phi@self.parameters[self.expert_size:];lp=-np.logaddexp(0,-z);ln=-np.logaddexp(0,z)
        return {'p':sigmoid(z),'z':z,'lp':lp,'ln':ln,'cache':cache,'route':route,'zs':zs,
                'logq':logq,'q':q,'expert_lp':expert_lp,'expert_ln':expert_ln,'mix_lp':mix_lp,'mix_ln':mix_ln,'phi':phi,'extra_nonzero':extra_nonzero}

    def predict_with_logits(self,x,route=None,features=None):
        if route is not None or features is not None:raise ValueError('v09 predicts from inputs plus frozen policy, no external route/cache')
        f=self._forward(x);return f['p'],f['z']
    def predict(self,x,route=None,features=None):return self.predict_with_logits(x,route,features)[0]
    def predict_population(self,pop):return self.predict(self.input_for(pop))
    def loss(self,y,p,z):return float(np.mean(native_losses(y,z)))

    def accounting(self,x,route=None,gradient=False,cached_features=False):
        if route is not None or cached_features:raise ValueError('No external route/cache')
        n=len(x);dense=self.routed and self.routing!='H';evaluations=n*(5 if dense else 1)
        forward=evaluations if self.quantum else 0;shift=16*forward if gradient else 0;circuits_n=forward+shift
        return {'model_record_visits':n,'expert_forward_examples':evaluations,'expert_backward_examples':evaluations if gradient else 0,
                'geometric_distance_pairs':5*n if self.routed else 0,'learned_gate_affine_examples':4*n if self.routing=='L' else 0,
                'mixture_expert_probability_values':5*n if dense else 0,'residual_feature_values':12*n if self.routing=='R' else 0,
                'forward_circuit_examples':forward,'shift_circuit_examples':shift,'circuit_examples':circuits_n,
                'layer_applications':2*circuits_n,'feature_ry_gates':4*circuits_n,'trainable_ry_gates':4*circuits_n,
                'trainable_rz_gates':4*circuits_n,'cx_gates':2*circuits_n,'readout_ry_gates':0,
                'moment_values_computed':5*circuits_n,'trig_feature_values':evaluations*(25 if self.routed else 121) if self.method.startswith('T_') or self.method=='G121' else 0,
                'mlp_hidden_evaluations':n*self.hidden,'measurement_settings_equivalent':2*circuits_n}

    def gradient(self,x,y,route=None,features=None):
        if route is not None or features is not None:raise ValueError('No external route/cache')
        x=self._inputs(x);y=check_labels(y,(len(x),));n=len(y);f=self._forward(x);g=np.zeros_like(self.parameters)
        objective=float(np.mean(-np.where(y==1,f['lp'],f['ln'])))
        if not self.routed or self.routing=='H':chain=(f['p']-y)/n
        else:
            post_pos=np.exp(f['logq']+f['expert_lp']-f['mix_lp'][:,None]);post_neg=np.exp(f['logq']+f['expert_ln']-f['mix_ln'][:,None])
            if self.routing=='R' and f['extra_nonzero']:
                chain=(f['p']-y)[:,None]*np.exp(f['logq']+f['expert_lp']+f['expert_ln']-f['mix_lp'][:,None]-f['mix_ln'][:,None])/n
            else:chain=((1-y)[:,None]*post_neg*sigmoid(f['zs'])-y[:,None]*post_pos*sigmoid(-f['zs']))/n
            if self.routing=='L':
                gate_chain=(f['q']-y[:,None]*post_pos-(1-y)[:,None]*post_neg)/n
                g[self.expert_size:]=(gate_chain[:,:4].T@np.column_stack((x,np.ones(n)))).ravel()
            elif self.routing=='R':g[self.expert_size:]=f['phi'].T@((f['p']-y)/n)
        for ids,b,sl,features_b in f['cache']:
            theta=self.parameters[sl];ch=chain[ids,b] if chain.ndim==2 else chain[ids]
            if self.quantum:
                jac=circuits.moment_jacobian(x[ids],theta[:8].reshape(2,2,2),5)
                g[sl]=np.r_[np.einsum('n,njm,m->j',ch,jac,theta[8:13]),features_b.T@ch,np.sum(ch)]
            elif self.routed or self.method=='G121':g[sl]=features_b.T@ch
            elif self.method=='LR2':
                g[:2]=x.T@ch+.001*theta[:2];g[2]=np.sum(ch);objective+=.0005*float(theta[:2]@theta[:2])
            else:
                W,bb,v,c=self.unpack_mlp(theta);dh=ch[:,None]*v[None,:]*(1-features_b**2)
                g[sl]=np.r_[(x[ids].T@dh).ravel(),dh.sum(0),features_b.T@ch,np.sum(ch)]
        self.last_gradient_diagnostics={'minimum_raw_probability':float(np.min(f['p'])),'maximum_raw_probability':float(np.max(f['p'])),
            'minimum_native_logit':float(np.min(f['z'])),'maximum_native_logit':float(np.max(f['z']))}
        return objective,g,f['p'],self.accounting(x,gradient=True)

    def routing_diagnostics(self,x):
        if not self.routed:return {'bank_count':1,'expert_evaluations_per_record':1}
        x=self._inputs(x);logq,q,nearest=self.gate(x)
        if self.routing=='H':q=np.eye(5)[nearest]
        entropy=-np.sum(np.where(q>0,q*np.where(np.isfinite(logq),logq,0),0),axis=1) if self.routing!='H' else np.zeros(len(x))
        return {'bank_count':5,'expert_evaluations_per_record':1 if self.routing=='H' else 5,
                'mean_weights':q.mean(0).tolist(),'argmax_counts':np.bincount(np.argmax(q,axis=1),minlength=5).tolist(),
                'nearest_counts':np.bincount(nearest,minlength=5).tolist(),'mean_entropy':float(entropy.mean()),
                'mean_effective_experts':float(np.exp(entropy).mean())}
