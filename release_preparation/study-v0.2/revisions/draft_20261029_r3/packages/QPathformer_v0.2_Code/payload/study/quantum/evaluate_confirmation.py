"""Independent endpoint audit and one-time, root-released confirmation reporting.

--prepare audits all validation-selected checkpoints without opening any test
file. --evaluate requires a root-issued EVALUATION_RELEASE.json bound to the
endpoint lock and this source. It never trains or reselects a model.
"""
import os
for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[name]="1"
import argparse
import csv
import math
from pathlib import Path
import statistics
import traceback
import numpy as np
import qstudy as s

ANALYSIS_PROTOCOL_SHA256="9b409934d07e8eb7a6380a02fe93780cab3323401d595c846da1b2ce7ba1e414"


def verify_analysis_protocol():
    path=s.ROOT.parent/"governance/ANALYSIS_PROTOCOL.json"
    if s.digest(path)!=ANALYSIS_PROTOCOL_SHA256:
        raise ValueError("Registered root analysis protocol identity changed")


def independently_predict(model,population):
    result=[]
    for x,original_depth in zip(population["x"],population["depth"]):
        d=int(model.effective_depth(np.asarray([original_depth]))[0])
        if model.is_mlp:
            h=model.hidden
            p=model.parameters
            inputs=[float(x[0]),float(x[1])]+[float(i+1==d) for i in range(4)]
            hidden=[max(0.,math.fsum(inputs[k]*float(p[k*h+j]) for k in range(6))+float(p[6*h+j])) for j in range(h)]
            logit=math.fsum(hidden[j]*float(p[7*h+j]) for j in range(h))+float(p[-1])
            e=math.exp(-abs(logit))
            probability=1/(1+e) if logit>=0 else e/(1+e)
        else:
            unitary=s.reference.unitary(x,model.bank(d),d)
            probability=float(sum(abs(unitary[k,0])**2 for k in (2,3)))
        result.append(probability)
    return np.asarray(result)


def independently_measure(y,p):
    pred=[int(v>=.5) for v in p]
    confusion=[[sum(int(a)==i and b==j for a,b in zip(y,pred)) for j in (0,1)] for i in (0,1)]
    scores=[]
    for label in (0,1):
        tp=confusion[label][label]
        denominator=2*tp+confusion[1-label][label]+confusion[label][1-label]
        scores.append(2*tp/denominator if denominator else 0.)
    losses=[]
    for label,probability in zip(y,p):
        q=min(1-1e-7,max(1e-7,float(probability)))
        losses.append(-math.log(q) if label else -math.log1p(-q))
    return {"bce":math.fsum(losses)/len(y),"macro_f1":sum(scores)/2,
            "accuracy":(confusion[0][0]+confusion[1][1])/len(y),"confusion":confusion,"n":len(y)}


def load_model(method,seed,path):
    model=s.Model(method,seed)
    with np.load(path,allow_pickle=False) as checkpoint:
        values=checkpoint["parameters"]
        if values.shape != model.parameters.shape or not np.isfinite(values).all():
            raise ValueError("Invalid checkpoint parameters")
        model.parameters[:]=values
        return model,int(checkpoint["round"]),int(checkpoint["adam_t"])


def endpoints():
    verify_analysis_protocol()
    freeze=s.read_json(s.ROOT/"STAGE_B_FREEZE.json")
    if freeze["training_seeds"] != [401,402,403,404,405]:
        raise ValueError("All five registered confirmation seeds are required")
    selection=s.read_json(s.ROOT/"STAGE_A_SELECTION.json")
    if (freeze["methods"] != selection["proposed_stage_b_methods"]
            or freeze.get("stage_a_selection_sha256") != s.digest(s.ROOT/"STAGE_A_SELECTION.json")):
        raise ValueError("Stage B identity differs from frozen development selection")
    if freeze.get("evaluation_source_sha256") != s.digest(__file__):
        raise ValueError("Evaluator must be registered before outcomes")
    result=[]
    for seed in freeze["training_seeds"]:
        for method in freeze["methods"]:
            s.verify_freeze("B",seed,method)
            folder=s.ROOT/"stage_B"/f"seed_{seed}"/method
            r=s.read_json(folder/"result.json")
            status=s.read_json(folder/"status.json")
            if r["status"]!="completed" or status["status"]!="completed" or r["engineering"]:
                raise ValueError("Every endpoint must complete before release")
            if (r["completed_rounds"]!=200 or r["optimizer_global_updates"]!=15000 or r["test_accessed"]
                    or r["stage_freeze_sha256"]!=s.digest(s.ROOT/"STAGE_B_FREEZE.json")):
                raise ValueError("Endpoint horizon or registration mismatch")
            checkpoint=folder/"selected_checkpoint.npz"
            if s.digest(checkpoint)!=r["selected_checkpoint_sha256"]:
                raise ValueError("Selected checkpoint identity changed")
            result.append((seed,method,folder,r))
    return freeze,selection,result


