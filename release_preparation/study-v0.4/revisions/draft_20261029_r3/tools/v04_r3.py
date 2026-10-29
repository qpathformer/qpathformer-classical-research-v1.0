"""Prepare the approved v0.4 corrections as a private draft successor."""
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
OLD=BASE/'study-v0.4/draft_20261029_r2'
NEW=BASE/'study-v0.4/draft_20261029_r3'
HELPERS=HERE/'v04_r3_helpers'
PROSE=HERE/'v04_r3_prose'
PYTHON=Path(r'C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe')
TITLE='Q-Pathformer Study v0.4 — Routing and Circuit Contribution'
RELEASE_ID=427659592
NOTES=Path(r'C:\Anthony Siljeg\CPU-QPU git repo prep\v6 final staging\study-v0.4_release_review_and_codex_notes.md')
original_selected=batch.selected_build
batch.selected_build=lambda n:NEW if n==4 else original_selected(n)
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
    published=load(BASE/'study-v0.3/publication_20261029_r3/POST_PUBLICATION_STATE.json')
    for r in published['releases']:
        if not r['draft']:
            need(batch.signature(next(x for x in state['releases'] if x['id']==r['id']))==batch.signature(r),'Published release changed: '+r['tag_name'])
    need(state['tags']==published['tags'],'Tags changed after the authorized v0.3 publication')
    r=next(x for x in state['releases'] if x['id']==RELEASE_ID)
    need(r['draft'] and r['tag_name']=='study-v0.4','v0.4 must remain the existing draft')
    if baseline:
        a={r['id']:batch.signature(r) for r in baseline['releases'] if r['id']!=RELEASE_ID}
        b={r['id']:batch.signature(r) for r in state['releases'] if r['id']!=RELEASE_ID}
        need(a==b,'Another release changed during this revision')

def guard_other_releases():
    check_state(capture(),load(NEW/'receipts/REMOTE_BASELINE_V04_REVISION.json'))

