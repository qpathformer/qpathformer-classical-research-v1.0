"""Independent density-channel reconstruction of the engineering capsule only.

No Aer/provider/production import and no confirmation payload access. Checks
logical per-gate noise without collapsing adjacent feature/train rotations.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math
import numpy as np
import reference_v04 as ref

ROOT=Path(__file__).resolve().parents[2];Q=ROOT/'quantum';HERE=Path(__file__).resolve().parent
def need(v,m):
    if not v:raise RuntimeError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}

def depolarize(rho,p,qubit):
    if qubit is None:return (1-p)*rho+p*np.eye(4)/4
    tensor=rho.reshape(2,2,2,2)
    reduced=np.trace(tensor,axis1=qubit,axis2=qubit+2)
    mixed=np.kron(np.eye(2)/2,reduced) if qubit==0 else np.kron(reduced,np.eye(2)/2)
    return (1-p)*rho+p*mixed

def density_probability(x,theta,one,two):
    rho=np.zeros((4,4),complex);rho[0,0]=1
    def apply_single(matrix,qubit):
        nonlocal rho
        u=np.kron(matrix,np.eye(2)) if qubit==0 else np.kron(np.eye(2),matrix)
        rho=depolarize(u@rho@u.conj().T,one,qubit)
    for layer in range(2):
        for qubit in (0,1):
            apply_single(ref.ry(math.pi*float(x[qubit])),qubit)
            apply_single(ref.ry(theta[layer,qubit,0]),qubit)
            apply_single(ref.rz(theta[layer,qubit,1]),qubit)
        rho=depolarize(ref.CX@rho@ref.CX.conj().T,two,None)
    apply_single(ref.ry(math.pi/2),0)
    need(abs(np.trace(rho)-1)<2e-12 and np.max(abs(rho-rho.conj().T))<2e-12,'Invalid reconstructed density')
    return float((rho[2,2]+rho[3,3]).real)

def channel_fixtures():
    rng=np.random.default_rng(491021);state=rng.normal(size=4)+1j*rng.normal(size=4);state/=np.linalg.norm(state);rho=np.outer(state,state.conj())
    paulis=[np.array([[0,1],[1,0]],complex),np.array([[0,-1j],[1j,0]]),np.diag([1,-1])]
    maximum=0.
    for qubit in (0,1):
        for p in (0.,.001,.3,1.):
            expected=(1-3*p/4)*rho
            for pauli in paulis:
                u=np.kron(pauli,np.eye(2)) if qubit==0 else np.kron(np.eye(2),pauli)
                expected+=p/4*u@rho@u.conj().T
            error=float(np.max(abs(depolarize(rho,p,qubit)-expected)));maximum=max(maximum,error);need(error<2e-15,'Depolarizing parameter convention differs')
    need(np.max(abs(depolarize(rho,1.,None)-np.eye(4)/4))<1e-15,'Two-qubit full depolarization differs')
    return maximum

def audit():
    folder=Q/'local_readiness_engineering_v01';commit_path=folder/'READINESS_COMMIT.json';commit=read(commit_path)
    need(commit['status']=='completed' and commit['engineering'] is True and commit['test_accessed'] is False,'Only completed engineering capsule allowed')
    need(set(commit['files'])=={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and p.name!='READINESS_COMMIT.json'},'Engineering capsule inventory differs')
    for name,meta in commit['files'].items():
        p=folder/name;need(p.stat().st_size==meta['bytes'] and sha(p)==meta['sha256'],'Engineering capsule changed')
    report=read(folder/'report.json');protocol=read(ROOT/'governance/LOCAL_READINESS_PROTOCOL.json')
    need(report['engineering'] is True and report['populations']==['engineering_circle','engineering_ellipse'] and report['training_seeds']==[9701],'Unexpected engineering scope')
    need(report['protocol_sha256']==sha(ROOT/'governance/LOCAL_READINESS_PROTOCOL.json'),'Readiness protocol differs')
    # Engineering CLI ran from quantum/, so its relative checkpoint provenance
    # is resolved there; absolute recorded sources remain checked as recorded.
    watched={(Path(p) if Path(p).is_absolute() else Q/p):h for p,h in report['watched_input_hashes'].items()}
    watched.update({commit_path:sha(commit_path),folder/'report.json':sha(folder/'report.json'),Path(__file__):sha(__file__),HERE/'reference_v04.py':sha(HERE/'reference_v04.py')})
    for p,h in watched.items():need(sha(p)==h,'Bound capsule source/evidence differs')
    channel_error=channel_fixtures();checkpoints={};maximum=0.;maximum_observed=0.;density_checks=0
    rows=report['circuits'];need(len(rows)==192,'Engineering fixture count differs')
    for row in rows:
        key=(row['population'],row['training_seed'],row['method'])
        if key not in checkpoints:
            path=Q/'engineering_pilot_v01'/key[0]/f'seed_{key[1]}'/key[2]/'selected_checkpoint.npz'
            need(sha(path)==row['checkpoint_sha256'],'Engineering checkpoint differs');checkpoints[key]=load(path)['parameters']
        theta=checkpoints[key][row['bank']*8:(row['bank']+1)*8].reshape(2,2,2)
        need(row['logical_operations']=={'ry':9,'rz':4,'cx':2},'Logical noise gate count differs')
        ideal=ref.scalar_circuit(row['x'],theta);need(abs(ideal-row['reference_probability'])<=2e-12,'Independent scalar ideal differs')
        for scenario in protocol['noise_scenarios']:
            p=density_probability(row['x'],theta,scenario['one_qubit_depolarizing'],scenario['cx_depolarizing'])
            saved=row['scenarios'][scenario['name']];error=abs(p-saved['premeasurement_probability']);maximum=max(maximum,error)
            flip=scenario['symmetric_readout_flip'];q=flip+(1-2*flip)*p
            oe=abs(q-saved['observed_probability']);maximum_observed=max(maximum_observed,oe)
            need(error<=2e-12 and oe<=2e-12,'Aer density/readout differs from independent channels');density_checks+=1
    counts=load(folder/'finite_shot_counts.npz');probabilities=load(folder/'finite_shot_probabilities.npz');records=read(folder/'finite_shot_records.json')
    need(len(counts)==len(probabilities)==len(records)==180 and set(counts)==set(probabilities)=={r['key'] for r in records},'Binomial array inventory differs')
    represented=0
    for row in records:
        pi=report['populations'].index(row['population']);mi=report['methods'].index(row['method']);ni=[x['name'] for x in protocol['noise_scenarios']].index(row['scenario'])
        sequence=[490101,pi,row['training_seed'],mi,ni,row['shots'],row['repeat_index']]
        need(row['seed_sequence']==sequence,'Shot RNG sequence differs')
        group=[r for r in rows if (r['population'],r['training_seed'],r['method'])==(row['population'],row['training_seed'],row['method'])]
        need([r['record_id'] for r in group]==row['record_ids'],'Binomial record identity differs')
        # Exact sampling replay uses the saved hash-bound probability after its independent channel check.
        p=np.array([r['scenarios'][row['scenario']]['observed_probability'] for r in group])
        expected=np.random.Generator(np.random.PCG64(np.random.SeedSequence(sequence))).binomial(row['shots'],p)
        need(np.array_equal(expected,counts[row['key']]) and np.array_equal(expected/row['shots'],probabilities[row['key']]),'Exact binomial replay differs')
        represented+=row['shots']*len(p)
    measured=read(folder/'measured_aer_counts.json');need(len(measured)==96,'Measured smoke inventory differs')
    for row in measured:
        n0,n1=row['counts']['0'],row['counts']['1'];need(n0+n1==1024==row['shots'],'Actual Aer count sum differs')
        p=row['density_expected_probability'];variance=1024*p*(1-p)
        if variance>0:need(abs(row['standardized_count_residual']-(n1-1024*p)/math.sqrt(variance))<=2e-12,'Measured residual arithmetic differs')
    need(report['circuit_count']==192 and report['matrix_comparisons']==384 and report['density_scenario_circuit_evaluations']==576 and report['actual_simulated_measurement_shots']==98304,'Capsule work totals differ')
    need(report['represented_binomial_trials']==represented,'Represented binomial trial count differs')
    for p,h in watched.items():need(sha(p)==h,'Watched evidence changed during independent review')
    return {'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'engineering_only':True,
       'engineering_capsule_commit_sha256':sha(commit_path),'protocol_sha256':report['protocol_sha256'],
       'independent_density_source_sha256':sha(__file__),'independent_gate_reference_sha256':sha(HERE/'reference_v04.py'),
       'pauli_vs_partial_trace_channel_fixture_maximum_error':channel_error,
       'logical_circuits':len(rows),'independent_density_scenario_comparisons':density_checks,
       'maximum_premeasurement_probability_error':maximum,'maximum_observed_probability_error':maximum_observed,
       'exact_binomial_arrays_reproduced':len(records),'represented_binomial_trials':represented,
       'actual_Aer_shots_recorded':98304,'measured_count_residuals_checked':96,
       'scope':'Independent NumPy density matrices apply depolarizing_error(p) semantics after each of13logical RY/RZ gates and2CX gates, plus analytic readout. Exact binomial replay uses verified saved probabilities. No actual Aer count resimulation, no hardware/calibration claim, no test model outcomes accessed.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    need(not args.output.exists(),'Preserve prior audit');result=audit()
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