def prepare():
    output=s.ROOT/"CONFIRMATION_ENDPOINT_LOCK.json"
    if output.exists():
        raise FileExistsError("Endpoint lock already exists")
    freeze,selection,items=endpoints()
    validation=s.load_population("confirmation","validation")
    train=s.load_population("confirmation","train")
    audits=[]
    for seed,method,folder,r in items:
        import json
        rows=[json.loads(line) for line in (folder/"ledger.jsonl").read_text().splitlines()]
        if [row["round"] for row in rows] != list(range(1,201)):
            raise ValueError("Missing or duplicate training rounds")
        chosen=min(rows,key=lambda row:(row["validation"]["bce"],row["round"]))
        if chosen["round"]!=r["selected_round"]:
            raise ValueError("Checkpoint not chosen by frozen validation rule")
        model,round_number,adam_t=load_model(method,seed,folder/"selected_checkpoint.npz")
        if round_number!=r["selected_round"] or adam_t!=75*round_number:
            raise ValueError("Selected checkpoint step mismatch")
        _,last_round,last_t=load_model(method,seed,folder/"last_checkpoint.npz")
        if last_round!=200 or last_t!=15000:
            raise ValueError("Full training horizon missing")
        with np.load(folder/"record_orders.npz",allow_pickle=False) as archive:
            orders=archive["orders"]
            if orders.shape!=(200,4800) or not np.array_equal(archive["record_ids"],train["ids"]):
                raise ValueError("Record order identity mismatch")
            if not np.all(np.sort(orders,axis=1)==np.arange(4800)[None,:]):
                raise ValueError("Epoch is not a complete permutation")
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
            if not all(np.array_equal(order,rng.permutation(4800)) for order in orders):
                raise ValueError("Record order differs from registered paired RNG")
        if method=="untied_balanced":
            with np.load(folder/"expanded_record_orders.npz",allow_pickle=False) as archive:
                expanded=archive["orders"]
                if (expanded.shape!=(200,4800,4) or np.any(expanded<0) or np.any(expanded>=4800)
                        or not np.array_equal(archive["record_ids"],train["ids"])):
                    raise ValueError("Wrong repeated exposure shape")
                for d in range(1,5):
                    if not np.all(train["depth"][expanded[:,:,d-1]]==d):
                        raise ValueError("Balanced bank accessed an unassigned row")
        saved=list(csv.DictReader((folder/"validation_predictions.csv").open(newline="")))
        if [int(row["record_id"]) for row in saved] != validation["ids"].tolist():
            raise ValueError("Validation records changed")
        if ([int(row["label"]) for row in saved]!=validation["y"].tolist()
                or [int(row["original_depth"]) for row in saved]!=validation["depth"].tolist()):
            raise ValueError("Validation label or original depth provenance changed")
        saved_p=np.asarray([float(row["probability"]) for row in saved])
        independent=independently_predict(model,validation)
        max_error=float(np.max(np.abs(saved_p-independent)))
        measured=independently_measure(validation["y"],independent)
        metric_error=max(abs(measured[k]-record[k]) for record in (r["selected_validation"],chosen["validation"])
                         for k in ("bce","macro_f1","accuracy"))
        if max_error>1e-10 or metric_error>1e-10:
            raise ValueError("Independent validation replay failed")
        audits.append({"seed":seed,"method":method,"selected_round":round_number,
                       "checkpoint_sha256":s.digest(folder/"selected_checkpoint.npz"),
                       "result_sha256":s.digest(folder/"result.json"),"ledger_sha256":s.digest(folder/"ledger.jsonl"),
                       "max_validation_probability_error":max_error,"max_validation_metric_error":metric_error,
                       "status":"pass"})
    lock={"status":"pass","created_utc":s.now(),"test_file_read":False,"endpoints":audits,
          "stage_b_freeze_sha256":s.digest(s.ROOT/"STAGE_B_FREEZE.json"),
          "stage_a_selection_sha256":s.digest(s.ROOT/"STAGE_A_SELECTION.json"),
          "data_seal_sha256":s.digest(s.ROOT/"data/DATA_SEAL.json"),
          "root_analysis_protocol_sha256":ANALYSIS_PROTOCOL_SHA256,
          "evaluator_sha256":s.digest(__file__),"selected_candidate":selection["selected_candidate"],
          "required_next_step":"Independent root review and a one-time EVALUATION_RELEASE.json"}
    s.write_json(output,lock)
    print("Independent validation endpoint audit passed:",len(audits))


