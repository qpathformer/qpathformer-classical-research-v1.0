"""Local circuit-level Aer audit on label-independent validation fixtures only.

This never reads a test population, creates a cloud service, or uses credentials.
It is distinct from the probability-level binomial sensitivity in final reporting.
"""
import os
for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[name]="1"
import argparse
import csv
import importlib.metadata
import math
from pathlib import Path
import sys
import traceback
import numpy as np
import qstudy as s
import ibm_local as ibm


def fixtures(dataset):
    seal=s.read_json(s.ROOT/"data/DATA_SEAL.json")
    path=s.ROOT/"data"/f"{dataset}_validation.npz"
    if s.digest(path)!=seal["files"][path.name]["sha256"]:
        raise ValueError("Validation fixture source changed")
    # Deliberately do not access the label array.
    with np.load(path,allow_pickle=False) as source:
        ids,classes=source["ids"],source["classes"]
        x,depth=source["x"],source["depth"]
        selected=[]
        for c in range(1,9):
            candidates=np.flatnonzero(classes==c)
            i=candidates[np.argmin(ids[candidates])]
            selected.append({"record_id":int(ids[i]),"synthetic_class":c,
                             "x":x[i].tolist(),"original_depth":int(depth[i])})
    return selected,s.digest(path)


def run(models,fixture_rows,source_hash,output,engineering):
    from qiskit import ClassicalRegister, qasm3
    from qiskit_aer import AerSimulator
    output.mkdir(exist_ok=False)
    (output/"circuits").mkdir()
    configuration={"created_utc":s.now(),"classification":"ENGINEERING PREFLIGHT" if engineering else "INTERNAL CIRCUIT READINESS",
                   "protocol_sha256":s.digest(s.ROOT/"READINESS_PROTOCOL.json"),
                   "source_hashes":{"local_readiness.py":s.digest(__file__),"ibm_local.py":s.digest(s.ROOT/"ibm_local.py")},
                   "validation_file_sha256":source_hash,"fixtures":fixture_rows,
                   "versions":{"python":sys.version,**{n:importlib.metadata.version(n) for n in ("numpy","qiskit","qiskit-aer")}},
                   "test_population_read":False,"labels_read":False,"hardware_jobs":0,"physical_shots":0,"credential_accessed":False}
    s.write_json(output/"configuration.json",configuration)
    numerical,compiled,measured,exact_circuits=[],[],[],[]
    try:
        for identity,model,checkpoint_hash in models:
            for fixture in fixture_rows:
                x=np.asarray(fixture["x"])
                original=fixture["original_depth"]
                d=int(model.effective_depth(np.asarray([original]))[0])
                bank=model.bank(d)
                padded=np.zeros((4,2,2));padded[:len(bank)]=bank
                ref=s.reference.unitary(x,bank,d)
                source=ibm.build_circuit(x,padded,d)
                target=ibm.compile_local(source,ibm.CompilerOptions(optimization_level=1,seed_transpiler=331,initial_layout=(0,1)))
                names=f"{identity}_C{fixture['synthetic_class']}"
                errors={"numpy_matrix":ibm.aligned_error(ref,s.quantum.unitary(x,bank,d)),
                        "qiskit_source":ibm.aligned_error(ref,ibm.logical_unitary(source)),
                        "qiskit_compiled":ibm.aligned_error(ref,ibm.logical_unitary(target))}
                if max(errors.values())>1e-10:
                    raise ValueError("Independent circuit translation failed")
                mapping=ibm.wire_mappings(target)
                measurement=target.copy()
                measurement.add_register(ClassicalRegister(1,"c"))
                measurement.measure(mapping["final_logical_to_physical"][0],0)
                (output/"circuits"/f"{names}.qasm").write_text(qasm3.dumps(measurement),encoding="utf-8")
                exact=target.copy()
                exact.save_statevector()
                exact_circuits.append(exact)
                compiled.append(target)
                measured.append(measurement)
                numerical.append({"identity":identity,"method":model.method,"fixture_class":fixture["synthetic_class"],
                                  "record_id":fixture["record_id"],"original_depth":original,"executed_depth":d,
                                  "checkpoint_sha256":checkpoint_hash,"reference_probability":ibm.probability_one(ref),
                                  "model_probability":float(model.predict(x[None,:],np.asarray([original]))[0]),
                                  "errors":errors,"mapping":mapping,"compiled_operations":dict(target.count_ops()),
                                  "compiled_depth_excluding_measurement":target.depth(),"qasm_file":f"circuits/{names}.qasm"})
        simulator=AerSimulator(method="statevector",device="CPU",precision="double",max_parallel_threads=1,max_parallel_experiments=1)
        result=simulator.run(exact_circuits).result()
        if not result.success:
            raise RuntimeError("Exact Aer statevector evaluation failed")
        for i,row in enumerate(numerical):
            state=np.asarray(result.get_statevector(i))
            bit=row["mapping"]["final_logical_to_physical"][0]
            probability=float(sum(abs(state[k])**2 for k in range(4) if (k>>bit)&1))
            row["aer_exact_probability"]=probability
            row["aer_reference_probability_error"]=abs(probability-row["reference_probability"])
            if max(row["aer_reference_probability_error"],abs(row["model_probability"]-row["reference_probability"]))>1e-10:
                raise ValueError("Aer/reference or model/reference marginal disagrees")
        sampled=[]
        total_tests=len(measured)*2*5
        for budget in (1024,4096):
            bound=math.sqrt(math.log(2*total_tests/.01)/(2*budget))
            for seed in (701,702,703,704,705):
                counts=ibm.local_counts(measured,budget,seed)
                for row,count in zip(numerical,counts):
                    probability=count.get("1",0)/budget
                    error=abs(probability-row["aer_exact_probability"])
                    sampled.append({"identity":row["identity"],"fixture_class":row["fixture_class"],"record_id":row["record_id"],
                                    "shots":budget,"shot_seed":seed,"counts":count,"probability":probability,
                                    "absolute_sampling_error":error,"simultaneous_hoeffding_bound":bound,"passed":error<=bound})
        s.write_json(output/"numerical_checks.json",numerical)
        s.write_json(output/"aer_counts.json",sampled)
        summary={"status":"pass" if all(r["passed"] for r in sampled) else "sampling_check_failed", "engineering":engineering,
                 "fixture_circuits":len(numerical),"independent_matrix_comparisons":3*len(numerical),
                 "max_matrix_error":max(max(r["errors"].values()) for r in numerical),
                 "max_aer_probability_error":max(r["aer_reference_probability_error"] for r in numerical),
                 "aer_sampled_executions":len(sampled),"aer_simulated_shots":len(numerical)*5*(1024+4096),
                 "sampling_family_alpha":.01,"sampling_failures":sum(not r["passed"] for r in sampled),
                 "test_population_read":False,"labels_read":False,"hardware_jobs":0,"physical_shots":0,
                 "scope":"Local compiled-circuit Aer checks on eight label-independent validation fixtures per selected checkpoint; not a predictive-quality estimate or an IBM-device certificate",
                 "compilation":"RY/RZ/CX simulator basis, optimization1, fixed layout0/1, transpiler seed331; not actual IBM backend ISA"}
        s.write_json(output/"summary.json",summary)
        s.write_json(output/"manifest.json",{"files":{str(p.relative_to(output)):s.digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
        print(summary)
    except BaseException as exc:
        s.write_json(output/"failure.json",{"utc":s.now(),"error":str(exc),"traceback":traceback.format_exc()})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engineering",action="store_true")
    args=parser.parse_args()
    protocol=s.read_json(s.ROOT/"READINESS_PROTOCOL.json")
    if protocol["source_hashes"]!={"local_readiness.py":s.digest(__file__),"ibm_local.py":s.digest(s.ROOT/"ibm_local.py")}:
        raise ValueError("Readiness source does not match registered protocol")
    if args.engineering:
        models=[(f"engineering_{m}",s.Model(m,901),None) for m in s.CANDIDATES]
        fixture_rows,source_hash=fixtures("engineering")
        return run(models,fixture_rows,source_hash,s.ROOT/"readiness_engineering_preflight",True)
    freeze=s.read_json(s.ROOT/"STAGE_B_FREEZE.json")
    if freeze.get("readiness_protocol_sha256")!=s.digest(s.ROOT/"READINESS_PROTOCOL.json"):
        raise ValueError("Stage B must register readiness before outcomes")
    from evaluate_confirmation import endpoints,load_model
    _,selection,items=endpoints()
    models=[]
    for seed,method,folder,r in items:
        if method==selection["selected_candidate"]:
            model,_,_=load_model(method,seed,folder/"selected_checkpoint.npz")
            models.append((f"seed_{seed}_{method}",model,r["selected_checkpoint_sha256"]))
    if len(models)!=5:
        raise ValueError("All five selected-candidate checkpoints are required")
    fixture_rows,source_hash=fixtures("confirmation")
    run(models,fixture_rows,source_hash,s.ROOT/"local_readiness_results",False)


if __name__=="__main__":
    main()
