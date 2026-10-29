"""Independent post-release exposure/learning diagnostics; no producer imports."""
from pathlib import Path
import math
import numpy as np
import audit_endpoints_v08 as audit
import replay_metrics_v08 as metrics
import statistics_v08 as statistics

EXPOSURE_FIELDS=("mean_post_warmup_effective_records","mean_unique_records_per_round",
    "flipped_training_record_fraction","flipped_label_draw_fraction",
    "noise_draw_fraction_minus_record_fraction","maximum_record_total_visits")

def load_training(root,population,seal):
    """Only the gated replay body may call this latent-data loader."""
    q=Path(root)/"quantum/data";train=q/f"{population}_train.npz"
    latent=q/seal["diagnostics"][population]["file"]
    audit.need(audit.sha(train)==seal["files"][train.name]["sha256"],"Released training data hash differs")
    audit.need(audit.sha(latent)==seal["diagnostics"][population]["sha256"],"Released latent data hash differs")
    with np.load(train,allow_pickle=False) as z:
        data={key:z[key] for key in ("ids","y","hash_route","kmeans_route")}
    with np.load(latent,allow_pickle=False) as z:
        audit.same(data["ids"],z["train_ids"],"Latent/observed training IDs differ")
        clean=z["train_clean_y"];flips=z["train_label_flip"]
    audit.need(data["ids"].shape==clean.shape==flips.shape==(4800,),"Latent training shape differs")
    audit.need(np.isin(clean,[0,1]).all() and np.isin(flips,[0,1]).all(),"Latent labels/flags invalid")
    audit.same(data["y"],np.bitwise_xor(clean.astype(np.int64),flips.astype(np.int64)),"Observed labels differ from clean/noise evidence")
    data["label_flip"]=flips.astype(bool)
    data["bindings"]={"training":audit.binding(train),"sealed_latent":audit.binding(latent)}
    return data

def reconstruct(orders,probabilities,refresh_losses,labels,flips,routes):
    orders=np.asarray(orders);p=np.asarray(probabilities,dtype=float)
    y=np.asarray(labels);flips=np.asarray(flips)
    audit.need(orders.ndim==2 and orders.dtype.kind in "iu","Integer replacement order matrix required")
    rounds,n=orders.shape
    audit.need(rounds>10 and p.shape==(rounds,n) and y.shape==flips.shape==(n,),"Exposure shape differs")
    audit.need(np.isfinite(p).all() and (p>0).all() and np.allclose(p.sum(1),1,rtol=0,atol=2e-14),"Actual law invalid")
    audit.need(np.all((orders>=0)&(orders<n)) and np.isin(y,[0,1]).all() and np.isin(flips,[0,1]).all(),"Invalid record/label identity")
    loss=np.asarray(refresh_losses,float)
    audit.need(loss.shape==(rounds-10,n) and np.isfinite(loss).all() and (loss>=0).all(),"Refresh loss shape/value differs")
    audit.need(set(routes)=={"hash","kmeans"} and all(np.asarray(v).shape==(n,) and np.isin(v,range(5)).all() for v in routes.values()),"Route inventory differs")
    flips=flips.astype(bool);rows=[];counts=[];exposure=np.zeros(n,dtype=np.int64)
    for r,indices in enumerate(orders):
        count=np.bincount(indices,minlength=n);counts.append(count);exposure+=count
        high=None if r<10 else loss[r-10]>5
        rows.append({"round":r+1,"draws":n,"unique_records":int(np.count_nonzero(count)),
            "repeat_visits_after_first":n-int(np.count_nonzero(count)),"maximum_record_multiplicity":int(count.max()),
            "distribution_effective_records":1/math.fsum(float(v)*float(v) for v in p[r]),
            "positive_draws":int(np.sum(y[indices])),"flipped_label_draws":int(np.sum(flips[indices])),
            "flipped_label_draw_fraction":float(np.mean(flips[indices])),
            "flipped_label_probability_mass":math.fsum(map(float,p[r,flips])),
            "high_loss_record_count":None if high is None else int(np.count_nonzero(high)),
            "high_loss_draws":None if high is None else int(np.sum(high[indices])),
            "high_loss_probability_mass":None if high is None else math.fsum(map(float,p[r,high])),
            "bank_draws":{kind:np.bincount(np.asarray(route)[indices],minlength=5).tolist() for kind,route in routes.items()}})
    total=rounds*n;noisy=int(exposure[flips].sum())
    result={"rounds":rows,"total_draws":total,"unique_records_over_horizon":int(np.count_nonzero(exposure)),
        "record_count":n,"flipped_training_record_count":int(flips.sum()),"flipped_training_record_fraction":float(flips.mean()),
        "flipped_label_draws":noisy,"flipped_label_draw_fraction":noisy/total,
        "noise_draw_fraction_minus_record_fraction":noisy/total-float(flips.mean()),
        "mean_post_warmup_effective_records":math.fsum(r["distribution_effective_records"] for r in rows[10:])/(rounds-10),
        "mean_unique_records_per_round":math.fsum(r["unique_records"] for r in rows)/rounds,
        "maximum_record_total_visits":int(exposure.max())}
    return result,np.asarray(counts),exposure

