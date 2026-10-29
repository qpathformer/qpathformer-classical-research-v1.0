"""Read-only verification of an extracted curated release package."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((root/'MANIFEST.json').read_text('utf-8'))
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
expected={e['path'] for e in manifest['files']}
assert actual==expected|{'MANIFEST.json','CHECKSUMS.sha256'},'Exact membership mismatch'
for e in manifest['files']:
    p=root/e['path'];assert p.resolve().is_relative_to(root.resolve());assert not p.is_symlink()
    assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256'],e['path']
checks={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (root/'CHECKSUMS.sha256').read_text('utf-8').splitlines()}
assert set(checks)==actual-{'CHECKSUMS.sha256'}
for name,h in checks.items():assert sha(root/name)==h,name
print(json.dumps({'status':'PASS','files':len(actual),'root':str(root),'scope':'Exact inventory, manifest and checksums; integrity record, not digital signature'}))
