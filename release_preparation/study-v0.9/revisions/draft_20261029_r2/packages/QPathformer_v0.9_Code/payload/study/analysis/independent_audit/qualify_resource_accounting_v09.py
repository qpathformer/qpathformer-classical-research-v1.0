"""Save bounded synthetic resource checker qualification and source contract."""
import json,time,unittest
from datetime import datetime,timezone
import audit_endpoints_v09 as a
import resource_accounting_v09 as r
import test_resource_accounting_v09 as tests

def main():
    sources={n:a.binding(a.HERE/n) for n in r.SOURCE_NAMES+('test_resource_accounting_v09.py','qualify_resource_accounting_v09.py')}
    start=time.perf_counter();cpu=time.process_time()
    with (tests.SESSION/'qualification.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.ResourceTests))
    receipt={'schema':'qpath-v09-resource-qualification-1','status':'PASS' if result.wasSuccessful() else 'FAIL','utc':datetime.now(timezone.utc).isoformat(),
      'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'sources':sources,
      'test_log':a.binding(tests.SESSION/'qualification.log'),'failure_details':[{'test':str(t),'traceback':s} for t,s in result.failures+result.errors],
      'wall_seconds':time.perf_counter()-start,'process_cpu_seconds':time.process_time()-cpu,'official_model_outcomes_accessed':False,'observer_launched':False}
    rp=tests.SESSION/'QUALIFICATION.json';a.write_new(rp,receipt);print(json.dumps(a.binding(rp)))
    a.need(result.wasSuccessful() and not result.skipped,'Resource qualification failed; retained')
    contract={'schema':'qpath-v09-independent-resource-contract-1','status':'QUALIFIED_PENDING_ROOT_APPROVAL','utc':datetime.now(timezone.utc).isoformat(),
      'source_bindings':{n:sources[n] for n in r.SOURCE_NAMES},'qualification':a.binding(rp),
      'analysis_contract':a.binding(a.HERE/'INDEPENDENT_ANALYSIS_CONTRACT.json'),
      'scope':'Read-only ledger, exact worker PID/creation ownership, request/terminal/resource equality, failed and unknown costs, all756 committed result cost fields, B636 scored endpoint cost parity and independent CPU/wall summaries.',
      'tolerance':'Absolute1e-8 for sums/serialized floating costs only; file hashes, identities, counts and unknown status must be exact.',
      'root_gate':'Resource release plus pre-existing independent analysis authorization and committed official scoring; exclusive auxiliary audit lease.',
      'limits':'Native lifetime peak through retained sample is not final-exit or training-only memory. Unknown failed-attempt CPU is not zero. Separate qualification/audit/conversion/reproduction/timing receipts remain separate; workerCPU minus trainingCPU is not isolated ETEL overhead.'}
    cp=a.HERE/'INDEPENDENT_RESOURCE_CONTRACT.json';a.write_new(cp,contract);print(json.dumps(a.binding(cp)))

if __name__=='__main__':main()
