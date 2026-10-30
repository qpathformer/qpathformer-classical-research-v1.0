"""Independent byte, provenance, rights and recorded-check audit for v0.6 r3."""
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import stat
import sys
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET
import zipfile

HERE=Path(__file__).resolve().parent
BASE=Path(r'C:\Q2\Release_Preparation\QPathformer_Classical_Research')
OLD=BASE/'study-v0.6/draft_20261029_r02'
NEW=BASE/'study-v0.6/draft_20261030_r3'
HELPERS=HERE.parent/'v06_r3_helpers'
OUT=NEW/'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json'

def need(ok,message):
    if not ok:raise RuntimeError(message)

def identity(data):return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def file_id(path):return identity(Path(path).read_bytes())
def equal_id(data,expected):return all(identity(data)[k]==expected[k] for k in ('bytes','sha256'))
def unique_object(pairs):
    result={}
    for k,v in pairs:
        need(k not in result,'Duplicate JSON key: '+k);result[k]=v
    return result
def decode(data):return json.loads(data,object_pairs_hook=unique_object)
def load(path):return decode(Path(path).read_bytes())
def save_exclusive(path,result):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
def now():return datetime.now(timezone.utc).isoformat()
def safe(name):
    need(isinstance(name,str) and name and not name.startswith('/'),'Unsafe path')
    need(not any(c in name for c in '\\:*?"<>|') and not any(ord(c)<32 for c in name),'Nonportable path '+repr(name))
    need(all(x not in ('','.','..') and not x.endswith((' ','.')) for x in name.split('/')),'Unsafe path '+name)
def indexed(entries):
    paths=[e['path'] for e in entries]
    for n in paths:safe(n)
    need(len(paths)==len(set(paths))==len({n.casefold() for n in paths}),'Duplicate or case-colliding records')
    return {e['path']:e for e in entries}

def read_package(folder,kind):
    name=f'QPathformer_v0.6_{kind}';zp=folder/'dist'/(name+'.zip');sp=folder/'dist'/(name+'.seal.json');seal=load(sp)
    need(seal['schema']=='qpath-study-release-seal-1' and seal['package_id']==name and seal['member_path_prefix']==name+'/','Unexpected package schema/root')
    need(seal['zip']['path']==zp.name and equal_id(zp.read_bytes(),seal['zip']),'External ZIP binding differs')
    need(Path(seal['actual_build_root'])==folder and Path(seal['assembled_at'])==folder/'assembly'/name,'Seal build origin differs')
    with zipfile.ZipFile(zp) as z:
        infos=z.infolist();names=[e.filename for e in infos]
        need(len(names)==len(set(names))==len({n.casefold() for n in names}),'Duplicate ZIP member')
        for e in infos:
            safe(e.filename);need(e.filename.startswith(name+'/') and not e.is_dir(),'Wrong ZIP root/directory')
            need((e.external_attr>>16)&0o170000 in (0,stat.S_IFREG) and not e.flag_bits&1,'Nonregular/encrypted ZIP member')
        need(z.testzip() is None,'ZIP CRC error')
        data={n[len(name)+1:]:z.read(n) for n in names}
    for key,n in [('internal_manifest','MANIFEST.json'),('internal_checksums','CHECKSUMS.sha256'),('source_map','provenance/SOURCE_MAP.json')]:
        need(seal[key]['path']==n and equal_id(data[n],seal[key]),'External inventory binding differs')
    manifest=decode(data['MANIFEST.json']);need(manifest['schema']=='qpath-package-manifest-1' and manifest['package']==name,'Wrong manifest header')
    entries=indexed(manifest['files']);need(set(entries)==set(data)-{'MANIFEST.json','CHECKSUMS.sha256'},'Manifest membership differs')
    for n,e in entries.items():need(equal_id(data[n],e),'Manifest identity differs '+n)
    raw=[]
    for line in data['CHECKSUMS.sha256'].decode('utf-8').splitlines():
        m=re.fullmatch(r'([0-9a-f]{64})  (.+)',line);need(m is not None,'Malformed checksum line')
        raw.append(dict(path=m[2],sha256=m[1]))
    checks=indexed(raw);need(set(checks)==set(data)-{'CHECKSUMS.sha256'},'Checksum membership differs')
    for n,e in checks.items():need(hashlib.sha256(data[n]).hexdigest()==e['sha256'],'Checksum differs '+n)
    need(seal['files']==len(data) and seal['manifest_entries']==len(entries) and seal['checksum_entries']==len(checks),'Seal counts differ')
    for n,b in data.items():
        if n.endswith('.json'):decode(b)
    return data,dict(package=name,zip=dict(path=str(zp),**file_id(zp)),seal=dict(path=str(sp),**file_id(sp)),files=len(data),actual_build_root=str(folder))

