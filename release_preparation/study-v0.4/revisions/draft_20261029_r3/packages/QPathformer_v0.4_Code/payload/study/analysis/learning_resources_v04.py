"""Post-audit validation learning and recorded-resource summaries. No test loader.

Both successful full-stage endpoint audits are required. This reads already
committed measurements; it neither evaluates models nor changes selection.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,json,statistics,traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'quantum'
METHODS=('q2_global','q2_hash','q2_kmeans','mlp_global','mlp_hash','mlp_kmeans','trig_global','trig_hash','trig_kmeans')
SEEDS={'A':(701,702,703),'B':(801,802,803,804,805)}
POPULATIONS={'A':('development_circle','development_ellipse'),'B':('confirmation_circle_1','confirmation_circle_2','confirmation_ellipse')}

def need(value,message):
    if not value:raise RuntimeError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,obj):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
def read_bound(path):
    before=sha(path);obj=read(path);need(sha(path)==before,'Metadata changed while read');return obj,before

def mapped_historical_path(recorded,original_root):
    """Resolve a declared original-root artifact into this checkout without edits."""
    original_root=Path(original_root).resolve();recorded=Path(recorded)
    need(recorded.is_absolute(),'Historical artifact path must be absolute')
    original_path=recorded.resolve()
    need(original_path.is_relative_to(original_root),'Historical artifact outside declared working root')
    relative=original_path.relative_to(original_root)
    need('..' not in relative.parts,'Unsafe historical artifact path')
    current=(ROOT/relative).resolve();need(current.is_relative_to(ROOT.resolve()),'Remapped artifact escapes current root')
    return current

def endpoint_folder(stage,row,original_root):
    need(stage in SEEDS and row['population'] in POPULATIONS[stage] and row['seed'] in SEEDS[stage] and row['method'] in METHODS,'Unregistered endpoint identity')
    current=(Q/f'stage_{stage}'/row['population']/f"seed_{row['seed']}"/row['method']).resolve()
    need(mapped_historical_path(row['path'],original_root)==current,'Historical endpoint path/identity mismatch')
    return current

def milestones(values,elapsed=None,threshold=.97,cadence=75,consecutive=3):
    """Keep first crossing separate from the first completed qualifying streak."""
    values=np.asarray(values,dtype=float)
    need(values.ndim==1 and len(values)>0 and np.isfinite(values).all() and np.all((values>=0)&(values<=1)),'Invalid milestone values')
    need(isinstance(cadence,int) and cadence>0 and isinstance(consecutive,int) and consecutive>0,'Invalid milestone protocol')
    if elapsed is not None:
        elapsed=np.asarray(elapsed,float);need(elapsed.shape==values.shape and np.isfinite(elapsed).all() and np.all(np.diff(elapsed)>=0) and elapsed[0]>=0,'Invalid elapsed history')
    first=None;confirmed=None;sequence_start=None;streak=0
    for index,value in enumerate(values):
        if value>=threshold:
            if first is None:first=index+1
            streak+=1
            if streak==consecutive and confirmed is None:confirmed=index+1;sequence_start=confirmed-consecutive+1
        else:streak=0
    return {'threshold':threshold,'cadence_updates':cadence,'confirmation_checks':consecutive,
       'first_round':first,'first_update':None if first is None else first*cadence,
       'first_elapsed_seconds':None if first is None or elapsed is None else float(elapsed[first-1]),
       'confirmed_sequence_start_round':sequence_start,'confirmed_sequence_start_update':None if sequence_start is None else sequence_start*cadence,
       'confirmed_round':confirmed,'confirmed_update':None if confirmed is None else confirmed*cadence,
       'confirmed_elapsed_seconds':None if confirmed is None or elapsed is None else float(elapsed[confirmed-1]),
       'horizon_rounds':len(values),'horizon_updates':len(values)*cadence,
       'first_reached':first is not None,'confirmed_reached':confirmed is not None,
       'final_macro_f1':float(values[-1])}

def finite_summary(values):
    values=list(map(float,values));need(values and np.isfinite(values).all(),'Empty/nonfinite summary')
    return {'n':len(values),'mean':statistics.mean(values),'sample_sd':statistics.stdev(values) if len(values)>1 else None,
            'median':statistics.median(values),'minimum':min(values),'maximum':max(values)}
def reaching_summary(rows,prefix):
    reached=[r['milestones'][prefix+'_update'] for r in rows if r['milestones'][prefix+'_reached']]
    return {'total_runs':len(rows),'reached':len(reached),'not_reached':len(rows)-len(reached),
       'horizon_updates':15000,'conditional_update_summary':finite_summary(reached) if reached else None,
       'scope':'Reached-only summary; nonreachers remain counted/censored at15000, never imputed as success.'}

def input_gate(stage,author_path,independent_path):
    need(stage in SEEDS,'Unregistered stage');author_path=Path(author_path).resolve();independent_path=Path(independent_path).resolve()
    expected_lock=Q/('STAGE_A_ENDPOINT_LOCK.json' if stage=='A' else 'CONFIRMATION_ENDPOINT_LOCK.json')
    need(author_path==expected_lock.resolve(),'Canonical author lock required')
    need(independent_path.is_relative_to(ROOT.resolve()),'Independent audit must be inside study root')
    author,ah=read_bound(author_path);independent,ih=read_bound(independent_path)
    freeze_path=Q/f'STAGE_{stage}_FREEZE.json';freeze,fh=read_bound(freeze_path)
    protocol_path=ROOT/'governance/ANALYSIS_PROTOCOL.json';protocol,ph=read_bound(protocol_path)
    plan_path=ROOT/'governance/STUDY_PLAN.json';plan,plan_sha=read_bound(plan_path);original_root=Path(plan['working_root'])
    seal_path=Q/'data/DATA_SEAL.json';seal,dh=read_bound(seal_path)
    count=len(SEEDS[stage])*len(POPULATIONS[stage])*9
    for obj in (author,independent):need(obj['status']=='PASS' and obj['stage']==stage and obj['engineering'] is False and obj['endpoint_count']==count,'Successful full official audits required')
    need(independent['endpoint_lock_sha256']==ah and independent['data_seal_sha256']==author['data_seal_sha256']==dh,'Audit lock/data mismatch')
    need(author['stage_freeze_sha256']==fh and freeze['review_status']=='approved_by_root','Stage freeze mismatch')
    need(author['analysis_protocol_sha256']==independent['analysis_protocol_sha256']==ph,'Analysis protocol binding mismatch')
    need(independent['validation_rounds_replayed']==count*200,'Every validation round must be independently verified')
    need(protocol['milestones']['threshold']==.97 and protocol['milestones']['cadence_updates']==75 and protocol['milestones']['confirmation_checks']==3,'Milestone protocol differs')
    auditor=ROOT/'analysis/classical_review/audit_endpoints_v04.py';need(independent['auditor_sha256']==sha(auditor),'Independent auditor changed')
    watched={author_path:ah,independent_path:ih,freeze_path:fh,protocol_path:ph,plan_path:plan_sha,seal_path:dh,auditor:sha(auditor),Path(__file__):sha(__file__)}
    for name,h in independent['independent_source_sha256'].items():
        path=auditor.parent/name;need(sha(path)==h,'Independent oracle changed');watched[path]=h
    need(author['source_hashes']==freeze['source_hashes'],'Frozen source identity differs')
    for name,h in freeze['source_hashes'].items():
        path=Q/name;need(sha(path)==h,'Frozen training source changed');watched[path]=h
    for name,h in author['audit_source_hashes'].items():
        path=mapped_historical_path(name,original_root);need(sha(path)==h,'Author audit changed');watched[path]=h
    expected={(p,s,m) for p in POPULATIONS[stage] for s in SEEDS[stage] for m in METHODS}
    ar={(r['population'],r['seed'],r['method']):r for r in author['endpoints']}
    ir={(r['population'],r['seed'],r['method']):r for r in independent['endpoints']}
    need(len(author['endpoints'])==len(independent['endpoints'])==count and set(ar)==set(ir)==expected,'Endpoint inventory differs')
    status_path=Q/f'stage_{stage}/stage_status.json';status,sh=read_bound(status_path);watched[status_path]=sh
    need(status['status']=='completed' and status['committed_endpoints']==count and sorted((r['seed'],r['exit_code']) for r in status['exits'])==[(s,0) for s in SEEDS[stage]],'Stage workers not complete')
    for key,row in ar.items():
        pop,seed,method=key;folder=endpoint_folder(stage,row,original_root)
        commit_path=folder/'endpoint_commit.json';commit,ch=read_bound(commit_path);watched[commit_path]=ch
        need(ch==row['endpoint_commit_sha256']==ir[key]['endpoint_commit_sha256'],'Audited endpoint commit differs')
        need(commit['files']==row['files'] and row['rounds']==200 and row['optimizer_updates']==15000,'Author endpoint evidence differs')
        need({p.name for p in folder.iterdir() if p.is_file() and p.name!='endpoint_commit.json'}==set(commit['files']),'Endpoint inventory changed')
        for name,item in commit['files'].items():
            need(Path(name).name==name,'Unsafe endpoint payload name');path=folder/name
            need(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'Endpoint payload changed');watched[path]=item['sha256']
    return author,independent,seal,status,watched,original_root

def endpoint_summary(stage,row,original_root):
    folder=endpoint_folder(stage,row,original_root);result=read(folder/'result.json');config=read(folder/'config.json')
    ledger=[json.loads(line) for line in (folder/'ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    need(len(ledger)==200 and [r['round'] for r in ledger]==list(range(1,201)) and [r['optimizer_updates'] for r in ledger]==list(range(75,15001,75)),'Incomplete validation history')
    milestone=milestones([r['validation']['macro_f1'] for r in ledger],[r['elapsed_seconds'] for r in ledger])
    selected=int(result['selected_round']);need(1<=selected<=200,'Invalid selection')
    with np.load(folder/'round_gradient_means.npz',allow_pickle=False) as f:mean_vectors=np.asarray(f['gradients'])
    need(mean_vectors.shape==(200,result['parameter_count']) and np.isfinite(mean_vectors).all(),'Invalid gradient diagnostic history')
    norms=np.linalg.norm(mean_vectors,axis=1);indices={'first':0,'selected':selected-1,'last':199}
    gradients={name:{'round':index+1,'mean_batch_gradient_norm':ledger[index]['mean_batch_gradient_norm'],
                    'maximum_batch_gradient_norm':ledger[index]['maximum_batch_gradient_norm'],
                    'norm_of_mean_batch_gradient_vector':float(norms[index])} for name,index in indices.items()}
    gradients['selected_full_training_gradient_norm']=result['selected_training_gradient_norm']
    gradients['scope']='Stored diagnostics from training batches/selected checkpoint; gradient cancellation can make norm(mean vector) smaller than mean(norm). No independent optimizer rerun.'
    fullwork={**result['work'],'inference_four_uncached':result['inference']['work_four_uncached_forwards'],
              'inference_fifth_cached':result['inference']['work_fifth_cached_comparison']}
    return {'stage':stage,'population':row['population'],'seed':row['seed'],'method':row['method'],
       'endpoint_commit_sha256':row['endpoint_commit_sha256'],'selected_checkpoint_sha256':row['files']['selected_checkpoint.npz']['sha256'],
       'ledger_sha256':row['files']['ledger.jsonl']['sha256'],'selected_round':selected,'selected_update':75*selected,
       'selected_validation':result['selected_validation'],'selected_training':result['selected_training'],
       'first_validation':ledger[0]['validation'],'final_validation':ledger[-1]['validation'],'milestones':milestone,
       'gradients':gradients,'parameter_count':result['parameter_count'],'bank_count':result['bank_count'],
       'parameters_per_bank':result['parameters_per_bank'],'train_bank_counts':result['train_bank_counts'],
       'bank_training_record_visits':result['bank_training_record_visits'],'validation_route_counts':result['validation_route_counts'],
       'training_records_seen':200*4800,'validation_records_seen':200*1600,'optimizer_updates':15000,
       'training_clipped_probability_visits':result['training_clipped_probabilities'],
       'training_clipped_probability_fraction':result['training_clipped_probabilities']/(200*4800),
       'work_by_phase':fullwork,'preparation':result['preparation'],
       'timing':{'training_loop_seconds':result['training_seconds'],'charged_training_loop_seconds':result['charged_training_seconds'],
                 'endpoint_timer_seconds':result['endpoint_total_seconds'],'inference_seconds_per_record':result['inference']['mean_seconds_per_record'],
                 'inference_total_repeat_seconds':result['inference']['total_repeat_seconds'],'inference_route_repeat_seconds':result['inference']['route_repeat_seconds']},
       'source_hashes':config['source_hashes'],'test_accessed':False}

def aggregate(rows):
    result={}
    for method in METHODS:
        cells=[r for r in rows if r['method']==method];work={}
        for row in cells:
            for phase,counters in row['work_by_phase'].items():
                dest=work.setdefault(phase,{})
                for key,value in counters.items():dest[key]=dest.get(key,0)+value
        result[method]={'n':len(cells),'seeds':[r['seed'] for r in cells],
          'selected_round':finite_summary(r['selected_round'] for r in cells),
          'selected_validation':{k:finite_summary(r['selected_validation'][k] for r in cells) for k in ('bce','macro_f1','accuracy')},
          'final_validation':{k:finite_summary(r['final_validation'][k] for r in cells) for k in ('bce','macro_f1','accuracy')},
          'first97':reaching_summary(cells,'first'),'confirmed97':reaching_summary(cells,'confirmed'),
          'timing':{k:finite_summary(r['timing'][k] for r in cells) for k in ('training_loop_seconds','charged_training_loop_seconds','endpoint_timer_seconds','inference_seconds_per_record')},
          'sum_recorded_work_by_phase':work,
          'sum_training_record_visits':sum(r['training_records_seen'] for r in cells),
          'sum_validation_record_visits':sum(r['validation_records_seen'] for r in cells),
          'sum_training_clipped_probability_visits':sum(r['training_clipped_probability_visits'] for r in cells)}
    return result

def write_csv(path,rows):
    names=('population','seed','method','selected_round','selected_update','first97_update','confirmed97_sequence_start_update',
       'confirmed97_update','not_first97_reached','not_confirmed97_reached','selected_validation_bce','selected_validation_macro_f1',
       'final_validation_bce','final_validation_macro_f1','training_loop_seconds','charged_training_loop_seconds',
       'endpoint_timer_seconds','inference_seconds_per_record','parameter_count','bank_count','training_record_visits',
       'validation_record_visits','training_clipped_probability_visits','bank_training_record_visits','endpoint_commit_sha256','selected_checkpoint_sha256')
    with Path(path).open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=names);writer.writeheader()
        for r in rows:
            m=r['milestones'];writer.writerow({**{k:r[k] for k in ('population','seed','method','selected_round','selected_update','parameter_count','bank_count','training_clipped_probability_visits','endpoint_commit_sha256','selected_checkpoint_sha256')},
             'first97_update':m['first_update'],'confirmed97_sequence_start_update':m['confirmed_sequence_start_update'],'confirmed97_update':m['confirmed_update'],
             'not_first97_reached':not m['first_reached'],'not_confirmed97_reached':not m['confirmed_reached'],
             'selected_validation_bce':r['selected_validation']['bce'],'selected_validation_macro_f1':r['selected_validation']['macro_f1'],
             'final_validation_bce':r['final_validation']['bce'],'final_validation_macro_f1':r['final_validation']['macro_f1'],
             **{k:r['timing'][k] for k in ('training_loop_seconds','charged_training_loop_seconds','endpoint_timer_seconds','inference_seconds_per_record')},
             'training_record_visits':r['training_records_seen'],'validation_record_visits':r['validation_records_seen'],
             'bank_training_record_visits':json.dumps(r['bank_training_record_visits'])})

def run(stage,author_path,independent_path,output):
    output=Path(output);need(not output.exists(),'Preserve prior analysis; output must be absent')
    author,independent,seal,status,watched,original_root=input_gate(stage,author_path,independent_path)
    output.mkdir(parents=True,exist_ok=False)
    try:
        rows=[endpoint_summary(stage,row,original_root) for row in author['endpoints']]
        populations={}
        for pop in POPULATIONS[stage]:
            cells=[r for r in rows if r['population']==pop];value={'population':pop,'stage':stage,'endpoint_count':len(cells),'methods':aggregate(cells),'endpoints':cells}
            write(output/(pop+'.json'),value);write_csv(output/(pop+'.csv'),cells);populations[pop]=value['methods']
        write_csv(output/'endpoint_metrics.csv',rows)
        result={'status':'PASS','stage':stage,'created_utc':datetime.now(timezone.utc).isoformat(),'endpoint_count':len(rows),
          'source_sha256':sha(__file__),'author_audit_sha256':sha(author_path),'independent_audit_sha256':sha(independent_path),
          'analysis_protocol_sha256':sha(ROOT/'governance/ANALYSIS_PROTOCOL.json'),'data_seal_sha256':sha(Q/'data/DATA_SEAL.json'),
          'path_handling':{'declared_original_working_root':str(original_root),'current_analysis_root':str(ROOT),'rule':'Historical absolute endpoint/source paths validated against original STUDY_PLAN working_root and remapped by study-relative identity; metadata bytes unchanged.'},
          'stage_execution_observed_wall_seconds':status['observed_wall_seconds'],
          'sum_endpoint_training_loop_seconds':sum(r['timing']['training_loop_seconds'] for r in rows),
          'sum_endpoint_charged_training_loop_seconds':sum(r['timing']['charged_training_loop_seconds'] for r in rows),
          'sum_endpoint_timer_seconds':sum(r['timing']['endpoint_timer_seconds'] for r in rows),
          'populations':populations,'preparation_actual_recorded_by_population':{p:seal['datasets'][p] for p in POPULATIONS[stage]},
          'scope':['Validation learning only; all200rounds/15000updates actually completed. No model test outcomes or early-checkpoint test evaluation.',
          'First threshold crossing and first completed three-check streak are different. Confirmation is150updates after its own qualifying sequence start, not necessarily150after first-ever crossing.',
          'Nonreachers counted and censored; reached-only medians are conditional and not estimates for allruns. No earlystopping savings are claimed.',
          'Selected checkpoint minimizes validationBCE; its validationF1 is not a separate best-F1 selection.',
          'Training loop timer covers batchtraining,allvalidation,and within-loop checkpoint/evidence work. Initial data/model setup excluded; endpointtimer adds posttrainingdiagnostics but stops before finalresult/commitwrites.',
          'Logged milestone elapsed ends at that round ledger construction; later ledger/status writes are outside that recorded instant.',
          'Chargedtraining is trainingloop plus reused applicablegeneration/routerfit/train-validation-cache charges. Charges repeated acrossarms/seeds are accounting, not extra actualprojectwalltime.',
          'Parallel workers overlap: summed endpoint seconds must not be labelled elapsedprojecttime. Stage observedwalltime is a separate launchermeasurement.',
          'Inference timers use loaded rawcoordinates, uncachedrouter+model, three repeats afteronewarmup; excludedIO/model-loading/fit. A fifthcached check is separatelycounted. Hostconcurrenttimings descriptive.',
          'Operation counts are logicalcircuits/gates and feature/activation/examples, not measuredFLOPs,MACs,hardwarelatency or energy.',
          'Gradientcurves and clipping/exposure diagnostics are recordedtrainingmeasurements, not an independent replay of everyoptimizerstep.']}
        for path,h in watched.items():need(sha(path)==h,'Bound input changed during analysis')
        write(output/'summary.json',result)
        files={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in output.iterdir() if p.is_file()}
        write(output/'ANALYSIS_COMMIT.json',{'status':'PASS','stage':stage,'endpoint_count':len(rows),'files':files,
             'source_sha256':sha(__file__),'created_utc':datetime.now(timezone.utc).isoformat(),'test_accessed':False})
        print(json.dumps({'status':'PASS','stage':stage,'endpoints':len(rows),'summary_sha256':sha(output/'summary.json')}))
    except BaseException:
        write(output/'FAILURE.json',{'status':'FAIL','traceback':traceback.format_exc(),'test_accessed':False});raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=SEEDS,required=True);p.add_argument('--author-lock',type=Path,required=True)
    p.add_argument('--independent-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(args.stage,args.author_lock,args.independent_audit,args.output)
