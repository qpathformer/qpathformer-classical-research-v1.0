"""Root-gated four clean-directory retrains; no original checkpoints copied."""
import os,sys
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deployment'))
import argparse,subprocess,shutil,time,hashlib,traceback
import numpy as np
import support as s
from compiler import original_raw
from compare import compare
def sources():return {**s.sources(),**{'analysis/reproduction/'+n:s.sha(s.ROOT/'analysis/reproduction'/n) for n in ('run.py','worker.py','compare.py','tests/test_reproduction.py')}}
def targets(protocol,jobs):
    answer=[]
    for item in protocol['fits']:
        matches=[j for j in jobs if all(j[k]==v for k,v in item.items())];s.require(len(matches)==1,'Reproduction target not unique');answer.append(matches[0])
    s.require(len(answer)==4 and len({j['run_id'] for j in answer})==4,'Exactly four targets');return answer
def copied(source,dest,records):
    dest.parent.mkdir(parents=True,exist_ok=True);s.require(not dest.exists(),'Clean destination exists');shutil.copyfile(source,dest);s.require(s.sha(source)==s.sha(dest),'Clean input copy differs');records.append({'source':s.binding(source),'clean':s.binding(dest)})
def record_child_closure(process,metadata,output):
    import process_identity
    row=s.read(metadata);expected=row['process_identity'];s.require(process.returncode is not None,'Child wait has not finished')
    if expected['pid']==process.pid:observed=None;basis='Popen native child handle completed'
    else:
        started=time.monotonic();observed=process_identity.identity(expected['pid'])
        while observed==expected:
            s.require(time.monotonic()-started<10,'Registered scientific child still live after bootstrap exit');time.sleep(.05);observed=process_identity.identity(expected['pid'])
        s.require(observed is None or observed['creation_token']!=expected['creation_token'],'Registered native identity still live');basis='Exact registered native PID/creation token absent or replaced'
    s.write(output,{'expected':expected,'observed':observed,'same_live_identity':False,'basis':basis,'metadata':s.binding(metadata),'child_exit_code':process.returncode,'utc':s.now()})