def describe(values):
    mean,sd=statistics.mean(values),statistics.stdev(values)
    half=2.7764451051977987*sd/math.sqrt(5)
    return {"n_training_seeds":5,"mean":mean,"sample_sd":sd,"descriptive_t95_interval":[mean-half,mean+half],"values_seed_401_to_405":values}


def evaluate():
    freeze,selection,items=endpoints()
    release=s.read_json(s.ROOT/"EVALUATION_RELEASE.json")
    lock_path=s.ROOT/"CONFIRMATION_ENDPOINT_LOCK.json"
    lock=s.read_json(lock_path)
    required={"review_status":"approved_by_root","endpoint_lock_sha256":s.digest(lock_path),
              "stage_b_freeze_sha256":s.digest(s.ROOT/"STAGE_B_FREEZE.json"),"evaluator_sha256":s.digest(__file__)}
    if any(release.get(k)!=v for k,v in required.items()) or not release.get("release_id"):
        raise PermissionError("Separate root-issued one-time evaluation release is required")
    lock_identity={"status":"pass","stage_b_freeze_sha256":s.digest(s.ROOT/"STAGE_B_FREEZE.json"),
                   "stage_a_selection_sha256":s.digest(s.ROOT/"STAGE_A_SELECTION.json"),
                   "data_seal_sha256":s.digest(s.ROOT/"data/DATA_SEAL.json"),
                   "evaluator_sha256":s.digest(__file__),"root_analysis_protocol_sha256":ANALYSIS_PROTOCOL_SHA256,
                   "selected_candidate":selection["selected_candidate"],"test_file_read":False}
    if any(lock.get(k)!=v for k,v in lock_identity.items()):
        raise ValueError("Endpoint lock status or registered identity mismatch")
    if len(lock["endpoints"])!=len(items) or len({(a["seed"],a["method"]) for a in lock["endpoints"]})!=len(items):
        raise ValueError("Endpoint lock contains missing or duplicate entries")
    for seed,method,folder,r in items:
        audit=next(a for a in lock["endpoints"] if a["seed"]==seed and a["method"]==method)
        if (audit["status"]!="pass" or audit["checkpoint_sha256"]!=s.digest(folder/"selected_checkpoint.npz")
                or audit["result_sha256"]!=s.digest(folder/"result.json") or audit["ledger_sha256"]!=s.digest(folder/"ledger.jsonl")):
            raise ValueError("Locked endpoint changed after review")
    output=s.ROOT/"confirmation_evaluation"
    output.mkdir(exist_ok=False)
    s.write_json(output/"TEST_ACCESS_EVENT.json",{"utc":s.now(),"release_id":release["release_id"],
                  "release_sha256":s.digest(s.ROOT/"EVALUATION_RELEASE.json"),"endpoint_lock_sha256":s.digest(lock_path),
                  "event":"Approved test access begins; no test outcome computed before this event"})
    try:
        seal=s.read_json(s.ROOT/"data/DATA_SEAL.json")
        path=s.ROOT/"data/confirmation_SEALED_test.npz"
        if s.digest(path)!=seal["files"][path.name]["sha256"]:
            raise ValueError("Sealed test bytes changed")
        with np.load(path,allow_pickle=False) as archive:
            test={key:archive[key] for key in archive.files}
        results=[]
        predictions={}
        shot_rows=[]
        for seed,method,folder,run in items:
            model,_,_=load_model(method,seed,folder/"selected_checkpoint.npz")
            actual=model.predict(test["x"],test["depth"])
            independent=independently_predict(model,test)
            error=float(np.max(np.abs(actual-independent)))
            if error>1e-10:
                raise ValueError("Independent final probability replay failed")
            metric=independently_measure(test["y"],actual)
            metric2=s.metrics(test["y"],actual)
            if max(abs(metric[k]-metric2[k]) for k in ("bce","macro_f1","accuracy"))>1e-12:
                raise ValueError("Independent final metric check failed")
            s.save_predictions(output/f"seed_{seed}_{method}_predictions.csv",test,actual)
            predictions[(seed,method)]=actual
            results.append({"seed":seed,"method":method,"metrics":metric,"probability_replay_max_error":error,
                            "selected_checkpoint_sha256":run["selected_checkpoint_sha256"],"parameter_count":run["parameter_count"],
                            "training_seconds":run["training_seconds"],"training_work":run["work"]})
            if method==selection["selected_candidate"]:
                arrays={"record_ids":test["ids"]}
                for budget in (1024,4096):
                    for shot_seed in (701,702,703,704,705):
                        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,shot_seed,budget])))
                        counts=rng.binomial(budget,actual)
                        arrays[f"shots_{budget}_seed_{shot_seed}"]=counts
                        shot_rows.append({"training_seed":seed,"shot_seed":shot_seed,"shots_per_record":budget,
                                          "metrics":independently_measure(test["y"],counts/budget)})
                np.savez(output/f"seed_{seed}_selected_probability_level_shots.npz",**arrays)
        aggregates={}
        for method in freeze["methods"]:
            aggregates[method]={key:describe([next(r for r in results if r["seed"]==seed and r["method"]==method)["metrics"][key]
                                             for seed in freeze["training_seeds"]]) for key in ("bce","macro_f1","accuracy")}
        candidate=selection["selected_candidate"]
        comparisons=[("selected_minus_scheduled",candidate,"scheduled"),("selected_minus_fixed4",candidate,"fixed4"),
                     ("selected_minus_mlp129",candidate,"mlp129")]
        if "untied_balanced" in freeze["methods"]:
            comparisons += [("balanced_minus_assigned","untied_balanced","untied_assigned"),
                            ("all_records_minus_balanced","untied_all_records","untied_balanced")]
        paired={}
        for name,a,b in comparisons:
            paired[name]={key:describe([aggregates[a][key]["values_seed_401_to_405"][i]-aggregates[b][key]["values_seed_401_to_405"][i]
                                       for i in range(5)]) for key in ("bce","macro_f1","accuracy")}
        # Registered conditional record bootstrap, common resample across seeds.
        y=test["y"]
        seed_losses=[]
        for seed in freeze["training_seeds"]:
            values=[]
            for method in (candidate,"scheduled"):
                q=np.clip(predictions[(seed,method)],1e-7,1-1e-7)
                values.append(-(y*np.log(q)+(1-y)*np.log1p(-q)))
            seed_losses.append(values[0]-values[1])
        record_difference=np.mean(seed_losses,axis=0)
        rng=np.random.Generator(np.random.PCG64(88003))
        cp=np.asarray([predictions[(seed,candidate)]>=.5 for seed in freeze["training_seeds"]])
        bp=np.asarray([predictions[(seed,"scheduled")]>=.5 for seed in freeze["training_seeds"]])
        bootstrap,bootstrap_f1,bootstrap_accuracy=[],[],[]
        def binary_seed_metrics(pred,label):
            scores=[]
            for value in (0,1):
                tp=np.sum((pred==value)&(label[None,:]==value),axis=1)
                fp=np.sum((pred==value)&(label[None,:]!=value),axis=1)
                fn=np.sum((pred!=value)&(label[None,:]==value),axis=1)
                den=2*tp+fp+fn
                scores.append(np.divide(2*tp,den,out=np.zeros(5),where=den!=0))
            return float(np.mean(scores)),float(np.mean(pred==label[None,:]))
        for _ in range(2000):
            ids=rng.integers(0,len(y),len(y))
            bootstrap.append(float(np.mean(record_difference[ids])))
            cf,ca=binary_seed_metrics(cp[:,ids],y[ids])
            bf,ba=binary_seed_metrics(bp[:,ids],y[ids])
            bootstrap_f1.append(cf-bf)
            bootstrap_accuracy.append(ca-ba)
        bootstrap=np.asarray(bootstrap)
        np.savez(output/"conditional_primary_record_bootstrap.npz",bce=bootstrap,
                 macro_f1=np.asarray(bootstrap_f1),accuracy=np.asarray(bootstrap_accuracy),record_ids=test["ids"])
        nested={}
        for budget in (1024,4096):
            nested[str(budget)]={key:describe([statistics.mean(r["metrics"][key] for r in shot_rows if r["training_seed"]==seed and r["shots_per_record"]==budget)
                                               for seed in freeze["training_seeds"]]) for key in ("bce","macro_f1","accuracy")}
        summary={"status":"complete","classification":"INTERNAL - NOT FOR PUBLICATION","created_utc":s.now(),
                 "selected_candidate":candidate,"training_seeds":freeze["training_seeds"],"methods":freeze["methods"],
                 "test_records":len(y),"per_seed":results,"aggregate":aggregates,"paired_contrasts":paired,
                 "primary_conditional_record_bootstrap":{"seed":88003,"replicates":2000,
                     "percentile95_interval":np.quantile(bootstrap,[.025,.975]).tolist(),
                     "secondary_macro_f1_interval":np.quantile(bootstrap_f1,[.025,.975]).tolist(),
                     "secondary_accuracy_interval":np.quantile(bootstrap_accuracy,[.025,.975]).tolist(),
                     "scope":"Conditions on frozen trained checkpoints; does not add training-seed or selection uncertainty"},
                 "practical_BCE_reduction_0_01_met":paired["selected_minus_scheduled"]["bce"]["mean"]<=-.01,
                 "nested_probability_level_readouts":nested,"raw_nested_readouts":shot_rows,
                 "readout_interpretation":"Ideal binomial counts from frozen probabilities, not executed Aer fixture circuits, not physical shots; five nested repeats are not independent training seeds",
                 "represented_bernoulli_trials":len(y)*5*5*(1024+4096),"physical_shots":0,"hardware_jobs":0,
                 "release_sha256":s.digest(s.ROOT/"EVALUATION_RELEASE.json"),"endpoint_lock_sha256":s.digest(lock_path),
                 "evaluator_sha256":s.digest(__file__),"data_seal_sha256":s.digest(s.ROOT/"data/DATA_SEAL.json"),
                 "root_analysis_protocol_sha256":ANALYSIS_PROTOCOL_SHA256,
                 "limitations":["One fixed fresh synthetic population; five paired training seeds.","Secondary contrasts are descriptive, not multiplicity-adjusted.",
                                "Capacity, record exposure, data diversity and compute controls bound but do not eliminate all mechanism confounding.",
                                "Random allocation classes do not measure semantic priority; no quantum advantage claim."]}
        s.write_json(output/"summary.json",summary)
        s.write_json(output/"manifest.json",{"files":{str(p.relative_to(output)):s.digest(p) for p in sorted(output.iterdir()) if p.is_file()}})
        print("Completed one-time confirmation reporting:",len(results),"endpoints")
    except BaseException as exc:
        s.write_json(output/"failure.json",{"utc":s.now(),"type":type(exc).__name__,"message":str(exc),"traceback":traceback.format_exc()})
        raise


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare",action="store_true")
    group.add_argument("--evaluate",action="store_true")
    args=parser.parse_args()
    prepare() if args.prepare else evaluate()
