"""Separate v0.7 package audit algorithm, run by the preparing agent."""
from pathlib import Path
from datetime import datetime,timezone
import ast,base64,hashlib,io,json,re,sys,zipfile
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import batch
BASE=batch.BASE;OLD=BASE/'study-v0.7/draft_20261029_r2';NEW=BASE/'study-v0.7/draft_20261030_r3'
HELPERS=HERE.parent/'v07_r3_helpers'
need,info,save=batch.need,batch.info,batch.save
def ident(data):return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def matches(data,e):return all(ident(data)[k]==e[k] for k in ('bytes','sha256'))
def unique(pairs):
    out={}
    for k,v in pairs:need(k not in out,'Duplicate JSON key '+k);out[k]=v
    return out
def decode(b):return json.loads(b,object_pairs_hook=unique)
def load(p):return decode(p.read_bytes())
def archive(folder,kind):
    name='QPathformer_v0.7_'+kind;zp=folder/'dist'/(name+'.zip');sp=zp.with_suffix('.seal.json');s=load(sp)
    result=batch.verify_package(zp,sp)
    need(s['schema']=='qpath-package-seal-1' and s['package']==name and s['expected_root']==name,'Unexpected seal schema')
    origin=OLD if folder==OLD or kind=='Study' else NEW
    need(s['actual_build_root']==str(origin) and s['actual_assembly_root']==str(origin/'assembly'/name),'Incorrect actual build origin')
    with zipfile.ZipFile(zp) as z:data={n[len(name)+1:]:z.read(n) for n in z.namelist()}
    for n,b in data.items():
        if n.endswith('.json'):decode(b)
    mf=decode(data['MANIFEST.json'])['files'];need(len(mf)==len({e['path'].casefold() for e in mf}),'Manifest case collision')
    for key in ('internal_manifest','internal_checksums','source_map'):need(s[key]['path'].startswith(name+'/'),'Seal path is not fully prefixed')
    return data,result
def sources(data,origin):
    m=decode(data['SOURCE_MAP.json']);need(m['actual_build_root']==str(origin),'Source-map origin differs')
    entries=m['files'];need(len(entries)==len({e['path'] for e in entries}),'Duplicate source mapping')
    need({e['path'] for e in entries}==set(data)-{'SOURCE_MAP.json','MANIFEST.json','CHECKSUMS.sha256'},'Incomplete source mapping')
    for e in entries:
        need(matches(data[e['path']],e['output_identity']),'Mapped output differs')
        if e['source_path']:need(matches(Path(e['source_path']).read_bytes(),e['source_identity']),'Mapped source differs')
    need(matches(Path(m['source_delivery_manifest']['path']).read_bytes(),m['source_delivery_manifest']),'Delivery manifest differs')
    return len(entries)
def rights(data,previous=None):
    scopes={n:decode(b) for n,b in data.items() if '/' not in n and n.endswith('_LICENSE_SCOPE.json')}
    for n,s in scopes.items():
        need(s['status']=='ADOPTED' and s['licensor']=='Anthony Siljeg','Scope not adopted')
        need(len(s['files'])==len({e['path'] for e in s['files']}),'Duplicate scope path')
        for e in s['files']:need(matches(data[e['path']],e),'Scope identity differs')
        if previous:
            p=decode(previous[n]);need({k:v for k,v in s.items() if k!='files'}=={k:v for k,v in p.items() if k!='files'},'Scope terms changed')
            need({e['path'] for e in s['files']}=={e['path'] for e in p['files']},'Scope expanded')
    a=decode(data['LICENSE_ADOPTION.json']);need({e['path'] for e in a['satisfied_by']}==set(scopes),'Adoption scope membership differs')
    for e in a['satisfied_by']:need(matches(data[e['path']],e),'Adoption identity binding differs')
    if previous:
        p=decode(previous['LICENSE_ADOPTION.json']);need({k:v for k,v in a.items() if k!='satisfied_by'}=={k:v for k,v in p.items() if k!='satisfied_by'},'Adoption decision changed')
    return {n:len(s['files']) for n,s in scopes.items()}
