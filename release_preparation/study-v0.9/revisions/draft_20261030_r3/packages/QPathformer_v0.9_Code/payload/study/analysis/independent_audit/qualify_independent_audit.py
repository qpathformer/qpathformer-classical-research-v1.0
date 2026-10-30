"""Qualify independent implementation using only disposable fixture outcomes."""
import json,time,unittest
from datetime import datetime,timezone
from pathlib import Path
import audit_endpoints_v09 as a
import test_reference_v09
import test_endpoints_v09 as e

def run():
    names=('reference_v09.py','audit_endpoints_v09.py','test_reference_v09.py','test_endpoints_v09.py','qualify_independent_audit.py')
    sources={n:a.binding(a.HERE/n) for n in names};suite=unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_reference_v09))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(e));start=time.perf_counter()
    with (e.SESSION/'qualification.log').open('x',encoding='utf-8') as f:result=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    evidence={'status':'PASS' if result.wasSuccessful() else 'FAIL','utc':datetime.now(timezone.utc).isoformat(),
      'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
      'wall_seconds':time.perf_counter()-start,'source_bindings':sources,'endpoint_reports':e.REPORTS,
      'fixture_source':str(e.SOURCE),'official_training_or_audits':False,
      'test_log':a.binding(e.SESSION/'qualification.log'),
      'failure_details':[{'test':str(t),'traceback':s} for t,s in result.failures+result.errors]}
    a.write_new(e.SESSION/'QUALIFICATION.json',evidence)
    a.need(result.wasSuccessful() and not result.skipped,'Independent qualification failed; evidence retained')
    contract={'schema':'qpath-v09-independent-audit-contract-1','status':'QUALIFIED_PENDING_ROOT_APPROVAL',
      'utc':datetime.now(timezone.utc).isoformat(),'tolerances':a.TOLERANCES,'stage_counts':a.COUNTS,
      'source_bindings':sources,'qualification':a.binding(e.SESSION/'QUALIFICATION.json'),
      'numerical_scope':'Absolute tolerances for numerical implementation replay only; not scientific effect thresholds. No tolerances permit file/recipe/count/stream mismatch.',
      'independence':'No imports of producer Model, trainer, production routers or author audit. Full4x4 tensor circuit oracle combines adjacent RY gates; scalar separate-gate cross-check. Independently derived stable mixture gradients and metrics.',
      'gradient_probes':'Minibatch1 and75 of every round, allparameters; every savedgradient is used by independentAdam replay. This is bounded verification, not a complete independent gradient retraining.',
      'warmup':'Exact paired expert initial vectors plus all750 saved expert gradients and10roundendvectors; independentAdam replay ensures all750steps same. L/R extra coefficients remain exactly0through750.',
      'selection':'Recompute common clippedBCE from each saved probability vector, independently verify those probabilities against reference; earlieststrictminimum. Never reselect using independent rounding.',
      'threshold_disagreements':'Class differences permitted only when BOTH probabilities lie within32float64eps of0.5; report all. Outside this band fail.',
      'data_scope':'Open sealed train+validation arrays and routerJSON only; never test modeloutcomes. Banknote samplecounts dynamicseal values;75batchesof64 perround independentofN.',
      'official_gate':'Complete48/72/636stage plus authorPASS receipt; root action independent_endpoint_audit binding manifest,author_audit,independent_contract. Auxiliaryauditexclusivelease.',
      'pre_freeze_findings':[{'finding':'Initial metric-edge qualification found .3 differs from np.linspace bin edge 0.30000000000000004.',
         'resolution':'Reference uses independently implemented interval masks with registered np.linspaceedges. Producer restored inherited searchsorted side=right edges before finalfixtures. No officialfit affected.'}]}
    a.write_new(a.HERE/'INDEPENDENT_AUDIT_CONTRACT.json',contract)
    print(json.dumps({'status':'PASS','tests':result.testsRun,'contract':a.binding(a.HERE/'INDEPENDENT_AUDIT_CONTRACT.json')},indent=2))
if __name__=='__main__':run()
