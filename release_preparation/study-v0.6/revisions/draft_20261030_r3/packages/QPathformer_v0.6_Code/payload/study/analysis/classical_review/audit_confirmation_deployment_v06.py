"""Released same-checkpoint coefficient/parity and recorded timing audit.

No producer imports, optimization, labels, benchmark rerun or hardware access.
The independent release gate checks all120 endpoints before any array access.
"""
import argparse,csv,hashlib,json,math,sys,traceback
from datetime import datetime,timezone
from pathlib import Path,PureWindowsPath
import numpy as np
import deployment_reference_v06 as d
import reference_v06 as model
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'analysis/independent_replay'))
from evidence_io import contained,digest,inventory,map_original_absolute,read_bound,recheck,require
from release_gate import validate_gate
REGISTRY='c03c1f46fdf5a658ac7a5aabda64a2c56990fdefaddceb30bf74d031899d8876'

def now():return datetime.now(timezone.utc).isoformat()
def timestamp(value):
    parsed=datetime.fromisoformat(value);require(parsed.tzinfo is not None,'Timezone-aware chronology required')
    return parsed.astimezone(timezone.utc)
def bind(path,h,watched):
    path=Path(path).resolve();require(str(path) not in watched or watched[str(path)]==h,'Conflicting prior evidence identity')
    require(digest(path)==h,'Bound payload changed');watched[str(path)]=h
def arrays(path,keys=None):
    with np.load(path,allow_pickle=False) as f:return {k:f[k] for k in (f.files if keys is None else keys)}
def close(actual,expected,tol=2e-12):
    a,b=np.asarray(actual),np.asarray(expected);require(a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all(),'Numeric shape/finite mismatch')
    error=float(np.max(abs(a-b),initial=0));require(error<=tol,'Numerical discrepancy: '+str(error));return error
def ah(array):return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()

def gate(root,expected_registry=REGISTRY):
    root=Path(root).resolve();q=root/'quantum'
    c=validate_gate(root,q/'EVALUATION_RELEASE.json',root/'analysis/independent_replay/ANALYSIS_READY.json')
    require(digest(q/'EVALUATION_REGISTRATION.json')==expected_registry,'Unexpected evaluation registration')
    watched=c['watched'];official=q/'confirmation_evaluation'
    inventory(official,c['commit']['files'],exclude=('EVALUATION_COMMIT.json',))
    for name,record in c['commit']['files'].items():bind(contained(official,name),record['sha256'],watched)
    folder=q/'deployment_confirmation';commit=read_bound(folder/'DEPLOYMENT_COMMIT.json',watched)
    require(commit['status']=='completed' and not (folder/'FAILURE.json').exists(),'Completed deployment required')
    inventory(folder,commit['files'],exclude=('DEPLOYMENT_COMMIT.json',))
    for name,record in commit['files'].items():bind(contained(folder,name),record['sha256'],watched)
    summary=read_bound(folder/'summary.json',watched)
    require(summary['status']=='PASS' and summary['compiled_checkpoints']==40 and summary['fast_trig_checkpoints']==40 and summary['selected_checkpoints']==120 and summary['timing_conditions']==600 and summary['timed_trials']==9000,'Full deployment scope required')
    require(summary['protocol_sha256']==digest(root/'governance/DEPLOYMENT_PROTOCOL.json') and summary['implementation_notes_sha256']==digest(root/'governance/DEPLOYMENT_IMPLEMENTATION_NOTES.json'),'Deployment protocol/memo differs')
    require(timestamp(commit['created_utc'])>=timestamp(c['commit']['completed_utc']),'Deployment predates official scoring completion')
    recorded={}
    for name,h in summary['source_hashes'].items():
        path=map_original_absolute(name,c['registration']['original_working_root'],root) if PureWindowsPath(name).is_absolute() else contained(root,name)
        bind(path,h,watched);recorded[str(path.resolve())]=h
    for name,h in watched.items():
        if not Path(name).is_relative_to(folder):require(recorded.get(name)==h,'Producer omitted bound deployment evidence: '+name)
    for pop in d.POPULATIONS:
        for split in ('validation','SEALED_test'):
            path=q/'data'/f'{pop}_{split}.npz';h=c['seal']['files'][path.name]['sha256']
            require(recorded.get(str(path.resolve()))==h,'Producer omitted sealed coordinate payload')
            bind(path,h,watched)
        path=q/'data'/f'{pop}_router.json';h=c['seal']['routers'][pop]['sha256']
        require(recorded.get(str(path.resolve()))==h,'Producer omitted sealed router');bind(path,h,watched)
    access=read_bound(folder/'ACCESS_EVENT.json',watched)
    require(access['release_sha256']==digest(q/'EVALUATION_RELEASE.json') and access['canonical_evaluation_commit_sha256']==digest(official/'EVALUATION_COMMIT.json'),'Deployment access chronology identity differs')
    c.update(folder=folder,deployment_commit=commit,summary=summary,registry_sha256=expected_registry)
    recheck(watched);return c

