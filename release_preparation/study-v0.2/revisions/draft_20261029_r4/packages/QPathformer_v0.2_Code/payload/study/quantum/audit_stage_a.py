"""Independently verify every completed development endpoint; never open test data."""
import os
for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[name]="1"
import csv
import json
import numpy as np
import qstudy as s
from evaluate_confirmation import independently_predict, independently_measure, load_model


def main():
    destination=s.ROOT/"STAGE_A_ENDPOINT_AUDIT.json"
    if destination.exists():
        raise FileExistsError("Preserve the first endpoint audit")
    freeze=s.read_json(s.ROOT/"STAGE_A_FREEZE.json")
    validation=s.load_population("development","validation")
    train=s.load_population("development","train")
    rows=[]
    for seed in freeze["training_seeds"]:
        for method in freeze["methods"]:
            s.verify_freeze("A",seed,method)
            folder=s.ROOT/"stage_A"/f"seed_{seed}"/method
            result=s.read_json(folder/"result.json")
            status=s.read_json(folder/"status.json")
            if (result["status"]!="completed" or status["status"]!="completed" or result["engineering"]
                    or result["completed_rounds"]!=200 or result["optimizer_global_updates"]!=15000
                    or result["test_accessed"] or result["stage_freeze_sha256"]!=s.digest(s.ROOT/"STAGE_A_FREEZE.json")):
                raise ValueError("Development endpoint incomplete or changed")
            ledger=[json.loads(line) for line in (folder/"ledger.jsonl").read_text().splitlines()]
            if [r["round"] for r in ledger]!=list(range(1,201)):
                raise ValueError("Development ledger is incomplete")
            chosen=min(ledger,key=lambda r:(r["validation"]["bce"],r["round"]))
            if chosen["round"]!=result["selected_round"]:
                raise ValueError("Validation checkpoint selection mismatch")
            model,selected_round,selected_t=load_model(method,seed,folder/"selected_checkpoint.npz")
            _,last_round,last_t=load_model(method,seed,folder/"last_checkpoint.npz")
            if (selected_round!=chosen["round"] or selected_t!=75*selected_round or last_round!=200 or last_t!=15000
                    or s.digest(folder/"selected_checkpoint.npz")!=result["selected_checkpoint_sha256"]):
                raise ValueError("Checkpoint identity or update count mismatch")
            with np.load(folder/"record_orders.npz",allow_pickle=False) as archive:
                order=archive["orders"]
                if (order.shape!=(200,4800) or not np.array_equal(archive["record_ids"],train["ids"])
                        or not np.all(np.sort(order,axis=1)==np.arange(4800)[None,:])):
                    raise ValueError("Incomplete shuffled training exposure")
                rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
                if not all(np.array_equal(row,rng.permutation(4800)) for row in order):
                    raise ValueError("Training record pairing differs from registered RNG")
            if method=="untied_balanced":
                with np.load(folder/"expanded_record_orders.npz",allow_pickle=False) as archive:
                    order=archive["orders"]
                    if (order.shape!=(200,4800,4) or np.any(order<0) or np.any(order>=4800)
                            or not np.array_equal(archive["record_ids"],train["ids"])):
                        raise ValueError("Balanced exposure shape mismatch")
                    for depth in range(1,5):
                        if not np.all(train["depth"][order[:,:,depth-1]]==depth):
                            raise ValueError("Balanced exposure included an unassigned record")
            with (folder/"validation_predictions.csv").open(newline="") as handle:
                saved=list(csv.DictReader(handle))
            if [int(r["record_id"]) for r in saved]!=validation["ids"].tolist():
                raise ValueError("Saved validation record identity mismatch")
            if ([int(r["label"]) for r in saved]!=validation["y"].tolist()
                    or [int(r["original_depth"]) for r in saved]!=validation["depth"].tolist()):
                raise ValueError("Saved validation labels or original depths changed")
            p=independently_predict(model,validation)
            probability_error=float(np.max(np.abs(p-np.asarray([float(r["probability"]) for r in saved]))))
            metric=independently_measure(validation["y"],p)
            metric_error=max(abs(metric[k]-record[k]) for record in (result["selected_validation"],chosen["validation"])
                             for k in ("bce","macro_f1","accuracy"))
            if probability_error>1e-10 or metric_error>1e-10:
                raise ValueError("Independent validation replay disagrees")
            rows.append({"seed":seed,"method":method,"status":"pass","selected_round":selected_round,
                         "independent_validation":metric,"probability_max_error":probability_error,
                         "metric_max_error":metric_error,"checkpoint_sha256":s.digest(folder/"selected_checkpoint.npz"),
                         "result_sha256":s.digest(folder/"result.json"),"ledger_sha256":s.digest(folder/"ledger.jsonl")})
    s.write_json(destination,{"status":"pass","created_utc":s.now(),"audit_source_sha256":s.digest(__file__),
                 "independent_evaluator_sha256":s.digest(s.ROOT/"evaluate_confirmation.py"),
                 "stage_a_freeze_sha256":s.digest(s.ROOT/"STAGE_A_FREEZE.json"),"test_file_read":False,
                 "count":len(rows),"endpoints":rows})
    print("All development endpoints independently verified:",len(rows))


if __name__=="__main__":
    main()
