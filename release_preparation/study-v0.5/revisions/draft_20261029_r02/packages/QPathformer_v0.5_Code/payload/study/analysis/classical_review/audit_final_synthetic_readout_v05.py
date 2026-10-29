"""Recheck the final registered source's generated untrained capsule, no outcomes."""
from pathlib import Path
import json, sys
import audit_synthetic_readout_v05 as previous

HERE=Path(__file__).resolve().parent
previous.FIXTURE=Path(r'C:\Anthony Siljeg\Q2_v05_synthetic_readiness_fixtures\0aee15a8-e391-4ec6-965e-c32229b39c5d')
out=HERE/'SYNTHETIC_READINESS_FINAL_INDEPENDENT_AUDIT.json'
if out.exists():raise FileExistsError(out)
result=previous.run()
report=previous.read(previous.FIXTURE/'capsule/report.json')
maximum=0.
for row in report['circuits']:
    for key in ('production_moments','aer_core_moments'):
        error=max(abs(row[key][name]-row['reference_moments'][name]) for name in row['reference_moments'])
        previous.need(error<=2e-12,'Final five-moment parity mismatch')
        maximum=max(maximum,error)
    previous.need(abs(row['compiled_aer_probability']-row['reference_probability'])<=2e-12,'Compiled head parity mismatch')
previous.need(report['production_model_forward_statevector_examples']==report['additional_full_moment_statevector_examples']==128,'Additional production work missing')
result.update(final_registered_source=True, maximum_saved_full_moment_parity_error=maximum,
    registration_sha256=previous.sha(previous.ROOT/'quantum/EVALUATION_REGISTRATION.json'))
result['source_sha256'][Path(__file__).relative_to(previous.ROOT).as_posix()]=previous.sha(__file__)
result['limits']='Independent density, moment, head and exact saved-probability joint RNG replay; saved compiled/Aer parity records checked but compiled QASM and actual stochastic simulator are not independently re-executed. No actual selected engineering or confirmation checkpoint used.'
with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='historical_producer_source_hashes'},indent=2))
