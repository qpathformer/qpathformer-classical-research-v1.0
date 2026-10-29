"""Independent replay of an explicitly generated, untrained capsule fixture only."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,traceback
import numpy as np
import readout_reference_v05 as ref
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
FIXTURE=Path(r'C:\Anthony Siljeg\Q2_v05_synthetic_readiness_fixtures\9b0cf24a-14cb-429b-98b7-eae7dca0cb88')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def need(v,m):
 if not v:raise RuntimeError(m)
def run():
 meta=read(FIXTURE/'SYNTHETIC_FIXTURE.json');seal=read(FIXTURE/'quantum/data/DATA_SEAL.json')
 need(seal['synthetic'] is True and meta['seed']==590503,'Only explicitly untrained synthetic fixture allowed')
 out=FIXTURE/'capsule';commit=read(out/'READINESS_COMMIT.json');need(commit['status']=='completed' and commit['engineering'] is True,'Synthetic capsule incomplete')
 for name,info in commit['files'].items():
  p=out/name;need(p.resolve().is_relative_to(out.resolve()) and p.stat().st_size==info['bytes'] and sha(p)==info['sha256'],'Synthetic payload changed')
 report=read(out/'report.json');protocol=read(ROOT/'governance/LOCAL_READINESS_PROTOCOL.json')
 need(report['checkpoint_count']==4 and report['checkpoint_fixture_pairs']==128 and report['populations']==['synthetic_fixture'],'Wrong synthetic scope')
 need(report['protocol_sha256']==sha(ROOT/'governance/LOCAL_READINESS_PROTOCOL.json'),'Protocol changed')
 models={};rows={};pmax=mmax=0.;settings_checked=0
 for method in protocol['methods']:
  folder=FIXTURE/'quantum/untrained_initial_states/synthetic_fixture/seed_8901'/method
  need(read(folder/'endpoint_commit.json')['synthetic_untrained'] is True,'Not an untrained checkpoint')
  with np.load(folder/'selected_checkpoint.npz',allow_pickle=False) as z:models[method]={k:z[k] for k in z.files}
 for row in report['circuits']:
  method=row['method'];model=models[method];width={'q2_kmeans':8,'qscalar_kmeans':10,'qmulti_kmeans':14,'qfrozen_kmeans':6}[method]
  theta=model['parameters'].reshape(5,width)[row['bank']];core=model['core_parameters'][row['bank']] if method=='qfrozen_kmeans' else theta[:8].reshape(2,2,2)
  ideal=ref.core_density(row['x'],core);m=ref.moments(ideal)
  mmax=max(mmax,float(abs(m-np.array([row['reference_moments'][n] for n in ('X0','X1','Z0','Z1','Z0Z1')])).max()))
  pred,_=ref.apply_head(method,theta,m);pmax=max(pmax,abs(pred-row['production_probability']))
  for scenario in protocol['noise_scenarios']:
   rho=ref.core_density(row['x'],core,scenario['one_qubit_depolarizing'],scenario['cx_depolarizing']);record=row['scenarios'][scenario['name']];joints={}
   for setting,saved in record['settings'].items():
    joint=ref.setting_distribution(rho,'legacy_q0' if setting=='legacy' else setting,scenario['one_qubit_depolarizing'],scenario['symmetric_readout_flip'])
    error=float(abs(joint-np.array(saved['observed_joint'])).max());pmax=max(pmax,error);need(error<=2e-12,'Independent density channel mismatch');settings_checked+=1;joints[setting]=joint
   fm=ref.grouped_moments(joints['XX'],joints.get('ZZ',np.ones(4)/4));prob,_=ref.apply_head(method,theta,fm)
   pmax=max(pmax,abs(prob-record['observed_probability']));need(abs(prob-record['observed_probability'])<=2e-12,'Independent noisy head mismatch')
  rows[row['key']]=(row,theta)
 need(mmax<=2e-12 and pmax<=2e-12,'Independent ideal moment/predictor mismatch')
 count_arrays=0;predictor_arrays=0
 with np.load(out/'finite_shot_counts.npz',allow_pickle=False) as counts,np.load(out/'finite_shot_probabilities.npz',allow_pickle=False) as probabilities:
  for item in read(out/'finite_shot_records.json'):
   selected=sorted([v for v in rows.values() if (v[0]['population'],v[0]['training_seed'],v[0]['method'])==(item['population'],item['training_seed'],item['method'])],key=lambda v:v[0]['record_id'])
   need([v[0]['record_id'] for v in selected]==item['record_ids'],'Shot fixture order changed')
   per_setting={}
   for setting in item['settings']:
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(item['seed_sequences'][setting])))
    expected=np.array([rng.multinomial(item['shots_per_setting'],r['scenarios'][item['scenario']]['settings'][setting]['observed_joint']) for r,_ in selected])
    saved=counts[item['key']+'__'+setting];need(np.array_equal(expected,saved),'Joint RNG draw mismatch');per_setting[setting]=saved/item['shots_per_setting'];count_arrays+=1
   recovered=[]
   for i,(row,theta) in enumerate(selected):
    mm=ref.grouped_moments(per_setting['XX'][i],per_setting['ZZ'][i] if 'ZZ' in per_setting else np.ones(4)/4)
    recovered.append(ref.apply_head(item['method'],theta,mm)[0])
   need(np.max(abs(np.asarray(recovered)-probabilities[item['key']]))<=2e-12,'Joint shot predictor mismatch');predictor_arrays+=1
  need(count_arrays==len(counts.files)==180 and predictor_arrays==len(probabilities.files)==120,'Shot-array scope differs')
 measured=read(out/'measured_aer_counts.json');need(len(measured)==96 and sum(a['shots'] for a in measured)==98304,'Synthetic actual Aer shot scope differs')
 for item in measured:
  counts=np.asarray(item['counts']);need(counts.shape==(4,) and np.all(counts>=0) and counts.sum()==item['shots'],'Measured counts invalid')
  need(item['count_order']==['00','01','10','11'],'Count bitstring order changed')
  # Producer intentionally maps logicalq0 to physicalwire1, so c1c0 already equals logical|q0q1>.
  need(np.array_equal(counts,ref.qiskit_count_vector(dict(zip(item['count_order'],map(int,counts))),logical_q0_wire=1)),'Wire map differs')
 return {'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'scope':'Independent density/Pauli/bit-flip/head/joint-count replay of an explicitly synthetic untrained fixture only. No selected engineering or confirmation checkpoint or registered data used.',
  'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in [Path(__file__),HERE/'readout_reference_v05.py',HERE/'test_readout_reference_v05.py',ROOT/'governance/LOCAL_READINESS_PROTOCOL.json']},
  'fixture_root':str(FIXTURE),'synthetic_fixture_sha256':sha(FIXTURE/'SYNTHETIC_FIXTURE.json'),'readiness_commit_sha256':sha(out/'READINESS_COMMIT.json'),
  'historical_producer_source_hashes':report['watched_input_hashes'],'checkpoints':4,'fixtures':128,'density_setting_distributions':settings_checked,
  'maximum_probability_error':pmax,'maximum_moment_error':mmax,'joint_count_arrays_exact':count_arrays,'predictor_arrays_verified':predictor_arrays,
  'measured_experiments_checked':len(measured),'actual_simulated_shots':98304,'model_test_outcomes_accessed':False,
  'limits':'Current public-gate revisions are reviewed separately; this checks immutable earlier synthetic mathematical evidence. Does not independently re-execute compiledAer/QASM or stochastic shots. Count statistics are descriptive; no stochastic pass/fail accuracy gate.'}
if __name__=='__main__':
 path=HERE/'SYNTHETIC_READINESS_INDEPENDENT_AUDIT.json'
 if path.exists():raise FileExistsError(path)
 try:r=run()
 except BaseException:r={'status':'FAIL','traceback':traceback.format_exc(),'model_test_outcomes_accessed':False}
 with path.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({k:v for k,v in r.items() if k!='historical_producer_source_hashes'},indent=2));sys.exit(0 if r['status']=='PASS' else 1)
