"""Persist synthetic independent analysis qualification; no official outcomes."""
import json,time,unittest
from datetime import datetime,timezone
import audit_endpoints_v09 as a
import replay_analysis_v09 as replay
import test_analysis_v09 as tests

def main():
    names=replay.SOURCE_NAMES+('test_analysis_v09.py','qualify_analysis_v09.py')
    sources={n:a.binding(a.HERE/n) for n in names};start=time.perf_counter();cpu=time.process_time()
    with (tests.TESTROOT/'qualification.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.AnalysisTests))
    receipt={'schema':'qpath-v09-independent-analysis-qualification-1','status':'PASS' if result.wasSuccessful() else 'FAIL',
      'utc':datetime.now(timezone.utc).isoformat(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
      'source_bindings':sources,'measurements':tests.MEASUREMENTS,'test_log':a.binding(tests.TESTROOT/'qualification.log'),
      'wall_seconds':time.perf_counter()-start,'process_cpu_seconds':time.process_time()-cpu,
      'official_model_outcomes_accessed':False,'official_training_performed':False,
      'failure_details':[{'test':str(t),'traceback':s} for t,s in result.failures+result.errors],
      'prior_failure':a.binding(a.HERE/'test_runs/INITIAL_ANALYSIS_QUALIFICATION_FAILURE.json')}
    a.write_new(tests.TESTROOT/'QUALIFICATION.json',receipt)
    print(json.dumps({'status':receipt['status'],'receipt':a.binding(tests.TESTROOT/'QUALIFICATION.json')},indent=2))
    a.need(result.wasSuccessful() and not result.skipped,'Independent analysis qualification failed; evidence retained')
    contract={'schema':'qpath-v09-independent-analysis-contract-1','revision':2,'status':'QUALIFIED_PENDING_ROOT_APPROVAL',
      'supersedes':a.binding(a.HERE/'INDEPENDENT_ANALYSIS_CONTRACT_v01.json'),
      'review_correction':{'finding':'Tail-only beta transform rounds to1 for t near0 and loses the central probability deficit.',
        'resolution':'Use the complementary beta integral for abs(t)<1; test t down to1e-12 against SciPy.',
        'retained_failure':a.binding(a.HERE/'test_runs/analysis_19969b8351124912be1eb54105852e37/QUALIFICATION.json')},
      'utc':datetime.now(timezone.utc).isoformat(),'source_bindings':{n:sources[n] for n in replay.SOURCE_NAMES},
      'qualification':a.binding(tests.TESTROOT/'QUALIFICATION.json'),
      'tolerances':{'probability_absolute':2e-12,'logit_absolute':1e-9,'gate_weight_absolute':2e-12,
        'expert_logit_absolute':1e-9,'ordinary_metric_absolute':2e-12,'native_metric_and_t_statistic_absolute':1e-8,
        'interval_quantile_pvalue_absolute':1e-10,'historical_adam_absolute':1e-8,'historical_gate_weighted_visits_absolute':1e-6,
        'threshold_band':a.TOLERANCES['threshold_band']},
      'independence':'No producer model, evaluator, metrics or statistics imports. Uses previously independently qualified tensor circuit and classical oracle. AP uses score histograms; t7 uses incomplete-beta continued fractions and quantile bisection, not SciPy.',
      'scope':'All636 B selected checkpoints and all3 splits; raw/clipped/native metrics, class/bank/boundary slices, latent annulus diagnostics, gate/expert diagnostics, 15000-update gate-only historical replay, milestones, endpoint costs, twelve primary population-level contrasts, secondary contrasts and descriptive Banknote.',
      'unit_of_inference':'Eight independent population means per synthetic family, with two paired seeds nested in each. Twelve Bonferroni primary BCE contrasts. Banknote five optimizer seeds on one fixed split are descriptive only.',
      'metric_scope':'Replay metrics from saved probabilities only after independent numerical prediction parity. Class disagreements allowed only if both probabilities are within32float64eps of.5; counted and retained. No test reselection.',
      'official_gate':'New root independent_prediction_statistics authorization bound to this contract, root evaluation release and committed official636-endpoint scoring; full endpoint and authority inventories rehashed before outcome access and before independent commit.',
      'execution':'Registered Python3.12.14 NumPy2.5.4 OpenBLAS1 runtime; auxiliary audit exclusive lease. No training or automatic retries.',
      'effect_threshold_note':'Numerical tolerances are implementation audit tolerances, not scientific evidence thresholds.'}
    a.write_new(a.HERE/'INDEPENDENT_ANALYSIS_CONTRACT.json',contract)
    print(json.dumps({'contract':a.binding(a.HERE/'INDEPENDENT_ANALYSIS_CONTRACT.json')},indent=2))

if __name__=='__main__':main()
