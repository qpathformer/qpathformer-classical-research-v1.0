"""Author comparison of freshly reproduced endpoints; read-only arrays."""
from pathlib import Path
import json
import numpy as np

def need(condition,message):
    if not condition:raise RuntimeError(message)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def array_error(left,right,tolerance,label):
    a,b=np.asarray(left),np.asarray(right)
    need(a.shape==b.shape and a.dtype==b.dtype,'Shape/dtype changed: '+label)
    need(np.isfinite(a).all() and np.isfinite(b).all(),'Nonfinite comparison: '+label)
    delta=float(np.max(np.abs(a-b),initial=0))
    need(delta<=tolerance,'Reproduction tolerance exceeded: '+label)
    return {'maximum_absolute_error':delta,'absolute_tolerance':tolerance,
            'bitwise_equal':bool(np.array_equal(a,b))}

def compare_endpoint(original,reproduced,protocol):
    a,b=Path(original),Path(reproduced);tol=protocol['same_environment_tolerances']
    ar,br=read(a/'result.json'),read(b/'result.json')
    for key in ('job_id','arm','base_model','sampling_policy','method','seed','population','selected_round',
                'completed_rounds','optimizer_global_updates','source_hashes'):
        if key=='source_hashes':
            need(read(a/'config.json')[key]==read(b/'config.json')[key],'Frozen reproduction sources differ')
        else:need(ar[key]==br[key],'Reproduction identity/selection/budget differs: '+key)
    rows_a=[json.loads(x) for x in (a/'ledger.jsonl').read_text().splitlines()]
    rows_b=[json.loads(x) for x in (b/'ledger.jsonl').read_text().splitlines()]
    need(len(rows_a)==len(rows_b)==200,'Full reproduction horizon missing')
    arrays={};classifications=0
    for name in ('round_parameters','training_logits','validation_logits','training_native_losses','validation_native_losses',
                 'training_probabilities','validation_probabilities'):
        aa=np.load(a/(name+'.npy'),mmap_mode='r',allow_pickle=False)
        bb=np.load(b/(name+'.npy'),mmap_mode='r',allow_pickle=False)
        bound=tol['parameters_abs'] if name=='round_parameters' else (
            tol['native_logits_abs'] if name.endswith('logits') else tol['metrics_abs'] if 'losses' in name else
            .25*tol['native_logits_abs'])
        arrays[name]=array_error(aa,bb,bound,name)
        if name.endswith('probabilities'):
            need(np.array_equal(aa>=.5,bb>=.5),'Reproduced classifications differ')
            classifications+=aa.size
    for name in ('record_orders','sampler_uniforms','sampling_probabilities','sampling_weights','sampling_counts',
                 'refresh_native_losses','refresh_scores','refresh_priority_probabilities','training_record_exposure'):
        aa=np.load(a/(name+'.npy'),mmap_mode='r',allow_pickle=False)
        bb=np.load(b/(name+'.npy'),mmap_mode='r',allow_pickle=False)
        need(aa.shape==bb.shape and aa.dtype==bb.dtype and np.array_equal(aa,bb),'Exact same-environment sampler replay differs: '+name)
        arrays[name]={'bitwise_equal':True}
    maximum_metric=0.
    for left,right in zip(rows_a,rows_b):
        need(left['round']==right['round'] and left['optimizer_updates']==right['optimizer_updates'] and
             left['selected']==right['selected'],'Curve identity/selection changed')
        for split in ('validation','full_training'):
            for key in ('bce','macro_f1','accuracy','brier','ece10'):
                difference=abs(left[split][key]-right[split][key]);maximum_metric=max(maximum_metric,difference)
                need(difference<=tol['metrics_abs'],'Reproduced metric curve differs')
            need(left[split]['confusion']==right[split]['confusion'],'Reproduced confusion differs')
    checkpoints={}
    for name in ('last_checkpoint.npz','selected_checkpoint.npz'):
        with np.load(a/name,allow_pickle=False) as left,np.load(b/name,allow_pickle=False) as right:
            checkpoints[name]=array_error(left['parameters'],right['parameters'],tol['parameters_abs'],name)
            need(int(left['adam_t'])==int(right['adam_t']),'Checkpoint optimizer horizon differs')
            need(int(left['completed_rounds'])==int(right['completed_rounds']),'Checkpoint selected round differs')
            array_error(left['validation_logits'],right['validation_logits'],tol['native_logits_abs'],name+' logits')
            need(np.array_equal(left['validation_probabilities']>=.5,right['validation_probabilities']>=.5),
                 'Checkpoint validation classes differ')
    return {'status':'PASS','job_id':ar['job_id'],'selected_round':ar['selected_round'],
            'rounds_verified':200,'updates_verified':15000,'arrays':arrays,'checkpoints':checkpoints,
            'maximum_metric_curve_absolute_error':maximum_metric,'exact_classifications_checked':classifications,
            'probability_tolerance_derivation':'sigmoid is1/4-Lipschitz; use registered native-logit absolute tolerance/4',
            'sampler_scope':'Same-environment replacement streams, probabilities, draws, weights and refresh arrays required bitwise equal; these four checks are not new independent populations.',
            'independent_reproduction_audit':'REQUIRED_SEPARATELY'}
