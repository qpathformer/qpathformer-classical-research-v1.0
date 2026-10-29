"""One-time source preparation, not a scientific run."""
from pathlib import Path

root = Path(__file__).resolve().parent
p = root / "study.py"
s = p.read_text()
s = s.replace("v0.7 trainer", "v0.8 trainer")
s = s.replace("import numpy as np", """os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
THREAD_KEYS=('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')
for _key in THREAD_KEYS:os.environ[_key]='1'
import numpy as np""")
s = s.replace("binary_cross_entropy,add_work", "binary_cross_entropy,add_work,native_losses as per_record_native_losses\nfrom sampling import priority_distribution,selected_distribution,inverse_cdf_draws,diagnostics as sampler_diagnostics,WARMUP_ROUNDS")
s = s.replace("(13901,),'A':(1301,1302),'B':(1401,1402)", "(1500,),'A':(1501,1502),'B':(1601,1602)")
s = s.replace("all eight arms", "all ten arms")
s = s.replace("'shuffle':'PCG64 SeedSequence(registered uint128 training_order); one permutation of training row positions per round'", "'sampling':'PCG64 SeedSequence(registered uint128 training_order); 4800 uniform float64 draws per round; inverse-CDF with replacement, side=right, lastCDF=1',\n          'priority':{'warmup_rounds':10,'loss_cap':5.,'epsilon':.001,'uniform_mixture':.5,'exponent':.5,'refresh':'start of each round11..200, same diagnostic refresh in U','weight':'1/(N*p_i), raw data gradient before batch mean; no normalization/clipping/sampler derivative; no regularizer'},")
s = s.replace("derivative; no regularizer'},,", "derivative; no regularizer'},")
s = s.replace("'engineering_rounds':2,'engineering_optimizer_updates':150", "'engineering_rounds':12,'engineering_optimizer_updates':900")
s = s.replace("'round_evidence':'float64 round_parameters,validation_probabilities,validation_native_losses; validation_logits onlynative-logitmodels; uint16 record_orders; flushbeforeledger'",
"""'round_evidence':'float64 parameters,train/validation p/logits/native BCE,uniforms,actual p,weights,refresh loss/scores/proposed p,raw minibatch gradients; uint16 indices/counts; all arrays flush before ledger',
          'refresh_evidence':'Rows0..rounds-11 correspond start of rounds11..rounds; parameters are initial_state for round1 or preceding round_parameters row; no validation/test/latent inputs',
          'uniform_control':'Replacement law and priority diagnostic refresh; proposed priority p retained but not used'""")
s = s.replace("'tests/test_v07_science.py'", "'sampling.py','tests/test_v08_science.py','tests/test_routers_data.py'")
s = s.replace("rounds=2 if stage=='engineering' else 200", "rounds=12 if stage=='engineering' else 200")
s = s.replace("    for name,stream in job['paired_streams'].items():", """    require(job['arm']==job['base_model']+'_'+{'uniform':'U','priority':'P'}[job['sampling_policy']],'Arm/policy mismatch')
    require(set(job['paired_streams'])=={'training_order','paired_circuit_core_initialization','sampling_diagnostics'},'Stream inventory mismatch')
    for name,stream in job['paired_streams'].items():""")
s = s.replace("with np.load(path,allow_pickle=False) as f:pop={k:f[k] for k in allowed}", """with np.load(path,allow_pickle=False) as f:
        require(set(f.files)==set(allowed),'Forbidden or missing training payload field')
        pop={k:f[k] for k in allowed}""")