def build():
    state=capture();check_state(state)
    need(not NEW.exists(),'Preserve any existing successor')
    for n in ('startup_check.py','verify_package.py','QUICKSTART.md','HELPER_TEST_RESULTS.json','POWERSHELL_TEST_RESULTS.json','test_helpers.py','test_powershell.py'):
        need((HELPERS/n).is_file(),'Missing helper evidence: '+n)
    for n in ('RELEASE_BODY.md','PROSE_CHANGES.json','SCIENTIFIC_PROSE_REVIEW.json'):
        need((PROSE/n).is_file(),'Missing reviewed prose: '+n)
    for kind in ('Study','Documentation','Code'):
        batch.verify_package(OLD/'dist'/f'QPathformer_v0.4_{kind}.zip',OLD/'dist'/f'QPathformer_v0.4_{kind}.seal.json')
    NEW.mkdir()
    save(NEW/'receipts/REMOTE_BASELINE_V04_REVISION.json',state)
    old_assets={p.name:info(p) for p in (OLD/'dist').iterdir()}
    prior={}
    for zp in sorted((OLD/'dist').glob('*.zip')):
        with zipfile.ZipFile(zp) as z:
            for n in z.namelist():
                p=(NEW/'assembly'/n).resolve();need(p.is_relative_to((NEW/'assembly').resolve()),'Unsafe extraction')
                p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
        root=NEW/'assembly'/zp.stem;prior[root.name]=files(root)
        for n in ('MANIFEST.json','CHECKSUMS.sha256'):(root/n).unlink()
    for p in sorted(PROSE.glob('QPathformer_v0.4_*/**/*')):
        if p.is_file():
            relative=p.relative_to(PROSE);need(relative.parts[1] not in ('historical','provenance','reports','payload','LICENSES'),'Prose edit touches preserved material')
            cp(p,NEW/'assembly'/relative)
    code=NEW/'assembly/QPathformer_v0.4_Code'
    for n in ('startup_check.py','verify_package.py'):cp(HELPERS/n,code/'tools'/n)
    cp(HELPERS/'QUICKSTART.md',code/'QUICKSTART.md')
    p=code/'DEPENDENCIES.md'
    write(p,p.read_text('utf-8')+'\nThe direct import inventory covers all 48 retained scientific Python files and both package helpers. Helper imports use the standard library and local verifier; they add no third-party dependency. Startup records the actual imported NumPy version separately from the historical environment.\n')
    dep=load(code/'DEPENDENCY_INVENTORY.json');imports={}
    pyfiles=sorted(code.rglob('*.py'));need(len(pyfiles)==50,'Expected 50 Python files')
    for p in pyfiles:
        rel=p.relative_to(code).as_posix()
        for node in ast.walk(ast.parse(p.read_text('utf-8-sig'))):
            names=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else ([node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module and node.level==0 else [])
            for name in names:imports.setdefault(name,set()).add(rel)
    dep['direct_import_inventory']={k:sorted(v) for k,v in sorted(imports.items())}
    dep['inventory_scope']=dict(scientific_python_files=48,package_helpers=2,granularity='Syntactic top-level import roots, including standard-library and local modules; not a list of third-party requirements.')
    save(code/'DEPENDENCY_INVENTORY.json',dep)
    inherited=package.inherit(code,[p.relative_to(code).as_posix() for p in pyfiles])
    previous=BASE/'study-v0.3/draft_20261029_r3/assembly/QPathformer_v0.3_Code'
    adopted=load(previous/'CODE_LICENSE_SCOPE.json');lineage=[]
    for name in ('verify_package.py','startup_check.py'):
        rel='tools/'+name;entry=next(e for e in adopted['files'] if e['path']==rel)
        need(info(previous/rel)=={k:entry[k] for k in ('bytes','sha256')},'Prior helper grant identity differs')
        lineage.append(dict(path=rel,current=info(code/rel),adopted_study='v0.3',source_path=str(previous/rel),source_identity=info(previous/rel),scope_record=str(previous/'CODE_LICENSE_SCOPE.json'),scope_record_identity=info(previous/'CODE_LICENSE_SCOPE.json'),relation='Byte-identical reuse' if info(code/rel)==info(previous/rel) else 'Adaptation of the tested v0.3 package helper for the three v0.4 checks',license='Q-Pathformer Platform License 1.0',interpretation='Existing applicable permissions remain in force. Exact current identity is included in this package adopted Code scope.'))
    inherited['package_helper_lineage']=lineage;save(code/'INHERITED_LICENSE_MAP.json',inherited)
    changes=[]
    for root in sorted((NEW/'assembly').iterdir()):
        for p in root.glob('*_LICENSE_SCOPE.json'):
            scope=load(p);before=json.loads(json.dumps(scope))
            for e in scope['files']:e.update(info(root/e['path']))
            if p.name=='CODE_LICENSE_SCOPE.json':
                scope['inherited_exact_matches']=len(inherited['exact_whole_file_matches']);scope['shared_expression_records']=len(inherited['shared_expression_evidence'])
            if scope!=before:save(p,scope)
        source=load(root/'SOURCE_MAP.json');oldmap={e['path']:e for e in source['files']};mapped=[]
        for n,ii in files(root).items():
            if n=='SOURCE_MAP.json':continue
            e=oldmap.get(n)
            if e is None or {k:e[k] for k in ('bytes','sha256')}!=ii:
                e=dict(path=n,source_absolute_path=str(root/n),source_identity=ii,**ii,handling='Reviewed current guidance/helper correction or refreshed exact scope/inventory in this Q2 successor; scientific, report and historical bytes preserved.')
                if n in prior[root.name]:e['previous_edition_identity']=prior[root.name][n]
            mapped.append(e)
        source.update(actual_build_root=str(NEW),files=mapped);save(root/'SOURCE_MAP.json',source)
        for n,ii in prior[root.name].items():
            if n.startswith(('payload/','reports/','historical/','provenance/')) or n in ('LICENSE_ADOPTION.json','LICENSES/CC-BY-4.0.txt','LICENSES/QPATHFORMER-PLATFORM-1.0.txt'):
                need(info(root/n)==ii,'Preserved material changed: '+root.name+'/'+n)
        changes += [dict(package=root.name,path=n,previous=prior[root.name].get(n),current=ii) for n,ii in files(root).items() if prior[root.name].get(n)!=ii]
    for p in (OLD/'report').glob('*.json'):cp(p,NEW/'report'/p.name)
    report=NEW/'assembly/QPathformer_v0.4_Study'
    save(NEW/'report/REPORT_PRESERVATION_BINDING.json',dict(status='IDENTICAL_REPORT_BYTES_HISTORICAL_VISUAL_QA_RETAINED',prior_review=dict(path=str(OLD/'report/REPORT_REVIEW.json'),**info(OLD/'report/REPORT_REVIEW.json')),reports=[dict(path=n,**ii) for n,ii in files(report).items() if n.startswith('reports/')],note='PDF/DOCX and historical edition/review records are byte-identical to the predecessor. No new report rendering or visual review is claimed. Current wrapper guidance is clarified separately.'))
    cp(OLD/'receipts/SOURCE_INVENTORY.json',NEW/'receipts/SOURCE_INVENTORY.json')
    cp(NOTES,NEW/'review'/NOTES.name)
    cp(HERE/'v04_r3_audit/PRELIMINARY_R2_CHECKS.json',NEW/'receipts/PRELIMINARY_R2_CHECKS.json')
    for name in ('HELPER_TEST_RESULTS.json','POWERSHELL_TEST_RESULTS.json'):cp(HELPERS/name,NEW/'receipts'/name)
    for p in HELPERS.iterdir():
        if p.is_file() and p.suffix in ('.py','.ps1'):cp(p,NEW/'tools'/p.name)
    for p in PROSE.glob('*.json'):cp(p,NEW/'receipts'/p.name)
    cp(PROSE/'RELEASE_BODY.md',NEW/'RELEASE_NOTES.md')
    write(NEW/'PREPARATION_BRIEF.md','# v0.4 reviewed successor\n\nApply the accepted notes using the v0.3 release structure. Correct package helpers, study-specific quickstart, scientific explanation and current publisher-review guidance. Preserve all 48 scientific Python files, full retained scientific payload, PDF/DOCX, historical records, canonical licence texts and adoption records. Refresh affected scoped identities and rebuild the three affected packages under this Q2 revision.\n\nThis remains a private draft. Publication, tag/visibility changes, full training, scientific scoring and QPU execution are outside this task. All published releases, main and v0.9.5 Latest remain protected.\n')
    save(NEW/'receipts/REVISION_RECORD.json',dict(status='APPROVED_REVIEW_CORRECTIONS_PREPARED',review=dict(path=str(NOTES),**info(NOTES)),authorization='User requested proceeding with v0.4 using the v0.3 format, applying the notes and preparing the updated private draft while keeping v0.9.5 Latest.',previous_build=str(OLD),actual_build_root=str(NEW),prior_assets=old_assets,changed_files=changes,scientific_python_files_unchanged=48,all_scientific_payload_unchanged=True,reports_and_historical_records_unchanged=True,adoption_and_license_texts_unchanged=True,prior_evidence_preserved=True,publication_authorized=False,checked_at_utc=now()))
    cp(Path(__file__),NEW/'tools/v04_r3.py')
    package.seal(4)
    need(old_assets=={p.name:info(p) for p in (OLD/'dist').iterdir()},'Prior assets changed')
    guard_other_releases()
    print(json.dumps(dict(status='SEALED_V04_R3',changed_files=len(changes),rebuilt_assets=6)))

def review_summary(startup):
    comparisons=[dict(name=p.name,previous=info(OLD/'dist'/p.name),current=info(p)) for p in sorted((NEW/'dist').iterdir())]
    disposition=dict(status='PASS_LOCAL_SUCCESSOR_READY_FOR_PRIVATE_DRAFT_UPDATE',addressed=['Exclusive receipt creation and truthful timeout/failure handling','Strict manifest/checksum path validation before mapping','Pre/post startup integrity and package fingerprint','v0.4-specific three checks and guarded PowerShell quickstart','Primary BCE, Q2 definition, named populations, classical controls and seed uncertainty','Historical readiness separated from packaging checks','Current publisher review clarified without changing historical records or adopted grants','Helper import inventory completed'],deferred=[dict(item='Historical Word keywords/timestamp cleanup',reason='No presentation error was found; preserve the report bytes and historical metadata.')],assets=comparisons,startup_binding=dict(path=str(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**info(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')),publication_authorized=False)
    save(NEW/'receipts/REVIEW_DISPOSITION.json',disposition)
    rows=['# v0.4 r3 revision summary','','The two helpers now enforce strict path/inventory validation, reserve receipts exclusively and verify package identity before and after startup. The PowerShell quickstart stops after verification failure and contains only the three v0.4 checks. Current explanations define Q2, lead with primary BCE, retain stronger classical controls and distinguish historical readiness from new packaging checks. Publisher review is clarified in current guidance; historical edition records remain unchanged.','','All 48 scientific Python files and full scientific payload, report PDF/DOCX, historical records, canonical licence texts and adoption records retain their reviewed bytes. Current wrapper/helper changes require new ZIPs and seals for all three packages. Earlier sealed evidence is preserved. Optional historical Word metadata cleanup is deferred because no report error warrants changing its bytes.','','The genuine final Code startup passed three checks: 50 Python files parsed, nine methods exercised, NumPy '+startup['numpy_version']+'. Mock regression controls, real PowerShell checks and final sealed-ZIP startup are separately recorded. No full training, official-data scoring, dependency installation or QPU execution was performed.','','## Asset identities','','| Asset | Previous bytes / SHA-256 | Current bytes / SHA-256 |','| --- | --- | --- |']
    for e in comparisons:rows.append(f'| {e["name"]} | {e["previous"]["bytes"]} / `{e["previous"]["sha256"]}` | {e["current"]["bytes"]} / `{e["current"]["sha256"]}` |')
    rows+=['','[Review disposition](receipts/REVIEW_DISPOSITION.json) · [Helper probes](receipts/HELPER_TEST_RESULTS.json) · [PowerShell checks](receipts/POWERSHELL_TEST_RESULTS.json) · [Final startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json).','','This is an updated private draft. Publication remains a separate action; v0.9.5 remains Latest.']
    write(NEW/'REVISION_SUMMARY.md','\n'.join(rows)+'\n')


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
    code = dest / 'QPathformer_v0.4_Code'
    receipt = NEW / 'receipts/QPathformer_v0.4_Code.startup.json'
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
    batch.verify_study(4)
    need(startup['parsed_python_files']==50 and startup['prediction_methods_checked']==9,'Unexpected genuine startup scope')
    review_summary(startup)
    print(json.dumps(dict(status=fresh['status'], startup_checks=len(startup['checks']), code_zip=cs['zip'])))

def commit():
    guard_other_releases()
    need(load(NEW / 'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json')['status']=='PASS', 'Independent audit absent')
    need(not batch.git('status','--porcelain').strip(), 'Preparation checkout dirty')
    record=batch.verify_study(4)
    path='release_preparation/study-v0.4/revisions/'+NEW.name
    dest=batch.R/path
    need(not dest.exists(),'Successor review tree already exists; preserve it')
    cp(Path(__file__),NEW/'tools/v04_r3.py')
    cp(HERE/'v04_r3_audit/audit.py',NEW/'tools/independent_audit.py')
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
    save(dest/'PACKAGE_INDEX.json',dict(study_version='v0.4',repository_edition='v1.0',packages=[dict(package=e['package'],zip=dict(path=Path(e['zip']['path']).name,**info(e['zip']['path'])),seal=dict(path=Path(e['seal']['path']).name,**info(e['seal']['path'])),actual_build_root=load(e['seal']['path'])['actual_build_root']) for e in record['packages']],selection_root=str(NEW)))
    cp(batch.B/'OWNER_LICENSE_AUTHORIZATION.json',dest/'OWNER_LICENSE_AUTHORIZATION.json')
    write(dest/'README.md','# Study v0.4 r3 review records\n\nThis successor corrects the release-level scientific wording, both package helpers and the PowerShell quickstart. Current package explanations and publisher-review guidance are updated. All 48 scientific Python files, the complete selected scientific payload, report PDF/DOCX, legal texts and historical adoption records retain their reviewed bytes. The report retains its prior visual QA; it was not rerendered.\n\n[Package identities](PACKAGE_INDEX.json) · [Independent successor audit](receipts/INDEPENDENT_SUCCESSOR_AUDIT.json) · [Fresh startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Helper regression probes](receipts/HELPER_TEST_RESULTS.json) · [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).\n\nThe exact package contents, including selected source code, are committed under packages/. ZIPs and seals are private draft release assets. r2 remains preserved as historical evidence. Main, other releases, visibility and the Latest designation remain unchanged. This revision does not publish the release.\n')
    batch.git('add',path);batch.git('commit','-m','Prepare corrected v0.4 r3 packages and verified source')
    commit=batch.git('rev-parse','HEAD').decode().strip();batch.git('push','origin',batch.BRANCH)
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==commit,'Remote branch differs')
    guard_other_releases()
    save(NEW/'receipts/REVIEW_BRANCH.json',dict(branch=batch.BRANCH,target_commit=commit,base_main=batch.EXPECTED_BASE,record_path=path,checked_at_utc=now()))
    print(json.dumps(dict(target_commit=commit)))

def upload():
    guard_other_releases()
    for kind in ('Study','Documentation','Code'):
        batch.verify_package(NEW/'dist'/f'QPathformer_v0.4_{kind}.zip',NEW/'dist'/f'QPathformer_v0.4_{kind}.seal.json')
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
    need(r['draft'] and r['tag_name']=='study-v0.4', 'Expected existing private draft')
    save(NEW / 'receipts/DRAFT_BEFORE_RESUME.json', r)
    payload = dict(tag_name='study-v0.4', target_commitish=target, name=TITLE, body=body, draft=True, prerelease=False, make_latest='false')
    req = NEW / 'receipts/RELEASE_MUTATION_REQUEST.json'; save(req,payload)
    r = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}', '--method','PATCH','--input',req)
    batch.check_release(r,4,target,TITLE)
    hist = dict(release_id=RELEASE_ID,status='SUPERSEDED_DRAFT_ASSETS_PRESERVED_BEFORE_REPLACEMENT',assets=[])
    for p in sorted((NEW / 'dist').iterdir()):
        current = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}')
        batch.check_release(current,4,target,TITLE)
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
        batch.run(batch.GH,'release','upload','study-v0.4',p,'--repo',batch.NAME,timeout=180)
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
        d=NEW/'qa/authenticated_downloads';batch.verify_package(d/f'QPathformer_v0.4_{kind}.zip',d/f'QPathformer_v0.4_{kind}.seal.json')
    guard_other_releases()
    receipt=dict(schema='qpath-draft-release-1',status='PRIVATE_DRAFT_UPLOADED_AND_AUTHENTICATED_DOWNLOAD_VERIFIED',study_version='v0.4',repository=dict(id=batch.REPO_ID,name=batch.NAME,private=True),draft_release=dict(id=RELEASE_ID,url=r['html_url'],tag_name='study-v0.4',target_commitish=target,name=TITLE,draft=True,prerelease=False,published_at=None),assets=downloaded,branch=batch.BRANCH,main_unchanged=batch.EXPECTED_BASE,protected_releases_unchanged=True,other_drafts_unchanged=True,v095_remains_latest=True,checked_at_utc=now(),publication_authorized=False)
    save(NEW/'receipts/DRAFT_RELEASE.json',receipt)
    cp(NEW/'receipts/DRAFT_RELEASE.json',batch.R/path/'DRAFT_RELEASE.json')
    cp(NEW/'receipts/SUPERSEDED_REMOTE_ASSETS.json',batch.R/path/'SUPERSEDED_REMOTE_ASSETS.json')
    batch.git('add',path);batch.git('commit','-m','Record verified v0.4 r3 private draft replacements');batch.git('push','origin',batch.BRANCH)
    evidence=batch.git('rev-parse','HEAD').decode().strip()
    payload['body']=body.rstrip()+f'\n\n[Authenticated draft assets](https://github.com/{batch.NAME}/blob/{evidence}/{path}/DRAFT_RELEASE.json).\n'
    req2=NEW/'receipts/RELEASE_RECEIPT_LINK_REQUEST.json';save(req2,payload)
    r=batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}','--method','PATCH','--input',req2)
    batch.check_release(r,4,target,TITLE)
    verified=[]
    for commit,relative in [(target,'README.md'),(target,'PACKAGE_INDEX.json'),(target,'receipts/PACKAGE_INDEX.json'),(target,'receipts/FRESH_PACKAGE_VERIFICATION.json'),(target,'receipts/QPathformer_v0.4_Code.startup.json'),(target,'receipts/ROOT_PACKAGE_VERIFICATION.json'),(target,'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json'),(evidence,'DRAFT_RELEASE.json')]:
        got=batch.api(f'repos/{batch.NAME}/contents/{path}/{relative}?ref={commit}')
        need(base64.b64decode(got['content'])==(batch.R/path/relative).read_bytes(),'Remote evidence differs '+relative)
        verified.append(dict(commit=commit,path=path+'/'+relative))
    guard_other_releases()
    completion=dict(status='PASS_PRIVATE_DRAFT_READY_FOR_REVIEW',release_id=RELEASE_ID,release_url=r['html_url'],study_version='v0.4',assets_verified=6,draft=True,private=True,target_commit=target,evidence_commit=evidence,links=verified,main_unchanged=True,protected_releases_unchanged=True,other_drafts_unchanged=True,latest='study-v0.9.5',completed_at_utc=now())
    save(NEW/'receipts/COMPLETION.json',completion)
    print(json.dumps(completion,indent=2))

def finalize():
    guard_other_releases()
    need(not batch.git('status','--porcelain').strip(),'Preparation checkout dirty')
    done=load(NEW/'receipts/COMPLETION.json');uploaded=load(NEW/'receipts/DRAFT_RELEASE.json');branch=load(NEW/'receipts/REVIEW_BRANCH.json');fresh=load(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    index=load(batch.B/'REVIEW_INDEX.json');item=next(e for e in index['studies'] if e['study_version']=='v0.4');prior=json.loads(json.dumps(item))
    history=batch.B/'history/before_v04_r3';need(not history.exists(),'Preserve prior review index history')
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md','receipts/COMPLETION.json','tools/batch.py'):cp(batch.B/name,history/name)
    evidence=f'https://github.com/{batch.NAME}/blob/{done["evidence_commit"]}/{branch["record_path"]}/'
    item.update(draft_url=done['release_url'],target_commit=done['target_commit'],local_pack_folder=str(NEW),local_assets=str(NEW/'dist'),record_path=branch['record_path'],evidence_commit=done['evidence_commit'],evidence_url=evidence+'README.md',receipt_url=evidence+'DRAFT_RELEASE.json',assets=uploaded['assets'],startup_status='PASS',startup_scope=fresh['scope'],startup_binding=dict(path=str(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**info(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')))
    scopes=[]
    for kind in ('Study','Documentation','Code'):
        with zipfile.ZipFile(NEW/'dist'/f'QPathformer_v0.4_{kind}.zip') as z:
            prefix=f'QPathformer_v0.4_{kind}/'
            for n in z.namelist():
                rel=n.removeprefix(prefix)
                if '/' not in rel and rel.endswith('_LICENSE_SCOPE.json'):
                    scope=json.loads(z.read(n));scopes.append(dict(package=kind,path=rel,files=len(scope['files']),identity=batch.bytes_info(z.read(n))))
    item['scopes']=scopes
    item['revision_note']='r3 helper, quickstart and current guidance corrections; report/scientific/historical bytes unchanged.'
    index.update(completed_at_utc=now(),latest_revision_note='v0.4 r3 corrections are verified in the private draft. v0.2 and v0.3 remain published; v0.9.5 remains Latest; all other selections are unchanged.')
    save(batch.B/'REVIEW_INDEX.json',index)
    for name in ('REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md'):
        text=(batch.B/name).read_text('utf-8')
        for key in ('draft_url','evidence_url','local_pack_folder'):text=text.replace(prior[key],item[key])
        text=text.replace(Path(prior['local_pack_folder']).as_posix(),NEW.as_posix())
        text+='\nThe current v0.4 selection is r3: strict inventory parsing, guarded PowerShell quickstart, exact pre/post startup integrity and corrected release-level metric/verification wording. All three package pairs were rebuilt for current helper/wrapper changes; report and scientific bytes are unchanged. v0.4 remains a private draft.\n'
        write(batch.B/name,text)
    dest=batch.R/'release_preparation/draft_batch_20261029'
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md'):cp(batch.B/name,dest/name)
    for p in history.rglob('*'):
        if p.is_file() and p.name!='LOCAL_REVIEW_INDEX.md':cp(p,dest/'history/before_v04_r3'/p.relative_to(history))
    selector=HERE/'batch.py';source=selector.read_text('utf-8')
    need("4:'draft_20261029_r2'" in source,'Unexpected v0.4 selected-build mapping')
    write(selector,source.replace("4:'draft_20261029_r2'","4:'draft_20261029_r3'",1));cp(selector,batch.B/'tools/batch.py');cp(selector,dest/'tools/batch.py')
    path='release_preparation/study-v0.4/CURRENT.json'
    save(batch.R/path,dict(study_version='v0.4',revision=NEW.name,target_commit=done['target_commit'],evidence_commit=done['evidence_commit'],record_path=branch['record_path'],draft=True,assets=uploaded['assets'],previous_revision=OLD.name))
    batch.git('add','release_preparation/draft_batch_20261029',path);batch.git('commit','-m','Index reviewed v0.4 successor packages and preserved reports');batch.git('push','origin',batch.BRANCH)
    commit=batch.git('rev-parse','HEAD').decode().strip();guard_other_releases()
    need(not batch.git('status','--porcelain').strip(),'Dirty checkout after index refresh')
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==commit,'Remote branch differs')
    path='release_preparation/draft_batch_20261029/REVIEW_INDEX.md';got=batch.api(f'repos/{batch.NAME}/contents/{path}?ref={commit}')
    need(base64.b64decode(got['content'])==(batch.B/'REVIEW_INDEX.md').read_bytes(),'Remote index differs')
    result=dict(status='PASS_V04_R3_PRIVATE_DRAFT_COMPLETE',release_url=done['release_url'],local_build=str(NEW),revision_summary=str(NEW/'REVISION_SUMMARY.md'),main_unchanged=batch.EXPECTED_BASE,other_releases_unchanged=True,v02_remains_published=True,v03_remains_published=True,latest='study-v0.9.5',repository_private=True,publication_performed=False,assets_verified=6,rebuilt_assets=6,reused_assets=0,final_evidence_commit=commit,remote_review_index=f'https://github.com/{batch.NAME}/blob/{commit}/{path}',completed_at_utc=now())
    save(NEW/'receipts/FINAL_REVISION_COMPLETION.json',result)
    last=load(history/'receipts/COMPLETION.json');last.update(final_evidence_commit=commit,remote_review_index=result['remote_review_index'],latest_revision='v0.4 r3',completed_at_utc=now());save(batch.B/'receipts/COMPLETION.json',last)
    print(json.dumps(result,indent=2))

if __name__=='__main__':globals()[sys.argv[1]]()
