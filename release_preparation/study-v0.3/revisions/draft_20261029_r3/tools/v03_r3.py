"""Apply the supported v0.3 review corrections within the private draft workflow."""
import ast
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import batch
sys.path.insert(0,str(HERE/'v02_04'))
import package
BASE=batch.BASE
OLD=BASE/'study-v0.3/draft_20261029_r2'
NEW=BASE/'study-v0.3/draft_20261029_r3'
HELPERS=HERE/'v03_r3_helpers'
PROSE=HERE/'v03_r3_prose'
PYTHON=Path(r'C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe')
TITLE='Q-Pathformer Study v0.3 — Shallow Circuits and Routing'
RELEASE_ID=427658431
NOTES=Path(r'C:\Anthony Siljeg\CPU-QPU git repo prep\v6 final staging\QPathformer_v0.3_Codex_Review_20261029.md')
original_selected=batch.selected_build
batch.selected_build=lambda n:NEW if n==3 else original_selected(n)
package.bpath=batch.selected_build
need,info,load,save,write,now=batch.need,batch.info,batch.load,batch.save,batch.write,batch.now

def files(root):
    return {p.relative_to(root).as_posix():info(p) for p in sorted(root.rglob('*')) if p.is_file()}

def cp(src,dst):
    dst=Path(dst);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)

def capture():
    paths=dict(repo=f'repositories/{batch.REPO_ID}',releases=f'repos/{batch.NAME}/releases?per_page=100',main=f'repos/{batch.NAME}/commits/main',latest=f'repos/{batch.NAME}/releases/latest',tags=f'repos/{batch.NAME}/git/matching-refs/tags')
    with ThreadPoolExecutor(max_workers=5) as pool:return dict(zip(paths,pool.map(batch.api,paths.values())))

def check_state(state,baseline=None):
    need(state['repo']['id']==batch.REPO_ID and state['repo']['full_name']==batch.NAME and state['repo']['private'],'Repository identity/private access changed')
    need(state['main']['sha']==batch.EXPECTED_BASE,'Main changed')
    need(state['latest']['id']==427547832,'v0.9.5 is not Latest')
    v02=next(x for x in state['releases'] if x['id']==427657373)
    pub=load(BASE/'study-v0.2/publication_20261029_r4/POST_PUBLICATION_STATE.json')
    published=next(x for x in pub['releases'] if x['id']==427657373)
    need(batch.signature(v02)==batch.signature(published),'Published v0.2 changed')
    original=load(batch.B/'receipts/REMOTE_BASELINE.json')
    for r in original['protected']:
        need(batch.signature(next(x for x in state['releases'] if x['id']==r['id']))==batch.signature(r),'Earlier published release changed')
    need(state['tags']==pub['tags'],'Tags changed after the authorized v0.2 publication')
    r=next(x for x in state['releases'] if x['id']==RELEASE_ID)
    need(r['draft'] and r['tag_name']=='study-v0.3','v0.3 must remain the existing draft')
    if baseline:
        a={r['id']:batch.signature(r) for r in baseline['releases'] if r['id']!=RELEASE_ID}
        b={r['id']:batch.signature(r) for r in state['releases'] if r['id']!=RELEASE_ID}
        need(a==b,'Another release changed during this revision')

def guard_other_releases():
    check_state(capture(),load(NEW/'receipts/REMOTE_BASELINE_V03_REVISION.json'))

