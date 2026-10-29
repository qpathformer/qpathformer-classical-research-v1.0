"""Read-only hash and metadata gates for completed peer-owned evidence.

No arrays, model constructors, training functions or numerical auditors are
called. Exact schemas follow the peer-owned v0.8 replay/reproduction contracts.
"""
from pathlib import Path
from support import gate,committed_output

REPLAY_SOURCES=("replay_evaluation_v08.py","replay_metrics_v08.py","statistics_v08.py",
    "reference_v08.py","audit_endpoints_v08.py","AUDIT_NUMERICAL_PROTOCOL.json",
    "sampler_reference.py","audit_sampling_trace.py","replay_priority_v08.py",
    "test_statistics_v08.py","test_replay_metrics_v08.py","test_replay_priority_v08.py",
    "test_replay_evaluation_v08.py","test_replay_wrapper_v08.py","run_replay_leased.py","run_replay_preflight.py")
REPRODUCTION_SOURCES=("audit_reproduction.py","compare_reference.py","test_reproduction_audit.py")
CONVERSION_SOURCES=("reference.py","verify_arrays.py","audit_artifacts.py","release_chains.py","test_reference.py")
PRODUCER_REPRODUCTION_SOURCES=("run.py","regenerate.py","compare.py","tests/test_reproduction.py")


def committed(root,item,filename,schema):
    gate.require(Path(item["path"]).name==filename,"Wrong readiness commit filename")
    record,folder=committed_output(item,root,schema)
    gate.require(not any((folder/p).exists() for p in ("FAILURE.json","REPLAY_FAILURE.json")),
                 "Preserved failure cannot satisfy readiness")
    gate.require("summary.json" in record["files"] and gate.read(folder/"summary.json").get("status")=="PASS",
                 "Committed readiness summary is not PASS")
    return record,folder


def freeze_sources(root,item,schema,directory,names,protocols,bound_values=False):
    root=Path(root)
    freeze=gate.read(gate.verify_binding(item,root))
    gate.require(freeze.get("schema")==schema and set(freeze["sources"])==set(names),
                 "Peer source inventory/schema changed")
    if not bound_values:
        gate.require(freeze.get("test_access_authorized") is False,"Source freeze unexpectedly authorizes testing")
    for name,expected in freeze["sources"].items():
        path=root/"analysis"/directory/name
        if bound_values:
            gate.require(gate.verify_binding(expected,root)==path,"Peer source path changed")
        else:
            gate.require(gate.sha(path)==expected,"Peer source hash changed")
    gate.require(set(freeze["protocols"])==set(protocols),"Peer protocol inventory changed")
    for name,item in freeze["protocols"].items():
        gate.require(gate.verify_binding(item,root)==root/"governance"/name,"Peer protocol path changed")
    return freeze


def validate_reference_inventory(folder,commit,rows,ids,bound_predictions=True):
    gate.require(len(rows)==len(ids) and [r["job_id"] for r in rows]==ids,
                 "Reference identities missing, duplicate, or reordered")
    expected={"predictions/"+job+"/"+split+"_reference.npz" for job in ids for split in ("validation","test")}
    actual={name for name in commit["files"] if name.startswith("predictions/")}
    gate.require(actual==expected,"Reference prediction payload inventory changed")
    for row in rows:
        gate.require(set(row["splits"])=={"validation","test"},"Reference split inventory changed")
        if not bound_predictions:
            # Conversion writer commits deterministic reference paths rather than
            # duplicating individual file bindings inside its numeric split rows.
            continue
        for split,saved in row["splits"].items():
            item=saved["prediction_binding"]
            path=gate.verify_binding(item,folder)
            gate.require(path==folder/"predictions"/row["job_id"]/(split+"_reference.npz") and
                         commit["files"][path.relative_to(folder).as_posix()]==
                         {k:item[k] for k in ("sha256","bytes")},"Reference prediction binding changed")


