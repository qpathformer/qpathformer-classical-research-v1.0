"""Verify exact extracted-package membership, sizes and SHA-256 checksums."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    actual={p.relative_to(ROOT).as_posix():p for p in ROOT.rglob('*') if p.is_file()}
    m=json.loads((ROOT/'MANIFEST.json').read_text('utf-8'));expected={e['path']:e for e in m['files']}
    if set(expected)!=set(actual)-{'MANIFEST.json','CHECKSUMS.sha256'}:raise ValueError('Manifest membership differs')
    for n,e in expected.items():
        if actual[n].stat().st_size!=e['bytes'] or digest(actual[n])!=e['sha256']:raise ValueError('Manifest differs: '+n)
    checks={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (ROOT/'CHECKSUMS.sha256').read_text('utf-8').splitlines()}
    if set(checks)!=set(actual)-{'CHECKSUMS.sha256'}:raise ValueError('Checksum membership differs')
    for n,h in checks.items():
        if digest(actual[n])!=h:raise ValueError('Checksum differs: '+n)
    print(json.dumps({'status':'PASS','files':len(actual)}))
if __name__=='__main__':main()
