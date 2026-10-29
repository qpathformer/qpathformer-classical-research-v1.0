"""Root-authorized one-time Stage A freeze after independent preflight review."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'quantum';G=ROOT/'governance';I=ROOT/'analysis/classical_review'
sys.path.insert(0,str(Q));import study
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(c,m):
 if not c:raise RuntimeError(m)
def write(p,v):
 with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n')
require(not (Q/'stage_A').exists(),'Stage A already exists; never duplicate')
package=read(Q/'ENGINEERING_REVIEW_PACKAGE.json');review=read(I/'INDEPENDENT_PREFLIGHT_REVIEW.json')
require(review['status']=='PASS_FOR_ROOT_STAGE_A_FREEZE_REVIEW','Independent preflight not PASS')
require(review['engineering_review_package_sha256']==sha(Q/'ENGINEERING_REVIEW_PACKAGE.json'),'Review package mismatch')
require(package['source_hashes']==review['training_source_sha256']==study.source_hashes(),'Training source mismatch')
require(package['data_seal_sha256']==review['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json'),'Data seal mismatch')
for name,h in review['governance_sha256'].items():require(sha(G/name)==h,'Protocol changed '+name)
for group in ['independent_evidence_sha256','independent_source_sha256']:
 for name,h in review[group].items():require(sha(I/name)==h,'Independent evidence/source changed '+name)
for name in review['independent_evidence_sha256']:require(read(I/name)['status']=='PASS','Independent evidence failed '+name)
require(read(I/'ENGINEERING_ENDPOINT_AUDIT_FINAL_BOUND.json')['endpoint_count']==18,'Wrong engineering audit count')
require(read(G/'RUNTIME.json')['packages']['numpy']=='2.5.4','Unregistered numerical runtime')
require(read(G/'baseline3_before.json')['status']=='PASS','Baseline3 before check notPASS')
notes={'scope':'Work counters, not comparable hardware FLOPs or execution speed.',
 'circuit':'Parameter-shift forwards, circuit record evaluations, layers, RY/RZ/CX gates and bank visits are counted; exact CPU statevector simulation.',
 'classical':'Forward/backward record examples, computed trigonometric feature values and MLP hidden activations. Gradient recomputation of features/activations is charged twice. No recorded MAC or FLOP counts.',
 'times':'Concurrent CPU times are measured process wall durations, not isolated dedicated device speed. Logical counts compare executed recipes; they are not hardware cost estimates.',
 'router':'Train-only fit and cached preparation retained; equal training bank occupancies, no equal heldout-occupancy assumption. Uncached routing + forward inference timing recorded separately.',
 'host_cpu':'AMD Ryzen AI 9 HX 370 w/ Radeon 890M;12physical cores24logical processors',
 'scope_exclusions':'No quantum hardware, GPU training, external jobs or network code; operating-system network isolation was not installed.'}
write(G/'RESOURCE_ACCOUNTING_NOTES.json',notes)
freeze={'study_id':'QPATH-ROUTING-v0.4','stage':'A','review_status':'approved_by_root','approved_utc':datetime.now(timezone.utc).isoformat(),
 'authorization':'User approved continuation of local v0.4 study; root completed independent preflight review.',
 'methods':list(study.METHODS),'populations':list(study.POPULATIONS['A']),'training_seeds':list(study.SEEDS['A']),
 'settings':study.SETTINGS,'source_hashes':study.source_hashes(),'data_seal_sha256':sha(Q/'data/DATA_SEAL.json'),
 'expected_endpoints':54,'protocol_hashes':review['governance_sha256'],
 'resource_notes_sha256':sha(G/'RESOURCE_ACCOUNTING_NOTES.json'),'runtime_sha256':sha(G/'RUNTIME.json'),
 'preflight_review_sha256':sha(I/'INDEPENDENT_PREFLIGHT_REVIEW.json'),'engineering_package_sha256':sha(Q/'ENGINEERING_REVIEW_PACKAGE.json'),
 'independent_audit_sources':review['independent_source_sha256'],
 'continuation':'All9 methods continue after54full endpoints independentlyaudited; separate rootBfreeze required. No test model outcomes until all135Bverified androotrelease.',
 'approved_training_source_changes':'None. Preserve failures; documentedreview required for recovery. Audit/evaluator/report tooling outside training source set may be implemented before respective output gates.'}
write(Q/'STAGE_A_FREEZE.json',freeze)
for p in study.POPULATIONS['A']:
 for s in study.SEEDS['A']:
  for m in study.METHODS:study.verify_freeze('A',p,s,m)
status=read(G/'CONTINUATION_STATUS.json');status.update(updated_utc=datetime.now(timezone.utc).isoformat(),phase='Stage A root frozen; launch authorized54runs; no stageB/test release',stage_a_freeze_sha256=sha(Q/'STAGE_A_FREEZE.json'))
(G/'CONTINUATION_STATUS.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
print('APPROVED54 StageA endpoints',sha(Q/'STAGE_A_FREEZE.json'))