def verify_score_replay(root,release,verified):
    root=Path(root)
    commit,folder=committed(root,release["independent_score_replay_commit"],"REPLAY_COMMIT.json",
                            "qpath-v08-independent-replay-commit-1")
    ids=[j["run_id"] for j in verified["jobs"]]
    gate.require(len(ids)==len(set(ids))==640 and commit.get("count")==640 and commit.get("run_ids")==ids,
                 "Complete 640-model score replay required")
    summary=gate.read(folder/"summary.json")
    shared={"release":verified["release_binding"],"official_evaluation_commit":verified["evaluation_commit"],
            "independent_replay_freeze":verified["release"]["independent_replay_freeze"]}
    for record in (commit,summary):
        gate.require(all(record.get(k)==v for k,v in shared.items()),"Score replay release/source/evaluation differs")
    gate.require(Path(verified["release"]["independent_replay_output"]).resolve()==folder,
                 "Score replay output not root-authorized")
    freeze_sources(root,shared["independent_replay_freeze"],"qpath-v08-independent-replay-source-freeze-1",
                   "independent_audit",REPLAY_SOURCES,
                   ("STUDY_PLAN.json","RUN_MATRIX.json","ANALYSIS_PROTOCOL.json"),bound_values=True)
    required={"replayed_endpoints":640,"reference_prediction_files":1280,"primary_comparisons_replayed":20,
              "independent_populations_per_family":8,"priority_endpoint_diagnostics_replayed":640,
              "priority_round_diagnostics_replayed":128000,"priority_training_draws_reconstructed":614400000,
              "priority_family_arm_summaries_replayed":40,"descriptive_priority_effects_replayed":20}
    gate.require(all(summary.get(k)==v for k,v in required.items()) and summary.get("ordered_run_ids")==ids,
                 "Incomplete independent prediction/statistics/priority replay")
    validate_reference_inventory(folder,commit,gate.read(folder/"endpoint_replay.json"),ids)
    gate.require("independent_primary_analysis.json" in commit["files"],"Independent primary analysis missing")
    primary=gate.read(folder/"independent_primary_analysis.json")
    protocol=gate.read(root/"governance/ANALYSIS_PROTOCOL.json")
    matrix=gate.read(root/"governance/RUN_MATRIX.json")
    populations=[p for p in matrix["populations"] if p["stage"]=="B"]
    expected={(p["family"],contrast["name"]) for p in populations for contrast in protocol["primary_contrasts"]}
    gate.require(len(primary)==20 and {(p["family"],p["contrast_name"]) for p in primary}==expected,
                 "Independent primary contrast identities incomplete")
    weights={r["name"]:r["weights"] for r in protocol["primary_contrasts"]}
    for row in primary:
        chosen=sorted(p["population_id"] for p in populations if p["family"]==row["family"])
        records=row["paired_population_records"]
        gate.require(row["weights"]==weights[row["contrast_name"]] and len(records)==8 and
                     [p["population_id"] for p in records]==chosen,
                     "Independent primary population/weight inventory differs")
        gate.require(all(len(p["paired_seed_differences"])==len(p["paired_seed_components"])==2
                         and all(set(c)==set(row["weights"]) for c in p["paired_seed_components"]) for p in records),
                     "Independent paired-seed components incomplete")
    return {"commit":commit,"folder":folder,"summary":summary}


def check_root_authority(root,item,schema,phase,folder,release,producer_item=None,ids=None):
    authority=gate.read(gate.verify_binding(item,root))
    gate.require(authority.get("schema")==schema and authority.get("review_status")=="approved_by_root" and
                 authority.get("phase")==phase and authority.get("test_access_authorized") is True and
                 authority.get("max_parallel_tasks")==authority.get("required_blas_threads")==1 and
                 Path(authority["output"]).resolve()==folder,"Independent phase root authorization differs")
    gate.require(authority["evaluation_release"]==release["evaluation_release"] and
                 authority["evaluation_commit"]==release["evaluation_commit"],"Independent evaluation binding differs")
    if producer_item is not None:gate.require(authority["producer_commit"]==producer_item,"Independent producer binding differs")
    if ids is not None:gate.require(authority["run_ids"]==ids,"Independent authorized target order differs")
    return authority