def lineage(code):
    m=decode(code['INHERITED_LICENSE_MAP.json']);blocks=0
    for e in m['exact_file_matches']+m['shared_expression_matches']:
        need(matches(code[e['path']],e),'Inherited current identity differs')
        scopepath=Path(e['scope_record']);need(matches(scopepath.read_bytes(),e['scope_identity']),'Inherited scope differs')
        scope=load(scopepath);members={x['path']:x for group in scope['groups'].values() for x in group}
        catalog=load(batch.B/'ADOPTED_SCOPE_CATALOG.json')
        candidates=[x for x in catalog['entries'] if x['scope_path']==str(scopepath) and x['entry']['path']==e['adopted_path']]
        need(candidates,'Earlier source location absent from scope catalog')
        prior=Path(candidates[0]['local_path']).read_bytes();need(matches(prior,members[e['adopted_path']]),'Earlier source not bound to adopted scope')
        if 'matching_blocks' not in e:need(prior==code[e['path']],'Earlier exact match differs')
        else:
            need(hashlib.sha256(prior).hexdigest()==e['adopted_sha256'],'Earlier shared source differs')
            old=prior.decode('utf-8-sig').replace('\r\n','\n').splitlines(keepends=True);current=code[e['path']].decode('utf-8-sig').replace('\r\n','\n').splitlines(keepends=True)
            for block in e['matching_blocks']:
                a=''.join(old[block['adopted_line_start']-1:block['adopted_line_start']-1+block['line_count']]).encode()
                b=''.join(current[block['selected_line_start']-1:block['selected_line_start']-1+block['line_count']]).encode()
                need(a==b and len(b)==block['utf8_bytes'] and hashlib.sha256(b).hexdigest()==block['sha256'],'Shared-expression block differs');blocks+=1
    need(len(m['exact_file_matches'])==5 and blocks==9,'Scientific inheritance counts differ')
    return dict(exact_scientific_matches=5,shared_expression_blocks=9)
def preservation(study):
    original=Path(r'C:\Q2\Improvement_Study_v0.7\docs\QPATH_RPT008_v0.7_Internal_Study_Report.docx')
    packaged=study['reports/QPathformer_v0.7_Report_Edition_1.docx']
    with zipfile.ZipFile(original) as a,zipfile.ZipFile(io.BytesIO(packaged)) as b:
        ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        old=[e for e in ET.fromstring(a.read('word/document.xml')).find(ns+'body') if e.tag!=ns+'sectPr'];new=[e for e in ET.fromstring(b.read('word/document.xml')).find(ns+'body') if e.tag!=ns+'sectPr']
        canon=lambda e:ET.canonicalize(ET.tostring(e,encoding='unicode'))
        need(len(old)==295 and len(new)==302 and all(canon(x)==canon(y) for x,y in zip(old,new)),'Report body preservation differs')
        need(sum(e.tag==ns+'tbl' for e in old)==58,'Report table count differs')
        media=[n for n in a.namelist() if n.startswith('word/media/')];need(len(media)==4 and all(a.read(n)==b.read(n) for n in media),'Figures differ')
        need(set(a.namelist())==set(b.namelist()) and {n for n in a.namelist() if a.read(n)!=b.read(n)}=={'word/document.xml','docProps/core.xml'},'Unexpected report parts changed')
    return dict(original=dict(path=str(original),**info(original)),original_body_elements=295,edition_elements=7,tables=58,figures=4,packaged_docx=ident(packaged),packaged_pdf=ident(study['reports/QPathformer_v0.7_Report_Edition_1.pdf']))
