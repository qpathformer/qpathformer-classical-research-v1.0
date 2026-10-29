"""Read historical aggregate evidence against the pinned sealed delivery manifest."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
OLD=Path(r'C:\Q2\Improvement_Study_v0.5')
MANIFEST='c0be8e4cc5126ae3027b3e8b55d869fb5a0e89b0dd64b609baea21cb23ce3e5e'
def sha(b):return hashlib.sha256(b).hexdigest()
def need(ok,message):
    if not ok:raise RuntimeError(message)
raw=(OLD/'DELIVERY_MANIFEST.json').read_bytes();need(sha(raw)==MANIFEST,'Historical manifest differs')
manifest=json.loads(raw);need(manifest['file_count']==30234 and manifest['total_size_bytes']==2812931271,'Historical inventory differs')
entries={r['relative_path']:r for r in manifest['files']};bindings={}
def bound(relative):
    path=OLD/relative;before=path.stat();data=path.read_bytes();after=path.stat()
    need(before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns,'Historical file changed during read')
    item=entries[relative];need(item['sha256']==sha(data) and item['size_bytes']==len(data),'Historical payload differs')
    bindings[relative]={'sha256':sha(data),'bytes':len(data)}
    return json.loads(data)
commit=bound('quantum/confirmation_evaluation/EVALUATION_COMMIT.json')
summary=bound('quantum/confirmation_evaluation/summary.json')
need(commit['status']==summary['status']=='completed' and commit['report_count']==summary['report_count']==165,'Historical outcomes incomplete')
need(commit['files']['summary.json']['sha256']==bindings['quantum/confirmation_evaluation/summary.json']['sha256'],'Historical evaluation commit mismatch')
need(summary['study_id']=='QPATH-READOUT-v0.5' and summary['training_seeds']==list(range(1001,1006)),'Historical identity mismatch')
methods=['qscalar_kmeans','qmulti_kmeans','mlp8tanh_kmeans','trig_kmeans','trig_global','mlp_global']
populations={p:{'methods':{m:summary['populations'][p]['statistics']['aggregate'][m] for m in methods}} for p in summary['population_order']}
out={'status':'PASS_EXTRACTED_VERIFIED_SOURCES','created_utc':datetime.now(timezone.utc).isoformat(),'study_id':'QPATH-READOUT-v0.5',
     'historical_delivery_manifest_sha256':MANIFEST,'source_sha256':sha(Path(__file__).read_bytes()),'inputs':bindings,
     'population_order':summary['population_order'],'methods':methods,'populations':populations,
     'scope':'Read-only historical context from delivered v0.5; no current model execution. Different tasks and populations mean raw cross-version score subtraction is not a paired improvement estimate.'}
for relative,item in bindings.items():need(sha((OLD/relative).read_bytes())==item['sha256'],'Historical source changed')
with (ROOT/'analysis/v05_context.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2,allow_nan=False)
print('Historical v0.5 aggregate context extracted from verified payloads; v0.5 unchanged.')
