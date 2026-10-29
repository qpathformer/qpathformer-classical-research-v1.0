"""Independent read-only byte audit of the final v0.2 r4 artifacts."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

BASE = Path(r'C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.2')
OLD = BASE / 'draft_20261029_r3'
NEW = BASE / 'draft_20261029_r4'
OUT = NEW / 'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json'

def need(condition, message):
    if not condition:
        raise AssertionError(message)

def identity(data):
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def file_id(path):
    return identity(Path(path).read_bytes())

def equal_id(data, expected):
    return all(identity(data)[key] == expected[key] for key in ('bytes','sha256'))

def unique_object(pairs):
    result = {}
    for k,v in pairs:
        need(k not in result, 'Duplicate JSON key: '+k)
        result[k]=v
    return result

def decode(data):
    return json.loads(data, object_pairs_hook=unique_object)

def load(path):
    return decode(Path(path).read_bytes())

def safe(name):
    need(isinstance(name,str) and name and not name.startswith('/'), 'Unsafe path')
    need(not any(c in name for c in '\\:*?"<>|') and not any(ord(c)<32 for c in name), 'Nonportable path: '+repr(name))
    need(all(x not in ('','.','..') and not x.endswith((' ','.')) for x in name.split('/')), 'Unsafe path: '+name)

def indexed(entries):
    paths=[e['path'] for e in entries]
    for n in paths: safe(n)
    need(len(paths)==len(set(paths))==len({n.casefold() for n in paths}), 'Repeated or case-colliding records')
    return {e['path']:e for e in entries}

def read_package(folder, kind):
    name=f'QPathformer_v0.2_{kind}'
    zp=folder/'dist'/(name+'.zip')
    sp=folder/'dist'/(name+'.seal.json')
    seal=load(sp)
    need(seal['package']==name and seal['expected_root']==name and seal['member_path_prefix']==name+'/', 'Unexpected package root')
    need(seal['zip']['path']==zp.name and equal_id(zp.read_bytes(),seal['zip']), 'External ZIP binding mismatch')
    with zipfile.ZipFile(zp) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        need(len(names)==len(set(names))==len({n.casefold() for n in names}), 'Duplicate ZIP member')
        for i in infos:
            safe(i.filename)
            need(i.filename.startswith(name+'/') and not i.is_dir(), 'Wrong ZIP root or directory member')
            need(stat.S_ISREG(i.external_attr >> 16) and not i.flag_bits&1, 'Nonregular/encrypted ZIP member')
        need(z.testzip() is None, 'ZIP CRC error')
        data={n[len(name)+1:]:z.read(n) for n in names}
    for key,filename in [('internal_manifest','MANIFEST.json'),('internal_checksums','CHECKSUMS.sha256'),('source_map','SOURCE_MAP.json')]:
        need(seal[key]['path']==name+'/'+filename and equal_id(data[filename],seal[key]), 'External inventory binding mismatch')
    manifest=decode(data['MANIFEST.json'])
    need(manifest['schema']=='qpath-package-manifest-1' and manifest['package']==name, 'Wrong manifest header')
    entries=indexed(manifest['files'])
    need(set(entries)==set(data)-{'MANIFEST.json','CHECKSUMS.sha256'}, 'Manifest membership mismatch')
    for n,e in entries.items(): need(equal_id(data[n],e), 'Manifest identity mismatch '+n)
    checksum_entries=[]
    for line in data['CHECKSUMS.sha256'].decode('utf-8').splitlines():
        m=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        need(m is not None, 'Malformed checksum line')
        checksum_entries.append({'sha256':m[1],'path':m[2]})
    checks=indexed(checksum_entries)
    need(set(checks)==set(data)-{'CHECKSUMS.sha256'}, 'Checksum membership mismatch')
    for n,e in checks.items():need(hashlib.sha256(data[n]).hexdigest()==e['sha256'], 'Checksum mismatch '+n)
    for n,b in data.items():
        if n.endswith('.json'): decode(b)
    return data, dict(package=name,zip=dict(path=str(zp),**file_id(zp)),seal=dict(path=str(sp),**file_id(sp)),files=len(data),actual_build_root=seal['actual_build_root'])

def main():
    need(not OUT.exists(), 'Preserve existing audit receipt')
    packages=[]; changes={}; scopes=[]; current={}; prior={}; mappings=0
    for kind in ('Code','Documentation','Study'):
        old, old_record=read_package(OLD,kind)
        data, record=read_package(NEW,kind)
        current[kind]=data; prior[kind]=old
        need(Path(record['actual_build_root'])==NEW, 'Incorrect successor build root')
        need(set(data)==set(old), 'Unexpected successor package membership change')
        changes[kind]=[n for n in sorted(data) if data[n]!=old[n]]
        need(data['LICENSE_ADOPTION.json']==old['LICENSE_ADOPTION.json'], 'Historical licence adoption rewritten')
        for n in data:
            if n.startswith('LICENSES/'):
                need(data[n]==old[n], 'Licence text changed')
        source_map=decode(data['SOURCE_MAP.json'])
        need(Path(source_map['actual_build_root'])==NEW,'Wrong source-map build root')
        mapped=indexed(source_map['files'])
        need(set(mapped)==set(data)-{'SOURCE_MAP.json','MANIFEST.json','CHECKSUMS.sha256'}, 'Source map membership mismatch')
        for n,e in mapped.items():
            need(equal_id(data[n],e),'Source-map selected identity mismatch '+n)
            source=Path(e['source_absolute_path'])
            need(source.is_file() and equal_id(source.read_bytes(),e['source_identity']),'Source-map source identity mismatch '+str(source))
            mappings+=1
        for n,b in data.items():
            if '/' not in n and n.endswith('_LICENSE_SCOPE.json'):
                s=decode(b)
                need(s['status']=='ADOPTED' and s['licensor']=='Anthony Siljeg','Incorrect licence adoption/scope')
                membership=indexed(s['files'])
                for member,e in membership.items(): need(member in data and equal_id(data[member],e),'Licence identity mismatch '+member)
                prior_scope=decode(old[n])
                for field in ['status','license','licensor','attribution','scope','exclusions']:
                    if field in prior_scope: need(s[field]==prior_scope[field],'Scope semantics changed '+n+' '+field)
                need(set(membership)=={e['path'] for e in prior_scope['files']},'Scope membership broadened')
                scopes.append(dict(package=kind,path=n,files=len(membership),**identity(b)))
        packages.append(record)
    code=current['Code'];oldcode=prior['Code']
    scientific=[n for n in code if n.startswith('payload/')]
    need(scientific and all(code[n]==oldcode[n] for n in scientific),'Scientific payload changed')
    py=[n for n in scientific if n.endswith('.py')]
    need(len(py)==40,'Expected 40 scientific Python sources')
    scoped={e['path'] for e in decode(code['CODE_LICENSE_SCOPE.json'])['files']}
    need(scoped=={n for n in code if n.endswith('.py')} and len(scoped)==42,'Python scope coverage incorrect')
    for helper in ('startup_check.py','verify_package.py'):
        n='tools/'+helper
        need(code[n]!=oldcode[n],'Helper correction missing')
        staged=Path(r'C:\Anthony Siljeg\draft_releases_20261029\v02_r4_helpers')/helper
        need(code[n]==staged.read_bytes(),'Sealed helper differs from reviewed/tested source')
    reports=[n for n in current['Study'] if n.startswith('reports/')]
    need(len(reports)==2 and all(current['Study'][n]==prior['Study'][n] for n in reports),'Report bytes changed')
    report_scope=decode(current['Study']['REPORT_LICENSE_SCOPE.json'])
    docx=next(n for n in reports if n.endswith('.docx'))
    with zipfile.ZipFile(io.BytesIO(current['Study'][docx])) as z:
        for e in report_scope['embedded_figures']:need(equal_id(z.read(e['path']),e),'Report figure scope mismatch')
    for kind,n in [('Study','START_HERE.md'),('Documentation','RESEARCH_GUIDE.md'),('Documentation','RELEASE_NOTES.md')]:
        t=current[kind][n].decode('utf-8')
        need('Changing circuit scheduling improved' not in t and 'MLP129' in t and '16 to 40' in t,'Scientific summary correction absent '+kind+'/'+n)
        need('classical GPU' in t and 'simulated locally' in t,'Execution distinction absent')
    for kind in ('Code','Documentation'):
        t=current[kind]['START_HERE.md'].decode('utf-8')
        need('classical GPU' in t and 'parameter sharing across depths' in t and 'Changing circuit scheduling improved' not in t,'Overview correction absent')
    t=current['Study']['provenance/EDITION_CHANGES.md'].decode('utf-8')
    need('does not limit reuse under the adopted CC BY 4.0 grant' in t and 'Private owner review required before public distribution' not in t,'Publisher workflow clarification absent')
    guide=current['Documentation']['RESEARCH_GUIDE.md'].decode('utf-8')
    need('parameter-shift circuit-example work' in guide and '82.35%' in guide,'Work/runtime distinction missing')
    dep=decode(code['DEPENDENCY_INVENTORY.json'])
    import_paths={p for members in dep['direct_import_inventory'].values() for p in members}
    need({'tools/startup_check.py','tools/verify_package.py'}.issubset(import_paths),'Helper import mappings missing')
    fresh=load(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    need(fresh['status']=='PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP' and fresh['package_bytes_unchanged'] and fresh['receipt_outside_entire_package'],'Fresh verification failed')
    pmap={p['package']:p for p in packages}
    for p in fresh['packages']:
        for kind in ('zip','seal'):
            need(p[kind]==pmap[p['package']][kind],'Fresh record asset mismatch')
    for field in ('code_zip','code_seal','code_startup_receipt'):
        entry=fresh[field]
        need(equal_id(Path(entry['path']).read_bytes(),entry),'Fresh binding mismatch '+field)
    startup_path=Path(fresh['code_startup_receipt']['path'])
    need(not startup_path.is_relative_to(NEW/'qa/fresh_extraction'),'Receipt inside package')
    startup=load(startup_path)
    need(startup['status']=='PASS' and startup['package_bytes_unchanged'] and not startup['errors'],'Genuine startup failure')
    need(len(startup['checks'])==4 and all(e['returncode']==0 and e['status']=='PASS' for e in startup['checks']),'Expected four successful genuine checks')
    need('classical CPU forward without updates' in [e['label'] for e in startup['checks']],'CPU forward absent')
    for e in startup['checks']:
        need('-B' in e['command'] and 'MOCK' not in json.dumps(e),'Startup binding is mocked or permits bytecode')
    expected_fingerprint=hashlib.sha256(json.dumps({n:identity(b) for n,b in code.items()},sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    for field in ('integrity_before','integrity_after'):
        need(startup[field]['status']=='PASS' and startup[field]['files']==len(code) and startup[field]['package_fingerprint_sha256']==expected_fingerprint,'Startup fingerprint mismatch')
    extracted=NEW/'qa/fresh_extraction/QPathformer_v0.2_Code'
    extracted_files={p.relative_to(extracted).as_posix():p.read_bytes() for p in extracted.rglob('*') if p.is_file()}
    need(extracted_files==code,'Fresh extraction differs from sealed code')
    invocation=load(NEW/'receipts/STARTUP_INVOCATION.json')
    need(invocation['returncode']==0 and Path(invocation['command'][2])==extracted/'tools/startup_check.py','Startup invocation binding incorrect')
    revision=load(NEW/'receipts/REVISION_RECORD.json')
    for n,i in revision['previous_assets'].items(): need(file_id(OLD/'dist'/n)==i,'Prior sealed evidence changed')
    binding_path=NEW/'receipts/HELPER_TEST_RESULTS.json'
    need(binding_path.is_file(),'Bound helper regression evidence absent')
    binding=load(binding_path)
    need(binding['status']=='PASS_HELPER_REGRESSION_PROBES' and 'not genuine numerical startup evidence' in binding['classification'],'Helper probe classification absent')
    tested={Path(e['path']).name:e for e in binding['tested_files']}
    for helper in ('startup_check.py','verify_package.py'):
        need(equal_id(code['tools/'+helper],tested[helper]),'Regression probe helper binding mismatch '+helper)
    need(equal_id((NEW/'tools/test_helpers.py').read_bytes(),tested['test_helpers.py']),'Regression harness binding mismatch')
    needed_probes={'duplicate_checksum_path','duplicate_manifest_path','preexisting_receipt_preserved','receipt_reserved_before_child_checks','prestartup_integrity_failure_stops_checks','midstartup_integrity_failure','rebound_inventories_do_not_hide_midstartup_change','child_timeout_recorded_as_failure'}
    probes={e['probe']:e for e in binding['probes']}
    need(needed_probes.issubset(probes) and all(e['status']=='PASS' for e in probes.values()),'Focused regression probes missing or failed')
    result=dict(schema='qpath-independent-successor-audit-1',status='PASS',checked_at_utc=datetime.now(timezone.utc).isoformat(),study_version='v0.2',actual_build_root=str(NEW),packages=packages,scopes=scopes,source_map_entries_checked=mappings,scientific_payload_files_unchanged=len(scientific),scientific_python_files_unchanged=40,reports_unchanged=[dict(path=n,**identity(current['Study'][n])) for n in reports],canonical_license_texts_and_adoption_records_unchanged=True,helper_sources_match_tested_staging=True,helper_regression_binding=dict(path=str(binding_path),**file_id(binding_path)),startup_binding=dict(path=str(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**file_id(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')),startup_fingerprint_matches_sealed_code=True,genuine_startup_checks=4,changed_package_files=changes,prior_sealed_evidence_preserved=True,review_boundary='Independent byte/inventory/scope/provenance/summary audit. Genuine numerical startup is evidenced by the actual final invocation and receipt; this audit does not rerun training, scoring, physical QPU jobs or report rendering.')
    with OUT.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'status':'PASS','receipt':str(OUT),'packages':len(packages),'source_map_entries':mappings,'scientific_python':40,'reports':2}))

if __name__=='__main__':main()
