"""Released, serial conversion/parity and raw-input inference benchmark.

No optimization, model selection, labels-based scoring, provider or hardware.
Canonical prediction evidence is never replaced by compiled predictions.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import numpy as np
import study as s
import routers
import deployment_compiler as compiler

PROTOCOL=s.ROOT.parent/'governance/DEPLOYMENT_PROTOCOL.json'
IMPLEMENTATION_NOTES=s.ROOT.parent/'governance/DEPLOYMENT_IMPLEMENTATION_NOTES.json'


def parity(p,z,reference_p,reference_z,ids=None):
    p,z,reference_p,reference_z=map(np.asarray,(p,z,reference_p,reference_z))
    s.require(p.shape==z.shape==reference_p.shape==reference_z.shape,'Parity shape mismatch')
    pe=float(np.max(abs(p-reference_p)));ze=float(np.max(abs(z-reference_z)))
    s.require(pe<=2e-12 and ze<=1e-9,'Compiled probability/logit mismatch')
    different=(p>=.5)!=(reference_p>=.5);inside=(abs(p-.5)<=2e-12)&(abs(reference_p-.5)<=2e-12)
    s.require(not np.any(different&~inside),'Compiled class difference outside both-in-band condition')
    ids=np.arange(len(p)) if ids is None else np.asarray(ids)
    return {'maximum_probability_error':pe,'maximum_logit_error':ze,'records':len(p),
        'class_disagreements':int(different.sum()),'canonical_near_band':int(np.sum(abs(reference_p-.5)<=2e-12)),
        'compiled_near_band':int(np.sum(abs(p-.5)<=2e-12)),
        'disagreements':[{'record_id':int(ids[i]),'canonical_probability':float(reference_p[i]),
                           'compiled_probability':float(p[i])} for i in np.flatnonzero(different)]}


def fixed_parity_inputs(policy):
    """Label-free off-grid probes and true clipped Voronoi-edge midpoints."""
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([690621])))
    offgrid=rng.uniform(-1,1,(128,2));centers=np.asarray(policy['centroids'],dtype=float)
    points=[];records=[]
    for i in range(5):
        for j in range(i+1,5):
            delta=centers[j]-centers[i];norm=float(np.linalg.norm(delta))
            s.require(norm>0,'Duplicate routing centroid')
            direction=np.array([-delta[1],delta[0]])/norm;mid=(centers[i]+centers[j])/2
            constraints=[]
            for axis in range(2):
                unit=np.eye(2)[axis];constraints.extend(((unit,1.),(-unit,1.)))
            for k in range(5):
                if k not in (i,j):constraints.append((2*(centers[k]-centers[i]),float(centers[k]@centers[k]-centers[i]@centers[i])))
            lo,hi=-float('inf'),float('inf');valid=True
            for a,b in constraints:
                slope=float(a@direction);remaining=float(b-a@mid)
                if abs(slope)<1e-14:
                    if remaining<-1e-12:valid=False;break
                elif slope>0:hi=min(hi,remaining/slope)
                else:lo=max(lo,remaining/slope)
            if not valid or not np.isfinite([lo,hi]).all() or hi-lo<=1e-12:continue
            edge=mid+((lo+hi)/2)*direction
            for side in (-1,0,1):
                point=edge+side*1e-10*delta/norm
                points.append(point);records.append({'centroid_pair':[i,j],'side':side,'normal_offset':side*1e-10})
    boundary=np.asarray(points,dtype=float).reshape(-1,2)
    return offgrid,boundary,records


def assert_quiescent():
    """Inspect this study's relevant Python commands; never stop processes."""
    if os.name!='nt':raise RuntimeError('Registered benchmark isolation probe requires Windows')
    command="Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' } | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
    raw=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,check=True).stdout.strip()
    processes=[] if not raw else json.loads(raw);processes=[processes] if isinstance(processes,dict) else processes
    own={os.getpid(),os.getppid()};relevant=[]
    tokens=('study.py','launch_stage.py','run_engineering.py','audit_','replay_and_analyse.py','evaluate_confirmation.py','local_readiness.py','deployment_benchmark.py')
    for row in processes:
        line=row.get('CommandLine') or ''
        if row['ProcessId'] not in own and any(t in line for t in tokens):
            relevant.append(row)
    s.require(not relevant,'Benchmark isolation blocked by relevant live processes: '+repr(relevant))
    return {'checked_utc':s.now(),'pid':os.getpid(),'excluded_self_and_parent':sorted(own),
            'relevant_other_process_count':0,'scope':'Python commands containing the declared training/evaluation/audit/benchmark entry-point names across projects; background OS work remains unisolated.'}


