"""Select one mechanism using complete Stage A validation evidence only."""
import argparse
import statistics
import qstudy as study


def select():
    freeze=study.read_json(study.ROOT/"STAGE_A_FREEZE.json")
    if freeze["training_seeds"] != [301,302,303] or tuple(freeze["methods"]) != study.STAGE_A_METHODS:
        raise ValueError("Unexpected Stage A population")
    rows=[]
    for seed in freeze["training_seeds"]:
        for method in freeze["methods"]:
            study.verify_freeze("A",seed,method)
            path=study.ROOT/"stage_A"/f"seed_{seed}"/method/"result.json"
            result=study.read_json(path)
            if (result["status"] != "completed" or result["engineering"] or result["completed_rounds"] != 200
                    or result["optimizer_global_updates"] != 15000 or result["test_accessed"]):
                raise RuntimeError("Incomplete or ineligible Stage A result")
            if result["stage_freeze_sha256"] != study.digest(study.ROOT/"STAGE_A_FREEZE.json"):
                raise RuntimeError("Stage A result freeze mismatch")
            rows.append({"method":method,"seed":seed,"validation_bce":result["selected_validation"]["bce"],
                         "training_circuit_examples":result["work"]["training_circuit_examples"],
                         "parameter_count":result["parameter_count"],"result_sha256":study.digest(path)})
    summary={}
    for method in study.STAGE_A_METHODS:
        chosen=[r for r in rows if r["method"]==method]
        summary[method]={"mean_validation_bce":statistics.mean(r["validation_bce"] for r in chosen),
                         "sample_sd_validation_bce":statistics.stdev(r["validation_bce"] for r in chosen),
                         "mean_training_circuit_examples":statistics.mean(r["training_circuit_examples"] for r in chosen),
                         "parameters":chosen[0]["parameter_count"]}
    best=min(summary[m]["mean_validation_bce"] for m in study.CANDIDATES)
    tied=[m for m in study.CANDIDATES if summary[m]["mean_validation_bce"] <= best+.002]
    selected=min(tied,key=lambda m:(summary[m]["mean_training_circuit_examples"],summary[m]["parameters"],m))
    improvement=summary["scheduled"]["mean_validation_bce"]-summary[selected]["mean_validation_bce"]
    methods=(["scheduled","fixed4","min_depth2","mlp129","mlp17","min_depth2_mlp129"]
             if selected=="min_depth2" else
             ["scheduled","fixed4","untied_assigned","untied_balanced","untied_all_records","mlp129","mlp17","mlp41"])
    result={"created_utc":study.now(),"classification":"DEVELOPMENT SELECTION - VALIDATION ONLY",
            "stage_a_freeze_sha256":study.digest(study.ROOT/"STAGE_A_FREEZE.json"),
            "selector_sha256":study.digest(__file__),"selected_candidate":selected,
            "minimum_candidate_mean_bce":best,"within_0_002_candidates":tied,
            "selected_minus_original_validation_bce":-improvement,
            "development_promising_flag":improvement >= .01,
            "confirmation_purpose":"promising candidate confirmation" if improvement >= .01 else "diagnostic confirmation; no implied improvement",
            "gate":"Mean validation BCE improvement at least 0.01 labels promising; confirmation proceeds regardless of this flag, preserving negative outcomes",
            "proposed_stage_b_methods":methods,"stage_b_training_seeds":[401,402,403,404,405],
            "method_summaries":summary,"all_27_results":rows,"test_accessed":False,
            "stage_b_requires_separate_root_review":True}
    path=study.ROOT/"STAGE_A_SELECTION.json"
    if path.exists():
        raise FileExistsError("Preserve the first frozen selection; no silent reselection")
    study.write_json(path,result)
    print(result["selected_candidate"],result["confirmation_purpose"])


if __name__=="__main__":
    select()