def inspect_sources(data,folder):
    source=decode(data['provenance/SOURCE_MAP.json']);need(Path(source['actual_build_root'])==folder,'Source-map build origin differs')
    entries=indexed(source['files']);generated=source['generated_files']
    for n in generated:safe(n)
    need(len(generated)==len(set(generated)) and not set(entries)&set(generated),'Generated/source map overlaps')
    need(set(entries)|set(generated)==set(data)-{'provenance/SOURCE_MAP.json','MANIFEST.json','CHECKSUMS.sha256'},'Source/generated coverage differs')
    for n,e in entries.items():
        need(equal_id(data[n],e['output_identity']),'Mapped output differs '+n)
        need(equal_id(Path(e['source']).read_bytes(),e['source_identity']),'Mapped retained source differs '+e['source'])
    need(equal_id(Path(source['original_report']['path']).read_bytes(),source['original_report']),'Original report source differs')
    need(equal_id(Path(source['source_delivery_manifest']['path']).read_bytes(),source['source_delivery_manifest']),'Retained delivery-manifest identity differs')
    return dict(source_map_entries=len(entries),generated_entries=len(generated))

def inspect_rights(data,old=None):
    need(hashlib.sha256(data['LICENSES/CC-BY-4.0.txt']).hexdigest()=='2ade8c89b8bbe0d859b124a9e47032c8494022f43091e8278ae8e2554a292196','CC text differs')
    need(hashlib.sha256(data['QPATHFORMER-PLATFORM-1.0.txt']).hexdigest()=='efa2911bfa72c36bd471bdf8d047c4a54cebf19e0a0f835184c348ef0e772057','Platform text differs')
    scopes={}
    for n,b in data.items():
        if '/' not in n and n.endswith('_LICENSE_SCOPE.json'):
            scope=decode(b);need(scope['status']=='ADOPTED','Scope not adopted')
            entries=indexed(scope['files'])
            for path,e in entries.items():need(equal_id(data[path],e),'Scoped identity differs '+path)
            if old:
                previous=decode(old[n]);need({k:v for k,v in scope.items() if k!='files'}=={k:v for k,v in previous.items() if k!='files'},'Scope terms/metadata changed '+n)
                need(set(entries)=={e['path'] for e in previous['files']},'Scope members changed '+n)
            scopes[n]=dict(files=len(entries),**identity(b))
    adoption=decode(data['LICENSE_ADOPTION.json']);need(adoption['status']=='ADOPTED' and adoption['licensor']=='Anthony Siljeg','Adoption differs')
    need({e['path'] for e in adoption['scopes']}==set(scopes),'Adoption scope membership differs')
    for e in adoption['scopes']:need(equal_id(data[e['path']],e),'Adoption-scope binding differs')
    if old:
        previous=decode(old['LICENSE_ADOPTION.json'])
        need({k:v for k,v in adoption.items() if k!='scopes'}=={k:v for k,v in previous.items() if k!='scopes'},'Owner adoption decision changed')
    return scopes

