"""Registered local Qiskit/Aer fixture and illustrative logical-noise capsule.

No provider/backend/network/hardware. Official execution requires all135 B
audits and root release; engineering mode is restricted to engineering data.
Compiled target and logical-noise circuits are intentionally separate.
"""
import argparse
import importlib.metadata
from pathlib import Path
import platform
import sys
import time
import traceback
import numpy as np
from qiskit import QuantumCircuit,ClassicalRegister,qasm2,transpile
from qiskit.quantum_info import Operator
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel,depolarizing_error,ReadoutError
import study as s
import reference_v03
import evaluate_confirmation as evaluation

PROTOCOL=s.ROOT.parent/'governance/LOCAL_READINESS_PROTOCOL.json'
METHODS=('q2_global','q2_hash','q2_kmeans')


def build_circuit(x,bank):
    """Logical q0 is Qiskit wire1, so Operator basis remains |q0 q1>."""
    x=np.asarray(x,dtype=float);bank=np.asarray(bank,dtype=float)
    s.require(x.shape==(2,) and bank.shape==(2,2,2) and np.isfinite(x).all() and np.isfinite(bank).all(),'Invalid circuit input')
    qc=QuantumCircuit(2)
    for layer in range(2):
        for logical in range(2):
            wire=1-logical;qc.ry(float(np.pi*x[logical]),wire)
            qc.ry(float(bank[layer,logical,0]),wire);qc.rz(float(bank[layer,logical,1]),wire)
        qc.cx(1,0)
    qc.ry(float(np.pi/2),1)
    return qc


def phase_error(actual,reference):
    a,b=np.asarray(actual),np.asarray(reference);overlap=np.vdot(b.ravel(),a.ravel())
    phase=overlap/abs(overlap) if abs(overlap)>0 else 1.
    return float(np.max(abs(a-phase*b)))


def noise_model(scenario,with_readout=False):
    noise=NoiseModel();one=scenario['one_qubit_depolarizing'];two=scenario['cx_depolarizing'];readout=scenario['symmetric_readout_flip']
    if one:noise.add_all_qubit_quantum_error(depolarizing_error(one,1),['ry','rz'])
    if two:noise.add_all_qubit_quantum_error(depolarizing_error(two,2),['cx'])
    if with_readout and readout:noise.add_all_qubit_readout_error(ReadoutError([[1-readout,readout],[readout,1-readout]]))
    return noise


def build_fixture(population,seed,method,folder,validation,indices,output,protocol):
    model=s.Model(method,seed);checkpoint=folder/'selected_checkpoint.npz'
    with np.load(checkpoint,allow_pickle=False) as f:model.parameters[:]=f['parameters']
    pop={k:a[indices] for k,a in validation.items()};route=model.route_for(pop);production=model.predict_population(pop)
    rows=[];logical=[];compiled=[]
    for i,xy in enumerate(pop['x']):
        bank_id=0 if route is None else int(route[i]);bank=model.parameters[bank_id*8:(bank_id+1)*8].reshape(2,2,2)
        qc=build_circuit(xy,bank);ref=reference_v03.unitary(xy,bank,2)
        reference_probability=float(np.sum(abs(ref[2:,0])**2))
        compiled_qc=transpile(qc,basis_gates=protocol['compile']['basis_gates'],coupling_map=protocol['compile']['coupling_map'],
            initial_layout=[0,1],optimization_level=protocol['compile']['optimization_level'],seed_transpiler=protocol['compile']['seed_transpiler'])
        source_error=phase_error(Operator(qc).data,ref);compiled_error=phase_error(Operator(compiled_qc).data,ref)
        compiled_probability=float(np.sum(abs(Operator(compiled_qc).data[2:,0])**2))
        s.require(max(source_error,compiled_error)<=2e-12,'Source/compiled unitary disagreement')
        s.require(abs(reference_probability-production[i])<=2e-12 and abs(compiled_probability-reference_probability)<=2e-12,'Ideal probability disagreement')
        key=f'{population}__seed{seed}__{method}__id{int(pop["ids"][i])}'
        for suffix,circuit in (('logical',qc),('compiled',compiled_qc)):
            with (output/'circuits'/f'{key}__{suffix}.qasm').open('x',encoding='utf-8') as f:f.write(qasm2.dumps(circuit)+'\n')
        rows.append({'key':key,'population':population,'training_seed':seed,'method':method,'fixture_index':i,
             'record_id':int(pop['ids'][i]),'x':xy.tolist(),'bank':bank_id,'hash_route':int(pop['hash_route'][i]),'kmeans_route':int(pop['kmeans_route'][i]),
             'checkpoint_sha256':s.digest(checkpoint),'production_probability':float(production[i]),'reference_probability':reference_probability,
             'compiled_probability':compiled_probability,'source_unitary_error':source_error,'compiled_unitary_error':compiled_error,
             'logical_operations':dict(qc.count_ops()),'compiled_operations':dict(compiled_qc.count_ops()),
             'logical_depth':qc.depth(),'compiled_depth':compiled_qc.depth(),'compiled_global_phase':float(compiled_qc.global_phase)})
        logical.append(qc);compiled.append(compiled_qc)
    return rows,logical,compiled


