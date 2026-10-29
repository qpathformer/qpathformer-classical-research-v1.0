"""Commit full-horizon endpoints and independently replay selected validation.

No test access. Produces a new absent audit file; failed audits remain evidence.
Root alone approves a next stage or a one-time evaluation release.
"""
import argparse
import csv
import json
from pathlib import Path
import traceback
import numpy as np
import qstudy as s
import replay
import numerical_verification as numerical


def require(condition,message):
    if not condition:raise RuntimeError(message)


def expected_work(method,pop,gradient):
    n=len(pop['x']);original=pop['depth']
    names=('forward_circuit_examples','shift_circuit_examples','circuit_examples','layer_applications',
           'feature_ry_gates','feature_rz_gates','trainable_ry_gates','trainable_rz_gates','cx_gates','readout_ry_gates','bank_record_visits')
    if method.startswith('mlp'):return dict.fromkeys(names,0)|{'model_record_visits':n}
    if method in ('fixed1','encoding1','readout1'):d=np.ones(n,dtype=np.int64)
    elif method in ('fixed2','hash40','kmeans40','ensemble40'):d=np.full(n,2)
    elif method=='fixed4':d=np.full(n,4)
    elif method=='min_depth2':d=np.maximum(original,2)
    else:d=original
    mult=5 if method=='ensemble40' else 1
    repeat=1+8*d+2*(method=='readout1') if gradient else np.ones(n,dtype=np.int64)
    examples=int(repeat.sum())*mult;layers=int((repeat*d).sum())*mult
    return {'forward_circuit_examples':n*mult,'shift_circuit_examples':examples-n*mult,'circuit_examples':examples,
            'layer_applications':layers,'feature_ry_gates':2*layers,'feature_rz_gates':2*layers*(method=='encoding1'),
            'trainable_ry_gates':2*layers,'trainable_rz_gates':2*layers,'cx_gates':layers,'readout_ry_gates':examples,
            'bank_record_visits':n*mult,'model_record_visits':n}