def report_preservation(study):
    source=next(Path(r'C:\Q2\Improvement_Study_v0.6\docs').glob('*.docx'))
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(io.BytesIO(study['reports/QPathformer_v0.6_Report.docx'])) as edition:
        ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        old=[x for x in ET.fromstring(original.read('word/document.xml')).find(ns+'body') if x.tag!=ns+'sectPr']
        new=[x for x in ET.fromstring(edition.read('word/document.xml')).find(ns+'body') if x.tag!=ns+'sectPr']
        canon=lambda e:ET.canonicalize(ET.tostring(e,encoding='unicode'))
        need(len(old)==222 and len(new)==228 and all(canon(a)==canon(b) for a,b in zip(old,new)),'Original report XML prefix differs')
        tables=sum(x.tag==ns+'tbl' for x in old);media=[n for n in original.namelist() if n.startswith('word/media/')]
        need(tables==39 and len(media)==3,'Original report counts differ')
        need(set(original.namelist())==set(edition.namelist()),'DOCX package membership differs')
        changed=[n for n in original.namelist() if original.read(n)!=edition.read(n)]
        need(set(changed)=={'word/document.xml','docProps/core.xml'},'Unexpected report parts changed')
        return dict(source=dict(path=str(source),**file_id(source)),original_body_elements=222,edition_note_elements=6,tables_preserved=39,figures_preserved=3,changed_original_parts=changed)

def scientific_lineage(code):
    coverage=decode(code['INHERITED_LICENSE_COVERAGE.json']);entries=indexed(coverage['files'])
    need(set(entries)=={n for n in code if n.endswith('.py')},'Inherited coverage file list differs')
    catalog_path=Path(coverage['scope_catalog']['path'])
    bound_catalog=catalog_path
    if not equal_id(bound_catalog.read_bytes(),coverage['scope_catalog']):
        bound_catalog=catalog_path.parent/'history/ADOPTED_SCOPE_CATALOG_initial.json'
    need(equal_id(bound_catalog.read_bytes(),coverage['scope_catalog']),'Inherited historical scope catalog differs')
    catalog=load(catalog_path)
    exact=blocks=0
    for n,e in entries.items():
        need(equal_id(code[n],e),'Inherited coverage current identity differs '+n)
        if not n.startswith('payload/'):continue
        for match in e['inherited_matches']:
            scopepath=Path(match['scope_path']);need(equal_id(scopepath.read_bytes(),match['scope_identity']),'Inherited scope identity differs')
            scope=load(scopepath);need(scope['status']=='ADOPTED_PLATFORM_1_0_SCOPED_CODE','Earlier scope is not adopted')
            members={e['path']:e for group in scope['groups'].values() for e in group}
            candidates=[x for x in catalog['entries'] if x['scope_path']==str(scopepath) and x['entry']['path']==match['adopted_path']]
            need(candidates,'Earlier adopted source absent from retained scope catalog')
            prior=Path(candidates[0]['local_path']);data=prior.read_bytes()
            need(equal_id(data,members[match['adopted_path']]),'Earlier source not bound by scope')
            if match['kind']=='exact_file':
                need(equal_id(data,match['identity']) and data==code[n],'Inherited exact source differs');exact+=1
            else:
                need(equal_id(data,match['adopted_identity']),'Inherited block source differs')
                a=code[n].decode().splitlines();b=data.decode().splitlines()
                for block in match['blocks']:
                    selected='\n'.join(a[block['selected_line_start']-1:block['selected_line_start']-1+block['line_count']])
                    adopted='\n'.join(b[block['adopted_line_start']-1:block['adopted_line_start']-1+block['line_count']])
                    need(selected==adopted and hashlib.sha256(selected.encode()).hexdigest()==block['text_sha256'],'Inherited block differs');blocks+=1
    need(exact==1 and blocks==2,'Unexpected scientific inheritance counts')
    return dict(exact_scientific_matches=exact,scientific_expression_blocks=blocks,declared_catalog=coverage['scope_catalog'],bound_catalog=dict(path=str(bound_catalog),**file_id(bound_catalog)),source_location_catalog=dict(path=str(catalog_path),**file_id(catalog_path)))

