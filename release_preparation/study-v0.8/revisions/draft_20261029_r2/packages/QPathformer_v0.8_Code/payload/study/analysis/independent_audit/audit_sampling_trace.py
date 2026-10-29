"""Independent retained-sampler and Adam replay. No producer imports or test loader."""
from pathlib import Path
import hashlib,json
import numpy as np
import reference_v08 as ref
import sampler_reference as sampling

GRADIENT_ATOL=1e-10
GRADIENT_RTOL=1e-8
STATE_ATOL=2e-12
LOSS_ATOL=1e-8
PRIORITY_ATOL=2e-15
SPOT_ROUNDS=(1,10,11,12,100,200)
SPOT_BATCHES=(0,74)

def need(value,message):
    if not value:raise RuntimeError(message)
def rawsha(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def near(a,b,atol,message,rtol=0.):
    a=np.asarray(a);b=np.asarray(b)
    need(a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all() and
         np.all(abs(a-b)<=atol+rtol*abs(b)),message)
def same(a,b,message):need(np.array_equal(a,b),message)

def audit_trace(folder,job,method,train,states,orders,initial,ledger,metric_check,native_check):
    folder=Path(folder);rounds=job['rounds'];n=4800;pc=len(initial)
    route=None if method.endswith('global') else train[method.split('_')[1]+'_route']
    banks=1 if route is None else 5;bw=pc//banks
    shapes={'training_probabilities':(rounds,n),'training_logits':(rounds,n),'training_native_losses':(rounds,),
        'sampler_uniforms':(rounds,n),'sampling_probabilities':(rounds,n),'sampling_weights':(rounds,n),
        'sampling_counts':(rounds,n),'refresh_native_losses':(rounds-10,n),'refresh_scores':(rounds-10,n),
        'refresh_priority_probabilities':(rounds-10,n),'minibatch_gradients':(rounds*75,pc)}
    contract=json.loads((folder/'sampling_contract.json').read_text())
    need(contract['schema']=='qpath-v08-sampling-trace-1' and contract['policy']==job['sampling_policy'],'Sampler contract identity differs')
    need(contract['array_shapes']=={k:list(v) for k,v in shapes.items()},'Sampler contract shape inventory differs')
    need(contract['uniform_stream']==job['paired_streams']['training_order'],'Uniform stream binding differs')
    ds=contract['sampling_diagnostics_stream']
    need(ds['binding']==job['paired_streams']['sampling_diagnostics'] and ds['consumed'] is False,'Diagnostic stream must remain unused')
    need(contract['arrays_flushed_before_ledger'] is True and contract['test_accessed'] is False,'Sampler trace contract differs')
    arrays={}
    for name,shape in shapes.items():
        a=np.load(folder/(name+'.npy'),mmap_mode='r',allow_pickle=False)
        dtype=np.uint16 if name=='sampling_counts' else np.float64
        need(a.shape==shape and a.dtype==dtype and np.isfinite(a).all(),'Invalid trace array '+name)
        arrays[name]=a
    # All end-round training states independently evaluated. Start-of-round refresh
    # states are exactly the preceding end-round states, so no second model pass.
    rp,rz=ref.predict_many_with_logits(method,states,train['x'],route)
    near(arrays['training_probabilities'],rp,2e-12,'Independent full-training probabilities differ')
    near(arrays['training_logits'],rz,1e-9,'Independent full-training logits differ')
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(int(job['paired_streams']['training_order']['uint128_decimal']))))
    mode={'uniform':'U','priority':'P'}[job['sampling_policy']]
    theta=np.array(initial,copy=True);m=np.zeros(pc);v=np.zeros(pc);step=0
    moments=[];class_exposure=np.zeros(2,dtype=np.int64);exposure=np.zeros(n,dtype=np.int64)
    visits=np.zeros(banks,dtype=np.int64);visits_by_round=[]
    absent_movement=np.zeros(banks);bank_grad=np.zeros(banks)
    maximum_gradient_error=0.;maximum_state_error=0.;maximum_refresh_loss_error=0.
    probes=[];round_gradient_means=[]
    core_mask=np.zeros(pc,dtype=bool)
    if method.startswith('q'):
        for bank in range(banks):core_mask[bank*bw:bank*bw+8]=True
    for r,row in enumerate(ledger):
        number=r+1;sd=row['sampling'];refresh=number>10
        expected_trace_names=set(arrays)-({k for k in arrays if k.startswith('refresh_')} if not refresh else set())
        need(set(row['sampler_trace_sha256'])==expected_trace_names,'Per-round trace inventory differs')
        for name in expected_trace_names:
            a=arrays[name]
            chosen=a[number-11] if name.startswith('refresh_') else a[r*75:(r+1)*75] if name=='minibatch_gradients' else a[r:r+1] if a.ndim==1 else a[r]
            need(rawsha(chosen)==row['sampler_trace_sha256'][name],'Per-round sampler trace hash differs '+name)
        start_state=initial if r==0 else states[r-1]
        need(sd['refresh_parameter_sha256']==rawsha(start_state),'Refresh parameter-state binding differs')
        need(sd['policy']==job['sampling_policy'] and sd['refresh_performed']==refresh and sd['refresh_row']==(number-11 if refresh else None),'Refresh schedule differs')
        loss=None
        if refresh:
            j=number-11
            independent_loss=sampling.native_losses(train['y'],rz[r-1])
            loss=arrays['refresh_native_losses'][j]
            maximum_refresh_loss_error=max(maximum_refresh_loss_error,float(abs(loss-independent_loss).max()))
            near(loss,independent_loss,LOSS_ATOL,'Independent round-start training loss refresh differs')
            # Also use committed logits for a tighter serialization/formula check.
            near(loss,sampling.native_losses(train['y'],arrays['training_logits'][r-1]),2e-12,'Refresh loss does not use previous-round training logits')
            scores,proposal=sampling.proposal(loss)
            near(arrays['refresh_scores'][j],scores,0.,'Capped square-root scores differ')
            near(arrays['refresh_priority_probabilities'][j],proposal,PRIORITY_ATOL,'Priority probability law differs')
        expected=sampling.effective_probabilities(mode,number,n,loss)['probabilities']
        actual=arrays['sampling_probabilities'][r]
        near(actual,expected,PRIORITY_ATOL,'Actual sampling distribution differs')
        if mode=='U' or not refresh:same(actual,np.full(n,1/n),'Uniform phase must be exact')
        else:same(actual,arrays['refresh_priority_probabilities'][number-11],'Priority actual p differs from retained proposal')
        u=rng.random(n);same(arrays['sampler_uniforms'][r],u,'Paired PCG64 uniform stream differs')
        order,weights=sampling.replay_draws(actual,u)
        same(orders[r],order,'Inverse-CDF with-replacement positions differ')
        same(arrays['sampling_weights'][r],weights,'Raw importance weights differ')
        need(np.all(weights<=2+1e-14),'Importance mixture weight bound differs')
        counts=np.bincount(order,minlength=n);same(arrays['sampling_counts'][r],counts,'Replacement record counts differ')
        exposure+=counts;cd=np.bincount(train['y'][order],minlength=2);class_exposure+=cd
        need(sd['class_draws']==cd.tolist() and sd['class_draws_cumulative']==class_exposure.tolist(),'Sampling class exposure differs')
        need(sd['record_exposure_sha256']==rawsha(exposure),'Cumulative record exposure hash differs')
        need(sd['high_loss_draws']==(int(np.sum(loss[order]>5)) if refresh else None),'Training cap-exceedance exposure differs')
        diagnostics={'minimum_probability':float(actual.min()),'maximum_probability':float(actual.max()),
            'probability_entropy_nats':float(-np.sum(actual*np.log(actual))),'distribution_effective_records':float(1/np.sum(actual*actual)),
            'minimum_sampled_weight':float(weights.min()),'maximum_sampled_weight':float(weights.max()),'mean_sampled_weight':float(weights.mean()),
            'sampled_weight_effective_count':float(weights.sum()**2/np.sum(weights*weights)),
            'unique_records_drawn':int(np.count_nonzero(counts)),'maximum_record_multiplicity':int(counts.max()),'draws_with_replacement':n}
        for key,value in diagnostics.items():near(sd[key],value,2e-12,'Sampling diagnostic differs '+key)
        for key in ('round_refresh_wall_seconds','round_refresh_cpu_seconds'):
            need(np.isfinite(sd[key]) and sd[key]>=0,'Invalid refresh cost')
            if not refresh:need(sd[key]==0.,'Warmup must not charge a refresh')
        gradients=arrays['minibatch_gradients'][r*75:(r+1)*75]
        round_gradient_means.append(gradients.sum(axis=0)/75)
        norms=np.linalg.norm(gradients,axis=1)
        near(row['mean_batch_gradient_norm'],norms.mean(),2e-12,'Mean raw gradient norm differs')
        near(row['maximum_batch_gradient_norm'],norms.max(),2e-12,'Maximum raw gradient norm differs')
        for group,mask in (('core',core_mask),('head',~core_mask)):
            norm=np.linalg.norm(gradients[:,mask],axis=1)
            near(row['mean_batch_gradient_group_norms'][group],norm.mean(),2e-12,'Mean group gradient norm differs')
            near(row['maximum_batch_gradient_group_norms'][group],norm.max(),2e-12,'Maximum group gradient norm differs')
        for b,g in enumerate(gradients):
            ids=order[b*64:(b+1)*64];br=None if route is None else route[ids]
            counts_by_bank=np.array([64]) if br is None else np.bincount(br,minlength=banks)
            if number in SPOT_ROUNDS and b in SPOT_BATCHES:
                independent_g=ref.weighted_gradient(method,theta,train['x'][ids],train['y'][ids],br,weights[b*64:(b+1)*64])
                error=float(abs(g-independent_g).max());maximum_gradient_error=max(maximum_gradient_error,error)
                near(g,independent_g,GRADIENT_ATOL,'Independent raw-gradient probe differs',GRADIENT_RTOL)
                probes.append({'round':number,'minibatch_index_zero_based':b,'update_before':step,'maximum_absolute_error':error})
            same(g.reshape(banks,bw)[counts_by_bank==0],np.zeros((np.sum(counts_by_bank==0),bw)),'Absent-bank raw data gradient differs')
            previous=theta.copy();step+=1
            m=.9*m+.1*g;v=.999*v+.001*(g*g)
            theta-=.01*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8)
            absent_movement+=np.linalg.norm((theta-previous).reshape(banks,bw),axis=1)*(counts_by_bank==0)
            bank_grad+=np.linalg.norm(g.reshape(banks,bw),axis=1)
            visits+=counts_by_bank
        maximum_state_error=max(maximum_state_error,float(abs(theta-states[r]).max()))
        near(theta,states[r],STATE_ATOL,'Full retained-gradient Adam parameter replay differs')
        moments.append((m.copy(),v.copy()))
        near(row['bank_absent_parameter_movement_l2_sum_cumulative'],absent_movement,STATE_ATOL,'Absent-bank Adam movement replay differs')
        near(row['bank_gradient_l2_sum_cumulative'],bank_grad,STATE_ATOL,'Bank gradient accumulation differs')
        visits_by_round.append(visits.copy())
        metric_check(ref.metrics(train['y'],arrays['training_probabilities'][r]),row['full_training'])
        native_check(train['y'],arrays['training_probabilities'][r],arrays['training_logits'][r],
                     arrays['training_native_losses'][r],row['full_training_native'])
    same(np.load(folder/'training_record_exposure.npy',allow_pickle=False),exposure,'Final training record exposure differs')
    with np.load(folder/'round_gradient_means.npz',allow_pickle=False) as z:
        near(z['gradients'],np.asarray(round_gradient_means),2e-12,'Round raw gradient means differ')
    for path in [*sorted(folder.glob('selected_round_*.npz')),folder/'last_checkpoint.npz',folder/'selected_checkpoint.npz']:
        with np.load(path,allow_pickle=False) as z:
            k=int(z['completed_rounds'])-1
            near(z['adam_m'],moments[k][0],STATE_ATOL,'Checkpoint first moment differs from complete replay')
            near(z['adam_v'],moments[k][1],STATE_ATOL,'Checkpoint second moment differs from complete replay')
    summary={'all_sampler_rounds_verified':rounds,'all_replacement_draws_verified':rounds*n,
        'all_refreshes_independently_replayed':rounds-10,'all_training_predictions_replayed':rounds*n,
        'all_adam_updates_replayed':step,'raw_gradient_spotchecks':probes,
        'maximum_gradient_probe_absolute_error':maximum_gradient_error,'maximum_adam_state_absolute_error':maximum_state_error,
        'maximum_refresh_native_loss_absolute_error':maximum_refresh_loss_error,
        'maximum_training_probability_absolute_error':float(abs(rp-arrays['training_probabilities']).max()),
        'maximum_training_logit_absolute_error':float(abs(rz-arrays['training_logits']).max()),
        'unique_records_exposed':int(np.count_nonzero(exposure)),'class_draws':class_exposure.tolist(),
        'sampler_uniform_sha256':hashlib.sha256((folder/'sampler_uniforms.npy').read_bytes()).hexdigest(),
        'raw_gradient_scope':'Every retained gradient drives independent Adam replay; only predeclared first/last batches in rounds1,10,11,12,100,200 are independently recomputed. This is not independent recomputation of every training gradient.',
        'trace_bytes':int(sum(v.nbytes for v in arrays.values())+orders.nbytes)}
    return {'summary':summary,'visits_by_round':visits_by_round,'class_exposure':class_exposure,'exposure':exposure}
