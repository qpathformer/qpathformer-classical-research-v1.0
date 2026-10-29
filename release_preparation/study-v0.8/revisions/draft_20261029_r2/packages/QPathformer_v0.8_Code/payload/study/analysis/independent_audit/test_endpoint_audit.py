"""Full independent endpoint audit using copied NONSTUDY producer fixtures."""
from pathlib import Path
import json,shutil,tempfile,unittest
from unittest import mock
import numpy as np
import audit_endpoints_v08 as audit

REAL_ROOT=Path(__file__).resolve().parents[2]
class EndpointAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates=sorted(p for p in (REAL_ROOT/'quantum/synthetic_fixtures').glob('NOTSTUDY_contract_*')
            if (p/'uniform_control/endpoint_commit.json').is_file())
        if not candidates:raise RuntimeError('Preserved explicitly synthetic producer fixture required')
        source=candidates[-1]
        parent=Path(__file__).resolve().parent/'synthetic_fixture_work';parent.mkdir(exist_ok=True)
        cls.root=Path(tempfile.mkdtemp(prefix='NOTSTUDY_independent_endpoint_',dir=parent))
        cls.q=cls.root/'quantum';cls.q.mkdir();gov=cls.root/'governance';gov.mkdir()
        shutil.copytree(source/'data',cls.q/'data')
        shutil.copyfile(source/'matrix.json',gov/'RUN_MATRIX.json')
        shutil.copyfile(source/'protocol.json',gov/'STUDY_PLAN.json')
        cls.jobs=audit.read(gov/'RUN_MATRIX.json')['runs']
        cls.by_arm={j['arm']:j for j in cls.jobs}
        pop=cls.jobs[0]['population_id'];train=cls.q/'data'/f'{pop}_train.npz'
        with np.load(train,allow_pickle=False) as z:
            clean={k:z[k] for k in ('x','y','ids','source_draw_ids','hash_route','kmeans_route','margin_bin')}
        with train.open('wb') as f:np.savez(f,**clean)
        seal=audit.read(cls.q/'data/DATA_SEAL.json');seal['files'][train.name]['sha256']=audit.sha(train)
        (cls.q/'data/DATA_SEAL.json').write_text(json.dumps(seal))
        cls.seal=seal
        marker=cls.q/'synthetic_fixture_only';marker.write_text('INERT INDEPENDENT ENDPOINT AUDIT FIXTURE; NOT STUDY SOURCE')
        source_hashes={marker.name:audit.sha(marker)}
        cls.auth=gov/'SYNTHETIC_AUTHORIZATION.json'
        sample_config=audit.read(source/'first/config.json')
        authority={'schema':'qpath-v08-stage-authorization-1','review_status':'approved_by_root','stage':'engineering',
            'run_ids':[j['run_id'] for j in cls.jobs],'scientific_source_hashes':source_hashes,'settings':sample_config['settings'],
            'data_seal_sha256':audit.sha(cls.q/'data/DATA_SEAL.json'),'matrix_sha256':audit.sha(gov/'RUN_MATRIX.json'),
            'protocol_sha256':audit.sha(gov/'STUDY_PLAN.json'),'classification':'NONSTUDY_FIXTURE_ONLY_NOT_OFFICIAL_AUTHORITY'}
        cls.auth.write_text(json.dumps(authority))
        for name in ('first','uniform_control'):
            endpoint=cls.q/name;shutil.copytree(source/name,endpoint)
            for filename in ('config.json','result.json','endpoint_commit.json'):
                obj=audit.read(endpoint/filename)
                obj.update(data_seal_sha256=authority['data_seal_sha256'],authorization_sha256=audit.sha(cls.auth),
                    stage_freeze_sha256=audit.sha(cls.auth),matrix_sha256=authority['matrix_sha256'],
                    protocol_sha256=authority['protocol_sha256'])
                if 'source_hashes' in obj:obj['source_hashes']=source_hashes
                if filename=='endpoint_commit.json':
                    obj['files']={p.name:{'sha256':audit.sha(p),'bytes':p.stat().st_size}
                        for p in endpoint.iterdir() if p.is_file() and p.name!='endpoint_commit.json'}
                (endpoint/filename).write_text(json.dumps(obj))
    def invoke(self,name):
        folder=self.q/name
        with mock.patch.object(audit,'ROOT',self.root),mock.patch.object(audit,'Q',self.q):
            return audit.audit_endpoint(folder,self.by_arm[audit.read(folder/'config.json')['arm']],self.seal,self.auth)
    def test_full_priority_and_uniform_endpoint_contract(self):
        for name in ('first','uniform_control'):
            result=self.invoke(name)
            self.assertEqual(result['rounds_verified'],12)
            self.assertEqual(result['sampling_and_optimizer_replay']['all_adam_updates_replayed'],900)
    def test_commit_payload_hash_rejection(self):
        # No payload is changed: substitute a bad digest for exactly one fixture path.
        original=audit.sha;target=self.q/'first/sampling_weights.npy'
        def altered(path):return 'f'*64 if Path(path)==target else original(path)
        with mock.patch.object(audit,'sha',side_effect=altered):
            with self.assertRaisesRegex(RuntimeError,'Committed payload changed'):
                self.invoke('first')

if __name__=='__main__':unittest.main(verbosity=2)
