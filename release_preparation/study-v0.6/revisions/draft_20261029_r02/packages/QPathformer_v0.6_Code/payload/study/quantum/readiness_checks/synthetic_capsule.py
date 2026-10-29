"""Preserved capsule preflight on generated inputs and untrained parameters only.

No actual registered data, endpoints or sealed test payloads are opened. The
production capsule's internal execution helper is exercised against an isolated
fixture tree; its public root-release gate is never bypassed for real evidence.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
import json
import shutil
from unittest.mock import patch
import numpy as np
import study as s
import local_readiness as capsule


def run(output_root):
    root=Path(output_root)
    if root.exists():raise FileExistsError(root)
    root.mkdir(parents=True,exist_ok=False)
    original=s.ROOT;protocol=s.read_json(original.parent/'governance/LOCAL_READINESS_PROTOCOL.json')
    population='generated_untrained_fixture';seed=690601
    rng=np.random.Generator(np.random.PCG64(690602))
    x=rng.uniform(-1,1,(32,2));ids=np.arange(32,dtype=np.int64)
    pop={'x':x,'y':np.zeros(32,dtype=np.int64),'ids':ids,'source_draw_ids':ids,
         'hash_route':ids%5,'kmeans_route':ids%5}
    data=root/'data';data.mkdir();np.savez(data/f'{population}_validation.npz',**pop)
    s.write_json(data/f'{population}_router.json',{'synthetic':True,'route':'record position modulo5; no fitted/real router'},True)
    (root/'device_snapshot').mkdir()
    shutil.copyfile(original/'device_snapshot/SNAPSHOT_MANIFEST.json',root/'device_snapshot/SNAPSHOT_MANIFEST.json')
    base=root/'generated_checkpoints'
    for method in capsule.METHODS:
        model=s.Model(method,seed)
        # Explicitly random, untrained values, covering both nonzero heads.
        model.parameters[:]=rng.uniform(-1.5,1.5,model.parameters.size)
        folder=base/population/f'seed_{seed}'/method;folder.mkdir(parents=True)
        np.savez(folder/'selected_checkpoint.npz',parameters=model.parameters,core_parameters=model.core_parameters)
        s.write_json(folder/'result.json',{'inference':{'synthetic':True},'frozen_cache':{'enabled':False},
                      'parameter_count':len(model.parameters),'fixed_core_parameter_count':0},True)
        files={p.name:{'sha256':s.digest(p),'bytes':p.stat().st_size} for p in folder.iterdir()}
        s.write_json(folder/'endpoint_commit.json',{'status':'completed','synthetic_untrained':True,'files':files},True)
    sources={p:s.digest(p) for p in (original/'local_readiness.py',original/'snapshot_execution.py',
              original/'device_snapshot.py',original/'circuits.py',original/'models.py',Path(__file__))}
    s.write_json(root/'SYNTHETIC_SCOPE.json',{'scope':'Generated32 inputs and two untrained parameter vectors; no registered dataset/model/test access.',
                  'source_hashes':{str(p):h for p,h in sources.items()},'created_utc':s.now()},True)
    def load(population_name,split):
        if (population_name,split)!=(population,'validation'):raise RuntimeError('Synthetic driver blocked any other data access')
        return {k:a.copy() for k,a in pop.items()}
    with patch.object(s,'ROOT',root),patch.object(s,'load_population',load):
        capsule.execute_capsule((population,),(seed,),base,root/'capsule',protocol,sources,True)
    report=s.read_json(root/'capsule/report.json')
    s.require(report['checkpoint_count']==2 and report['checkpoint_fixture_pairs']==64,'Synthetic coverage mismatch')
    s.require(report['finite_shot_count_array_count']==90 and report['finite_shot_predictor_array_count']==60,'Synthetic shot inventory mismatch')
    s.require(report['actual_simulated_measurement_shots']==49152,'Synthetic measured shot count mismatch')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-root',type=Path,required=True)
    a=p.parse_args();r=run(a.output_root)
    print(json.dumps({k:r[k] for k in ('status','checkpoint_count','checkpoint_fixture_pairs','finite_shot_count_array_count','actual_simulated_measurement_shots')}))