def coefficient_forward(x,table,route):
    # Use the independent scalar math.fsum path, including global one-bank tables.
    if len(table)==1:return d.laurent.predict_compiled(x,np.repeat(table,5,axis=0),np.zeros(len(x),dtype=np.int64))
    return d.laurent.predict_compiled(x,table,route)

def disclosed_parity(record,n):
    require(set(record)=={'maximum_probability_error','maximum_logit_error','records','class_disagreements','canonical_near_band','compiled_near_band','disagreements'},'Parity disclosure schema differs')
    require(record['records']==n and type(record['records']) is int,'Parity disclosure record count differs')
    for field,limit in (('maximum_probability_error',2e-12),('maximum_logit_error',1e-9)):
        require(math.isfinite(record[field]) and 0<=record[field]<=limit,'Parity disclosure tolerance differs')
    for field in ('class_disagreements','canonical_near_band','compiled_near_band'):
        require(type(record[field]) is int and 0<=record[field]<=n,'Parity disclosure count differs')
    require(record['class_disagreements']==len(record['disagreements'])<=min(record['canonical_near_band'],record['compiled_near_band']),'Parity disclosed differences/counts differ')
    ids=[]
    for row in record['disagreements']:
        require(set(row)=={'record_id','canonical_probability','compiled_probability'} and type(row['record_id']) is int and 0<=row['record_id']<n,'Parity disclosed record identity differs')
        p,q=row['canonical_probability'],row['compiled_probability']
        require(math.isfinite(p) and math.isfinite(q) and (p>=.5)!=(q>=.5) and abs(p-.5)<=2e-12 and abs(q-.5)<=2e-12 and abs(p-q)<=2e-12,'Parity disclosed class band differs')
        ids.append(row['record_id'])
    require(ids==sorted(set(ids)),'Parity disclosed record order differs')

