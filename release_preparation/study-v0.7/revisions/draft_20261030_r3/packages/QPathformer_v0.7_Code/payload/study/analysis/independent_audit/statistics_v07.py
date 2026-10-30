"""Independent v0.7 statistics; pure functions, never read study outcomes."""
import math
import numpy as np

FAMILIES=("checkerboard","spiral","annulus","disks")
ARMS=("ScalarK","MultiK","MultiHash","TrigK","TrigHash","TrigG25","TrigG121","MLPG129")
CONTRASTS=(("MultiK","ScalarK"),("MultiK","MultiHash"),("MultiK","TrigK"),
           ("TrigK","TrigHash"),("TrigK","TrigG121"))
SEEDS=(1401,1402)
CONFIDENCE=.9975
PRACTICAL=.01


def need(condition,message):
    if not condition:raise ValueError(message)


def cdf_t7(x):
    """Exact df7 density integral after x=sqrt(7)*tan(theta).

    cos(theta)^6 integrates as a short even-angle trigonometric series.
    This implementation does not call scipy or the official statistics module.
    """
    angle=math.atan(float(x)/math.sqrt(7.))
    integral=(10*angle+7.5*math.sin(2*angle)+1.5*math.sin(4*angle)+math.sin(6*angle)/6)/(10*math.pi)
    return .5+integral


def quantile_t7(probability):
    need(0<float(probability)<1,"Interior probability required")
    if probability==.5:return 0.
    if probability<.5:return -quantile_t7(1-probability)
    low=0.;high=1.
    while cdf_t7(high)<probability:
        high*=2
        need(high<1e7,"Quantile outside supported numeric range")
    for _ in range(100):
        middle=(low+high)/2
        if cdf_t7(middle)<probability:low=middle
        else:high=middle
    return (low+high)/2


def population_interval(differences):
    values=np.asarray(differences,dtype=float)
    need(values.shape==(8,) and np.isfinite(values).all(),"Exactly eight finite population differences required")
    mean=math.fsum(values.tolist())/8
    sample_variance=math.fsum((float(v)-mean)**2 for v in values)/7
    standard_deviation=math.sqrt(sample_variance)
    standard_error=standard_deviation/math.sqrt(8)
    critical=quantile_t7((1+CONFIDENCE)/2)
    low,high=mean-critical*standard_error,mean+critical*standard_error
    return {"n_independent_populations":8,"df":7,"confidence":CONFIDENCE,
            "population_differences":values.tolist(),"mean_difference":mean,
            "sample_sd":standard_deviation,"standard_error":standard_error,
            "critical_t":critical,"lower":low,"upper":high,
            "direction_supported_first":high<0,
            "exceeds_practical_reference_first":high<-PRACTICAL,
            "direction_supported_second":low>0,
            "exceeds_practical_reference_second":low>PRACTICAL,
            "crosses_zero":low<=0<=high,
            "zero_variance":standard_deviation==0,
            "interpretation_limit":"Nominal small-sample t interval under population-difference assumptions; a zero-crossing interval does not establish equivalence."}


def primary_contrasts(rows,population_metadata):
    """rows require population_id, training_seed_id, arm and common_bce.

    Reject missing, duplicate or extra confirmation identities. Historical
    selected populations and record-level replicates cannot inflate the unit N.
    """
    need(len(rows)==512,"All 512 confirmation endpoint rows required")
    populations={p["population_id"]:p for p in population_metadata}
    need(len(populations)==32,"Exactly 32 confirmation populations required")
    by_id={}
    for row in rows:
        key=(row["population_id"],row["training_seed_id"],row["arm"])
        need(key not in by_id,"Duplicate confirmation row")
        need(row["population_id"] in populations and row["training_seed_id"] in SEEDS and row["arm"] in ARMS,"Unregistered confirmation row")
        need(math.isfinite(float(row["common_bce"])),"Nonfinite common BCE")
        by_id[key]=float(row["common_bce"])
    expected={(p,s,a) for p in populations for s in SEEDS for a in ARMS}
    need(set(by_id)==expected,"Confirmation identity matrix incomplete")
    result=[]
    for family in FAMILIES:
        chosen=sorted(p for p,meta in populations.items() if meta["family"]==family)
        need(len(chosen)==8,"Eight independent populations per family required")
        for first,second in CONTRASTS:
            paired=[]
            for population in chosen:
                differences=[by_id[population,seed,first]-by_id[population,seed,second] for seed in SEEDS]
                paired.append({"population_id":population,"paired_seed_differences":differences,
                               "mean_difference":math.fsum(differences)/2})
            interval=population_interval([r["mean_difference"] for r in paired])
            result.append({"family":family,"first":first,"second":second,
                           "paired_population_records":paired,**interval})
    need(len(result)==20,"Primary comparison family must remain exactly twenty")
    return result


def positive_metrics_and_grouped_ap(labels,probabilities):
    y=np.asarray(labels);scores=np.asarray(probabilities,float)
    need(y.shape==scores.shape and y.ndim==1 and len(y)>0 and np.isin(y,[0,1]).all(),"Nonempty binary labels required")
    need(np.isfinite(scores).all() and np.all((scores>=0)&(scores<=1)),"Probability range invalid")
    predicted=scores>=.5;positive=int(y.sum());tp=int(np.sum(predicted&(y==1)));predicted_count=int(predicted.sum())
    precision=tp/predicted_count if predicted_count else None
    recall=tp/positive if positive else None
    order=np.argsort(-scores,kind="stable");sorted_y=y[order];sorted_score=scores[order]
    retrieved=0;true_positives=0;weighted_precision=0.;groups=[]
    i=0
    while i<len(y):
        end=i+1
        while end<len(y) and sorted_score[end]==sorted_score[i]:end+=1
        new_positive=int(np.sum(sorted_y[i:end]));true_positives+=new_positive;retrieved=end
        group_precision=true_positives/retrieved
        weighted_precision+=new_positive*group_precision
        groups.append({"score":float(sorted_score[i]),"records":end-i,"positive_records":new_positive,
                       "cumulative_records":retrieved,"cumulative_positive_records":true_positives,
                       "precision":group_precision})
        i=end
    return {"positive_records":positive,"predicted_positive_records":predicted_count,
            "true_positive_records":tp,"positive_precision":precision,"positive_recall":recall,
            "grouped_tie_average_precision":weighted_precision/positive if positive else None,
            "score_groups":groups,"undefined_precision_when_no_predictions":predicted_count==0,
            "undefined_recall_and_ap_when_no_positive":positive==0}


def validation_milestones(f1_by_round):
    values=np.asarray(f1_by_round,float)
    need(values.shape==(200,) and np.isfinite(values).all() and np.all((values>=0)&(values<=1)),"Full 200-round validation trajectory required")
    output=[]
    for level in (.9,.95,.97):
        reaches=np.flatnonzero(values>=level)
        first=int(reaches[0])+1 if len(reaches) else None
        output.append({"threshold":level,"reached":first is not None,"first_observed_round":first,
                       "first_observed_optimizer_update":None if first is None else first*75,
                       "evaluation_spacing_updates":75,"right_censored_after_updates":None if first is not None else 15000,
                       "meaning":"First observed validation crossing, not a continuously observed stopping time; training always completes."})
    return output