def verify_endpoint(folder,official_folder,training,ledger,official_row):
    folder=Path(folder);official_folder=Path(official_folder)
    orders=np.load(folder/"record_orders.npy",allow_pickle=False)
    laws=np.load(folder/"sampling_probabilities.npy",allow_pickle=False)
    losses=np.load(folder/"refresh_native_losses.npy",allow_pickle=False)
    audit.need(orders.shape==laws.shape==(200,4800) and len(ledger)==200,"Full priority horizon required")
    expected,counts,exposure=reconstruct(orders,laws,losses,training["y"],training["label_flip"],
        {k:training[k+"_route"] for k in ("hash","kmeans")})
    audit.same(counts,np.load(folder/"sampling_counts.npy",allow_pickle=False),"Retained counts differ from sampled record positions")
    audit.same(exposure,np.load(folder/"training_record_exposure.npy",allow_pickle=False),"Retained exposure differs")
    expected["data_evidence"]=training["bindings"]
    names=("sampling_counts.npy","sampling_probabilities.npy","refresh_native_losses.npy",
           "training_record_exposure.npy","population_identity.npz")
    expected["trace_evidence"]={name:audit.binding(folder/name) for name in names}
    for r,row in enumerate(expected["rounds"]):
        audit.need(ledger[r]["round"]==r+1 and ledger[r]["optimizer_updates"]==75*(r+1),"Learning ledger horizon differs")
        row["logged_sampler"]=ledger[r]["sampling"]
    metrics.compare(expected,official_row["priority"],"priority exposure",tolerance=1e-9)
    curve=[{name:row[name] for name in ("round","optimizer_updates","full_training","full_training_native","validation","validation_native")} for row in ledger]
    audit.need(official_row["learning_curve"]==curve,"Official learning curve differs from committed ledger")
    with np.load(official_folder/"training_priority_evidence.npz",allow_pickle=False) as z:
        fields={"training_record_ids":training["ids"],"observed_labels":training["y"],"label_flip":training["label_flip"],
            "record_exposure":exposure,"mean_actual_round_probability":laws.mean(axis=0),
            "hash_route":training["hash_route"],"kmeans_route":training["kmeans_route"]}
        audit.need(set(z.files)==set(fields),"Priority output array inventory differs")
        for name,value in fields.items():audit.same(z[name],value,"Official priority evidence differs "+name)
    return {"all_training_draws_replayed":960000,"all_round_exposure_records":200,
        "learning_curve_rounds_checked":200,"priority_arrays_checked":len(fields),
        "latent_training_binding":training["bindings"]["sealed_latent"],
        "post_release_only":True,"record_counts_reconstructed_from_positions":True}

def describe(values):
    values=list(map(float,values));n=len(values);mean=math.fsum(values)/n
    return {"n":n,"mean":mean,"sample_sd":math.sqrt(math.fsum((x-mean)**2 for x in values)/(n-1)) if n>1 else None,
        "minimum":min(values),"maximum":max(values),"median":float(np.median(values)),"values":values}

def check_summary(records,actual):
    index={(r["family"],r["population"],r["seed"],r["arm"]):r for r in records}
    audit.need(len(index)==len(records)==640,"Complete640 unique summary records required")
    summaries=actual["exposure_and_learning"];effects=actual["all_base_priority_effects_descriptive"]
    audit.need(len(summaries)==40 and {(r["family"],r["arm"]) for r in summaries}==
        {(f,a) for f in statistics.FAMILIES for a in statistics.ARMS},"Priority summary inventory differs")
    for summary in summaries:
        family,arm=summary["family"],summary["arm"]
        pops=sorted({r["population"] for r in records if r["family"]==family})
        audit.need(len(pops)==8,"Eight population exposure blocks required")
        blocks=[]
        for population in pops:
            pair=[index[family,population,s,arm] for s in statistics.SEEDS]
            curve=[]
            for round_number in (25,50,100,200):
                entries=[p["learning_curve"][round_number-1] for p in pair]
                curve.append({"round":round_number,"optimizer_updates":75*round_number,
                    "full_training":{k:math.fsum(r["full_training"][k] for r in entries)/2 for k in ("bce","macro_f1","accuracy")},
                    "validation":{k:math.fsum(r["validation"][k] for r in entries)/2 for k in ("bce","macro_f1","accuracy")},
                    "full_training_native_bce":math.fsum(r["full_training_native"]["native_bce"] for r in entries)/2,
                    "validation_native_bce":math.fsum(r["validation_native"]["native_bce"] for r in entries)/2})
            blocks.append({"population":population,"paired_seed_ids":list(statistics.SEEDS),
                "exposure":{k:math.fsum(r["priority"][k] for r in pair)/2 for k in EXPOSURE_FIELDS},
                "fixed_learning_milestones":curve})
        expected={"population_blocks":blocks,"population_mean_descriptions":{
            k:describe([b["exposure"][k] for b in blocks]) for k in EXPOSURE_FIELDS}}
        metrics.compare(expected,summary,"priority population summary",tolerance=1e-9)
    bases=("MultiK","MultiHash","TrigK","TrigHash","TrigG121")
    audit.need(len(effects)==20 and {(r["family"],r["base_model"]) for r in effects}==
        {(f,b) for f in statistics.FAMILIES for b in bases},"Descriptive priority-effect inventory differs")
    for effect in effects:
        family,base=effect["family"],effect["base_model"]
        pops=sorted({r["population"] for r in records if r["family"]==family});blocks=[]
        for population in pops:
            differences=[index[family,population,s,base+"_P"]["test"]["bce"]-index[family,population,s,base+"_U"]["test"]["bce"] for s in statistics.SEEDS]
            blocks.append({"population":population,"seed_ids":list(statistics.SEEDS),
                "paired_seed_differences":differences,"mean_difference":math.fsum(differences)/2})
        metrics.compare({"population_blocks":blocks,"description":describe([b["mean_difference"] for b in blocks])},effect,"descriptive priority effect")