def verify(c):
    root,q,folder,watched=c['study'],c['quantum'],c['folder'],c['watched']
    summary=c['summary'];conversions=read_bound(folder/'conversion.json',watched);fast=read_bound(folder/'fast_trig.json',watched)
    expected_c=[(p,s,m) for p in d.POPULATIONS for s in d.SEEDS for m in d.METHODS[:2]]
    expected_f=[(p,s,m) for p in d.POPULATIONS for s in d.SEEDS for m in ('trig_kmeans','trig_global')]
    key=lambda p,s,m:f'{p}__seed{s}__{m}'
    require([r['key'] for r in conversions]==[key(*v) for v in expected_c] and [r['key'] for r in fast]==[key(*v) for v in expected_f],'Exact conversion/repack identity order differs')
    converted={r['key']:r for r in conversions+fast};fixtures={};params={};timing_expected={};coefficient_checks=[];parity_checks=[];geometry=[]
    files={'ACCESS_EVENT.json','conversion.json','fast_trig.json','load_measurements.json','router_load_measurements.json','timing_trials.json','isolation_checks.json','timing_output_examples.npz','summary.json'}
    for pop in d.POPULATIONS:
        validation=arrays(q/'data'/f'{pop}_validation.npz',('x','ids','kmeans_route'));test=arrays(q/'data'/f'{pop}_SEALED_test.npz',('x','ids','kmeans_route'))
        # Access only input coordinates/IDs/routes. Label and latent fields are never inspected.
        validation={k:validation[k] for k in ('x','ids','kmeans_route')};test={k:test[k] for k in ('x','ids','kmeans_route')}
        policy=read_bound(q/'data'/f'{pop}_router.json',watched);centers=np.asarray(policy['centroids'])
        for popdata in (validation,test):require(np.array_equal(d.route(popdata['x'],centers),popdata['kmeans_route']),'Independent cached routing differs')
        indices=np.argsort(validation['ids'],kind='stable')[:1024];x=validation['x'][indices];route=validation['kmeans_route'][indices]
        fixture=read_bound(folder/f'{pop}_fixtures.json',watched);files.add(f'{pop}_fixtures.json')
        require(fixture['benchmark_ids']==validation['ids'][indices].tolist(),'Benchmark fixture IDs differ')
        offgrid=np.random.Generator(np.random.PCG64(np.random.SeedSequence([690621]))).uniform(-1,1,(128,2))
        close(offgrid,fixture['offgrid_coordinates'],0.);boundary=np.asarray(fixture['boundary_coordinates']);geometry.append({'population':pop,**d.verify_boundary_fixtures(centers,boundary,fixture['boundary_definitions'])})
        require(np.array_equal(d.route(boundary,centers),fixture['boundary_routes']),'Boundary routes differ')
        fixtures[pop]=(x,route)
        for seed in d.SEEDS:
            for method in d.METHODS:
                ident=pop,seed,method;name=key(*ident);ep=q/'stage_B'/pop/f'seed_{seed}'/method
                checkpoint=arrays(ep/'selected_checkpoint.npz');theta=checkpoint['parameters'];params[name]=theta
                selected=c['endpoints'][ident];require(selected['files']['selected_checkpoint.npz']['sha256']==digest(ep/'selected_checkpoint.npz'),'Selected checkpoint identity differs')
                r=None if method.endswith('_global') else route;pp,zz=model.predict_with_logits(method,theta,x,r)
                timing_expected[(name,'circuit' if method in d.METHODS[:2] else 'classical')]=(pp,zz)
                if name not in converted:continue
                item=converted[name];representation='compiled' if method in d.METHODS[:2] else 'fast_trig'
                expected_name=name+f'__{representation}.npz';require(item['compiled_file']==expected_name and item['representation']==representation,'Coefficient representation identity differs')
                require(item['checkpoint_sha256']==digest(ep/'selected_checkpoint.npz') and item['router_policy_sha256']==digest(q/'data'/f'{pop}_router.json'),'Conversion source identity differs')
                path=folder/expected_name;require(item['compiled_sha256']==digest(path),'Coefficient artifact digest differs');table_arrays=arrays(path);table=table_arrays['coefficients'];files.add(expected_name)
                if representation=='compiled':
                    require(set(table_arrays)=={'coefficients','construction_grid','construction_logits','construction_moments'},'Compiled NPZ inventory differs')
                    exact,diagnostic=d.coefficients(method,theta,table);coefficient_checks.append({'key':name,**diagnostic})
                    grid=np.stack(np.meshgrid(-1+2*np.arange(5)/5,-1+2*np.arange(5)/5,indexing='ij'),axis=-1).reshape(25,2)
                    close(table_arrays['construction_grid'],grid,0.)
                    for bank in range(5):
                        p0,z0=model.predict_with_logits(method,theta,grid,np.full(25,bank))
                        close(table_arrays['construction_logits'][bank],z0,1e-9)
                        width=10 if method=='qscalar_kmeans' else 14;core=theta[bank*width:bank*width+8].reshape(2,2,2)
                        moments=np.array([model.scalar_observables(point,core) for point in grid])
                        close(table_arrays['construction_moments'][bank],moments[:,:1 if method=='qscalar_kmeans' else 5])
                    require(item['construction_statevector_examples']==125,'Projection construction work differs')
                else:
                    require(np.array_equal(table,theta.reshape(-1,25)) and set(table_arrays)=={'coefficients'},'Fast Trig weights changed')
                    require(item['construction_statevector_examples']==0,'Repack cannot charge circuit construction')
                require(item['coefficient_bytes']==table.nbytes and item['original_parameter_bytes']==theta.nbytes and item['compiled_file_bytes']==path.stat().st_size,'Storage accounting differs')
                for field in ('compile_ns','compiled_load_ns'):require(type(item[field]) is int and item[field]>=0,'Invalid construction/load timing')
                expected_work={'records':1,'trig_feature_values':25,'core_statevector_examples':0,'logit_dot_multiplications':25,'logit_dot_additions':24,'sigmoid_evaluations':1,'coefficient_bytes':table.nbytes}
                require(all(item['analytical_inference_work_per_record'][k]==v for k,v in expected_work.items()),'Analytical inference counts differ')
                pf=arrays(folder/(name+'__parity.npz'));files.add(name+'__parity.npz');checks={}
                prediction_path=q/'confirmation_evaluation'/pop/f'seed_{seed}'/method/'predictions.csv'
                with prediction_path.open(newline='',encoding='utf-8') as f:records=list(csv.DictReader(f))
                require([int(v['record_id']) for v in records]==test['ids'].tolist(),'Canonical test record IDs differ')
                tp=np.array([float(v['probability']) for v in records]);tz=np.array([float(v['native_logit']) for v in records])
                for split,data,cp,cz in (('validation',validation,checkpoint['validation_probabilities'],checkpoint['validation_logits']),('test',test,tp,tz)):
                    rp,rz=coefficient_forward(data['x'],table,None if method.endswith('_global') else data['kmeans_route'])
                    close(rp,pf[split+'_probabilities']);close(rz,pf[split+'_logits'],1e-9)
                    checks[split]=d.parity(cp,cz,pf[split+'_probabilities'],pf[split+'_logits'],data['ids'])
                    require(checks[split]==item['checks'][split],'Canonical saved parity summary differs')
                for kind,points in (('offgrid',offgrid),('router_boundary',boundary)):
                    disclosed_parity(item['checks'][kind],len(points))
                    route2=None if method.endswith('_global') else d.route(points,centers)
                    cp,cz=model.predict_with_logits(method,theta,points,route2);rp,rz=coefficient_forward(points,table,route2)
                    checks[kind]=d.parity(cp,cz,rp,rz,np.arange(len(points)))
                require(set(item['checks'])=={'validation','test','offgrid','router_boundary','forced_offgrid_banks'} and len(item['checks']['forced_offgrid_banks'])==len(table),'Forced-bank parity inventory differs')
                for bank in range(len(table)):
                    disclosed_parity(item['checks']['forced_offgrid_banks'][bank],len(offgrid))
                    forced=None if method.endswith('_global') else np.full(len(offgrid),bank)
                    cp,cz=model.predict_with_logits(method,theta,offgrid,forced);rp,rz=coefficient_forward(offgrid,table,forced)
                    checks['forced_bank_'+str(bank)]=d.parity(cp,cz,rp,rz,np.arange(len(offgrid)))
                parity_checks.append({'key':name,'checks':checks})
                timing_expected[(name,representation)]=coefficient_forward(x,table,r)
    expected_conditions=len(d.POPULATIONS)*len(d.SEEDS)*10*3
    trials=read_bound(folder/'timing_trials.json',watched);require(len(trials)==17*expected_conditions,'Exact trial row count differs')
    expected_order=[]
    for pi,pop in enumerate(d.POPULATIONS):
        for si,seed in enumerate(d.SEEDS):
            for batch in (1,32,1024):
                for trial in range(-2,15):
                    for method in d.trial_order(pi,si,trial):
                        representations=['circuit','compiled'] if method in d.METHODS[:2] else ['classical','fast_trig'] if method in ('trig_kmeans','trig_global') else ['classical']
                        if len(representations)==2 and trial%2:representations.reverse()
                        expected_order.extend((pop,seed,method,rep,batch,trial) for rep in representations)
    require([(t['population'],t['seed'],t['method'],t['representation'],t['batch_size'],t['trial']) for t in trials]==expected_order,'Paired/counterbalanced trial order differs')
    example=arrays(folder/'timing_output_examples.npz');conditions={};timing_summary=[];expected_arrays=set();timing_errors=[]
    for row in trials:
        require(row['key']==key(row['population'],row['seed'],row['method']),'Timing key identity differs')
        conditions.setdefault((row['key'],row['representation'],row['batch_size']),[]).append(row)
    for (name,rep,batch),records in conditions.items():
        timing_summary.append(d.timing_summary(records));stem=name+f'__{rep}__batch{batch}';expected_arrays.update((stem+'__p',stem+'__z'))
        pp,zz=timing_expected[(name,rep)];expectedp,expectedz=(pp[:128],zz[:128]) if batch==1 else (pp,zz) if batch==32 else (np.tile(pp,32),np.tile(zz,32))
        p,z=example[stem+'__p'],example[stem+'__z'];require(ah(p)==records[0]['probability_sha256'] and ah(z)==records[0]['logit_sha256'],'Timed output digest differs')
        timing_errors.append({'condition':stem,'probability_error':close(p,expectedp),'logit_error':close(z,expectedz,1e-9)})
    require(set(example)==expected_arrays and len(conditions)==expected_conditions,'Timed output array inventory differs')
    require(timing_summary==summary['summaries'],'Median/quartile timing summary differs')
    loads=read_bound(folder/'load_measurements.json',watched);require([v['key'] for v in loads]==[key(p,s,m) for p in d.POPULATIONS for s in d.SEEDS for m in d.METHODS],'Checkpoint load inventory differs')
    for v in loads:
        require(type(v['load_ns']) is int and v['load_ns']>=0 and v['parameter_array_bytes']==params[v['key']].nbytes,'Checkpoint load timing/storage differs')
        pop,seedpart,method=v['key'].split('__');ep=q/'stage_B'/pop/('seed_'+seedpart[4:])/method/'selected_checkpoint.npz'
        require(v['checkpoint_file_bytes']==ep.stat().st_size and v['representation']==('circuit' if method in d.METHODS[:2] else 'classical'),'Checkpoint load representation/file bytes differ')
    routers=read_bound(folder/'router_load_measurements.json',watched);require([v['population'] for v in routers]==list(d.POPULATIONS),'Router load scope differs')
    for v in routers:require(type(v['load_ns']) is int and v['load_ns']>=0 and v['centroid_float64_bytes']==80 and v['policy_file_bytes']==(q/'data'/f'{v["population"]}_router.json').stat().st_size,'Router load storage/timing differs')
    isolation=read_bound(folder/'isolation_checks.json',watched);require(len(isolation)==3 and all(v['relevant_other_process_count']==0 and type(v['pid']) is int for v in isolation),'Three recorded process-isolation checks required')
    expected_payloads=9+len(d.POPULATIONS)+2*len(converted)
    require(set(c['deployment_commit']['files'])==files and len(files)==expected_payloads,'Exact deployment output inventory differs')
    return {'selected_checkpoints':len(params),'compiled_checkpoints':len(conversions),'fast_trig_checkpoints':len(fast),'total_representations':len(timing_expected),'coefficient_checks':coefficient_checks,'parity_checks':parity_checks,'router_boundary_checks':geometry,'timing_conditions':len(conditions),'timed_trials':15*len(conditions),'warmup_trials':2*len(conditions),'timing_output_errors':timing_errors,'payload_count':expected_payloads,'scope':'Independent same-checkpoint Laurent coefficients and scalar/vector predictions, geometry/routing, recorded timing/cost arithmetic. Timing is not rerun; process-isolation records cannot prove absence of unrelated OS work.'}

