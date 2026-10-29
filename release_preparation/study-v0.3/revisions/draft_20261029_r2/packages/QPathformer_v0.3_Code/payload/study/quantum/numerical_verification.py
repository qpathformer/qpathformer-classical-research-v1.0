"""Root-approved verification-only handling of floating-point threshold ambiguity.

Canonical probabilities and p>=0.5 decisions never change. Sensitivities are
diagnostic class assignments, never trained models, BCE values or selections.
"""
from pathlib import Path
import hashlib
import numpy as np
import replay

PROTOCOL_PATH=Path(__file__).resolve().parent.parent/'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json'
PROTOCOL_SHA='049f4a627fda5fa08c739cc53375aa104e28d223bb78d525841d0f01d7931e0e'
PROBABILITY_TOLERANCE=2e-12
BCE_TOLERANCE=1e-10
BAND=32*np.finfo(np.float64).eps
CASES=('all_ambiguous_to0','all_ambiguous_to1','label_assisted_all_incorrect','label_assisted_all_correct')


def require(condition,message):
    if not condition:raise RuntimeError(message)


def verify_protocol():
    require(hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()==PROTOCOL_SHA,'Numerical recovery protocol changed')


def classification_metrics(y,pred):
    y=np.asarray(y,int);pred=np.asarray(pred,int)
    confusion=np.array([[np.sum((y==a)&(pred==b)) for b in (0,1)] for a in (0,1)],dtype=int)
    f=[]
    for label in (0,1):
        den=int(confusion[label].sum()+confusion[:,label].sum())
        f.append(float(2*confusion[label,label]/den) if den else 0.)
    return {'n':len(y),'confusion':confusion.tolist(),'macro_f1':float(sum(f)/2),'accuracy':float(np.trace(confusion)/len(y))}


def check_canonical_metrics(canonical,recorded):
    for key in ('n','confusion','clipped','macro_f1','accuracy'):
        require(canonical[key]==recorded[key],f'Canonical recorded {key} mismatch')
    require(abs(canonical['bce']-recorded['bce'])<=BCE_TOLERANCE,'Canonical recorded BCE mismatch')


def verify_pair(pop,canonical_probability,reference_probability):
    p=np.asarray(canonical_probability,float);r=np.asarray(reference_probability,float);y=np.asarray(pop['y'],int)
    require(p.shape==r.shape==y.shape and len(y)>0 and np.isfinite(p).all() and np.isfinite(r).all(),'Invalid verification inputs')
    require(np.all((y==0)|(y==1)),'Invalid binary labels')
    error=float(np.max(abs(p-r)));require(error<=PROBABILITY_TOLERANCE,'Independent probability mismatch')
    canonical=replay.metrics(y,p);reference=replay.metrics(y,r)
    bce_error=abs(canonical['bce']-reference['bce']);require(bce_error<=BCE_TOLERANCE,'Independent BCE mismatch')
    cp=p>=.5;rp=r>=.5;cm=abs(p-.5)<=BAND;rm=abs(r-.5)<=BAND;different=cp!=rp
    outside=different&~(cm&rm)
    require(not np.any(outside),'Class disagreement outside the fixed numerical ambiguity band')
    def counts(mask):
        return {'n':int(np.sum(mask)),'canonical_near_band':int(np.sum(cm&mask)),
                'reference_near_band':int(np.sum(rm&mask)),'union_near_band':int(np.sum((cm|rm)&mask)),
                'class_disagreements':int(np.sum(different&mask)),'outside_band_class_disagreements':int(np.sum(outside&mask)),
                'exact_class_agreement':bool(not np.any(different&mask))}
    sensitivities={}
    for case in CASES:
        pred=cp.astype(int).copy()
        if case=='all_ambiguous_to0':pred[cm]=0
        elif case=='all_ambiguous_to1':pred[cm]=1
        elif case=='label_assisted_all_incorrect':pred[cm]=1-y[cm]
        else:pred[cm]=y[cm]
        sensitivities[case]=classification_metrics(y,pred)
    records=[]
    for i in np.flatnonzero(different):
        records.append({'record_id':int(pop['ids'][i]),'original_depth':int(pop['depth'][i]),'hash_route':int(pop['hash_route'][i]),
                        'kmeans_route':int(pop['kmeans_route'][i]),'label':int(y[i]),'canonical_probability':float(p[i]),
                        'reference_probability':float(r[i]),'canonical_class':int(cp[i]),'reference_class':int(rp[i])})
    return {'protocol_sha256':PROTOCOL_SHA,'probability_tolerance':PROBABILITY_TOLERANCE,'bce_tolerance':BCE_TOLERANCE,
            'band_half_width':float(BAND),'band_definition':'Inclusive32float64eps around0.5; engineering convention, not a formal error or confidence bound.',
            'maximum_probability_error':error,'independent_bce_error':float(bce_error),'counts':counts(np.ones(len(y),bool)),
            'by_original_depth':{str(d):counts(pop['depth']==d) for d in range(1,5)},
            'by_route':{kind:{str(k):counts(pop[kind+'_route']==k) for k in range(5)} for kind in ('hash','kmeans')},
            'canonical_metrics':canonical,'raw_reference_metrics':reference,
            'raw_reference_minus_canonical':{k:reference[k]-canonical[k] for k in ('bce','macro_f1','accuracy')},
            'disagreements':records,'sensitivity':sensitivities,
            'sensitivity_scope':'Canonical near-band mask only. All0/all1 are alternative conventions, not extrema. Label-assisted all-incorrect/all-correct are diagnostic extrema, not attainable models or statistical intervals. No BCE is assigned and no favorable case is selected.',
            'verification_scope':'Canonical saved metric reproducibility plus independent probability/BCE agreement and no unexplained threshold disagreement. Exact classifier agreement is reported separately, never implied by PASS.'}
