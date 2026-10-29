"""Compare a clean retrain with its registered original; no model training."""
import json
from pathlib import Path
import numpy as np
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def require(ok,why):
    if not ok:raise RuntimeError(why)
def error(a,b,tol,label):
    require(a.shape==b.shape and a.dtype==b.dtype and np.isfinite(a).all() and np.isfinite(b).all(),'Invalid comparison '+label);delta=float(np.max(abs(a-b),initial=0));require(delta<=tol,'Reproduction mismatch '+label);return delta
def compare(original,reproduced,rounds=200):
    a,b=Path(original),Path(reproduced);left,right=read(a/'result.json'),read(b/'result.json')
    for k in ('job_id','arm','seed','population','selected_round','completed_rounds','optimizer_global_updates','extra_optimizer_updates','source_hashes','data_seal_sha256','matrix_sha256','protocol_sha256'):require(left[k]==right[k],'Reproduction identity/selection mismatch '+k)
    require(left['completed_rounds']==rounds and left['optimizer_global_updates']==rounds*75,'Full reproduction budget missing');errors={}
    for name in ('round_parameters','training_logits','validation_logits','training_probabilities','validation_probabilities','validation_native_losses','minibatch_gradients'):
        aa=np.load(a/(name+'.npy'),allow_pickle=False,mmap_mode='r');bb=np.load(b/(name+'.npy'),allow_pickle=False,mmap_mode='r');errors[name]=error(aa,bb,1e-12,name)
        if name.endswith('probabilities'):require(np.array_equal(aa>=.5,bb>=.5),'Reproduction class changes')
    for name in ('sampler_uniforms','record_orders','training_record_exposure'):
        aa=np.load(a/(name+'.npy'),allow_pickle=False,mmap_mode='r');bb=np.load(b/(name+'.npy'),allow_pickle=False,mmap_mode='r');require(np.array_equal(aa,bb),'Reproduction sampler differs '+name)
    rowsa=[json.loads(x) for x in (a/'rounds.jsonl').read_text().splitlines()];rowsb=[json.loads(x) for x in (b/'rounds.jsonl').read_text().splitlines()];require(len(rowsa)==len(rowsb)==rounds,'Curve horizon differs');maxcurve=0.
    for aa,bb in zip(rowsa,rowsb):
        for k in ('round','optimizer_updates','extra_optimizer_updates','selected'):require(aa[k]==bb[k],'Curve identity differs')
        for split in ('validation','full_training'):
            for k in ('bce','macro_f1','accuracy','brier','ece10'):
                delta=abs(aa[split][k]-bb[split][k]);require(delta<=1e-12,'Reproduction curve metric differs');maxcurve=max(maxcurve,delta)
            require(aa[split]['confusion']==bb[split]['confusion'],'Curve classes differ')
    for name in ('selected_checkpoint.npz','last_checkpoint.npz'):
        with np.load(a/name,allow_pickle=False) as aa,np.load(b/name,allow_pickle=False) as bb:
            require(set(aa.files)==set(bb.files),'Checkpoint members differ')
            for k in aa.files:
                if aa[k].dtype.kind=='b':require(np.array_equal(aa[k],bb[k]),'Boolean checkpoint differs')
                else:errors[name+'/'+k]=error(aa[k],bb[k],1e-12,name+'/'+k)
    return {'status':'PASS','job_id':left['job_id'],'selected_round':left['selected_round'],'rounds':rounds,'updates':rounds*75,'max_abs_errors':errors,'maximum_curve_metric_error':maxcurve,'changed_classes':0,'samplers_bitwise_equal':True,'independent_replay_required':True}
