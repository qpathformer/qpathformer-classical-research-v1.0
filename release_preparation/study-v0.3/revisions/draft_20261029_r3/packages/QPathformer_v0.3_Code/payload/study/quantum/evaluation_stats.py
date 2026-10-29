"""Registered descriptive seed and conditional paired-record statistics.

Inputs are probabilities in method, seed, original record order. Five training
seeds are the replication unit; the shared test records are not independent
training replicates. No model execution or data loading occurs in this module.
"""
import numpy as np
from scipy.stats import t

METRICS=('bce','macro_f1','accuracy')


def metrics_array(y,p):
    y=np.asarray(y);p=np.asarray(p,float)
    if p.shape[-1]!=len(y) or len(y)==0 or not np.isfinite(p).all():raise ValueError('Invalid metric inputs')
    q=np.clip(p,1e-7,1-1e-7);pred=p>=.5
    bce=-np.mean(y*np.log(q)+(1-y)*np.log1p(-q),axis=-1)
    f=[]
    for label in (0,1):
        tp=np.sum((y==label)&(pred==label),axis=-1)
        den=np.sum(y==label)+np.sum(pred==label,axis=-1)
        f.append(np.divide(2*tp,den,out=np.zeros_like(tp,dtype=float),where=den!=0))
    return np.stack([bce,(f[0]+f[1])/2,np.mean(pred==y,axis=-1)],axis=-1)


def describe(values,confidence=.95):
    v=np.asarray(values,float)
    if v.ndim!=1 or len(v)!=5 or not np.isfinite(v).all():raise ValueError('Expected five finite training-seed values')
    mean=float(v.mean());sd=float(v.std(ddof=1));half=float(t.ppf((1+confidence)/2,4)*sd/np.sqrt(5))
    return {'n_training_seeds':5,'values':v.tolist(),'mean':mean,'sample_sd':sd,'confidence':confidence,
            't_interval':[mean-half,mean+half],'degrees_of_freedom':4}


def paired_bootstrap(y,p,replicates=2000,seed=98003):
    """Recompute each checkpoint metric then average seeds; shared record indices."""
    y=np.asarray(y);p=np.asarray(p,float)
    if p.ndim!=3 or p.shape[1]!=5:raise ValueError('Expected method x five seeds x record')
    rng=np.random.Generator(np.random.PCG64(seed))
    out=np.empty((replicates,p.shape[0],3),float)
    for k in range(replicates):
        ix=rng.integers(0,len(y),len(y))
        out[k]=metrics_array(y[ix],p[:,:,ix]).mean(axis=1)
    return out


def summarize(y,p,methods,protocol):
    values=metrics_array(y,p)
    boot=paired_bootstrap(y,p,protocol['record_bootstrap']['replicates'],protocol['record_bootstrap']['seed'])
    result={'metric_order':list(METRICS),'method_order':list(methods),'training_seeds':[601,602,603,604,605],
            'n_test_records':len(y),'aggregates':{},'contrasts':[],
            'uncertainty_scope':'Seed t intervals describe five paired training seeds on one fixed population. Record bootstrap is conditional on all fixed checkpoints and one test population, shared across methods/seeds; it excludes training, routing fit, model selection and new-population uncertainty. Do not pool these uncertainty sources.',
            'bootstrap':{'replicates':len(boot),'seed':98003,'bit_generator':'PCG64','percentile_method':'linear','unit':'test record; shared indices for every method and seed'}}
    for i,method in enumerate(methods):
        result['aggregates'][method]={name:describe(values[i,:,j]) for j,name in enumerate(METRICS)}
    primary=[tuple(v) for v in protocol['primary_contrasts']]
    pairs=primary+[tuple(v) for v in protocol['secondary_contrasts']]
    for a,b in pairs:
        i,j=methods.index(a),methods.index(b);is_primary=(a,b) in primary
        row={'first':a,'second':b,'family':'primary' if is_primary else 'secondary','direction':'first minus second','metrics':{}}
        for k,name in enumerate(METRICS):
            contrast=values[i,:,k]-values[j,:,k];samples=boot[:,i,k]-boot[:,j,k]
            entry={'seed':describe(contrast),'conditional_record_bootstrap95':np.quantile(samples,[.025,.975],method='linear').tolist()}
            if is_primary and name=='bce':
                alpha=.05/3;entry['seed_bonferroni']=describe(contrast,1-alpha)
                entry['conditional_record_bootstrap_bonferroni']=np.quantile(samples,[alpha/2,1-alpha/2],method='linear').tolist()
                entry['practical_improvement_threshold']=-.01
                entry['mean_reaches_practical_magnitude']=bool(contrast.mean()<=-.01)
            if name=='macro_f1':entry['percentage_point_mean']=100*float(contrast.mean())
            row['metrics'][name]=entry
        result['contrasts'].append(row)
    return result,boot
