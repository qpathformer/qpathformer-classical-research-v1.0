"""Read a retained historical IBM snapshot without accounts or remote access."""
from pathlib import Path
import hashlib,json

HERE=Path(__file__).resolve().parent/'device_snapshot'

def load_backend():
    from qiskit_ibm_runtime.fake_provider import FakeManilaV2
    manifest=json.loads((HERE/'SNAPSHOT_MANIFEST.json').read_text(encoding='utf-8'))
    for name,row in manifest['files'].items():
        if Path(name).name!=name:raise ValueError('Unsafe snapshot name')
        raw=(HERE/name).read_bytes()
        if len(raw)!=row['size_bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise RuntimeError('Archived snapshot changed: '+name)
    class ArchivedManila(FakeManilaV2):
        dirname=str(HERE)
    backend=ArchivedManila()
    if backend.num_qubits!=5:raise RuntimeError('Unexpected snapshot topology')
    return backend