def run(authorization,output):
    import durable,resource_probe
    from models import Model
    output=Path(output).resolve()
    with durable.auxiliary_lease(s.ROOT,'reproduction'):
        release,verified,env=s.gate(authorization,output,'reproduction',sources());protocol=s.read(s.ROOT/'governance/REPRODUCTION_PROTOCOL.json');jobs=targets(protocol,verified['jobs']);auth=s.verify(release['training_authorization']);freeze=s.read(auth)
        s.require(freeze['schema']=='qpath-v09-stage-authorization-1' and freeze['stage']=='B' and freeze['review_status']=='approved_by_root','Original B authorization required');s.require(freeze['data_seal_sha256']==s.sha(s.ROOT/'quantum/data/DATA_SEAL.json'),'Data seal changed');s.require(freeze['scientific_source_hashes']==verified['scientific_source_hashes'],'Training source differs')
        attempt=s.claim('reproduction',authorization,output,release);output.mkdir();start=time.perf_counter();cpu=time.process_time();clean=output/'clean_source_data';clean.mkdir();copies=[]
        try:
            for name,h in freeze['scientific_source_hashes'].items():
                source=s.ROOT/'quantum'/name;s.require(s.sha(source)==h,'Frozen source changed');copied(source,clean/'quantum'/name,copies)
            for name in ('STUDY_PLAN.json','RUN_MATRIX.json'):copied(s.ROOT/'governance'/name,clean/'governance'/name,copies)
            copied(auth,clean/'governance/STAGE_B_FREEZE.json',copies)
            for source in (s.ROOT/'quantum/data').iterdir():
                s.require(source.is_file() and source.suffix in ('.json','.npz'),'Unexpected data payload');copied(source,clean/'quantum/data'/source.name,copies)
            s.require(not list(clean.rglob('*checkpoint*')),'Original checkpoint copied into clean root')
            s.write(output/'CLEAN_INPUT_REBUILD.json',{'copies':copies,'checkpoints_copied':False,'scope':'Exact hash-verified frozen source/data rebuild; train starts fresh for each registered recipe.'});records=[]
            for job in jobs:
                key=hashlib.sha256(job['run_id'].encode()).hexdigest()[:24];destination=clean/'endpoints'/key;trainer_args=[str(clean/'quantum/study.py'),'--job-id',job['run_id'],'--authorization',str(clean/'governance/STAGE_B_FREEZE.json'),'--output',str(destination)];request=output/(key+'_REQUEST.json');s.write(request,{'metadata':str(output/(key+'_PROCESS.json')),'trainer_arguments':trainer_args});command=[env['interpreter'],'-B','-X','utf8',str(Path(__file__).with_name('worker.py')),'--request',str(request)]
                with (output/(key+'_stdout.log')).open('x') as out,(output/(key+'_stderr.log')).open('x') as err:
                    process=subprocess.Popen(command,cwd=clean,stdout=out,stderr=err,shell=False,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    s.write(output/(key+'_BOOTSTRAP.json'),{'pid':process.pid,'command':command,'utc':s.now(),'process_role':'candidate PID; actual native identity recorded by child before training'})
                    try:code=process.wait(timeout=7230)
                    except subprocess.TimeoutExpired:
                        process.terminate();process.wait(timeout=30);raise RuntimeError('Reproduction fit exceeded original7200-second bound; partial evidence preserved')
                s.require(code==0,'Clean training failed; preserve evidence');record_child_closure(process,output/(key+'_PROCESS.json'),output/(key+'_PROCESS_CLOSED.json'));original,_=s.endpoint(job,verified);comparison=compare(original,destination)
                model,policy,_=s.load_model(job,verified);other=Model(job['arm'],job['training_seed_id'],{k:int(v['uint128_decimal']) for k,v in job['paired_streams'].items()},policy)
                with np.load(destination/'selected_checkpoint.npz',allow_pickle=False) as f:other.parameters[:]=f['parameters']
                predictions={}
                for split in ('validation','test'):
                    data=s.population(job['population_id'],split,verified['seal']);raw=data.get('raw_x',data['x']);p,z=original_raw(model,raw,policy);rp,rz=original_raw(other,raw,policy);delta=float(abs(p-rp).max());s.require(delta<=1e-12 and np.array_equal(p>=.5,rp>=.5),'Reproduced pipeline differs')
                    with (output/(key+'_'+split+'_predictions.npz')).open('xb') as f:np.savez(f,ids=data['ids'],original_probability=p,reproduced_probability=rp,original_logits=z,reproduced_logits=rz)
                    predictions[split]={'n':len(p),'max_probability_error':delta,'changed_classes':0}
                record={'job':job,'comparison':comparison,'predictions':predictions,'original_endpoint_commit':s.binding(original/'endpoint_commit.json'),'reproduced_endpoint_commit':s.binding(destination/'endpoint_commit.json')};records.append(record);s.write(output/(key+'_COMPARISON.json'),record);print(s.json.dumps({'reproduced':len(records),'required':4,'job_id':job['run_id']}),flush=True)
            summary={'fits':4,'records':records,'environment':env,'wall_seconds':time.perf_counter()-start,'coordinator_cpu_seconds':time.process_time()-cpu,'resources':resource_probe.process_resources(),'attempt':attempt,'training_process_cpu_seconds':sum(s.read(Path(x['reproduced_endpoint_commit']['path']).parent/'result.json')['training_process_cpu_seconds'] for x in records),'independent_reproduction_audit_required':True};s.write(output/'REPRODUCTION_SUMMARY.json',summary);s.recheck(authorization,release,verified,sources());return s.commit(output,'reproduction',authorization,summary)
        except BaseException as e:s.write(output/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'partial_artifacts_preserved':True});raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--authorization',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(s.json.dumps(run(a.authorization,a.output)))