def preliminary():
    packages=[];current={};scopes={};mapped=0
    for kind in ('Study','Documentation','Code'):
        data,record=read_package(OLD,kind);current[kind]=data;packages.append(record)
        mapped+=inspect_sources(data,OLD)['source_map_entries'];scopes[kind]=inspect_rights(data)
    code=current['Code'];scientific=[n for n in code if n.startswith('payload/') and n.endswith('.py')]
    need(len(scientific)==59,'Expected 59 scientific Python')
    for n in scientific:need(code[n]==(Path(r'C:\Q2\Improvement_Study_v0.6')/n.removeprefix('payload/study/')).read_bytes(),'Scientific source differs from original '+n)
    result=dict(status='PASS_PRELIMINARY_R02',checked_at_utc=now(),packages=packages,assets=[dict(name=p.name,**file_id(p)) for p in sorted((OLD/'dist').iterdir())],source_map_entries_checked=mapped,scopes=scopes,scientific_python_files=59,original_report_preservation=report_preservation(current['Study']),scientific_inheritance=scientific_lineage(code),review_boundary='Independent exact package, source, adoption-scope, report XML/media and inherited-expression audit. Retained delivery manifest hash checked; no full archive scan, report render or scientific experiment rerun.')
    save_exclusive(HERE/'PRELIMINARY_R02_CHECKS.json',result)
    print(json.dumps(dict(status=result['status'],source_map_entries=mapped,scientific_python=59,report_elements=222)))

def helper_lineage(code,oldcode):
    coverage=decode(code['INHERITED_LICENSE_COVERAGE.json']);previous=decode(oldcode['INHERITED_LICENSE_COVERAGE.json'])
    entries=indexed(coverage['files']);old_entries=indexed(previous['files'])
    for n in entries:
        if n.startswith('payload/'):need(entries[n]==old_entries[n],'Historical scientific rights entry changed '+n)
    need(equal_id(Path(coverage['scope_catalog']['path']).read_bytes(),coverage['scope_catalog']),'New current catalog identity is stale')
    history=coverage['previous_scope_catalog']
    need(history['original_record']==previous['scope_catalog'],'Prior scope-catalog identity not retained')
    need(equal_id(Path(history['historical_copy']['path']).read_bytes(),history['historical_copy']),'Historical scope catalog copy differs')
    need(all(history['historical_copy'][k]==previous['scope_catalog'][k] for k in ('bytes','sha256')),'Historical scope catalog binding differs')
    lineage=coverage['package_helper_lineage']
    need({e['path'] for e in lineage}=={'tools/startup_check.py','tools/verify_package.py'},'Helper lineage coverage differs')
    for e in lineage:
        n=e['path'];source=Path(e['source_path']).read_bytes();scope=load(e['scope_record'])
        need(equal_id(code[n],e['current']) and equal_id(source,e['source_identity']),'Helper source/current binding differs')
        need(equal_id(Path(e['scope_record']).read_bytes(),e['scope_record_identity']),'Helper source scope binding differs')
        need(scope['status']=='ADOPTED' and scope['license']==e['license']=='Q-Pathformer Platform License 1.0','Inherited helper scope not adopted')
        need(equal_id(source,next(x for x in scope['files'] if x['path']==n)),'Inherited helper source not scoped')
        match=entries[n]['inherited_matches'];need(len(match)==1 and match[0]['adopted_study']=='v0.5','Helper per-file inherited binding absent')
        match=match[0]
        need(Path(match['source_path']).read_bytes()==source and equal_id(source,match['adopted_identity']),'Helper per-file source identity differs')
        need(equal_id(Path(match['scope_path']).read_bytes(),match['scope_identity']),'Helper per-file scope identity differs')
        if n.endswith('verify_package.py'):need(code[n]==source and match['kind']=='exact_file','Verifier exact reuse claim differs')
        else:
            need(code[n]!=source and match['kind']=='adapted_package_helper','Startup adaptation claim differs')
            need(max(b.size for b in difflib.SequenceMatcher(None,code[n].decode().splitlines(),source.decode().splitlines(),autojunk=False).get_matching_blocks())>20,'Startup adaptation common source not substantiated')
    return lineage

