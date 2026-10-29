"""Independently replay six disposable paired endpoints, never official study."""
import json,time
from datetime import datetime,timezone
from pathlib import Path
import audit_endpoints_v09 as a

root=a.ROOT/'quantum/synthetic_fixtures/trainer_20261022T084133'
manifest=a.read(root/'governance/FIXTURE_MANIFEST.json');auth_path=Path(manifest['authorization']['path']);auth=a.read(auth_path)
seal=a.read(root/'quantum/data/DATA_SEAL.json');paired={};cache={};reports=[];start=time.perf_counter()
a.need({j['arm'] for j in manifest['jobs']}=={'C_S','C_L','C_R','T_S','T_L','T_R'} and len(manifest['jobs'])==6,'Wrong paired fixture')
for job in manifest['jobs']:
    reports.append(a.audit_endpoint(root,job,root/'endpoints'/job['run_id'],auth,auth_path,seal,paired,cache))
    print(json.dumps({'fixture_verified':len(reports),'arm':job['arm']}),flush=True)
a.need(len(paired)==1,'Expected one population/seed pair')
receipt={'schema':'qpath-v09-independent-paired-warmup-1','status':'PASS','utc':datetime.now(timezone.utc).isoformat(),
  'scope':'Six disposable synthetic qualification endpoints; not official training or audit. No test payloads opened.',
  'fixture':str(root),'manifest':a.binding(root/'governance/FIXTURE_MANIFEST.json'),
  'independent_contract':a.binding(a.HERE/'INDEPENDENT_AUDIT_CONTRACT.json'),
  'source_bindings':{n:a.binding(a.HERE/n) for n in ('audit_endpoints_v09.py','reference_v09.py','qualify_paired_warmup.py')},
  'verified_endpoints':6,'completed_rounds_each':20,'updates_each':1500,'endpoints':reports,
  'paired_evidence':[{'population':key[0],'seed':key[1],'hashes':value} for key,value in paired.items()],
  'full750_warmup_check':'Exact initial expert vectors, all750 expert gradient vectors and10roundend vectors across C_S/L/R and T_S/L/R. IndependentAdam replays every step; all extra coefficients zero through750.',
  'wall_seconds':time.perf_counter()-start}
a.write_new(a.HERE/'PAIRED_WARMUP_QUALIFICATION_v01.json',receipt)
print(json.dumps({'status':'PASS','receipt':a.binding(a.HERE/'PAIRED_WARMUP_QUALIFICATION_v01.json')},indent=2))