def build():
    state=capture();check_state(state)
    need(not NEW.exists(),'Preserve any existing successor')
    for n in ('startup_check.py','verify_package.py','QUICKSTART.md','HELPER_TEST_RESULTS.json','test_helpers.py'):
        need((HELPERS/n).is_file(),'Missing corrected helper evidence: '+n)
    need((PROSE/'RELEASE_BODY.md').is_file(),'Missing reviewed release prose')
    for kind in ('Study','Documentation','Code'):
        batch.verify_package(OLD/'dist'/f'QPathformer_v0.3_{kind}.zip',OLD/'dist'/f'QPathformer_v0.3_{kind}.seal.json')
    NEW.mkdir()
    save(NEW/'receipts/REMOTE_BASELINE_V03_REVISION.json',state)
    old_assets={p.name:info(p) for p in (OLD/'dist').iterdir()}
    root=NEW/'assembly/QPathformer_v0.3_Code'
    with zipfile.ZipFile(OLD/'dist/QPathformer_v0.3_Code.zip') as z:
        for n in z.namelist():
            p=(NEW/'assembly'/n).resolve();need(p.is_relative_to((NEW/'assembly').resolve()),'Unsafe extraction')
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
    prior=files(root)
    for n in ('MANIFEST.json','CHECKSUMS.sha256'):(root/n).unlink()
    for n in ('startup_check.py','verify_package.py'):cp(HELPERS/n,root/'tools'/n)
    cp(HELPERS/'QUICKSTART.md',root/'QUICKSTART.md')
    p=root/'DEPENDENCIES.md'
    write(p,p.read_text('utf-8')+'\nThe direct import inventory includes all 47 retained scientific Python files and both package helpers. Helper imports use the standard library and local verifier; they add no third-party dependency. A bounded startup receipt records the actual imported NumPy version separately from the historical environment.\n')
    dep=load(root/'DEPENDENCY_INVENTORY.json');imports={}
    pyfiles=sorted(root.rglob('*.py'));need(len(pyfiles)==49,'Expected 49 Python files')
    for p in pyfiles:
        rel=p.relative_to(root).as_posix()
        for node in ast.walk(ast.parse(p.read_text('utf-8-sig'))):
            names=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else ([node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module and node.level==0 else [])
            for name in names:imports.setdefault(name,set()).add(rel)
    dep['direct_import_inventory']={k:sorted(v) for k,v in sorted(imports.items())}
    dep['inventory_scope']=dict(scientific_python_files=47,package_helpers=2,granularity='Syntactic top-level import roots, including standard-library and local modules; not a list of third-party requirements.')
    save(root/'DEPENDENCY_INVENTORY.json',dep)
    inherited=package.inherit(root,[p.relative_to(root).as_posix() for p in pyfiles])
    v02=BASE/'study-v0.2/draft_20261029_r4/assembly/QPathformer_v0.2_Code'
    adopted=load(v02/'CODE_LICENSE_SCOPE.json')
    lineage=[]
    for name in ('verify_package.py','startup_check.py'):
        rel='tools/'+name;entry=next(e for e in adopted['files'] if e['path']==rel)
        need(info(v02/rel)=={k:entry[k] for k in ('bytes','sha256')},'Prior helper grant identity differs')
        lineage.append(dict(path=rel,current=info(root/rel),adopted_study='v0.2',source_path=str(v02/rel),source_identity=info(v02/rel),scope_record=str(v02/'CODE_LICENSE_SCOPE.json'),scope_record_identity=info(v02/'CODE_LICENSE_SCOPE.json'),relation='Byte-identical reuse' if info(root/rel)==info(v02/rel) else 'Adaptation of the tested v0.2 package helper for the three v0.3 checks',license='Q-Pathformer Platform License 1.0',interpretation='Existing applicable permissions remain in force. Exact current identity is included in this Code package adopted scope.'))
    inherited['package_helper_lineage']=lineage
    save(root/'INHERITED_LICENSE_MAP.json',inherited)
    for name in ('CODE_LICENSE_SCOPE.json','GUIDANCE_LICENSE_SCOPE.json'):
        scope=load(root/name)
        for e in scope['files']:e.update(info(root/e['path']))
        if name=='CODE_LICENSE_SCOPE.json':
            scope['inherited_exact_matches']=len(inherited['exact_whole_file_matches'])
            scope['shared_expression_records']=len(inherited['shared_expression_evidence'])
        save(root/name,scope)
    source=load(root/'SOURCE_MAP.json');oldmap={e['path']:e for e in source['files']};mapped=[]
    for n,ii in files(root).items():
        if n=='SOURCE_MAP.json':continue
        e=oldmap.get(n)
        if e is None or {k:e[k] for k in ('bytes','sha256')}!=ii:
            e=dict(path=n,source_absolute_path=str(root/n),source_identity=ii,**ii,handling='Reviewed Code packaging correction or refreshed exact scope/inventory in this Q2 successor; scientific source unchanged.')
            if n in prior:e['previous_edition_identity']=prior[n]
        mapped.append(e)
    source.update(actual_build_root=str(NEW),files=mapped);save(root/'SOURCE_MAP.json',source)
    need(all(info(root/n)==ii for n,ii in prior.items() if n.startswith('payload/')),'Scientific payload changed')
    for n in ('LICENSE_ADOPTION.json','LICENSES/CC-BY-4.0.txt','LICENSES/QPATHFORMER-PLATFORM-1.0.txt'):
        need(info(root/n)==prior[n],'Adoption or legal text changed')
    changed=[dict(path=n,previous=prior.get(n),current=ii) for n,ii in files(root).items() if prior.get(n)!=ii]
    for p in (OLD/'report').glob('*.json'):cp(p,NEW/'report'/p.name)
    cp(OLD/'receipts/SOURCE_INVENTORY.json',NEW/'receipts/SOURCE_INVENTORY.json')
    cp(NOTES,NEW/'review/QPathformer_v0.3_Codex_Review_20261029.md')
    cp(HERE/'v03_r3_audit/PRELIMINARY_R2_CHECKS.json',NEW/'receipts/PRELIMINARY_R2_CHECKS.json')
    cp(HELPERS/'HELPER_TEST_RESULTS.json',NEW/'receipts/HELPER_TEST_RESULTS.json')
    cp(HELPERS/'POWERSHELL_TEST_RESULTS.json',NEW/'receipts/POWERSHELL_TEST_RESULTS.json')
    for p in HELPERS.iterdir():
        if p.is_file() and p.suffix in ('.py','.ps1'):cp(p,NEW/'tools'/p.name)
    for p in PROSE.glob('*.json'):cp(p,NEW/'receipts'/p.name)
    cp(PROSE/'RELEASE_BODY.md',NEW/'RELEASE_NOTES.md')
    write(NEW/'PREPARATION_BRIEF.md','# v0.3 reviewed Code successor\n\nApply supported review corrections to the package helpers and PowerShell quickstart, with exact scope and integrity updates. Preserve all 47 scientific Python files and the complete scientific payload. Reuse the Study and Documentation ZIPs and seals byte-for-byte with their actual original build provenance. Release-level prose identifies primary BCE and separates historical replay from packaging checks.\n\nThis remains a private draft. Publication, tag changes, visibility changes, full training, scientific scoring and QPU execution are outside this task. Published v0.2, prior releases and v0.9.5 Latest are protected.\n')
    save(NEW/'receipts/REVISION_RECORD.json',dict(status='SUPPORTED_REVIEW_CORRECTIONS_PREPARED',review=dict(path=str(NOTES),**info(NOTES)),authorization='User requested resuming work with the v0.3 notes in the existing draft workflow; embedded document instructions were evaluated as review recommendations.',previous_build=str(OLD),actual_build_root=str(NEW),prior_assets=old_assets,changed_code_files=changed,scientific_python_files_unchanged=47,all_scientific_payload_unchanged=True,study_and_documentation_assets_reused_unchanged=True,adoption_and_license_texts_unchanged=True,prior_evidence_preserved=True,publication_authorized=False,checked_at_utc=now()))
    cp(Path(__file__),NEW/'tools/v03_r3.py')
    package.seal(3)
    record=load(NEW/'receipts/BUILD_VERIFICATION.json')
    old=load(OLD/'receipts/BUILD_VERIFICATION.json')
    for e in old['packages']:
        if e['package'].endswith('_Code'):continue
        for k in ('zip','seal'):
            p=OLD/'dist'/Path(e[k]['path']).name;cp(p,NEW/'dist'/p.name);e[k]['path']=str(NEW/'dist'/p.name)
        e['unchanged_origin_build']=load(e['seal']['path'])['actual_build_root']
        record['packages'].append(e)
    record['packages'].sort(key=lambda x:x['package']);save(NEW/'receipts/BUILD_VERIFICATION.json',record)
    save(NEW/'receipts/PACKAGE_INDEX.json',dict(status='SEALED_AWAITING_FRESH_STARTUP',study_version='v0.3',packages=record['packages'],assets=[dict(path=e[k]['path'],**info(e[k]['path'])) for e in record['packages'] for k in ('zip','seal')]))
    need(old_assets=={p.name:info(p) for p in (OLD/'dist').iterdir()},'Prior assets changed')
    guard_other_releases()
    print(json.dumps(dict(status='SEALED_V03_R3',changed_code_files=len(changed),rebuilt_assets=2,reused_assets=4)))


def verify():
    need(not (NEW / 'qa/fresh_extraction').exists(), 'Fresh extraction already exists; preserve evidence')
    build_record = load(NEW / 'receipts/BUILD_VERIFICATION.json')
    dest = NEW / 'qa/fresh_extraction'
    packages = []
    for e in build_record['packages']:
        result = batch.verify_package(e['zip']['path'], e['seal']['path'])
        with zipfile.ZipFile(e['zip']['path']) as z:
            for n in z.namelist():
                p = dest / n
                need(p.resolve().is_relative_to(dest.resolve()), 'Unsafe extraction')
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(n))
        packages.append(dict(package=e['package'], zip=e['zip'], seal=e['seal'], fresh_extraction=str(dest / e['package']), verification=dict(status='PASS',files=result['files'])))
    before = files(dest)
    code = dest / 'QPathformer_v0.3_Code'
    receipt = NEW / 'receipts/QPathformer_v0.3_Code.startup.json'
    command = [str(PYTHON), '-B', str(code / 'tools/startup_check.py'), '--output', str(receipt)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    env.pop('PYTHONOPTIMIZE', None)
    r = subprocess.run(command, cwd=code, env=env, capture_output=True, text=True, timeout=500)
    save(NEW / 'receipts/STARTUP_INVOCATION.json', dict(command=command, cwd=str(code), returncode=r.returncode, stdout=r.stdout, stderr=r.stderr))
    need(before == files(dest), 'Startup changed package bytes or membership')
    need(r.returncode == 0 and receipt.is_file() and load(receipt)['status'] == 'PASS', 'Genuine startup failed: '+r.stdout+' '+r.stderr)
    cs = next(e for e in packages if e['package'].endswith('_Code'))
    startup = load(receipt)
    need(len(startup['checks']) == 3, 'Expected all three genuine startup checks')
    fresh = dict(status='PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP', checked_at_utc=now(), packages=packages, code_zip=cs['zip'], code_seal=cs['seal'], code_startup_receipt=dict(path=str(receipt), **info(receipt)), package_bytes_unchanged=True, receipt_outside_entire_package=True, scope=startup['scope'], not_verified=startup['not_verified'])
    save(NEW / 'receipts/FRESH_PACKAGE_VERIFICATION.json', fresh)
    pi = load(NEW / 'receipts/PACKAGE_INDEX.json')
    pi.update(status='READY_FOR_DRAFT_REVIEW', startup_binding=dict(path=str(NEW / 'receipts/FRESH_PACKAGE_VERIFICATION.json'), **info(NEW / 'receipts/FRESH_PACKAGE_VERIFICATION.json')))
    save(NEW / 'receipts/PACKAGE_INDEX.json', pi)
    batch.verify_study(3)
    need(startup['parsed_python_files']==49 and startup['prediction_methods_checked']==13,'Unexpected genuine startup scope')
    comparisons=[dict(name=p.name,previous=info(OLD/'dist'/p.name),current=info(p),unchanged=info(OLD/'dist'/p.name)==info(p)) for p in sorted((NEW/'dist').iterdir())]
    disposition=dict(status='PASS_LOCAL_SUCCESSOR_READY_FOR_PRIVATE_DRAFT_UPDATE',addressed=['C01 strict inventory parsing and duplicate rejection','C02 PowerShell stop-on-verification-failure tested on Windows','R01 primary BCE and distinct uncertainty intervals','R02 historical study checks separated from packaging startup','R04 predecessor private evidence and original Q2 source identities verified'],resolved_without_package_repair=['R03: all predecessor remote sizes/hashes match; no copied footer or corrupted size prose in saved release body'],optional_improvements=['v0.2 CPU-forward prose removed','v0.3 parsed-file count and NumPy version recorded','Exclusive receipt creation and pre/post package integrity checks'],deferred=[dict(item='Optional Word metadata modernization',reason='Report bytes and valid Study/Documentation assets are deliberately preserved; metadata is not a scientific error.')],assets=comparisons,startup_binding=dict(path=str(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**info(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')),publication_authorized=False)
    save(NEW/'receipts/REVIEW_DISPOSITION.json',disposition)
    rows=['# v0.3 r3 revision summary','','C01/C02 are corrected: strict inventory parsing and an explicitly guarded PowerShell quickstart. The startup helper also reserves receipts exclusively and verifies integrity before and after its three v0.3 checks. The release body identifies primary BCE and distinguishes historical replay and simulated-shot analyses from packaging checks.','','The current remote predecessor has no pasted-size or footer defect. Private evidence links resolve, both indexes agree, and the available Q2 originals match all 56 selected source files. The 47 scientific Python files and full scientific payload remain unchanged. Study/Documentation ZIPs and seals are reused byte-for-byte, including the unchanged PDF/DOCX. The original build provenance remains authoritative. Optional Word metadata cleanup is deferred to preserve report bytes.','','The genuine startup on the final freshly extracted Code ZIP passed three checks, parsed 49 Python files, exercised 13 methods and recorded NumPy '+startup['numpy_version']+'. Helper regressions and actual PowerShell checks have separate receipts; mock controls are not scientific startup evidence. No training, official scoring or QPU jobs were run.','','## Asset identities','','| Asset | Previous bytes / SHA-256 | Current bytes / SHA-256 |','| --- | --- | --- |']
    for e in comparisons:rows.append(f'| {e["name"]} | {e["previous"]["bytes"]} / `{e["previous"]["sha256"]}` | {e["current"]["bytes"]} / `{e["current"]["sha256"]}` |')
    rows+=['','[Review disposition](receipts/REVIEW_DISPOSITION.json) · [Helper probes](receipts/HELPER_TEST_RESULTS.json) · [PowerShell checks](receipts/POWERSHELL_TEST_RESULTS.json) · [Final startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json).','','The adopted licence scheme and legal texts are unchanged. This is a private draft revision; publication remains a separate action.']
    write(NEW/'REVISION_SUMMARY.md','\n'.join(rows)+'\n')
    print(json.dumps(dict(status=fresh['status'], startup_checks=len(startup['checks']), code_zip=cs['zip'])))

def commit():
    guard_other_releases()
    need(load(NEW / 'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json')['status']=='PASS', 'Independent audit absent')
    need(not batch.git('status','--porcelain').strip(), 'Preparation checkout dirty')
    record=batch.verify_study(3)
    path='release_preparation/study-v0.3/revisions/'+NEW.name
    dest=batch.R/path
    need(not dest.exists(),'Successor review tree already exists; preserve it')
    cp(Path(__file__),NEW/'tools/v03_r3.py')
    cp(HERE/'v03_r3_audit/audit.py',NEW/'tools/independent_audit.py')
    cp(HERE/'v03_r3_audit/audit_lineage.py',NEW/'tools/independent_lineage_audit.py')
    for name in ('startup_check.py','verify_package.py'):cp(HELPERS/name,NEW/'tools'/name)
    write(NEW/'tools/README.md','# Preparation and audit tools\n\nThese are retained implementation snapshots for the recorded local checks. The helper regression harness uses the recorded historical Q2 fixture path and the two adjacent helper copies. The preparation and independent audit scripts retain their actual local environment paths; they are evidence, not a portable full-study runner. Genuine final startup is separately recorded against the sealed Code ZIP.\n')
    for folder in ('receipts','report','tools','review'):
        for p in (NEW/folder).rglob('*'):
            if p.is_file() and p.suffix.lower() in ('.json','.md','.py','.ps1'):cp(p,dest/folder/p.relative_to(NEW/folder))
    for p in NEW.iterdir():
        if p.is_file() and p.suffix.lower() in ('.json','.md'):cp(p,dest/p.name)
    for e in record['packages']:
        with zipfile.ZipFile(e['zip']['path']) as z:
            for n in z.namelist():
                out=(dest/'packages'/n).resolve()
                need(out.is_relative_to((dest/'packages').resolve()),'Unsafe review extraction')
                out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(n))
    save(dest/'PACKAGE_INDEX.json',dict(study_version='v0.3',repository_edition='v1.0',packages=[dict(package=e['package'],zip=dict(path=Path(e['zip']['path']).name,**info(e['zip']['path'])),seal=dict(path=Path(e['seal']['path']).name,**info(e['seal']['path'])),actual_build_root=load(e['seal']['path'])['actual_build_root']) for e in record['packages']],selection_root=str(NEW)))
    cp(batch.B/'OWNER_LICENSE_AUTHORIZATION.json',dest/'OWNER_LICENSE_AUTHORIZATION.json')
    write(dest/'README.md','# Study v0.3 r3 review records\n\nThis successor corrects the release-level scientific wording, both package helpers and the PowerShell quickstart. The Study and Documentation ZIP/seal pairs are reused byte-for-byte with their original build provenance. All 47 scientific Python files, the complete selected scientific payload, report PDF/DOCX, legal texts and historical adoption records retain their reviewed bytes. The report retains its prior visual QA; it was not rerendered.\n\n[Package identities](PACKAGE_INDEX.json) · [Independent successor audit](receipts/INDEPENDENT_SUCCESSOR_AUDIT.json) · [Fresh startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Helper regression probes](receipts/HELPER_TEST_RESULTS.json) · [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).\n\nThe exact package contents, including selected source code, are committed under packages/. ZIPs and seals are private draft release assets. r2 remains preserved as historical evidence. Main, other releases, visibility and the Latest designation remain unchanged. This revision does not publish the release.\n')
    batch.git('add',path);batch.git('commit','-m','Prepare corrected v0.3 r3 packages and verified source')
    commit=batch.git('rev-parse','HEAD').decode().strip();batch.git('push','origin',batch.BRANCH)
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==commit,'Remote branch differs')
    guard_other_releases()
    save(NEW/'receipts/REVIEW_BRANCH.json',dict(branch=batch.BRANCH,target_commit=commit,base_main=batch.EXPECTED_BASE,record_path=path,checked_at_utc=now()))
    print(json.dumps(dict(target_commit=commit)))

def upload():
    guard_other_releases()
    for kind in ('Study','Documentation','Code'):
        batch.verify_package(NEW/'dist'/f'QPathformer_v0.3_{kind}.zip',NEW/'dist'/f'QPathformer_v0.3_{kind}.seal.json')
    branch = load(NEW / 'receipts/REVIEW_BRANCH.json')
    target, path = branch['target_commit'], branch['record_path']
    baseurl = f'https://github.com/{batch.NAME}/blob/{target}/{path}/'
    body = (NEW / 'RELEASE_NOTES.md').read_text('utf-8')
    body = body.replace('{{EVIDENCE_BASE}}', baseurl)
    need('{{' not in body and '}}' not in body, 'Unresolved release template fields')
    # Resolve relative links against the exact committed successor review tree.
    def link(m):
        label, href = m.groups()
        if href.startswith(('https://','http://','#')): return m.group(0)
        need((batch.R/path/href).is_file(), 'Release link absent: '+href)
        return f'[{label}]({baseurl}{href})'
    body = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, body)
    r = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}')
    need(r['draft'] and r['tag_name']=='study-v0.3', 'Expected existing private draft')
    save(NEW / 'receipts/DRAFT_BEFORE_RESUME.json', r)
    payload = dict(tag_name='study-v0.3', target_commitish=target, name=TITLE, body=body, draft=True, prerelease=False, make_latest='false')
    req = NEW / 'receipts/RELEASE_MUTATION_REQUEST.json'; save(req,payload)
    r = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}', '--method','PATCH','--input',req)
    batch.check_release(r,3,target,TITLE)
    hist = dict(release_id=RELEASE_ID,status='SUPERSEDED_DRAFT_ASSETS_PRESERVED_BEFORE_REPLACEMENT',assets=[])
    for p in sorted((NEW / 'dist').iterdir()):
        current = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}')
        batch.check_release(current,3,target,TITLE)
        assets = {a['name']:a for a in current['assets']}
        if p.name in assets:
            a = assets[p.name]
            if a['size']==info(p)['bytes'] and a.get('digest')=='sha256:'+info(p)['sha256']: continue
            old = batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','-H','Accept: application/octet-stream',timeout=180)
            need(batch.bytes_info(old)==info(OLD/'dist'/p.name),'Existing draft asset differs from reviewed r2')
            oldpath = NEW/'qa/superseded_remote_assets'/str(a['id'])/p.name
            oldpath.parent.mkdir(parents=True,exist_ok=True); oldpath.write_bytes(old)
            hist['assets'].append(dict(id=a['id'],name=a['name'],path=str(oldpath),**batch.bytes_info(old),preserved_at_utc=now(),replacement=dict(path=str(p),**info(p))))
            save(NEW/'receipts/SUPERSEDED_REMOTE_ASSETS.json',hist)
            batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','--method','DELETE')
        batch.run(batch.GH,'release','upload','study-v0.3',p,'--repo',batch.NAME,timeout=180)
    r = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}')
    need({a['name'] for a in r['assets']}=={p.name for p in (NEW/'dist').iterdir()},'Unexpected draft assets')
    downloaded=[]
    for a in r['assets']:
        data = batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','-H','Accept: application/octet-stream',timeout=180)
        p = NEW/'dist'/a['name']; need(batch.bytes_info(data)==info(p),'Authenticated download differs')
        need(a['size']==len(data) and a['digest']=='sha256:'+batch.bytes_info(data)['sha256'],'Remote identity differs')
        dest=NEW/'qa/authenticated_downloads'/a['name'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        downloaded.append(dict(id=a['id'],name=a['name'],**info(p),download_verified=True))
    for kind in ('Study','Documentation','Code'):
        d=NEW/'qa/authenticated_downloads';batch.verify_package(d/f'QPathformer_v0.3_{kind}.zip',d/f'QPathformer_v0.3_{kind}.seal.json')
    guard_other_releases()
    receipt=dict(schema='qpath-draft-release-1',status='PRIVATE_DRAFT_UPLOADED_AND_AUTHENTICATED_DOWNLOAD_VERIFIED',study_version='v0.3',repository=dict(id=batch.REPO_ID,name=batch.NAME,private=True),draft_release=dict(id=RELEASE_ID,url=r['html_url'],tag_name='study-v0.3',target_commitish=target,name=TITLE,draft=True,prerelease=False,published_at=None),assets=downloaded,branch=batch.BRANCH,main_unchanged=batch.EXPECTED_BASE,protected_releases_unchanged=True,other_drafts_unchanged=True,v095_remains_latest=True,checked_at_utc=now(),publication_authorized=False)
    save(NEW/'receipts/DRAFT_RELEASE.json',receipt)
    cp(NEW/'receipts/DRAFT_RELEASE.json',batch.R/path/'DRAFT_RELEASE.json')
    cp(NEW/'receipts/SUPERSEDED_REMOTE_ASSETS.json',batch.R/path/'SUPERSEDED_REMOTE_ASSETS.json')
    batch.git('add',path);batch.git('commit','-m','Record verified v0.3 r3 private draft replacements');batch.git('push','origin',batch.BRANCH)
    evidence=batch.git('rev-parse','HEAD').decode().strip()
    payload['body']=body.rstrip()+f'\n\n[Authenticated draft assets](https://github.com/{batch.NAME}/blob/{evidence}/{path}/DRAFT_RELEASE.json).\n'
    req2=NEW/'receipts/RELEASE_RECEIPT_LINK_REQUEST.json';save(req2,payload)
    r=batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}','--method','PATCH','--input',req2)
    batch.check_release(r,3,target,TITLE)
    verified=[]
    for commit,relative in [(target,'README.md'),(target,'PACKAGE_INDEX.json'),(target,'receipts/PACKAGE_INDEX.json'),(target,'receipts/FRESH_PACKAGE_VERIFICATION.json'),(target,'receipts/QPathformer_v0.3_Code.startup.json'),(target,'receipts/ROOT_PACKAGE_VERIFICATION.json'),(target,'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json'),(evidence,'DRAFT_RELEASE.json')]:
        got=batch.api(f'repos/{batch.NAME}/contents/{path}/{relative}?ref={commit}')
        need(base64.b64decode(got['content'])==(batch.R/path/relative).read_bytes(),'Remote evidence differs '+relative)
        verified.append(dict(commit=commit,path=path+'/'+relative))
    guard_other_releases()
    completion=dict(status='PASS_PRIVATE_DRAFT_READY_FOR_REVIEW',release_id=RELEASE_ID,release_url=r['html_url'],study_version='v0.3',assets_verified=6,draft=True,private=True,target_commit=target,evidence_commit=evidence,links=verified,main_unchanged=True,protected_releases_unchanged=True,other_drafts_unchanged=True,latest='study-v0.9.5',completed_at_utc=now())
    save(NEW/'receipts/COMPLETION.json',completion)
    print(json.dumps(completion,indent=2))