def trial_batches(x,batch_size):
    if batch_size==1:return [x[i:i+1] for i in range(128)]
    if batch_size==32:return [x[i:i+32] for i in range(0,1024,32)]
    if batch_size==1024:return [x]*32
    raise ValueError('Unregistered batch size')


def measure_trial(forward,batches):
    values=[];start=time.perf_counter_ns()
    for x in batches:values.append(forward(x))
    elapsed=time.perf_counter_ns()-start
    # Hashing/concatenation is outside prediction latency. Each model call and
    # raw-input routing/feature/readout work occurs inside the timed interval.
    p=np.concatenate([v[0] for v in values]);z=np.concatenate([v[1] for v in values])
    return elapsed,p,z


def checked_endpoint(population,seed,method,watched):
    folder=s.ROOT/'stage_B'/population/f'seed_{seed}'/method
    commit=s.read_json(folder/'endpoint_commit.json');s.require(commit['status']=='completed','Uncommitted endpoint')
    watched[folder/'endpoint_commit.json']=s.digest(folder/'endpoint_commit.json')
    for name in ('selected_checkpoint.npz','result.json'):
        path=folder/name;h=s.digest(path);s.require(h==commit['files'][name]['sha256'],'Endpoint payload mismatch');watched[path]=h
    start=time.perf_counter_ns();model=s.Model(method,seed)
    with np.load(folder/'selected_checkpoint.npz',allow_pickle=False) as data:
        model.parameters[:]=data['parameters'];vp=data['validation_probabilities'].copy();vz=data['validation_logits'].copy()
    load_ns=time.perf_counter_ns()-start
    return folder,model,vp,vz,load_ns


def checked_data_path(population,split,watched):
    """Bind each sealed payload before array access and recheck it on exit."""
    seal_path=s.ROOT/'data/DATA_SEAL.json';seal_hash=s.digest(seal_path)
    s.require(watched.get(seal_path)==seal_hash,'Data seal is not bound by the release guard')
    seal=s.read_json(seal_path);s.require(s.digest(seal_path)==seal_hash,'Data seal changed while reading')
    name=f'{population}_{split}.npz';path=s.ROOT/'data'/name
    digest=s.digest(path);s.require(digest==seal['files'][name]['sha256'],'Sealed data payload changed: '+name)
    watched[path]=digest
    return path


def checked_evaluation_commit(evaluation,watched):
    """Check the exact completed canonical inventory, including every byte."""
    root=s.ROOT/'confirmation_evaluation';path=root/'EVALUATION_COMMIT.json'
    h=s.digest(path);commit=s.read_json(path);s.require(s.digest(path)==h,'Evaluation commit changed while reading')
    expected=evaluation.expected_output_paths()
    s.require(commit.get('status')=='completed' and commit.get('study_id')=='QPATH-GENERALIZATION-v0.6','Completed canonical evaluation required')
    endpoint_count=len(s.POPULATIONS['B'])*len(s.SEEDS['B'])*len(s.METHODS)
    s.require(commit.get('report_count')==endpoint_count and commit.get('prediction_file_count')==endpoint_count and
              commit.get('population_count')==len(s.POPULATIONS['B']) and commit.get('payload_count')==len(expected),'Canonical evaluation coverage mismatch')
    s.require(isinstance(commit.get('files'),dict) and set(commit['files'])==expected,'Canonical evaluation inventory differs')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    s.require(actual==expected|{'EVALUATION_COMMIT.json'},'Unexpected or missing canonical evaluation payload')
    for relative in sorted(expected):
        payload=evaluation.safe_path(root,relative);record=commit['files'][relative]
        s.require(payload.is_file() and payload.stat().st_size==record['bytes'],'Canonical evaluation payload size changed: '+relative)
        digest=s.digest(payload);s.require(digest==record['sha256'],'Canonical evaluation payload changed: '+relative)
        watched[payload]=digest
    for key,name in (('release_sha256','EVALUATION_RELEASE.json'),('registration_sha256','EVALUATION_REGISTRATION.json'),('endpoint_lock_sha256','CONFIRMATION_ENDPOINT_LOCK.json')):
        s.require(commit[key]==s.digest(s.ROOT/name),'Canonical evaluation identity mismatch: '+key)
    watched[path]=h
    return commit,path


