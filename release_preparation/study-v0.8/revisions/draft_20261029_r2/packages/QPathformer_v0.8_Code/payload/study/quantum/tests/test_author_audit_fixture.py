"""Author auditor integration against preserved NONSTUDY synthetic fits only."""
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import study
import audit_stage_v08 as auditor

class AuditFixtureTests(unittest.TestCase):
    def test_preserved_synthetic_endpoint_audit_and_corruption_rejection(self):
        parent=Path(__file__).resolve().parents[1]/'synthetic_fixtures'
        candidates=sorted(p for p in parent.glob('NOTSTUDY_contract_*') if (p/'uniform_control/endpoint_commit.json').is_file())
        self.assertTrue(candidates,'Run synthetic science fixtures before audit integration')
        source=candidates[-1]
        fresh=Path(tempfile.mkdtemp(prefix='NOTSTUDY_authoraudit_',dir=parent))
        q=fresh/'quantum';q.mkdir()
        shutil.copytree(source/'data',q/'data')
        for name in ('first','uniform_control'):shutil.copytree(source/name,q/name)
        for name in ('matrix.json','protocol.json'):shutil.copyfile(source/name,q/name)
        matrix=q/'matrix.json';protocol=q/'protocol.json'
        jobs=study.read_json(matrix)['runs'];population=jobs[0]['population_id']
        # Original fixture deliberately ends by injecting a forbidden field.
        # Restore only its clean public fields into a NEW copied fixture.
        train=q/'data'/f'{population}_train.npz'
        with np.load(train) as f:payload={key:f[key] for key in f.files if key!='clean_y'}
        np.savez(train,**payload)
        seal=study.read_json(q/'data/DATA_SEAL.json')
        seal['files'][train.name]['sha256']=study.digest(train)
        (q/'data/DATA_SEAL.json').write_text(json.dumps(seal))
        sources={'synthetic_fixture_only':'0'*64}
        auth=q/'synthetic_authorization.json'
        authority={'schema':'qpath-v08-stage-authorization-1','review_status':'approved_by_root','stage':'engineering',
                   'run_ids':[j['run_id'] for j in jobs],'scientific_source_hashes':sources,'settings':study.SETTINGS,
                   'data_seal_sha256':study.digest(q/'data/DATA_SEAL.json'),
                   'matrix_sha256':study.digest(matrix),'protocol_sha256':study.digest(protocol),
                   'classification':'SYNTHETIC_UNIT_TEST_ONLY_NOT_ROOT_STUDY_APPROVAL'}
        auth.write_text(json.dumps(authority))
        manifest=fresh/'synthetic_manifest.json'
        # OFFICIAL_STUDY is the schema branch under test; the fixture is not registered.
        manifest.write_text(json.dumps({'stage':'engineering','mode':'OFFICIAL_STUDY','study_root':str(fresh),
                         'jobs':jobs,'authorization':{'path':str(auth),'sha256':study.digest(auth)},
                         'classification':'NONSTUDY_AUTHOR_AUDIT_FIXTURE'}))
        state=fresh/'execution/state';state.mkdir(parents=True)
        db=sqlite3.connect(state/'ledger.sqlite3')
        db.executescript('CREATE TABLE jobs(job_id TEXT,recipe_sha TEXT,manifest_sha TEXT,phase TEXT,current_attempt TEXT);'
                        'CREATE TABLE attempts(attempt_id TEXT,endpoint TEXT,metadata_dir TEXT,status TEXT,commit_sha TEXT);')
        for index,(job,directory) in enumerate(zip(jobs,('first','uniform_control'))):
            endpoint=q/directory
            for name in ('config.json','result.json'):
                obj=study.read_json(endpoint/name)
                obj.update(data_seal_sha256=authority['data_seal_sha256'],authorization_sha256=study.digest(auth),
                           stage_freeze_sha256=study.digest(auth),matrix_sha256=study.digest(matrix),protocol_sha256=study.digest(protocol))
                (endpoint/name).write_text(json.dumps(obj))
            commit=study.read_json(endpoint/'endpoint_commit.json')
            commit.update(data_seal_sha256=authority['data_seal_sha256'],authorization_sha256=study.digest(auth),
                          matrix_sha256=study.digest(matrix),protocol_sha256=study.digest(protocol))
            commit['files']={p.name:{'sha256':study.digest(p),'bytes':p.stat().st_size}
                             for p in endpoint.iterdir() if p.is_file() and p.name!='endpoint_commit.json'}
            (endpoint/'endpoint_commit.json').write_text(json.dumps(commit))
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(job['run_id'],'fixture',study.digest(manifest),'engineering',str(index)))
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',(str(index),str(endpoint),str(fresh),'succeeded',study.digest(endpoint/'endpoint_commit.json')))
        db.commit();db.close()
        with mock.patch.object(study,'ROOT',q),mock.patch.object(study,'MATRIX_PATH',matrix), \
             mock.patch.object(study,'PROTOCOL_PATH',protocol),mock.patch.object(study,'source_hashes',return_value=sources), \
             mock.patch.object(auditor,'ROOT',fresh),mock.patch.object(auditor,'STAGE_COUNTS',{'engineering':2}):
            out=fresh/'NONSTUDY_AUTHOR_AUDIT.json';auditor.audit(manifest,out)
            receipt=study.read_json(out)
            self.assertEqual(receipt['verified_endpoints'],2)
            self.assertEqual(receipt['selected_minibatch_gradients_recomputed'],48)
            (q/'first/result.json').write_text('{"deliberately_corrupted_synthetic_metadata":true}')
            with self.assertRaisesRegex(RuntimeError,'Changed endpointpayload'):
                auditor.audit(manifest,fresh/'REJECTED_AUDIT.json')
        print('Preserved NONSTUDY fixture:',fresh)

if __name__=='__main__':unittest.main(verbosity=2)