def run(root,output):
    output=Path(output).resolve();require(not output.exists(),'Preserve prior deployment audit');c=gate(root)
    own=[Path(__file__),Path(d.__file__),Path(d.laurent.__file__),Path(model.__file__)]
    for p in own:bind(p,digest(p),c['watched'])
    output.mkdir(parents=True,exist_ok=False)
    def write(name,value):
        with (output/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    write('ACCESS_EVENT.json',{'created_utc':now(),'release_id':c['release']['release_id'],'deployment_commit_sha256':digest(c['folder']/'DEPLOYMENT_COMMIT.json'),'scope':'Released input/checkpoint/canonical-output parity only; no label scoring or fitting.'})
    try:
        checks=verify(c);recheck(c['watched'])
        result={'status':'PASS','study_id':'QPATH-GENERALIZATION-v0.6','created_utc':now(),'checks':checks,'release_sha256':digest(c['quantum']/'EVALUATION_RELEASE.json'),'registration_sha256':c['registry_sha256'],'deployment_commit_sha256':digest(c['folder']/'DEPLOYMENT_COMMIT.json'),'official_evaluation_commit_sha256':digest(c['quantum']/'confirmation_evaluation/EVALUATION_COMMIT.json'),'auditor_sources':{p.relative_to(ROOT).as_posix():digest(p) for p in own},'watched_input_hashes':c['watched'],'labels_scored':False,'training_or_benchmark_executed':False}
        write('summary.json',result);recheck(c['watched'])
        write('AUDIT_COMMIT.json',{'status':'completed','created_utc':now(),'deployment_commit_sha256':result['deployment_commit_sha256'],'files':{p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in output.iterdir() if p.is_file()}});return result
    except BaseException as error:
        write('FAILURE.json',{'status':'FAIL','created_utc':now(),'error':str(error),'traceback':traceback.format_exc()});raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    require(args.output.resolve().parent==HERE,'Output must be new child of classical_review');result=run(ROOT,args.output)
    print(json.dumps({'status':result['status'],'output':str(args.output)}))