def audit(stage,output):
    if output.exists():raise FileExistsError('Audit output exists; preserve prior result')
    numerical.verify_protocol()
    audit_sources={n:s.digest(s.ROOT/n) for n in ('audit_stage.py','replay.py','reference_v03.py','numerical_verification.py')}
    dataset='development' if stage=='A' else 'confirmation'
    train=s.load_population(dataset,'train');val=s.load_population(dataset,'validation')
    freeze_hash=s.digest(s.ROOT/f'STAGE_{stage}_FREEZE.json');data_hash=s.digest(s.ROOT/'data/DATA_SEAL.json')
    rows=[];max_probability_error=0.;max_metric_error=0.
    for seed in s.SEEDS[stage]:
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
        expected_orders=np.asarray([rng.permutation(4800) for _ in range(200)],dtype=np.int32)
        for method in s.METHODS:
            s.verify_freeze(stage,seed,method)
            folder=s.ROOT/f'stage_{stage}'/f'seed_{seed}'/method
            require(not (folder/'failure.json').exists(),f'Failed endpoint {seed}/{method}')
            status=s.read_json(folder/'status.json');config=s.read_json(folder/'config.json');result=s.read_json(folder/'result.json');commit=s.read_json(folder/'endpoint_commit.json')
            require(status['status']=='completed' and status['round']==200,'Incomplete status')
            require(result['status']=='completed' and result['completed_rounds']==200 and result['optimizer_global_updates']==15000,'Incomplete horizon')
            require((config['seed'],config['method'],config['stage'],config['engineering'])==(seed,method,stage,False),'Wrong endpoint identity')
            require(config['source_hashes']==s.source_hashes() and config['stage_freeze_sha256']==freeze_hash and config['data_seal_sha256']==data_hash,'Configuration binding changed')
            bound={'result_sha256':'result.json','config_sha256':'config.json','selected_checkpoint_sha256':'selected_checkpoint.npz',
                   'last_checkpoint_sha256':'last_checkpoint.npz','ledger_sha256':'ledger.jsonl','record_orders_sha256':'record_orders.npz'}
            hashes={name:s.digest(folder/file) for name,file in bound.items()}
            require(all(commit[key]==value for key,value in hashes.items()),'Endpoint commit mismatch')
            with np.load(folder/'record_orders.npz',allow_pickle=False) as orders:
                require(np.array_equal(orders['orders'],expected_orders) and np.array_equal(orders['record_ids'],train['ids']),'Paired record order mismatch')
            ledger=[json.loads(line) for line in (folder/'ledger.jsonl').read_text().splitlines()]
            require(len(ledger)==200,'Wrong ledger horizon')
            train_work=expected_work(method,train,True);val_work=expected_work(method,val,False)
            for r,entry in enumerate(ledger,1):
                require(entry['round']==r and entry['optimizer_updates']==75*r,'Wrong round/update sequence')
                require(entry['work_cumulative']['training']=={k:v*r for k,v in train_work.items()},'Training work mismatch')
                require(entry['work_cumulative']['validation']=={k:v*r for k,v in val_work.items()},'Validation work mismatch')
            selected=min(range(200),key=lambda i:ledger[i]['validation']['bce'])+1
            require(selected==result['selected_round'],'Selected endpoint does not minimize validation BCE')
            require(hashes['selected_checkpoint_sha256']==s.digest(folder/f'selected_round_{selected:04d}.npz'),'Selected generation mismatch')
            with np.load(folder/'last_checkpoint.npz',allow_pickle=False) as last:
                require(int(last['completed_rounds'])==200 and int(last['current_round'])==200 and int(last['adam_t'])==15000,'Last checkpoint incomplete')
            with np.load(folder/'selected_checkpoint.npz',allow_pickle=False) as cp:
                require(int(cp['current_round'])==selected and int(cp['completed_rounds'])==selected and int(cp['adam_t'])==75*selected,'Selected checkpoint state mismatch')
                theta=cp['parameters'].copy()
            p=replay.predict(method,theta,val['x'],val['depth'],val['hash_route'],val['kmeans_route'])
            with (folder/'validation_predictions.csv').open(newline='',encoding='utf-8') as stream:saved=list(csv.DictReader(stream))
            require(len(saved)==1600,'Validation prediction count')
            for field,key in [('record_id','ids'),('original_depth','depth'),('hash_route','hash_route'),('kmeans_route','kmeans_route'),('label','y')]:
                require(np.array_equal(np.asarray([int(row[field]) for row in saved]),val[key]),'Validation population identity mismatch')
            saved_p=np.asarray([float(row['probability']) for row in saved]);err=float(np.max(abs(p-saved_p)))
            verification=numerical.verify_pair(val,saved_p,p);metric=verification['canonical_metrics']
            max_probability_error=max(max_probability_error,err)
            require(np.array_equal(np.asarray([int(row['prediction']) for row in saved]),(saved_p>=.5).astype(int)),'Saved predicted class mismatch')
            numerical.check_canonical_metrics(metric,result['selected_validation'])
            numerical.check_canonical_metrics(metric,ledger[selected-1]['validation'])
            max_metric_error=max(max_metric_error,verification['independent_bce_error'])
            fixture=np.argsort(val['ids'],kind='stable')[:1024]
            fixture_pop={k:v[fixture] for k,v in val.items()}
            comparison_work=expected_work(method,fixture_pop,False)
            require(result['inference']['work_separate_from_training']=={k:4*v for k,v in comparison_work.items()},'Measured inference work mismatch')
            rows.append({'seed':seed,'method':method,'path':str(folder.relative_to(s.ROOT)).replace('\\','/'),'selected_round':selected,
                         'selected_validation':metric,**hashes,'endpoint_commit_sha256':s.digest(folder/'endpoint_commit.json'),
                         'status_sha256':s.digest(folder/'status.json'),'validation_predictions_sha256':s.digest(folder/'validation_predictions.csv'),
                         'maximum_probability_error':err,
                         'numerical_verification':verification,
                         'reconstructed_cached_comparison_work':comparison_work,
                         'resource_addendum':'An additional cached comparison forward is executed outside the four measured inference forwards. Its work is reconstructed here; original training/results remain unchanged.'})
    numerical.verify_protocol()
    require(all(s.digest(s.ROOT/n)==digest for n,digest in audit_sources.items()),'Author audit source changed during verification')
    return {'status':'PASS','stage':stage,'endpoints':rows,'endpoint_count':len(rows),'test_accessed':False,'data_seal_sha256':data_hash,
            'stage_freeze_sha256':freeze_hash,'training_source_hashes':s.source_hashes(),
            'audit_sources':audit_sources,
            'numerical_recovery_protocol_sha256':numerical.PROTOCOL_SHA,
            'exact_class_agreement':all(row['numerical_verification']['counts']['exact_class_agreement'] for row in rows),
            'class_disagreements':sum(row['numerical_verification']['counts']['class_disagreements'] for row in rows),
            'maximum_probability_error':max_probability_error,'maximum_metric_error':max_metric_error,'created_utc':s.now(),
            'maximum_metric_error_scope':'Independent BCE difference; canonical confusion/F1/accuracy checked exactly against result and selected ledger.',
            'scope':'Full endpoint/ledger/order/work audit plus canonical validation metric replay, independent probability/BCE checks and explicit threshold-ambiguity verification. PASS does not imply exact classifier agreement. Root approval required for next stage or test release.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=['A','B'],required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    try:result=audit(args.stage,args.output)
    except BaseException as error:
        result={'status':'FAIL','stage':args.stage,'test_accessed':False,'error':str(error),'traceback':traceback.format_exc(),'created_utc':s.now()}
        s.write_json(args.output,result);raise
    s.write_json(args.output,result);print(f'PASS {result["endpoint_count"]} endpoints, max probability error {result["maximum_probability_error"]:.3g}')


if __name__=='__main__':main()
