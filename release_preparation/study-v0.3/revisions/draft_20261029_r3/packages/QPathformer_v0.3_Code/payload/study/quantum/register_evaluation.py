"""Create an absent pre-test evaluator/readiness registration, never a release."""
import json
from pathlib import Path
import qstudy as s
import evaluate_confirmation as e
import numerical_verification as numerical


def main():
    if e.REGISTRATION.exists():raise FileExistsError('Registration already exists; preserve it and review changes explicitly')
    if e.RELEASE.exists() or e.OUTPUT.exists():raise RuntimeError('Cannot register after release/evaluation')
    numerical.verify_protocol()
    files=['audit_stage.py','replay.py','evaluate_confirmation.py','evaluation_stats.py','numerical_verification.py','ibm_local_v03.py','local_readiness.py',
           'READINESS_PROTOCOL.json','RESOURCE_ACCOUNTING_ADDENDUM.json','register_evaluation.py','evaluation_checks/test_evaluation.py']
    value={'status':'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS','study_id':'QPATH-QMECH-v0.3','created_utc':s.now(),
           'verification_revision':'recovery01; verification/diagnostics only, approved after development and before confirmation',
           'supersedes_registration_sha256':'dffec12bc3d866836791edc0b605ae3820121c7408009755f75ea68487a33192',
           'numerical_recovery_protocol_sha256':numerical.PROTOCOL_SHA,
           'analysis_protocol_sha256':e.PROTOCOL_SHA,'data_seal_sha256':s.digest(s.ROOT/'data/DATA_SEAL.json'),
           'stage_A_freeze_sha256':s.digest(s.ROOT/'STAGE_A_FREEZE.json'),'training_source_hashes':s.source_hashes(),
           'source_hashes':{name:s.digest(s.ROOT/name) for name in files},
           'external_source_hashes':{'analysis/classical_review/audit_endpoints_v03.py':s.digest(s.ROOT.parent/'analysis/classical_review/audit_endpoints_v03.py')},
           'method_order':list(s.METHODS),'training_seeds':list(s.SEEDS['B']),'records':1600,'endpoint_count':65,
           'threshold':.5,'bce_clip':[1e-7,1-1e-7],'numpy_for_exact_binomial_replay':'2.5.4',
           'release_schema':{'path':'EVALUATION_RELEASE.json','status':'released_by_root','study_id':'QPATH-QMECH-v0.3',
                 'scope':'all_65_registered_confirmation_endpoints_once','required_hashes':['registration_sha256','endpoint_lock_sha256','independent_endpoint_review_sha256','stage_freeze_sha256','data_seal_sha256','analysis_protocol_sha256','numerical_recovery_protocol_sha256'],
                 'additional_fields':['release_id','created_utc']},
           'independent_review_schema':{'path':'CONFIRMATION_ENDPOINT_INDEPENDENT_REVIEW.json','status':'PASS','stage':'B','endpoint_count':65,
                 'required_fields':['endpoint_lock_sha256','independent_audit_path','independent_audit_sha256'],
                 'audit_scope':'Actual independent audit must be PASS/B/65, bind current lock, and bind registered auditor source.'},
           'readout':{'methods':list(e.READOUT_METHODS),'budgets':list(e.BUDGETS),'shot_seeds':list(e.SHOT_SEEDS),
                 'rng':'NumPy2.5.4 Generator(PCG64(SeedSequence([training_seed, shot_seed, budget, method_order.index(method)])))',
                 'array_key':'{method}_seed{training_seed}_shots{budget}_measurement{shot_seed}',
                 'count_array_count':150,'dtype':'int64','array_shape':[1600],'record_order':'Original confirmation NPZ row order, identical to saved prediction CSVs',
                 'nesting':'Five measurement seeds within each of five training checkpoints. Separate budget draws, not shared-shot prefixes; training replication n=5.'},
           'prediction_columns':['record_id','original_depth','hash_route','kmeans_route','label','probability','prediction'],
           'bootstrap_array_schema':{'file':'bootstrap_arrays.npz','key':'metric_means','shape':[2000,13,3],
                 'axis_order':['replicate','registered method','metric'],'metrics':['bce','macro_f1','accuracy'],
                 'rng':'Generator(PCG64(98003)); integers(0,1600,1600) once per replicate, shared across methods/seeds'},
           'output_root':'confirmation_evaluation','expected_output_paths':sorted(e.expected_output_paths()),
           'completion_commit':'EVALUATION_COMMIT.json is created exclusively after all135 payloads. It binds relative path, SHA256 and bytes for every payload, 65 reports, 65 prediction files and150 integer count arrays. No success commit after failure.',
           'readiness_protocol_sha256':s.digest(s.ROOT/'READINESS_PROTOCOL.json'),
           'preflight_evidence':{n:s.digest(s.ROOT/n) for n in ('evaluation_recovery_preflight_v01.log','evaluation_recovery_preflight_optimized_v01.log','readiness_engineering_v02/report.json')},
           'limitations':'Registration is not root release or final study completion. No test loading until all65 endpoints, both validation audits, current metadata/source hashes and root release pass. No training, tuning, silent overwrite or recovery occurs in the evaluator.'}
    if s.digest(e.PROTOCOL)!=e.PROTOCOL_SHA:raise RuntimeError('Analysis protocol changed')
    e.write_new(e.REGISTRATION,value)
    print(json.dumps({'path':str(e.REGISTRATION),'sha256':s.digest(e.REGISTRATION),'source_files':len(files),'test_accessed':False}))


if __name__=='__main__':main()
