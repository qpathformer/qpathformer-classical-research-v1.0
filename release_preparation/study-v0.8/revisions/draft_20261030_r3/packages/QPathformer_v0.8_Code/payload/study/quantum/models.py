"""Registered v0.8 weighted-gradient models, derived from reviewed v0.7.

All ten allowed arms optimize stable, unbounded logit BCE. Historical legacy
and fixed-core helper branches remain unreachable through METHODS. No network.
"""
from __future__ import annotations
import numpy as np
import circuits

BASE_METHODS={'MultiK':'qmulti_kmeans','MultiHash':'qmulti_hash',
              'TrigK':'trig_kmeans','TrigHash':'trig_hash','TrigG121':'trig121_global'}
ARM_METHODS={base+'_'+policy:method for base,method in BASE_METHODS.items() for policy in ('U','P')}
METHODS=tuple(BASE_METHODS.values())
PARAMETER_COUNTS=dict(zip(METHODS,(70,70,125,125,121)))
MOMENT_ORDER=('X0','X1','Z0','Z1','Z0Z1')
CLIP=1e-7


def sigmoid(z):
    z=np.asarray(z,dtype=np.float64); out=np.empty_like(z); positive=z>=0
    out[positive]=1/(1+np.exp(-z[positive])); e=np.exp(z[~positive]);out[~positive]=e/(1+e)
    return out


def check_labels(y,shape):
    y=np.asarray(y)
    if y.ndim!=1 or y.shape!=shape or len(y)==0 or not np.isin(y,[0,1]).all():
        raise ValueError('Nonempty matching binary labels required')
    return y


def binary_cross_entropy(y,p):
    p=np.asarray(p,dtype=np.float64);y=check_labels(y,p.shape)
    if not np.isfinite(p).all() or np.any(p<0) or np.any(p>1):raise ValueError('Invalid probabilities')
    q=np.clip(p,CLIP,1-CLIP)
    return float(-np.mean(y*np.log(q)+(1-y)*np.log1p(-q)))


def logit_cross_entropy(y,z):
    return float(np.mean(native_losses(y,z)))


def native_losses(y,z):
    """Per-record stable BCE; no clipping, reduction, or sampler derivative."""
    z=np.asarray(z,dtype=np.float64);y=check_labels(y,z.shape)
    if not np.isfinite(z).all():raise ValueError('Finite native logits required')
    return np.maximum(z,0)-y*z+np.log1p(np.exp(-np.abs(z)))


def checked_weights(sample_weight,n):
    if sample_weight is None:return np.ones(n,dtype=np.float64)
    w=np.asarray(sample_weight,dtype=np.float64)
    if w.shape!=(n,) or not np.isfinite(w).all() or np.any(w<=0):
        raise ValueError('Finite positive per-record weights required')
    return w


