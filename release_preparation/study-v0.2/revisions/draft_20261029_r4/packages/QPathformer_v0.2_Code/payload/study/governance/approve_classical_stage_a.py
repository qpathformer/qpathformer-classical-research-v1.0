from pathlib import Path
from datetime import datetime, timezone
import hashlib, json

root = Path(__file__).resolve().parents[1]
c = root/'classical'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
review_path = c/'readiness/INDEPENDENT_PROTOCOL_REVIEW.json'
assert sha(review_path) == '72ca4ae620296b93e0a060a9e5d9932b772977c49c2d81cf6ce4be69230e23d0'
review = json.loads(review_path.read_text())
assert review['status'] == 'PASS'
for name, expected in review['reviewed_file_sha256'].items():
    assert sha(c/name) == expected, name
ready = json.loads((c/'readiness/final_readiness.json').read_text())
for name, expected in ready['code_sha256'].items():
    assert sha(c/name) == expected, name
assert sha(c/'data/manifest.json') == review['data_manifest_sha256']
assert json.loads((c/'data_work/DATA_AUDIT.json').read_text())['status'] == 'PASS'
event = {'approved_utc': datetime.now(timezone.utc).isoformat(), 'review_status': 'approved_by_root',
         'scope': 'Freeze reviewed Stage A protocol and execute all 12 development endpoints with three paired common warmups. Keep all sealed test outcomes unread. Stage B requires frozen selection and endpoint checks.',
         'independent_review_sha256': sha(review_path), 'readiness_sha256': sha(c/'readiness/final_readiness.json'),
         'data_audit_sha256': sha(c/'data_work/DATA_AUDIT.json'),
         'root_analysis_protocol_sha256': sha(root/'governance/ANALYSIS_PROTOCOL.json'),
         'expected_code_sha256': ready['code_sha256'],
         'expected_data_manifest_sha256': review['data_manifest_sha256']}
out = root/'governance/CLASSICAL_STAGE_A_APPROVAL.json'
if out.exists(): raise FileExistsError(out)
out.write_text(json.dumps(event, indent=2)+'\n', encoding='utf-8')
print('Approved Stage A', sha(out))
