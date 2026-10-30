"""Hash-bound post-confirmation gate for conversion, timing and reproduction."""
import os,sys,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2]
for p in ('analysis/author','execution','quantum'):sys.path.insert(0,str(ROOT/p))
FILES=('compiler.py','support.py','producer.py','timing.py','tests/test_deployment.py')
def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def binding(p):
    p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def require(ok,why):
    if not ok:raise RuntimeError(why)
def verify(b):
    p=Path(b['path']).resolve();require(p.is_relative_to(ROOT) and binding(p)==b,'Changed bound evidence: '+str(p));return p
def write(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def sources():return {'analysis/deployment/'+n:sha(ROOT/'analysis/deployment'/n) for n in FILES}
def gate(authorization,output,phase,expected_sources):
    from release_gate_v09 import verify_completed_evaluation
    output=Path(output).resolve();r=read(authorization)
    import process_identity
    attempt_dir=ROOT/'analysis/derived_attempts'
    if attempt_dir.exists():
        for previous in attempt_dir.glob('*.json'):
            prior=read(previous)
            for child in Path(prior['output']).glob('*_PROCESS.json'):
                require(not process_identity.alive(read(child)['process_identity']),'A retained derived scientific child is still live')
    require(output.is_relative_to(ROOT/'analysis') and not output.exists(),'New root-local derived output required')
    require(r.get('schema')=='qpath-v09-derived-release-1' and r.get('review_status')=='approved_by_root' and r.get('phase')==phase,'Explicit root derived release required')
    require(Path(r['output']).resolve()==output and r.get('test_access_authorized') is True,'Root-bound output/test release required')
    require(r.get('required_blas_threads')==1 and r.get('max_parallel_tasks')==1,'Serial BLAS1 required')
    require(r['source_sha256']==expected_sources,'Derived source changed')
    for name,h in expected_sources.items():require(sha(ROOT/name)==h,'Changed derived source')
    protocol_names=('DEPLOYMENT_PROTOCOL.json','REPRODUCTION_PROTOCOL.json','RUN_MATRIX.json')
    require(set(r['protocols'])==set(protocol_names),'Complete derivative protocol inventory required')
    for name,b in r['protocols'].items():require(verify(b)==ROOT/'governance'/name,'Wrong protocol')
    verified=verify_completed_evaluation(ROOT,verify(r['evaluation_release']),r['evaluation_commit'])
    score=read(verify(r['independent_score_replay']));verify_score_replay(score,r['evaluation_commit'])
    import resource_probe
    env=resource_probe.inspect();expected=read(verify(r['runtime_environment']))
    for key in ('python','interpreter','numpy_version','openblas_dll_sha256','openblas_config','effective_blas_threads'):require(env[key]==expected[key],'Runtime changed: '+key)
    require(env['effective_blas_threads']==1,'Effective BLAS threads not1')
    return r,verified,env
def verify_score_replay(score,evaluation_commit):
    require(score.get('status')=='PASS' and score.get('verified_endpoints')==636 and score.get('schema') in ('qpath-v09-independent-analysis-1','qpath-v09-independent-analysis-commit-1'),'Independent score replay incomplete')
    require(score.get('author_evaluation_commit')==evaluation_commit,'Score replay must bind exact official evaluation commit')
    if 'evaluation_commit' in score:require(score['evaluation_commit']==evaluation_commit,'Conflicting legacy evaluation commit alias')
def endpoint(job,verified):
    entry=verified['endpoints'][job['run_id']];b=entry['commit'];p=verify(b);c=read(p)
    require(c['job_id']==job['run_id'] and c['stage']=='B' and c['test_accessed'] is False,'Endpoint identity differs')
    for n,item in c['files'].items():
        f=(p.parent/n).resolve();require(f.is_relative_to(p.parent) and sha(f)==item['sha256'] and f.stat().st_size==item['bytes'],'Endpoint payload changed')
    return p.parent,b
def load_model(job,verified):
    import numpy as np
    from models import Model
    p,b=endpoint(job,verified);policy_path=ROOT/'quantum/data'/f"{job['population_id']}_router.json"
    require(sha(policy_path)==verified['seal']['routers'][job['population_id']]['sha256'],'Frozen router policy changed');policy=read(policy_path)
    streams={k:int(v['uint128_decimal']) for k,v in job['paired_streams'].items()};model=Model(job['arm'],job['training_seed_id'],streams,policy)
    with np.load(p/'selected_checkpoint.npz',allow_pickle=False) as f:parameters=f['parameters']
    require(parameters.shape==model.parameters.shape and np.isfinite(parameters).all(),'Invalid selected checkpoint');model.parameters[:]=parameters
    return model,policy,b
def population(name,split,seal):
    import numpy as np
    filename=f"{name}_{'SEALED_test' if split=='test' else split}.npz";p=ROOT/'quantum/data'/filename
    require(sha(p)==seal['files'][filename]['sha256'],'Data payload changed')
    with np.load(p,allow_pickle=False) as f:return {k:f[k] for k in f.files}
def claim(phase,authorization,output,release):
    import process_identity
    folder=ROOT/'analysis/derived_attempts';folder.mkdir(exist_ok=True);prefix=phase.replace('/','_');previous=sorted(folder.glob(prefix+'_*.json'))
    for p in previous:
        item=read(p);require(not process_identity.alive(item['process_identity']),'Prior derived worker still live');require(not (Path(item['output'])/'DERIVED_COMMIT.json').exists(),'Completed derivative must not be duplicated')
    if previous:require(release.get('recovery',{}).get('review_status')=='approved_by_root' and release['recovery'].get('prior_attempts')==[binding(p) for p in previous],'Preserved failure needs exact root recovery')
    p=folder/(prefix+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json');write(p,{'phase':phase,'utc':now(),'process_identity':process_identity.identity(),'authorization':binding(authorization),'output':str(output),'automatic_retry':False});return binding(p)
def commit(output,phase,authorization,summary):
    output=Path(output);files={p.relative_to(output).as_posix():binding(p) for p in output.rglob('*') if p.is_file()}
    value={'schema':'qpath-v09-derived-commit-1','status':'PASS','phase':phase,'utc':now(),'authorization':binding(authorization),'files':files,'summary':summary};write(output/'DERIVED_COMMIT.json',value);return binding(output/'DERIVED_COMMIT.json')
def recheck(authorization,release,verified,expected_sources):
    require(read(authorization)==release,'Derived release changed during execution')
    require(expected_sources==release['source_sha256'],'Root-bound derivative source changed')
    for name,h in expected_sources.items():require(sha(ROOT/name)==h,'Derived source changed during execution')
    for b in release['protocols'].values():verify(b)
    for key in ('evaluation_release','evaluation_commit','independent_score_replay','runtime_environment'):verify(release[key])
    for name,h in verified['release']['evaluator_sources'].items():require(sha(ROOT/name)==h,'Evaluation gate source changed')
    for name,h in verified['scientific_source_hashes'].items():require(sha(ROOT/'quantum'/name)==h,'Frozen scientific source changed during derivative')
    seal_path=verify(verified['release']['protocols']['data_seal']);seal=read(seal_path)
    for name,item in seal['files'].items():require(sha(ROOT/'quantum/data'/name)==item['sha256'],'Data changed during derivative')
    for item in seal['routers'].values():require(sha(ROOT/'quantum/data'/item['file'])==item['sha256'],'Router changed during derivative')
    for entry in verified['endpoints'].values():verify(entry['commit']);verify(entry['selected_checkpoint'])
def verify_derived(b,phase):
    p=verify(b);c=read(p);require(c['schema']=='qpath-v09-derived-commit-1' and c['status']=='PASS' and c['phase']==phase,'Wrong completed derivative')
    for name,item in c['files'].items():require(verify(item)==(p.parent/name).resolve(),'Derived payload path differs')
    require({q.relative_to(p.parent).as_posix() for q in p.parent.rglob('*') if q.is_file()}==set(c['files'])|{'DERIVED_COMMIT.json'},'Uncommitted derivative files');return p.parent,c
