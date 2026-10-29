"""Author full-horizon evidence audit; no test data or optimizer reruns.

Replays every validation round through production and the selected state through
an independent scalar oracle. The separate reviewer must independently replay
ALL validation rounds with its own oracle before a stage is accepted by root.
"""
import argparse
import csv
import json
from pathlib import Path
import traceback
import numpy as np
import study as s
import verification as v


def audit_endpoint(folder,stage,population,seed,method,engineering=False):
    folder=Path(folder);commit=s.read_json(folder/'endpoint_commit.json')
    s.require(commit.get('status')=='completed','Endpoint not committed')
    s.require((commit['population'],commit['seed'],commit['method'])==(population,seed,method),'Commit identity mismatch')
    inventory=commit['files'];actual={p.name for p in folder.iterdir() if p.is_file() and p.name!='endpoint_commit.json'}
    s.require(actual==set(inventory) and bool(inventory),'Endpoint inventory mismatch')
    s.require(not any(p.is_symlink() for p in folder.iterdir()),'Endpoint symlink rejected')
    for name,meta in inventory.items():
        s.require(Path(name).name==name,'Nonlocal endpoint artifact')
        p=folder/name;s.require(p.stat().st_size==meta['bytes'] and s.digest(p)==meta['sha256'],'Committed payload changed: '+name)
    config=s.read_json(folder/'config.json');result=s.read_json(folder/'result.json');status=s.read_json(folder/'status.json')
    for item in (config,result,status):
        s.require((item['population'],item['seed'],item['method'])==(population,seed,method),'Endpoint identity mismatch')
    s.require(config['study_id']==result['study_id']=='QPATH-READOUT-v0.5','Study identity mismatch')
    s.require(config['engineering']==engineering and result['engineering']==engineering,'Engineering/official mix')
    rounds=config['rounds'];s.require(rounds>=1 and (engineering or rounds==200),'Incorrect horizon')
    s.require(status['status']=='completed' and status['round']==rounds and result['completed_rounds']==rounds,'Incomplete endpoint')
    if not engineering:
        s.verify_freeze(stage,population,seed,method)
        s.require(config['stage_freeze_sha256']==s.digest(s.ROOT/f'STAGE_{stage}_FREEZE.json'),'Stage freeze mismatch')
    source=s.source_hashes();s.require(config['source_hashes']==source==commit['source_hashes'],'Training sources mismatch')
    s.require(config['data_seal_sha256']==s.digest(s.ROOT/'data/DATA_SEAL.json'),'Data seal mismatch')
    train=s.load_population(population,'train');val=s.load_population(population,'validation')
    if engineering:
        train={k:a[:config['train_records']] for k,a in train.items()};val={k:a[:config['validation_records']] for k,a in val.items()}
    s.require((len(train['y']),len(val['y']))==(config['train_records'],config['validation_records']),'Split size mismatch')
    model=s.Model(method,seed)
    with np.load(folder/'initial_state.npz',allow_pickle=False) as initial:
        s.require(np.array_equal(initial['parameters'],model.parameters),'Initialization parameters changed')
        s.require(np.array_equal(initial['master_initial'],model.master_initial),'Initialization master changed')
        s.require(np.array_equal(initial['core_parameters'],model.core_parameters),'Frozen core initialization changed')
    with np.load(folder/'population_identity.npz',allow_pickle=False) as identity:
        s.require(np.array_equal(identity['train_ids'],train['ids']) and np.array_equal(identity['validation_ids'],val['ids']),'Population IDs changed')
    states=np.load(folder/'round_parameters.npy',allow_pickle=False,mmap_mode='r')
    probabilities=np.load(folder/'validation_probabilities.npy',allow_pickle=False,mmap_mode='r')
    native_losses=np.load(folder/'validation_native_losses.npy',allow_pickle=False,mmap_mode='r')
    logits=np.load(folder/'validation_logits.npy',allow_pickle=False,mmap_mode='r') if model.native_logits else None
    s.require(model.native_logits or not (folder/'validation_logits.npy').exists(),'Legacy native logits invented')
    orders=np.load(folder/'record_orders.npy',allow_pickle=False,mmap_mode='r')
    s.require(states.shape==(rounds,len(model.parameters)) and states.dtype==np.float64,'State array shape/dtype')
    s.require(probabilities.shape==(rounds,len(val['y'])) and probabilities.dtype==np.float64,'Probability array shape/dtype')
    s.require(native_losses.shape==(rounds,) and native_losses.dtype==np.float64 and np.isfinite(native_losses).all(),'Native loss evidence invalid')
    if logits is not None:s.require(logits.shape==probabilities.shape and logits.dtype==np.float64 and np.isfinite(logits).all(),'Native logit evidence invalid')
    s.require(orders.shape==(rounds,len(train['y'])) and orders.dtype==np.uint16,'Order shape/dtype')
    s.require(np.isfinite(states).all() and np.isfinite(probabilities).all(),'Unwritten/nonfinite round evidence')
    ledger=[json.loads(line) for line in (folder/'ledger.jsonl').read_text().splitlines()]
    s.require(len(ledger)==rounds,'Incomplete ledger')
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,2])))
    cache=result['frozen_cache'];cached=None;cache_work={}
    s.require(cache['enabled']==model.frozen,'Feature cache arm mismatch')
    if model.frozen:
        s.require(s.read_json(folder/'frozen_cache.json')==cache,'Cache metadata differs')
        s.require(cache['core_sha256']==s.array_digest(model.core_parameters),'Cache core identity mismatch')
        for part,pop in (('train',train),('validation',val)):
            item=cache['records'][part];a=np.load(folder/item['file'],allow_pickle=False)
            s.require(s.digest(folder/item['file'])==item['file_sha256'] and s.array_digest(a)==item['array_sha256'],'Cache bytes changed')
            s.require(a.shape==(len(pop['y']),5) and item['shape']==list(a.shape) and item['bytes']==a.nbytes,'Cache shape/bytes mismatch')
            for key,value in (('ids',pop['ids']),('route',model.route_for(pop)),('input',pop['x'])):
                s.require(s.array_digest(value)==item[key+'_sha256'],'Cache population identity mismatch')
            s.require(np.array_equal(a,model.cache_features(pop['x'],model.route_for(pop))),'Cache replay mismatch')
            cache_work[part]=model.cache_accounting(pop['x'],model.route_for(pop))
            if part=='validation':cached=a
        s.require(cache['work']==cache_work and cache['bytes']==(len(train['y'])+len(val['y']))*5*8,'Cache work/storage mismatch')
    work={'training':{},'validation':{},'fixed_feature_preparation':cache_work};visits=np.zeros(model.banks,dtype=np.int64)
    best=float('inf');selected=None;maximum=0.;updates_per_round=(len(train['y'])+63)//64
    for i,row in enumerate(ledger):
        s.require(row['round']==i+1 and row['optimizer_updates']==(i+1)*updates_per_round,'Round/update sequence')
        order=rng.permutation(len(train['y'])).astype(np.uint16)
        s.require(np.array_equal(order,orders[i]),'Paired sample order mismatch')
        for array,key in ((states[i],'round_parameter_sha256'),(probabilities[i],'validation_probability_sha256'),(orders[i],'record_order_sha256')):
            s.require(s.array_digest(array)==row[key],'Round array commitment mismatch')
        s.require(s.array_digest(native_losses[i:i+1])==row['validation_native_loss_sha256'],'Native loss row hash')
        s.require(row['validation_logit_sha256']==(None if logits is None else s.array_digest(logits[i])),'Native logit row hash')
        model.parameters[:]=states[i];p,z=model.predict_with_logits(val['x'],model.route_for(val),cached)
        error=float(np.max(abs(p-probabilities[i])));maximum=max(maximum,error)
        s.require(error<=2e-12,'Full-round production replay mismatch')
        if z is not None:s.require(np.max(abs(z-logits[i]))<=1e-9,'Full-round native logit replay mismatch')
        s.require(abs(model.loss(val['y'],p,z)-native_losses[i])<=1e-8,'Full-round native loss replay mismatch')
        s.require(row['validation_native']==s.native_diagnostics(model,val['y'],probabilities[i],None if logits is None else logits[i]),'Native diagnostics mismatch')
        canonical=s.metrics(val['y'],probabilities[i]);v.check_canonical(canonical,row['validation'])
        chosen=canonical['bce']<best;s.require(row['selected']==chosen,'Earliest minimum selection flag mismatch')
        if chosen:best=canonical['bce'];selected=i+1
        s.add_work(work['training'],model.accounting(train['x'],model.route_for(train),gradient=True,cached_features=model.frozen))
        s.add_work(work['validation'],model.accounting(val['x'],model.route_for(val),cached_features=model.frozen))
        for ids,bank,sl in model.components(train['x'],model.route_for(train)):visits[bank]+=len(ids)
        s.require(row['work_cumulative']==work and row['bank_record_visits_cumulative']==visits.tolist(),'Work/exposure mismatch')
    s.require(result['selected_round']==selected,'Selected round mismatch')
    s.require(result['optimizer_global_updates']==rounds*updates_per_round,'Final updates mismatch')
    s.require(result['work']['training']==work['training'] and result['work']['validation']==work['validation'],'Result work mismatch')
    s.require(result['bank_training_record_visits']==visits.tolist(),'Result exposure mismatch')
    s.require(result['parameter_count']==len(model.parameters) and result['fixed_core_parameter_count']==model.core_parameters.size,'Parameter counts')
    s.require(result['stored_model_parameter_count']==len(model.parameters)+model.core_parameters.size,'Stored parameter count')
    s.require(result['fixed_core_sha256']==s.array_digest(model.core_parameters),'Fixed core hash')
    for filename,index in (('selected_checkpoint.npz',selected-1),('last_checkpoint.npz',rounds-1)):
        with np.load(folder/filename,allow_pickle=False) as c:
            s.require(np.array_equal(c['parameters'],states[index]),'Checkpoint parameters differ from round state')
            s.require(np.array_equal(c['core_parameters'],model.core_parameters),'Checkpoint fixed core changed')
            s.require(bool(c['validation_evidence_present']) and bool(c['has_native_logits'])==model.native_logits,'Checkpoint native schema')
            s.require(np.array_equal(c['validation_probabilities'],probabilities[index]),'Checkpoint validation probabilities')
            s.require(np.array_equal(c['validation_logits'],np.array([]) if logits is None else logits[index]),'Checkpoint validation logits')
            s.require(np.array_equal(c['validation_native_loss'],np.array([native_losses[index]])),'Checkpoint native loss')
            s.require(int(c['adam_t'])==(index+1)*updates_per_round and int(c['completed_rounds'])==index+1,'Checkpoint horizon mismatch')
            s.require(c['adam_m'].shape==model.parameters.shape and c['adam_v'].shape==model.parameters.shape,'Adam shape')
            s.require(np.isfinite(c['adam_m']).all() and np.isfinite(c['adam_v']).all() and np.all(c['adam_v']>=0),'Invalid Adam state')
    model.parameters[:]=states[selected-1];p=np.asarray(probabilities[selected-1])
    with (folder/'validation_predictions.csv').open(newline='') as f:csvrows=list(csv.DictReader(f))
    s.require(len(csvrows)==len(p),'Prediction row count')
    for i,row in enumerate(csvrows):
        s.require(int(row['record_id'])==int(val['ids'][i]) and int(row['label'])==int(val['y'][i]),'Prediction identity/label')
        s.require(int(row['hash_route'])==int(val['hash_route'][i]) and int(row['kmeans_route'])==int(val['kmeans_route'][i]),'Prediction routes')
        s.require(float(row['probability'])==p[i] and int(row['prediction'])==int(p[i]>=.5),'Canonical CSV prediction')
        s.require(row['native_logit']=='' if logits is None else float(row['native_logit'])==logits[selected-1,i],'CSV native logit')
    v.check_canonical(s.metrics(val['y'],p),result['selected_validation'])
    oracle,oz=v.scalar_reference_with_logits(method,model.parameters,val['x'],model.route_for(val),model.core_parameters)
    numerical=v.verify_pair(val,p,oracle)
    numerical['native']=v.verify_native(val['y'],None if logits is None else logits[selected-1],oz,float(native_losses[selected-1]))
    # Recheck every immutable endpoint byte after replay; no changed endpoint accepted.
    for name,meta in inventory.items():s.require(s.digest(folder/name)==meta['sha256'],'Endpoint changed during audit')
    return {'population':population,'seed':seed,'method':method,'path':str(folder.resolve()),'rounds':rounds,
            'optimizer_updates':rounds*updates_per_round,'selected_round':selected,'selected_validation':s.metrics(val['y'],p),
            'validation_rounds_replayed':rounds,'validation_record_predictions_replayed':rounds*len(p),
            'maximum_full_round_production_probability_error':maximum,'numerical_verification':numerical,
            'endpoint_commit_sha256':s.digest(folder/'endpoint_commit.json'),'files':inventory}


