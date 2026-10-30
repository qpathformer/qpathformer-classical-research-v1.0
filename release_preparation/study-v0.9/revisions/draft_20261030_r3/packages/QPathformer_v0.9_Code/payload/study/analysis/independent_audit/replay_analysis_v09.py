"""Independent post-release prediction, metrics, diagnostics and statistics replay.

No production model, evaluator, metric or statistics code is imported. Official
entry requires root release, complete636 audited B endpoints and scored payloads.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
import argparse,json,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import audit_endpoints_v09 as a
import reference_v09 as ref
import statistics_v09 as stats

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SOURCE_NAMES=('reference_v09.py','audit_endpoints_v09.py','statistics_v09.py','replay_analysis_v09.py')
PROTOCOLS={'study_plan':'governance/STUDY_PLAN.json','run_matrix':'governance/RUN_MATRIX.json',
           'analysis_protocol':'governance/ANALYSIS_PROTOCOL.json','data_seal':'quantum/data/DATA_SEAL.json'}

def verify(root,b):return a.inside(root,a.check_binding(b))

def verify_gate(root,authorization):
    root=Path(root).resolve();auth=a.read(authorization)
    a.need(auth.get('schema')=='qpath-v09-independent-analysis-release-1' and auth.get('review_status')=='approved_by_root' and
      auth.get('stage')=='B' and auth.get('action')=='independent_prediction_statistics','Independent root analysis release required')
    contract_path=verify(root,auth['independent_contract']);contract=a.read(contract_path)
    a.need(contract_path==root/'analysis/independent_audit/INDEPENDENT_ANALYSIS_CONTRACT.json','Wrong independent contract path')
    a.need(set(contract['source_bindings'])==set(SOURCE_NAMES),'Independent source inventory incomplete')
    for name,b in contract['source_bindings'].items():a.need(verify(root,b)==root/'analysis/independent_audit'/name,'Independent source location')
    release_path=verify(root,auth['evaluation_release']);release=a.read(release_path)
    a.need(release.get('schema')=='qpath-v09-evaluation-release-1' and release.get('review_status')=='approved_by_root' and release.get('stage')=='B','Official evaluation release missing')
    a.need(set(release['protocols'])==set(PROTOCOLS),'Evaluation protocol inventory incomplete');protocols={}
    for key,path in PROTOCOLS.items():
        p=verify(root,release['protocols'][key]);a.need(p==root/path,'Registered protocol path mismatch');protocols[key]=a.read(p)
    jobs=[j for j in protocols['run_matrix']['runs'] if j['stage']=='B'];ids={j['run_id'] for j in jobs}
    a.need(len(ids)==len(jobs)==636 and protocols['analysis_protocol']['confirmation_count']==636,'All636 confirmation jobs required')
    scientific=release['scientific_source_hashes']
    a.need(set(scientific)=={'models.py','study.py','circuits.py','reference_v03.py','prepare_data.py','routers.py','tests/test_v09_science.py'},'Scientific sources incomplete')
    for name,digest in scientific.items():a.need(a.sha(root/'quantum'/name)==digest,'Scientific source changed')
    a.need(set(release['evaluator_sources'])=={f'analysis/author/{n}' for n in ('metrics_v09.py','release_gate_v09.py','evaluate_v09.py','test_author_v09.py')},'Author source inventory')
    for name,digest in release['evaluator_sources'].items():a.need(a.sha(a.inside(root,root/name))==digest,'Author source changed')
    author=a.read(verify(root,release['author_audit']));independent=a.read(verify(root,release['independent_audit']))
    a.need(author.get('schema')=='qpath-v09-author-stage-audit-1' and independent.get('schema')=='qpath-v09-independent-endpoint-audit-1','Audit schema')
    for audit in (author,independent):a.need(audit.get('status')=='PASS' and audit.get('stage')=='B' and audit.get('verified_endpoints')==636 and
      audit.get('test_model_outcomes_accessed') is False and len(audit['endpoints'])==636 and {e['job_id'] for e in audit['endpoints']}==ids,'Audits incomplete or unsealed')
    a.need(independent['author_audit']==release['author_audit'] and independent['manifest']==author['manifest'],'Independent audit binds different evidence')
    manifest=a.read(verify(root,author['manifest']));a.need(manifest['stage']=='B' and manifest['jobs']==jobs and manifest['authorization']==author['authorization'],'Audited B manifest changed')
    freeze_path=verify(root,author['authorization']);freeze=a.read(freeze_path)
    a.need(freeze['stage']=='B' and freeze['review_status']=='approved_by_root' and freeze['run_ids']==[j['run_id'] for j in jobs] and freeze['scientific_source_hashes']==scientific,'Scientific freeze mismatch')
    for key,pk in (('matrix_sha256','run_matrix'),('protocol_sha256','study_plan'),('data_seal_sha256','data_seal')):
        a.need(freeze[key]==release['protocols'][pk]['sha256'],'Frozen protocol hash mismatch')
    maps=[{e['job_id']:e for e in group['endpoints']} for group in (author,independent,release)]
    a.need(all(set(m)==ids and len(g['endpoints'])==636 for m,g in zip(maps,(author,independent,release))),'Endpoint maps incomplete')
    for job in jobs:
        entries=[m[job['run_id']] for m in maps];entry=entries[0]
        for key in ('job_id','arm','population','seed','completed_rounds','optimizer_global_updates','selected_round','commit','selected_checkpoint'):
            a.need(all(e[key]==entry[key] for e in entries),'Auditors/release disagree '+key)
        a.need(entry['arm']==job['arm'] and entry['population']==job['population_id'] and entry['seed']==job['training_seed_id'] and
          entry['completed_rounds']==job['rounds']==200 and entry['optimizer_global_updates']==job['updates']==15000,'Incomplete endpoint recipe')
        cp=verify(root,entry['commit']);commit=a.read(cp);selected=verify(root,entry['selected_checkpoint'])
        a.need(cp.name=='endpoint_commit.json' and selected==cp.parent/'selected_checkpoint.npz','Endpoint path mismatch')
        a.need(commit.get('status')=='completed' and commit.get('schema')=='qpath-v09-endpoint-1' and commit['test_accessed'] is False and
          commit['stage']=='B' and commit['job_id']==job['run_id'] and commit['authorization_sha256']==a.sha(freeze_path),'Endpoint authority mismatch')
        for key in ('scientific_source_hashes','matrix_sha256','protocol_sha256','data_seal_sha256'):
            ck='source_hashes' if key=='scientific_source_hashes' else key;a.need(commit[ck]==freeze[key],'Commit source/protocol mismatch')
        a.need(set(commit['files'])=={p.name for p in cp.parent.iterdir() if p.is_file()}-{'endpoint_commit.json'},'Endpoint inventory mismatch')
        for name,b in commit['files'].items():
            a.need(Path(name).name==name,'Unsafe endpoint payload');p=cp.parent/name
            a.need(p.stat().st_size==b['bytes'] and a.sha(p)==b['sha256'],'Endpoint payload changed')
        a.need(commit['files']['selected_checkpoint.npz']=={k:entry['selected_checkpoint'][k] for k in ('sha256','bytes')},'Checkpoint hash mismatch')
    ec_path=verify(root,auth['author_evaluation_commit']);ec=a.read(ec_path)
    a.need(ec.get('schema')=='qpath-v09-author-evaluation-commit-1' and ec.get('status')=='PASS' and ec.get('scored_endpoints')==636 and
      ec['release']==auth['evaluation_release'] and ec['evaluator_sources']==release['evaluator_sources'],'Official scoring incomplete/different release')
    actual={p.relative_to(ec_path.parent).as_posix() for p in ec_path.parent.rglob('*') if p.is_file() and p!=ec_path}
    a.need(actual==set(ec['files']),'Official evaluation payload inventory mismatch')
    for name,b in ec['files'].items():
        p=a.inside(ec_path.parent,ec_path.parent/name);a.need(p.stat().st_size==b['bytes'] and a.sha(p)==b['sha256'],'Scored payload changed')
    return {'authorization':a.binding(authorization),'release':release,'protocols':protocols,'jobs':jobs,'entries':maps[0],
      'seal':protocols['data_seal'],'evaluation_root':ec_path.parent,'evaluation_commit':auth['author_evaluation_commit'],'contract':contract,
      'contract_binding':auth['independent_contract']}

class Comparisons:
    def __init__(self):self.count=0;self.maximum={}
    def array(self,actual,expected,category,tolerance):
        error=a.close(actual,expected,tolerance,category);self.count+=1;self.maximum[category]=max(self.maximum.get(category,0.),error)
    def tree(self,actual,expected,path='metric'):
        if isinstance(expected,dict):
            a.need(set(actual)==set(expected),path+' keys differ')
            for k,v in expected.items():self.tree(actual[k],v,path+'.'+k)
        elif isinstance(expected,list):
            a.need(len(actual)==len(expected),path+' length differs')
            for i,v in enumerate(expected):self.tree(actual[i],v,path+f'[{i}]')
        elif isinstance(expected,float):
            category='native_metric' if any(k in path for k in ('native','t_statistic')) else 'statistic' if any(k in path for k in ('critical_t','interval','two_sided','bonferroni')) else 'metric'
            self.array(actual,expected,category,1e-8 if category=='native_metric' else 1e-10 if category=='statistic' else 2e-12)
        else:a.need(actual==expected,path+' value differs');self.count+=1

def load_data(root,verified,pop,split,consumed):
    name=f"{pop}_{'SEALED_test' if split=='test' else split}.npz";path=root/'quantum/data'/name;seal=verified['seal']
    a.need(a.sha(path)==seal['files'][name]['sha256'],'Data hash mismatch');consumed[str(path)]=a.binding(path)
    with np.load(path,allow_pickle=False) as f:data={k:f[k] for k in f.files}
    policy_path=root/'quantum/data'/f'{pop}_router.json';a.need(a.sha(policy_path)==seal['routers'][pop]['sha256'],'Router hash mismatch');consumed[str(policy_path)]=a.binding(policy_path);policy=a.read(policy_path)
    a.need(len(data['y'])==seal['datasets'][pop]['counts'][split],'Data count mismatch')
    dist=np.sum((data['x'][:,None,:]-np.asarray(policy['centroids'])[None,:,:])**2,axis=2)
    a.exact(data['kmeans_route'],np.argmin(dist,axis=1),'Data geometry');sorted_d=np.sort(dist,axis=1)
    a.exact(data['margin_bin'],np.searchsorted(policy['margin_bins']['unique_edges'][1:-1],sorted_d[:,1]-sorted_d[:,0],side='right'),'Data margin bins')
    if 'raw_x' in data:
        a.close(data['x'],ref.preprocessing(data['raw_x'],policy,2),2e-14,'Independent preprocessing2')
        a.close(data['x4'],ref.preprocessing(data['raw_x'],policy,4),2e-14,'Independent preprocessing4')
    return data,policy

def weights(arm,theta,x,policy):
    if not arm.startswith(('C_','T_')):return np.ones((len(x),1))
    distance=np.sum((x[:,None,:]-np.asarray(policy['centroids'])[None,:,:])**2,axis=2)
    if arm[-1]=='H':return np.eye(5)[np.argmin(distance,axis=1)]
    logits=-distance/policy['tau']
    if arm[-1]=='L':logits[:,:4]+=np.einsum('ni,ji->nj',np.c_[x,np.ones(len(x))],theta[ref.sizes(arm)[0]:].reshape(4,3))
    return np.exp(logits-ref.lse(logits,axis=1)[:,None])

def slices(data,p,z,policy):
    def metric(mask):return stats.metrics(data['y'][mask],p[mask],z[mask])
    return {'classes':[{'label':k,'metrics':metric(data['y']==k)} for k in (0,1)],
      'fixed_geometric_banks':[{'bank':k,'metrics':metric(data['kmeans_route']==k)} for k in range(5)],
      'fixed_geometry_margin_bins':[{'bin':k,'metrics':metric(data['margin_bin']==k)} for k in range(policy['margin_bins']['bins'])],
      'margin_definition':policy['margin_bins'],'interpretation':'Slices use common training-fitted geometry for every arm; class/slice metrics are descriptive.'}

def bank_diagnostics(arm,y,q,expert_z):
    entropy=-np.sum(np.where(q>0,q*np.log(np.maximum(q,np.finfo(float).tiny)),0.),axis=1);conditional=[]
    positive=ref.sigmoid(expert_z);common=np.where(y[:,None]==1,-np.log(np.clip(positive,1e-7,1-1e-7)),-np.log1p(-np.clip(positive,1e-7,1-1e-7)))
    native=np.where(y[:,None]==1,np.logaddexp(0,-expert_z),np.logaddexp(0,expert_z))
    for label in (0,1):
        mask=y==label
        for bank in range(q.shape[1]):
            mass=float(q[mask,bank].sum())
            conditional.append({'label':label,'bank':bank,'record_count':int(mask.sum()),'weight_mass':mass,
              'native_expert_bce':float(np.dot(q[mask,bank],native[mask,bank])/mass) if mass else None,
              'common_expert_bce':float(np.dot(q[mask,bank],common[mask,bank])/mass) if mass else None})
    result={'bank_count':q.shape[1],'mean_weights':q.mean(0).tolist(),'argmax_occupancy':np.bincount(q.argmax(1),minlength=q.shape[1]).tolist(),
      'mean_entropy':float(entropy.mean()),'mean_effective_experts':float(np.exp(entropy).mean()),'class_conditional_weight_and_expert_loss':conditional,
      'interpretation':'Selected-state descriptive weights and expert losses. These are not historical training exposure or mixture-loss decomposition.'}
    if arm.endswith('_L'):
        z=expert_z[np.arange(len(y)),q.argmax(1)];result['postfit_argmax_gate']={'metrics':stats.metrics(y,ref.sigmoid(z),z),
          'interpretation':'Diagnostic replacement of the selected soft gate by its argmax; no retraining or reselection.'}
    return result

def training_exposure(arm,theta,train,policy,endpoint):
    visits=np.load(endpoint/'training_record_exposure.npy',allow_pickle=False);a.need(visits.sum()==960000,'Incomplete exposure');y=train['y'];x=train['x']
    if not arm.endswith('_L'):
        q=weights(arm,theta,x,policy);exposure=np.stack([np.sum(q*(visits*(y==k))[:,None],axis=0) for k in (0,1)])
        return {'class_bank_weighted_visits':exposure.tolist(),'total_visits':960000,'replayed_gate_updates':0,
          'scope':'Exact saved sampler counts with the fixed training gate; uniform sampling with replacement.'}
    order=np.load(endpoint/'record_orders.npy',mmap_mode='r',allow_pickle=False);g=np.load(endpoint/'minibatch_gradients.npy',mmap_mode='r',allow_pickle=False);rounds=np.load(endpoint/'round_parameters.npy',mmap_mode='r',allow_pickle=False)
    base=-np.sum((x[:,None,:]-np.asarray(policy['centroids'])[None,:,:])**2,axis=2)/policy['tau'];phi=np.c_[x,np.ones(len(x))]
    coefficient=np.zeros(12);m=np.zeros(12);v=np.zeros(12);exposure=np.zeros((2,5));expert=ref.sizes(arm)[0]
    for t in range(15000):
        ids=order[t//75,(t%75)*64:(t%75+1)*64];z=base[ids].copy();z[:,:4]+=np.einsum('ni,ji->nj',phi[ids],coefficient.reshape(4,3));q=np.exp(z-ref.lse(z,axis=1)[:,None])
        for label in (0,1):exposure[label]+=q[y[ids]==label].sum(0)
        if t>=750:coefficient,m,v=ref.adam(coefficient,g[t,expert:],m,v,t-749,.001)
        if (t+1)%75==0:a.close(coefficient,rounds[t//75,expert:],1e-8,'Independent historical gate Adam')
    a.need(abs(float(exposure.sum())-960000)<1e-5,'Historical exposure mass')
    return {'class_bank_weighted_visits':exposure.tolist(),'total_visits':960000,'replayed_gate_updates':14250,
      'scope':'Actual pre-update gate weights on saved sampled batches; gate-only Adam replay verified against every saved round. No model refit.'}

def milestones(endpoint):
    lines=[json.loads(l) for l in (endpoint/'rounds.jsonl').read_text().splitlines()];a.need(len(lines)==200,'Incomplete validation curve');result=[]
    for threshold in (.90,.95,.97):
        hit=next((l for l in lines if l['validation']['macro_f1']>=threshold),None)
        result.append({'threshold':threshold,'reached':hit is not None,'first_observed_round':hit['round'] if hit else None,
          'first_observed_updates':hit['optimizer_updates'] if hit else None,'first_observed_elapsed_seconds':hit['elapsed_seconds'] if hit else None})
    return result

def replay(root,authorization,output):
    root=Path(root).resolve();output=a.inside(root,output);a.need(root==ROOT and not output.exists(),'Official root/new output required')
    verified=verify_gate(root,authorization);start=time.perf_counter();cpu=time.process_time();output.mkdir(parents=True,exist_ok=False)
    a.write_new(output/'REPLAY_STARTED.json',{'utc':datetime.now(timezone.utc).isoformat(),'authorization':verified['authorization'],'author_commit':verified['evaluation_commit']})
    try:
        evaluation=verified['evaluation_root'];author_rows=a.read(evaluation/'ENDPOINT_RESULTS.json')
        a.need(len(author_rows)==636 and {r['job_id'] for r in author_rows}=={j['run_id'] for j in verified['jobs']},'Author scored rows incomplete')
        rowmap={r['job_id']:r for r in author_rows};comp=Comparisons();popcache={};consumed={};rows=[];proofs=[]
        for job in verified['jobs']:
            identity=job['run_id'];entry=verified['entries'][identity];endpoint=Path(entry['endpoint']);saved=rowmap[identity];arm=job['arm'];pop=job['population_id']
            if pop not in popcache:popcache[pop]={split:load_data(root,verified,pop,split,consumed) for split in ('train','validation','test')}
            with np.load(entry['selected_checkpoint']['path'],allow_pickle=False) as f:
                theta=f['parameters'];a.need(int(f['current_round'])==entry['selected_round'],'Selected checkpoint round mismatch')
            prediction_path=evaluation/'endpoints'/(identity.replace('/','__')+'.npz')
            with np.load(prediction_path,allow_pickle=False) as f:predictions={k:f[k] for k in f.files}
            row={'job_id':identity,'family':job['family'],'population':pop,'seed':job['training_seed_id'],'arm':arm};near=0
            for split,(data,policy) in popcache[pop].items():
                x=data['x4'] if arm=='MLP4' else data['x'];f=ref.forward(arm,theta,x,policy);p,z=f['p'],f['z']
                sp,sz=predictions[split+'_probabilities'],predictions[split+'_logits'];q=weights(arm,theta,x,policy);expert_z=f['zs'] if arm.startswith(('C_','T_')) else z[:,None]
                comp.array(sp,p,'prediction_probability',2e-12);comp.array(sz,z,'prediction_logit',1e-9)
                comp.array(predictions[split+'_weights'],q,'gate_weights',2e-12);comp.array(predictions[split+'_expert_logits'],expert_z,'expert_logits',1e-9)
                for name,field in (('ids','ids'),('labels','y'),('margin_bin','margin_bin'),('geometric_route','kmeans_route')):a.exact(predictions[split+'_'+name],data[field],'Prediction aligned '+field)
                changed=(sp>=.5)!=(p>=.5);a.need(np.all(~changed|((abs(sp-.5)<=a.TOLERANCES['threshold_band'])&(abs(p-.5)<=a.TOLERANCES['threshold_band']))),'Threshold disagreement outside band');near+=int(changed.sum())
                row[split]=stats.metrics(data['y'],sp,sz);comp.tree(saved[split],row[split]);comp.tree(saved[split+'_slices'],slices(data,sp,sz,policy))
                comp.tree(saved[split+'_bank_diagnostics'],bank_diagnostics(arm,data['y'],predictions[split+'_weights'],predictions[split+'_expert_logits']))
            if job['family']=='annulus':
                meta=verified['seal']['diagnostics'][pop];path=root/'quantum/data'/meta['file'];a.need(a.sha(path)==meta['sha256'],'Latent diagnostic hash mismatch');consumed[str(path)]=a.binding(path)
                with np.load(path,allow_pickle=False) as latent:
                    a.exact(latent['test_ids'],predictions['test_ids'],'Latent IDs');clean=latent['test_clean_y'];flipped=latent['test_label_flip'].astype(bool)
                a.exact(clean,predictions['test_clean_y'],'Clean labels');a.exact(flipped,predictions['test_label_flip'],'Flip flags')
                sp,sz=predictions['test_probabilities'],predictions['test_logits'];labels=predictions['test_labels']
                comp.tree(saved['annulus_clean_label_test'],stats.metrics(clean,sp,sz))
                comp.tree(saved['annulus_flip_strata'],[{'flipped':bool(f),'observed':stats.metrics(labels[flipped==f],sp[flipped==f],sz[flipped==f]),
                  'clean':stats.metrics(clean[flipped==f],sp[flipped==f],sz[flipped==f])} for f in (False,True)])
            exposure=training_exposure(arm,theta,*popcache[pop]['train'],endpoint)
            # Large accumulated exposure counts have an absolute 1e-6 audit tolerance.
            comp.array(saved['actual_training_gate_exposure']['class_bank_weighted_visits'],exposure['class_bank_weighted_visits'],'historical_gate_exposure',1e-6)
            for k in ('total_visits','replayed_gate_updates','scope'):a.need(saved['actual_training_gate_exposure'][k]==exposure[k],'Exposure descriptor mismatch')
            row['validation_milestones']=milestones(endpoint);comp.tree(saved['validation_milestones'],row['validation_milestones'])
            result=a.read(endpoint/'result.json')
            for key,value in saved['costs'].items():
                expected=entry['selected_checkpoint']['bytes'] if key=='checkpoint_bytes' else sum(b['bytes'] for b in a.read(endpoint/'endpoint_commit.json')['files'].values()) if key=='endpoint_payload_bytes' else result[key]
                comp.tree(value,expected,'costs.'+key)
            rows.append(row);proofs.append({'job_id':identity,'selected_checkpoint':entry['selected_checkpoint'],'author_prediction_file':a.binding(prediction_path),
              'threshold_band_disagreements':near,'historical_gate_updates_replayed':exposure['replayed_gate_updates']})
            print(json.dumps({'independently_replayed':len(rows),'required':636,'job_id':identity}),flush=True)
        statistics=stats.analyze(rows,verified['protocols']['analysis_protocol']);comp.tree(a.read(evaluation/'STATISTICAL_ANALYSIS.json'),statistics,'statistics')
        milestones_summary=[]
        for family,arm in sorted({(r['family'],r['arm']) for r in rows}):
            selected=[r for r in rows if (r['family'],r['arm'])==(family,arm)]
            for k,threshold in enumerate((.90,.95,.97)):
                mm=[r['validation_milestones'][k] for r in selected]
                milestones_summary.append({'family':family,'arm':arm,'threshold':threshold,'n':len(mm),'never':sum(not x['reached'] for x in mm),
                  'reached_updates':stats.distribution([x['first_observed_updates'] for x in mm]),'limitation':'Descriptive validation observations at round boundaries; not test performance, early stopping or reselection.'})
        comp.tree(a.read(evaluation/'VALIDATION_MILESTONES.json'),milestones_summary,'milestones')
        for b in consumed.values():a.check_binding(b)
        for b in verified['contract']['source_bindings'].values():a.check_binding(b)
        a.check_binding(verified['authorization']);a.check_binding(verified['evaluation_commit'])
        # Rehash every authority, selected endpoint and committed scoring payload
        # again before writing a success receipt; no mutation race is accepted.
        final_gate=verify_gate(root,authorization)
        a.need(final_gate['authorization']==verified['authorization'] and final_gate['evaluation_commit']==verified['evaluation_commit'],'Gate changed during independent replay')
        a.write_new(output/'INDEPENDENT_METRICS.json',rows);a.write_new(output/'INDEPENDENT_STATISTICS.json',statistics)
        report={'schema':'qpath-v09-independent-analysis-1','status':'PASS','utc':datetime.now(timezone.utc).isoformat(),'verified_endpoints':636,
          'authorization':verified['authorization'],'author_evaluation_commit':verified['evaluation_commit'],'contract':verified['contract_binding'],
          'endpoints':proofs,'comparisons':comp.count,'maximum_absolute_discrepancies':comp.maximum,
          'primary_independent_populations':8,'paired_seeds_per_population':2,'primary_contrasts':12,
          'threshold_band_disagreements':sum(p['threshold_band_disagreements'] for p in proofs),'training_performed':False,
          'prediction_oracle':'Independently qualified full tensor circuit/trigonometric/global implementation; no producer numerical imports.',
          'statistics_oracle':'Independent metric functions, tie-histogram AP, fsum population summaries, incomplete-beta t7 probabilities and bisection quantiles.',
          'metric_scope':'Metrics replay uses saved probabilities after independent numerical parity; bounded threshold-rounding disagreements retained. No reselection.',
          'scope':'All636selected checkpoints, alltrain/validation/test predictions and metrics, declared slices, bankweights/expertloss/argmax, historicalexposure, annuluslatentdiagnostics, milestones, allregisteredcontrasts and descriptiveBanknote.',
          'wall_seconds':time.perf_counter()-start,'process_cpu_seconds':time.process_time()-cpu}
        a.write_new(output/'INDEPENDENT_REPLAY.json',report)
        files={p.relative_to(output).as_posix():{k:a.binding(p)[k] for k in ('sha256','bytes')} for p in output.rglob('*') if p.is_file()}
        commit={'schema':'qpath-v09-independent-analysis-commit-1','status':'PASS','verified_endpoints':636,'files':files,
          'authorization':verified['authorization'],'author_evaluation_commit':verified['evaluation_commit'],'contract':verified['contract_binding']}
        a.write_new(output/'INDEPENDENT_ANALYSIS_COMMIT.json',commit);return a.binding(output/'INDEPENDENT_ANALYSIS_COMMIT.json')
    except BaseException as error:
        a.write_new(output/'INDEPENDENT_REPLAY_FAILURE.json',{'utc':datetime.now(timezone.utc).isoformat(),'error':repr(error),'traceback':traceback.format_exc(),'automatic_retry':False});raise

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--authorization',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    sys.path.insert(0,str(ROOT/'execution'));import durable,resource_probe
    env=resource_probe.inspect();a.need(env['python']=='3.12.14' and env['numpy_version']=='2.5.4' and env['effective_blas_threads']==1,'Registered runtime required')
    with durable.auxiliary_lease(ROOT,'audit'):result=replay(ROOT,args.authorization,args.output)
    print(json.dumps(result))
if __name__=='__main__':main()
