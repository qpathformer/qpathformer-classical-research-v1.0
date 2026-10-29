"""Nine v0.4 raw-coordinate models. No data access, routing fit or network.

For routed arms, each record activates exactly one bank. Gradients use the
global batch denominator, including an empty bank's zero raw gradient. Adam
updates all coordinates, so existing momentum can update an inactive bank.
"""
from __future__ import annotations
import numpy as np
import circuits

METHODS=('q2_global','q2_hash','q2_kmeans','mlp_global','mlp_hash','mlp_kmeans',
         'trig_global','trig_hash','trig_kmeans')
CLIP=1e-7


def sigmoid(z):
    z=np.asarray(z,dtype=np.float64); out=np.empty_like(z); mask=z>=0
    out[mask]=1/(1+np.exp(-z[mask])); e=np.exp(z[~mask]); out[~mask]=e/(1+e)
    return out


def binary_cross_entropy(y,p):
    y=np.asarray(y); p=np.asarray(p,dtype=np.float64)
    if y.shape!=p.shape or y.ndim!=1 or len(y)==0 or not np.isin(y,[0,1]).all():
        raise ValueError('Loss needs nonempty matching binary labels and probabilities')
    if not np.isfinite(p).all() or np.any(p<0) or np.any(p>1):raise ValueError('Invalid probability')
    pc=np.clip(p,CLIP,1-CLIP)
    return float(-np.mean(y*np.log(pc)+(1-y)*np.log1p(-pc)))


def trig_features(x):
    x=np.asarray(x,dtype=np.float64)
    u=np.pi*x
    phi=np.stack([np.ones_like(u),np.cos(u),np.sin(u),np.cos(2*u),np.sin(2*u)],axis=2)
    return (phi[:,0,:,None]*phi[:,1,None,:]).reshape(len(x),25)


class Adam:
    def __init__(self,shape,lr=.01):
        self.m=np.zeros(shape,dtype=np.float64); self.v=np.zeros(shape,dtype=np.float64)
        self.t=0; self.lr=lr
    def step(self,parameters,gradient):
        self.t+=1; self.m=.9*self.m+.1*gradient; self.v=.999*self.v+.001*gradient**2
        parameters-=self.lr*(self.m/(1-.9**self.t))/(np.sqrt(self.v/(1-.999**self.t))+1e-8)


def add_work(target,part):
    for key,value in part.items():target[key]=target.get(key,0)+int(value)
    return target


