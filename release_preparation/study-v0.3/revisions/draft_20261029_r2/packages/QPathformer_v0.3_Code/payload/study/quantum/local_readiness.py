"""Validation-only local matrix, transpilation and ideal Aer fixture audit.

Uses all registered methods/seeds, never outcome-selected checkpoints. This is
not IBM hardware evidence and its RY/RZ/CX basis is not a physical device ISA.
"""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time
import traceback
import numpy as np
from qiskit import transpile,qasm2,ClassicalRegister
from qiskit.quantum_info import Operator
from qiskit_aer import AerSimulator
import qstudy as s
import reference_v03
from ibm_local_v03 import build_circuit,selected_circuit_parameters,phase_aligned_error

METHODS=('encoding1','readout1','kmeans40')
SHOTS=(1024,4096)
MEASURE_SEEDS=(801,802,803,804,805)


def require(condition,message):
    if not condition:raise RuntimeError(message)


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def run(output,engineering=False):
    if output.exists():raise FileExistsError(output)
    dataset='engineering' if engineering else 'confirmation';seeds=(9501,) if engineering else s.SEEDS['B']
    base=s.ROOT/'engineering_pilot_v02' if engineering else s.ROOT/'stage_B'
    watched={s.ROOT/name:s.digest(s.ROOT/name) for name in ('ibm_local_v03.py','local_readiness.py','reference_v03.py','READINESS_PROTOCOL.json','data/DATA_SEAL.json')}
    watched[s.ROOT/'data'/f'{dataset}_router.json']=s.digest(s.ROOT/'data'/f'{dataset}_router.json')
    watched[s.ROOT/'data'/f'{dataset}_validation.npz']=s.digest(s.ROOT/'data'/f'{dataset}_validation.npz')
    pop=s.load_population(dataset,'validation')
    fixture=[]
    for cls in range(1,9):
        indices=np.flatnonzero(pop['classes']==cls)
        require(len(indices)>0,'Missing allocation class')
        fixture.append(int(indices[np.argmin(pop['ids'][indices])]))
    for bank in range(5):
        indices=np.flatnonzero(pop['kmeans_route']==bank)
        require(len(indices)>0,'Missing validation kmeans bank')
        fixture.append(int(indices[np.argmin(pop['ids'][indices])]))
    fixture=sorted(set(fixture),key=lambda index:int(pop['ids'][index]))
    lock=None
    if not engineering:
        watched[s.ROOT/'CONFIRMATION_ENDPOINT_LOCK.json']=s.digest(s.ROOT/'CONFIRMATION_ENDPOINT_LOCK.json')
        watched[s.ROOT/'STAGE_B_FREEZE.json']=s.digest(s.ROOT/'STAGE_B_FREEZE.json')
        watched[s.ROOT/'EVALUATION_REGISTRATION.json']=s.digest(s.ROOT/'EVALUATION_REGISTRATION.json')
        lock=s.read_json(s.ROOT/'CONFIRMATION_ENDPOINT_LOCK.json')
        require(lock['status']=='PASS' and lock['stage']=='B' and lock['endpoint_count']==65,'Full B endpoint lock required')
        require(lock['stage_freeze_sha256']==s.digest(s.ROOT/'STAGE_B_FREEZE.json') and lock['data_seal_sha256']==s.digest(s.ROOT/'data/DATA_SEAL.json'),'Stale lock')
        require(lock['training_source_hashes']==s.source_hashes(),'Training source changed')
        registration=s.read_json(s.ROOT/'EVALUATION_REGISTRATION.json')
        for name,digest in registration['source_hashes'].items():
            require(s.digest(s.ROOT/name)==digest,'Registered evaluation/readiness source changed');watched[s.ROOT/name]=digest
    output.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
    try:
        rows=[];sources=[];compiled=[];bound={};maximum_source_error=maximum_compiled_error=0.
        for seed in seeds:
            for method in METHODS:
                folder=base/method if engineering else base/f'seed_{seed}'/method
                result=s.read_json(folder/'result.json');require(result['status']=='completed','Checkpoint endpoint incomplete')
                checkpoint=folder/'selected_checkpoint.npz';checkpoint_hash=s.digest(checkpoint);bound[str(checkpoint)]=checkpoint_hash
                watched[folder/'result.json']=s.digest(folder/'result.json')
                require(result['selected_checkpoint_sha256']==checkpoint_hash,'Checkpoint changed')
                if not engineering:
                    s.verify_freeze('B',seed,method)
                    row=next(r for r in lock['endpoints'] if r['seed']==seed and r['method']==method)
                    require(row['selected_checkpoint_sha256']==checkpoint_hash and row['result_sha256']==s.digest(folder/'result.json'),'Locked endpoint changed')
                with np.load(checkpoint,allow_pickle=False) as cp:parameters=cp['parameters'].copy()
                for index in fixture:
                    bank,depth,encoding,beta=selected_circuit_parameters(method,parameters,pop['depth'][index],pop['hash_route'][index],pop['kmeans_route'][index])
                    qc=build_circuit(pop['x'][index],bank,depth,encoding,beta)
                    reference=reference_v03.unitary(pop['x'][index],bank,depth,encoding,beta)
                    source_error=phase_aligned_error(Operator(qc).data,reference)
                    transpiled=transpile(qc,basis_gates=['ry','rz','cx'],optimization_level=1,seed_transpiler=97003)
                    compiled_error=phase_aligned_error(Operator(transpiled).data,reference)
                    require(max(source_error,compiled_error)<=1e-10,'Unitary mapping mismatch')
                    key=f'{method}_seed{seed}_class{int(pop["classes"][index])}_id{int(pop["ids"][index])}'
                    (output/'circuits').mkdir(exist_ok=True)
                    (output/'circuits'/f'{key}_source.qasm').write_text(qasm2.dumps(qc)+'\n',encoding='utf-8')
                    (output/'circuits'/f'{key}_compiled.qasm').write_text(qasm2.dumps(transpiled)+'\n',encoding='utf-8')
                    reference_probability=float(np.sum(abs(reference[2:,0])**2))
                    row={'key':key,'method':method,'training_seed':seed,'record_id':int(pop['ids'][index]),'allocation_class':int(pop['classes'][index]),
                         'x':pop['x'][index].tolist(),'original_depth':int(pop['depth'][index]),'kmeans_route':int(pop['kmeans_route'][index]),
                         'checkpoint_sha256':checkpoint_hash,'depth':depth,'encoding':encoding,'readout_beta':beta,
                         'reference_probability':reference_probability,'source_unitary_error':source_error,'compiled_unitary_error':compiled_error,
                         'source_operations':dict(qc.count_ops()),'compiled_operations':dict(transpiled.count_ops()),
                         'source_depth':qc.depth(),'compiled_depth':transpiled.depth()}
                    rows.append(row);sources.append(qc);compiled.append(transpiled)
                    maximum_source_error=max(maximum_source_error,source_error);maximum_compiled_error=max(maximum_compiled_error,compiled_error)
        exact=AerSimulator(method='statevector',max_parallel_threads=1,max_parallel_experiments=1)
        exact_circuits=[]
        for qc in compiled:
            clone=qc.copy();clone.save_statevector();exact_circuits.append(clone)
        exact_result=exact.run(exact_circuits,shots=1,seed_simulator=97003).result()
        require(exact_result.success,'Aer exact execution failed')
        maximum_probability_error=0.
        for index,row in enumerate(rows):
            state=np.asarray(exact_result.get_statevector(index));p=float(np.sum(abs(state[2:])**2))
            error=abs(p-row['reference_probability']);require(error<=1e-10,'Aer marginal mismatch')
            row['aer_probability']=p;row['aer_probability_error']=error;maximum_probability_error=max(maximum_probability_error,error)
        measured=[]
        for index,qc in enumerate(compiled):
            clone=qc.copy();clone.add_register(ClassicalRegister(1));clone.measure(1,0);measured.append(clone)
            (output/'circuits'/f'{rows[index]["key"]}_measured.qasm').write_text(qasm2.dumps(clone)+'\n',encoding='utf-8')
        simulator=AerSimulator(method='statevector',max_parallel_threads=1,max_parallel_experiments=1)
        count_rows=[]
        comparison_count=len(rows)*len(SHOTS)*len(MEASURE_SEEDS)
        for budget in SHOTS:
            epsilon=float(np.sqrt(np.log(2*comparison_count/.01)/(2*budget)))
            for measurement_seed in MEASURE_SEEDS:
                seed=int(np.random.SeedSequence([97003,budget,measurement_seed]).generate_state(1,dtype=np.uint32)[0])
                result=simulator.run(measured,shots=budget,seed_simulator=seed).result();require(result.success,'Aer shot execution failed')
                for index,row in enumerate(rows):
                    counts=result.get_counts(index);n1=int(counts.get('1',0));n0=int(counts.get('0',0))
                    require(n0+n1==budget,'Incomplete Aer shot count')
                    error=abs(n1/budget-row['reference_probability'])
                    count_rows.append({'key':row['key'],'budget':budget,'measurement_seed':measurement_seed,'aer_seed_simulator':seed,
                                      'counts':{'0':n0,'1':n1},'absolute_error':error,'hoeffding_familywise_99_bound':epsilon,'within_bound':bool(error<=epsilon)})
        for path,digest in bound.items():require(s.digest(path)==digest,'Checkpoint changed during readiness')
        for path,digest in watched.items():require(s.digest(path)==digest,'Bound source/protocol/data/endpoint metadata changed during readiness')
        write_new(output/'counts.json',count_rows)
        violations=sum(not r['within_bound'] for r in count_rows)
        report={'status':'PASS' if violations==0 else 'PASS_WITH_SHOT_SMOKE_FLAG','matrix_exact_status':'PASS',
                'shot_smoke_status':'PASS' if violations==0 else 'FLAG_RETAINED_WITHOUT_RETRY',
                'engineering':engineering,'created_utc':s.now(),'dataset':dataset,'test_accessed':False,
                'methods':list(METHODS),'training_seeds':list(seeds),'fixture_rule':'Deterministic union of smallest validation record ID per random allocation class C1..C8 and per kmeans bank0..4; unique records sorted by ID; labels not used.',
                'fixture_record_ids':[int(pop['ids'][i]) for i in fixture],'circuit_count':len(rows),'matrix_comparisons':2*len(rows),
                'aer_exact_probability_checks':len(rows),'maximum_source_unitary_error':maximum_source_error,
                'maximum_compiled_unitary_error':maximum_compiled_error,'maximum_aer_probability_error':maximum_probability_error,
                'actual_simulated_measurement_shots':len(rows)*sum(SHOTS)*len(MEASURE_SEEDS),
                'shot_comparisons':comparison_count,'hoeffding_familywise_alpha':.01,
                'hoeffding_violations':violations,
                'statistical_check_note':'Hoeffding union bound is a stochastic smoke check across all registered comparisons, not a circuit correctness proof or efficacy test. An observed violation is retained and flagged, never resampled.',
                'scope':'Local ideal Aer validation fixture only; no noise, IBM provider, remote backend, physical shots or device ISA. RY/RZ/CX transpilation is simulator basis. Full-test binomial sensitivity is a separate probability-level calculation.',
                'environment':{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'numpy':np.__version__,
                               'qiskit':importlib.metadata.version('qiskit'),'qiskit_aer':importlib.metadata.version('qiskit-aer')},
                'router_policy_sha256':s.digest(s.ROOT/'data'/f'{dataset}_router.json'),'data_seal_sha256':s.digest(s.ROOT/'data/DATA_SEAL.json'),
                'checkpoint_hashes':bound,'watched_input_hashes':{str(p):v for p,v in watched.items()},
                'source_hashes':{n:watched[s.ROOT/n] for n in ('ibm_local_v03.py','local_readiness.py','reference_v03.py')},
                'counts_sha256':s.digest(output/'counts.json'),'elapsed_seconds':time.perf_counter()-start,'circuits':rows}
        write_new(output/'report.json',report)
        inventory={p.relative_to(output).as_posix():s.digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
        write_new(output/'READINESS_COMMIT.json',{'status':'completed','created_utc':s.now(),'files':inventory,'test_accessed':False})
        print(json.dumps({k:report[k] for k in ('status','circuit_count','maximum_aer_probability_error','actual_simulated_measurement_shots','hoeffding_violations')}))
    except BaseException as error:
        write_new(output/'FAILURE.json',{'status':'FAIL','created_utc':s.now(),'error':str(error),'traceback':traceback.format_exc(),'test_accessed':False});raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--engineering',action='store_true')
    args=parser.parse_args();run(args.output,args.engineering)


if __name__=='__main__':main()
