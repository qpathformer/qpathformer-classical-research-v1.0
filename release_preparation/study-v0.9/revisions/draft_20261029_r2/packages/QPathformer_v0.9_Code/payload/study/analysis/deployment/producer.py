"""Produce all 276 compiled representations only after root evaluation release."""
import os,sys
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
sys.dont_write_bytecode=True
import argparse,time,hashlib,traceback
from pathlib import Path
import numpy as np
import support as s
from compiler import CIRCUIT_ARMS,Compiled,compile_parameters,probes,parity,original_raw,trig_features
def run(authorization,output):
    import durable,resource_probe
    output=Path(output).resolve()
    with durable.auxiliary_lease(s.ROOT,'conversion'):
        release,verified,env=s.gate(authorization,output,'conversion',s.sources());jobs=[j for j in verified['jobs'] if j['arm'] in CIRCUIT_ARMS]
        s.require(len(jobs)==276,'All 276 circuit endpoints required');attempt=s.claim('conversion',authorization,output,release);output.mkdir();start=time.perf_counter();cpu=time.process_time();records=[]
        try:
            matrix=s.read(s.ROOT/'governance/RUN_MATRIX.json');popmap={p['population_id']:p for p in matrix['populations']}
            for job in jobs:
                model,policy,endpoint=s.load_model(job,verified);name=job['population_id'];pop=popmap[name];begin=time.perf_counter();coef,extra,grid=compile_parameters(job['arm'],model.parameters);seconds=time.perf_counter()-begin;compiled=Compiled(job['arm'],coef,extra,policy)
                random,boundary=probes(policy,int(pop['proposed_streams']['boundary_diagnostic']['uint128_decimal']));checks={}
                for label,x in [('offgrid',random),('centroid_pair_boundary',boundary)]:checks[label]=parity(*compiled.predict_with_logits(x),*model.predict_with_logits(x))
                forced=np.vstack((random,boundary));reference=np.column_stack([model._expert(forced,theta)[0] for theta in model.parameters[:70].reshape(5,14)]);force_error=float(abs(compiled.core_logits(forced)-reference).max());s.require(force_error<=1e-10,'Forced bank parity failed')
                for split in ('validation','test'):
                    data=s.population(name,split,verified['seal']);raw=data.get('raw_x',data['x']);checks[split]=parity(*compiled.predict_raw(raw),*original_raw(model,raw,policy))
                key=hashlib.sha256(job['run_id'].encode()).hexdigest()[:24];folder=output/key;folder.mkdir()
                with (folder/'coefficients.npz').open('xb') as f:np.savez(f,coefficients=coef,extra=extra,grid_logits=grid)
                s.write(folder/'policy.json',policy)
                record={'job_id':job['run_id'],'arm':job['arm'],'population':name,'endpoint_commit':endpoint,'coefficients':s.binding(folder/'coefficients.npz'),'policy':s.binding(folder/'policy.json'),'conversion_seconds':seconds,'core_table_bytes':coef.nbytes,'extra_coefficient_bytes':extra.nbytes,'serialized_representation_bytes':(folder/'coefficients.npz').stat().st_size+(folder/'policy.json').stat().st_size,'banks':5,'terms_per_core':25,'forced_bank_max_logit_error':force_error,'parity':checks,'router_and_preprocessing_preserved':True,'mixture_is_not_one_25term_polynomial':job['arm']!='C_H','construction_circuit_examples':125}
                s.write(folder/'conversion.json',record);records.append(record);print(s.json.dumps({'converted':len(records),'required':276,'job_id':job['run_id']}),flush=True)
            summary={'models':276,'bank_cores':1380,'records':records,'environment':env,'attempt':attempt,'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,'resources':resource_probe.process_resources(),'independent_Laurent_replay':'required separately before timing'};s.write(output/'CONVERSION_SUMMARY.json',summary)
            s.recheck(authorization,release,verified,s.sources());return s.commit(output,'conversion',authorization,summary)
        except BaseException as e:s.write(output/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'partial_artifacts_preserved':True});raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--authorization',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(s.json.dumps(run(a.authorization,a.output)))
