"""Released-only independent prediction/statistics replay. No producer imports.

The caller must wrap this entire process in the external ETEL auxiliary lease.
--freeze writes source identities only and cannot read heldout arrays/outcomes.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import bisect
import hashlib
import json
import math
import struct
import time
import traceback
import numpy as np
import audit_endpoints_v07 as audit
import reference_v07 as reference
import replay_metrics_v07 as metrics
import statistics_v07 as statistics

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1];Q=ROOT/"quantum"
SOURCES=("replay_evaluation_v07.py","replay_metrics_v07.py","statistics_v07.py",
         "reference_v07.py","audit_endpoints_v07.py","AUDIT_NUMERICAL_PROTOCOL.json",
         "test_statistics_v07.py","test_replay_metrics_v07.py","test_independent_audit.py",
         "test_replay_evaluation_v07.py","run_replay_leased.py")


def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as f:json.dump(value,f,indent=2,allow_nan=False)


def freeze(output):
    write_new(output,{"schema":"qpath-v07-independent-replay-source-freeze-1",
                      "status":"SOURCE_PREPARED_NOT_TEST_ACCESS_AUTHORIZATION",
                      "created_utc":datetime.now(timezone.utc).isoformat(),
                      "sources":{name:audit.binding(HERE/name) for name in SOURCES},
                      "protocols":{name:audit.binding(ROOT/"governance"/name) for name in
                                   ("STUDY_PLAN.json","RUN_MATRIX.json","ANALYSIS_PROTOCOL.json")}})


def validate_release_flags(release):
    audit.need(release.get("schema")=="qpath-v07-test-release-1" and release.get("review_status")=="approved_by_root",
               "Explicit root test release required")
    audit.need(release.get("stage")=="B" and release.get("test_access_authorized") is True and
               release.get("all_confirmation_endpoints_independently_audited") is True,
               "All confirmation endpoints must be released")
    audit.need("independent_replay_freeze" in release,"Root must bind separate independent replay sources")


def verify_release(release_path):
    """Complete all gate checks before any sealed NPZ or test metric is opened."""
    audit.need(Path(release_path).resolve().is_relative_to(ROOT.resolve()),"Root release must be inside study")
    release=audit.read(release_path);validate_release_flags(release)
    for key in ("analysis_protocol","study_plan","run_matrix","data_seal","runtime_environment",
                "evaluator_freeze","author_audit","independent_audit","independent_replay_freeze"):
        audit.verify_binding(release[key])
    paths={"analysis_protocol":ROOT/"governance/ANALYSIS_PROTOCOL.json",
           "study_plan":ROOT/"governance/STUDY_PLAN.json","run_matrix":ROOT/"governance/RUN_MATRIX.json",
           "data_seal":Q/"data/DATA_SEAL.json"}
    for key,path in paths.items():audit.need(Path(release[key]["path"]).resolve()==path.resolve(),"Wrong active study authority")
    evaluator=audit.read(release["evaluator_freeze"]["path"])
    audit.need(evaluator["schema"]=="qpath-v07-evaluator-source-freeze-1" and evaluator["test_access_authorized"] is False,"Official source freeze differs")
    for name,digest in evaluator["sources"].items():
        path=(ROOT/name).resolve();audit.need(path.is_relative_to(ROOT.resolve()) and audit.sha(path)==digest,"Official source freeze drift")
    for key in ("analysis_protocol","study_plan","run_matrix"):
        audit.need(evaluator[key]==release[key],"Official source freeze protocol binding differs")
    frozen=audit.read(release["independent_replay_freeze"]["path"])
    audit.need(frozen["schema"]=="qpath-v07-independent-replay-source-freeze-1" and set(frozen["sources"])==set(SOURCES),"Independent source inventory differs")
    for name,item in frozen["sources"].items():
        audit.need(audit.verify_binding(item)==(HERE/name).resolve(),"Wrong independent source path")
    for name,item in frozen["protocols"].items():
        audit.need(audit.verify_binding(item)==(ROOT/"governance"/name).resolve(),"Independent protocol binding differs")
    matrix=audit.read(paths["run_matrix"]);jobs=[j for j in matrix["runs"] if j["stage"]=="B"]
    audit.need(len(jobs)==512 and release["run_ids"]==[j["run_id"] for j in jobs],"Root release must enumerate exact 512 B jobs")
    independent=audit.read(release["independent_audit"]["path"]);author=audit.read(release["author_audit"]["path"])
    audit.need(release["author_audit"]["sha256"]!=release["independent_audit"]["sha256"],"Separate author and independent audit required")
    expected={j["run_id"] for j in jobs};maps=[]
    for receipt in (author,independent):
        audit.need(receipt["status"]=="PASS" and receipt["stage"]=="B" and receipt["verified_endpoints"]==512,"Incomplete B audit")
        items=receipt["endpoints"];audit.need(len(items)==512 and {e["job_id"] for e in items}==expected,"Audit exact identities differ")
        maps.append({item["job_id"]:item["commit"] for item in items})
    audit.need(maps[0]==maps[1],"Audits must bind identical attempts")
    for job in jobs:
        commit_path=audit.verify_binding(maps[0][job["run_id"]])
        audit.need(commit_path.is_relative_to((ROOT/"execution/attempts").resolve()),"Endpoint outside registered attempts")
        commit,commit_hash=audit.check_commit(commit_path.parent)
        audit.need(commit_hash==maps[0][job["run_id"]]["sha256"] and commit["job_id"]==job["run_id"] and
                   commit["stage"]=="B" and commit["completed_rounds"]==200 and commit["optimizer_global_updates"]==15000,
                   "Released endpoint incomplete or wrong")
        audit.need(commit["data_seal_sha256"]==release["data_seal"]["sha256"] and
                   commit["matrix_sha256"]==release["run_matrix"]["sha256"] and
                   commit["protocol_sha256"]==release["study_plan"]["sha256"],"Endpoint release bindings differ")
        request=audit.read(commit_path.parent.parent/"REQUEST.json")
        audit.need(request["job"]==job,"Released attempt recipe differs")
        for source,digest in commit["source_hashes"].items():audit.need(audit.sha(Q/source)==digest,"Frozen scientific source changed")
    snapshot=audit.ledger_snapshot()
    audit.need(all(r["status"] not in {"running","launch_pending"} for r in snapshot["all_attempts"]),"Live fits prohibit replay")
    current={r["job_id"]:r for r in snapshot["current"] if r["phase"]=="B"}
    audit.need(set(current)==expected and all(current[k]["status"]=="succeeded" and current[k]["commit_sha"]==maps[0][k]["sha256"] for k in expected),"Current B ledger differs from audited attempts")
    return release,jobs,maps[0],matrix


def routes_and_margin(x,policy):
    values=np.asarray(x,float);centers=np.asarray(policy["centroids"],float)
    audit.need(values.ndim==2 and values.shape[1]==2 and centers.shape==(5,2),"Independent router input shape")
    difference=values[:,None,:]-centers[None,:,:]
    distance=difference[:,:,0]*difference[:,:,0]+difference[:,:,1]*difference[:,:,1]
    geometric=np.argmin(distance,axis=1).astype(np.int64)
    hashes=[]
    prefix=b"QPATH-V07-HASH5\x00"+policy["hash_salt"].encode("ascii")+b"\x00"
    for a,b in values:
        encoded=struct.pack("<dd",0. if a==0 else float(a),0. if b==0 else float(b))
        digest=hashlib.sha256(prefix+encoded).hexdigest()
        hashes.append(bisect.bisect_left(policy["hash_cutpoints_hex"],digest))
    ordered=np.sort(distance,axis=1);margin=ordered[:,1]-ordered[:,0]
    cutpoints=np.asarray(policy["margin_bins"]["unique_edges"],float)[1:-1]
    bins=np.array([sum(value>=edge for edge in cutpoints) for value in margin],dtype=np.int64)
    return {"kmeans_route":geometric,"hash_route":np.asarray(hashes,dtype=np.int64),"margin_bin":bins}


def verify_output_commit(folder,release_path):
    path=folder/"EVALUATION_COMMIT.json";commit=audit.read(path)
    audit.need(commit.get("schema")=="qpath-v07-evaluation-commit-1" and commit["status"]=="completed" and commit["count"]==512,"Official evaluation incomplete")
    audit.need(commit["release"]==audit.binding(release_path),"Official evaluation bound another release")
    audit.need(not (folder/"EVALUATION_FAILURE.json").exists(),"Failed official evaluation cannot be replayed as complete")
    jobs=[j for j in audit.read(ROOT/"governance/RUN_MATRIX.json")["runs"] if j["stage"]=="B"]
    required={"EVALUATION_START.json","summary.json","endpoint_index.json","primary_analysis.json",
              "descriptive_summary.json","diagnostic_summary.json"}
    for job in jobs:
        required.update(f"endpoints/{job['run_id']}/{name}" for name in
                        ("metrics.json","validation_predictions.npz","test_predictions.npz"))
    audit.need(required.issubset(commit["files"]),"Official evaluation lacks required records")
    actual={p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p!=path}
    audit.need(actual==set(commit["files"]),"Official evaluation inventory differs")
    for name,info in commit["files"].items():
        p=(folder/name).resolve();audit.need(p.is_relative_to(folder.resolve()),"Unsafe official output name")
        audit.need(p.stat().st_size==info["bytes"] and audit.sha(p)==info["sha256"],"Official evaluation payload changed")
    summary=audit.read(folder/"summary.json")
    audit.need(summary["status"]=="PASS" and summary["evaluated_endpoints"]==512 and summary["release"]==commit["release"],"Official summary incomplete or differently bound")
    index=audit.read(folder/"endpoint_index.json")
    audit.need([r["job_id"] for r in index]==[j["run_id"] for j in jobs],"Official index differs from full matrix order")
    for row in index:
        audit.need(audit.verify_binding(row["metrics"])==(folder/"endpoints"/row["job_id"]/"metrics.json").resolve(),"Official index metric binding differs")
    return audit.binding(path)


def compare_primary(expected,actual):
    audit.need(actual["family_size"]==20 and actual["alpha_family"]==.05 and len(actual["contrasts"])==20,"Primary family differs")
    for reference,official in zip(expected,actual["contrasts"]):
        checks={"family":reference["family"],"first":reference["first"],"second":reference["second"],
                "n_independent_populations":8,"paired_seeds_per_population":2,"degrees_of_freedom":7,
                "nominal_confidence":.9975,"mean_difference":reference["mean_difference"],
                "population_difference_sd":reference["sample_sd"],"standard_error":reference["standard_error"],
                "t_critical":reference["critical_t"],"interval":[reference["lower"],reference["upper"]],
                "supports_first_direction":reference["direction_supported_first"],
                "supports_first_practical_reference":reference["exceeds_practical_reference_first"],
                "supports_second_direction":reference["direction_supported_second"],
                "supports_second_practical_reference":reference["exceeds_practical_reference_second"],
                "crosses_zero_inconclusive_not_equivalence":reference["crosses_zero"]}
        metrics.compare(checks,official,"primary",tolerance=1e-10)
        audit.need(len(official["population_blocks"])==8,"Primary population count differs")
        for row,target in zip(reference["paired_population_records"],official["population_blocks"]):
            metrics.compare({"population":row["population_id"],"seed_ids":[1401,1402],
                             "paired_seed_differences":row["paired_seed_differences"],"mean_difference":row["mean_difference"]},target,"primary block")


def describe(values):
    values=list(map(float,values));n=len(values);mean=math.fsum(values)/n
    return {"n":n,"mean":mean,"sample_sd":math.sqrt(math.fsum((v-mean)**2 for v in values)/(n-1)) if n>1 else None,
            "minimum":min(values),"maximum":max(values),"median":float(np.median(values)),"values":values}


def confirmation_populations(matrix):
    populations=[p for p in matrix["populations"] if p["stage"]=="B"]
    audit.need(len(populations)==32 and len({p["population_id"] for p in populations})==32,"Exactly32 confirmation populations required")
    for family in statistics.FAMILIES:
        audit.need(sum(p["family"]==family for p in populations)==8,"Exactly8 confirmation populations per family required")
    return populations


def check_descriptive(records,actual):
    index={(r["family"],r["population"],r["seed"],r["arm"]):r for r in records}
    required={(family,arm) for family in statistics.FAMILIES for arm in statistics.ARMS}
    audit.need(len(actual)==32 and {(r["family"],r["arm"]) for r in actual}==required,"Descriptive family/arm inventory differs")
    expected_metrics={"bce","native_bce","macro_f1","accuracy","brier","ece10",
                      "positive_precision","positive_recall","grouped_tie_average_precision"}
    for summary in actual:
        audit.need(set(summary["metrics"])==expected_metrics,"Descriptive metric inventory differs")
        audit.need(set(summary["validation_milestones"])=={"0.9","0.95","0.97"},"Descriptive milestone inventory differs")
        family,arm=summary["family"],summary["arm"]
        populations=sorted({r["population"] for r in records if r["family"]==family})
        for metric,entry in summary["metrics"].items():
            means=[];undefined=[]
            for pop in populations:
                values=[index[family,pop,seed,arm]["test"][metric] for seed in statistics.SEEDS]
                if any(v is None for v in values):undefined.append(pop)
                else:means.append(math.fsum(values)/2)
            metrics.compare({"population_means":describe(means) if means else None,"undefined_population_ids":undefined},entry,"descriptive")
        for key,entry in summary["validation_milestones"].items():
            rows=[index[family,pop,seed,arm] for pop in populations for seed in statistics.SEEDS]
            reached=[r["validation_milestones"][key]["first_observed_updates"] for r in rows if r["validation_milestones"][key]["reached"]]
            metrics.compare({"total_endpoints":16,"reached":len(reached),"right_censored":16-len(reached),
                             "censor_updates":15000,"reached_only_median_updates":float(np.median(reached)) if reached else None,
                             "reached_updates":reached},entry,"milestone summary")


def check_diagnostic_summary(records,actual):
    index={(r["family"],r["population"],r["seed"],r["arm"]):r for r in records}
    expected={}
    for family in statistics.FAMILIES:
        populations=sorted({r["population"] for r in records if r["family"]==family})
        for arm in statistics.ARMS:
            for kind in ("hash","kmeans","geometric_margin"):
                bins=max(len(index[family,p,s,arm]["diagnostics"]["test"][kind]) for p in populations for s in statistics.SEEDS)
                for number in range(bins):
                    blocks=[]
                    for population in populations:
                        slices=[index[family,population,s,arm]["diagnostics"]["test"][kind] for s in statistics.SEEDS]
                        if any(len(s)<=number for s in slices):
                            blocks.append({"population":population,"status":"BIN_ABSENT_AFTER_TRAIN_EDGE_COLLAPSE"})
                            continue
                        selected=[s[number] for s in slices]
                        audit.need(selected[0]["n"]==selected[1]["n"],"Paired diagnostic counts differ")
                        n=selected[0]["n"]
                        if not n:
                            blocks.append({"population":population,"status":"EMPTY_BIN","n":0})
                            continue
                        block={"population":population,"status":"OBSERVED","n":n}
                        for metric in ("bce","macro_f1","positive_prevalence"):
                            block[metric]=math.fsum(s["metrics"][metric] for s in selected)/2
                        blocks.append(block)
                    observed=[b for b in blocks if b["status"]=="OBSERVED"]
                    expected[family,arm,kind,number]={"family":family,"arm":arm,"slice_policy":kind,"bin":number,
                        "population_blocks":blocks,"population_mean_descriptions":{
                            metric:describe([b[metric] for b in observed]) if observed else None
                            for metric in ("bce","macro_f1","positive_prevalence")}}
    actual_index={(r["family"],r["arm"],r["slice_policy"],r["bin"]):r for r in actual}
    audit.need(len(actual_index)==len(actual) and set(expected)==set(actual_index),"Diagnostic summary inventory differs")
    for key,value in expected.items():metrics.compare(value,actual_index[key],"diagnostic summary")


def replay(release_path,output):
    began=time.perf_counter()
    release,jobs,commits,matrix=verify_release(release_path)
    release_binding=audit.binding(release_path);output=Path(output).resolve()
    audit.need(output.is_relative_to((ROOT/"analysis").resolve()) and not output.exists(),"New independent analysis output required")
    official=Path(release["evaluation_output"]).resolve()
    audit.need(official.is_relative_to((ROOT/"analysis").resolve()) and official!=output,"Official output location invalid")
    official_commit=verify_output_commit(official,release_path)
    seal=audit.read(Q/"data/DATA_SEAL.json");output.mkdir(parents=True,exist_ok=False)
    reports=[];rows=[];primary_rows=[];cache={}
    try:
        for job in jobs:
            identity=job["run_id"];population=job["population_id"];method=audit.ARM_METHODS[job["arm"]]
            checkpoint_path=Path(commits[identity]["path"]).parent/"selected_checkpoint.npz"
            checkpoint=audit.load(checkpoint_path);theta=checkpoint["parameters"]
            official_row=audit.read(official/"endpoints"/identity/"metrics.json")
            metrics.compare({"job_id":identity,"family":job["family"],"population":population,
                             "seed":job["training_seed_id"],"arm":job["arm"],
                             "selected_round":int(checkpoint["current_round"])},official_row,"endpoint")
            report={"job_id":identity,"splits":{}}
            for split in ("validation","test"):
                key=(population,split)
                if key not in cache:
                    name=f"{population}_{'SEALED_test' if split=='test' else split}.npz"
                    path=Q/"data"/name;policy_path=Q/"data"/f"{population}_router.json"
                    audit.need(audit.sha(path)==seal["files"][name]["sha256"] and audit.sha(policy_path)==seal["routers"][population]["sha256"],"Heldout data/router changed")
                    pop=audit.load_primary_population(path);policy=audit.read(policy_path)
                    computed=routes_and_margin(pop["x"],policy)
                    for field,value in computed.items():audit.same(pop[field],value,"Independent raw-coordinate routing differs")
                    cache[key]=(pop,policy)
                pop,policy=cache[key]
                saved=audit.load(official/"endpoints"/identity/f"{split}_predictions.npz")
                for target,source in (("record_ids","ids"),("source_draw_ids","source_draw_ids"),("labels","y"),
                                      ("hash_route","hash_route"),("kmeans_route","kmeans_route"),("margin_bin","margin_bin")):
                    audit.same(saved[target],pop[source],"Official prediction record identity differs")
                route=None if method.endswith("_global") else pop[method.split("_")[1]+"_route"]
                p,z=reference.predict_with_logits(method,theta,pop["x"],route)
                canonical=saved["probabilities"];canonical_z=saved["native_logits"]
                threshold=audit.threshold_check(pop["y"],canonical,p,pop["ids"])
                audit.near(z,canonical_z,audit.ZTOL,"Independent heldout logits differ")
                spots=np.argsort(pop["ids"],kind="stable")[:7]
                scalar,scalar_z=reference.scalar_predict_with_logits(method,theta,pop["x"][spots],None if route is None else route[spots])
                audit.near(scalar,canonical[spots],audit.PTOL,"Heldout scalar oracle differs")
                audit.near(scalar_z,canonical_z[spots],audit.ZTOL,"Heldout scalar logits differ")
                audit.same(saved["predictions"],(canonical>=.5).astype(np.int8),"Official threshold predictions differ")
                reconstructed=metrics.score(pop["y"],canonical,canonical_z)
                metrics.compare(reconstructed,official_row[split],identity+"/"+split)
                independent_bce=reference.bce(pop["y"],p)
                audit.near(independent_bce,reconstructed["bce"],audit.BTOL,"Independent heldout BCE differs")
                for kind,assignment,count in (("hash",pop["hash_route"],5),("kmeans",pop["kmeans_route"],5),
                                               ("geometric_margin",pop["margin_bin"],policy["margin_bins"]["bins"])):
                    slices=official_row["diagnostics"][split][kind];audit.need(len(slices)==count,"All diagnostic bins required")
                    for number in range(count):
                        chosen=assignment==number
                        metrics.compare({"bin":number,"n":int(chosen.sum()),
                                         "metrics":metrics.score(pop["y"][chosen],canonical[chosen],canonical_z[chosen])},
                                        slices[number],identity+"/"+split+"/"+kind)
                path=output/"predictions"/identity/f"{split}_reference.npz";path.parent.mkdir(parents=True,exist_ok=True)
                with path.open("xb") as f:np.savez(f,record_ids=pop["ids"],probabilities=p,native_logits=z)
                report["splits"][split]={"maximum_probability_error":float(np.max(abs(p-canonical))),
                                          "maximum_native_logit_error":float(np.max(abs(z-canonical_z))),
                                          "scalar_spotcheck_records":len(spots),
                                          "maximum_scalar_probability_error":float(np.max(abs(scalar-canonical[spots]))),
                                          "independent_common_bce":independent_bce,"canonical_reconstructed_common_bce":reconstructed["bce"],
                                          "threshold":threshold,"prediction_binding":audit.binding(path)}
                if split=="test":
                    primary_rows.append({"population_id":population,"training_seed_id":job["training_seed_id"],
                                         "arm":job["arm"],"common_bce":reconstructed["bce"]})
            ledger_path=checkpoint_path.parent/"ledger.jsonl"
            ledger=[json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
            milestones=statistics.validation_milestones([row["validation"]["macro_f1"] for row in ledger])
            for entry in milestones:
                metrics.compare({"reached":entry["reached"],"first_observed_round":entry["first_observed_round"],
                                 "first_observed_updates":entry["first_observed_optimizer_update"],
                                 "right_censored":not entry["reached"],"censor_updates":15000,"resolution_updates":75},
                                official_row["validation_milestones"][str(entry["threshold"])],"validation milestone")
            source_result=audit.read(checkpoint_path.parent/"result.json")
            for field,value in official_row["training_mechanism_and_costs"].items():
                if field!="scope":metrics.compare(source_result[field],value,"training mechanism")
            reports.append(report);rows.append(official_row)
            print(json.dumps({"replayed":len(reports),"required":512,"job_id":identity}),flush=True)
        confirmation=confirmation_populations(matrix)
        primary=statistics.primary_contrasts(primary_rows,confirmation)
        compare_primary(primary,audit.read(official/"primary_analysis.json"))
        check_descriptive(rows,audit.read(official/"descriptive_summary.json"))
        check_diagnostic_summary(rows,audit.read(official/"diagnostic_summary.json"))
        write_new(output/"independent_primary_analysis.json",primary)
        write_new(output/"endpoint_replay.json",reports)
        audit.need(audit.binding(release_path)==release_binding,"Root release changed")
        audit.need(verify_output_commit(official,release_path)==official_commit,"Official outputs changed during replay")
        verify_release(release_path)
        summary={"status":"PASS","replayed_endpoints":512,"validation_and_test_prediction_rows":512*3200,
                 "primary_comparisons_replayed":20,"independent_populations_per_family":8,
                 "test_access_was_root_released":True,"real_quantum_hardware_used":False,
                 "release":release_binding,"official_evaluation_commit":official_commit,
                 "numerical_scope":"Independent raw-coordinate router, scalar/vector oracle-derived prediction/logits, canonical saved-probability metric reconstruction, separate analytic df7 interval calculation. Threshold ties retained with registered numerical-band sensitivity.",
                 "remaining_scope":"Deployment conversion, isolated timing and shot diagnostics require their separate independent checks.",
                 "created_utc":datetime.now(timezone.utc).isoformat(),"seconds":time.perf_counter()-began}
        write_new(output/"summary.json",summary)
        inventory={p.relative_to(output).as_posix():{"sha256":audit.sha(p),"bytes":p.stat().st_size} for p in sorted(output.rglob("*")) if p.is_file()}
        write_new(output/"REPLAY_COMMIT.json",{"status":"completed","files":inventory,"release":release_binding})
        return summary
    except BaseException as error:
        write_new(output/"REPLAY_FAILURE.json",{"status":"FAILED_PRESERVED","completed_endpoints":len(reports),
                                               "error":repr(error),"traceback":traceback.format_exc()})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze",action="store_true")
    parser.add_argument("--release",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.freeze:
        audit.need(args.release is None,"Freeze never permits evaluation");freeze(args.output)
    else:
        audit.need(args.release is not None,"Root release required");print(json.dumps(replay(args.release,args.output)))


if __name__=="__main__":main()
