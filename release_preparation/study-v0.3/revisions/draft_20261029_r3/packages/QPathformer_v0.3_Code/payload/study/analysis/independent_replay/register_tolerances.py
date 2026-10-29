"""One-time pre-test registration, exclusive creation, no model/data loading."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE.parents[1] / 'governance/ANALYSIS_PROTOCOL.json'
EXPECTED_ANALYSIS_SHA = '7401f1ab9f805eed0a1cd97a86e1aab9be3c27746e0a529a991efdaf9e1766f5'
RECOVERY_SHA = '049f4a627fda5fa08c739cc53375aa104e28d223bb78d525841d0f01d7931e0e'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if __name__ == '__main__':
    if sha(PROTOCOL) != EXPECTED_ANALYSIS_SHA: raise ValueError('Analysis registration changed')
    recovery = HERE.parents[1] / 'governance/NUMERICAL_RECOVERY_PROTOCOL_01.json'
    if sha(recovery) != RECOVERY_SHA: raise ValueError('Recovery protocol changed')
    previous = HERE / 'TOLERANCE_PROTOCOL_PRE_RECOVERY_01.json'
    if sha(previous) != '96a2a5615db53967ed820d86bb0a0fbf26632205f24325d99cf9d67c7a577121': raise ValueError('Original tolerances not preserved')
    record = {
        'status': 'REGISTERED_BEFORE_CONFIRMATION_TEST_ACCESS',
        'registered_utc': datetime.now(timezone.utc).isoformat(),
        'authority': 'Root-approved numerical verification recovery01 after the development audit failure, before Stage B. Original registration is preserved; this is not the original pre-development rule.',
        'analysis_protocol_sha256': EXPECTED_ANALYSIS_SHA,
        'numerical_recovery_protocol_sha256': RECOVERY_SHA,
        'original_tolerance_protocol_sha256': sha(previous),
        'probability_maximum_absolute_error': 2e-12,
        'bce_maximum_absolute_error': 1e-9,
        'threshold_decisions': 'Every disagreement must have BOTH probabilities within inclusive32float64-epsilon of0.5; otherwise FAIL. Record all disagreements and exact_classifier_agreement honestly. Never alter saved probabilities or >=0.5 predictions.',
        'threshold_band_half_width': 7.105427357601002e-15,
        'sensitivity': 'Canonical saved-probability band only; retain all-class0/all-class1 and all-incorrect/all-correct label-assisted classification scenarios. No hypothetical BCE, no statistical-bound claim.',
        'record_identities_labels_depths_routes_confusion': 'Exact canonical agreement required. Raw independent class metrics are retained separately.',
        'readout_counts': 'Exact integer equality required under NumPy2.5.4 using hash-bound saved float probabilities after independent matrix verification.',
        'independence': 'Explicit tensor-product matrix and scalar MLP implementation; production replay imports no official model/circuit/oracle.',
        'preflight': 'Engineering validation only.26 cases,64 rows each; max probability error9.992007221626409e-16,0 threshold disagreements. All1600 engineering routes checked.',
        'final_adapter': 'Amended immutable readiness manifest will bind the revised adapter, official registration and peer-review evidence before Stage B.',
        'source_hashes_at_registration': {p.name: sha(p) for p in HERE.glob('*.py')},
        'engineering_preflight_sha256': sha(HERE / 'ENGINEERING_PREFLIGHT_v01.json'),
        'test_outcomes_accessed': False, 'confirmation_data_accessed': False,
    }
    with (HERE / 'TOLERANCE_PROTOCOL.json').open('x', encoding='utf-8') as f:
        json.dump(record, f, indent=2, allow_nan=False)
    print(sha(HERE / 'TOLERANCE_PROTOCOL.json'))