def run(stage,output,engineering_root=None):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    rows=[];source=s.source_hashes();seal=s.digest(s.ROOT/'data/DATA_SEAL.json')
    bound={p:s.digest(p) for p in (Path(__file__),s.ROOT/'verification.py',s.ROOT.parent/'governance/ANALYSIS_PROTOCOL.json')}
    try:
        if engineering_root is None:
            root=s.ROOT/f'stage_{stage}';st=s.read_json(root/'stage_status.json')
            s.require(st['status']=='completed' and all(x['exit_code']==0 for x in st['exits']),'Stage workers not successfully closed')
            populations=s.POPULATIONS[stage];seeds=s.SEEDS[stage]
        else:root=Path(engineering_root);populations=s.ENGINEERING;seeds=(8901,)
        expected=len(populations)*len(seeds)*len(s.METHODS)
        s.require(len(list(root.glob('*/seed_*/*/endpoint_commit.json')))==expected,'Endpoint count mismatch')
        for population in populations:
            for seed in seeds:
                for method in s.METHODS:
                    rows.append(audit_endpoint(root/population/f'seed_{seed}'/method,stage,population,seed,method,engineering_root is not None))
        s.require(s.source_hashes()==source and s.digest(s.ROOT/'data/DATA_SEAL.json')==seal,'Frozen source/data changed during audit')
        for path,digest in bound.items():s.require(s.digest(path)==digest,'Audit/protocol source changed')
        result={'status':'PASS','stage':stage,'engineering':engineering_root is not None,'endpoint_count':len(rows),
                'endpoints':rows,'source_hashes':source,'data_seal_sha256':seal,
                'analysis_protocol_sha256':bound[s.ROOT.parent/'governance/ANALYSIS_PROTOCOL.json'],
                'audit_source_hashes':{str(k):v for k,v in bound.items()},'created_utc':s.now(),'test_accessed':False,
                'stage_freeze_sha256':None if engineering_root is not None else s.digest(s.ROOT/f'STAGE_{stage}_FREEZE.json'),
                'scope':'Author full-round production replay and selected-round independent scalar oracle; separate independent ALL-round oracle audit is also mandatory. Not a rerun of every Adam update.'}
        s.write_json(output,result,True);print(f'PASS {len(rows)} endpoints; '+str(sum(r['validation_record_predictions_replayed'] for r in rows))+' round-record predictions')
    except BaseException as error:
        s.write_json(output,{'status':'FAIL','stage':stage,'completed_endpoint_count':len(rows),'error':str(error),
                    'traceback':traceback.format_exc(),'created_utc':s.now(),'test_accessed':False},True);raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=s.SEEDS,default='A')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--engineering-root',type=Path)
    a=p.parse_args();run(a.stage,a.output,a.engineering_root)


if __name__=='__main__':main()