class Model:
    def __init__(self,method,seed):
        if method not in METHODS:raise ValueError('Unregistered method')
        self.method=method; self.seed=int(seed); self.family,self.routing=method.split('_')
        self.banks=1 if self.routing=='global' else 5
        self.hidden=32 if self.routing=='global' else 2
        if self.family=='q2':
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1])))
            # Retain the v0.3 master shape and bank prefixes, including RNG order.
            self.master_initial=rng.uniform(-.1,.1,(5,4,2,2))
            self.bank_width=8; self.parameters=self.master_initial[:self.banks,:2].reshape(-1).copy()
            self.initialization='PCG64 SeedSequence([seed,1]); uniform[-.1,.1] master[5,4,2,2]; first2layers; global bank0'
        elif self.family=='mlp':
            self.bank_width=4*self.hidden+1
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,4,self.hidden])))
            banks=[]
            for _ in range(self.banks):
                a=np.sqrt(6/(2+self.hidden)); b=np.sqrt(6/(self.hidden+1))
                banks.append(np.r_[rng.uniform(-a,a,2*self.hidden),np.zeros(self.hidden),
                                   rng.uniform(-b,b,self.hidden),0.])
            self.master_initial=np.asarray(banks); self.parameters=self.master_initial.ravel().copy()
            self.initialization='PCG64 SeedSequence([seed,4,width]); per-bank Xavier W then zero bias then Xavier v then zero output bias'
        else:
            self.bank_width=25; self.master_initial=np.zeros((self.banks,25))
            self.parameters=self.master_initial.ravel().copy()
            self.initialization='All coefficients zero; constant tensor feature is the sole intercept'

    def route_for(self,pop):
        return None if self.routing=='global' else pop[self.routing+'_route']

    def components(self,x,route=None):
        x=np.asarray(x,dtype=np.float64)
        if x.ndim!=2 or x.shape[1]!=2 or not np.isfinite(x).all():raise ValueError('Finite raw N-by-2 coordinates required')
        if self.routing=='global':
            if route is not None:raise ValueError('Global model must not receive a route')
            yield np.arange(len(x)),0,slice(0,self.bank_width)
        else:
            values=np.asarray(route)
            if values.shape!=(len(x),) or not np.isfinite(values).all() or np.any(values!=values.astype(int)) or np.any(values<0) or np.any(values>4):
                raise ValueError('Route must be integer bank0..4 for each record')
            for bank in range(5):
                ids=np.flatnonzero(values==bank)
                if len(ids):yield ids,bank,slice(bank*self.bank_width,(bank+1)*self.bank_width)

    def unpack_mlp(self,theta):
        h=self.hidden
        return theta[:2*h].reshape(2,h),theta[2*h:3*h],theta[3*h:4*h],theta[-1]

    def predict(self,x,route=None):
        x=np.asarray(x,dtype=np.float64); p=np.empty(len(x),dtype=np.float64)
        if not np.isfinite(self.parameters).all():raise ValueError('Nonfinite parameters')
        for ids,bank,sl in self.components(x,route):
            theta=self.parameters[sl]; f=x[ids]
            if self.family=='q2':p[ids]=circuits.predict(f,theta.reshape(2,2,2),2)
            elif self.family=='mlp':
                W,b,v,c=self.unpack_mlp(theta); p[ids]=sigmoid(np.maximum(f@W+b,0)@v+c)
            else:p[ids]=sigmoid(trig_features(f)@theta)
        return p

    def predict_population(self,pop):return self.predict(pop['x'],self.route_for(pop))

    def accounting(self,x,route=None,gradient=False):
        n=len(x); total=circuits.work(np.array([],dtype=np.int64))
        # Traversing components validates routing even for classical models.
        for ids,bank,sl in self.components(x,route):
            if self.family=='q2':add_work(total,circuits.work(np.full(len(ids),2),gradient=gradient))
        total['model_record_visits']=n
        total['bank_record_visits']=n
        total['classical_forward_examples']=n if self.family!='q2' else 0
        total['classical_backward_examples']=n if gradient and self.family!='q2' else 0
        total['trig_feature_values']=25*n*(2 if gradient else 1) if self.family=='trig' else 0
        total['mlp_hidden_evaluations']=n*self.hidden*(2 if gradient else 1) if self.family=='mlp' else 0
        return total

    def gradient(self,x,y,route=None):
        x=np.asarray(x,dtype=np.float64); y=np.asarray(y); n=len(y)
        if n==0 or len(x)!=n:raise ValueError('Nonempty matching batch required')
        p=self.predict(x,route); loss=binary_cross_entropy(y,p); grad=np.zeros_like(self.parameters)
        for ids,bank,sl in self.components(x,route):
            f=x[ids]; theta=self.parameters[sl]
            inactive=(p[ids]<CLIP)|(p[ids]>1-CLIP)
            if self.family=='q2':
                pc=np.clip(p[ids],CLIP,1-CLIP); chain=(pc-y[ids])/(pc*(1-pc)); chain[inactive]=0
                jac=circuits.jacobian(f,theta.reshape(2,2,2),2)
                grad[sl]=np.sum(jac*chain[:,None],axis=0)/n
            else:
                g=(p[ids]-y[ids])/n; g[inactive]=0
                if self.family=='mlp':
                    W,b,v,c=self.unpack_mlp(theta); z=f@W+b; h=np.maximum(z,0)
                    dz=g[:,None]*v[None,:]*(z>0)
                    grad[sl]=np.r_[(f.T@dz).ravel(),dz.sum(0),h.T@g,g.sum()]
                else:grad[sl]=trig_features(f).T@g
        return loss,grad,p,self.accounting(x,route,gradient=True)
