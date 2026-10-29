"""Register final evaluation/readiness software before confirmation test access.

This creates metadata only. It is not root stage approval or test release.
"""
import argparse
from pathlib import Path
import study as s
import evaluate_confirmation as e


def register():
    target=s.ROOT/'EVALUATION_REGISTRATION.json'
    if target.exists():raise FileExistsError('Preserve the prior registration; any amendment requires explicit review')
    s.require(not e.RELEASE.exists() and not e.OUTPUT.exists(),'Registration must precede test release/access')
    plan=s.read_json(s.ROOT.parent/'governance/STUDY_PLAN.json')
    s.require(plan['study_id']=='QPATH-GENERALIZATION-v0.6' and plan['methods']==list(s.METHODS),'Study specification mismatch')
    source=s.source_hashes()
    freeze=s.ROOT/'STAGE_A_FREEZE.json'
    if freeze.exists():s.require(s.read_json(freeze)['source_hashes']==source,'Frozen training sources changed')
    names=['quantum/'+name for name in ('evaluate_confirmation.py','verification.py','path_mapping.py','local_readiness.py',
              'audit_stage.py','register_evaluation.py','evaluation_checks/test_evaluation_v06.py',
              'snapshot_execution.py','device_snapshot.py','deployment_compiler.py','deployment_benchmark.py',
              'deployment_checks/test_compiler.py','deployment_checks/test_benchmark.py','deployment_checks/test_integrity.py',
              'readiness_checks/synthetic_capsule.py','device_snapshot/SNAPSHOT_MANIFEST.json')]
    names+=['analysis/statistics_v06.py','governance/ANALYSIS_PROTOCOL.json','governance/LOCAL_READINESS_PROTOCOL.json','governance/DEPLOYMENT_PROTOCOL.json',
            'governance/STUDY_PLAN.json','governance/DEPLOYMENT_IMPLEMENTATION_NOTES.json','governance/simulator_requirements_lock.txt',
            'analysis/classical_review/audit_endpoints_v06.py','analysis/classical_review/reference_v06.py',
            'analysis/classical_review/laurent_reference_v06.py']
    snapshot=s.read_json(s.ROOT/'device_snapshot/SNAPSHOT_MANIFEST.json')
    for name,meta in snapshot['files'].items():
        s.require(Path(name).name==name,'Unsafe snapshot filename')
        relative='quantum/device_snapshot/'+name;path=s.ROOT.parent/relative
        s.require(s.digest(path)==meta['sha256'] and path.stat().st_size==meta['size_bytes'],'Snapshot payload changed')
        names.append(relative)
    hashes={name:s.digest(s.ROOT.parent/name) for name in names}
    result={'status':'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS','study_id':'QPATH-GENERALIZATION-v0.6','created_utc':s.now(),
      'original_working_root':plan['working_root'],'methods':list(s.METHODS),'training_seeds':list(s.SEEDS['B']),
      'populations':list(s.POPULATIONS['B']),'training_source_hashes':source,'source_hashes':hashes,
      'data_seal_sha256':s.digest(s.ROOT/'data/DATA_SEAL.json'),
      'analysis_protocol_sha256':hashes['governance/ANALYSIS_PROTOCOL.json'],
      'readiness_protocol_sha256':hashes['governance/LOCAL_READINESS_PROTOCOL.json'],
      'deployment_protocol_sha256':hashes['governance/DEPLOYMENT_PROTOCOL.json'],
      'independent_auditor_path':'analysis/classical_review/audit_endpoints_v06.py',
      'expected_output_paths':sorted(e.expected_output_paths()),'expected_payload_count':len(e.expected_output_paths()),
      'root_release_required':True,'independent_replay_ready_required':True,
      'scope':'All120 selected confirmation endpoints once, root statistics helper, separate registered validation-only local simulator/noise capsule, and same-checkpoint conversion/isolated inference benchmark with equal-kernel Trig controls. No training changes or test reselection.',
      'relocation':'Validate recorded absolute provenance against original_working_root, then remap under current study root. Never open recorded original paths or rewrite sealed metadata.'}
    s.write_json(target,result,True);print(s.digest(target))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--register',action='store_true',required=True)
    parser.parse_args();register()

