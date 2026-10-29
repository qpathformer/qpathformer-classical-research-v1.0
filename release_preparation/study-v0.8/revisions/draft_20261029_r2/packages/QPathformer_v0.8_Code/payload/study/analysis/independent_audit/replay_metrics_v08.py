"""Independent heldout metric reconstruction. Pure arrays, no study I/O."""
import math
import numpy as np
import reference_v08 as ref
from statistics_v08 import positive_metrics_and_grouped_ap


def score(y,p,z):
    y=np.asarray(y);p=np.asarray(p,float);z=np.asarray(z,float)
    if not len(y):return None
    base=ref.metrics(y,p);extra=positive_metrics_and_grouped_ap(y,p)
    n=len(y);positive=int(y.sum());confusion=np.asarray(base["confusion"])
    tn,fp,fn,tp=map(int,confusion.ravel())
    clipped=np.clip(p,ref.CLIP,1-ref.CLIP)
    per_record=np.where(y==1,-np.log(clipped),-np.log1p(-clipped))
    sd=float(np.std(per_record,ddof=1)) if n>1 else None
    critical=1.959963984540054;den=n+critical**2
    center=(positive+critical**2/2)/den
    radius=critical*math.sqrt(positive*(n-positive)/n+critical**2/4)/den
    native=ref.stable_logit_bce(y,z);is_clipped=(p<ref.CLIP)|(p>1-ref.CLIP)
    reliability=[]
    for k,entry in enumerate(base["reliability10"]):
        reliability.append({"bin":k,"lower":k/10,"upper":(k+1)/10,"upper_inclusive":k==9,
                            "n":entry["n"],"mean_probability":entry["mean_probability"],
                            "positive_fraction":entry["positive_fraction"]})
    f=[]
    for k in (0,1):
        denominator=confusion[k,:].sum()+confusion[:,k].sum()
        f.append(float(2*confusion[k,k]/denominator) if denominator else 0.)
    return {
        "n":n,"negative_count":n-positive,"positive_count":positive,"positive_prevalence":positive/n,
        "bce":base["bce"],"bce_record_sd":sd,"bce_record_se":None if sd is None else sd/math.sqrt(n),
        "macro_f1":base["macro_f1"],"accuracy":base["accuracy"],"class_f1":f,"brier":base["brier"],
        "ece10":base["ece10"],"reliability_bins":reliability,
        "positive_precision":extra["positive_precision"],"positive_recall":extra["positive_recall"],
        "grouped_tie_average_precision":extra["grouped_tie_average_precision"],
        "confusion_tn_fp_fn_tp":[tn,fp,fn,tp],"positive_prevalence_wilson95":[max(0.,center-radius),min(1.,center+radius)],
        "probability_min":float(p.min()),"probability_max":float(p.max()),
        "clipped_count":int(is_clipped.sum()),"clipped_wrong_count":int(np.sum(is_clipped&((p>=.5)!=y))),
        "exact_zero_count":int(np.sum(p==0)),"exact_one_count":int(np.sum(p==1)),
        "native_bce":native,"native_minus_clipped_bce":native-base["bce"],
        "native_logit_min":float(z.min()),"native_logit_max":float(z.max()),
        "absolute_logit_over20_count":int(np.sum(abs(z)>20)),"absolute_logit_over40_count":int(np.sum(abs(z)>40))}


def compare(expected,actual,path="metric",tolerance=2e-12):
    """Compare independently calculated fields; prose-only extra keys may remain."""
    if isinstance(expected,dict):
        for key,value in expected.items():
            if key not in actual:raise ValueError(f"{path}.{key} missing")
            compare(value,actual[key],path+"."+key,tolerance)
    elif isinstance(expected,list):
        if len(expected)!=len(actual):raise ValueError(f"{path} length differs")
        for i,(a,b) in enumerate(zip(expected,actual)):compare(a,b,path+f"[{i}]",tolerance)
    elif expected is None or isinstance(expected,(bool,str,int,np.integer)):
        if expected!=actual:raise ValueError(f"{path} exact value differs")
    else:
        if not math.isfinite(float(actual)) or abs(float(expected)-float(actual))>tolerance:
            raise ValueError(f"{path} numerical value differs")