s = s.replace("qpath-v07-", "qpath-v08-").replace("QPATH-ROUTING-REPLICATION-v0.7","QPATH-PRIORITY-ROUTING-v0.8")
s = s.replace("'arm':job['arm'],", "'arm':job['arm'],'base_model':job['base_model'],'sampling_policy':job['sampling_policy'],")
s = s.replace("('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')", "THREAD_KEYS")
anchor = "    np.savez(output/'population_identity.npz',train_ids=training['ids'],validation_ids=validation['ids'])"
s = s.replace(anchor, """    # Every stochastic input, frozen round law and raw update gradient is retained.
    trace={}
    definitions={
        'training_probabilities':((rounds,4800),np.float64),
        'training_logits':((rounds,4800),np.float64),
        'training_native_losses':((rounds,),np.float64),
        'sampler_uniforms':((rounds,4800),np.float64),
        'sampling_probabilities':((rounds,4800),np.float64),
        'sampling_weights':((rounds,4800),np.float64),
        'sampling_counts':((rounds,4800),np.uint16),
        'refresh_native_losses':((rounds-WARMUP_ROUNDS,4800),np.float64),
        'refresh_scores':((rounds-WARMUP_ROUNDS,4800),np.float64),
        'refresh_priority_probabilities':((rounds-WARMUP_ROUNDS,4800),np.float64),
        'minibatch_gradients':((job['updates'],len(model.parameters)),np.float64)}
    for name,(shape,dtype) in definitions.items():
        value=np.lib.format.open_memmap(output/(name+'.npy'),mode='w+',dtype=dtype,shape=shape)
        value[:]=0 if dtype==np.uint16 else np.nan
        value.flush();trace[name]=value;arrays.append(value)
    write_json(output/'sampling_contract.json',{
        'schema':'qpath-v08-sampling-trace-1','policy':job['sampling_policy'],
        'array_shapes':{k:list(v.shape) for k,v in trace.items()},
        'refresh_row_rule':'refresh row r-11 describes start of round r>=11',
        'refresh_parameter_rule':'round_parameters[r-2], before any round-r updates',
        'uniform_stream':job['paired_streams']['training_order'],
        'sampling_diagnostics_stream':{'binding':job['paired_streams']['sampling_diagnostics'],'consumed':False,'reason':'all training-record diagnostics are exhaustive, no diagnostic random subset'},
        'indices':'uint16 positional indices with replacement; record_orders.npy',
        'weights':'float64 1/(4800*actual_round_probability[index]) without normalization/clipping',
        'gradient':'minibatch_gradients.npy is weighted native data gradient before unchanged Adam; no regularizer',
        'arrays_flushed_before_ledger':True,'test_accessed':False},True)
""" + anchor)
s = s.replace("work={'training':{},'validation':{}}", "work={'training':{},'validation':{},'full_training_diagnostics':{},'priority_refresh':{}}")
s = s.replace("    fixed_core_hash=array_digest(model.core_parameters)", """    refresh_seconds=0.;refresh_cpu_seconds=0.;sampling_seconds=0.;sampling_cpu_seconds=0.
    full_training_diagnostic_seconds=0.;full_training_diagnostic_cpu_seconds=0.
    record_exposure=np.zeros(4800,dtype=np.int64);class_exposure=np.zeros(2,dtype=np.int64)
    policy_code={'uniform':'U','priority':'P'}[job['sampling_policy']]
    fixed_core_hash=array_digest(model.core_parameters)""")
s = s.replace("                order=rng.permutation(len(training['y']));orders[current_round-1]=order", """                r=current_round-1;refresh_state_sha=array_digest(model.parameters)
                refresh_row=None;proposed=None;refresh_loss=None
                round_refresh_wall=0.;round_refresh_cpu=0.
                if current_round>WARMUP_ROUNDS:
                    tw=time.perf_counter();tc=time.process_time()
                    refresh_p,refresh_z=model.predict_with_logits(training['x'],route,train_features)
                    refresh_loss=per_record_native_losses(training['y'],refresh_z)
                    scores,proposed=priority_distribution(refresh_loss)
                    refresh_row=current_round-WARMUP_ROUNDS-1
                    trace['refresh_native_losses'][refresh_row]=refresh_loss
                    trace['refresh_scores'][refresh_row]=scores
                    trace['refresh_priority_probabilities'][refresh_row]=proposed
                    add_work(work['priority_refresh'],model.accounting(training['x'],route,cached_features=model.frozen))
                    round_refresh_wall=time.perf_counter()-tw;round_refresh_cpu=time.process_time()-tc
                    refresh_seconds+=round_refresh_wall;refresh_cpu_seconds+=round_refresh_cpu
                tw=time.perf_counter();tc=time.process_time()
                sampling_p=selected_distribution(4800,current_round,policy_code,proposed)
                uniforms=rng.random(4800)
                order,weights=inverse_cdf_draws(sampling_p,uniforms)
                orders[r]=order
                counts=np.bincount(order,minlength=4800)
                trace['sampler_uniforms'][r]=uniforms;trace['sampling_probabilities'][r]=sampling_p
                trace['sampling_weights'][r]=weights;trace['sampling_counts'][r]=counts
                record_exposure+=counts;round_class=np.bincount(training['y'][order],minlength=2)
                class_exposure+=round_class
                sd=sampler_diagnostics(sampling_p,weights,counts)
                sd.update({'policy':job['sampling_policy'],'refresh_performed':refresh_row is not None,
                    'refresh_row':refresh_row,'refresh_parameter_sha256':refresh_state_sha,
                    'class_draws':round_class.tolist(),'class_draws_cumulative':class_exposure.tolist(),
                    'record_exposure_sha256':array_digest(record_exposure),
                    'high_loss_draws':None if refresh_loss is None else int(np.sum(refresh_loss[order]>5.)),
                    'high_loss_rule':'native BCE>5 at fixed round-start refresh; descriptive cap exceedance',
                    'round_refresh_wall_seconds':round_refresh_wall,'round_refresh_cpu_seconds':round_refresh_cpu})
                sampling_seconds+=time.perf_counter()-tw;sampling_cpu_seconds+=time.process_time()-tc""")
