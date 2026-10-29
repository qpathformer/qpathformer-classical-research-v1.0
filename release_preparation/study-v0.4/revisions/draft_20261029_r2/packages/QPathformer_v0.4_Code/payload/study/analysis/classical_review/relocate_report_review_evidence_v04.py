"""Preserve prior report-content bytes in the deliverable evidence directory."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,msg):
    if not v:raise RuntimeError(msg)


def main():
    canonical=HERE/'FINAL_REPORT_CONTENT_SCIENTIFIC_REVIEW.json'
    archive=HERE/'FINAL_REPORT_CONTENT_SCIENTIFIC_REVIEW_ITERATION03.json'
    old_relative='report_work/qa_iteration_report_02/report_content.json'
    new_relative='analysis/classical_review/REPORT_CONTENT_ITERATION02.json'
    source=ROOT/old_relative; destination=ROOT/new_relative
    prior_sha='ad2b747ad99ba0412e917580c6ac8f62fddf298663b008feb85027f8452a0dbe'
    need(sha(canonical)==prior_sha and not archive.exists() and not destination.exists(),'Prior identity or exclusive destination differs')
    prior=json.loads(canonical.read_text(encoding='utf-8'))
    expected=prior['evidence_sha256'][old_relative]
    need(sha(source)==expected,'Historical content source differs')
    for name,h in prior['evidence_sha256'].items():need(sha(ROOT/name)==h,'Review evidence changed: '+name)
    with destination.open('xb') as f:f.write(source.read_bytes())
    need(sha(destination)==sha(source)==expected,'Copied historical content differs')
    result=dict(prior); result['evidence_sha256']=dict(prior['evidence_sha256'])
    del result['evidence_sha256'][old_relative]
    result['evidence_sha256'][new_relative]=expected
    result['evidence_sha256'][archive.relative_to(ROOT).as_posix()]=prior_sha
    result['created_utc']=datetime.now(timezone.utc).isoformat()
    result['evidence_path_relocation']={'status':'PASS','reason':'QA iteration directories are excluded from final delivery; preserve the exact already-reviewed content bytes in the delivered review-evidence directory.',
      'historical_path':old_relative,'delivered_path':new_relative,'sha256':expected,
      'scientific_content_changed':False,'reviewed_final_content_sha256_unchanged':prior['reviewed_content_sha256'],
      'previous_review_sha256':prior_sha,'relocation_script_sha256':sha(__file__)}
    need(canonical.parent.resolve()==HERE and archive.parent.resolve()==HERE,'Review archive outside owned directory')
    canonical.rename(archive)
    need(sha(archive)==prior_sha,'Archived review differs')
    with canonical.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':'PASS','review_sha256':sha(canonical),'preserved_review_sha256':sha(archive),'relocated_content_sha256':sha(destination),'reviewed_content_sha256':result['reviewed_content_sha256']}))


if __name__=='__main__':main()
