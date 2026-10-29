"""Independent read-only byte audit of the final v0.4 r3 artifacts."""
from datetime import datetime, timezone
import hashlib
import ast
import difflib
import io
import json
from pathlib import Path
import re
import posixpath
import stat
import sys
from urllib.parse import unquote, urlparse
import zipfile

BASE = Path(r'C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.4')
OLD = BASE / 'draft_20261029_r2'
NEW = BASE / 'draft_20261029_r3'
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
    name=f'QPathformer_v0.4_{kind}'
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

def report_preservation(study):
    import xml.etree.ElementTree as E
    source=Path(r'C:\Q2\Improvement_Study_v0.4\docs\QPATH-RPT-005_Routing_and_Circuit_Contribution_Study_v0.4.docx')
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(io.BytesIO(study['reports/QPathformer_v0.4_Report.docx'])) as edition:
        ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        original_body=E.fromstring(original.read('word/document.xml')).find(ns+'body')
        edition_body=E.fromstring(edition.read('word/document.xml')).find(ns+'body')
        old=[x for x in original_body if x.tag!=ns+'sectPr']
        new=[x for x in edition_body if x.tag!=ns+'sectPr']
        canonical=lambda x:E.canonicalize(E.tostring(x,encoding='unicode'))
        need(len(old)==185 and len(new)>len(old),'Unexpected report body length')
        need(all(canonical(a)==canonical(b) for a,b in zip(old,new)),'Historical report body changed')
        tables=sum(x.tag==ns+'tbl' for x in old)
        need(tables==31,'Unexpected original table count')
        media=[n for n in original.namelist() if n.startswith('word/media/')]
        need(len(media)==4 and all(original.read(n)==edition.read(n) for n in media),'Original figures changed')
        return dict(original_report=dict(path=str(source),**file_id(source)),body_elements_preserved=len(old),tables_preserved=tables,figures_preserved=len(media))

def lineage_check(code,oldcode,study,oldstudy):
    inherited=decode(code['INHERITED_LICENSE_MAP.json']);old=decode(oldcode['INHERITED_LICENSE_MAP.json'])
    need(inherited['exact_whole_file_matches']==old['exact_whole_file_matches']==[],'Unexpected whole-file inherited match claim')
    need(inherited['shared_expression_evidence']==old['shared_expression_evidence'],'Historical scientific shared expression changed')
    need(len(inherited['shared_expression_evidence'])==2,'Expected two inherited scientific records')
    block_count=0
    for e in inherited['shared_expression_evidence']:
        need(equal_id(code[e['path']],e),'Inherited current source binding mismatch')
        source=Path(e['adopted_source']);scope_path=Path(e['scope_record'])
        need(equal_id(source.read_bytes(),e['adopted_identity']),'Earlier adopted source binding mismatch')
        need(equal_id(scope_path.read_bytes(),e['scope_record_identity']),'Earlier adopted scope binding mismatch')
        adopted_scope=load(scope_path)
        need(adopted_scope['status']=='ADOPTED_PLATFORM_1_0_SCOPED_CODE','Earlier scientific scope is not adopted')
        prior_members=[x for group in adopted_scope['groups'].values() for x in group]
        member=next(x for x in prior_members if x['path']==e['adopted_identity']['path'])
        need(equal_id(source.read_bytes(),member),'Earlier scientific source absent from adopted scope')
        selected=code[e['path']].decode('utf-8').splitlines(keepends=True)
        adopted=source.read_text('utf-8').splitlines(keepends=True)
        for block in e['matching_blocks']:
            a=''.join(selected[block['selected_start_line']-1:block['selected_end_line']])
            b=''.join(adopted[block['adopted_start_line']-1:block['adopted_end_line']])
            need(a==b and len(a)==block['characters'] and hashlib.sha256(a.encode()).hexdigest()==block['utf8_text_sha256'],'Inherited expression block differs')
            block_count+=1
    need(block_count==3,'Expected three shared scientific expression blocks')
    helper_lineage=inherited['package_helper_lineage']
    need({e['path'] for e in helper_lineage}=={'tools/startup_check.py','tools/verify_package.py'},'Helper lineage incomplete')
    helper_results=[]
    for e in helper_lineage:
        current=code[e['path']];source=Path(e['source_path']).read_bytes();prior_scope=load(e['scope_record'])
        need(equal_id(current,e['current']) and equal_id(source,e['source_identity']),'Helper lineage identity mismatch')
        need(equal_id(Path(e['scope_record']).read_bytes(),e['scope_record_identity']),'Helper lineage scope identity mismatch')
        need(prior_scope['status']=='ADOPTED' and prior_scope['license']==e['license']=='Q-Pathformer Platform License 1.0','Helper source scope not adopted')
        member=next(x for x in prior_scope['files'] if x['path']==e['path'])
        need(equal_id(source,member),'Helper inherited source not scoped')
        if e['path'].endswith('verify_package.py'):
            need(current==source and e['relation']=='Byte-identical reuse','Verifier reuse claim differs')
        else:
            need(current!=source and e['relation'].startswith('Adaptation'),'Startup adaptation claim differs')
            need(max(b.size for b in difflib.SequenceMatcher(None,current.decode().splitlines(),source.decode().splitlines(),autojunk=False).get_matching_blocks())>20,'Startup common implementation not substantiated')
        helper_results.append(dict(path=e['path'],current=e['current'],source=e['source_identity'],scope=e['scope_record_identity'],relation=e['relation']))
    need(study['INHERITED_REPORT_EXPRESSION.json']==oldstudy['INHERITED_REPORT_EXPRESSION.json'],'Historical report inheritance record changed')
    report_map=decode(study['INHERITED_REPORT_EXPRESSION.json'])
    need(not report_map['matches'],'Unsubstantiated positive report inheritance claim')
    return dict(shared_scientific_records=2,shared_scientific_blocks=3,helper_lineage=helper_results,report_inheritance_matches=0)

