"""Author endpoint audit. Reads train/validation evidence only; no test scoring."""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[_key]='1'
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
import numpy as np
import study
from models import Model,ARM_METHODS,PARAMETER_COUNTS,logit_cross_entropy,sigmoid,Adam,native_losses
import sampling

ROOT=Path(__file__).resolve().parent.parent
STAGE_COUNTS={'engineering':40,'A':80,'B':640}
sys.path.insert(0,str(ROOT/'execution'))
import durable
import resource_probe

def require(v,m):
    if not v:raise RuntimeError(m)
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ah(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def binding(p):return {'path':str(Path(p).resolve()),'sha256':digest(p),'bytes':Path(p).stat().st_size}
def compare_metrics(saved,expected,context):
    for key in ('bce','macro_f1','accuracy','brier','ece10'):
        require(abs(saved[key]-expected[key])<=1e-14,context+' '+key)
    for key in ('confusion','n','clipped'):
        require(saved[key]==expected[key],context+' '+key)
    require(saved['reliability10']==expected['reliability10'],context+' reliability')

def audit(manifest_path,output):
    started=time.perf_counter()
    manifest=read(manifest_path);stage=manifest['stage'];jobs=manifest['jobs']
    require(manifest['mode']=='OFFICIAL_STUDY' and manifest['study_root']==str(ROOT),'Wrong official study binding')
    counts=STAGE_COUNTS
    matrix=read(study.MATRIX_PATH);expected=[j for j in matrix['runs'] if study.STAGE_MAP[j['stage']]==stage]
    require(jobs==expected and len(jobs)==counts[stage],'Incomplete stage matrix')
    auth_path=Path(manifest['authorization']['path']);auth=read(auth_path)
    require(digest(auth_path)==manifest['authorization']['sha256'],'Authorization mismatch')
    require(auth['scientific_source_hashes']==study.source_hashes(),'Scientific sources changed')
    require(auth['data_seal_sha256']==digest(ROOT/'quantum/data/DATA_SEAL.json'),'Data seal changed')
    env=resource_probe.inspect();require(env['effective_blas_threads']==1 and env['numpy_version']=='2.5.4','Wrong numerical audit runtime')
    db_path=ROOT/'execution/state/ledger.sqlite3'
    db=sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    rows={r['job_id']:dict(r) for r in db.execute('SELECT j.job_id,j.recipe_sha,j.manifest_sha,j.phase,j.current_attempt,a.endpoint,a.metadata_dir,a.status,a.commit_sha FROM jobs j JOIN attempts a ON a.attempt_id=j.current_attempt')}
    db.close()
    reports=[];arraypairs=0;gradient_checks=0;payloads=0;popcache={};pairedorders={};pairedinit={}
    for job in jobs:
        identity=job['run_id'];row=rows[identity]
        require(row['status']=='succeeded','Non-successful endpoint '+identity)
        require(row['manifest_sha']==digest(manifest_path),'Ledger manifest changed')
        endpoint=Path(row['endpoint'])
        commit_path=endpoint/'endpoint_commit.json';commit=read(commit_path)
        require(digest(commit_path)==row['commit_sha'],'Committed ledgerdigest changed')
        require(commit['schema']=='qpath-v08-endpoint-1','Endpoint schema')
        require(commit['job_id']==identity and commit['arm']==job['arm'] and commit['population']==job['population_id'] and commit['seed']==job['training_seed_id'],'Endpointidentity')
        require(commit['source_hashes']==auth['scientific_source_hashes'] and commit['data_seal_sha256']==auth['data_seal_sha256'],'Endpointsource/data')
        require(commit['authorization_sha256']==digest(auth_path) and commit['test_accessed'] is False,'Endpointauthority/test')
        require(commit['matrix_sha256']==digest(study.MATRIX_PATH) and commit['protocol_sha256']==digest(study.PROTOCOL_PATH),'Protocolbinding')
        require(set(p.name for p in endpoint.iterdir() if p.is_file())==set(commit['files'])|{'endpoint_commit.json'},'Unexpected endpointpayload')
        for name,item in commit['files'].items():
            require(Path(name).name==name,'Unsafe endpointpayloadpath')
            require(digest(endpoint/name)==item['sha256'] and (endpoint/name).stat().st_size==item['bytes'],'Changed endpointpayload')
            payloads+=1
        result=read(endpoint/'result.json');config=read(endpoint/'config.json')
        require(result['completed_rounds']==job['rounds'] and result['optimizer_global_updates']==job['updates'],'Incompletehorizon')
        require(result['test_accessed'] is False and config['test_accessed'] is False,'Test access declared')
        require(config['source_hashes']==study.source_hashes() and config['paired_streams']==job['paired_streams'],'Configsources/streams')
        require(config['rounds']==job['rounds'] and config['train_records']==4800 and config['validation_records']==1600 and config['batch_size']==64,'Configbudget')
        require(config['stage_freeze_sha256']==digest(auth_path),'Configstagebinding')
        population=job['population_id']
        if population not in popcache:popcache[population]=(study.load_population(population,'train'),study.load_population(population,'validation'))
        train,val=popcache[population]
        for artifact in (commit,config,result):
            require(artifact['base_model']==job['base_model'] and artifact['sampling_policy']==job['sampling_policy'],'Sampling recipe identity')
        method=ARM_METHODS[job['arm']];streams={k:int(v['uint128_decimal']) for k,v in job['paired_streams'].items()}
        require(commit['method']==method,'Committed method mismatch')
        for item in (config,result):
            require(item['job_id']==identity and item['arm']==job['arm'] and item['method']==method and
                    item['seed']==job['training_seed_id'] and item['stage']==stage and item['population']==population,'Result/config recipe mismatch')
        model=Model(method,job['training_seed_id'],streams);nparam=PARAMETER_COUNTS[method];rounds=job['rounds']
        with np.load(endpoint/'initial_state.npz',allow_pickle=False) as initial:
            for field in ('parameters','master_initial','core_parameters'):np.testing.assert_array_equal(initial[field],getattr(model,field));arraypairs+=1
        states=np.load(endpoint/'round_parameters.npy',allow_pickle=False)
        probs=np.load(endpoint/'validation_probabilities.npy',allow_pickle=False)
        logits=np.load(endpoint/'validation_logits.npy',allow_pickle=False)
        losses=np.load(endpoint/'validation_native_losses.npy',allow_pickle=False)
        orders=np.load(endpoint/'record_orders.npy',allow_pickle=False)
        require(states.shape==(rounds,nparam) and states.dtype==np.float64 and np.isfinite(states).all(),'Roundstate shape/values')
        require(probs.shape==logits.shape==(rounds,1600) and probs.dtype==logits.dtype==np.float64,'Validation arrayshape/type')
        require(np.isfinite(probs).all() and np.isfinite(logits).all() and np.all((probs>=0)&(probs<=1)),'Probability/logitvalues')
        np.testing.assert_array_equal(probs,sigmoid(logits));arraypairs+=1
        require(losses.shape==(rounds,) and losses.dtype==np.float64 and np.isfinite(losses).all(),'Nativeloss array')
        require(orders.shape==(rounds,4800) and orders.dtype==np.uint16,'Recordordershape/type')
        with np.load(endpoint/'population_identity.npz',allow_pickle=False) as popids:
            np.testing.assert_array_equal(popids['train_ids'],train['ids']);np.testing.assert_array_equal(popids['validation_ids'],val['ids']);arraypairs+=2
        trace_names=('training_probabilities','training_logits','training_native_losses','sampler_uniforms',
            'sampling_probabilities','sampling_weights','sampling_counts','refresh_native_losses','refresh_scores',
            'refresh_priority_probabilities','minibatch_gradients')
        trace={name:np.load(endpoint/(name+'.npy'),allow_pickle=False,mmap_mode='r') for name in trace_names}
        for name,value in trace.items():
            shape=((job['updates'],nparam) if name=='minibatch_gradients' else (rounds,) if name=='training_native_losses'
                else (rounds-10,4800) if name.startswith('refresh_') else (rounds,4800))
            require(value.shape==shape,'Sampler trace shape '+name)
            require(value.dtype==(np.uint16 if name=='sampling_counts' else np.float64),'Sampler trace dtype '+name)
            require(np.isfinite(value).all(),'Nonfinite sampler trace '+name)
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(streams['training_order'])))
        for i in range(rounds):
            np.testing.assert_array_equal(trace['sampler_uniforms'][i],rng.random(4800));arraypairs+=1
        pair=(population,job['training_seed_id'])
        if pair in pairedorders:require(pairedorders[pair]==ah(trace['sampler_uniforms']),'Crossarm uniform stream differs')
        pairedorders[pair]=ah(trace['sampler_uniforms'])
        if job['base_model'] in ('MultiK','MultiHash'):
            with np.load(endpoint/'initial_state.npz',allow_pickle=False) as initial:initialh=ah(initial['parameters'])
            if pair in pairedinit:require(pairedinit[pair]==initialh,'Paired Multi initialization differs')
            pairedinit[pair]=initialh
        route=model.route_for(train)
        replay=Model(method,job['training_seed_id'],streams);opt=Adam(replay.parameters.shape)
        exposure=np.zeros(4800,dtype=np.int64);bank_visits=np.zeros(model.banks,dtype=np.int64)
        class_visits=np.zeros(2,dtype=np.int64)
        selected_moments={}
        ledger=[json.loads(line) for line in (endpoint/'ledger.jsonl').read_text().splitlines()]
        require(len(ledger)==rounds,'Incompleteledger')
        best=float('inf');selected=0
        for i,line in enumerate(ledger):
            require(line['round']==i+1 and line['optimizer_updates']==75*(i+1),'Round/updateledger')
            expected_metrics=study.metrics(val['y'],probs[i]);compare_metrics(line['validation'],expected_metrics,'Validationledger')
            native=logit_cross_entropy(val['y'],logits[i])
            require(native==losses[i] and abs(native-line['validation_native']['native_bce'])<=1e-14,'Nativelossledger')
            require(line['round_parameter_sha256']==ah(states[i]) and line['validation_probability_sha256']==ah(probs[i]),'Roundarrayhash')
            require(line['validation_logit_sha256']==ah(logits[i]) and line['validation_native_loss_sha256']==ah(losses[i:i+1]),'Roundlogithash')
            require(line['record_order_sha256']==ah(orders[i]),'Orderhashledger')
            sd=line['sampling'];before=replay.parameters.copy()
            require(sd['refresh_parameter_sha256']==ah(before),'Refresh start-state changed')
            proposed=None;refresh_row=None
            if i>=10:
                refresh_row=i-10
                _,fresh_logits=replay.predict_with_logits(train['x'],route)
                fresh_loss=native_losses(train['y'],fresh_logits)
                score,proposed=sampling.priority_distribution(fresh_loss)
                for name,value in (('refresh_native_losses',fresh_loss),('refresh_scores',score),('refresh_priority_probabilities',proposed)):
                    np.testing.assert_array_equal(trace[name][refresh_row],value);arraypairs+=1
            require(sd['refresh_performed']==(i>=10) and sd['refresh_row']==refresh_row,'Refresh schedule changed')
            pp=sampling.selected_distribution(4800,i+1,{'uniform':'U','priority':'P'}[job['sampling_policy']],proposed)
            indices,weights=sampling.inverse_cdf_draws(pp,trace['sampler_uniforms'][i])
            counts=np.bincount(indices,minlength=4800)
            for actual,want in ((trace['sampling_probabilities'][i],pp),(orders[i],indices),
                                (trace['sampling_weights'][i],weights),(trace['sampling_counts'][i],counts)):
                np.testing.assert_array_equal(actual,want);arraypairs+=1
            basic=sampling.diagnostics(pp,weights,counts)
            for key,value in basic.items():require(sd[key]==value,'Sampling diagnostic '+key)
            exposure+=counts;classdraw=np.bincount(train['y'][indices],minlength=2);class_visits+=classdraw
            bank_visits+=np.bincount(route[indices],minlength=model.banks) if route is not None else [4800]
            require(sd['class_draws']==classdraw.tolist() and sd['class_draws_cumulative']==class_visits.tolist(),'Class exposure')
            require(sd['record_exposure_sha256']==ah(exposure),'Record exposure hash')
            high=None if i<10 else int(np.sum(trace['refresh_native_losses'][refresh_row][indices]>5.))
            require(sd['high_loss_draws']==high,'High-loss draw count')
            require(line['bank_record_visits_cumulative']==bank_visits.tolist(),'Round sampled bank exposure')
            for batch in range(75):
                gradient=trace['minibatch_gradients'][i*75+batch]
                if batch in (0,74):
                    ix=indices[batch*64:(batch+1)*64]
                    expected_gradient=replay.gradient(train['x'][ix],train['y'][ix],None if route is None else route[ix],
                                                       sample_weight=weights[batch*64:(batch+1)*64])[1]
                    np.testing.assert_array_equal(gradient,expected_gradient);arraypairs+=1;gradient_checks+=1
                opt.step(replay.parameters,gradient)
            np.testing.assert_array_equal(replay.parameters,states[i]);arraypairs+=1
            p_train,z_train=replay.predict_with_logits(train['x'],route)
            p_val,z_val=replay.predict_with_logits(val['x'],replay.route_for(val))
            for actual,want in ((trace['training_probabilities'][i],p_train),(trace['training_logits'][i],z_train),
                                (probs[i],p_val),(logits[i],z_val)):
                np.testing.assert_array_equal(actual,want);arraypairs+=1
            compare_metrics(line['full_training'],study.metrics(train['y'],p_train),'Full training ledger')
            train_native=logit_cross_entropy(train['y'],z_train)
            require(trace['training_native_losses'][i]==train_native==line['full_training_native']['native_bce'],'Full train native loss')
            trace_hashes={k:ah(v[refresh_row] if k.startswith('refresh_') else
                v[i*75:(i+1)*75] if k=='minibatch_gradients' else v[i:i+1] if v.ndim==1 else v[i])
                for k,v in trace.items() if not k.startswith('refresh_') or refresh_row is not None}
            require(line['sampler_trace_sha256']==trace_hashes,'Sampler trace ledger binding')

            chosen=expected_metrics['bce']<best
            require(line['selected']==chosen,'Selectedroundflagdiffers')
            if chosen:
                best=expected_metrics['bce'];selected=i+1;selected_moments={'adam_m':opt.m.copy(),'adam_v':opt.v.copy()}
        require(result['selected_round']==selected,'Earliestminselectiondiffers')
        for name,index in (('selected_checkpoint.npz',selected-1),('last_checkpoint.npz',rounds-1)):
            with np.load(endpoint/name,allow_pickle=False) as checkpoint:
                np.testing.assert_array_equal(checkpoint['parameters'],states[index]);arraypairs+=1
                np.testing.assert_array_equal(checkpoint['validation_probabilities'],probs[index]);arraypairs+=1
                np.testing.assert_array_equal(checkpoint['validation_logits'],logits[index]);arraypairs+=1
                require(int(checkpoint['adam_t'])==75*(index+1) and int(checkpoint['current_round'])==index+1,'Checkpointtime')
                for moment in ('adam_m','adam_v'):require(checkpoint[moment].shape==(nparam,) and np.isfinite(checkpoint[moment]).all(),'Optimizermoment')
                require(np.all(checkpoint['adam_v']>=0),'InvalidAdamvariance')
                expected_moments=selected_moments if name=='selected_checkpoint.npz' else {'adam_m':opt.m,'adam_v':opt.v}
                for key,value in expected_moments.items():np.testing.assert_array_equal(checkpoint[key],value);arraypairs+=1
        model.parameters[:]=states[selected-1]
        predicted,actual_logits=model.predict_with_logits(val['x'],model.route_for(val))
        np.testing.assert_array_equal(predicted,probs[selected-1]);np.testing.assert_array_equal(actual_logits,logits[selected-1]);arraypairs+=2
        compare_metrics(result['selected_validation'],study.metrics(val['y'],predicted),'Selectedresult')
        route=model.route_for(train)
        bank_counts=np.bincount(route,minlength=model.banks) if route is not None else np.array([4800])
        require(result['bank_training_record_visits']==bank_visits.tolist(),'Sampled bank visits differ')
        np.testing.assert_array_equal(np.load(endpoint/'training_record_exposure.npy',allow_pickle=False),exposure);arraypairs+=1
        require(result['sampling_diagnostics']['refresh_count']==rounds-10,'Refresh count')
        require(result['sampling_diagnostics']['class_draws']==class_visits.tolist(),'Final class exposure')
        require(sum(result['bank_training_record_visits'])==4800*rounds,'Missingrecordvisits')
        w=result['work']['training']
        require(w['model_record_visits']==4800*rounds,'Trainingworkvisits')
        require(w['core_statevector_examples']==(4800*rounds*17 if model.quantum else 0),'Trainingcircuitwork')
        require(result['inference']['performed'] is False,'Unexpected concurrent inference timing')
        reports.append({'job_id':identity,'arm':job['arm'],'population':population,'seed':job['training_seed_id'],
            'completed_rounds':rounds,'optimizer_global_updates':job['updates'],'selected_round':selected,
            'commit':binding(commit_path),'endpoint':str(endpoint),'selected_checkpoint':binding(endpoint/'selected_checkpoint.npz')})
        print(json.dumps({'stage':stage,'verified':len(reports),'required':len(jobs),'job_id':identity}),flush=True)
    require(study.source_hashes()==auth['scientific_source_hashes'],'Sourceschangedduringaudit')
    report={'schema':'qpath-v08-author-stage-audit-1','status':'PASS','stage':stage,'verified_endpoints':len(reports),
        'utc':datetime.now(timezone.utc).isoformat(),'manifest':binding(manifest_path),'authorization':binding(auth_path),
        'data_seal_sha256':auth['data_seal_sha256'],'scientific_source_hashes':auth['scientific_source_hashes'],
        'payload_files_rehashed':payloads,'array_comparisons':arraypairs,'selected_minibatch_gradients_recomputed':gradient_checks,'endpoints':reports,
        'test_model_outcomes_accessed':False,'retraining_performed':False,'effective_blas_threads':1,
        'audit_runtime':env,'audit_process_resources':resource_probe.process_resources(),
        'scope':'Author audit of every full endpoint, all round train/validation predictions and metrics, refreshed loss/scores/probabilities, paired uniforms, replacement indices/weights, every Adam update from retained raw gradients, first/last minibatch gradients per round, earliestvalidationselection and exact selected forward replay. Independent reviewer remains separately required.',
        'wall_seconds':time.perf_counter()-started}
    with Path(output).open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({'status':'PASS','stage':stage,'verified_endpoints':len(reports),'output':str(output),'sha256':digest(output)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    with durable.auxiliary_lease(ROOT,'audit'):audit(a.manifest,a.output)
