"""Preserved synthetic capsule preflight with untrained initial parameters.

No registered population payload or selected trained checkpoint is loaded.
The original protocol is read-only; the official registered gate is not invoked.
"""
import sys
from pathlib import Path
from unittest.mock import patch
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import study as s
import local_readiness as r


def main():
    root=Path(r'C:\Anthony Siljeg\Q2_v05_synthetic_readiness_fixtures')/str(uuid.uuid4());q=root/'quantum';data=q/'data';data.mkdir(parents=True)
    population='synthetic_fixture';seed=8901;rng=np.random.Generator(np.random.PCG64(590503));n=32
    x=rng.uniform(-1,1,(n,2));route=np.arange(n)%5;ids=np.arange(n)+9000000
    payload=data/f'{population}_validation.npz'
    np.savez(payload,x=x,y=np.arange(n)%2,ids=ids,source_draw_ids=np.arange(n),kmeans_route=route,hash_route=route[::-1])
    router=data/f'{population}_router.json';s.write_json(router,{'synthetic':True,'policy':'Explicit cyclic routes for initial-state circuit testing only'},True)
    s.write_json(data/'DATA_SEAL.json',{'synthetic':True,'files':{payload.name:{'sha256':s.digest(payload)}},
        'routers':{population:{'sha256':s.digest(router)}}},True)
    base=q/'untrained_initial_states'
    for method in r.METHODS:
        folder=base/population/f'seed_{seed}'/method;folder.mkdir(parents=True);model=s.Model(method,seed)
        np.savez(folder/'selected_checkpoint.npz',parameters=model.parameters,core_parameters=model.core_parameters)
        s.write_json(folder/'result.json',{'status':'synthetic_untrained','inference':{'scope':'No measured latency; generated untrained fixture'},
            'frozen_cache':{'enabled':model.frozen,'scope':'No cached training performed'},'parameter_count':len(model.parameters),
            'fixed_core_parameter_count':model.core_parameters.size},True)
        s.write_json(folder/'endpoint_commit.json',{'status':'completed','synthetic_untrained':True,
            'files':{p.name:{'sha256':s.digest(p),'bytes':p.stat().st_size} for p in folder.iterdir()}},True)
    protocol=s.read_json(r.PROTOCOL);watched={r.PROTOCOL:s.digest(r.PROTOCOL),Path(r.__file__):s.digest(r.__file__),Path(__file__):s.digest(__file__)}
    s.write_json(root/'SYNTHETIC_FIXTURE.json',{'scope':'Generated coordinates/cyclic routes and untrained initial parameters only. No registered population/test/trained checkpoint loaded.',
        'seed':590503,'source_hashes':s.source_hashes(),'protocol_sha256':s.digest(r.PROTOCOL),'created_utc':s.now()},True)
    with patch.object(s,'ROOT',q),patch.object(s,'ENGINEERING',(population,)):
        r.execute_capsule((population,),(seed,),base,root/'capsule',protocol,watched,True)
    print('SYNTHETIC_OUTPUT='+str(root))


if __name__=='__main__':main()