def markdown_links(packages):
    total=0
    for kind,data in packages.items():
        for n,b in data.items():
            if not n.endswith('.md'):continue
            for target in re.findall(r'\[[^\]]*\]\(([^)\s]+)\)',b.decode('utf-8')):
                parsed=urlparse(target.strip('<>'))
                if parsed.scheme or parsed.netloc or not parsed.path:continue
                resolved=posixpath.normpath(posixpath.join(posixpath.dirname(n),unquote(parsed.path)))
                need(resolved in data or any(n.startswith(resolved.rstrip('/')+'/') for n in data),'Broken Markdown link '+kind+'/'+n+' -> '+target);total+=1
    return total

def regression_bindings(code):
    results=load(NEW/'receipts/HELPER_TEST_RESULTS.json');ps=load(NEW/'receipts/POWERSHELL_TEST_RESULTS.json')
    need(results['status']=='PASS_HELPER_REGRESSION_PROBES' and 'not genuine numerical startup evidence' in results['classification'],'Mocked probe evidence misclassified')
    need(ps['status']=='PASS_POWERSHELL_QUICKSTART_CHECKS' and ps['powershell_version'],'PowerShell evidence absent')
    for receipt in (results,ps):
        tested={Path(e['path']).name:e for e in receipt['tested_files']}
        for name in ('startup_check.py','verify_package.py'):
            need(equal_id(code['tools/'+name],tested[name]),'Tested helper differs from selected ZIP')
        need(equal_id(code['QUICKSTART.md'],tested['QUICKSTART.md']),'Tested quickstart differs from selected ZIP')
        for name in ('test_helpers.py','test_powershell.py'):need(equal_id((NEW/'tools'/name).read_bytes(),tested[name]),'Retained test harness differs')
        need(all(e['status']=='PASS' for e in receipt['probes']),'Recorded probe failed')
    probes={p['probe']:p for p in results['probes']}
    required={'duplicate_checksum_path','conflicting_duplicate_checksum_path','duplicate_manifest_path','conflicting_duplicate_manifest_path','manifest_case_collision','unsafe_manifest_path','malformed_manifest_size','malformed_manifest_digest','malformed_manifest_record','checksum_case_collision','malformed_checksum_syntax','duplicate_manifest_json_key','preexisting_receipt_preserved','receipt_reserved_before_child_checks','foreign_receipt_content_preserved','prestartup_integrity_failure_stops_checks','midstartup_integrity_failure','rebound_inventories_do_not_hide_midstartup_change','child_timeout_recorded_as_failure','child_nonzero_recorded_as_failure','child_launch_error_recorded_as_failure'}
    need(required.issubset(probes),'Required helper failure probes absent')
    for component in ('deployment_compiler.py','tests/test_models.py','deployment_checks/test_compiler.py'):
        for variant in ('_consistent_inventory','_original_inventory'):
            need('missing_required_'+component+variant in probes,'Required component rejection probe absent')
    need('reduced_test_suite_rejected' in probes,'Reduced suite failure probe absent')
    for variant in ('False','True'):
        entry=probes['actual_missing_compiler_'+variant]
        need(entry['classification']=='ACTUAL_STARTUP_PROCESS' and entry['returncode']!=0 and entry['result']['status']=='FAIL' and not entry['result']['checks'],'Actual missing-compiler startup failed to reject')
    for mode in ('ordinary','python_O','PYTHONOPTIMIZE_1'):
        for condition in ('valid','changed_same_size','missing','unexpected'):
            p=probes[f'optimization_{mode}_{condition}']
            need(p['classification']=='ACTUAL_VERIFIER_PROCESS' and (p['returncode']==0)==(condition=='valid'),'Optimization probe failed')
            if mode=='python_O':need('-O' in p['command'],'Optimization flag not exercised')
    psprobes={p['probe']:p for p in ps['probes']}
    for name in ('invalid_missing','invalid_changed_same_size','invalid_unexpected'):
        e=psprobes[name];need(e['returncode']!=0 and not e['startup_receipt_created'] and e['package_bytes_unchanged'] and e['classification']=='ACTUAL_POWERSHELL_STOP_BEFORE_STARTUP','PowerShell failed to stop invalid fixture')
    valid=psprobes['valid']
    need(valid['returncode']==0 and valid['startup_receipt_created'] and valid['package_bytes_unchanged'],'PowerShell valid fixture failed')
    need(valid['classification']=='GENUINE_BOUNDED_STARTUP_ON_UNSEALED_DISPOSABLE_HELPER_FIXTURE_NOT_FINAL_ZIP','PowerShell fixture misclassified')
    need(valid['startup_result']['status']=='PASS' and len(valid['startup_result']['checks'])==6 and valid['startup_result']['tests_run']==6,'PowerShell genuine checks absent')
    return dict(helper_probes=len(probes),powershell_probes=len(psprobes),powershell_version=ps['powershell_version'],helper_receipt=dict(path=str(NEW/'receipts/HELPER_TEST_RESULTS.json'),**file_id(NEW/'receipts/HELPER_TEST_RESULTS.json')),powershell_receipt=dict(path=str(NEW/'receipts/POWERSHELL_TEST_RESULTS.json'),**file_id(NEW/'receipts/POWERSHELL_TEST_RESULTS.json')))