def verify_reproduction(root,release,verified):
    root=Path(root);protocol=gate.read(root/"governance/REPRODUCTION_PROTOCOL.json");ids=protocol["endpoints"]
    gate.require(protocol["count"]==len(ids)==len(set(ids))==4,"Four preselected clean reproductions required")
    producer_item=release["reproduction_commit"]
    producer,pfolder=committed(root,producer_item,"REPRODUCTION_COMMIT.json","qpath-v08-reproduction-commit-1")
    independent,folder=committed(root,release["independent_reproduction_commit"],
                                 "INDEPENDENT_REPRODUCTION_COMMIT.json","qpath-v08-independent-reproduction-commit-1")
    summary_path=gate.verify_binding(release["independent_reproduction_audit"],root)
    gate.require(summary_path==folder/"summary.json" and independent["files"]["summary.json"]==
                 {k:release["independent_reproduction_audit"][k] for k in ("sha256","bytes")},
                 "Independent reproduction summary must be in its committed inventory")
    summary=gate.read(summary_path)
    for record in (summary,independent):
        gate.require(record.get("phase")=="reproduction" and record.get("count")==4 and record.get("run_ids")==ids and
                     record.get("producer_commit")==producer_item and record.get("evaluation_commit")==verified["evaluation_commit"],
                     "Independent reproduction identity/evaluation differs")
    gate.require(summary.get("full_rounds")==800 and summary.get("full_updates")==60000 and
                 summary.get("original_checkpoints_copied") is False,"Full clean reproduction proof missing")
    authority=check_root_authority(root,independent["authorization"],"qpath-v08-independent-reproduction-release-1",
                                   "reproduction",folder,release,producer_item,ids)
    gate.require(summary["authorization"]==independent["authorization"] and
                 summary["source_freeze"]==independent["source_freeze"]==authority["source_freeze"],
                 "Independent reproduction summary/source authority differs")
    freeze_sources(root,authority["source_freeze"],"qpath-v08-independent-reproduction-source-freeze-1",
                   "independent_reproduction",REPRODUCTION_SOURCES,
                   ("REPRODUCTION_PROTOCOL.json","STUDY_PLAN.json","RUN_MATRIX.json"))
    psummary=gate.read(pfolder/"summary.json")
    for record in (producer,psummary):
        gate.require(record.get("count")==4 and record.get("run_ids")==ids and
                     record.get("evaluation_commit")==verified["evaluation_commit"],"Producer reproduction identity differs")
    pauthority=check_root_authority(root,producer["authorization"],"qpath-v08-reproduction-release-1",
                                    "reproduction",pfolder,release,ids=ids)
    gate.require(producer["registration"]==pauthority["registration"]==psummary["registration"] and
                 psummary["authorization"]==producer["authorization"] and
                 psummary.get("full_rounds")==800 and psummary.get("full_updates")==60000 and
                 psummary.get("original_checkpoints_copied") is False,"Producer summary/registration incomplete")
    registration=gate.read(gate.verify_binding(producer["registration"],root))
    expected={"analysis/reproduction/"+name for name in PRODUCER_REPRODUCTION_SOURCES}
    gate.require(registration.get("schema")=="qpath-v08-reproduction-registration-1" and
                 registration.get("test_access_authorized") is False and registration.get("run_ids")==ids and
                 set(registration["sources"])==expected,"Producer reproduction source registration differs")
    for relative,digest in registration["sources"].items():gate.require(gate.sha(root/relative)==digest,"Reproduction source drift")
    for key,name in (("protocol","REPRODUCTION_PROTOCOL.json"),("matrix","RUN_MATRIX.json")):
        gate.require(gate.verify_binding(registration[key],root)==root/"governance"/name,"Reproduction protocol differs")
    gate.require(registration["same_environment_tolerances"]==protocol["same_environment_tolerances"],"Reproduction tolerances changed")
    gate.verify_binding(pauthority["training_authorization"],root)
    gate.require(psummary["training_authorization"]==pauthority["training_authorization"],"Original B authority differs")
    index=gate.read(pfolder/"endpoint_index.json");rows=gate.read(folder/"endpoint_comparisons.json")
    gate.require(len(index)==len(rows)==4 and [r["job_id"] for r in index]==[r["job_id"] for r in rows]==ids,
                 "Reproduction endpoint identities missing or reordered")
    for identity,row,saved in zip(ids,rows,index):
        gate.require(row.get("status")=="PASS" and row.get("full_rounds")==200 and row.get("full_updates")==15000 and
                     row["original_commit"]==verified["endpoint_commits"][identity] and
                     row["reproduced_commit"]==saved["endpoint_commit"],"Reproduction comparison is incomplete")
        gate.require(gate.verify_binding(saved["endpoint_commit"],root)==
                     pfolder/"endpoints"/identity/"endpoint_commit.json","Reproduction endpoint escaped output")
    gate.require(gate.read(folder/"clean_provenance_review.json").get("status")=="PASS",
                 "Independent clean-source/data provenance missing")
    return {"commit":independent,"folder":folder,"summary":summary,"producer":producer}


