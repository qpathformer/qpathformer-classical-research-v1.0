"""Synthetic gate/output tests; no real confirmation data is opened."""
import copy
import builtins
import io
import json
from pathlib import Path,PureWindowsPath
import shutil
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import study as s
import evaluate_confirmation as e
import verification as v
from path_mapping import remap_recorded

ACTUAL_ROOT=s.ROOT
ORIGINAL=r'C:\QPATH_UNAVAILABLE_ORIGINAL\study'


def build_fixture():
    root=Path(r'C:\Anthony Siljeg\Q2_v06_synthetic_evaluator_fixtures')/str(uuid.uuid4())
    q=root/'quantum';q.mkdir(parents=True);(root/'governance').mkdir();(root/'analysis/classical_review').mkdir(parents=True)
    for name in s.source_hashes():
        dest=q/name;dest.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(ACTUAL_ROOT/name,dest)
    extra=['audit_stage.py','verification.py','evaluate_confirmation.py','path_mapping.py','local_readiness.py']
    for name in extra:shutil.copyfile(ACTUAL_ROOT/name,q/name)
    for name in ('ANALYSIS_PROTOCOL.json','LOCAL_READINESS_PROTOCOL.json','DEPLOYMENT_PROTOCOL.json'):
        shutil.copyfile(ACTUAL_ROOT.parent/'governance'/name,root/'governance'/name)
    for name in ('audit_endpoints_v06.py','reference_v06.py'):
        shutil.copyfile(ACTUAL_ROOT.parent/'analysis/classical_review'/name,root/'analysis/classical_review'/name)
    shutil.copyfile(ACTUAL_ROOT.parent/'analysis/statistics_v06.py',root/'analysis/statistics_v06.py')
    (q/'data').mkdir();s.write_json(q/'data/DATA_SEAL.json',{'classification':'SYNTHETIC_METADATA_ONLY_NO_TEST_PAYLOAD'})
    source={name:s.digest(q/name) for name in s.source_hashes()}
    freeze={'review_status':'approved_by_root','methods':list(s.METHODS),'populations':list(s.POPULATIONS['B']),
        'training_seeds':list(s.SEEDS['B']),'settings':s.SETTINGS,'source_hashes':source,'data_seal_sha256':s.digest(q/'data/DATA_SEAL.json')}
    s.write_json(q/'STAGE_B_FREEZE.json',freeze)
    rows=[];independent=[]
    for pop in s.POPULATIONS['B']:
        for seed in s.SEEDS['B']:
            for method in s.METHODS:
                folder=q/'stage_B'/pop/f'seed_{seed}'/method;folder.mkdir(parents=True)
                model=s.Model(method,seed)
                np.savez(folder/'selected_checkpoint.npz',parameters=model.parameters,core_parameters=model.core_parameters)
                result={'status':'completed','population':pop,'seed':seed,'method':method,'stage':'B','engineering':False,
                        'completed_rounds':200,'optimizer_global_updates':15000}
                s.write_json(folder/'result.json',result);s.write_json(folder/'status.json',{'status':'completed','round':200})
                files={p.name:{'sha256':s.digest(p),'bytes':p.stat().st_size} for p in folder.iterdir()}
                s.write_json(folder/'endpoint_commit.json',{'status':'completed','files':files})
                h=s.digest(folder/'endpoint_commit.json')
                rows.append({'population':pop,'seed':seed,'method':method,'selected_round':1,
                  'path':str(PureWindowsPath(ORIGINAL)/'quantum'/'stage_B'/pop/f'seed_{seed}'/method),
                  'endpoint_commit_sha256':h,'files':files})
                independent.append({'population':pop,'seed':seed,'method':method,'endpoint_commit_sha256':h,
                                    'selected_checkpoint_sha256':s.digest(folder/'selected_checkpoint.npz'),
                                    'rounds_verified':200,'validation_predictions_replayed':320000})
    s.write_json(q/'stage_B/stage_status.json',{'status':'completed','committed_endpoints':120,'exits':[{'seed':seed,'exit_code':0} for seed in s.SEEDS['B']]})
    lock={'status':'PASS','stage':'B','engineering':False,'endpoint_count':120,'endpoints':rows,
          'created_utc':'2026-10-18T00:00:00+00:00','source_hashes':source,'data_seal_sha256':freeze['data_seal_sha256'],
          'stage_freeze_sha256':s.digest(q/'STAGE_B_FREEZE.json'),'analysis_protocol_sha256':s.digest(root/'governance/ANALYSIS_PROTOCOL.json'),
          'audit_source_hashes':{str(PureWindowsPath(ORIGINAL)/'quantum'/name):s.digest(q/name) for name in ('audit_stage.py','verification.py')}}
    s.write_json(q/'CONFIRMATION_ENDPOINT_LOCK.json',lock)
    audit_path=root/'analysis/classical_review/SYNTHETIC_INDEPENDENT_AUDIT.json'
    auditor='analysis/classical_review/audit_endpoints_v06.py'
    audit={'status':'PASS','stage':'B','engineering':False,'endpoint_count':120,'validation_rounds_replayed':24000,
        'created_utc':'2026-10-18T00:01:00+00:00','endpoint_lock_sha256':s.digest(q/'CONFIRMATION_ENDPOINT_LOCK.json'),
        'data_seal_sha256':freeze['data_seal_sha256'],'analysis_protocol_sha256':lock['analysis_protocol_sha256'],
        'auditor_sha256':s.digest(root/auditor),'endpoints':independent,
        'independent_source_sha256':{name:s.digest(root/'analysis/classical_review'/name) for name in ('audit_endpoints_v06.py','reference_v06.py')}}
    s.write_json(audit_path,audit)
    review={'status':'PASS','stage':'B','endpoint_count':120,'endpoint_lock_sha256':s.digest(q/'CONFIRMATION_ENDPOINT_LOCK.json'),
        'independent_audit_path':audit_path.relative_to(root).as_posix(),'independent_audit_sha256':s.digest(audit_path)}
    s.write_json(q/'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json',review)
    source_paths=['quantum/'+name for name in extra]+[auditor,'analysis/classical_review/reference_v06.py','analysis/statistics_v06.py']
    reg={'status':'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS','original_working_root':ORIGINAL,
         'methods':list(s.METHODS),'populations':list(s.POPULATIONS['B']),'training_seeds':list(s.SEEDS['B']),
         'training_source_hashes':source,'source_hashes':{name:s.digest(root/name) for name in source_paths},
         'expected_output_paths':sorted(e.expected_output_paths()),'independent_auditor_path':auditor,
         'analysis_protocol_sha256':lock['analysis_protocol_sha256'],'readiness_protocol_sha256':s.digest(root/'governance/LOCAL_READINESS_PROTOCOL.json'),'deployment_protocol_sha256':s.digest(root/'governance/DEPLOYMENT_PROTOCOL.json'),
         'data_seal_sha256':freeze['data_seal_sha256']}
    s.write_json(q/'EVALUATION_REGISTRATION.json',reg)
    ready_dir=root/'analysis/independent_replay';ready_dir.mkdir()
    (ready_dir/'synthetic_adapter.py').write_text('# Synthetic marker only\n');s.write_json(ready_dir/'synthetic_evidence.json',{'synthetic':True})
    ready={'status':'READY_BEFORE_CONFIRMATION_TEST_ACCESS','study_id':'QPATH-GENERALIZATION-v0.6',
           'registration_sha256':s.digest(q/'EVALUATION_REGISTRATION.json'),'analysis_protocol_sha256':lock['analysis_protocol_sha256'],
           'independent_oracle_path':'analysis/classical_review/reference_v06.py','independent_oracle_sha256':s.digest(root/'analysis/classical_review/reference_v06.py'),
           'source_hashes':{'analysis/independent_replay/synthetic_adapter.py':s.digest(ready_dir/'synthetic_adapter.py')},
           'evidence_hashes':{'analysis/independent_replay/synthetic_evidence.json':s.digest(ready_dir/'synthetic_evidence.json')}}
    s.write_json(ready_dir/'ANALYSIS_READY.json',ready)
    release={'status':'released_by_root','study_id':'QPATH-GENERALIZATION-v0.6','scope':'all_120_registered_confirmation_endpoints_once',
             'release_id':'SYNTHETIC_NOT_REAL_RELEASE','created_utc':'2026-10-18T00:02:00+00:00',
             'independent_replay_ready_sha256':s.digest(ready_dir/'ANALYSIS_READY.json')}
    for key,path in {'registration_sha256':q/'EVALUATION_REGISTRATION.json','endpoint_lock_sha256':q/'CONFIRMATION_ENDPOINT_LOCK.json',
         'independent_endpoint_review_sha256':q/'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json','stage_freeze_sha256':q/'STAGE_B_FREEZE.json',
         'data_seal_sha256':q/'data/DATA_SEAL.json','analysis_protocol_sha256':root/'governance/ANALYSIS_PROTOCOL.json',
         'readiness_protocol_sha256':root/'governance/LOCAL_READINESS_PROTOCOL.json','deployment_protocol_sha256':root/'governance/DEPLOYMENT_PROTOCOL.json'}.items():release[key]=s.digest(path)
    s.write_json(q/'EVALUATION_RELEASE.json',release)
    s.write_json(root/'SYNTHETIC_FIXTURE.json',{'purpose':'No training/test data; isolated fake metadata and initial weights for evaluator guard/output/relocation tests','original_root_intentionally_unavailable':ORIGINAL})
    return root


class EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.fixture=build_fixture()

    def patches(self):
        root=self.fixture;q=root/'quantum'
        values={'ROOT':q,'STUDY_ROOT':root,'REGISTRATION':q/'EVALUATION_REGISTRATION.json','LOCK':q/'CONFIRMATION_ENDPOINT_LOCK.json',
            'REVIEW':q/'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json','RELEASE':q/'EVALUATION_RELEASE.json','OUTPUT':q/'confirmation_evaluation',
            'PROTOCOL':root/'governance/ANALYSIS_PROTOCOL.json','READINESS_PROTOCOL':root/'governance/LOCAL_READINESS_PROTOCOL.json','DEPLOYMENT_PROTOCOL':root/'governance/DEPLOYMENT_PROTOCOL.json'}
        return patch.multiple(e,**values),patch.object(s,'ROOT',q),patch.multiple(e.stats,PROTOCOL_PATH=root/'governance/ANALYSIS_PROTOCOL.json',__file__=str(root/'analysis/statistics_v06.py'))

    def forbid_original_reads(self,original_open):
        def wrapped(file,*args,**kwargs):
            if isinstance(file,(str,bytes,Path)):
                path=Path(file.decode() if isinstance(file,bytes) else file).resolve()
                if path.is_relative_to(ACTUAL_ROOT.parent):raise AssertionError('Relocated verification opened original working tree: '+str(path))
            return original_open(file,*args,**kwargs)
        return wrapped

    def test_01_relocated_guard_and_mutations(self):
        with self.patches()[0],self.patches()[1],self.patches()[2]:
            reg,lock,release,watched=e.verify_guard();self.assertEqual(len(lock['endpoints']),120)
            self.assertTrue(all(path.is_relative_to(self.fixture) for path in watched))
            cases=[(e.RELEASE,'status','not_released'),(e.RELEASE,'independent_replay_ready_sha256','0'*64),
                   (e.REGISTRATION,'expected_output_paths',[]),(e.LOCK,'endpoint_count',119),
                   (e.REVIEW,'independent_audit_sha256','0'*64)]
            for path,key,value in cases:
                original=path.read_bytes();d=json.loads(original);d[key]=value;s.write_json(path,d)
                try:
                    with self.assertRaises(RuntimeError):e.verify_guard()
                finally:path.write_bytes(original)
            checkpoint=self.fixture/'quantum/stage_B/confirmation_checkerboard/seed_1201/qscalar_kmeans/selected_checkpoint.npz'
            original=checkpoint.read_bytes();checkpoint.write_bytes(original+b'corrupt')
            try:
                with self.assertRaises(RuntimeError):e.verify_guard()
            finally:checkpoint.write_bytes(original)

    def test_01a_semantically_invalid_independent_audit(self):
        with self.patches()[0],self.patches()[1],self.patches()[2]:
            path=self.fixture/'analysis/classical_review/SYNTHETIC_INDEPENDENT_AUDIT.json'
            originals={p:p.read_bytes() for p in (path,e.REVIEW,e.RELEASE)}
            mutations=[('engineering',True),('data_seal_sha256','0'*64),('validation_rounds_replayed',23999)]
            for key,value in mutations:
                audit=json.loads(originals[path]);audit[key]=value;s.write_json(path,audit)
                review=json.loads(originals[e.REVIEW]);review['independent_audit_sha256']=s.digest(path);s.write_json(e.REVIEW,review)
                release=json.loads(originals[e.RELEASE]);release['independent_endpoint_review_sha256']=s.digest(e.REVIEW);s.write_json(e.RELEASE,release)
                try:
                    with self.assertRaises(RuntimeError):e.verify_guard()
                finally:
                    for p,blob in originals.items():p.write_bytes(blob)

    def test_02_complete_synthetic_250_payload_commit(self):
        with self.patches()[0],self.patches()[1],self.patches()[2],patch('io.open',self.forbid_original_reads(io.open)),patch('builtins.open',self.forbid_original_reads(builtins.open)):
            reg,lock,release,watched=e.verify_guard();e.OUTPUT.mkdir()
            s.write_json(e.OUTPUT/'ACCESS_EVENT.json',{'synthetic':True,'no_actual_test_access':True},True)
            x=np.array([[-.7,-.2],[-.3,.4],[.1,-.5],[.6,.2],[-.4,-.6],[.8,.7]])
            pops={pop:{'x':x.copy(),'y':np.array([0,1,0,1,1,0]),'ids':np.arange(6)+10000*j,
                        'hash_route':np.array([0,1,2,3,4,0]),'kmeans_route':np.array([4,3,2,1,0,4])}
                    for j,pop in enumerate(s.POPULATIONS['B'])}
            for pop in pops.values():
                pop['clean_y']=pop['y'].copy();pop['label_flip']=np.zeros(6,dtype=bool)
            endpoints={(r['population'],r['seed'],r['method']):r for r in lock['endpoints']}
            summaries,reports=e.evaluate_payloads(pops,endpoints,e.OUTPUT)
            e.finish_commit(e.OUTPUT,release,reg,lock,watched,summaries,reports,0.)
            commit=s.read_json(e.OUTPUT/'EVALUATION_COMMIT.json')
            self.assertEqual(commit['payload_count'],250);self.assertEqual(len(reports),120)
            self.assertEqual(set(commit['files']),e.expected_output_paths())
            with self.assertRaises(RuntimeError):e.verify_guard()
            e.verify_guard(output_must_be_absent=False) # read-only copy verification after completion

    def test_03_numerical_band_and_extrema(self):
        pop={'y':np.array([0,1,0,1]),'ids':np.arange(4),'hash_route':np.zeros(4,int),'kmeans_route':np.zeros(4,int)}
        p=np.array([.5,np.nextafter(.5,0),.8,.2]);q=p.copy();q[0]=np.nextafter(.5,0);q[1]=.5
        d=v.verify_pair(pop,p,q);self.assertEqual(d['counts']['class_disagreements'],2)
        self.assertEqual(d['sensitivity']['label_assisted_all_correct']['accuracy'],.5)
        self.assertEqual(d['sensitivity']['label_assisted_all_incorrect']['accuracy'],0.)
        q[0]=.5-1e-13
        with self.assertRaises(RuntimeError):v.verify_pair(pop,p,q)

    def test_04_path_escape_rejected(self):
        p=remap_recorded(ORIGINAL+r'\quantum\example.json',ORIGINAL,self.fixture)
        self.assertEqual(p,self.fixture/'quantum/example.json')
        for bad in (r'C:\unrelated\file',ORIGINAL+r'\..\escape',r'..\relative'):
            with self.assertRaises(ValueError):remap_recorded(bad,ORIGINAL,self.fixture)

    def test_05_native_logits_and_saturated_canonical_losses(self):
        y=np.array([1,0,1,0]);z=np.array([-1000.,1000.,-20.,20.])
        native=float(np.mean(np.maximum(z,0)-y*z+np.log1p(np.exp(-abs(z)))))
        checked=v.verify_native(y,z,z.copy(),native)
        self.assertEqual(checked['maximum_logit_error'],0.)
        altered=z.copy();altered[0]+=1e-6
        with self.assertRaises(RuntimeError):v.verify_native(y,z,altered,native)
        with self.assertRaises(RuntimeError):v.verify_native(y,z,z,native+.01)
        with self.assertRaises(RuntimeError):v.verify_native(y,None,z,native)


if __name__=='__main__':unittest.main()
