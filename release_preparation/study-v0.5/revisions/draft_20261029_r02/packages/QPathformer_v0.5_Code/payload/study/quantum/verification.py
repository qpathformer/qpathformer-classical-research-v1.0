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
    for key in ('bce','macro_f1','accuracy','brier','ece10'):
        s.require(abs(actual[key]-recorded[key])<=CANONICAL_METRIC_TOLERANCE,f'Canonical {key} mismatch')
    for a,b in zip(actual['reliability10'],recorded['reliability10']):
        for key in ('bin','lower','upper','count'):s.require(a[key]==b[key],'Reliability bin mismatch')
        for key in ('mean_probability','fraction_positive'):
            s.require(a[key] is None and b[key] is None or a[key] is not None and b[key] is not None and abs(a[key]-b[key])<=CANONICAL_METRIC_TOLERANCE,'Reliability mean mismatch')
    s.require(len(recorded['reliability10'])==10,'Ten reliability bins required')


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


def scalar_reference_with_logits(method,parameters,x,route=None,core_parameters=None):
    """Author oracle independent of production gate/feature/MLP forward helpers."""
    family,routing=method.split('_');h=32 if family=='mlp' else int(family[3:].replace('relu','').replace('tanh','')) if family.startswith('mlp') else 0
    width={'q2':8,'qscalar':10,'qmulti':14,'qfrozen':6}.get(family,4*h+1 if h else 25)
    result=[];logits=[];I=np.eye(2);X=np.array([[0.,1.],[1.,0.]]);Z=np.diag([1.,-1.])
    operators=[np.kron(X,I),np.kron(I,X),np.kron(Z,I),np.kron(I,Z),np.kron(Z,Z)]
    for i,xy in enumerate(x):
        bank=0 if routing=='global' else int(route[i]);theta=parameters[bank*width:(bank+1)*width]
        if family=='q2':
            result.append(reference_v03.probability(xy,theta.reshape(2,2,2),2));continue
        if family.startswith('q'):
            core=core_parameters[bank] if family=='qfrozen' else theta[:8].reshape(2,2,2)
            head=theta if family=='qfrozen' else theta[8:]
            psi=reference_v03.unitary(xy,core,2,beta=0)[:,0]
            moments=[float(np.real(np.vdot(psi,P@psi))) for P in operators[:len(head)-1]]
            logit=sum(float(head[j])*moments[j] for j in range(len(moments)))+float(head[-1])
        elif family.startswith('mlp'):
            hidden=[xy[0]*theta[j]+xy[1]*theta[h+j]+theta[2*h+j] for j in range(h)]
            hidden=[math.tanh(a) if 'tanh' in family else max(0.,a) for a in hidden]
            logit=sum(hidden[j]*theta[3*h+j] for j in range(h))+theta[-1]
        else:
            def phi(t):return [1.,math.cos(math.pi*t),math.sin(math.pi*t),math.cos(2*math.pi*t),math.sin(2*math.pi*t)]
            a,b=phi(xy[0]),phi(xy[1]);logit=sum(theta[j*5+k]*a[j]*b[k] for j in range(5) for k in range(5))
        logits.append(logit)
        if logit>=0:result.append(1/(1+math.exp(-logit)))
        else:
            value=math.exp(logit);result.append(value/(1+value))
    return np.asarray(result),None if family=='q2' else np.asarray(logits)


def scalar_reference(method,parameters,x,route=None,core_parameters=None):
    return scalar_reference_with_logits(method,parameters,x,route,core_parameters)[0]


def verify_native(y,canonical_logits,reference_logits,canonical_loss):
    if canonical_logits is None:
        s.require(reference_logits is None,'Legacy model must not invent native logits')
        return {'has_native_logits':False}
    a=np.asarray(canonical_logits);b=np.asarray(reference_logits)
    s.require(a.shape==b.shape==np.asarray(y).shape and np.isfinite(a).all() and np.isfinite(b).all(),'Invalid native logits')
    maximum=float(np.max(abs(a-b)));s.require(maximum<=1e-9,'Independent native logits mismatch')
    loss=float(np.mean(np.maximum(b,0)-y*b+np.log1p(np.exp(-abs(b)))))
    error=abs(loss-canonical_loss);s.require(error<=1e-8,'Independent native loss mismatch')
    return {'has_native_logits':True,'maximum_logit_error':maximum,'independent_native_loss':loss,'native_loss_error':error}