s = s.replace("None if train_features is None else train_features[ids])", "None if train_features is None else train_features[ids],sample_weight=weights[offset:offset+len(ids)])")
s = s.replace("                    opt.step(model.parameters,g);loss_sum+=len(ids)*loss", "                    trace['minibatch_gradients'][opt.t]=g\n                    opt.step(model.parameters,g);loss_sum+=len(ids)*loss")
s = s.replace("                p,z=model.predict_with_logits(validation['x'],model.route_for(validation),validation_features)", """                tw=time.perf_counter();tc=time.process_time()
                full_train_p,full_train_z=model.predict_with_logits(training['x'],route,train_features)
                tm=metrics(training['y'],full_train_p);tnd=native_diagnostics(model,training['y'],full_train_p,full_train_z)
                trace['training_probabilities'][r]=full_train_p;trace['training_logits'][r]=full_train_z
                trace['training_native_losses'][r]=tnd['native_bce']
                add_work(work['full_training_diagnostics'],model.accounting(training['x'],route,cached_features=model.frozen))
                full_training_diagnostic_seconds+=time.perf_counter()-tw;full_training_diagnostic_cpu_seconds+=time.process_time()-tc
                p,z=model.predict_with_logits(validation['x'],model.route_for(validation),validation_features)""")
s = s.replace("'training_common_clipped_bce':common_loss_sum/len(order),", """'training_common_clipped_bce':common_loss_sum/len(order),
                     'training_sampled_scope':'with-replacement minibatches, weighted native objective and unweighted sampled clipped BCE; full_training fields are population diagnostics',
                     'full_training':tm,'full_training_native':tnd,'sampling':sd,
                     'sampler_trace_sha256':{k:array_digest(v[refresh_row] if k.startswith('refresh_') else
                        v[r*75:(r+1)*75] if k=='minibatch_gradients' else v[r:r+1] if v.ndim==1 else v[r])
                        for k,v in trace.items() if not k.startswith('refresh_') or refresh_row is not None},""")
s = s.replace("        np.savez(output/'round_gradient_means.npz',gradients=np.asarray(gradient_means))", "        np.savez(output/'round_gradient_means.npz',gradients=np.asarray(gradient_means))\n        np.save(output/'training_record_exposure.npy',record_exposure,allow_pickle=False)")
s = s.replace("'training_seconds':training_seconds,", """'sampling_diagnostics':{'refresh_count':rounds-WARMUP_ROUNDS,
                    'replacement_draws':rounds*4800,'unique_records_exposed':int(np.count_nonzero(record_exposure)),
                    'class_draws':class_exposure.tolist(),'refresh_wall_seconds':refresh_seconds,'refresh_cpu_seconds':refresh_cpu_seconds,
                    'sampling_wall_seconds':sampling_seconds,'sampling_cpu_seconds':sampling_cpu_seconds,
                    'full_training_diagnostic_wall_seconds':full_training_diagnostic_seconds,'full_training_diagnostic_cpu_seconds':full_training_diagnostic_cpu_seconds,
                    'scope':'Refresh includes full train forward/loss/probability construction and work bookkeeping; sampling includes RNG/inverseCDF/exposure/trace assignment; training diagnostics include full end-round train forward and metrics. Array flushes and ledger serialization are additional loop work.',
                    'trace_bytes':sum(v.nbytes for v in trace.values())+orders.nbytes,
                    'sampling_diagnostics_stream_consumed':False},
                'training_seconds':training_seconds,""")
p.write_text(s,encoding="utf-8",newline="\n")
