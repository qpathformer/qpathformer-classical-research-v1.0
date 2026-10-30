"""Run four short, isolated synthetic qualification fits; no study data access.

Uses the production 20-round engineering loop with a tiny synthetic four-feature
population. These four fits are not registered scientific endpoints or results.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):os.environ[k]='1'
import hashlib,json,shutil,sqlite3,sys,time
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import study,routers

def main():
    science=Path(__file__).resolve().parents[1];root=science.parent
    target=science/'synthetic_fixtures'/('trainer_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
    q=target/'quantum';g=target/'governance';q.mkdir(parents=True);g.mkdir();(q/'tests').mkdir();(q/'data').mkdir()
    originals=(study.ROOT,study.GOVERNANCE,study.MATRIX_PATH,study.PROTOCOL_PATH)
    source_names=list(study.source_hashes())
    for name in source_names:shutil.copyfile(science/name,q/name)
    rng=np.random.default_rng(77829);raw=rng.normal(size=(80,4));labels=(raw[:,0]-.2*raw[:,1]+.1*raw[:,2]>0).astype(int)
    prep=routers.fit_preprocessing(raw[:60]);trainx=routers.preprocess(raw[:60],prep,2);policy=routers.fit_route_policy(trainx,9191);policy['preprocessing']=prep
    name='banknote_synthetic_fixture';policy_path=q/'data'/f'{name}_router.json';study.write_json(policy_path,policy,True)
    files={}
    for split,ids in [('train',np.arange(60)),('validation',np.arange(60,80))]:
        x=routers.preprocess(raw[ids],policy,2)
        payload={'x':x,'x4':routers.preprocess(raw[ids],policy,4),'raw_x':raw[ids],'source_row_indices':ids,'y':labels[ids],'ids':ids+10000,
                 'kmeans_route':routers.route(x,policy),'margin_bin':routers.margin_bins(x,policy)}
        path=q/'data'/f'{name}_{split}.npz';np.savez(path,**payload);files[path.name]={'sha256':study.digest(path),'n':len(ids)}
    seal={'files':files,'routers':{name:{'sha256':study.digest(policy_path)}},'datasets':{name:{'counts':{'train':60,'validation':20}}}}
    study.write_json(q/'data/DATA_SEAL.json',seal,True)
    streams={}
    for role in ('training_order','paired_circuit_core_initialization','mlp_initialization'):
        ns='QPATH-v09-trainer-fixture|'+role;streams[role]={'namespace':ns,'uint128_decimal':str(int.from_bytes(hashlib.sha256(ns.encode()).digest()[:16],'little'))}
    jobs=[{'run_id':'fixture_'+arm,'stage':'engineering','population_id':name,'training_seed_id':1700,'arm':arm,'rounds':20,'updates_per_round':75,'updates':1500,'batch_size':64,'paired_streams':streams} for arm in ('C_R','T_L','MLP4','LR2')]
    study.write_json(g/'RUN_MATRIX.json',{'runs':jobs,'populations':[{'population_id':name,'family':'synthetic_fixture'}]},True)
    study.write_json(g/'STUDY_PLAN.json',{'study_id':'SYNTHETIC_QUALIFICATION_NOT_OFFICIAL_V09'},True)
    study.ROOT=q;study.GOVERNANCE=g;study.MATRIX_PATH=g/'RUN_MATRIX.json';study.PROTOCOL_PATH=g/'STUDY_PLAN.json'
    freeze={'schema':'qpath-v09-stage-authorization-1','review_status':'approved_by_root','stage':'engineering','run_ids':[j['run_id'] for j in jobs],
            'settings':study.SETTINGS,'scientific_source_hashes':study.source_hashes(),'data_seal_sha256':study.digest(q/'data/DATA_SEAL.json'),
            'matrix_sha256':study.digest(study.MATRIX_PATH),'protocol_sha256':study.digest(study.PROTOCOL_PATH),'scope':'SYNTHETIC_FIXTURE_ONLY_NONOFFICIAL'}
    auth=g/'ENGINEERING_FIXTURE_AUTHORIZATION.json';study.write_json(auth,freeze,True)
    # Tampered recipes fail before any endpoint directory exists.
    bad=dict(freeze);bad['matrix_sha256']='0'*64;badpath=g/'TAMPERED_AUTHORIZATION.json';study.write_json(badpath,bad,True)
    rejected=False
    try:study.train(jobs[0]['run_id'],target/'should_not_exist',badpath)
    except RuntimeError:rejected=True
    assert rejected and not (target/'should_not_exist').exists()
    reports=[]
    try:
        for job in jobs:
            result=study.train(job['run_id'],target/'endpoints'/job['run_id'],auth)
            assert result['completed_rounds']==20 and result['optimizer_global_updates']==1500
            reports.append({'job_id':job['run_id'],'selected_round':result['selected_round'],'commit':str(target/'endpoints'/job['run_id']/'endpoint_commit.json'),'training_seconds':result['training_seconds']})
            print(json.dumps(reports[-1]),flush=True)
        # Exercise author audit on a fixture-only ledger, with explicit in-memory
        # root/count override; production stage counts remain48/72/636 unchanged.
        import audit_stage_v09 as author
        manifest_path=g/'FIXTURE_MANIFEST.json'
        manifest={'mode':'OFFICIAL_STUDY','study_root':str(target),'stage':'engineering','jobs':jobs,
                  'authorization':{'path':str(auth),'sha256':study.digest(auth)},'scope':'SYNTHETIC_FIXTURE_ONLY_NONOFFICIAL'}
        study.write_json(manifest_path,manifest,True);state=target/'execution/state';state.mkdir(parents=True)
        db=sqlite3.connect(state/'ledger.sqlite3')
        db.executescript('CREATE TABLE jobs(job_id TEXT,recipe_sha TEXT,manifest_sha TEXT,phase TEXT,current_attempt TEXT); CREATE TABLE attempts(attempt_id TEXT,endpoint TEXT,metadata_dir TEXT,status TEXT,commit_sha TEXT);')
        for job in jobs:
            identity=job['run_id'];endpoint=target/'endpoints'/identity
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(identity,'fixture',study.digest(manifest_path),'succeeded',identity))
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',(identity,str(endpoint),str(endpoint),'succeeded',study.digest(endpoint/'endpoint_commit.json')))
        db.commit();db.close()
        oldroot=author.ROOT;oldcounts=author.STAGE_COUNTS
        try:
            author.ROOT=target;author.STAGE_COUNTS={'engineering':4}
            audit_receipt=author.audit(manifest_path,target/'AUTHOR_AUDIT_FIXTURE.json')
            assert audit_receipt['verified_endpoints']==4
        finally:author.ROOT=oldroot;author.STAGE_COUNTS=oldcounts
        receipt={'status':'PASS_FOUR_ISOLATED_SYNTHETIC_TRAINER_FIXTURES','fixture_root':str(target),'official_data_used':False,'official_endpoints_created':False,
                 'tampered_authority_failed_before_output':True,'author_audit_all_four_endpoints':True,'full_engineering_loop_rounds':20,'full_engineering_loop_updates':1500,'endpoints':reports,
                 'source_hashes':study.source_hashes(),'utc':study.now()}
        study.write_json(target/'FIXTURE_RECEIPT.json',receipt,True)
        print(json.dumps({'status':receipt['status'],'receipt':str(target/'FIXTURE_RECEIPT.json')}),flush=True)
    finally:study.ROOT,study.GOVERNANCE,study.MATRIX_PATH,study.PROTOCOL_PATH=originals
if __name__=='__main__':main()