def trig_features(x,max_frequency=2):
    if max_frequency not in (2,5):raise ValueError('Registered frequencies are 2 and 5')
    x=np.asarray(x,dtype=np.float64);u=np.pi*x
    columns=[np.ones_like(u)]
    for frequency in range(1,max_frequency+1):columns.extend((np.cos(frequency*u),np.sin(frequency*u)))
    phi=np.stack(columns,axis=2)
    return (phi[:,0,:,None]*phi[:,1,None,:]).reshape(len(x),(2*max_frequency+1)**2)


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
    def __init__(self,method,seed,initialization_streams):
        if method not in METHODS:raise ValueError('Unregistered method')
        self.method=method;self.seed=int(seed);self.family,self.routing=method.split('_')
        self.banks=1 if self.routing=='global' else 5
        self.legacy=self.family=='q2';self.quantum=self.family.startswith('q')
        self.frozen=self.family=='qfrozen';self.native_logits=not self.legacy
        self.hidden=0;self.activation=None;self.moment_count=0
        self.max_frequency=5 if self.family=='trig121' else 2
        if not isinstance(initialization_streams,dict):raise ValueError('Explicit stream mapping required')
        for key in ('paired_circuit_core_initialization',):
            if key not in initialization_streams or int(initialization_streams[key])<0:raise ValueError('Missing explicit initialization stream')
        self.initialization_streams={k:int(initialization_streams[k]) for k in ('paired_circuit_core_initialization',)}
        self.core_parameters=np.empty((0,),dtype=np.float64)
        if self.quantum:
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(self.initialization_streams['paired_circuit_core_initialization'])))
            self.master_initial=rng.uniform(-.1,.1,(5,4,2,2))
            core=self.master_initial[:self.banks,:2].reshape(self.banks,8).copy()
            self.moment_count=0 if self.legacy else (1 if self.family=='qscalar' else 5)
            if self.legacy:self.parameters=core.ravel();self.bank_width=8
            else:
                head=np.zeros((self.banks,self.moment_count+1));head[:,0]=2.
                if self.frozen:
                    self.core_parameters=core.reshape(self.banks,2,2,2).copy()
                    self.parameters=head.ravel();self.bank_width=6
                else:
                    self.parameters=np.column_stack((core,head)).ravel();self.bank_width=8+head.shape[1]
            self.initialization='PCG64 SeedSequence(registered uint128 paired_circuit_core_initialization),Uniform[-.1,.1],master[5,4,2,2],first2layers; head2X0+bias0'
        elif self.family.startswith('mlp'):
            self.activation='tanh' if 'tanh' in self.family else 'relu'
            self.hidden=32 if self.family=='mlp' else int(self.family[3:].replace('relu','').replace('tanh',''))
            self.bank_width=4*self.hidden+1
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(self.initialization_streams['mlp_initialization'])))
            rows=[]
            for _ in range(self.banks):
                a=np.sqrt(6/(2+self.hidden));b=np.sqrt(6/(self.hidden+1))
                rows.append(np.r_[rng.uniform(-a,a,2*self.hidden),np.zeros(self.hidden),rng.uniform(-b,b,self.hidden),0.])
            self.master_initial=np.asarray(rows);self.parameters=self.master_initial.ravel().copy()
            self.initialization='PCG64 SeedSequence(registered uint128 mlp_initialization); per-bank Xavier W/v,zero biases'
        else:
            self.bank_width=(2*self.max_frequency+1)**2
            self.master_initial=np.zeros((self.banks,self.bank_width));self.parameters=self.master_initial.ravel().copy()
            self.initialization=f'All{self.bank_width} tensor-feature coefficients zero,including constant term'
        if len(self.parameters)!=PARAMETER_COUNTS[method]:raise RuntimeError('Registered parameter count mismatch')
        self.core_mask=np.zeros(len(self.parameters),dtype=bool)
        if self.quantum and not self.frozen:
            for bank in range(self.banks):self.core_mask[bank*self.bank_width:bank*self.bank_width+8]=True
        self.head_mask=~self.core_mask
        self.training_objective=('legacy clipped Born BCE; derivatives outside clip interval are zero' if self.legacy
                                 else 'stable native logit BCE; derivative sigmoid(logit)-label, no clipping zero-gradient rule')

    def route_for(self,pop):return None if self.routing=='global' else pop[self.routing+'_route']

    def components(self,x,route=None):
        x=np.asarray(x,dtype=np.float64)
        if x.ndim!=2 or x.shape[1]!=2 or not np.isfinite(x).all():raise ValueError('Finite N-by-2 rawcoordinates required')
        if self.routing=='global':
            if route is not None:raise ValueError('Global model must not receive route')
            yield np.arange(len(x)),0,slice(0,self.bank_width)
        else:
            r=np.asarray(route)
            if r.shape!=(len(x),) or not np.isfinite(r).all() or np.any(r!=r.astype(int)) or np.any(r<0) or np.any(r>4):
                raise ValueError('Each route must be integer0..4')
            for bank in range(5):
                ids=np.flatnonzero(r==bank)
                if len(ids):yield ids,bank,slice(bank*self.bank_width,(bank+1)*self.bank_width)

    def unpack_mlp(self,theta):
        h=self.hidden
        return theta[:2*h].reshape(2,h),theta[2*h:3*h],theta[3*h:4*h],theta[-1]

    def checked_features(self,x,features):
        if features is None:return None
        a=np.asarray(features,dtype=np.float64)
        if not self.frozen or a.shape!=(len(x),5) or not np.isfinite(a).all() or np.any(abs(a)>1+2e-12):
            raise ValueError('Only frozen-core models accept finite N-by-5 cached moments')
        return a

    def cache_features(self,x,route):
        if not self.frozen:raise ValueError('Only frozen core may cache features')
        x=np.asarray(x,dtype=np.float64);features=np.empty((len(x),5),dtype=np.float64)
        for ids,bank,sl in self.components(x,route):features[ids]=circuits.moments(x[ids],self.core_parameters[bank],5)
        return features

    def predict_with_logits(self,x,route=None,features=None):
        x=np.asarray(x,dtype=np.float64);features=self.checked_features(x,features)
        p=np.empty(len(x),dtype=np.float64);logits=None if self.legacy else np.empty(len(x),dtype=np.float64)
        if not np.isfinite(self.parameters).all():raise ValueError('Nonfinite parameters')
        for ids,bank,sl in self.components(x,route):
            theta=self.parameters[sl];f=x[ids]
            if self.legacy:p[ids]=circuits.predict(f,theta.reshape(2,2,2),2)
            else:
                if self.quantum:
                    core=self.core_parameters[bank] if self.frozen else theta[:8].reshape(2,2,2)
                    head=theta if self.frozen else theta[8:]
                    m=features[ids] if features is not None else circuits.moments(f,core,self.moment_count)
                    z=m@head[:-1]+head[-1]
                elif self.family.startswith('mlp'):
                    W,b,v,c=self.unpack_mlp(theta);h=f@W+b
                    h=np.tanh(h) if self.activation=='tanh' else np.maximum(h,0)
                    z=h@v+c
                else:z=trig_features(f,self.max_frequency)@theta
                logits[ids]=z;p[ids]=sigmoid(z)
        return p,logits

    def predict(self,x,route=None,features=None):return self.predict_with_logits(x,route,features)[0]
    def predict_population(self,pop,features=None):return self.predict(pop['x'],self.route_for(pop),features)
    def loss(self,y,p,logits):return binary_cross_entropy(y,p) if self.legacy else logit_cross_entropy(y,logits)

    def accounting(self,x,route=None,gradient=False,cached_features=False):
        n=len(x);list(self.components(x,route))
        if cached_features and not self.frozen:raise ValueError('Cache accounting only for frozen core')
        result=circuits.work(np.array([],dtype=np.int64))
        if self.legacy:add_work(result,circuits.work(np.full(n,2),gradient=gradient))
        core_passes=0
        if self.quantum and not self.legacy and not cached_features:
            core_passes=n*(17 if gradient and not self.frozen else 1)
            result.update(forward_circuit_examples=n,shift_circuit_examples=core_passes-n,
                circuit_examples=core_passes,layer_applications=2*core_passes,
                feature_ry_gates=4*core_passes,trainable_ry_gates=4*core_passes,
                trainable_rz_gates=4*core_passes,cx_gates=2*core_passes,readout_ry_gates=0)
        result.update(model_record_visits=n,bank_record_visits=n,
            core_statevector_examples=result['circuit_examples'],moment_values_computed=core_passes*self.moment_count,
            frozen_cached_feature_rows=n if cached_features else 0,
            classical_forward_examples=n if not self.legacy else 0,
            classical_backward_examples=n if gradient and not self.legacy else 0,
            head_feature_values=n*self.moment_count if self.quantum and not self.legacy else 0,
            trig_feature_values=self.bank_width*n if self.family.startswith('trig') else 0,
            mlp_hidden_evaluations=n*self.hidden,
            measurement_settings_equivalent=(2 if self.moment_count==5 else 1)*core_passes if not self.legacy else result['circuit_examples'])
        result['fixed_core_ry_gates']=result['trainable_ry_gates'] if self.frozen else 0
        result['fixed_core_rz_gates']=result['trainable_rz_gates'] if self.frozen else 0
        if self.frozen:result['trainable_ry_gates']=0;result['trainable_rz_gates']=0
        return result

    def cache_accounting(self,x,route):
        result=self.accounting(x,route)
        result.update(model_record_visits=0,bank_record_visits=0,classical_forward_examples=0,head_feature_values=0)
        result['feature_preparation_records']=len(x)
        return result

    def gradient(self,x,y,route=None,features=None,sample_weight=None):
        x=np.asarray(x,dtype=np.float64);y=check_labels(y,(len(x),));n=len(y)
        weights=checked_weights(sample_weight,n)
        features=self.checked_features(x,features);p=np.empty(n);logits=None if self.legacy else np.empty(n)
        gradient=np.zeros_like(self.parameters)
        for ids,bank,sl in self.components(x,route):
            f=x[ids];theta=self.parameters[sl]
            if self.legacy:
                probability=circuits.predict(f,theta.reshape(2,2,2),2);p[ids]=probability
                q=np.clip(probability,CLIP,1-CLIP);chain=(q-y[ids])/(q*(1-q))
                chain[(probability<CLIP)|(probability>1-CLIP)]=0
                gradient[sl]=np.sum(circuits.jacobian(f,theta.reshape(2,2,2),2)*chain[:,None],axis=0)/n
                continue
            if self.quantum:
                core=self.core_parameters[bank] if self.frozen else theta[:8].reshape(2,2,2)
                head=theta if self.frozen else theta[8:]
                m=features[ids] if features is not None else circuits.moments(f,core,self.moment_count)
                z=m@head[:-1]+head[-1];probability=sigmoid(z);g=weights[ids]*(probability-y[ids])/n
                hgrad=np.r_[m.T@g,g.sum()]
                if self.frozen:gradient[sl]=hgrad
                else:
                    jac=circuits.moment_jacobian(f,core,self.moment_count)
                    cgrad=np.einsum('n,njm,m->j',g,jac,head[:-1])
                    gradient[sl]=np.r_[cgrad,hgrad]
            elif self.family.startswith('mlp'):
                W,b,v,c=self.unpack_mlp(theta);a=f@W+b
                h=np.tanh(a) if self.activation=='tanh' else np.maximum(a,0)
                z=h@v+c;probability=sigmoid(z);g=weights[ids]*(probability-y[ids])/n
                dz=g[:,None]*v[None,:]*((1-h*h) if self.activation=='tanh' else (a>0))
                gradient[sl]=np.r_[(f.T@dz).ravel(),dz.sum(0),h.T@g,g.sum()]
            else:
                phi=trig_features(f,self.max_frequency);z=phi@theta;probability=sigmoid(z);g=weights[ids]*(probability-y[ids])/n
                gradient[sl]=phi.T@g
            logits[ids]=z;p[ids]=probability
        # Diagnostics from the existing forward arrays; no extra model execution.
        self.last_gradient_diagnostics={'minimum_raw_probability':float(np.min(p)),
            'maximum_raw_probability':float(np.max(p)),
            'minimum_native_logit':None if logits is None else float(np.min(logits)),
            'maximum_native_logit':None if logits is None else float(np.max(logits))}
        return float(np.mean(weights*native_losses(y,logits))),gradient,p,self.accounting(x,route,True,features is not None)
