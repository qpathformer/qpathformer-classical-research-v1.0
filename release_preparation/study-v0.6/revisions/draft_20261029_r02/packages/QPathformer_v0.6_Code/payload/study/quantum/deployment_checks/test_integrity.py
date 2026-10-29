"""Synthetic integrity and completion tests; no registered population access.

The integration test replaces the official release guard and latency measure
with explicit synthetic stubs. It tests inventory/assembly, not real release
authorization or performance. Every fixture is preserved outside the study.
"""
import csv
import json
import shutil
import sys
import types
import uuid
from pathlib import Path
from unittest.mock import patch
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import deployment_benchmark as b
import study as s
import routers

ACTUAL_ROOT=s.ROOT
FIXTURES=ACTUAL_ROOT.parent.parent/'Q2_v06_synthetic_deployment_fixtures'


def fixture():
    root=FIXTURES/('attempt_'+uuid.uuid4().hex);q=root/'quantum';(q/'data').mkdir(parents=True)
    (root/'governance').mkdir()
    for name in ('DEPLOYMENT_PROTOCOL.json','DEPLOYMENT_IMPLEMENTATION_NOTES.json'):
        shutil.copyfile(ACTUAL_ROOT.parent/'governance'/name,root/'governance'/name)
    shutil.copyfile(ACTUAL_ROOT/'deployment_compiler.py',q/'deployment_compiler.py')
    population='confirmation_synthetic';seed=1201
    policy={'schema':'qpath-v03-input-route-1','banks':5,'centroids':[[-.6,-.5],[-.4,.6],[0.,0.],[.5,-.4],[.6,.6]]}
    s.write_json(q/'data'/f'{population}_router.json',policy,True)
    rng=np.random.Generator(np.random.PCG64(690629));arrays={};seal={'files':{}}
    for split,n in (('validation',1024),('SEALED_test',40)):
        x=rng.uniform(-1,1,(n,2));arrays[split]={'x':x,'ids':np.arange(n),'kmeans_route':routers.route(x,policy,'kmeans')}
        path=q/'data'/f'{population}_{split}.npz';np.savez(path,**arrays[split]);seal['files'][path.name]={'sha256':s.digest(path)}
    s.write_json(q/'data/DATA_SEAL.json',seal,True)
    for name in ('EVALUATION_RELEASE.json','EVALUATION_REGISTRATION.json','CONFIRMATION_ENDPOINT_LOCK.json'):
        s.write_json(q/name,{'synthetic':True,'status':'synthetic_only'},True)
    out=q/'confirmation_evaluation';out.mkdir();paths=set()
    def write(relative,value):
        path=out/relative;path.parent.mkdir(parents=True,exist_ok=True);s.write_json(path,value,True);paths.add(relative)
    write('ACCESS_EVENT.json',{'synthetic':True});write('summary.json',{'synthetic':True})
    write(f'{population}/statistics/population_summary.json',{'synthetic':True})
    stat=out/population/'statistics/bootstrap_counts.npy';np.save(stat,np.zeros((2,40),dtype=np.int64));paths.add(stat.relative_to(out).as_posix())
    for method in s.METHODS:
        model=s.Model(method,seed);val=arrays['validation'];test=arrays['SEALED_test']
        vp,vz=model.predict_with_logits(val['x'],None if model.routing=='global' else val['kmeans_route'])
        tp,tz=model.predict_with_logits(test['x'],None if model.routing=='global' else test['kmeans_route'])
        folder=q/'stage_B'/population/f'seed_{seed}'/method;folder.mkdir(parents=True)
        np.savez(folder/'selected_checkpoint.npz',parameters=model.parameters,validation_probabilities=vp,validation_logits=vz)
        s.write_json(folder/'result.json',{'synthetic':True,'untrained':True},True)
        inventory={name:{'sha256':s.digest(folder/name),'bytes':(folder/name).stat().st_size} for name in ('selected_checkpoint.npz','result.json')}
        s.write_json(folder/'endpoint_commit.json',{'status':'completed','files':inventory,'synthetic':True},True)
        prefix=f'{population}/seed_{seed}/{method}'
        write(prefix+'/report.json',{'synthetic':True})
        csvpath=out/prefix/'predictions.csv'
        with csvpath.open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=['record_id','probability','native_logit']);writer.writeheader()
            writer.writerows({'record_id':int(i),'probability':repr(float(p)),'native_logit':repr(float(z))} for i,p,z in zip(test['ids'],tp,tz))
        paths.add(prefix+'/predictions.csv')
    commit={'status':'completed','study_id':'QPATH-GENERALIZATION-v0.6','report_count':6,'prediction_file_count':6,'population_count':1,'payload_count':len(paths),
            'files':{name:{'sha256':s.digest(out/name),'bytes':(out/name).stat().st_size} for name in paths}}
    for key,name in (('release_sha256','EVALUATION_RELEASE.json'),('registration_sha256','EVALUATION_REGISTRATION.json'),('endpoint_lock_sha256','CONFIRMATION_ENDPOINT_LOCK.json')):commit[key]=s.digest(q/name)
    s.write_json(out/'EVALUATION_COMMIT.json',commit,True)
    def safe(root,relative):
        p=(root/relative).resolve()
        if not p.is_relative_to(root.resolve()):raise RuntimeError('Unsafe path')
        return p
    fake=types.SimpleNamespace(expected_output_paths=lambda:paths.copy(),safe_path=safe,
        verify_guard=lambda **kwargs:({}, {}, {}, {q/'data/DATA_SEAL.json':s.digest(q/'data/DATA_SEAL.json')}))
    s.write_json(root/'SYNTHETIC_FIXTURE.json',{'scope':'Generated coordinates and untrained model parameters only. Fake release gate and mock latency. Never a registered study or measured benchmark.','source_benchmark_sha256':s.digest(Path(b.__file__))},True)
    return root,q,population,seed,arrays,fake


