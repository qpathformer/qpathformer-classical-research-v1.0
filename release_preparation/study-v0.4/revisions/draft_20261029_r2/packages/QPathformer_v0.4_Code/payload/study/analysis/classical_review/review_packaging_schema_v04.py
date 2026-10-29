"""Narrow review of scalar scientific-content-hash compatibility corrections."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,msg):
    if not v:raise RuntimeError(msg)

def main():
    paths=['governance/finalize_report_package.py','governance/copy_final_package.py',
      'governance/packaging_recovery_01/finalize_report_package_before.py',
      'governance/packaging_recovery_01/copy_final_package_before.py',
      'governance/packaging_recovery_01/RECOVERY.txt',
      'analysis/classical_review/FINAL_REPORT_CONTENT_SCIENTIFIC_REVIEW.json',
      'analysis/classical_review/FINAL_REPORT_CONTENT_SCIENTIFIC_REVIEW_ITERATION03.json',
      'analysis/classical_review/REPORT_CONTENT_ITERATION02.json']
    for p in paths[:4]:ast.parse((ROOT/p).read_text(encoding='utf-8-sig'))
    review=json.loads((ROOT/paths[5]).read_text(encoding='utf-8'))
    need(isinstance(review['reviewed_content_sha256'],str) and review['reviewed_content_sha256']==sha(ROOT/'report_work/report_content.json'),'Canonical review content differs')
    need(review['status']=='PASS' and review['findings']==[],'Canonical review incomplete')
    for name,h in review['evidence_sha256'].items():
        path=(ROOT/name).resolve()
        need(path.is_relative_to(ROOT) and sha(path)==h,'Active evidence differs: '+name)
        need(not any(part.startswith('qa_iteration_') for part in Path(name).parts),'Active review still requires excluded QA evidence')
    result={'status':'PASS','findings':[],'created_utc':datetime.now(timezone.utc).isoformat(),
      'source_and_evidence_sha256':{p:sha(ROOT/p) for p in paths},
      'scope':'Narrow read-only review of the two exact source diffs against preserved pre-fix helpers; syntax and current review-evidence identity checks. Neither packaging helper was executed by this reviewer.',
      'checks':['Both corrections treat reviewed_content_sha256 as the actual scalar SHA256 and compare/watch the canonical report_content.json; evidence_sha256 remains a relative-path-to-hash map.',
      'The source diffs retain prior PASS/findings, safe evidence-path, final five-commit, visual QA and broader package integrity gates unchanged.',
      'The active scientific review retains the exact final content identity and all unchanged evidence. Its formerly excluded historical content reference now points to an exclusive byte-identical copy under analysis/classical_review.',
      'Previous canonical review and historical report-content bytes are preserved unchanged. Historical QA path remains explanatory metadata only, not an active evidence requirement.'],
      'scientific_content_changed':False,'training_or_result_sources_changed':False,'full_experiments_or_payload_replay_repeated':False,
      'limits':'Finalizer execution, destination copy, final manifest and two independent delivery verification passes remain root-owned later gates.'}
    output=HERE/'PACKAGING_SCHEMA_COMPATIBILITY_REVIEW.json'
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':'PASS','path':str(output),'sha256':sha(output),'scientific_review_sha256':sha(ROOT/paths[5])}))

if __name__=='__main__':main()
