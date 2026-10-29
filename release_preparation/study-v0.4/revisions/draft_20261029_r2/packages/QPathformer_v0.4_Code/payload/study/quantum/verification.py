"""Verification-only canonical classification and independent-oracle checks.

32eps is an explicitly registered numerical convention, not an uncertainty
interval. Label-assisted extrema are diagnostics, never fitted classifiers.
"""
import math
import numpy as np
import reference_v03
import study as s

PROBABILITY_TOLERANCE=2e-12
INDEPENDENT_BCE_TOLERANCE=1e-8
CANONICAL_METRIC_TOLERANCE=2e-12
BAND=32*np.finfo(np.float64).eps


def classification(y,pred):
    y=np.asarray(y);pred=np.asarray(pred)
    c=[[int(np.sum((y==a)&(pred==b))) for b in (0,1)] for a in (0,1)]
    f=[]
    for k in (0,1):
        den=2*c[k][k]+c[k][1-k]+c[1-k][k];f.append(2*c[k][k]/den if den else 0.)
    return {'confusion':c,'macro_f1':float(np.mean(f)),'accuracy':float(np.mean(y==pred)),'n':len(y)}


def check_canonical(actual,recorded):
    for key in ('n','clipped','confusion'):s.require(actual[key]==recorded[key],f'Canonical {key} mismatch')
    for key in ('bce','macro_f1','accuracy'):
        s.require(abs(actual[key]-recorded[key])<=CANONICAL_METRIC_TOLERANCE,f'Canonical {key} mismatch')


def verify_pair(pop,p,reference):
    p=np.asarray(p,dtype=float);reference=np.asarray(reference,dtype=float)
    s.require(p.shape==reference.shape==(len(pop['y']),),'Probability shape mismatch')
    s.require(np.isfinite(reference).all() and np.all((reference>=0)&(reference<=1)),'Invalid oracle probability')
    error=float(np.max(abs(p-reference)));s.require(error<=PROBABILITY_TOLERANCE,'Independent probability mismatch')
    canonical=s.metrics(pop['y'],p);other=s.metrics(pop['y'],reference)
    bce_error=abs(canonical['bce']-other['bce']);s.require(bce_error<=INDEPENDENT_BCE_TOLERANCE,'Independent BCE mismatch')
    mask=abs(p-.5)<=BAND;othermask=abs(reference-.5)<=BAND
    pred=p>=.5;refpred=reference>=.5;diff=pred!=refpred;outside=diff&~(mask&othermask)
    s.require(not np.any(outside),'Class disagreement outside both-in-band condition')
    sensitivity={}
    for name,value in (('all_ambiguous_to0',0),('all_ambiguous_to1',1),
                       ('label_assisted_all_incorrect',1-pop['y']),('label_assisted_all_correct',pop['y'])):
        alt=pred.copy();alt[mask]=value if np.isscalar(value) else value[mask]
        sensitivity[name]=classification(pop['y'],alt)
    records=[{'record_id':int(pop['ids'][i]),'label':int(pop['y'][i]),'hash_route':int(pop['hash_route'][i]),
              'kmeans_route':int(pop['kmeans_route'][i]),'canonical_probability':float(p[i]),'reference_probability':float(reference[i]),
              'canonical_prediction':int(pred[i]),'reference_prediction':int(refpred[i])} for i in np.flatnonzero(diff)]
    counts={'n':len(p),'canonical_near_band':int(mask.sum()),'reference_near_band':int(othermask.sum()),
            'union_near_band':int((mask|othermask).sum()),'class_disagreements':int(diff.sum()),
            'outside_band_class_disagreements':int(outside.sum()),'exact_class_agreement':not bool(np.any(diff))}
    return {'maximum_probability_error':error,'independent_bce_error':bce_error,'band_half_width':float(BAND),
            'counts':counts,'canonical_metrics':canonical,'raw_reference_metrics':other,'disagreements':records,
            'sensitivity':sensitivity,'scope':'Canonical saved probabilities and p>=.5 retained. Constant assignments are conventions; label-assisted cases are diagnostic extrema, not attainable models.'}


def scalar_reference(method,parameters,x,route=None):
    """Author oracle independent of production gate/feature/MLP forward helpers."""
    family,routing=method.split('_');h=32 if routing=='global' else 2
    width=8 if family=='q2' else 4*h+1 if family=='mlp' else 25
    result=[]
    for i,xy in enumerate(x):
        bank=0 if routing=='global' else int(route[i]);theta=parameters[bank*width:(bank+1)*width]
        if family=='q2':
            result.append(reference_v03.probability(xy,theta.reshape(2,2,2),2));continue
        if family=='mlp':
            hidden=[max(0.,xy[0]*theta[j]+xy[1]*theta[h+j]+theta[2*h+j]) for j in range(h)]
            logit=sum(hidden[j]*theta[3*h+j] for j in range(h))+theta[-1]
        else:
            def phi(t):return [1.,math.cos(math.pi*t),math.sin(math.pi*t),math.cos(2*math.pi*t),math.sin(2*math.pi*t)]
            a,b=phi(xy[0]),phi(xy[1]);logit=sum(theta[j*5+k]*a[j]*b[k] for j in range(5) for k in range(5))
        if logit>=0:result.append(1/(1+math.exp(-logit)))
        else:
            value=math.exp(logit);result.append(value/(1+value))
    return np.asarray(result)