class IntegrityTests(unittest.TestCase):
    def test_sealed_hash_precedes_numpy_load(self):
        root,q,pop,seed,arrays,fake=fixture()
        path=q/'data'/f'{pop}_SEALED_test.npz';path.write_bytes(path.read_bytes()+b'altered')
        watched={q/'data/DATA_SEAL.json':s.digest(q/'data/DATA_SEAL.json')}
        with patch.object(s,'ROOT',q),patch.object(np,'load',side_effect=AssertionError('Must reject before array loading')):
            with self.assertRaisesRegex(RuntimeError,'Sealed data payload changed'):
                b.load_canonical_test(pop,seed,s.METHODS[0],{},watched)

    def test_commit_rejects_changed_extra_unsafe_and_incomplete(self):
        root,q,pop,seed,arrays,fake=fixture();cp=q/'confirmation_evaluation/EVALUATION_COMMIT.json';original=cp.read_bytes()
        with patch.object(s,'ROOT',q),patch.object(s,'POPULATIONS',{'B':(pop,)}),patch.object(s,'SEEDS',{'B':(seed,)}):
            watched={};b.checked_evaluation_commit(fake,watched)
            self.assertEqual(len(watched),17)
            extra=cp.parent/'EXTRA.txt';extra.write_text('extra')
            with self.assertRaises(RuntimeError):b.checked_evaluation_commit(fake,{})
            extra.unlink()
            for mutate in ('unsafe','missing','size','hash'):
                commit=json.loads(original)
                key=next(iter(commit['files']))
                if mutate=='unsafe':commit['files']['../escaped']=commit['files'].pop(key)
                if mutate=='missing':commit['files'].pop(key)
                if mutate=='size':commit['files'][key]['bytes']+=1
                if mutate=='hash':commit['files'][key]['sha256']='0'*64
                cp.write_text(json.dumps(commit))
                with self.assertRaises(RuntimeError):b.checked_evaluation_commit(fake,{})
                cp.write_bytes(original)
            altered=cp.parent/'summary.json';altered.write_text('{"changed":true}')
            with self.assertRaises(RuntimeError):b.checked_evaluation_commit(fake,{})

    def test_synthetic_complete_runner_with_mock_latency(self):
        root,q,pop,seed,arrays,fake=fixture();output=q/'synthetic_deployment_output'
        def mock_measure(forward,batches):
            p,z=forward(batches[0][:1]);n=sum(map(len,batches))
            return 1000,np.repeat(p,n),np.repeat(z,n)
        env={key:'1' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
        with patch.object(s,'ROOT',q),patch.object(s,'POPULATIONS',{'B':(pop,)}),patch.object(s,'SEEDS',{'B':(seed,)}),\
             patch.object(s,'load_population',side_effect=lambda p,split:arrays[split]),\
             patch.object(b,'PROTOCOL',root/'governance/DEPLOYMENT_PROTOCOL.json'),\
             patch.object(b,'IMPLEMENTATION_NOTES',root/'governance/DEPLOYMENT_IMPLEMENTATION_NOTES.json'),\
             patch.object(b,'assert_quiescent',return_value={'synthetic_mock':True}),patch.object(b,'measure_trial',side_effect=mock_measure),\
             patch.dict(sys.modules,{'evaluate_confirmation':fake}),patch.dict('os.environ',env):
            b.run(output)
            with self.assertRaises(FileExistsError):b.run(output)
        summary=s.read_json(output/'summary.json');commit=s.read_json(output/'DEPLOYMENT_COMMIT.json')
        self.assertEqual(summary['selected_checkpoints'],6);self.assertEqual(summary['compiled_checkpoints'],2)
        self.assertEqual(summary['fast_trig_checkpoints'],2);self.assertEqual(summary['timing_conditions'],30)
        self.assertEqual(summary['timed_trials'],450)
        self.assertEqual(len(s.read_json(output/'timing_trials.json')),510)
        self.assertEqual(set(commit['files']),{p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}-{'DEPLOYMENT_COMMIT.json'})
        for name,record in commit['files'].items():self.assertEqual(s.digest(output/name),record['sha256'])
        watched=summary['source_hashes']
        for split in ('validation','SEALED_test'):self.assertIn(str(q/'data'/f'{pop}_{split}.npz'),watched)
        s.write_json(root/'SYNTHETIC_COMPLETION_CHECK.json',{'status':'PASS','scope':'Mock timings only; no latency conclusions. Fake release guard. All integrity/assembly checks passed.','commit_sha256':s.digest(output/'DEPLOYMENT_COMMIT.json')},True)


if __name__=='__main__':unittest.main()
