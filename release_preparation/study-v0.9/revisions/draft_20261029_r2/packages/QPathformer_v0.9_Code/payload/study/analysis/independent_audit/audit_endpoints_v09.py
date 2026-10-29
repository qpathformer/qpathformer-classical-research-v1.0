"""Independent endpoint replay. Never imports the producer numerical code.

Official entry requires a hash-bound root audit release and complete stage.
Only train/validation arrays are opened. Test payloads/outcomes are not read.
"""
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[_key]='1'
import argparse,csv,hashlib,json,sqlite3,sys,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import reference_v09 as ref

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
COUNTS={'engineering':48,'A':72,'B':636}
TOLERANCES={'probability_absolute':2e-12,'logit_absolute':1e-9,'gradient_absolute':1e-9,
            'adam_parameter_absolute':1e-8,'metric_absolute':2e-12,'native_loss_absolute':1e-8,
            'threshold_band':32*np.finfo(np.float64).eps}
need=ref.need
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def ah(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def binding(p):
    p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def check_binding(b):
    p=Path(b['path']);need(p.is_file() and sha(p)==b['sha256'] and p.stat().st_size==b['bytes'],'Binding changed: '+str(p));return p
def inside(root,p):
    p=Path(p).resolve();need(p.is_relative_to(Path(root).resolve()),'Path escapes scope');return p
def write_new(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def close(a,b,tol,context):
    a,b=np.asarray(a),np.asarray(b)
    need(a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all(),context+' shape/nonfinite')
    error=float(np.max(np.abs(a-b))) if a.size else 0.
    need(error<=tol,context+f' maximum absolute error {error} exceeds {tol}')
    return error
def exact(a,b,context):need(np.array_equal(a,b),context+' differs')

def tree_close(saved,expected,context,tol=2e-12):
    if isinstance(expected,dict):
        need(set(saved)==set(expected),context+' keys')
        for k,v in expected.items():tree_close(saved[k],v,context+'.'+k,tol)
    elif isinstance(expected,list):
        need(len(saved)==len(expected),context+' length')
        for i,v in enumerate(expected):tree_close(saved[i],v,context+f'[{i}]',tol)
    elif isinstance(expected,float):close(saved,expected,tol,context)
    else:need(saved==expected,context+' value')

def native(y,p,z):
    return {'native_bce':ref.native_bce(y,z),'minimum_raw_probability':float(np.min(p)),
      'maximum_raw_probability':float(np.max(p)),'minimum_native_logit':float(np.min(z)),
      'maximum_native_logit':float(np.max(z)),
      'clipped_wrong_prediction_count':int(np.sum(((p<ref.CLIP)|(p>1-ref.CLIP))&((p>=.5)!=y)))}

def routing(arm,theta,x,policy):
    if not arm.startswith(('C_','T_')):return {'bank_count':1,'expert_evaluations_per_record':1}
    f=ref.forward(arm,theta,x,policy);weights=np.eye(5)[f['route']] if arm[-1]=='H' else np.exp(f['logq'])
    entropy=-np.sum(np.where(weights>0,weights*np.log(np.maximum(weights,1e-300)),0.),axis=1)
    return {'bank_count':5,'expert_evaluations_per_record':1 if arm[-1]=='H' else 5,
            'mean_weights':weights.mean(0).tolist(),'argmax_counts':np.bincount(np.argmax(weights,axis=1),minlength=5).tolist(),
            'nearest_counts':np.bincount(f['route'],minlength=5).tolist(),
            'mean_entropy':float(entropy.mean()),'mean_effective_experts':float(np.exp(entropy).mean())}

def work(arm,n,gradient):
    routed=arm.startswith(('C_','T_'));dense=routed and arm[-1]!='H';e=n*(5 if dense else 1)
    f=e if arm.startswith('C_') else 0;s=16*f if gradient else 0;c=f+s
    return dict(model_record_visits=n,expert_forward_examples=e,expert_backward_examples=e if gradient else 0,
      geometric_distance_pairs=5*n if routed else 0,learned_gate_affine_examples=4*n if arm.endswith('_L') else 0,
      mixture_expert_probability_values=5*n if dense else 0,residual_feature_values=12*n if arm.endswith('_R') else 0,
      forward_circuit_examples=f,shift_circuit_examples=s,circuit_examples=c,layer_applications=2*c,
      feature_ry_gates=4*c,trainable_ry_gates=4*c,trainable_rz_gates=4*c,cx_gates=2*c,readout_ry_gates=0,
      moment_values_computed=5*c,trig_feature_values=e*(25 if routed else 121) if arm.startswith('T_') or arm=='G121' else 0,
      mlp_hidden_evaluations=n*16 if arm.startswith('MLP') else 0,measurement_settings_equivalent=2*c)

def population(root,pop,seal):
    folder=Path(root)/'quantum/data';pp=folder/(pop+'_router.json')
    need(sha(pp)==seal['routers'][pop]['sha256'],'Router seal mismatch');policy=read(pp)
    data=[]
    for split in ('train','validation'):
        name=f'{pop}_{split}.npz';p=folder/name
        need(sha(p)==seal['files'][name]['sha256'],'Data seal mismatch '+name)
        with np.load(p,allow_pickle=False) as f:arrays={k:f[k] for k in f.files}
        n=seal['files'][name]['n'];need(len(arrays['x'])==len(arrays['y'])==n,'Sealed sample count mismatch')
        need(arrays['x'].shape==(n,2) and arrays['x'].dtype==np.float64 and np.isfinite(arrays['x']).all(),'Data shape/type')
        need(set(np.unique(arrays['y']))<={0,1} and len(set(arrays['ids'].tolist()))==n,'Labels/IDs invalid')
        distances=np.sum((arrays['x'][:,None,:]-np.asarray(policy['centroids'])[None,:,:])**2,axis=2)
        exact(arrays['kmeans_route'],np.argmin(distances,axis=1),'Cached geometric route')
        ordered=np.sort(distances,axis=1);margin=ordered[:,1]-ordered[:,0]
        edges=policy['margin_bins']['unique_edges']
        exact(arrays['margin_bin'],np.searchsorted(np.asarray(edges)[1:-1],margin,side='right'),'Cached margin bins')
        if 'raw_x' in arrays:
            close(arrays['x'],ref.preprocessing(arrays['raw_x'],policy,2),2e-14,'Stored 2D preprocessing')
            close(arrays['x4'],ref.preprocessing(arrays['raw_x'],policy,4),2e-14,'Stored 4D preprocessing')
        data.append(arrays)
    need(not(set(data[0]['ids'].tolist())&set(data[1]['ids'].tolist())),'Train/validation ID overlap')
    return *data,policy

def audit_endpoint(root,job,endpoint,auth,auth_path,seal,paired,popcache):
    """Pure endpoint checker also used by isolated pre-release fixture tests."""
    root=Path(root);endpoint=inside(root,endpoint);cp_path=endpoint/'endpoint_commit.json';commit=read(cp_path)
    arm,pop,seed,stage=job['arm'],job['population_id'],job['training_seed_id'],job['stage']
    rounds=job['rounds'];need(rounds==(20 if stage=='engineering' else 200) and job['updates']==75*rounds and
        job['updates_per_round']==75 and job['batch_size']==64,'Registered full budget invalid')
    need(commit['schema']=='qpath-v09-endpoint-1' and commit['status']=='completed','Commit schema/status')
    files=commit['files'];need({p.relative_to(endpoint).as_posix() for p in endpoint.rglob('*') if p.is_file()}==set(files)|{'endpoint_commit.json'},'Endpoint inventory changed')
    for name,b in files.items():
        need(Path(name).name==name,'Nested/unsafe endpoint payload');p=inside(endpoint,endpoint/name)
        need(sha(p)==b['sha256'] and p.stat().st_size==b['bytes'],'Payload binding changed '+name)
    config,result=read(endpoint/'config.json'),read(endpoint/'result.json')
    expected={'job_id':job['run_id'],'arm':arm,'method':arm,'population':pop,'seed':seed,'stage':stage,'test_accessed':False,
      'source_hashes':auth['scientific_source_hashes'],'data_seal_sha256':auth['data_seal_sha256'],
      'authorization_sha256':sha(auth_path),'matrix_sha256':auth['matrix_sha256'],'protocol_sha256':auth['protocol_sha256']}
    for artifact in (commit,config,result):
        for k,v in expected.items():need(artifact.get(k)==v,'Artifact recipe/binding '+k)
    for artifact in (result,commit):need(artifact['completed_rounds']==rounds and artifact['optimizer_global_updates']==75*rounds,'Incomplete endpoint')
    need(config['settings']==auth['settings'] and config['paired_streams']==job['paired_streams'],'Frozen recipe/settings changed')
    need(config['environment']['numpy']=='2.5.4' and config['environment']['python'].startswith('3.12.14 ') and
         len(config['environment']['threads'])==6 and set(config['environment']['threads'].values())=={'1'},'Training runtime mismatch')
    for key,s in job['paired_streams'].items():
        need(int(s['uint128_decimal'])==int.from_bytes(hashlib.sha256(s['namespace'].encode('ascii')).digest()[:16],'little'),'Stream hash mismatch '+key)
    need(set(job['paired_streams'])=={'training_order','paired_circuit_core_initialization','mlp_initialization'},'Missing registered stream')
    if pop not in popcache:popcache[pop]=population(root,pop,seal)
    train,val,policy=popcache[pop];x=train['x4'] if arm=='MLP4' else train['x'];vx=val['x4'] if arm=='MLP4' else val['x']
    need(config['router_policy_sha256']==seal['routers'][pop]['sha256'],'Router configuration hash')
    need(config['train_records']==len(x) and config['validation_records']==len(vx) and config['rounds']==rounds and config['batch_size']==64,'Config samples/budget')
    theta,master=ref.initial(arm,job['paired_streams']);expert,extra=ref.sizes(arm);nparam=len(theta)
    for obj in (result,config):need(obj['parameter_count']==nparam,'Parameter count mismatch')
    need(result['expert_parameter_count']==expert and result['extra_parameter_count']==extra,'Expert/head capacity mismatch')
    with np.load(endpoint/'initial_state.npz',allow_pickle=False) as f:
        exact(f['parameters'],theta,'Initial parameters');exact(f['master_initial'],master,'Master initialization');need(f['core_parameters'].size==0,'Unexpected frozen core')
    shapes={'round_parameters':(rounds,nparam),'validation_probabilities':(rounds,len(vx)),'validation_logits':(rounds,len(vx)),
      'validation_native_losses':(rounds,),'training_probabilities':(rounds,len(x)),'training_logits':(rounds,len(x)),
      'sampler_uniforms':(rounds,4800),'record_orders':(rounds,4800),'minibatch_gradients':(rounds*75,nparam)}
    arrays={k:np.load(endpoint/(k+'.npy'),mmap_mode='r',allow_pickle=False) for k in shapes}
    for k,a in arrays.items():need(a.shape==shapes[k] and a.dtype==(np.uint32 if k=='record_orders' else np.float64) and np.isfinite(a).all(),'Trace shape/dtype/nonfinite '+k)
    key=(pop,seed);pair=paired.setdefault(key,{})
    uh=ah(arrays['sampler_uniforms']);need(pair.setdefault('uniforms',uh)==uh,'Cross-arm uniform stream mismatch')
    if arm.startswith(('C_','T_')):
        init=ah(theta[:expert]);need(pair.setdefault(arm[0]+'_initial',init)==init,'Cross-arm expert initialization mismatch')
        if arm[-1] in 'SLR':
            warm=ah(arrays['minibatch_gradients'][:750,:expert]);need(pair.setdefault(arm[0]+'_warm750_gradients',warm)==warm,'Paired warmup gradients differ within 750 updates')
            states=ah(arrays['round_parameters'][:10,:expert]);need(pair.setdefault(arm[0]+'_warm10_rounds',states)==states,'Paired warmup parameters differ')
            if extra:need(np.all(arrays['round_parameters'][:10,expert:]==0),'Extra coefficients changed during warmup')
    lines=[json.loads(s) for s in (endpoint/'rounds.jsonl').read_text().splitlines()];need(len(lines)==rounds,'Round ledger incomplete')
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(int(job['paired_streams']['training_order']['uint128_decimal']))))
    m=np.zeros(expert);v=np.zeros(expert);em=np.zeros(extra);ev=np.zeros(extra);exposure=np.zeros(len(x),np.int64)
    best=float('inf');selected=0;choices=[];maxerrors={'probability':0.,'logit':0.,'gradient':0.,'Adam_parameter':0.};near=0;gradientchecks=0
    def checkpoint(name,r):
        with np.load(endpoint/name,allow_pickle=False) as cp:
            exact(cp['parameters'],arrays['round_parameters'][r],'Checkpoint parameters')
            exact(cp['validation_probabilities'],arrays['validation_probabilities'][r],'Checkpoint validation probabilities')
            exact(cp['validation_logits'],arrays['validation_logits'][r],'Checkpoint validation logits')
            need(cp['core_parameters'].size==0 and bool(cp['validation_evidence_present']),'Checkpoint evidence/core')
            need(int(cp['current_round'])==int(cp['completed_rounds'])==r+1 and int(cp['adam_t'])==75*(r+1) and
                 int(cp['extra_adam_t'])==(max(0,75*(r+1)-750) if extra else 0),'Checkpoint steps')
            for k,value in (('adam_m',m),('adam_v',v),('extra_adam_m',em),('extra_adam_v',ev)):close(cp[k],value,1e-10,'Checkpoint moment '+k)
    for r,line in enumerate(lines):
        need(line['round']==r+1 and line['optimizer_updates']==75*(r+1) and line['extra_optimizer_updates']==(max(0,75*(r+1)-750) if extra else 0),'Round update index')
        uniforms=rng.random(4800);exact(arrays['sampler_uniforms'][r],uniforms,'Uniform replay')
        indices=np.floor(len(x)*uniforms).astype(np.uint32);exact(arrays['record_orders'][r],indices,'Index replay');exposure+=np.bincount(indices,minlength=len(x))
        for b in range(75):
            t=75*r+b+1;g=arrays['minibatch_gradients'][t-1]
            if b in (0,74):
                ix=indices[b*64:(b+1)*64];oracle=ref.gradient(arm,theta,x[ix],train['y'][ix],policy)
                maxerrors['gradient']=max(maxerrors['gradient'],close(g,oracle,1e-9,'Independent gradient probe'));gradientchecks+=1
            theta[:expert],m,v=ref.adam(theta[:expert],g[:expert],m,v,t,.01)
            if extra and t>750:theta[expert:],em,ev=ref.adam(theta[expert:],g[expert:],em,ev,t-750,.001)
        maxerrors['Adam_parameter']=max(maxerrors['Adam_parameter'],close(theta,arrays['round_parameters'][r],1e-8,'Every saved-gradient Adam update'))
        # Evaluate the recorded parameters independently; Adam drift is separately bounded above.
        savedtheta=arrays['round_parameters'][r]
        for label,ds,xx in (('training',train,x),('validation',val,vx)):
            p,z=ref.predict(arm,savedtheta,xx,policy);sp,sz=arrays[label+'_probabilities'][r],arrays[label+'_logits'][r]
            maxerrors['probability']=max(maxerrors['probability'],close(sp,p,2e-12,'Independent '+label+' probabilities'))
            maxerrors['logit']=max(maxerrors['logit'],close(sz,z,1e-9,'Independent '+label+' logits'))
            disagreements=(sp>=.5)!=(p>=.5)
            need(np.all(~disagreements|((np.abs(sp-.5)<=TOLERANCES['threshold_band'])&(np.abs(p-.5)<=TOLERANCES['threshold_band']))),'Classification differs outside frozen rounding band')
            near+=int(disagreements.sum())
            metric=ref.metrics(ds['y'],sp);native_metrics=native(ds['y'],sp,sz)
            key='full_training' if label=='training' else label
            tree_close(line[key],metric,'Round '+key)
            tree_close(line[key+'_native'],native_metrics,'Round '+key+' native',1e-8)
            close(sp,ref.sigmoid(sz),2e-15,'Raw probability/logit consistency')
        vm=ref.metrics(val['y'],arrays['validation_probabilities'][r])
        close(arrays['validation_native_losses'][r],ref.native_bce(val['y'],arrays['validation_logits'][r]),1e-8,'Saved native validation loss')
        tree_close(line['routing_validation'],routing(arm,savedtheta,vx,policy),'Routing validation',2e-12)
        for field,a in (('round_parameter_sha256',savedtheta),('validation_probability_sha256',arrays['validation_probabilities'][r]),
                       ('validation_logit_sha256',arrays['validation_logits'][r]),('record_order_sha256',indices),('uniform_sha256',uniforms),
                       ('gradient_sha256',arrays['minibatch_gradients'][75*r:75*(r+1)]),('training_exposure_sha256',exposure)):
            need(line[field]==ah(a),'Round hash '+field)
        chosen=vm['bce']<best;need(line['selected']==chosen,'Strict earliest common validation selection differs')
        if chosen:
            best=vm['bce'];selected=r+1;choices.append(selected);checkpoint(f'selected_round_{selected:04d}.npz',r)
        if r==rounds-1:checkpoint('last_checkpoint.npz',r)
    need(result['selected_round']==selected,'Final selection differs')
    need({p.name for p in endpoint.glob('selected_round_*.npz')}=={f'selected_round_{i:04d}.npz' for i in choices},'Selected checkpoint inventory')
    need(sha(endpoint/'selected_checkpoint.npz')==sha(endpoint/f'selected_round_{selected:04d}.npz'),'Selected final checkpoint copy differs')
    for label,ds,xx in (('training',train,x),('validation',val,vx)):
        p,z=arrays[label+'_probabilities'][selected-1],arrays[label+'_logits'][selected-1]
        tree_close(result['selected_'+label],ref.metrics(ds['y'],p),'Selected '+label)
        tree_close(result['selected_'+label+'_native'],native(ds['y'],p,z),'Selected '+label+' native',1e-8)
        tree_close(result['routing_'+label],routing(arm,arrays['round_parameters'][selected-1],xx,policy),'Selected routing '+label)
    with (endpoint/'validation_predictions.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    need(len(rows)==len(vx),'Validation prediction row count')
    for i,row in enumerate(rows):
        need(row['record_id']==str(val['ids'][i]) and int(row['label'])==int(val['y'][i]) and
             int(row['prediction'])==int(arrays['validation_probabilities'][selected-1,i]>=.5) and
             int(row['kmeans_route'])==int(val['kmeans_route'][i]) and int(row['margin_bin'])==int(val['margin_bin'][i]),'Validation prediction metadata')
        close(float(row['probability']),arrays['validation_probabilities'][selected-1,i],2e-15,'Validation CSV probability')
        close(float(row['native_logit']),arrays['validation_logits'][selected-1,i],1e-12,'Validation CSV logit')
    exact(np.load(endpoint/'training_record_exposure.npy',allow_pickle=False),exposure,'Full exposure replay')
    need(result['full_training_record_visits']==4800*rounds and result['unique_train_records_exposed']==int(np.sum(exposure>0)),'Exposure accounting')
    need(result['work']['training']==work(arm,rounds*4800,True),'Training operation accounting')
    need(result['work']['full_training_diagnostics']==work(arm,rounds*len(x),False) and result['work']['validation']==work(arm,rounds*len(vx),False),'Forward diagnostic accounting')
    need(result['timing_performed'] is False and read(endpoint/'status.json')['status']=='completed','Timing/status invalid')
    for k in ('training_seconds','training_process_cpu_seconds','endpoint_total_seconds','invocation_process_cpu_seconds_through_result','diagnostic_forward_wall_seconds','diagnostic_forward_cpu_seconds','sampler_wall_seconds','sampler_cpu_seconds'):
        if k in result:need(np.isfinite(result[k]) and result[k]>=0,'Invalid cost '+k)
    return {'job_id':job['run_id'],'arm':arm,'population':pop,'seed':seed,'completed_rounds':rounds,
      'optimizer_global_updates':job['updates'],'selected_round':selected,'commit':binding(cp_path),'endpoint':str(endpoint),
      'selected_checkpoint':binding(endpoint/'selected_checkpoint.npz'),'payload_files_rehashed':len(files),
      'independent_gradient_probes':gradientchecks,'maximum_absolute_errors':maxerrors,'threshold_band_disagreements':near}

def audit(manifest_path,author_path,authorization_path,output):
    start=time.perf_counter();manifest=read(manifest_path);author=read(author_path);release=read(authorization_path)
    stage=manifest['stage'];need(stage in COUNTS,'Unknown stage');root=Path(manifest['study_root']).resolve()
    need(root==ROOT and manifest['mode']=='OFFICIAL_STUDY','Wrong official root/mode')
    need(release.get('review_status')=='approved_by_root' and release.get('stage')==stage and release.get('action')=='independent_endpoint_audit','Root audit release missing')
    for key,path in (('manifest',manifest_path),('author_audit',author_path),('independent_contract',HERE/'INDEPENDENT_AUDIT_CONTRACT.json')):
        need(check_binding(release[key]).resolve()==Path(path).resolve(),'Wrong root-bound '+key)
    contract=read(HERE/'INDEPENDENT_AUDIT_CONTRACT.json');need(contract['tolerances']==TOLERANCES,'Audit tolerances changed')
    for name,b in contract['source_bindings'].items():need(check_binding(b)==HERE/name,'Independent source binding mismatch')
    matrix_path=root/'governance/RUN_MATRIX.json';protocol_path=root/'governance/STUDY_PLAN.json';matrix=read(matrix_path)
    for item in manifest['bindings']:check_binding(item)
    for key in ('matrix','protocol','interpreter','trainer'):check_binding(manifest[key])
    need(Path(manifest['matrix']['path']).resolve()==matrix_path and Path(manifest['protocol']['path']).resolve()==protocol_path,'Manifest authority locations')
    jobs=[j for j in matrix['runs'] if j['stage']==stage]
    need(manifest['jobs']==jobs and len(jobs)==COUNTS[stage] and len({j['run_id'] for j in jobs})==len(jobs),'Incomplete/changed official matrix')
    auth_path=check_binding(manifest['authorization']);auth=read(auth_path)
    need(auth['review_status']=='approved_by_root' and auth['schema']=='qpath-v09-stage-authorization-1' and auth['stage']==stage and auth['run_ids']==[j['run_id'] for j in jobs],'Scientific authority mismatch')
    need(auth['matrix_sha256']==sha(matrix_path) and auth['protocol_sha256']==sha(protocol_path),'Matrix/protocol freeze mismatch')
    seal_path=root/'quantum/data/DATA_SEAL.json';need(sha(seal_path)==auth['data_seal_sha256'],'Data seal mismatch');seal=read(seal_path)
    for name,digest in auth['scientific_source_hashes'].items():need(sha(inside(root/'quantum',root/'quantum'/name))==digest,'Scientific source changed')
    need(author['status']=='PASS' and author['stage']==stage and author['verified_endpoints']==len(jobs),'Author audit missing/incomplete')
    need(check_binding(author['manifest']).resolve()==Path(manifest_path).resolve(),'Author audit wrong manifest')
    author_commits={r['job_id']:r['commit'] for r in author['endpoints']};need(set(author_commits)=={j['run_id'] for j in jobs},'Author audit endpoints differ')
    db=sqlite3.connect((root/'execution/state/ledger.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    rows={r['job_id']:dict(r) for r in db.execute('SELECT j.job_id,j.recipe_sha,j.manifest_sha,j.phase,j.current_attempt,a.endpoint,a.metadata_dir,a.status,a.commit_sha FROM jobs j JOIN attempts a ON a.attempt_id=j.current_attempt')};db.close()
    paired={};popcache={};reports=[]
    for job in jobs:
        row=rows[job['run_id']];need(row['status']=='succeeded' and row['phase']==stage and row['manifest_sha']==sha(manifest_path),'Ledger state/manifest mismatch')
        need(row['recipe_sha']==hashlib.sha256(canonical(job)).hexdigest(),'Ledger exact recipe mismatch')
        request=read(Path(row['metadata_dir'])/'REQUEST.json');need(request['job']==job and request['recipe_sha256']==row['recipe_sha'] and request['manifest_sha256']==sha(manifest_path) and
            Path(request['endpoint']).resolve()==Path(row['endpoint']).resolve(),'Durable request mismatch')
        commit_path=check_binding(author_commits[job['run_id']]);need(commit_path.resolve()==(Path(row['endpoint'])/'endpoint_commit.json').resolve() and sha(commit_path)==row['commit_sha'],'Ledger/author commit differs')
        reports.append(audit_endpoint(root,job,row['endpoint'],auth,auth_path,seal,paired,popcache))
        print(json.dumps({'stage':stage,'independently_verified':len(reports),'required':len(jobs),'job_id':job['run_id']}),flush=True)
    for name,digest in auth['scientific_source_hashes'].items():need(sha(root/'quantum'/name)==digest,'Source changed during audit')
    report={'schema':'qpath-v09-independent-endpoint-audit-1','status':'PASS','stage':stage,'verified_endpoints':len(reports),
      'utc':datetime.now(timezone.utc).isoformat(),'manifest':binding(manifest_path),'author_audit':binding(author_path),
      'root_release':binding(authorization_path),'contract':binding(HERE/'INDEPENDENT_AUDIT_CONTRACT.json'),
      'endpoints':reports,'test_model_outcomes_accessed':False,'retraining_performed':False,'effective_blas_threads':1,
      'scope':'Every payload, round, sampler value/index, Adam update from retained gradient, all train/validation predictions; independent gradients at minibatches 1 and 75 of every round; full 750-update paired warmup; strict earliest common validation BCE. Gradient probes are bounded, not full independent retraining.',
      'wall_seconds':time.perf_counter()-start}
    write_new(output,report);return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('manifest','author-audit','authorization','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(ROOT/'execution'));import durable,resource_probe
    environment=resource_probe.inspect();need(environment['effective_blas_threads']==1 and environment['numpy_version']=='2.5.4' and environment['python']=='3.12.14','Wrong independent audit runtime')
    with durable.auxiliary_lease(ROOT,'audit'):r=audit(a.manifest,a.author_audit,a.authorization,a.output)
    print(json.dumps({'status':r['status'],'verified_endpoints':r['verified_endpoints']}))
if __name__=='__main__':main()
