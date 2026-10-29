"""Recreate four registered populations from frozen streams; no model imports."""
from pathlib import Path
import hashlib
import json
import time
import numpy as np

def require(value,message):
    if not value:raise RuntimeError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def binding(path):
    p=Path(path).resolve();return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def coordinate_payload(path,expected,d):
    require(sha(path)==expected,'Freshness coordinate source changed')
    with np.load(path,allow_pickle=False) as data:x=data['x']
    return set(d.feature_keys(x))

def recreate(root,clean,d,registered_jobs):
    """d is imported ONLY from the clean copied frozen scientific directory."""
    root,clean=Path(root),Path(clean)
    require(Path(d.__file__).resolve()==clean/'quantum/prepare_data.py','Generator not loaded from clean source')
    matrix=read(root/'governance/RUN_MATRIX.json')
    original=root/'quantum/data';seal=read(original/'DATA_SEAL.json')
    registration=read(root/'governance/DATA_REGISTRATION.json')
    require(sha(root/'governance/DATA_REGISTRATION.json')==seal['registration_sha256'],'Registration changed')
    populations={job['population_id'] for job in registered_jobs}
    require(len(populations)==4,'Four distinct reproduction populations required')
    excluded=set();historical=[];started=time.perf_counter()
    # These are coordinate-only inputs to freshness, never labels or checkpoints.
    for row in seal['historical_sources']:
        p=Path(row['path'])
        excluded.update(coordinate_payload(p,row['sha256'],d))
        historical.append(binding(p))
    require(len(excluded)==registration['historical_unique_observed'],'Historical exclusion universe changed')
    history_seconds=time.perf_counter()-started
    destination=clean/'quantum/data';destination.mkdir(parents=True,exist_ok=False)
    original_seal=(original/'DATA_SEAL.json').read_bytes()
    reports=[];prior_sources=[]
    last=max(i for i,pop in enumerate(matrix['populations']) if pop['population_id'] in populations)
    for ordinal,population in enumerate(matrix['populations'][:last+1]):
        name=population['population_id']
        if name not in populations:
            for split in ('train','validation','SEALED_test'):
                filename=f'{name}_{split}.npz';p=original/filename
                excluded.update(coordinate_payload(p,seal['files'][filename]['sha256'],d))
                prior_sources.append(binding(p))
            continue
        begin=time.perf_counter();cpu=time.process_time()
        parts,latent,redraw,keys=d.generate(population,excluded,registration['record_id_base']+ordinal*1000000)
        require(redraw==seal['datasets'][name]['redraw'],'Regenerated draw/exclusion/strata history differs')
        require(keys.isdisjoint(excluded),'Regenerated coordinates overlap previous inputs')
        excluded.update(keys)
        salt='qpath-v08-population-hash-'+str(d.stream_value(population['proposed_streams']['hash_salt']))
        all_x=np.concatenate([parts[s]['x'] for s in ('train','validation','test')])
        hashes=d.feature_hashes(all_x,salt)
        require(len(hashes)==len(set(hashes)),'Regenerated input hash collision')
        fit_start=time.perf_counter()
        policy=d.fit_route_policy(parts['train']['x'],d.stream_value(population['proposed_streams']['kmeans_initialization']),salt)
        fit_seconds=time.perf_counter()-fit_start
        policy['population']=name
        policy['training_ids_array_sha256']=d.array_hash(parts['train']['ids'])
        policy['margin_bins']=d.fit_margin_bins(parts['train']['x'],policy)
        router=destination/f'{name}_router.json';d.write_json(router,policy)
        require(sha(router)==seal['routers'][name]['sha256'],'Regenerated router bytes differ')
        payloads=[];hidden={}
        for split,part in parts.items():
            for kind in ('hash','kmeans'):part[kind+'_route']=d.route(part['x'],policy,kind)
            part['margin_bin']=d.margin_bins(part['x'],policy,policy['margin_bins'])
            for key,value in latent[split].items():hidden[f'{split}_{key}']=value
            filename=f"{name}_{'SEALED_test' if split=='test' else split}.npz"
            path=destination/filename
            with path.open('xb') as f:np.savez(f,**part)
            expected=seal['files'][filename]
            require({key:d.array_hash(value) for key,value in part.items()}==expected['arrays'],
                    'Regenerated population arrays differ')
            require(sha(path)==expected['sha256'],'Regenerated NPZ bytes differ')
            payloads.append(binding(path))
        latent_path=destination/f'{name}_SEALED_diagnostics.npz'
        with latent_path.open('xb') as f:np.savez(f,**hidden)
        require(sha(latent_path)==seal['diagnostics'][name]['sha256'],'Regenerated latent evidence differs')
        reports.append({'population_id':name,'ordinal':ordinal,'source_streams':population['proposed_streams'],
                        'public_payloads':payloads,'router':binding(router),'latent_payload':binding(latent_path),
                        'redraw':redraw,'wall_seconds':time.perf_counter()-begin,
                        'process_cpu_seconds':time.process_time()-cpu,'router_fit_seconds':fit_seconds,
                        'copied_original_data_arrays':False,'copied_original_router':False})
    require(len(reports)==4,'Incomplete clean population recreation')
    # Exact original metadata preserves the unmodified trainer's data/source gate.
    # Its original preparation charge is not a new measurement; actual costs above.
    with (destination/'DATA_SEAL.json').open('xb') as f:f.write(original_seal)
    return {'schema':'qpath-v08-clean-data-recreation-1','status':'PASS','population_count':4,
            'historical_coordinate_payloads':historical,'preceding_current_population_coordinate_payloads':prior_sources,
            'historical_exclusion_seconds':history_seconds,'populations':reports,
            'copied_metadata_only_data_seal':binding(destination/'DATA_SEAL.json'),
            'scope':'Data and routers regenerated from frozen streams. Historical and preceding new population x arrays supply exact exclusion only. No original labels, trained parameters or checkpoints copied. Hidden flags remain isolated.',
            'preparation_cost_scope':'Original seal preparation charges remain copied metadata for exact unchanged trainer validation; recreated preparation costs are measured separately above and must not be double counted.'}
