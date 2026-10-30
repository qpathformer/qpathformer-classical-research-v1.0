"""Register immutable independent readiness after final registry and peer evidence.

Metadata-only. The expected registry digest is supplied explicitly by root;
peer review must bind that identical actual registration and every source.
No test population, outcome, checkpoint execution or release is performed.
"""
from datetime import datetime,timezone
import argparse,json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
from evidence_io import contained,digest,read_bound,recheck,require
from release_gate import training_hashes,expected_output_paths
from statistics_reference import validate_protocol
HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
STUDY_ID='QPATH-GENERALIZATION-v0.6'

def register(expected_registration_sha256):
    require(isinstance(expected_registration_sha256,str) and len(expected_registration_sha256)==64
            and all(c in '0123456789abcdef' for c in expected_registration_sha256),'Exact lowercase registry SHA256 required')
    ready=HERE/'ANALYSIS_READY.json'
    require(not ready.exists(),'Preserve prior READY; registration is exclusive')
    require(not (STUDY/'quantum/EVALUATION_RELEASE.json').exists()
            and not (STUDY/'quantum/confirmation_evaluation').exists(),'Must register before actual test release/access')
    watched={};registry_path=STUDY/'quantum/EVALUATION_REGISTRATION.json'
    registry=read_bound(registry_path,watched)
    require(watched[str(registry_path.resolve())]==expected_registration_sha256
            and registry['status']=='REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS'
            and registry['study_id']==STUDY_ID,'Unexpected final official registration')
    require(registry['expected_output_paths']==sorted(expected_output_paths())
            and registry['expected_payload_count']==250,'Official output contract differs')
    require(registry['training_source_hashes']==training_hashes(STUDY/'quantum'),'Training sources changed')
    for name,h in registry['source_hashes'].items():
        path=contained(STUDY,name);require(digest(path)==h,'Official source changed:'+name);watched[str(path.resolve())]=h
    protocol_path=STUDY/'governance/ANALYSIS_PROTOCOL.json';protocol=read_bound(protocol_path,watched);validate_protocol(protocol)
    require(registry['analysis_protocol_sha256']==digest(protocol_path),'Analysis protocol identity differs')
    paths=sorted(HERE.glob('*.py'))+[STUDY/'analysis/classical_review/reference_v06.py']
    sources={path.relative_to(STUDY).as_posix():digest(path) for path in paths}
    core_path=STUDY/'analysis/classical_review/STATISTICS_AND_NUMERICAL_CORE_REVIEW.json'
    review_path=STUDY/'analysis/classical_review/INDEPENDENT_REPLAY_ADAPTER_REVIEW.json'
    core=read_bound(core_path,watched);review=read_bound(review_path,watched)
    require(core['status']=='PASS' and core['study_id']==STUDY_ID and core['findings']==[],'Core peer review must pass')
    require(review['status']=='PASS' and review['study_id']==STUDY_ID and review['findings']==[],'Adapter peer review must pass')
    require(review['source_hashes']==sources and review['registration_sha256']==expected_registration_sha256,
            'Adapter review must bind every current source and actual registry')
    evidence={core_path.relative_to(STUDY).as_posix():digest(core_path),review_path.relative_to(STUDY).as_posix():digest(review_path)}
    for group in ('source_sha256','evidence_sha256'):
        for name,h in core[group].items():
            path=contained(STUDY,name);require(digest(path)==h,'Core review evidence changed:'+name)
            evidence[name]=h
    preflight_path=HERE/'RELOCATED_PREFLIGHT_RESULT.json';preflight=read_bound(preflight_path,watched)
    require(preflight['status']=='PASS' and preflight['synthetic_only'] is True
            and preflight['real_confirmation_outcomes_accessed'] is False and preflight['endpoint_count']==120
            and preflight['prediction_pairs_replayed']==192000 and preflight['population_count']==4
            and preflight['metadata_rewritten'] is False,'Complete relocated synthetic preflight required')
    require(preflight['current_source_hashes']=={p.name:sources[p.relative_to(STUDY).as_posix()] for p in HERE.glob('*.py')},
            'Relocated preflight does not bind current sources')
    oracle='analysis/classical_review/reference_v06.py'
    require(preflight['independent_oracle_sha256']==sources[oracle]
            and preflight['analysis_protocol_sha256']==digest(protocol_path),'Preflight oracle/protocol differs')
    require(digest(HERE/'RELOCATED_PREFLIGHT_CLI.log')==preflight['log_sha256'],'Relocated CLI evidence changed')
    evidence[preflight_path.relative_to(STUDY).as_posix()]=digest(preflight_path)
    for pattern in ('CORE*.log','PREDICTION*.log','ADAPTER_TESTS*.log','RELOCATED_PREFLIGHT_CLI.log'):
        matched=list(HERE.glob(pattern));require(bool(matched),'Required durable test evidence missing:'+pattern)
        for p in matched:evidence[p.relative_to(STUDY).as_posix()]=digest(p)
    for name,h in {**sources,**evidence}.items():watched[str(contained(STUDY,name).resolve())]=h
    recheck(watched)
    result={'status':'READY_BEFORE_CONFIRMATION_TEST_ACCESS','study_id':STUDY_ID,
            'created_utc':datetime.now(timezone.utc).isoformat(),'registration_sha256':expected_registration_sha256,
            'analysis_protocol_sha256':digest(protocol_path),'independent_oracle_path':oracle,
            'independent_oracle_sha256':sources[oracle],'source_hashes':sources,'evidence_hashes':evidence,
            'model_test_outcomes_accessed':False,
            'scope':'Only after root release and actual official completion: all120 selected checkpoints and192000 checkpoint-record probabilities; native logits/loss; canonical BCE/F1/accuracy/Brier/calibration and observed class quality/tie-aware AP; numerical32eps diagnostics; ten contrasts per population, paired-five-seed ordinary95%/primary family16 adjusted99.6875% intervals and10000 paired-record bootstrap replicates with exact count hashes. Supplemental annulus latent/noise-oracle metrics are generator context, never training or selection inputs.',
            'portability':'Validate recorded absolute provenance under registered original_working_root, remap to current package without metadata rewrite. Copied CLI preflight forbids every original-tree open.',
            'synthetic_scope':'Artificial metadata/checkpoints with scalar and vector independent oracles. Separate peer cross-comparison checked official statistics; implementation never imports official models/statistics.',
            'generated_fixture_policy':'synthetic_fixture_work is reproducible generated testing material retained in working tree; exclude from scientific delivery. Durable source/log/summary/review evidence is retained.'}
    with ready.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':result['status'],'path':str(ready),'sha256':digest(ready)}))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-registration-sha256',required=True)
    args=parser.parse_args();register(args.expected_registration_sha256)
if __name__=='__main__':main()