def verify_conversion(root,release,verified):
    root=Path(root);item=release["conversion_commit"]
    producer,pfolder=committed(root,item,"CONVERSION_COMMIT.json","qpath-v08-conversion-commit-1")
    gate.require(producer["registration"]==verified["registration_binding"] and
                 producer["evaluation_commit"]==verified["evaluation_commit"],"Conversion derives from different evidence")
    producer_authority=check_root_authority(root,producer["authorization"],"qpath-v08-deployment-release-1",
                                            "conversion",pfolder,release)
    gate.require(producer_authority["registration"]==producer["registration"]==verified["registration_binding"] and
                 producer_authority["independent_score_replay_commit"]==release["independent_score_replay_commit"],
                 "Producer conversion source/score replay authority differs")
    registration=gate.read(gate.verify_binding(producer["registration"],root))
    gate.require(registration==verified["registration"] and registration.get("test_access_authorized") is False,
                 "Producer conversion source registration differs")
    for relative,digest in registration["sources"].items():
        path=(root/relative).resolve()
        gate.require(path.is_relative_to(root) and gate.sha(path)==digest,"Producer conversion source changed")
    for key,name in (("deployment_protocol","DEPLOYMENT_PROTOCOL.json"),
                     ("readiness_protocol","LOCAL_READINESS_PROTOCOL.json"),("run_matrix","RUN_MATRIX.json")):
        gate.require(gate.verify_binding(registration[key],root)==root/"governance"/name,
                     "Producer conversion protocol differs")
    independent,folder=committed(root,release["independent_conversion_commit"],"INDEPENDENT_DEPLOYMENT_COMMIT.json",
                                 "qpath-v08-independent-deployment-commit-1")
    path=gate.verify_binding(release["independent_conversion_audit"],root)
    gate.require(path==folder/"summary.json" and independent["files"]["summary.json"]==
                 {k:release["independent_conversion_audit"][k] for k in ("sha256","bytes")},
                 "Independent conversion summary is not committed")
    summary=gate.read(path)
    gate.require(independent.get("phase")=="conversion" and summary.get("phase")=="conversion" and
                 summary.get("circuit_endpoints")==256 and summary.get("independent_circuit_coefficients")==256 and
                 summary.get("representations_replayed")==640 and summary.get("learned_trig_exact_repacks")==384 and
                 summary.get("validation_and_test_probability_rows")==2048000 and
                 summary.get("producer_commit")==summary.get("conversion_commit")==item and
                 summary.get("authorization")==independent["authorization"],"Independent conversion scope/bindings incomplete")
    authority=check_root_authority(root,independent["authorization"],"qpath-v08-independent-deployment-release-1",
                                   "conversion",folder,release,item)
    freeze_sources(root,authority["source_freeze"],"qpath-v08-independent-deployment-source-freeze-1",
                   "independent_deployment",CONVERSION_SOURCES,
                   ("RUN_MATRIX.json","DEPLOYMENT_PROTOCOL.json","LOCAL_READINESS_PROTOCOL.json"))
    gate.require(authority["independent_score_replay_commit"]==release["independent_score_replay_commit"],
                 "Conversion independent score replay differs")
    ids=[job["run_id"] for job in verified["jobs"]]
    rows=gate.read(folder/"conversion_replay.json")
    validate_reference_inventory(folder,independent,rows,ids,bound_predictions=False)
    gate.require([r["arm"] for r in rows]==[j["arm"] for j in verified["jobs"]],"Conversion arm order changed")
    index=gate.read(pfolder/"endpoint_index.json")
    gate.require(len(index)==640 and [r["job_id"] for r in index]==ids,"Producer conversion identities incomplete")
    for job,row in zip(verified["jobs"],index):
        gate.require(row["arm"]==job["arm"],"Producer conversion arm differs")
        for key,name in (("record","conversion.json"),("representation","representation.npz")):
            gate.require(gate.verify_binding(row[key],root)==pfolder/"endpoints"/job["run_id"]/name,
                         "Producer conversion record binding differs")
    return producer,pfolder