def startup_binding(code,packages):
    fresh=load(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    need(fresh['status']=='PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP' and fresh['package_bytes_unchanged'] and fresh['receipt_outside_entire_package'],'Fresh verification absent')
    pmap={p['package']:p for p in packages}
    need({p['package'] for p in fresh['packages']}==set(pmap),'Fresh package list differs')
    for p in fresh['packages']:
        for key in ('zip','seal'):need(p[key]==pmap[p['package']][key],'Fresh asset binding differs')
    for key in ('code_zip','code_seal','code_startup_receipt'):
        e=fresh[key];need(equal_id(Path(e['path']).read_bytes(),e),'Fresh bound identity differs '+key)
    receipt=Path(fresh['code_startup_receipt']['path']);need(not receipt.is_relative_to(NEW/'qa/fresh_extraction'),'Startup receipt inside extraction')
    startup=load(receipt)
    need(startup['status']=='PASS' and not startup['errors'] and startup['package_bytes_unchanged'],'Final startup failed')
    need(len(startup['checks'])==6 and startup['tests_run']==6 and startup['parsed_python_files']==61 and startup['model_methods_checked']==6,'Final startup scope differs')
    need(startup['numpy_version'] and startup['scipy_version'] and len(set(startup['methods']))==6,'Final runtime/recipe inventory absent')
    for e in startup['checks']:
        need(e['status']=='PASS' and e['returncode']==0 and '-B' in e['command'] and 'MOCK' not in json.dumps(e),'Final check is not genuine bounded PASS')
    commands=' '.join(' '.join(e['command']) for e in startup['checks'])
    need('test_shapes_and_paired_initial_predictions' in commands and 'test_moments_and_state_against_independent_matrices' in commands,'Wrong selected tests')
    expected={'test_models.ModelTests.test_shapes_and_paired_initial_predictions','test_models.ModelTests.test_moments_and_state_against_independent_matrices','test_compiler.CompilerTests.test_orthogonal_period_two_nodes','test_compiler.CompilerTests.test_both_heads_off_grid_and_forced_banks','test_compiler.CompilerTests.test_constant_logits_and_invalid_contracts','test_compiler.CompilerTests.test_learned_trig_uses_identical_coefficient_kernel'}
    need({e['test_id'] for e in startup['checks']}==expected,'Six required test identities differ')
    for e in startup['checks']:
        observation=decode(e['stdout'])
        need(observation['tests_run']==1 and observation['test_id']==e['test_id'],'Child test observation differs')
    need('v0.6' in startup['scope'] and 'CLI help' not in startup['scope'],'Irrelevant startup scope remains')
    fingerprint=hashlib.sha256(json.dumps({n:identity(b) for n,b in code.items()},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for key in ('integrity_before','integrity_after'):
        e=startup[key];need(e['status']=='PASS' and e['files']==len(code) and e['package_fingerprint_sha256']==fingerprint,'Startup extracted-package fingerprint differs')
    extracted=NEW/'qa/fresh_extraction/QPathformer_v0.6_Code'
    need({p.relative_to(extracted).as_posix():p.read_bytes() for p in extracted.rglob('*') if p.is_file()}==code,'Final extraction differs from Code ZIP')
    invocation=load(NEW/'receipts/STARTUP_INVOCATION.json')
    need(invocation['returncode']==0 and Path(invocation['command'][2])==extracted/'tools/startup_check.py','Wrong final startup invocation')
    return dict(binding=dict(path=str(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**file_id(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')),checks=6,tests_run=6,parsed_python_files=61,model_methods_checked=6,numpy_version=startup['numpy_version'],scipy_version=startup['scipy_version'],fingerprint_matches_sealed_code=True)

def main():
    need(not OUT.exists(),'Preserve existing audit receipt')
    preliminary=load(HERE/'PRELIMINARY_R02_CHECKS.json')
    for e in preliminary['assets']:need(equal_id((OLD/'dist'/e['name']).read_bytes(),e),'Old sealed asset changed')
    packages=[];current={};previous={};changes={};scopes={};source_counts={}
    for kind in ('Study','Documentation','Code'):
        old,_=read_package(OLD,kind);data,record=read_package(NEW,kind)
        need(set(data)==set(old),'Package membership changed '+kind)
        current[kind]=data;previous[kind]=old;packages.append(record)
        changes[kind]=[n for n in sorted(data) if data[n]!=old[n]]
        for n in data:
            if n.startswith(('payload/','reports/','historical/','provenance/')) and n!='provenance/SOURCE_MAP.json':need(data[n]==old[n],'Preserved scientific/historical/report material changed '+kind+'/'+n)
        source_counts[kind]=inspect_sources(data,NEW);scopes[kind]=inspect_rights(data,old)
    code=current['Code'];oldcode=previous['Code'];science=[n for n in code if n.startswith('payload/') and n.endswith('.py')]
    need(len(science)==59 and len([n for n in code if n.endswith('.py')])==61,'Python selection differs')
    for n in science:need(code[n]==(Path(r'C:\Q2\Improvement_Study_v0.6')/n.removeprefix('payload/study/')).read_bytes(),'Scientific source differs from original')
    need(current['Study']['REPORT_LICENSE_SCOPE.json']==previous['Study']['REPORT_LICENSE_SCOPE.json'],'Unchanged report scope unnecessarily altered')
    for n in ('startup_check.py','verify_package.py'):
        need(code['tools/'+n]==(HELPERS/n).read_bytes() and code['tools/'+n]!=oldcode['tools/'+n],'Corrected helper differs from tested staging')
    need(not any(isinstance(x,ast.Assert) for x in ast.walk(ast.parse(code['tools/verify_package.py']))),'Verifier still relies on removable assertions')
    quick=code['QUICKSTART.md'].decode();need(quick.count('$LASTEXITCODE -ne 0')==2 and 'throw ' in quick and 'v0.6' in quick,'Quickstart failure handling or scope differs')
    need('seal' in quick.lower() and 'extract' in quick.lower(),'External seal/extraction boundary missing')
    actual_imports={}
    for n,b in code.items():
        if not n.endswith('.py'):continue
        for node in ast.walk(ast.parse(b,filename=n)):
            names=[x.name.split('.')[0] for x in node.names] if isinstance(node,ast.Import) else ([node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module and node.level==0 else [])
            for name in names:actual_imports.setdefault(name,set()).add(n)
    dep=decode(code['DEPENDENCY_INVENTORY.json'])
    need('qiskit_ibm_runtime' in dep['optional_scientific'],'Optional historical simulator dependency omitted')
    need({k:set(v) for k,v in dep['direct_import_inventory'].items()}==actual_imports,'Direct dependency import inventory differs')
    need(set(dep['observed_import_roots'])==set(actual_imports),'Observed import roots do not describe direct Python coverage')
    embedded=dep['embedded_startup_import_roots']
    need(embedded['path']=='tools/startup_check.py' and set(embedded['roots'])==set('json socket sys unittest numpy scipy circuits models routers study verification test_models deployment_compiler test_compiler'.split()),'Embedded child-program imports absent')
    inherited=scientific_lineage(code);helpers=helper_lineage(code,oldcode)
    report=report_preservation(current['Study']);local_links=markdown_links(current)
    need((NEW/'INVENTORY.json').read_bytes()==(OLD/'INVENTORY.json').read_bytes(),'Retained original inventory changed')
    source_receipt=load(NEW/'receipts/SOURCE_INVENTORY.json');need(source_receipt,'New source inventory wrapper absent')
    regressions=regression_bindings(code);startup=startup_binding(code,packages)
    body=(NEW/'RELEASE_NOTES.md').read_text('utf-8');guide=current['Documentation']['RESEARCH_GUIDE.md'].decode()
    need('clipped BCE' in body and 'Multi' in body and 'Scalar' in body and 'mean' in body and 'draft' in body.lower() and 'v0.9.5' in body,'Release wording lacks required metric/attribution/status')
    for value in ('99.6875','10,000','6,400','983,040','265,420,800','15,000'):
        need(value in guide,'Research guide accounting/inference detail absent '+value)
    need('7.16e-15' in guide and '6.39e-14' in guide and '1,000' in guide,'Conversion qualifications absent')
    sys.path.insert(0,str(HERE.parent));import batch
    baseline=load(NEW/'receipts/REMOTE_BASELINE_V06_REVISION.json')
    releases=batch.api(f'repos/{batch.NAME}/releases?per_page=100')
    need({r['id']:batch.signature(r) for r in releases if r['id']!=427653047}=={r['id']:batch.signature(r) for r in baseline['releases'] if r['id']!=427653047},'Another release changed')
    need(batch.api(f'repos/{batch.NAME}/git/matching-refs/tags')==baseline['tags'],'Existing tags changed')
    need(batch.api(f'repos/{batch.NAME}/releases/latest')['id']==427547832 and batch.api(f'repositories/{batch.REPO_ID}')['private'],'Latest/private state differs')
    need(batch.api(f'repos/{batch.NAME}/commits/main')['sha']==batch.EXPECTED_BASE,'Main differs')
    need(next(r for r in releases if r['id']==427653047)['draft'],'v0.6 unexpectedly published')
    result=dict(schema='qpath-independent-successor-audit-1',status='PASS',checked_at_utc=now(),study_version='v0.6',actual_build_root=str(NEW),packages=packages,scopes=scopes,source_map_counts=source_counts,source_map_entries_checked=sum(e['source_map_entries'] for e in source_counts.values()),scientific_python_files_unchanged=59,scientific_payload_and_historical_records_unchanged=True,reports_unchanged=[dict(path=n,**identity(b)) for n,b in current['Study'].items() if n.startswith('reports/')],original_report_preservation=report,canonical_licences_and_adoption_decisions_unchanged=True,adoption_scope_identity_bindings_refreshed=True,scientific_inheritance=inherited,package_helper_lineage=helpers,dependency_module_file_pairs=sum(map(len,actual_imports.values())),active_local_markdown_links_checked=local_links,regression_evidence=regressions,final_startup=startup,changed_package_files=changes,prior_sealed_evidence_preserved=True,repository_private=True,v095_latest=True,v05_and_other_releases_unchanged=True,v06_still_draft=True,preliminary_binding=dict(path=str(HERE/'PRELIMINARY_R02_CHECKS.json'),**file_id(HERE/'PRELIMINARY_R02_CHECKS.json')),review_boundary='Separate exact package/inventory/source/scope/adoption/lineage audit algorithm executed by the same agent as preparation, not a second reviewer and binding of separately performed helper, PowerShell and genuine final startup checks. Original DOCX structural/body/table/media preservation verified. No report rerender, full archive replay, training, scoring, sampling or QPU work performed.')
    save_exclusive(OUT,result)
    print(json.dumps(dict(status='PASS',receipt=str(OUT),source_map_entries=result['source_map_entries_checked'],scientific_python=59,helper_probes=regressions['helper_probes'],powershell_probes=regressions['powershell_probes'],genuine_checks=6)))

if __name__=='__main__':globals()[sys.argv[1]]()