def markdown_links(current):
    checked=0
    for kind,files in current.items():
        for name,b in files.items():
            if not name.endswith('.md'):continue
            for target in re.findall(r'\[[^\]]*\]\(([^)\s]+)\)',b.decode('utf-8')):
                parsed=urlparse(target.strip('<>'))
                if parsed.scheme or parsed.netloc or not parsed.path:continue
                resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),unquote(parsed.path)))
                need(resolved in files or any(n.startswith(resolved.rstrip('/')+'/') for n in files),'Broken packaged Markdown link '+kind+'/'+name+' -> '+target)
                checked+=1
    return checked

def main():
    need(not OUT.exists(),'Preserve existing audit receipt')
    preliminary=load(Path(__file__).parent/'PRELIMINARY_R2_CHECKS.json')
    for e in preliminary['assets']:
        need(equal_id((OLD/'dist'/e['name']).read_bytes(),e),'Historical sealed asset altered')
    packages=[];changes={};scopes=[];current={};prior={};mappings=0
    for kind in ('Code','Documentation','Study'):
        old,old_record=read_package(OLD,kind)
        data,record=read_package(NEW,kind)
        current[kind]=data;prior[kind]=old
        expected_root=NEW
        need(Path(record['actual_build_root'])==expected_root,'Incorrect retained or successor build root')
        need(set(data)==set(old),'Unexpected package membership change')
        changes[kind]=[n for n in sorted(data) if data[n]!=old[n]]
        for n in data:
            if n.startswith(('historical/','provenance/','reports/')):
                need(data[n]==old[n],'Historical retained record or report changed: '+kind+'/'+n)
        need(data['LICENSE_ADOPTION.json']==old['LICENSE_ADOPTION.json'],'Historical licence adoption changed')
        for n in data:
            if n.startswith('LICENSES/'):need(data[n]==old[n],'Licence text changed')
        need(hashlib.sha256(data['LICENSES/CC-BY-4.0.txt']).hexdigest()=='2ade8c89b8bbe0d859b124a9e47032c8494022f43091e8278ae8e2554a292196','CC legal text differs')
        need(hashlib.sha256(data['LICENSES/QPATHFORMER-PLATFORM-1.0.txt']).hexdigest()=='efa2911bfa72c36bd471bdf8d047c4a54cebf19e0a0f835184c348ef0e772057','Platform legal text differs')
        source_map=decode(data['SOURCE_MAP.json'])
        need(Path(source_map['actual_build_root'])==expected_root,'Wrong source-map build root')
        mapped=indexed(source_map['files'])
        need(set(mapped)==set(data)-{'SOURCE_MAP.json','MANIFEST.json','CHECKSUMS.sha256'},'Source-map membership differs')
        for n,e in mapped.items():
            need(equal_id(data[n],e),'Source-map selected identity differs '+n)
            source=Path(e['source_absolute_path'])
            need(source.is_file() and equal_id(source.read_bytes(),e['source_identity']),'Source-map source identity differs '+str(source))
            mappings+=1
        for n,b in data.items():
            if '/' not in n and n.endswith('_LICENSE_SCOPE.json'):
                scope=decode(b);previous=decode(old[n]);entries=indexed(scope['files'])
                need(scope['status']=='ADOPTED' and scope['licensor']=='Anthony Siljeg','Incorrect licence state')
                for rel,e in entries.items():need(rel in data and equal_id(data[rel],e),'Incorrect scoped identity '+rel)
                for field in ('status','license','licensor','attribution','scope','exclusions'):
                    if field in previous:need(scope[field]==previous[field],'Scope meaning changed '+n)
                need(set(entries)=={e['path'] for e in previous['files']},'Scope membership changed')
                scopes.append(dict(package=kind,path=n,files=len(entries),**identity(b)))
        packages.append(record)
    code=current['Code'];oldcode=prior['Code']
    scientific=[n for n in code if n.startswith('payload/')]
    need(all(code[n]==oldcode[n] for n in scientific),'Scientific payload changed')
    py=[n for n in scientific if n.endswith('.py')]
    need(len(py)==48,'Expected 48 scientific Python sources')
    scope=decode(code['CODE_LICENSE_SCOPE.json'])
    need({e['path'] for e in scope['files']}=={n for n in code if n.endswith('.py')} and len(scope['files'])==50,'Python scope coverage differs')
    for helper in ('startup_check.py','verify_package.py'):
        n='tools/'+helper
        need(code[n]!=oldcode[n],'Expected helper correction missing')
        staged=Path(r'C:\Anthony Siljeg\draft_releases_20261029\v04_r3_helpers')/helper
        need(code[n]==staged.read_bytes(),'Sealed helper differs from tested staging')
    inventory=load(NEW/'receipts/SOURCE_INVENTORY.json')
    need(len(inventory['selected_files'])==57 and len(inventory['selected_code'])==54,'Selected source accounting changed')
    for e in inventory['selected_files']:
        need(equal_id(Path(e['absolute_path']).read_bytes(),e),'Original selected source changed '+e['path'])
    for n in scientific:
        source=Path(inventory['source_root'])/n.removeprefix('payload/study/')
        need(code[n]==source.read_bytes(),'Scientific package differs from original '+n)
    reports=[n for n in current['Study'] if n.startswith('reports/')]
    need(len(reports)==2 and all(current['Study'][n]==prior['Study'][n] for n in reports),'Report bytes changed')
    structural=report_preservation(current['Study'])
    quick=code['QUICKSTART.md'].decode('utf-8')
    need(quick.count('$LASTEXITCODE -ne 0')==2 and 'throw ' in quick,'PowerShell exit handling absent')
    need('v0.2' not in quick and 'CPU text forward' not in quick,'Irrelevant v0.2 quickstart scope remains')
    need('seal' in quick.lower() and 'extract' in quick.lower(),'External seal/extraction boundary absent')
    dep=decode(code['DEPENDENCY_INVENTORY.json'])
    import_paths={p for members in dep['direct_import_inventory'].values() for p in members}
    need({'tools/startup_check.py','tools/verify_package.py'}.issubset(import_paths),'Helper imports absent from dependency inventory')
    actual_imports={}
    for name,b in code.items():
        if not name.endswith('.py'):continue
        for node in ast.walk(ast.parse(b,filename=name)):
            mods=[n.name.split('.')[0] for n in node.names] if isinstance(node,ast.Import) else ([node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module and node.level==0 else [])
            for mod in mods:actual_imports.setdefault(mod,set()).add(name)
    need({m:set(paths) for m,paths in dep['direct_import_inventory'].items()}==actual_imports,'Dependency import inventory differs from actual selected Python')
    lineage=lineage_check(code,oldcode,current['Study'],prior['Study'])
    local_links=markdown_links(current)
    fresh=load(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    need(fresh['status']=='PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP' and fresh['package_bytes_unchanged'] and fresh['receipt_outside_entire_package'],'Fresh startup failed')
    pmap={p['package']:p for p in packages}
    for p in fresh['packages']:
        for key in ('zip','seal'):need(p[key]==pmap[p['package']][key],'Fresh selected asset mismatch')
    for field in ('code_zip','code_seal','code_startup_receipt'):
        e=fresh[field];need(equal_id(Path(e['path']).read_bytes(),e),'Fresh binding mismatch '+field)
    startup_path=Path(fresh['code_startup_receipt']['path'])
    need(not startup_path.is_relative_to(NEW/'qa/fresh_extraction'),'Receipt inside package')
    startup=load(startup_path)
    need(startup['status']=='PASS' and startup['package_bytes_unchanged'] and not startup['errors'],'Final startup failed')
    need(len(startup['checks'])==3 and all(e['status']=='PASS' and e['returncode']==0 for e in startup['checks']),'Expected three genuine checks')
    need(startup['parsed_python_files']==50 and startup['prediction_methods_checked']==9 and startup['numpy_version'],'Actual startup scope counts/version missing')
    need('CPU text forward' not in startup['scope'] and 'v0.2' not in startup['scope'],'Startup scope remains generic v0.2')
    for e in startup['checks']:need('-B' in e['command'] and 'MOCK' not in json.dumps(e),'Genuine startup command is mocked or allows bytecode')
    fingerprint=hashlib.sha256(json.dumps({n:identity(b) for n,b in code.items()},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for field in ('integrity_before','integrity_after'):
        need(startup[field]['status']=='PASS' and startup[field]['files']==len(code) and startup[field]['package_fingerprint_sha256']==fingerprint,'Startup fingerprint mismatch')
    extracted=NEW/'qa/fresh_extraction/QPathformer_v0.4_Code'
    need({p.relative_to(extracted).as_posix():p.read_bytes() for p in extracted.rglob('*') if p.is_file()}==code,'Final extraction differs from sealed code')
    invocation=load(NEW/'receipts/STARTUP_INVOCATION.json')
    need(invocation['returncode']==0 and Path(invocation['command'][2])==extracted/'tools/startup_check.py','Incorrect final startup invocation')
    binding_path=NEW/'receipts/HELPER_TEST_RESULTS.json'
    binding=load(binding_path)
    need(binding['status']=='PASS_HELPER_REGRESSION_PROBES' and 'not genuine numerical startup evidence' in binding['classification'],'Helper probes not passed or misclassified')
    tested={Path(e['path']).name:e for e in binding['tested_files']}
    for helper in ('startup_check.py','verify_package.py'):
        need(equal_id(code['tools/'+helper],tested[helper]),'Tested-helper binding mismatch')
    need(equal_id((NEW/'tools/test_helpers.py').read_bytes(),tested['test_helpers.py']),'Probe harness identity mismatch')
    need(all(e['status']=='PASS' for e in binding['probes']),'A helper probe failed')
    needed={'duplicate_checksum_path','conflicting_duplicate_checksum_path','duplicate_manifest_path','missing_file','changed_same_size_guidance','extra_file','preexisting_receipt_preserved','receipt_reserved_before_child_checks','prestartup_integrity_failure_stops_checks','midstartup_integrity_failure','child_timeout_recorded_as_failure'}
    need(needed.issubset({p['probe'] for p in binding['probes']}),'Required narrow helper probes absent')
    powershell_path=NEW/'receipts/POWERSHELL_TEST_RESULTS.json'
    ps=load(powershell_path)
    need(ps['status']=='PASS_POWERSHELL_QUICKSTART_CHECKS' and ps['powershell_version'],'PowerShell checks not passed')
    ps_tested={Path(e['path']).name:e for e in ps['tested_files']}
    for name in ('startup_check.py','verify_package.py'):need(equal_id(code['tools/'+name],ps_tested[name]),'PowerShell helper binding mismatch')
    need(equal_id(code['QUICKSTART.md'],ps_tested['QUICKSTART.md']),'PowerShell quickstart binding mismatch')
    need(equal_id((NEW/'tools/test_powershell.py').read_bytes(),ps_tested['test_powershell.py']),'PowerShell harness binding mismatch')
    psprobes={e['probe']:e for e in ps['probes']}
    for name in ('invalid_missing','invalid_changed_same_size','invalid_unexpected'):
        e=psprobes[name]
        need(e['status']=='PASS' and e['returncode']!=0 and not e['startup_receipt_created'] and e['package_bytes_unchanged'],'PowerShell did not stop invalid package before startup')
        need(e['classification']=='ACTUAL_POWERSHELL_STOP_BEFORE_STARTUP','PowerShell invalid test was mocked')
    valid=psprobes['valid']
    need(valid['status']=='PASS' and valid['returncode']==0 and valid['startup_receipt_created'] and valid['package_bytes_unchanged'],'PowerShell valid fixture failed')
    need(valid['classification']=='GENUINE_BOUNDED_STARTUP_ON_UNSEALED_DISPOSABLE_HELPER_FIXTURE_NOT_FINAL_ZIP','PowerShell fixture misclassified as final ZIP')
    need(valid['startup_result']['status']=='PASS' and len(valid['startup_result']['checks'])==3,'PowerShell valid fixture startup evidence missing')
    body=(NEW/'RELEASE_NOTES.md').read_text('utf-8')
    need('BCE' in body and all(x in body for x in ('0.17689','0.18280','0.21207','98.32%','97.16%','94.41%')),'Release primary metrics missing')
    need('737,280' in body and '45' in body and 'physical' in body.lower(),'Release counting distinctions absent')
    need('draft' in body.lower() and 'v0.9.5' in body,'Draft workflow constraints missing')
    guide=current['Documentation']['RESEARCH_GUIDE.md'].decode('utf-8')
    for value in ('99.4444','5,000','1,440','720','737,280','199,065,600','15,000'):
        need(value in guide,'Research guide accounting/inference detail absent: '+value)
    need('The publisher' in current['Study']['START_HERE.md'].decode('utf-8') and 'does not limit reuse' in current['Study']['START_HERE.md'].decode('utf-8'),'Publication/adopted-grant clarification absent')
    result=dict(schema='qpath-independent-successor-audit-1',status='PASS',checked_at_utc=datetime.now(timezone.utc).isoformat(),study_version='v0.4',actual_build_root=str(NEW),packages=packages,scopes=scopes,source_map_entries_checked=mappings,scientific_payload_files_unchanged=len(scientific),scientific_python_files_unchanged=48,original_selected_files_checked=len(inventory['selected_files']),original_report_preservation=structural,historical_records_and_report_bytes_unchanged=True,reports_unchanged=[dict(path=n,**identity(current['Study'][n])) for n in reports],canonical_license_texts_and_adoption_records_unchanged=True,helper_sources_match_tested_staging=True,helper_regression_binding=dict(path=str(binding_path),**file_id(binding_path)),helper_probes_passed=len(binding['probes']),powershell_regression_binding=dict(path=str(powershell_path),**file_id(powershell_path)),powershell_probes_passed=len(ps['probes']),powershell_version=ps['powershell_version'],startup_binding=dict(path=str(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**file_id(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')),startup_fingerprint_matches_sealed_code=True,genuine_startup_checks=3,parsed_python_files=50,prediction_methods_checked=9,numpy_version=startup['numpy_version'],changed_package_files=changes,prior_sealed_evidence_preserved=True,review_boundary='Independent byte/inventory/scope/source/provenance audit; source report body, tables and media compared structurally. Actual numerical startup and PowerShell regression results are separately bound evidence. No training, scoring, shots, QPU work, full archive replay or new report rendering performed.')
    result.update(helper_and_scientific_lineage=lineage,active_local_markdown_links_checked=local_links,code_selection_source_files=54,dependency_module_file_pairs=sum(map(len,actual_imports.values())),all_three_packages_rebuilt=True,preliminary_audit_binding=dict(path=str(Path(__file__).parent/'PRELIMINARY_R2_CHECKS.json'),**file_id(Path(__file__).parent/'PRELIMINARY_R2_CHECKS.json')))
    with OUT.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(status='PASS',receipt=str(OUT),packages=len(packages),source_map_entries=mappings,scientific_python=48,reports=2)))

if __name__=='__main__':main()