def preliminary():
    import v07_r3 as pipeline
    need(not (HERE/'PRELIMINARY_R2_CHECKS.json').exists(),'Preliminary receipt exists')
    state=pipeline.capture();pipeline.check_state(state)
    folder=HERE/'authenticated_predecessor';folder.mkdir(exist_ok=True)
    r=next(r for r in state['releases'] if r['id']==pipeline.RELEASE_ID);assets=[]
    notes=pipeline.NOTES.read_text('utf-8')
    for a in r['assets']:
        data=batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','-H','Accept: application/octet-stream',timeout=180)
        need(ident(data)==info(OLD/'dist'/a['name']) and ident(data)['sha256'] in notes,'Reviewed attachment differs')
        cached=folder/a['name']
        if cached.exists():need(cached.read_bytes()==data,'Preserve earlier download evidence')
        else:cached.write_bytes(data)
        assets.append(dict(name=a['name'],id=a['id'],**ident(data)))
    records=[];current={};counts={}
    for kind in ('Code','Documentation','Study'):
        data,e=archive(OLD,kind);current[kind]=data;records.append(e);counts[kind]=sources(data,OLD);rights(data)
    scientific=[n for n in current['Code'] if n.startswith('payload/') and n.endswith('.py')];need(len(scientific)==50,'Scientific selection count differs')
    for n in scientific:need(current['Code'][n]==(Path(r'C:\Q2\Improvement_Study_v0.7')/n.removeprefix('payload/study/')).read_bytes(),'Scientific source differs')
    links=[]
    for sha,path in re.findall(r'https://github\.com/'+re.escape(batch.NAME)+r'/blob/([0-9a-f]{40})/([^\s)]+)',r['body']):
        got=batch.api(f'repos/{batch.NAME}/contents/{path}?ref={sha}');need(base64.b64decode(got['content'])==(batch.R/path).read_bytes(),'Prior evidence link differs');links.append(dict(commit=sha,path=path))
    save(HERE/'PRELIMINARY_R2_CHECKS.json',dict(status='PASS',checked_at_utc=batch.now(),assets=assets,packages=records,source_map_entries=counts,scientific_python=50,report=preservation(current['Study']),lineage=lineage(current['Code']),authenticated_evidence_links=links,private=True,latest='study-v0.9.5'))
    print(json.dumps(dict(status='PASS_PRELIMINARY',assets=len(assets),source_entries=sum(counts.values()),scientific_python=50)))
