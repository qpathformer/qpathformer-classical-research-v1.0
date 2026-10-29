"""Small reviewer fixtures; no official outcomes, training, or full history replay."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[key] = '1'
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from unittest.mock import patch
import numpy as np
from scipy.stats import t
import statistics_v09 as candidate
import replay_analysis_v09 as replay

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / 'governance/INDEPENDENT_ANALYSIS_SOURCE_REVIEW_v01.json'
def binding(path):
    value = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve()), sha256=hashlib.sha256(value).hexdigest(), bytes=len(value))
def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

contract_path = HERE / 'INDEPENDENT_ANALYSIS_CONTRACT.json'
contract = read(contract_path)
assert binding(contract_path)['sha256'] == '9a59ec60f722d4a3fd7032b6d6641145b2432a32d5a594494f674cdaa7169b40'
for record in contract['source_bindings'].values():
    assert binding(record['path']) == record
qualification_path = Path(contract['qualification']['path'])
assert binding(qualification_path) == contract['qualification']
qualification = read(qualification_path)
assert qualification['status'] == 'PASS' and qualification['tests_run'] == 7
assert binding(qualification['test_log']['path']) == qualification['test_log']

checks = []
def passed(name, detail):
    checks.append(dict(name=name, status='PASS', detail=detail))

# Hand-calculated tied-score classification and AP, without author functions.
y = np.array([1, 0, 1, 0])
p = np.array([.8, .8, .2, .2])
z = np.log(p/(1-p))
m = candidate.metrics(y, p, z)
assert m['confusion'] == [[1, 1], [1, 1]]
assert m['macro_f1'] == m['accuracy'] == m['average_precision'] == .5
assert abs(m['bce'] + .5*(math.log(.8)+math.log(.2))) < 1e-15
assert abs(m['brier']-.34) < 1e-15 and abs(m['ece10']-.3) < 1e-15
assert candidate.metrics(np.zeros(2), np.array([.1,.2]), np.array([-2.,-1.]))['average_precision'] is None
empty = candidate.metrics(np.array([]), np.array([]), np.array([]))
assert empty['n'] == 0 and empty['bce'] is None
passed('hand_calculated_metrics', 'Four tied scores: AP=.5, F1=.5, accuracy=.5, Brier=.34, ECE=.3; no-positive AP and empty-slice null behavior.')

# Deliberately large opposite seed effects: the inference unit must remain each
# population mean, rather than treating the sixteen seed effects independently.
rows = []
effects = np.arange(1,9)*.002
for i, effect in enumerate(effects):
    for seed, offset in ((1801,.05), (1802,-.05)):
        for arm, value in (('C_S', .4), ('C_L', .4+effect+offset)):
            rows.append(dict(family='constructed', population=f'p{i}', seed=seed, arm=arm, test={'bce':value}))
confidence = 1-.05/12
c = candidate.contrast(rows, 'constructed', 'C_L', 'C_S', confidence, True)
expected_mean = statistics.mean(effects)
expected_se = statistics.stdev(effects)/math.sqrt(8)
assert c['n_independent_populations'] == 8 and c['paired_seeds_per_population'] == 2 and c['df'] == 7
assert abs(c['mean_difference']-expected_mean) < 1e-15
assert abs(c['standard_error']-expected_se) < 1e-15
critical = float(t.ppf(1-.05/24,7))
np.testing.assert_allclose(c['interval'], [expected_mean-critical*expected_se, expected_mean+critical*expected_se], atol=1e-14, rtol=0)
try:
    candidate.contrast(rows[:-1], 'constructed', 'C_L', 'C_S', confidence, True)
    raise AssertionError('Missing paired seed accepted')
except RuntimeError:
    pass
passed('nested_seed_population_unit', 'Opposite +/-0.05 seed offsets cancel within eight populations; mean/SE/Bonferroni interval agree with direct arithmetic. Missing paired seed rejected.')

# Independent library reference across central and tail regions; candidate
# production implementation itself imports no SciPy.
values = np.r_[0., np.logspace(-12,4,97)]
prob_error = max(abs(candidate.two_sided_t7(float(v))-2*t.sf(v,7)) for v in values)
quantile_error = max(abs(candidate.critical_t7(cf)-t.ppf((1+cf)/2,7)) for cf in (.5,.8,.95,confidence,.9999))
assert prob_error < 2e-12 and quantile_error < 2e-10
assert candidate.two_sided_t7(0.) == 1
passed('custom_student_t7', {'probability_cases':len(values), 'maximum_probability_error':prob_error, 'maximum_quantile_error':quantile_error})

# Reuse only the inert authority builder; no statistical/numerical expected
# values come from the producer. Patch NPZ loading to prove no array is opened.
import test_analysis_v09 as fixture_factory
fixture = fixture_factory.AnalysisTests()
inert_root, authority_path, authority = fixture.gate_fixture()
with patch.object(replay.np, 'load', side_effect=AssertionError('Array access inside release gate')):
    verified = replay.verify_gate(inert_root, authority_path)
    assert len(verified['jobs']) == 636
    release = read(authority['evaluation_release']['path'])
    audit_path = Path(release['independent_audit']['path'])
    original_audit = audit_path.read_bytes()
    audit = json.loads(original_audit)
    audit['verified_endpoints'] = 635
    audit_path.write_text(json.dumps(audit))
    # Rebind the enclosing documents: the gate must reject incompleteness even
    # when ordinary hashes are internally consistent.
    release_path = Path(authority['evaluation_release']['path'])
    release['independent_audit'] = binding(audit_path)
    release_path.write_text(json.dumps(release))
    authority['evaluation_release'] = binding(release_path)
    authority_path.write_text(json.dumps(authority))
    try:
        replay.verify_gate(inert_root, authority_path)
        raise AssertionError('635-endpoint audit accepted')
    except RuntimeError as error:
        assert 'Audits incomplete' in str(error)
passed('636_gate_without_outcome_access', 'Inert 636-job authority passes without np.load; hash-consistent 635-endpoint independent audit fails before model outcome access. Fixtures are separate from official data.')

imports = {}
for name in replay.SOURCE_NAMES:
    tree = ast.parse((HERE/name).read_text(encoding='utf-8-sig'))
    found = sorted({node.module or '' for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} |
                   {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names})
    assert not any(module.split('.')[0] in ('models','study','evaluate_v09','metrics_v09','scipy') for module in found)
    imports[name] = found
passed('production_numerical_import_independence', imports)

receipt = {
    'schema':'qpath-v09-independent-analysis-source-review-1',
    'status':'PASS_SOURCE_AND_BOUNDED_SYNTHETIC_REVIEW',
    'reviewer':'/root/v09_science',
    'utc':datetime.now(timezone.utc).isoformat(),
    'contract':binding(contract_path),
    'author_qualification':binding(qualification_path),
    'source_bindings':contract['source_bindings'],
    'reviewer_source':binding(__file__),
    'reviewer_constructed_fixture_root':str(inert_root),
    'checks':checks,
    'source_review':[
        'Root independent release, root scoring release, complete 636 unique jobs, both PASS B audits, manifest/freeze/source/protocol bindings and matching selected checkpoints are checked before scored predictions or model arrays are loaded.',
        'Endpoint payload and scored-output inventories are rehashed. Consumed data/router/latent files, independent sources, author commit and all authorities are rechecked before success commit.',
        'All 636 selected models and all three splits use the separately qualified tensor/classical oracle. Saved probabilities/logits/weights/expert logits and aligned IDs/labels/routes/margin bins are compared before diagnostic/statistical reuse.',
        'Independent metrics cover raw/clipped/native probability loss, ties, calibration bins and both registered classes. Bank, class, margin, annulus latent and postfit learned argmax diagnostics match the frozen scope.',
        'Learned-gate historical exposure replays 15000 saved-gradient Adam steps with activation after 750 and compares every round state; it is not refitting. Full numerical fixture qualification was inspected, not redundantly rerun during the current endpoint audit.',
        'Twelve primary comparisons use eight population means after averaging paired seeds; independent incomplete-beta t7 probabilities and bisection quantiles reproduce separate SciPy checks. Banknote remains descriptive on one split.',
        'Exclusive-create outputs, preserved failure receipts and ETEL auxiliary audit lease prevent automatic retry and overlap with training or timing. Official output requires the registered root and numerical environment.'
    ],
    'limitations':[
        'This is source and constructed-fixture qualification; it does not accept any official confirmation scoring, replay, or test outcome.',
        'Metric replay deliberately uses author-saved probabilities only after independent numerical prediction parity. Class changes are allowed solely when both probabilities lie within 32 float64 epsilon of 0.5 and are counted; this is disclosed in the contract.',
        'The reviewer reused the inert authority fixture builder for contract-shaped documents; independent hand-calculated metrics and population-unit tests do not depend on producer numerical functions.',
        'The separate author resource inventory is hash-bound but is not numerically reconstructed by this command. Native process resource verification and final report accounting remain separate requirements.'
    ],
    'blocking_findings':[],
    'resolved_finding':{'record':binding(ROOT / 'governance/INDEPENDENT_ANALYSIS_REVIEW_FINDING_v01.json'), 'resolution':'Revision 2 uses direct central complementary beta below |t|=1; reviewer now checks97 logarithmic nonzero values from1e-12 through1e4. Prior contract and adverse author/reviewer receipts are preserved.'},
    'official_model_outcomes_accessed':False,
    'official_training_or_derived_phase_launched':False,
}
with OUTPUT.open('x', encoding='utf-8') as stream:
    json.dump(receipt, stream, indent=2, allow_nan=False)
print(json.dumps({'status':receipt['status'], 'checks':len(checks), 'output':binding(OUTPUT)}))
