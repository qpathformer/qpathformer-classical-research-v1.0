"""Prepare author v0.8 audit; no endpoint access."""
from pathlib import Path
root=Path(__file__).resolve().parent
s=(root/'audit_stage_v07.py').read_text()
s=s.replace('logit_cross_entropy,sigmoid','logit_cross_entropy,sigmoid,Adam,native_losses\nimport sampling')
s=s.replace("{'engineering':32,'A':64,'B':512}","{'engineering':40,'A':80,'B':640}")
s=s.replace("qpath-v07-","qpath-v08-")
s=s.replace("reports=[];arraypairs=0;", "reports=[];arraypairs=0;gradient_checks=0;")
s=s.replace("        require(commit['job_id']==identity", "        require(commit['schema']=='qpath-v08-endpoint-1','Endpoint schema')\n        require(commit['job_id']==identity")
s=s.replace("        method=ARM_METHODS", """        for artifact in (commit,config,result):
            require(artifact['base_model']==job['base_model'] and artifact['sampling_policy']==job['sampling_policy'],'Sampling recipe identity')
        method=ARM_METHODS""")
start=s.index("        rng=np.random.Generator")
end=s.index("        ledger=",start)
s=s[:start]+"""        trace_names=('training_probabilities','training_logits','training_native_losses','sampler_uniforms',
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
""" +s[end:]
anchor="            require(line['record_order_sha256']==ah(orders[i]),'Orderhashledger')"
s=s.replace(anchor,anchor+"""
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
""")
s=s.replace("if chosen:best=expected_metrics['bce'];selected=i+1", "if chosen:\n                best=expected_metrics['bce'];selected=i+1;selected_moments={'adam_m':opt.m.copy(),'adam_v':opt.v.copy()}")
s=s.replace("                require(np.all(checkpoint['adam_v']>=0),'InvalidAdamvariance')", """                require(np.all(checkpoint['adam_v']>=0),'InvalidAdamvariance')
                expected_moments=selected_moments if name=='selected_checkpoint.npz' else {'adam_m':opt.m,'adam_v':opt.v}
                for key,value in expected_moments.items():np.testing.assert_array_equal(checkpoint[key],value);arraypairs+=1""")
s=s.replace("require(result['bank_training_record_visits']==(bank_counts*rounds).tolist(),'Bankvisitsdiffers')", """require(result['bank_training_record_visits']==bank_visits.tolist(),'Sampled bank visits differ')
        np.testing.assert_array_equal(np.load(endpoint/'training_record_exposure.npy',allow_pickle=False),exposure);arraypairs+=1
        require(result['sampling_diagnostics']['refresh_count']==rounds-10,'Refresh count')
        require(result['sampling_diagnostics']['class_draws']==class_visits.tolist(),'Final class exposure')""")
s=s.replace("'array_comparisons':arraypairs,", "'array_comparisons':arraypairs,'selected_minibatch_gradients_recomputed':gradient_checks,")
s=s.replace("all stored round predictions/metrics/recordorders", "all round train/validation predictions and metrics, refreshed loss/scores/probabilities, paired uniforms, replacement indices/weights, every Adam update from retained raw gradients, first/last minibatch gradients per round")
(root/'audit_stage_v08.py').write_text(s,encoding='utf-8',newline='\n')
