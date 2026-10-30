"""Author audit: retained budgets, SGD inputs, Adam path and every validation round.

No confirmation test payload or model outcome is opened. Independent audit is
separate; this author replay deliberately uses the registered implementation.
"""
from __future__ import annotations
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):os.environ[key]='1'
import argparse,json,sqlite3,sys,time
from pathlib import Path
import numpy as np
import study
from models import Model,Adam,PARAMETER_COUNTS,sigmoid,native_losses

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'execution'))
STAGE_COUNTS={'engineering':48,'A':72,'B':636}
require=study.require;read=study.read_json;digest=study.digest;ah=study.array_digest

def binding(path):
    p=Path(path);return {'path':str(p.resolve()),'sha256':digest(p),'bytes':p.stat().st_size}

def compare_metrics(saved,expected,context):
    for k in ('bce','macro_f1','accuracy','brier','ece10'):require(abs(saved[k]-expected[k])<=1e-14,context+' '+k)
    for k in ('confusion','n','clipped','reliability10'):require(saved[k]==expected[k],context+' '+k)

def audit(manifest_path,output):
    import resource_probe
    start=time.perf_counter();manifest=read(manifest_path);stage=manifest['stage'];jobs=manifest['jobs'];matrix=read(study.MATRIX_PATH)
    require(manifest['mode']=='OFFICIAL_STUDY' and Path(manifest['study_root']).resolve()==ROOT,'Wrong study root/mode')
    expected=[j for j in matrix['runs'] if study.STAGE_MAP[j['stage']]==stage]
    require(jobs==expected and len(jobs)==STAGE_COUNTS[stage],'Incomplete registered stage matrix')
    auth_path=Path(manifest['authorization']['path']);auth=read(auth_path)
    require(digest(auth_path)==manifest['authorization']['sha256'],'Authorization hash mismatch')
    for job in jobs:study.verify_freeze(job,auth_path)
    env=resource_probe.inspect();require(env['effective_blas_threads']==1 and env['numpy_version']=='2.5.4','Wrong audit runtime')
    db=sqlite3.connect((ROOT/'execution/state/ledger.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    rows={r['job_id']:dict(r) for r in db.execute('SELECT j.job_id,j.recipe_sha,j.manifest_sha,j.phase,j.current_attempt,a.endpoint,a.metadata_dir,a.status,a.commit_sha FROM jobs j JOIN attempts a ON a.attempt_id=j.current_attempt')};db.close()
    reports=[];payloads=0;gradient_checks=0;arraypairs=0;popcache={};paired_orders={};paired_init={};warmup={}
    for job in jobs:
        identity=job['run_id'];row=rows[identity];require(row['status']=='succeeded','Unsuccessful endpoint '+identity)
        require(row['manifest_sha']==digest(manifest_path),'Ledger manifest changed');endpoint=Path(row['endpoint']);commit_path=endpoint/'endpoint_commit.json';commit=read(commit_path)
        require(digest(commit_path)==row['commit_sha'],'Committed ledger digest changed')
        require(commit['schema']=='qpath-v09-endpoint-1' and commit['status']=='completed','Endpoint schema/status')
        require(commit['source_hashes']==auth['scientific_source_hashes'] and commit['data_seal_sha256']==auth['data_seal_sha256'],'Endpoint source/data mismatch')
        require(commit['authorization_sha256']==digest(auth_path) and commit['test_accessed'] is False,'Endpoint authority/test declaration')
        require(commit['matrix_sha256']==digest(study.MATRIX_PATH) and commit['protocol_sha256']==digest(study.PROTOCOL_PATH),'Protocol/matrix binding')
        require(set(p.name for p in endpoint.iterdir() if p.is_file())==set(commit['files'])|{'endpoint_commit.json'},'Unexpected endpoint file inventory')
        for name,item in commit['files'].items():
            require(Path(name).name==name,'Unsafe endpoint path');require(digest(endpoint/name)==item['sha256'] and (endpoint/name).stat().st_size==item['bytes'],'Changed endpoint payload');payloads+=1
        config=read(endpoint/'config.json');result=read(endpoint/'result.json');arm=job['arm'];population=job['population_id'];seed=job['training_seed_id'];rounds=job['rounds']
        for artifact in (commit,config,result):
            require(artifact['job_id']==identity and artifact['arm']==arm and artifact['method']==arm and artifact['population']==population and artifact['seed']==seed and artifact['stage']==stage,'Artifact recipe identity mismatch')
            require(artifact['test_accessed'] is False,'Declared test access')
        require(result['completed_rounds']==commit['completed_rounds']==rounds and result['optimizer_global_updates']==commit['optimizer_global_updates']==job['updates'],'Incomplete full horizon')
        require(config['settings']==study.SETTINGS and config['source_hashes']==study.source_hashes() and config['paired_streams']==job['paired_streams'],'Configuration recipe changed')
        if population not in popcache:popcache[population]=(study.load_population(population,'train'),study.load_population(population,'validation'),read(study.ROOT/'data'/f'{population}_router.json'))
        train,val,policy=popcache[population];streams={k:int(v['uint128_decimal']) for k,v in job['paired_streams'].items()};model=Model(arm,seed,streams,policy);x=model.input_for(train);vx=model.input_for(val)
        require(config['train_records']==len(x) and config['validation_records']==len(vx) and config['rounds']==rounds and config['batch_size']==64,'Configuration sample/budget mismatch')
        with np.load(endpoint/'initial_state.npz',allow_pickle=False) as initial:
            for name in ('parameters','master_initial','core_parameters'):np.testing.assert_array_equal(initial[name],getattr(model,name));arraypairs+=1
        nparam=PARAMETER_COUNTS[arm]
        shapes={'round_parameters':(rounds,nparam),'validation_probabilities':(rounds,len(vx)),'validation_logits':(rounds,len(vx)),
                'validation_native_losses':(rounds,),'training_probabilities':(rounds,len(x)),'training_logits':(rounds,len(x)),
                'sampler_uniforms':(rounds,4800),'record_orders':(rounds,4800),'minibatch_gradients':(rounds*75,nparam)}
        arrays={k:np.load(endpoint/(k+'.npy'),mmap_mode='r',allow_pickle=False) for k in shapes}
        for k,a in arrays.items():
            require(a.shape==shapes[k] and a.dtype==(np.uint32 if k=='record_orders' else np.float64),'Array shape/dtype '+k)
            require(np.isfinite(a).all(),'Nonfinite trace '+k)
        np.testing.assert_array_equal(arrays['validation_probabilities'],sigmoid(arrays['validation_logits']));arraypairs+=1
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(streams['training_order'])));pair=(population,seed)
        for r in range(rounds):np.testing.assert_array_equal(arrays['sampler_uniforms'][r],rng.random(4800));arraypairs+=1
        uh=ah(arrays['sampler_uniforms'])
        if pair in paired_orders:require(paired_orders[pair]==uh,'Cross-arm sampler differs')
        paired_orders[pair]=uh
        if model.routed:
            core_pair=(population,seed,arm[0]);ih=ah(model.parameters[:model.expert_size])
            if core_pair in paired_init:require(paired_init[core_pair]==ih,'Cross-arm expert initialisation differs')
            paired_init[core_pair]=ih
            if model.routing in ('S','L','R'):
                wh=ah(arrays['round_parameters'][:10,:model.expert_size])
                if core_pair in warmup:require(warmup[core_pair]==wh,'Full750-update paired warmup differs')
                warmup[core_pair]=wh
                if model.extra_size:require(np.all(arrays['round_parameters'][:10,model.expert_size:]==0),'Extra coefficients changed during warmup')
        ledger=[json.loads(s) for s in (endpoint/'rounds.jsonl').read_text(encoding='utf-8').splitlines()];require(len(ledger)==rounds,'Incomplete round ledger')
        opt=Adam((model.expert_size,),.01);extra_opt=Adam((model.extra_size,),.001);best=float('inf');selected=0;selected_moments={};exposure=np.zeros(len(x),dtype=np.int64)
        for r,line in enumerate(ledger):
            require(line['round']==r+1 and line['optimizer_updates']==75*(r+1),'Ledger round/update mismatch')
            indices=np.floor(len(x)*arrays['sampler_uniforms'][r]).astype(np.uint32)
            np.testing.assert_array_equal(indices,arrays['record_orders'][r]);arraypairs+=1;exposure+=np.bincount(indices,minlength=len(x))
            for b in range(75):
                g=arrays['minibatch_gradients'][r*75+b]
                if b in (0,74):
                    ix=indices[b*64:(b+1)*64];expected_g=model.gradient(x[ix],train['y'][ix])[1]
                    np.testing.assert_array_equal(g,expected_g);gradient_checks+=1;arraypairs+=1
                opt.step(model.parameters[:model.expert_size],g[:model.expert_size])
                if opt.t>750 and model.extra_size:extra_opt.step(model.parameters[model.expert_size:],g[model.expert_size:])
            np.testing.assert_array_equal(model.parameters,arrays['round_parameters'][r]);arraypairs+=1
            require(line['extra_optimizer_updates']==extra_opt.t,'Extra optimizer schedule mismatch')
            tp,tz=model.predict_with_logits(x);vp,vz=model.predict_with_logits(vx)
            for actual,expected_a in [(arrays['training_probabilities'][r],tp),(arrays['training_logits'][r],tz),(arrays['validation_probabilities'][r],vp),(arrays['validation_logits'][r],vz)]:np.testing.assert_array_equal(actual,expected_a);arraypairs+=1
            vm=study.metrics(val['y'],vp);compare_metrics(line['validation'],vm,'Validation');compare_metrics(line['full_training'],study.metrics(train['y'],tp),'Training')
            require(arrays['validation_native_losses'][r]==float(np.mean(native_losses(val['y'],vz)))==line['validation_native']['native_bce'],'Native validation loss mismatch')
            require(line['full_training_native']==study.native_diagnostics(model,train['y'],tp,tz),'Full train native diagnostics mismatch')
            require(line['validation_native']==study.native_diagnostics(model,val['y'],vp,vz),'Validation native diagnostics mismatch')
            require(line['routing_validation']==model.routing_diagnostics(vx),'Round routing diagnostics mismatch')
            for name,value in [('round_parameter_sha256',model.parameters),('validation_probability_sha256',vp),('validation_logit_sha256',vz),('record_order_sha256',indices),('uniform_sha256',arrays['sampler_uniforms'][r]),('gradient_sha256',arrays['minibatch_gradients'][r*75:(r+1)*75]),('training_exposure_sha256',exposure)]:require(line[name]==ah(value),'Round trace hash '+name)
            chosen=vm['bce']<best;require(line['selected']==chosen,'Validation selection flag differs')
            if chosen:
                best=vm['bce'];selected=r+1;selected_moments={name:value.copy() for name,value in [('adam_m',opt.m),('adam_v',opt.v),('extra_adam_m',extra_opt.m),('extra_adam_v',extra_opt.v)]}
        require(result['selected_round']==selected,'Earliest minimum selection differs')
        for name,index in [('selected_checkpoint.npz',selected-1),('last_checkpoint.npz',rounds-1)]:
            moments=selected_moments if name.startswith('selected') else {'adam_m':opt.m,'adam_v':opt.v,'extra_adam_m':extra_opt.m,'extra_adam_v':extra_opt.v}
            with np.load(endpoint/name,allow_pickle=False) as cp:
                np.testing.assert_array_equal(cp['parameters'],arrays['round_parameters'][index]);np.testing.assert_array_equal(cp['validation_probabilities'],arrays['validation_probabilities'][index]);np.testing.assert_array_equal(cp['validation_logits'],arrays['validation_logits'][index]);arraypairs+=3
                require(int(cp['adam_t'])==75*(index+1) and int(cp['extra_adam_t'])==(max(0,75*(index+1)-750) if model.extra_size else 0),'Checkpoint Adam steps')
                for k,v in moments.items():np.testing.assert_array_equal(cp[k],v);arraypairs+=1
        model.parameters[:]=arrays['round_parameters'][selected-1];vp,vz=model.predict_with_logits(vx);tp,tz=model.predict_with_logits(x)
        compare_metrics(result['selected_validation'],study.metrics(val['y'],vp),'Selected validation');compare_metrics(result['selected_training'],study.metrics(train['y'],tp),'Selected training')
        require(result['selected_validation_native']==study.native_diagnostics(model,val['y'],vp,vz) and result['selected_training_native']==study.native_diagnostics(model,train['y'],tp,tz),'Selected native diagnostics mismatch')
        require(result['routing_validation']==model.routing_diagnostics(vx) and result['routing_training']==model.routing_diagnostics(x),'Selected routing diagnostics mismatch')
        np.testing.assert_array_equal(np.load(endpoint/'training_record_exposure.npy',allow_pickle=False),exposure);arraypairs+=1
        require(result['full_training_record_visits']==4800*rounds and result['work']['training']['model_record_visits']==4800*rounds,'Training visits changed')
        require(result['work']['training']['expert_forward_examples']==4800*rounds*(5 if model.routed and model.routing!='H' else 1),'Expert evaluation accounting changed')
        expected_work={k:v*75*rounds for k,v in model.accounting(np.zeros((64,model.input_dim)),gradient=True).items()}
        require(result['work']['training']==expected_work,'Detailed training operation accounting changed')
        require(result['timing_performed'] is False,'Concurrent inference timing detected')
        reports.append({'job_id':identity,'arm':arm,'population':population,'seed':seed,'completed_rounds':rounds,'optimizer_global_updates':job['updates'],'selected_round':selected,'commit':binding(commit_path),'endpoint':str(endpoint),'selected_checkpoint':binding(endpoint/'selected_checkpoint.npz')})
        print(json.dumps({'stage':stage,'verified':len(reports),'required':len(jobs),'job_id':identity}),flush=True)
    require(study.source_hashes()==auth['scientific_source_hashes'],'Sources changed during audit')
    report={'schema':'qpath-v09-author-stage-audit-1','status':'PASS','stage':stage,'verified_endpoints':len(reports),'utc':study.now(),
      'manifest':binding(manifest_path),'authorization':binding(auth_path),'scientific_source_hashes':auth['scientific_source_hashes'],'data_seal_sha256':auth['data_seal_sha256'],
      'payload_files_rehashed':payloads,'array_comparisons':arraypairs,'selected_minibatch_gradients_recomputed':gradient_checks,
      'endpoints':reports,'test_model_outcomes_accessed':False,'retraining_performed':False,'audit_runtime':env,'effective_blas_threads':1,
      'scope':'Author numerical replay: complete payload hashes, all uniform draws and indices, every Adam update from recorded gradients, first/last minibatch gradients each round, all train/validation predictions and selection; exact paired750-update warmup. Separate independent audit required.',
      'wall_seconds':time.perf_counter()-start}
    study.write_json(output,report,True);return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    import durable
    with durable.auxiliary_lease(ROOT,'audit'):
        r=audit(a.manifest,a.output)
    print(json.dumps({'status':r['status'],'stage':r['stage'],'verified_endpoints':r['verified_endpoints']}))
if __name__=='__main__':main()
