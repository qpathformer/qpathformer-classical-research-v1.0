"""Three separately released serial sessions; raw inputs include preprocessing."""
import os,sys
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
sys.dont_write_bytecode=True
import argparse,csv,time,hashlib,traceback,gc
from pathlib import Path
import numpy as np
import support as s
from compiler import Compiled,original_raw
def ordered_jobs(jobs,matrix,session):
    populations={p['population_id']:p for p in matrix['populations']};blocks={}
    for name in sorted({j['population_id'] for j in jobs}):
        group=[j for j in jobs if j['population_id']==name];stream=int(populations[name]['proposed_streams']['deployment_order']['uint128_decimal']);gen=np.random.Generator(np.random.PCG64(np.random.SeedSequence([stream,session])));blocks[name]=[group[i] for i in gen.permutation(len(group))]
    ordered=[]
    while any(blocks.values()):
        for name in sorted(blocks):
            if blocks[name]:ordered.append(blocks[name].pop(0))
    return ordered
def run(authorization,output):
    import durable,resource_probe
    output=Path(output).resolve();header=s.read(authorization);session=header.get('session');s.require(session in (1,2,3),'Registered sessions1..3 only')
    with durable.timing_lease(s.ROOT,authorization):
        release,verified,env=s.gate(authorization,output,'timing',s.sources())
        conversions,cc=s.verify_derived(release['conversion_commit'],'conversion');reproduction,rc=s.verify_derived(release['reproduction_commit'],'reproduction')
        for field,expected in [('independent_conversion_replay',release['conversion_commit']),('independent_reproduction_replay',release['reproduction_commit'])]:
            receipt=s.read(s.verify(release[field]));s.require(receipt.get('status')=='PASS' and receipt.get('derived_commit')==expected,'Independent derivative replay missing or stale')
        attempt=s.claim('timing_'+str(session),authorization,output,release);output.mkdir();start=time.perf_counter();cpu=time.process_time();before=resource_probe.process_resources();jobs=ordered_jobs(verified['jobs'],s.read(s.ROOT/'governance/RUN_MATRIX.json'),session);conversion_map={x['job_id']:x for x in s.read(conversions/'CONVERSION_SUMMARY.json')['records']};conditions=0;warmups=0;trials=0;checksums=0.;details=[]
        try:
            with (output/'timed_trials.csv').open('x',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=['session','block','job_id','representation','batch','trial','wall_ns','cpu_ns','probability_sum']);writer.writeheader()
                for block,job in enumerate(jobs):
                    model,policy,_=s.load_model(job,verified);data=s.population(job['population_id'],'validation',verified['seal']);raw=data.get('raw_x',data['x']);fixture=raw[np.arange(1024)%len(raw)].copy();representations=[('original',lambda x:original_raw(model,x,policy))]
                    if job['run_id'] in conversion_map:
                        item=conversion_map[job['run_id']]
                        with np.load(s.verify(item['coefficients']),allow_pickle=False) as a:compiled=Compiled(job['arm'],a['coefficients'],a['extra'],policy)
                        representations.append(('converted',compiled.predict_raw))
                    if (session+block)%2:representations.reverse()
                    per_model=[]
                    for batch in (1,32,1024):
                        x=fixture[:batch]
                        for name,predict in representations:
                            gc.collect()
                            for _ in range(2):p,z=predict(x);checksums+=float(p.sum());warmups+=1
                            walls=[]
                            for trial in range(15):
                                t0=time.perf_counter_ns();c0=time.process_time_ns();p,z=predict(x);c1=time.process_time_ns();t1=time.perf_counter_ns();checksum=float(p.sum());checksums+=checksum;walls.append(t1-t0);trials+=1
                                writer.writerow({'session':session,'block':block,'job_id':job['run_id'],'representation':name,'batch':batch,'trial':trial,'wall_ns':t1-t0,'cpu_ns':c1-c0,'probability_sum':checksum})
                            conditions+=1;per_model.append({'representation':name,'batch':batch,'median_wall_ns':float(np.median(walls)),'records_per_second':float(batch*1e9/np.median(walls))})
                    details.append({'job_id':job['run_id'],'conditions':per_model,'raw_input_dimension':raw.shape[1],'repeated_validation_rows_for_1024':len(raw)<1024,'expert_evaluations_per_record':5 if job['arm'].startswith(('C_','T_')) and job['arm'][-1]!='H' else 1,'router_gate_preprocessing_overhead':'Included in every end-to-end timed call; no cached input transform, features, routes or gate weights.'});f.flush()
                    print(s.json.dumps({'session':session,'timed_models':block+1,'required':636}),flush=True)
            s.require(len(jobs)==636 and conditions==2736 and warmups==5472 and trials==41040,'Frozen timing inventory differs')
            summary={'session':session,'models':636,'representations':912,'conditions':conditions,'warmups':warmups,'timed_trials':trials,'details':details,'environment':env,'resources_before':before,'resources_after':resource_probe.process_resources(),'perf_counter':vars(time.get_clock_info('perf_counter')),'cpu_counter':vars(time.get_clock_info('process_time')),'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,'probability_checksum':checksums,'attempt':attempt,'load_scope':'Exclusive ETEL compute lease excludes study training/reproduction/audits; unrelated OS activity uncontrolled.','inference_scope':'Raw input preprocessing, router, gate and residual included. Model/checkpoint loading and output checksum outside timed intervals.'};s.write(output/'TIMING_SUMMARY.json',summary);s.recheck(authorization,release,verified,s.sources());return s.commit(output,'timing',authorization,summary)
        except BaseException as e:s.write(output/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'partial_artifacts_preserved':True});raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--authorization',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(s.json.dumps(run(a.authorization,a.output)))