def main():
    need(not (NEW/'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json').exists(),'Audit already exists')
    current={};records=[];changed={};scopes={};counts={}
    for kind in ('Code','Documentation','Study'):
        old,_=archive(OLD,kind);data,e=archive(NEW,kind);current[kind]=data;records.append(e);need(set(old)==set(data),'Package members changed')
        if kind=='Study':need(data==old and info(NEW/'dist'/('QPathformer_v0.7_'+kind+'.zip'))==info(OLD/'dist'/('QPathformer_v0.7_'+kind+'.zip')),'Study bytes changed')
        for n,b in old.items():
            if n.startswith(('payload/','source/','reports/','provenance/','LICENSES/')):need(b==data[n],'Preserved material changed '+n)
        scopes[kind]=rights(data,old);counts[kind]=sources(data,OLD if kind=='Study' else NEW)
        changed[kind]=[n for n in data if data[n]!=old[n]]
    code=current['Code'];need(len([n for n in code if n.endswith('.py')])==52,'Python count differs')
    oldcode,_=archive(OLD,'Code');m=decode(code['INHERITED_LICENSE_MAP.json']);oldm=decode(oldcode['INHERITED_LICENSE_MAP.json'])
    need({k:v for k,v in m.items() if k!='package_helper_lineage'}==oldm,'Earlier scientific grants changed')
    for e in m['package_helper_lineage']:
        need(matches(code[e['path']],e['current']) and matches(Path(e['source_path']).read_bytes(),e['source_identity']),'Helper lineage differs')
        scope=load(Path(e['scope_record']));need(matches(Path(e['scope_record']).read_bytes(),e['scope_record_identity']),'Helper scope differs')
        need(matches(Path(e['source_path']).read_bytes(),next(x for x in scope['files'] if x['path']==e['path'])),'Prior helper not scoped')
    for helper in ('startup_check.py','verify_package.py'):
        need(code['tools/'+helper]==(HELPERS/helper).read_bytes(),'Selected helper differs')
        need(not any(isinstance(x,ast.Assert) for x in ast.walk(ast.parse(code['tools/'+helper]))),'Removable helper assertion')
    imports={}
    for n,b in code.items():
        if n.endswith('.py'):
            for node in ast.walk(ast.parse(b)):
                names=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else ([node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module and node.level==0 else [])
                for name in names:imports.setdefault(name,set()).add(n)
    dep=decode(code['DEPENDENCY_INVENTORY.json']);need({k:set(v) for k,v in dep['direct_import_inventory'].items()}==imports and set(dep['all_import_roots'])==set(imports),'Direct imports differ')
    probes=load(NEW/'receipts/HELPER_TEST_RESULTS.json');ps=load(NEW/'receipts/POWERSHELL_TEST_RESULTS.json')
    for receipt in (probes,ps):
        need(all(e['status']=='PASS' for e in receipt['probes']),'Failure probe recorded')
        for e in receipt['tested_files']:need(matches((HELPERS/Path(e['path']).name).read_bytes(),e),'Tested helper/harness changed')
    tests={e['probe']:e for e in probes['probes']}
    for mode in ('ordinary','python_O','PYTHONOPTIMIZE_1'):
        for condition in ('valid','changed_payload','missing_launcher','failing_cli','missing_help'):
            e=tests['startup_'+mode+'_'+condition];need((e['returncode']==0)==(condition=='valid'),'Actual startup-mode probe differs')
    fresh=load(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    for key in ('code_zip','code_seal','code_startup_receipt'):need(matches(Path(fresh[key]['path']).read_bytes(),fresh[key]),'Fresh binding differs')
    startup=load(Path(fresh['code_startup_receipt']['path']));need(startup['status']=='PASS' and startup['parsed_python_files']==52 and startup['cli_help_checks']==3 and startup['numerical_input_records']==2 and len(startup['checks'])==4 and not startup['errors'],'Startup scope differs')
    need(startup['package_bytes_unchanged'] and all(e['returncode']==0 and e['status']=='PASS' for e in startup['checks']),'Startup failure details present')
    fingerprint=hashlib.sha256(json.dumps({n:ident(b) for n,b in code.items()},sort_keys=True,separators=(',',':')).encode()).hexdigest();need(startup['integrity_after']['package_fingerprint_sha256']==fingerprint,'Startup fingerprint differs')
    clarify=load(NEW/'report/VISUAL_REVIEW_CLARIFICATION.json');need(clarify['report_pdf']==ident(current['Study']['reports/QPathformer_v0.7_Report_Edition_1.pdf']),'Clarification PDF binding differs')
    need(clarify['study_zip']==info(NEW/'dist/QPathformer_v0.7_Study.zip') and clarify['study_seal']==info(NEW/'dist/QPathformer_v0.7_Study.seal.json'),'Clarification asset binding differs')
    import v07_r3 as pipeline;pipeline.guard_other_releases()
    save(NEW/'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json',dict(status='PASS',checked_at_utc=batch.now(),reviewer='Separate algorithm run by the preparing agent; not a second reviewer',packages=records,scopes=scopes,source_map_counts=counts,changed_files=changed,scientific_python_files_unchanged=50,report=preservation(current['Study']),inherited_scientific_grants=lineage(code),study_assets_unchanged=True,adoption_decisions_and_legal_texts_unchanged=True,helper_probes=len(probes['probes']),powershell_probes=len(ps['probes']),startup_checks=4,cli_help_checks=3,numerical_inputs=2,parsed_python_files=52,repository_private=True,v095_latest=True,v07_still_draft=True,boundary='Exact package/source/scope/report structure and fresh-check bindings. Page 37 separately checked for the disclosure clarification; no new all-page review or scientific experiments.'))
    print(json.dumps(dict(status='PASS',helper_probes=len(probes['probes']),powershell_probes=len(ps['probes']),startup_checks=4,scientific_python_unchanged=50,study_assets_reused=2)))
if __name__=='__main__':globals()[sys.argv[1]]()