def execute_capsule(populations,seeds,base,output,protocol,watched,engineering):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);(output/'circuits').mkdir();start=time.perf_counter()
    try:
        rows=[];logical=[];compiled=[];fixtures={}
        for population in populations:
            val=s.load_population(population,'validation');indices=np.argsort(val['ids'],kind='stable')[:32]
            s.require(len(indices)==32,'Missing registered fixture size');fixtures[population]=val['ids'][indices].tolist()
            for name in (f'{population}_validation.npz',f'{population}_router.json'):
                path=s.ROOT/'data'/name;watched[path]=s.digest(path)
            for seed in seeds:
                for method in METHODS:
                    folder=base/population/f'seed_{seed}'/method
                    commit=s.read_json(folder/'endpoint_commit.json');s.require(commit['status']=='completed','Checkpoint endpoint not committed')
                    for name in ('selected_checkpoint.npz','result.json'):
                        path=folder/name;s.require(s.digest(path)==commit['files'][name]['sha256'],'Changed checkpoint/result');watched[path]=s.digest(path)
                    watched[folder/'endpoint_commit.json']=s.digest(folder/'endpoint_commit.json')
                    rr,qq,cc=build_fixture(population,seed,method,folder,val,indices,output,protocol)
                    rows.extend(rr);logical.extend(qq);compiled.extend(cc)
        timings={};density=np.empty((len(protocol['noise_scenarios']),len(rows)),dtype=float)
        for scenario_index,scenario in enumerate(protocol['noise_scenarios']):
            t=time.perf_counter();sim=AerSimulator(method='density_matrix',noise_model=noise_model(scenario),max_parallel_threads=1,max_parallel_experiments=1)
            jobs=[]
            for qc in logical:
                c=qc.copy();c.save_density_matrix();jobs.append(c)
            result=sim.run(jobs,shots=1,seed_simulator=protocol['aer_measured_smoke']['seed_simulator']).result()
            s.require(result.success,'Density-matrix execution failed')
            for i,row in enumerate(rows):
                rho=np.asarray(result.data(i)['density_matrix']);p1=float(np.real(rho[2,2]+rho[3,3]));r=scenario['symmetric_readout_flip']
                s.require(-2e-12<=p1<=1+2e-12,'Invalid density probability');observed=float(np.clip(r+(1-2*r)*p1,0,1));density[scenario_index,i]=observed
                row.setdefault('scenarios',{})[scenario['name']]={'premeasurement_probability':p1,'observed_probability':observed,
                         'absolute_distortion_from_ideal':abs(observed-row['reference_probability']),
                         'classification_disagreement_from_ideal':bool((observed>=.5)!=(row['reference_probability']>=.5))}
                if scenario['name']=='ideal':s.require(abs(observed-row['reference_probability'])<=2e-12,'Aer ideal probability disagrees')
            timings['density_'+scenario['name']]=time.perf_counter()-t
        # Compiled ideal Aer is separate from the logical-gate noise channels.
        t=time.perf_counter();sim=AerSimulator(method='statevector',max_parallel_threads=1,max_parallel_experiments=1);jobs=[]
        for qc in compiled:
            c=qc.copy();c.save_statevector();jobs.append(c)
        result=sim.run(jobs,shots=1,seed_simulator=protocol['aer_measured_smoke']['seed_simulator']).result()
        s.require(result.success,'Compiled ideal Aer failed')
        for i,row in enumerate(rows):
            state=np.asarray(result.get_statevector(i));p=float(np.sum(abs(state[2:])**2));row['compiled_aer_probability']=p
            s.require(abs(p-row['reference_probability'])<=2e-12,'Compiled Aer probability disagrees')
        timings['compiled_ideal_aer']=time.perf_counter()-t
        counts={};sampled={};shot_rows=[];shot_config=protocol['finite_shot'];t=time.perf_counter()
        for pi,population in enumerate(populations):
            for seed in seeds:
                for mi,method in enumerate(METHODS):
                    ids=[i for i,row in enumerate(rows) if (row['population'],row['training_seed'],row['method'])==(population,seed,method)]
                    s.require(len(ids)==32,'Fixture group size mismatch')
                    for ni,scenario in enumerate(protocol['noise_scenarios']):
                        p=density[ni,ids]
                        for shots in shot_config['shots']:
                            for repeat in range(shot_config['replicates']):
                                sequence=[490101,pi,seed,mi,ni,shots,repeat];rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(sequence)))
                                n1=rng.binomial(shots,p).astype(np.int64);q=n1/shots
                                key=f'{population}__seed{seed}__{method}__{scenario["name"]}__shots{shots}__repeat{repeat}'
                                counts[key]=n1;sampled[key]=q
                                shot_rows.append({'key':key,'population':population,'training_seed':seed,'method':method,'scenario':scenario['name'],
                                    'shots':shots,'repeat_index':repeat,'seed_sequence':sequence,'record_ids':[rows[i]['record_id'] for i in ids],
                                    'mean_absolute_probability_error':float(np.mean(abs(q-p))),'classification_disagreement_from_density':float(np.mean((q>=.5)!=(p>=.5)))})
        np.savez_compressed(output/'finite_shot_counts.npz',**counts);np.savez_compressed(output/'finite_shot_probabilities.npz',**sampled)
        s.write_json(output/'finite_shot_records.json',shot_rows,True);timings['binomial_sampling']=time.perf_counter()-t
        # Actual measured Aer smoke, without a stochastic pass/fail threshold.
        smoke_indices=[i for i,row in enumerate(rows) if row['fixture_index']<8];measured=[]
        for i in smoke_indices:
            qc=logical[i].copy();qc.add_register(ClassicalRegister(1));qc.measure(1,0);measured.append(qc)
            with (output/'circuits'/f'{rows[i]["key"]}__measured.qasm').open('x',encoding='utf-8') as f:f.write(qasm2.dumps(qc)+'\n')
        smoke=[];sm=protocol['aer_measured_smoke']
        for scenario in protocol['noise_scenarios']:
            if scenario['name'] not in sm['scenarios']:continue
            t=time.perf_counter();sim=AerSimulator(method='density_matrix',noise_model=noise_model(scenario,True),max_parallel_threads=1,max_parallel_experiments=1)
            result=sim.run(measured,shots=sm['shots'],seed_simulator=sm['seed_simulator']).result();s.require(result.success,'Measured Aer smoke execution failed')
            for j,i in enumerate(smoke_indices):
                c=result.get_counts(j);n1=int(c.get('1',0));n0=int(c.get('0',0));s.require(n0+n1==sm['shots'],'Measured shot count mismatch')
                p=rows[i]['scenarios'][scenario['name']]['observed_probability'];variance=sm['shots']*p*(1-p)
                smoke.append({'key':rows[i]['key'],'scenario':scenario['name'],'shots':sm['shots'],'counts':{'0':n0,'1':n1},
                              'density_expected_probability':p,'observed_probability':n1/sm['shots'],
                              'standardized_count_residual':float((n1-sm['shots']*p)/np.sqrt(variance)) if variance>0 else None,
                              'degenerate_variance':variance==0,'seed_simulator':sm['seed_simulator']})
            timings['measured_aer_'+scenario['name']]=time.perf_counter()-t
        s.write_json(output/'measured_aer_counts.json',smoke,True)
        summaries={}
        for population in populations:
            summaries[population]={}
            for method in METHODS:
                chosen=[row for row in rows if row['population']==population and row['method']==method]
                summaries[population][method]={name:{'checkpoint_fixture_pairs':len(chosen),
                    'mean_absolute_distortion':float(np.mean([r['scenarios'][name]['absolute_distortion_from_ideal'] for r in chosen])),
                    'maximum_absolute_distortion':float(np.max([r['scenarios'][name]['absolute_distortion_from_ideal'] for r in chosen])),
                    'classification_disagreement_fraction':float(np.mean([r['scenarios'][name]['classification_disagreement_from_ideal'] for r in chosen]))}
                    for name in [scenario['name'] for scenario in protocol['noise_scenarios']]}
        for path,digest in watched.items():s.require(s.digest(path)==digest,'Bound source/protocol/data/checkpoint changed during capsule')
        report={'status':'PASS','engineering':engineering,'created_utc':s.now(),'test_accessed':False,
          'scope':protocol['scope'],'matrix_and_ideal_status':'PASS','measured_smoke_status':'RECORDED_WITHOUT_STOCHASTIC_PASS_FAIL_GATE',
          'populations':list(populations),'training_seeds':list(seeds),'methods':list(METHODS),'fixture_ids':fixtures,
          'circuit_count':len(rows),'matrix_comparisons':2*len(rows),'density_scenario_circuit_evaluations':len(rows)*3,
          'compiled_ideal_aer_circuit_evaluations':len(rows),'measured_aer_circuit_experiments':len(smoke),
          'actual_simulated_measurement_shots':sum(r['shots'] for r in smoke),'finite_shot_array_count':len(counts),
          'represented_binomial_trials':sum(r['shots']*32 for r in shot_rows),
          'maximum_source_unitary_error':max(row['source_unitary_error'] for row in rows),
          'maximum_compiled_unitary_error':max(row['compiled_unitary_error'] for row in rows),
          'maximum_ideal_density_probability_error':max(abs(row['scenarios']['ideal']['observed_probability']-row['reference_probability']) for row in rows),
          'maximum_compiled_aer_probability_error':max(abs(row['compiled_aer_probability']-row['reference_probability']) for row in rows),
          'summaries':summaries,'timings_seconds':timings,'elapsed_seconds':time.perf_counter()-start,
          'protocol_sha256':s.digest(PROTOCOL),'watched_input_hashes':{str(p):digest for p,digest in watched.items()},
          'environment':{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'numpy':np.__version__,
                 'qiskit':importlib.metadata.version('qiskit'),'qiskit_aer':importlib.metadata.version('qiskit-aer')},
          'limits':protocol['limitations'],'noise_semantics':protocol['noise_semantics'],
          'compiled_layout':'initial_layout=[0,1], fully connected abstract2qubit basis; logicalq0 mapswire1',
          'sampling_scope':'Independent budgets and repeats within each fixed checkpoint/fixture; not extra independent training seeds. No labels or accuracy used to select fixtures or assess noise.',
          'circuits':rows}
        s.write_json(output/'report.json',report,True)
        inventory={p.relative_to(output).as_posix():{'sha256':s.digest(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()}
        s.write_json(output/'READINESS_COMMIT.json',{'status':'completed','created_utc':s.now(),'files':inventory,'engineering':engineering,'test_accessed':False},True)
        print({k:report[k] for k in ('status','engineering','circuit_count','actual_simulated_measurement_shots','finite_shot_array_count')})
    except BaseException as error:
        s.write_json(output/'FAILURE.json',{'status':'FAIL','error':str(error),'traceback':traceback.format_exc(),'created_utc':s.now(),'test_accessed':False},True);raise


def run(output,engineering_root=None):
    if Path(output).exists():raise FileExistsError(output)
    protocol=s.read_json(PROTOCOL);s.require(protocol['methods']==list(METHODS),'Readiness method order differs')
    s.require(np.__version__=='2.5.4','Registered NumPy required')
    watched={PROTOCOL:s.digest(PROTOCOL),Path(__file__):s.digest(__file__),s.ROOT/'data/DATA_SEAL.json':s.digest(s.ROOT/'data/DATA_SEAL.json')}
    for name,digest in s.source_hashes().items():watched[s.ROOT/name]=digest
    if engineering_root is not None:
        populations=s.ENGINEERING;seeds=(9701,);base=Path(engineering_root)
    else:
        reg,lock,release,bound=evaluation.verify_guard(output_must_be_absent=False);watched.update(bound)
        populations=s.POPULATIONS['B'];seeds=s.SEEDS['B'];base=s.ROOT/'stage_B'
        s.require(protocol['populations']==list(populations) and protocol['training_seeds']==list(seeds),'Readiness scope differs')
    execute_capsule(populations,seeds,base,output,protocol,watched,engineering_root is not None)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--engineering-root',type=Path)
    a=p.parse_args();run(a.output,a.engineering_root)


if __name__=='__main__':main()
