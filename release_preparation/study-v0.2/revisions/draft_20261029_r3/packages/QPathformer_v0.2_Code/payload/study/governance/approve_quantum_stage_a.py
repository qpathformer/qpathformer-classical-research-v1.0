from pathlib import Path
from datetime import datetime, timezone
import json, hashlib

root = Path(__file__).resolve().parents[1]
q = root / 'quantum'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
protocol = q / 'PROPOSED_PROTOCOL.json'
assert sha(protocol) == '6638b90e5cfe1c26b5faa7751659263c14c67ca5e314712798ca0d03c95b2ede'
freeze = json.loads(protocol.read_text())
for name, expected in freeze['source_hashes'].items():
    assert sha(q/name) == expected, name
assert sha(q/'data/DATA_SEAL.json') == freeze['data_seal_sha256']
assert json.loads((root/'governance/QUANTUM_DATA_AUDIT.json').read_text())['status'] == 'PASS'
freeze.update(review_status='approved_by_root', approved_utc=datetime.now(timezone.utc).isoformat(),
              independent_review='Root reviewed generation, model gradients, exposure accounting, complete-run selector, launcher, frozen protocol and preflight evidence. Independent reconstruction checked all 24000 records and hashes.',
              proposal_sha256=sha(protocol), data_audit_sha256=sha(root/'governance/QUANTUM_DATA_AUDIT.json'),
              next_action='Execute all 27 registered Stage A runs; never read sealed outcomes. Selection and Stage B freeze follow independent completion checks.')
out = q/'STAGE_A_FREEZE.json'
if out.exists(): raise FileExistsError(out)
out.write_text(json.dumps(freeze, indent=2)+'\n', encoding='utf-8')
print('Approved Stage A', sha(out))
