"""Local multi-observable circuit capsule; no provider, network or hardware.

Public execution requires all165 endpoint audits and root release. Preflight is
limited to the separate synthetic driver and generated untrained fixtures.
Logical gate noise and abstract compiled circuits have separate resource counts.
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
import circuits
import evaluate_confirmation as evaluation
from models import sigmoid

PROTOCOL=s.ROOT.parent/'governance/LOCAL_READINESS_PROTOCOL.json'
METHODS=('q2_kmeans','qscalar_kmeans','qmulti_kmeans','qfrozen_kmeans')
MOMENTS=('X0','X1','Z0','Z1','Z0Z1')
I=np.eye(2);X=np.array([[0.,1.],[1.,0.]]);Z=np.diag([1.,-1.])
OPERATORS=(np.kron(X,I),np.kron(I,X),np.kron(Z,I),np.kron(I,Z),np.kron(Z,Z))
SIGNS=np.array([[1.,1.,-1.,-1.],[1.,-1.,1.,-1.],[1.,-1.,-1.,1.]])


def matrix_ry(angle):
    c,t=np.cos(angle/2),np.sin(angle/2);return np.array([[c,-t],[t,c]])


def classification_pair(actual,reference):
    band=32*np.finfo(np.float64).eps;different=(actual>=.5)!=(reference>=.5)
    inside=abs(actual-.5)<=band and abs(reference-.5)<=band
    s.require(not different or inside,'Readiness class disagreement outside numerical band')
    return {'canonical_prediction':int(actual>=.5),'reference_prediction':int(reference>=.5),
            'class_disagreement':bool(different),'canonical_near_band':bool(abs(actual-.5)<=band),
            'reference_near_band':bool(abs(reference-.5)<=band),'band_half_width':float(band)}


def build_core(x,bank):
    """Logical q0 is wire1; Operator/state/count order is |q0 q1>."""
    x=np.asarray(x);bank=np.asarray(bank)
    s.require(x.shape==(2,) and bank.shape==(2,2,2) and np.isfinite(x).all() and np.isfinite(bank).all(),'Invalid circuit input')
    qc=QuantumCircuit(2)
    for layer in range(2):
        for logical in range(2):
            wire=1-logical;qc.ry(float(np.pi*x[logical]),wire)
            qc.ry(float(bank[layer,logical,0]),wire);qc.rz(float(bank[layer,logical,1]),wire)
        qc.cx(1,0)
    return qc


def measurement_circuit(core,setting):
    qc=core.copy()
    if setting=='XX':
        qc.ry(float(-np.pi/2),1);qc.ry(float(-np.pi/2),0)
    elif setting=='legacy':qc.ry(float(np.pi/2),1)
    elif setting!='ZZ':raise ValueError('Unknown measurement setting')
    return qc


def phase_error(a,b):
    a,b=np.asarray(a),np.asarray(b);overlap=np.vdot(b.ravel(),a.ravel());phase=overlap/abs(overlap) if abs(overlap)>0 else 1.
    return float(np.max(abs(a-phase*b)))


def valid_joint(probability):
    a=np.asarray(probability,dtype=float)
    s.require(a.shape==(4,) and np.isfinite(a).all() and np.min(a)>=-2e-12 and abs(a.sum()-1)<=2e-12,'Invalid joint distribution')
    a=np.clip(a,0,1);return a/a.sum()


def readout_joint(joint,rate):
    transition=np.array([[1-rate,rate],[rate,1-rate]])
    return valid_joint(np.kron(transition,transition)@joint)


def estimate_moments(joints):
    xx=SIGNS@np.asarray(joints['XX'])
    values={'X0':float(xx[0]),'X1':float(xx[1])}
    if 'ZZ' in joints:
        zz=SIGNS@np.asarray(joints['ZZ']);values.update(Z0=float(zz[0]),Z1=float(zz[1]),Z0Z1=float(zz[2]))
    return values


def head_probability(row,moments):
    if row['method']=='q2_kmeans':return float(np.clip((1+moments['X0'])/2,0,1))
    names=('X0',) if row['method']=='qscalar_kmeans' else MOMENTS
    z=sum(row['head'][i]*moments[key] for i,key in enumerate(names))+row['head'][-1]
    return float(sigmoid(np.array([z]))[0])


def noise_model(scenario,with_readout=False):
    noise=NoiseModel();one=scenario['one_qubit_depolarizing'];two=scenario['cx_depolarizing'];r=scenario['symmetric_readout_flip']
    if one:noise.add_all_qubit_quantum_error(depolarizing_error(one,1),['ry','rz'])
    if two:noise.add_all_qubit_quantum_error(depolarizing_error(two,2),['cx'])
    if with_readout and r:noise.add_all_qubit_readout_error(ReadoutError([[1-r,r],[r,1-r]]))
    return noise


def compiled_circuit(qc,protocol):
    c=protocol['compile']
    return transpile(qc,basis_gates=c['basis_gates'],coupling_map=c['coupling_map'],initial_layout=[0,1],
                     optimization_level=c['optimization_level'],seed_transpiler=c['seed_transpiler'])


def write_qasm(output,key,qc):
    with (output/'circuits'/f'{key}.qasm').open('x',encoding='utf-8') as f:f.write(qasm2.dumps(qc)+'\n')


def fixture_group(population,seed,method,folder,validation,indices,output,protocol):
    model=s.Model(method,seed);checkpoint=folder/'selected_checkpoint.npz'
    with np.load(checkpoint,allow_pickle=False) as c:
        model.parameters[:]=c['parameters'];s.require(np.array_equal(c['core_parameters'],model.core_parameters),'Frozen core checkpoint mismatch')
    pop={k:a[indices] for k,a in validation.items()};route=model.route_for(pop);production=model.predict_population(pop)
    rows=[];cores=[];entries=[];legacy=[]
    for i,xy in enumerate(pop['x']):
        bank_id=int(route[i]);theta=model.parameters[bank_id*model.bank_width:(bank_id+1)*model.bank_width]
        bank=model.core_parameters[bank_id] if model.frozen else theta[:8].reshape(2,2,2)
        head=[] if model.legacy else (theta if model.frozen else theta[8:]).tolist()
        core=build_core(xy,bank);ref=reference_v03.unitary(xy,bank,2,beta=0);psi=ref[:,0]
        moments={name:float(np.real(np.vdot(psi,op@psi))) for name,op in zip(MOMENTS,OPERATORS)}
        produced=dict(zip(MOMENTS,circuits.moments(xy[None,:],bank,5)[0].tolist()))
        moment_error=max(abs(produced[k]-moments[k]) for k in MOMENTS)
        s.require(moment_error<=2e-12,'Full production Pauli moment mismatch')
        source_error=phase_error(Operator(core).data,ref);s.require(source_error<=2e-12,'Core unitary mismatch')
        key=f'{population}__seed{seed}__{method}__id{int(pop["ids"][i])}'
        row={'key':key,'population':population,'training_seed':seed,'method':method,'fixture_index':i,'record_id':int(pop['ids'][i]),
             'x':xy.tolist(),'bank':bank_id,'checkpoint_sha256':s.digest(checkpoint),'head':head,
             'production_probability':float(production[i]),'reference_moments':moments,'production_moments':produced,
             'maximum_production_moment_error':moment_error,'source_unitary_error':source_error,
             'core_operations':dict(core.count_ops()),'required_settings':['XX'] if model.family in ('q2','qscalar') else ['XX','ZZ'],
             'settings':{},'scenarios':{}}
        row['reference_probability']=head_probability(row,moments)
        s.require(abs(row['reference_probability']-production[i])<=2e-12,'Independent moment/head prediction mismatch')
        row['numerical_classification']=classification_pair(float(production[i]),row['reference_probability'])
        write_qasm(output,key+'__core',core)
        for setting in row['required_settings']+(['legacy'] if model.legacy else []):
            qc=measurement_circuit(core,setting);compiled=compiled_circuit(qc,protocol)
            rotation=(np.kron(matrix_ry(-np.pi/2),matrix_ry(-np.pi/2)) if setting=='XX' else
                      np.kron(matrix_ry(np.pi/2),I) if setting=='legacy' else np.eye(4))
            reference=rotation@ref;actual=Operator(qc).data;after=Operator(compiled).data
            source=phase_error(actual,reference);error=phase_error(after,reference)
            s.require(max(source,error)<=2e-12,'Measurement circuit source/compile mismatch')
            joint=valid_joint(abs(reference[:,0])**2);compiled_joint=valid_joint(abs(after[:,0])**2)
            s.require(np.max(abs(joint-compiled_joint))<=2e-12,'Compiled joint distribution mismatch')
            row['settings'][setting]={'source_unitary_error':source,'compiled_unitary_error':error,'reference_joint':joint.tolist(),
                 'logical_operations':dict(qc.count_ops()),'compiled_operations':dict(compiled.count_ops()),
                 'logical_depth':qc.depth(),'compiled_depth':compiled.depth(),'compiled_global_phase':float(compiled.global_phase)}
            for suffix,circuit in (('logical',qc),('compiled',compiled)):write_qasm(output,key+'__'+setting+'__'+suffix,circuit)
            entry={'row_index':i,'setting':setting,'circuit':qc,'compiled':compiled}
            (legacy if setting=='legacy' else entries).append(entry)
            if setting=='legacy':s.require(abs(float(joint[2:].sum())-production[i])<=2e-12,'Original legacy readout mismatch')
        rows.append(row);cores.append(core)
    return rows,cores,entries,legacy


def run_aer(circuits,scenario=None,measured=False,shots=1,seed=590103):
    sim=AerSimulator(method='density_matrix' if scenario is not None else 'statevector',
        noise_model=noise_model(scenario,measured) if scenario is not None else None,
        max_parallel_threads=1,max_parallel_experiments=1)
    result=sim.run(circuits,shots=shots,seed_simulator=seed).result();s.require(result.success,'Aer execution failed');return result


def execute_capsule(populations,seeds,base,output,protocol,watched,engineering):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);(output/'circuits').mkdir();start=time.perf_counter()
    try:
        rows=[];cores=[];entries=[];legacy=[];fixtures={};timings={};checkpoint_resources=[]
        for population in populations:
            val=s.load_population(population,'validation');indices=np.argsort(val['ids'],kind='stable')[:32];fixtures[population]=val['ids'][indices].tolist()
            for name in (f'{population}_validation.npz',f'{population}_router.json'):
                path=s.ROOT/'data'/name;watched[path]=s.digest(path)
            for seed in seeds:
                for method in METHODS:
                    folder=base/population/f'seed_{seed}'/method;commit=s.read_json(folder/'endpoint_commit.json')
                    s.require(commit['status']=='completed','Uncommitted checkpoint')
                    for name in ('selected_checkpoint.npz','result.json'):
                        path=folder/name;h=s.digest(path);s.require(h==commit['files'][name]['sha256'],'Changed checkpoint/result');watched[path]=h
                    watched[folder/'endpoint_commit.json']=s.digest(folder/'endpoint_commit.json')
                    endpoint=s.read_json(folder/'result.json')
                    checkpoint_resources.append({'population':population,'training_seed':seed,'method':method,
                        'inference':endpoint['inference'],'frozen_cache':endpoint['frozen_cache'],
                        'trainable_parameters':endpoint['parameter_count'],'fixed_core_parameters':endpoint['fixed_core_parameter_count']})
                    rr,cc,ee,ll=fixture_group(population,seed,method,folder,val,indices,output,protocol);offset=len(rows)
                    for entry in ee+ll:entry['row_index']+=offset
                    rows.extend(rr);cores.extend(cc);entries.extend(ee);legacy.extend(ll)
        # Aer pre-readout state checks all five moments even for a scalar model.
        t=time.perf_counter();jobs=[]
        for core in cores:c=core.copy();c.save_statevector();jobs.append(c)
        result=run_aer(jobs)
        for i,row in enumerate(rows):
            psi=np.asarray(result.get_statevector(i));moments={name:float(np.real(np.vdot(psi,op@psi))) for name,op in zip(MOMENTS,OPERATORS)}
            row['aer_core_moments']=moments;row['maximum_aer_moment_error']=max(abs(moments[k]-row['reference_moments'][k]) for k in MOMENTS)
            s.require(row['maximum_aer_moment_error']<=2e-12,'Aer Pauli moment mismatch')
            row['aer_core_probability']=head_probability(row,moments)
            s.require(abs(row['aer_core_probability']-row['reference_probability'])<=2e-12,'Aer moment head probability mismatch')
        timings['core_ideal_aer']=time.perf_counter()-t
        # Required settings plus the separately charged historical legacy circuit.
        all_entries=entries+legacy;t=time.perf_counter();jobs=[]
        for entry in all_entries:c=entry['compiled'].copy();c.save_statevector();jobs.append(c)
        result=run_aer(jobs)
        for j,entry in enumerate(all_entries):
            row=rows[entry['row_index']];setting=row['settings'][entry['setting']];joint=valid_joint(abs(np.asarray(result.get_statevector(j)))**2)
            setting['compiled_aer_joint']=joint.tolist();setting['compiled_aer_joint_error']=float(np.max(abs(joint-setting['reference_joint'])))
            s.require(setting['compiled_aer_joint_error']<=2e-12,'Compiled Aer joint mismatch')
        for row in rows:
            moments=estimate_moments({k:row['settings'][k]['compiled_aer_joint'] for k in row['required_settings']})
            p=head_probability(row,moments);row['compiled_aer_probability']=p
            s.require(abs(p-row['reference_probability'])<=2e-12,'Compiled Aer head probability mismatch')
            row['compiled_numerical_classification']=classification_pair(row['production_probability'],p)
        timings['compiled_ideal_aer']=time.perf_counter()-t
        for scenario in protocol['noise_scenarios']:
            t=time.perf_counter();jobs=[]
            for entry in all_entries:c=entry['circuit'].copy();c.save_density_matrix();jobs.append(c)
            result=run_aer(jobs,scenario)
            for j,entry in enumerate(all_entries):
                row=rows[entry['row_index']];rho=np.asarray(result.data(j)['density_matrix']);pre=valid_joint(np.real(np.diag(rho)))
                observed=readout_joint(pre,scenario['symmetric_readout_flip'])
                record=row['scenarios'].setdefault(scenario['name'],{'settings':{}})
                record['settings'][entry['setting']]={'premeasurement_joint':pre.tolist(),'observed_joint':observed.tolist()}
                if scenario['name']=='ideal':s.require(np.max(abs(observed-row['settings'][entry['setting']]['reference_joint']))<=2e-12,'Ideal density joint mismatch')
            for row in rows:
                record=row['scenarios'][scenario['name']];m=estimate_moments({k:record['settings'][k]['observed_joint'] for k in row['required_settings']})
                p=head_probability(row,m);record.update(observed_moments=m,observed_probability=p,
                    absolute_distortion_from_ideal=abs(p-row['reference_probability']),classification_disagreement_from_ideal=bool((p>=.5)!=(row['reference_probability']>=.5)))
                if row['method']=='q2_kmeans':
                    original=float(sum(record['settings']['legacy']['observed_joint'][2:]));record['original_legacy_probability']=original
                    s.require(abs(original-p)<=2e-12,'Original legacy versus XX marginal noise mismatch')
            timings['logical_density_'+scenario['name']]=time.perf_counter()-t
        counts={};sampled={};shot_rows=[];config=protocol['finite_shot'];t=time.perf_counter()
        for pi,population in enumerate(populations):
            for seed in seeds:
                for mi,method in enumerate(METHODS):
                    ids=[i for i,r in enumerate(rows) if (r['population'],r['training_seed'],r['method'])==(population,seed,method)]
                    s.require(len(ids)==32,'Fixture count mismatch');settings=rows[ids[0]]['required_settings']
                    for ni,scenario in enumerate(protocol['noise_scenarios']):
                        target=np.array([rows[i]['scenarios'][scenario['name']]['observed_probability'] for i in ids])
                        for shots in config['shots_per_setting']:
                            for repeat in range(config['replicates']):
                                key=f'{population}__seed{seed}__{method}__{scenario["name"]}__shots{shots}__repeat{repeat}'
                                by_setting={};sequences={}
                                for setting in settings:
                                    setting_index=('XX','ZZ').index(setting);sequence=[590101,pi,seed,mi,ni,shots,repeat,setting_index]
                                    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(sequence)))
                                    draws=np.asarray([rng.multinomial(shots,rows[i]['scenarios'][scenario['name']]['settings'][setting]['observed_joint']) for i in ids],dtype=np.int64)
                                    counts[key+'__'+setting]=draws;by_setting[setting]=draws/shots;sequences[setting]=sequence
                                q=np.array([head_probability(rows[i],estimate_moments({k:a[j] for k,a in by_setting.items()})) for j,i in enumerate(ids)])
                                sampled[key]=q;shot_rows.append({'key':key,'population':population,'training_seed':seed,'method':method,'scenario':scenario['name'],
                                    'shots_per_setting':shots,'settings':settings,'repeat_index':repeat,'seed_sequences':sequences,
                                    'record_ids':[rows[i]['record_id'] for i in ids],'total_shots':shots*32*len(settings),
                                    'mean_signed_probability_error':float(np.mean(q-target)),'mean_absolute_probability_error':float(np.mean(abs(q-target))),
                                    'classification_disagreement_from_density':float(np.mean((q>=.5)!=(target>=.5)))})
        np.savez_compressed(output/'finite_shot_counts.npz',**counts);np.savez_compressed(output/'finite_shot_probabilities.npz',**sampled)
        s.write_json(output/'finite_shot_records.json',shot_rows,True);timings['joint_multinomial_sampling']=time.perf_counter()-t
        shot_summaries=[]
        for pop in populations:
            for seed in seeds:
                for method in METHODS:
                    fixture=[r for r in rows if (r['population'],r['training_seed'],r['method'])==(pop,seed,method)]
                    for scenario in protocol['noise_scenarios']:
                        target=np.array([r['scenarios'][scenario['name']]['observed_probability'] for r in fixture])
                        for shots in config['shots_per_setting']:
                            selected=[r for r in shot_rows if (r['population'],r['training_seed'],r['method'],r['scenario'],r['shots_per_setting'])==(pop,seed,method,scenario['name'],shots)]
                            a=np.array([sampled[r['key']] for r in selected]);s.require(len(a)==5,'Five shot repeats required')
                            bias=np.mean(a,axis=0)-target;variance=np.var(a,axis=0,ddof=1)
                            shot_summaries.append({'population':pop,'training_seed':seed,'method':method,'scenario':scenario['name'],
                                'shots_per_setting':shots,'replicates':5,'fixture_ids':[r['record_id'] for r in fixture],
                                'empirical_bias_per_fixture':bias.tolist(),'sample_variance_per_fixture':variance.tolist(),
                                'mean_signed_bias':float(np.mean(bias)),'mean_absolute_bias':float(np.mean(abs(bias))),
                                'mean_sample_variance':float(np.mean(variance)),
                                'scope':'Five-repeat descriptive estimates around the same noisy density predictor; not a fitted bias correction or independent training sample.'})
        s.write_json(output/'finite_shot_summary.json',shot_summaries,True)
        smoke_entries=[entry for entry in entries if rows[entry['row_index']]['fixture_index']<8];measured=[]
        for entry in smoke_entries:
            qc=entry['circuit'].copy();qc.add_register(ClassicalRegister(2));qc.measure([0,1],[0,1]);measured.append(qc)
            write_qasm(output,rows[entry['row_index']]['key']+'__'+entry['setting']+'__measured',qc)
        smoke=[];sm=protocol['aer_measured_smoke']
        for scenario in protocol['noise_scenarios']:
            if scenario['name'] not in sm['scenarios']:continue
            t=time.perf_counter();result=run_aer(measured,scenario,True,sm['shots_per_setting'],sm['seed_simulator'])
            for j,entry in enumerate(smoke_entries):
                row=rows[entry['row_index']];raw=result.get_counts(j);c=np.array([int(raw.get(format(k,'02b'),0)) for k in range(4)])
                s.require(c.sum()==sm['shots_per_setting'],'Aer measured total mismatch');joint=np.array(row['scenarios'][scenario['name']]['settings'][entry['setting']]['observed_joint'])
                variance=sm['shots_per_setting']*joint*(1-joint);residual=[float((c[k]-sm['shots_per_setting']*joint[k])/np.sqrt(variance[k])) if variance[k]>0 else None for k in range(4)]
                smoke.append({'key':row['key'],'setting':entry['setting'],'scenario':scenario['name'],'shots':sm['shots_per_setting'],
                    'counts':c.tolist(),'count_order':['00','01','10','11'],'density_expected_joint':joint.tolist(),
                    'observed_moments':(SIGNS@(c/sm['shots_per_setting'])).tolist(),'standardized_count_residuals':residual,'seed_simulator':sm['seed_simulator']})
            timings['measured_aer_'+scenario['name']]=time.perf_counter()-t
        s.write_json(output/'measured_aer_counts.json',smoke,True)
        summaries={}
        for pop in populations:
            summaries[pop]={}
            for method in METHODS:
                rr=[r for r in rows if r['population']==pop and r['method']==method]
                summaries[pop][method]={scenario['name']:{'checkpoint_fixture_pairs':len(rr),
                    'mean_absolute_distortion':float(np.mean([r['scenarios'][scenario['name']]['absolute_distortion_from_ideal'] for r in rr])),
                    'maximum_absolute_distortion':float(max(r['scenarios'][scenario['name']]['absolute_distortion_from_ideal'] for r in rr)),
                    'classification_disagreement_fraction':float(np.mean([r['scenarios'][scenario['name']]['classification_disagreement_from_ideal'] for r in rr]))} for scenario in protocol['noise_scenarios']}
        for path,h in watched.items():s.require(s.digest(path)==h,'Bound capsule source/data/checkpoint changed')
        report={'status':'PASS','engineering':engineering,'created_utc':s.now(),'test_accessed':False,'scope':protocol['scope'],
            'matrix_and_ideal_status':'PASS','measured_smoke_status':'RECORDED_WITHOUT_STOCHASTIC_PASS_FAIL_GATE',
            'populations':list(populations),'training_seeds':list(seeds),'methods':list(METHODS),'fixture_ids':fixtures,
            'checkpoint_count':len(populations)*len(seeds)*len(METHODS),'checkpoint_fixture_pairs':len(rows),
            'required_measurement_circuits':len(entries),'additional_original_legacy_circuits':len(legacy),
            'core_ideal_aer_evaluations':len(cores),'compiled_ideal_aer_evaluations':len(all_entries),
            'production_model_forward_statevector_examples':len(rows),'additional_full_moment_statevector_examples':len(rows),
            'logical_density_evaluations':len(all_entries)*len(protocol['noise_scenarios']),
            'measured_aer_circuit_experiments':len(smoke),'actual_simulated_measurement_shots':sum(r['shots'] for r in smoke),
            'finite_shot_count_array_count':len(counts),'finite_shot_predictor_array_count':len(sampled),
            'represented_multinomial_trials':sum(r['total_shots'] for r in shot_rows),
            'maximum_core_unitary_error':max(r['source_unitary_error'] for r in rows),
            'maximum_compiled_unitary_error':max(a['compiled_unitary_error'] for r in rows for a in r['settings'].values()),
            'maximum_aer_moment_error':max(r['maximum_aer_moment_error'] for r in rows),
            'maximum_production_moment_error':max(r['maximum_production_moment_error'] for r in rows),
            'summaries':summaries,'checkpoint_resources':checkpoint_resources,'timings_seconds':timings,'elapsed_seconds':time.perf_counter()-start,
            'protocol_sha256':s.digest(PROTOCOL),'watched_input_hashes':{str(p):h for p,h in watched.items()},
            'environment':{'python':sys.version,'numpy':np.__version__,'qiskit':importlib.metadata.version('qiskit'),'qiskit_aer':importlib.metadata.version('qiskit-aer'),
                'platform':platform.platform(),'executable':sys.executable},'limits':protocol['limitations'],'noise_semantics':protocol['noise_semantics'],
            'sampling_scope':'Joint four-outcome draws in ascending fixture ID order, independently seeded by budget/replicate/setting. Repeats are nested within checkpoint, not independent trained models or shared shot-budget prefixes.',
            'cost_scope':'XX includes both q0 and q1 readout rotations even for scalar/legacy. Extra original legacy checks are separately charged. All quoted shots are simulated, no physical shots.',
            'circuits':rows}
        s.write_json(output/'report.json',report,True)
        inventory={p.relative_to(output).as_posix():{'sha256':s.digest(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()}
        s.write_json(output/'READINESS_COMMIT.json',{'status':'completed','created_utc':s.now(),'files':inventory,'engineering':engineering,'test_accessed':False},True)
        print({k:report[k] for k in ('status','engineering','checkpoint_fixture_pairs','actual_simulated_measurement_shots','finite_shot_count_array_count')})
    except BaseException as error:
        s.write_json(output/'FAILURE.json',{'status':'FAIL','error':str(error),'traceback':traceback.format_exc(),'created_utc':s.now(),'test_accessed':False},True);raise


def run(output):
    if Path(output).exists():raise FileExistsError(output)
    protocol=s.read_json(PROTOCOL);s.require(protocol['methods']==list(METHODS),'Readiness methods differ')
    s.require(np.__version__=='2.5.4','Registered NumPy required')
    watched={PROTOCOL:s.digest(PROTOCOL),Path(__file__):s.digest(__file__),s.ROOT/'data/DATA_SEAL.json':s.digest(s.ROOT/'data/DATA_SEAL.json')}
    for name,h in s.source_hashes().items():watched[s.ROOT/name]=h
    reg,lock,release,bound=evaluation.verify_guard(output_must_be_absent=False);watched.update(bound)
    populations=s.POPULATIONS['B'];seeds=s.SEEDS['B'];base=s.ROOT/'stage_B'
    s.require(protocol['populations']==list(populations) and protocol['training_seeds']==list(seeds),'Readiness scope differs')
    execute_capsule(populations,seeds,base,output,protocol,watched,False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.output)