def finalize():
    guard_other_releases()
    need(not batch.git('status','--porcelain').strip(),'Preparation checkout dirty')
    done=load(NEW/'receipts/COMPLETION.json');uploaded=load(NEW/'receipts/DRAFT_RELEASE.json');branch=load(NEW/'receipts/REVIEW_BRANCH.json');fresh=load(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    index=load(batch.B/'REVIEW_INDEX.json');item=next(e for e in index['studies'] if e['study_version']=='v0.3');prior=json.loads(json.dumps(item))
    history=batch.B/'history/before_v03_r3';need(not history.exists(),'Preserve prior review index history')
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md','receipts/COMPLETION.json','tools/batch.py'):cp(batch.B/name,history/name)
    evidence=f'https://github.com/{batch.NAME}/blob/{done["evidence_commit"]}/{branch["record_path"]}/'
    item.update(draft_url=done['release_url'],target_commit=done['target_commit'],local_pack_folder=str(NEW),local_assets=str(NEW/'dist'),record_path=branch['record_path'],evidence_commit=done['evidence_commit'],evidence_url=evidence+'README.md',receipt_url=evidence+'DRAFT_RELEASE.json',assets=uploaded['assets'],startup_status='PASS',startup_scope=fresh['scope'],startup_binding=dict(path=str(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**info(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')))
    scopes=[]
    for kind in ('Study','Documentation','Code'):
        with zipfile.ZipFile(NEW/'dist'/f'QPathformer_v0.3_{kind}.zip') as z:
            prefix=f'QPathformer_v0.3_{kind}/'
            for n in z.namelist():
                rel=n.removeprefix(prefix)
                if '/' not in rel and rel.endswith('_LICENSE_SCOPE.json'):
                    scope=json.loads(z.read(n));scopes.append(dict(package=kind,path=rel,files=len(scope['files']),identity=batch.bytes_info(z.read(n))))
    item['scopes']=scopes
    item['revision_note']='r3 Code helper/quickstart corrections; original Study and Documentation ZIPs and seals reused unchanged.'
    index.update(completed_at_utc=now(),latest_revision_note='v0.3 r3 Code corrections are verified in the private draft. v0.2 remains published; v0.9.5 remains Latest; all other study selections are unchanged.')
    save(batch.B/'REVIEW_INDEX.json',index)
    for name in ('REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md'):
        text=(batch.B/name).read_text('utf-8')
        for key in ('draft_url','evidence_url','local_pack_folder'):text=text.replace(prior[key],item[key])
        text=text.replace(Path(prior['local_pack_folder']).as_posix(),NEW.as_posix())
        text+='\nThe current v0.3 selection is r3: strict inventory parsing, guarded PowerShell quickstart, exact pre/post startup integrity and corrected release-level metric/verification wording. Only the Code ZIP and seal changed; Study and Documentation assets are reused unchanged. v0.3 remains a private draft.\n'
        write(batch.B/name,text)
    dest=batch.R/'release_preparation/draft_batch_20261029'
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md'):cp(batch.B/name,dest/name)
    for p in history.rglob('*'):
        if p.is_file() and p.name!='LOCAL_REVIEW_INDEX.md':cp(p,dest/'history/before_v03_r3'/p.relative_to(history))
    selector=HERE/'batch.py';source=selector.read_text('utf-8')
    need("3:'draft_20261029_r2'" in source,'Unexpected v0.3 selected-build mapping')
    write(selector,source.replace("3:'draft_20261029_r2'","3:'draft_20261029_r3'",1));cp(selector,batch.B/'tools/batch.py');cp(selector,dest/'tools/batch.py')
    path='release_preparation/study-v0.3/CURRENT.json'
    save(batch.R/path,dict(study_version='v0.3',revision=NEW.name,target_commit=done['target_commit'],evidence_commit=done['evidence_commit'],record_path=branch['record_path'],draft=True,assets=uploaded['assets'],previous_revision=OLD.name))
    batch.git('add','release_preparation/draft_batch_20261029',path);batch.git('commit','-m','Index reviewed v0.3 Code successor and retained report assets');batch.git('push','origin',batch.BRANCH)
    commit=batch.git('rev-parse','HEAD').decode().strip();guard_other_releases()
    need(not batch.git('status','--porcelain').strip(),'Dirty checkout after index refresh')
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==commit,'Remote branch differs')
    path='release_preparation/draft_batch_20261029/REVIEW_INDEX.md';got=batch.api(f'repos/{batch.NAME}/contents/{path}?ref={commit}')
    need(base64.b64decode(got['content'])==(batch.B/'REVIEW_INDEX.md').read_bytes(),'Remote index differs')
    result=dict(status='PASS_V03_R3_PRIVATE_DRAFT_COMPLETE',release_url=done['release_url'],local_build=str(NEW),revision_summary=str(NEW/'REVISION_SUMMARY.md'),main_unchanged=batch.EXPECTED_BASE,other_releases_unchanged=True,v02_remains_published=True,latest='study-v0.9.5',repository_private=True,publication_performed=False,assets_verified=6,rebuilt_assets=2,reused_assets=4,final_evidence_commit=commit,remote_review_index=f'https://github.com/{batch.NAME}/blob/{commit}/{path}',completed_at_utc=now())
    save(NEW/'receipts/FINAL_REVISION_COMPLETION.json',result)
    last=load(history/'receipts/COMPLETION.json');last.update(final_evidence_commit=commit,remote_review_index=result['remote_review_index'],latest_revision='v0.3 r3',completed_at_utc=now());save(batch.B/'receipts/COMPLETION.json',last)
    print(json.dumps(result,indent=2))

if __name__=='__main__':globals()[sys.argv[1]]()
