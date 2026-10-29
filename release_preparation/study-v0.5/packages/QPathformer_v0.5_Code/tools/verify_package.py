import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
files={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
m=json.loads((root/'MANIFEST.json').read_text('utf-8'))
expected={x['path']:x for x in m['files']}
assert set(expected)==set(files)-{'MANIFEST.json','CHECKSUMS.sha256'},'Manifest membership mismatch'
for n,e in expected.items():
 b=files[n].read_bytes();assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256'],n
cs={line[66:]:line[:64] for line in (root/'CHECKSUMS.sha256').read_text().splitlines()}
assert set(cs)==set(files)-{'CHECKSUMS.sha256'},'Checksum membership mismatch'
for n,h in cs.items():assert hashlib.sha256(files[n].read_bytes()).hexdigest()==h,n
print('PASS exact membership and all hashes')
