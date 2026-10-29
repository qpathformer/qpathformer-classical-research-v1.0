"""Independent synthetic-only snapshot density proof; no real study payloads.

This checks serialized noise mixtures and compiled QASM using NumPy matrices.
It does not invoke Qiskit/Aer or regenerate a backend from calibration files.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,traceback
import numpy as np
import readout_reference_v06 as r

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def need(x,message):
    if not x:raise RuntimeError(message)
def compare(a,b,limit=2e-12):
    error=float(np.max(abs(np.asarray(a)-np.asarray(b)),initial=0));need(np.isfinite(error) and error<=limit,'Independent numerical mismatch: '+str(error));return error

def audit(folder):
    scope=read(folder/'SYNTHETIC_SCOPE.json');need('untrained' in scope['scope'] and 'no registered' in scope['scope'],'Synthetic scope required')
    for name,h in scope['source_hashes'].items():need(sha(name)==h,'Synthetic source changed')
    capsule=folder/'capsule';commit=read(capsule/'READINESS_COMMIT.json');need(commit['status']=='completed' and commit['engineering'] is True and commit['test_accessed'] is False,'Completed synthetic capsule required')
    hashes={}
    for name,item in commit['files'].items():
        p=(capsule/name).resolve();need(p.is_relative_to(capsule.resolve()),'Payload escape')
        need(p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],'Synthetic payload changed');hashes[name]=sha(p)
    report=read(capsule/'report.json');need(report['engineering'] and report['test_accessed'] is False,'Synthetic report required')
    need(report['checkpoint_count']==2 and report['checkpoint_fixture_pairs']==64,'Expected two untrained synthetic checkpoints')
    table=read(capsule/'snapshot_channel_tables.json');noise=read(capsule/'snapshot_noise_model.json')
    with np.load(capsule/'snapshot_quantum_channels.npz',allow_pickle=False) as f:saved={k:f[k] for k in f.files}
    channels={};maxchannel=0.;readout={};channel_count=0
    for error in noise['errors']:
        if error['type']=='roerror':
            p=np.asarray(error['probabilities'],float);need(p.shape==(2,2) and np.all(p>=0) and np.max(abs(p.sum(1)-1))<2e-12,'Readout stochastic matrix invalid')
            for (q,) in error['gate_qubits']:need(q not in readout,'Duplicate readout');readout[q]=p
            continue
        s=r.reconstruct_superop(error);channel_count+=1
        for qs in error['gate_qubits']:
            for operation in error['operations']:
                rows=[a for a in table['channels'] if (a['operation'],a['physical_qubits'])==(operation,qs)]
                need(len(rows)==1,'Exported channel mapping differs');maxchannel=max(maxchannel,compare(s,saved[rows[0]['array_key']]))
                identity=(operation,tuple(qs));need(identity not in channels,'Duplicate native channel');channels[identity]=s
    need(len(channels)==len(table['channels']),'Channel inventory differs')
    for q,p in readout.items():compare(p,table['readout_matrices'][str(q)],0.)
    maxideal=maxnative=maxmild=maxhead=maxmoment=0.;nsettings=0
    for row in report['circuits']:
        checkpoint=folder/'generated_checkpoints'/row['population']/f'seed_{row["training_seed"]}'/row['method']/'selected_checkpoint.npz'
        need(sha(checkpoint)==row['checkpoint_sha256'],'Synthetic checkpoint identity differs')
        with np.load(checkpoint,allow_pickle=False) as f:parameters=f['parameters']
        width=10 if row['method']=='qscalar_kmeans' else 14;theta=parameters[row['bank']*width:(row['bank']+1)*width];core=theta[:8].reshape(2,2,2)
        compare(theta[8:],row['head'],0.);idealrho=r.core_density(row['x'],core);mom=r.moments(idealrho)
        for field in ('reference_moments','production_moments','aer_core_moments'):maxmoment=max(maxmoment,compare(mom,[row[field][k] for k in ('X0','X1','Z0','Z1','Z0Z1')]))
        idealp=r.apply_head(row['method'],theta,mom)[0];maxhead=max(maxhead,compare(idealp,row['production_probability']))
        predictions={name:{} for name in ('ideal','illustrative_mild','archived_manila')}
        for setting in row['required_settings']:
            operations=r.parse_native_qasm((capsule/'circuits'/f'{row["key"]}__{setting}__compiled.qasm').read_text())
            idealnative=r.native_density(operations);native=r.native_density(operations,channels)
            idealjoint=np.diag(idealnative).real;nativejoint=np.diag(native).real
            idealjoint=np.maximum(idealjoint,0);idealjoint/=idealjoint.sum();nativejoint=np.maximum(nativejoint,0);nativejoint/=nativejoint.sum()
            expectedideal=r.setting_distribution(idealrho,setting)
            maxideal=max(maxideal,compare(idealjoint,expectedideal),compare(idealjoint,row['settings'][setting]['compiled_aer_joint']))
            maxnative=max(maxnative,compare(nativejoint,row['scenarios']['archived_manila']['settings'][setting]['premeasurement_joint']))
            observed=r.asymmetric_readout(nativejoint,readout);maxnative=max(maxnative,compare(observed,row['scenarios']['archived_manila']['settings'][setting]['observed_joint']))
            mildrho=r.core_density(row['x'],core,.001,.01);mild=r.setting_distribution(mildrho,setting,.001,.01)
            maxmild=max(maxmild,compare(mild,row['scenarios']['illustrative_mild']['settings'][setting]['observed_joint']))
            predictions['ideal'][setting]=idealjoint;predictions['archived_manila'][setting]=observed;predictions['illustrative_mild'][setting]=mild;nsettings+=1
        for name,joints in predictions.items():
            moments=r.grouped_moments(joints['XX'],joints.get('ZZ',np.full(4,.25)))
            p=r.apply_head(row['method'],theta,moments)[0];maxhead=max(maxhead,compare(p,row['scenarios'][name]['observed_probability']))
    records=read(capsule/'finite_shot_records.json')
    with np.load(capsule/'finite_shot_counts.npz',allow_pickle=False) as f:counts={k:f[k] for k in f.files}
    with np.load(capsule/'finite_shot_probabilities.npz',allow_pickle=False) as f:probabilities={k:f[k] for k in f.files}
    checked=0;maxsample=0.
    for rec in records:
        rows=[x for x in report['circuits'] if (x['population'],x['training_seed'],x['method'])==(rec['population'],rec['training_seed'],rec['method'])]
        need([x['record_id'] for x in rows]==rec['record_ids'],'Shot fixture order differs')
        drawn={}
        for setting in rec['settings']:
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(rec['seed_sequences'][setting])))
            draws=np.array([rng.multinomial(rec['shots_per_setting'],row['scenarios'][rec['scenario']]['settings'][setting]['observed_joint']) for row in rows],dtype=np.int64)
            need(np.array_equal(draws,counts[rec['key']+'__'+setting]),'Exact seeded joint draw differs');drawn[setting]=draws/rec['shots_per_setting'];checked+=1
        values=[]
        for i,row in enumerate(rows):
            moments=r.grouped_moments(drawn['XX'][i],drawn['ZZ'][i] if 'ZZ' in drawn else np.full(4,.25))
            theta=np.r_[np.zeros(8),row['head']];values.append(r.apply_head(row['method'],theta,moments)[0])
        maxsample=max(maxsample,compare(values,probabilities[rec['key']]))
    need(checked==len(counts)==90 and len(probabilities)==len(records)==60,'Synthetic sampling count differs')
    for name,h in hashes.items():need(sha(capsule/name)==h,'Synthetic payload changed during audit')
    return {'status':'PASS_SYNTHETIC_ONLY','created_utc':datetime.now(timezone.utc).isoformat(),'scope':'Independent NumPy-only reconstruction of every serialized quantum channel mixture and all compiled native density distributions, logical mild noise, grouped moment/head calculations and exact retained canonical multinomial draws. No production, Qiskit or Aer imports; no actual study populations/checkpoints/test outcomes. Does not recreate snapshot NoiseModel.from_backend or rerun transpilation/Aer.','synthetic_root':str(folder),'synthetic_scope_sha256':sha(folder/'SYNTHETIC_SCOPE.json'),'readiness_commit_sha256':sha(capsule/'READINESS_COMMIT.json'),'report_sha256':sha(capsule/'report.json'),'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in (Path(__file__),HERE/'readout_reference_v06.py')},'serialized_quantum_errors_reconstructed':channel_count,'channel_mappings_reconstructed':len(channels),'readout_matrices_reconstructed':len(readout),'checkpoint_fixture_pairs':64,'measurement_settings_checked':nsettings,'joint_count_arrays_exact':checked,'nonlinear_predictor_arrays_checked':len(probabilities),'maximum_exported_superop_error':maxchannel,'maximum_ideal_joint_error':maxideal,'maximum_snapshot_density_readout_error':maxnative,'maximum_logical_mild_error':maxmild,'maximum_five_moment_error':maxmoment,'maximum_head_probability_error':maxhead,'maximum_finite_shot_head_error':maxsample,'actual_study_or_model_outcomes_accessed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--synthetic-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    try:result=audit(a.synthetic_root)
    except Exception:result={'status':'FAIL','traceback':traceback.format_exc()}
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='PASS_SYNTHETIC_ONLY' else 1)