def load_canonical_test(population,seed,method,evaluation_commit,watched):
    filename=checked_data_path(population,'SEALED_test',watched)
    with np.load(filename,allow_pickle=False) as data:
        pop={key:data[key] for key in ('x','ids','kmeans_route')}
    path=s.ROOT/'confirmation_evaluation'/population/f'seed_{seed}'/method/'predictions.csv'
    relative=path.relative_to(s.ROOT/'confirmation_evaluation').as_posix();h=s.digest(path)
    s.require(h==evaluation_commit['files'][relative]['sha256'],'Canonical prediction file changed');watched[path]=h
    with path.open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    s.require(np.array_equal(np.array([int(r['record_id']) for r in rows]),pop['ids']),'Test record ordering mismatch')
    p=np.array([float(r['probability']) for r in rows]);z=np.array([float(r['native_logit']) for r in rows])
    return pop,p,z


def run(output):
    import evaluate_confirmation as evaluation
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    protocol=s.read_json(PROTOCOL)
    s.require(np.__version__=='2.5.4','Registered NumPy required')
    bench=protocol['benchmark'];tolerances=protocol['tolerances']
    s.require(bench['batch_sizes']==[1,32,1024] and bench['warmup_trials']==2 and bench['timed_trials']==15,'Benchmark budget differs from implementation')
    s.require(tolerances['probability_atol']==2e-12 and tolerances['logit_atol']==1e-9 and tolerances['class_ambiguity_band']==2e-12,'Parity tolerance mismatch')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        s.require(os.environ.get(key)=='1','One-thread environment required: '+key)
    reg,lock,release,watched=evaluation.verify_guard(output_must_be_absent=False)
    for path in (PROTOCOL,IMPLEMENTATION_NOTES,Path(__file__),s.ROOT/'deployment_compiler.py'):
        watched[path]=s.digest(path)
    notes=s.read_json(IMPLEMENTATION_NOTES)
    s.require(notes['status']=='REGISTERED_IMPLEMENTATION_BEFORE_DEPLOYMENT_RESULTS' and
              notes['added_representations']=={'trig_kmeans':'fast_trig','trig_global':'fast_trig'},'Deployment implementation memo differs')
    commit,commit_path=checked_evaluation_commit(evaluation,watched)
    isolation=[assert_quiescent()]
    output.mkdir(parents=True,exist_ok=False)
    s.write_json(output/'ACCESS_EVENT.json',{'created_utc':s.now(),'release_sha256':s.digest(s.ROOT/'EVALUATION_RELEASE.json'),
        'canonical_evaluation_commit_sha256':watched[commit_path],'scope':'Read test coordinates/IDs/routes and saved canonical outputs for same-checkpoint parity only; no label scoring or fitting.'},True)
    try:
        loaded={};compiled={};conversion=[];fast_trig=[];fixture={};load_records=[];router_loads=[];saved_outputs={};timings=[]
        for population in s.POPULATIONS['B']:
            checked_data_path(population,'validation',watched)
            validation=s.load_population(population,'validation')
            indices=np.argsort(validation['ids'],kind='stable')[:1024];fixture[population]=validation['x'][indices]
            policy_path=s.ROOT/'data'/f'{population}_router.json';start=time.perf_counter_ns();policy=s.read_json(policy_path)
            router_loads.append({'population':population,'load_ns':time.perf_counter_ns()-start,
                                 'policy_file_bytes':policy_path.stat().st_size,'centroid_float64_bytes':80,
                                 'scope':'One shared policy load, outside prediction latency and checkpoint load timings.'})
            watched[policy_path]=s.digest(policy_path)
            s.require(np.array_equal(validation['kmeans_route'],routers.route(validation['x'],policy,'kmeans')),'Validation cached routes differ from frozen policy')
            offgrid,boundary,edge_records=fixed_parity_inputs(policy)
            s.write_json(output/f'{population}_fixtures.json',{'benchmark_ids':validation['ids'][indices].tolist(),
                'offgrid_coordinates':offgrid.tolist(),'boundary_coordinates':boundary.tolist(),'boundary_definitions':edge_records,
                'boundary_routes':routers.route(boundary,policy,'kmeans').tolist()},True)
            for seed in s.SEEDS['B']:
                for method in s.METHODS:
                    folder,model,vp,vz,load_ns=checked_endpoint(population,seed,method,watched)
                    key=f'{population}__seed{seed}__{method}';loaded[key]=(model,policy)
                    load_records.append({'key':key,'representation':'circuit' if model.quantum else 'classical','load_ns':load_ns,
                        'checkpoint_file_bytes':(folder/'selected_checkpoint.npz').stat().st_size,'parameter_array_bytes':model.parameters.nbytes})
                    if method not in compiler.METHODS and method not in ('trig_kmeans','trig_global'):continue
                    start=time.perf_counter_ns()
                    if model.quantum:table,evidence=compiler.compile_model(method,model.parameters,True)
                    else:table=compiler.learned_trig_coefficients(method,model.parameters)
                    compile_ns=time.perf_counter_ns()-start
                    representation='compiled' if model.quantum else 'fast_trig'
                    artifact=output/(key+f'__{representation}.npz')
                    if model.quantum:
                        np.savez(artifact,coefficients=table,construction_grid=compiler.GRID,
                                 construction_logits=np.array([r['grid_logits'] for r in evidence]),
                                 construction_moments=np.array([r['grid_moments'] for r in evidence]))
                    else:np.savez(artifact,coefficients=table)
                    start=time.perf_counter_ns()
                    with np.load(artifact,allow_pickle=False) as f:table=f['coefficients'].copy()
                    table.setflags(write=False);compiled[key]=table;coefficient_load_ns=time.perf_counter_ns()-start
                    checks={};arrays={}
                    test,tp,tz=load_canonical_test(population,seed,method,commit,watched)
                    s.require(np.array_equal(test['kmeans_route'],routers.route(test['x'],policy,'kmeans')),'Test cached routes differ from frozen policy')
                    for name,x,route,reference_p,reference_z,ids in (
                            ('validation',validation['x'],validation['kmeans_route'],vp,vz,validation['ids']),
                            ('test',test['x'],test['kmeans_route'],tp,tz,test['ids'])):
                        p,z=compiler.predict_coefficients(x,table,None if model.routing=='global' else route);checks[name]=parity(p,z,reference_p,reference_z,ids)
                        arrays[name+'_probabilities']=p;arrays[name+'_logits']=z
                    for name,x in (('offgrid',offgrid),('router_boundary',boundary)):
                        route=None if model.routing=='global' else routers.route(x,policy,'kmeans');rp,rz=model.predict_with_logits(x,route)
                        p,z=compiler.predict_coefficients(x,table,route);checks[name]=parity(p,z,rp,rz)
                    forced=[]
                    for bank in range(len(table)):
                        route=None if model.routing=='global' else np.full(len(offgrid),bank);rp,rz=model.predict_with_logits(offgrid,route)
                        p,z=compiler.predict_coefficients(offgrid,table,route);forced.append(parity(p,z,rp,rz))
                    checks['forced_offgrid_banks']=forced
                    np.savez_compressed(output/(key+'__parity.npz'),**arrays)
                    record={'key':key,'representation':representation,'checkpoint_sha256':watched[folder/'selected_checkpoint.npz'],
                        'router_policy_sha256':watched[policy_path],'compiled_file':artifact.name,'compiled_sha256':s.digest(artifact),
                        'compile_ns':compile_ns,'compiled_load_ns':coefficient_load_ns,'coefficient_bytes':table.nbytes,
                        'compiled_file_bytes':artifact.stat().st_size,'original_parameter_bytes':model.parameters.nbytes,
                        'construction_statevector_examples':125 if model.quantum else 0,
                        'coefficient_operation':'forced-bank Fourier projection' if model.quantum else 'exact reshape/copy of trained coefficients; no fit',
                        'analytical_inference_work_per_record':compiler.inference_work(1,len(table)),'checks':checks}
                    (conversion if model.quantum else fast_trig).append(record)
        s.write_json(output/'conversion.json',conversion,True)
        s.write_json(output/'fast_trig.json',fast_trig,True)
        s.write_json(output/'load_measurements.json',load_records,True)
        s.write_json(output/'router_load_measurements.json',router_loads,True)
        # All conversion and parity work is complete before any timed trial.
        isolation.append(assert_quiescent())
        for pi,population in enumerate(s.POPULATIONS['B']):
            for si,seed in enumerate(s.SEEDS['B']):
                for size in (1,32,1024):
                    batches=trial_batches(fixture[population],size)
                    for trial in range(-2,15):
                        shift=(pi*len(s.SEEDS['B'])+si+trial+2)%len(s.METHODS)
                        order=s.METHODS[shift:]+s.METHODS[:shift]
                        if trial%2:order=order[::-1]
                        for method in order:
                            key=f'{population}__seed{seed}__{method}';model,policy=loaded[key]
                            representations=(['circuit','compiled'] if model.quantum else
                                             ['classical','fast_trig'] if method in ('trig_kmeans','trig_global') else ['classical'])
                            if len(representations)==2 and trial%2:representations=representations[::-1]
                            for representation in representations:
                                def forward(x):
                                    route=None if model.routing=='global' else routers.route(x,policy,'kmeans')
                                    return (compiler.predict_coefficients(x,compiled[key],route) if representation in ('compiled','fast_trig')
                                            else model.predict_with_logits(x,route))
                                elapsed,p,z=measure_trial(forward,batches)
                                output_key=key+f'__{representation}__batch{size}'
                                ph=s.array_digest(p);zh=s.array_digest(z)
                                if output_key not in saved_outputs:saved_outputs[output_key]=(p,z,ph,zh)
                                else:s.require((ph,zh)==saved_outputs[output_key][2:],'Timed prediction outputs changed across trials')
                                timings.append({'key':key,'population':population,'seed':seed,'method':method,'representation':representation,
                                    'batch_size':size,'trial':trial,'warmup':trial<0,'calls':len(batches),'prediction_records':len(p),
                                    'elapsed_ns':elapsed,'ns_per_record':elapsed/len(p),'probability_sha256':ph,'logit_sha256':zh})
        isolation.append(assert_quiescent())
        s.write_json(output/'timing_trials.json',timings,True);s.write_json(output/'isolation_checks.json',isolation,True)
        arrays={}
        for key,(p,z,_,_) in saved_outputs.items():arrays[key+'__p']=p;arrays[key+'__z']=z
        np.savez_compressed(output/'timing_output_examples.npz',**arrays)
        summary=[]
        for key in saved_outputs:
            chosen=[r for r in timings if r['key']+f'__{r["representation"]}__batch{r["batch_size"]}'==key and not r['warmup']]
            a=np.array([r['ns_per_record'] for r in chosen]);s.require(len(a)==15,'Incomplete timing trial set')
            first=chosen[0];summary.append({k:first[k] for k in ('key','population','seed','method','representation','batch_size')}|
                {'timed_repeats':15,'median_ns_per_record':float(np.median(a)),'q25_ns_per_record':float(np.quantile(a,.25)),
                 'q75_ns_per_record':float(np.quantile(a,.75))})
        for path,h in watched.items():s.require(s.digest(path)==h,'Bound deployment input changed')
        s.write_json(output/'summary.json',{'status':'PASS','compiled_checkpoints':len(conversion),'fast_trig_checkpoints':len(fast_trig),'selected_checkpoints':len(loaded),
            'timing_conditions':len(summary),'timed_trials':sum(not r['warmup'] for r in timings),'summaries':summary,
            'protocol_sha256':s.digest(PROTOCOL),'implementation_notes_sha256':s.digest(IMPLEMENTATION_NOTES),'source_hashes':{str(p):h for p,h in watched.items()},
            'scope':'Same-checkpoint float64 conversion. Technical timing repeats are not independent training seeds. No physical quantum speed claim.'},True)
        inventory={p.relative_to(output).as_posix():{'sha256':s.digest(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()}
        s.write_json(output/'DEPLOYMENT_COMMIT.json',{'status':'completed','created_utc':s.now(),'files':inventory},True)
        print('PASS deployment conversion and isolated benchmark')
    except BaseException as error:
        s.write_json(output/'FAILURE.json',{'status':'FAIL','created_utc':s.now(),'error':str(error),'traceback':traceback.format_exc()},True);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.output)
