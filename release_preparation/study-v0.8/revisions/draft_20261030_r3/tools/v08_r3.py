"""Prepare the approved v0.8 corrections as a private draft successor."""
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
BASE=batch.BASE
OLD=BASE/'study-v0.8/draft_20261029_r2'
NEW=BASE/'study-v0.8/draft_20261030_r3'
HELPERS=HERE/'v08_r3_helpers'
PROSE=HERE/'v08_r3_prose'
PYTHON=Path(r'C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe')
TITLE='Q-Pathformer Study v0.8 — Priority Training and Routed Models'
RELEASE_ID=427665050
NOTES=Path(r'C:\Anthony Siljeg\CPU-QPU git repo prep\v6 final staging\study-v0.8_release_review_and_codex_notes.md')
original_selected=batch.selected_build
batch.selected_build=lambda n:NEW if n==8 else original_selected(n)
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
    published=load(BASE/'study-v0.7/publication_20261030_r3/POST_PUBLICATION_STATE.json')
    for r in published['releases']:
        if not r['draft']:
            need(batch.signature(next(x for x in state['releases'] if x['id']==r['id']))==batch.signature(r),'Published release changed: '+r['tag_name'])
    need(state['tags']==published['tags'],'Tags changed after the authorized v0.7 publication')
    r=next(x for x in state['releases'] if x['id']==RELEASE_ID)
    need(r['draft'] and r['tag_name']=='study-v0.8','v0.8 must remain the existing draft')
    if baseline:
        a={r['id']:batch.signature(r) for r in baseline['releases'] if r['id']!=RELEASE_ID}
        b={r['id']:batch.signature(r) for r in state['releases'] if r['id']!=RELEASE_ID}
        need(a==b,'Another release changed during this revision')

def guard_other_releases():
    check_state(capture(),load(NEW/'receipts/REMOTE_BASELINE_V08_REVISION.json'))

def seal():
    need(not (NEW/'dist').exists(),'Preserve sealed assets');(NEW/'dist').mkdir()
    packages=[]
    for kind in ('Code','Documentation','Study'):
        root=NEW/'assembly'/('QPathformer_v0.8_'+kind)
        manifest=load(OLD/'assembly'/root.name/'MANIFEST.json')
        manifest['files']=[dict(path=n,**ii) for n,ii in files(root).items()]
        save(root/'MANIFEST.json',manifest)
        write(root/'CHECKSUMS.sha256',''.join(ii['sha256']+'  '+n+'\n' for n,ii in files(root).items()))
        zp=NEW/'dist'/(root.name+'.zip')
        with zipfile.ZipFile(zp,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for n in files(root):
                zi=zipfile.ZipInfo(root.name+'/'+n,(2026,10,30,12,0,0));zi.create_system=3;zi.external_attr=0o100644<<16;zi.compress_type=zipfile.ZIP_DEFLATED;z.writestr(zi,(root/n).read_bytes(),compresslevel=9)
        record=load(OLD/'dist'/(root.name+'.seal.json'))
        need(record['schema']=='qpath-package-seal-1','Unexpected v0.8 seal')
        record.update(zip=dict(path=zp.name,**info(zp)),actual_build_root=str(NEW),actual_assembly_root=str(root),created_at_utc=now())
        for key in ('internal_manifest','internal_checksums','source_map'):record[key].update(info(root/record[key]['path'].removeprefix(root.name+'/')))
        save(zp.with_suffix('.seal.json'),record)
        result=batch.verify_package(NEW/'dist'/(root.name+'.zip'),NEW/'dist'/(root.name+'.seal.json'))
        result['reused_unchanged']=False;result['actual_build_root']=str(NEW);packages.append(result)
    save(NEW/'receipts/BUILD_VERIFICATION.json',dict(status='PASS_SEALED_PACKAGE_CHAINS',packages=packages))
    save(NEW/'receipts/PACKAGE_INDEX.json',dict(study_version='v0.8',selection_root=str(NEW),status='SEALED_AWAITING_FRESH_STARTUP',packages=packages,rebuilt_assets=6,reused_assets=0))

def build():
    state=capture();check_state(state);need(not NEW.exists(),'Preserve any existing successor')
    prelim=load(HERE/'v08_r3_audit/PRELIMINARY_R2_CHECKS.json');need(prelim['status']=='PASS','Preliminary checks absent')
    for name in ('HELPER_TEST_RESULTS.json','POWERSHELL_TEST_RESULTS.json'):need(load(HELPERS/name)['status'].startswith('PASS'),'Helper checks absent')
    clarification=load(HERE/'v08_r3_audit/VISUAL_REVIEW_CLARIFICATION.json');need(clarification['status']=='PASS_V08_DISCLOSURE_CLARIFIED','Page clarification incomplete')
    NEW.mkdir();save(NEW/'receipts/REMOTE_BASELINE_V08_REVISION.json',state)
    old_assets={p.name:info(p) for p in (OLD/'dist').iterdir()};prior={}
    for kind in ('Code','Documentation','Study'):
        name='QPathformer_v0.8_'+kind
        batch.verify_package(OLD/'dist'/(name+'.zip'),OLD/'dist'/(name+'.seal.json'))
        with zipfile.ZipFile(OLD/'dist'/(name+'.zip')) as z:
            for n in z.namelist():
                p=(NEW/'assembly'/n).resolve();need(p.is_relative_to((NEW/'assembly').resolve()),'Unsafe extraction');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
        root=NEW/'assembly'/name;prior[name]=files(root)
        for n in ('MANIFEST.json','CHECKSUMS.sha256'):(root/n).unlink()
    for p in PROSE.glob('QPathformer_v0.8_*/**/*'):
        if p.is_file():
            rel=p.relative_to(PROSE);need(len(rel.parts)==2,'Unexpected prose path');cp(p,NEW/'assembly'/rel)
    code=NEW/'assembly/QPathformer_v0.8_Code'
    for name in ('startup_check.py','verify_package.py'):cp(HELPERS/name,code/'tools'/name)
    cp(HELPERS/'QUICKSTART.md',code/'QUICKSTART.md')
    dep=load(code/'DEPENDENCY_INVENTORY.json');imports={};pyfiles=list(code.rglob('*.py'));need(len(pyfiles)==85,'Expected 85 selected Python files')
    for p in pyfiles:
        rel=p.relative_to(code).as_posix()
        for node in ast.walk(ast.parse(p.read_text('utf-8-sig'))):
            names=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else ([node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module and node.level==0 else [])
            for name in names:imports.setdefault(name,set()).add(rel)
    dep['all_import_roots']=sorted(imports);dep['direct_import_inventory']={k:sorted(v) for k,v in sorted(imports.items())}
    dep['embedded_startup_import_roots']=dict(path='tools/startup_check.py',roots=sorted('socket json sys numpy scipy circuits models routers reference_v03 runpy'.split()),scope='Explicit imports in generated bounded child programs; target CLI source imports are listed in the direct inventory.')
    dep['inventory_scope']=dict(scientific_python_files=83,package_helpers=2,boundary='Direct inventory includes local and standard-library modules, not only third-party requirements. Original helper imports were already included; this revision refreshes changed helper imports and separately records embedded programs.')
    save(code/'DEPENDENCY_INVENTORY.json',dep)
    selected=load(code/'SOURCE_SELECTION.json');need(len(selected['selected'])==87,'Unexpected source selection')
    selected['selection_description']='87 retained implementation/protocol files; payload/study/execution/README_EXECUTION.txt is an additional guidance file separately bound by SOURCE_MAP.json, GUIDANCE_LICENSE_SCOPE.json and complete inventories.';save(code/'SOURCE_SELECTION.json',selected)
    inherited=load(code/'INHERITED_LICENSE_MAP.json');previous=BASE/'study-v0.7/draft_20261030_r3/assembly/QPathformer_v0.7_Code';scope=load(previous/'CODE_LICENSE_SCOPE.json')
    lineage=[]
    for name in ('startup_check.py','verify_package.py'):
        rel='tools/'+name;e=next(e for e in scope['files'] if e['path']==rel);need(info(previous/rel)=={k:e[k] for k in ('bytes','sha256')},'Prior helper scope differs')
        if name=='verify_package.py':need((code/rel).read_text('utf-8')==(previous/rel).read_text('utf-8'),'Verifier source differs beyond newlines')
        relation='Verifier source reused with newline normalization only' if name=='verify_package.py' else 'Adapted guarded startup structure; original v0.8 numerical/CLI scope retained'
        lineage.append(dict(path=rel,current=info(code/rel),source_path=str(previous/rel),source_identity=info(previous/rel),scope_record=str(previous/'CODE_LICENSE_SCOPE.json'),scope_record_identity=info(previous/'CODE_LICENSE_SCOPE.json'),license='Q-Pathformer Platform License 1.0',relation=relation,adopted_study='v0.7'))
    inherited['package_helper_lineage']=lineage;save(code/'INHERITED_LICENSE_MAP.json',inherited)
    changes=[];source_bindings=[]
    for kind in ('Code','Documentation','Study'):
        root=NEW/'assembly'/('QPathformer_v0.8_'+kind)
        for p in root.glob('*_LICENSE_SCOPE.json'):
            scope=load(p)
            for e in scope['files']:e.update(info(root/e['path']))
            save(p,scope)
        adoption=load(root/'LICENSE_ADOPTION.json')
        for e in adoption['satisfied_by']:e.update(info(root/e['path']))
        save(root/'LICENSE_ADOPTION.json',adoption)
        source=load(root/'SOURCE_MAP.json');oldmap={e['path']:e for e in source['files']};mapped=[]
        for n,ii in files(root).items():
            if n=='SOURCE_MAP.json':continue
            e=oldmap.get(n);need(e is not None,'Unexpected package member')
            if prior[root.name][n]!=ii:e=dict(path=n,source_path=str(root/n),source_identity=ii,output_identity=ii,previous_edition_identity=prior[root.name][n],transformation='Reviewed current wrapper/helper or refreshed binding; scientific and historical source unchanged')
            mapped.append(e)
        source.update(actual_build_root=str(NEW),files=mapped);save(root/'SOURCE_MAP.json',source)
        source_bindings.append(dict(package=root.name,source_map=info(root/'SOURCE_MAP.json')))
        for n,ii in prior[root.name].items():
            if n.startswith(('payload/','source/','reports/','provenance/','LICENSES/')):need(info(root/n)==ii,'Preserved source changed '+n)
        changes.extend(dict(package=root.name,path=n,previous=prior[root.name].get(n),current=ii) for n,ii in files(root).items() if prior[root.name].get(n)!=ii)
    for p in (OLD/'report').iterdir():
        if p.is_file() and p.suffix in ('.json','.md'):cp(p,NEW/'report'/p.name)
    cp(HERE/'v08_r3_audit/VISUAL_REVIEW_CLARIFICATION.json',NEW/'report/VISUAL_REVIEW_CLARIFICATION.json')
    for e in clarification['targeted_evidence']:
        dest=NEW/'qa/targeted_report_review'/Path(e['path']).name;cp(e['path'],dest);e['path']=str(dest)
    for name in ('review_pages.py','record_clarification.py'):cp(HERE/'v08_r3_audit'/name,NEW/'tools'/name)
    cp(PROSE/'stage_prose.py',NEW/'tools/stage_prose.py')
    inv=load(OLD/'receipts/SOURCE_INVENTORY.json')
    for e in inv['selected_source_verification']['files']:need(info(e['path'])=={k:e[k] for k in ('bytes','sha256')},'Selected source changed')
    cp(OLD/'receipts/SOURCE_INVENTORY.json',NEW/'receipts/SOURCE_INVENTORY.json')
    save(NEW/'receipts/REVISED_SOURCE_BINDINGS.json',dict(status='PASS_SELECTED_ORIGINALS_RECONFIRMED',source_inventory=dict(path=str(OLD/'receipts/SOURCE_INVENTORY.json'),**info(OLD/'receipts/SOURCE_INVENTORY.json')),current_source_maps=source_bindings,study_origin=str(NEW),full_archive_rescanned=False))
    cp(NOTES,NEW/'review'/NOTES.name);cp(HERE/'v08_r3_audit/PRELIMINARY_R2_CHECKS.json',NEW/'receipts/PRELIMINARY_R2_CHECKS.json')
    for name in ('HELPER_TEST_RESULTS.json','POWERSHELL_TEST_RESULTS.json'):cp(HELPERS/name,NEW/'receipts'/name)
    for p in HELPERS.glob('*.py'):cp(p,NEW/'tools'/p.name)
    for p in PROSE.glob('*.json'):cp(p,NEW/'receipts'/p.name)
    cp(PROSE/'RELEASE_BODY.md',NEW/'RELEASE_NOTES.md')
    write(NEW/'PREPARATION_BRIEF.md','# v0.8 private draft revision\n\nApply the user-approved packaging and explanatory corrections using the established release format. Rebuild all three package wrappers; preserve the report PDF/DOCX bytes unchanged. Preserve all 83 scientific Python files, original protocols, report, historical records, legal texts and adoption decisions. Refresh changed scope identities. Retain the v0.8 seal/source-map schemas and original source-version names. Publication is not authorized. Repository remains private; v0.9.5 stays Latest.\n')
    save(NEW/'receipts/REVISION_RECORD.json',dict(status='APPROVED_CORRECTIONS_PREPARED',review=dict(path=str(NOTES),**info(NOTES)),authorization='User requested applying v0.8 notes and preparing an updated private draft for final check, retaining private visibility and v0.9.5 Latest.',previous_build=str(OLD),actual_build_root=str(NEW),prior_assets=old_assets,changed_files=changes,scientific_python_files_unchanged=83,study_assets_reused=False,adoption_decisions_unchanged=True,publication_authorized=False,checked_at_utc=now()))
    cp(Path(__file__),NEW/'tools/v08_r3.py');seal();clarification.update(study_zip=info(NEW/'dist/QPathformer_v0.8_Study.zip'),study_seal=info(NEW/'dist/QPathformer_v0.8_Study.seal.json'),study_assets_unchanged=False);save(NEW/'report/VISUAL_REVIEW_CLARIFICATION.json',clarification);need(old_assets=={p.name:info(p) for p in (OLD/'dist').iterdir()},'Prior assets changed');guard_other_releases()
    print(json.dumps(dict(status='SEALED_V08_R3',changed_files=len(changes),rebuilt_assets=6,reused_assets=0)))

def review_summary(startup):
    write(NEW/'REVISION_SUMMARY.md','# v0.8 r3 revision summary\n\nThe existing private draft now uses the established release format. Current explanations distinguish priority sampling, population replication, frozen model routing, conversion/timing limits and Q-Path Multiplier - Elastic Task Execution Layer (ETEL) v0.1 using retained source version 0.2.0.\n\nBoth packaging helpers use unconditional validation. Strict inventories reject duplicate and malformed records. Startup checks package integrity before and after a two-input numerical smoke check and three CLI help paths. Every selected Python file is parsed; receipt creation is exclusive and external. The startup scope does not include the v0.6 six-test suite or ETEL fit/recovery execution.\n\nAll 83 retained scientific Python files, protocols and legal texts are unchanged. All three ZIP/seal pairs are rebuilt with current scope bindings; Study START_HERE adds PDF viewing guidance while the report PDF/DOCX remain byte-identical. The external visual-review clarification identifies the cross-study v0.9 sentence in historical metadata and binds the unchanged v0.8 report. Only pages 37 and 38 received new targeted visual/text checks, not a new all-page report review.\n\nFresh final startup passed its numerical smoke check and all three CLI help paths, with 85 Python files parsed. NumPy '+startup['numpy_version']+'; SciPy '+startup['scipy_version']+'. No training, official scoring, sampling, timing benchmark, ETEL job or QPU work ran.\n\n[Final startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Package identities](receipts/PACKAGE_INDEX.json) · [Disclosure clarification](report/VISUAL_REVIEW_CLARIFICATION.json) · [Helper probes](receipts/HELPER_TEST_RESULTS.json).\n\nThis remains an unpublished private draft for the owner final check. v0.9.5 remains Latest.\n')

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
    code = dest / 'QPathformer_v0.8_Code'
    receipt = NEW / 'receipts/QPathformer_v0.8_Code.startup.json'
    command = [str(PYTHON), '-B', str(code / 'tools/startup_check.py'), '--output', str(receipt)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    env.pop('PYTHONOPTIMIZE', None)
    r = subprocess.run(command, cwd=code, env=env, capture_output=True, text=True, timeout=500)
    save(NEW / 'receipts/STARTUP_INVOCATION.json', dict(command=command, cwd=str(code), returncode=r.returncode, stdout=r.stdout, stderr=r.stderr))
    need(before == files(dest), 'Startup changed package bytes or membership')
    need(r.returncode == 0 and receipt.is_file() and load(receipt)['status'] == 'PASS', 'Genuine startup failed: '+r.stdout+' '+r.stderr)
    cs = next(e for e in packages if e['package'].endswith('_Code'))
    startup = load(receipt)
    need(len(startup['checks']) == 4, 'Expected numerical smoke plus three CLI checks')
    fresh = dict(status='PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP', checked_at_utc=now(), packages=packages, code_zip=cs['zip'], code_seal=cs['seal'], code_startup_receipt=dict(path=str(receipt), **info(receipt)), package_bytes_unchanged=True, receipt_outside_entire_package=True, scope=startup['scope'], not_verified=startup['not_verified'])
    save(NEW / 'receipts/FRESH_PACKAGE_VERIFICATION.json', fresh)
    pi = load(NEW / 'receipts/PACKAGE_INDEX.json')
    pi.update(status='READY_FOR_DRAFT_REVIEW', startup_binding=dict(path=str(NEW / 'receipts/FRESH_PACKAGE_VERIFICATION.json'), **info(NEW / 'receipts/FRESH_PACKAGE_VERIFICATION.json')))
    save(NEW / 'receipts/PACKAGE_INDEX.json', pi)
    batch.verify_study(8)
    need(startup['parsed_python_files']==85 and startup['cli_help_checks']==3 and startup['numerical_input_records']==2,'Unexpected genuine startup scope')
    review_summary(startup)
    print(json.dumps(dict(status=fresh['status'], startup_checks=len(startup['checks']), code_zip=cs['zip'])))

def commit():
    guard_other_releases()
    need(load(NEW / 'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json')['status']=='PASS', 'Separate audit absent')
    need(not batch.git('status','--porcelain').strip(), 'Preparation checkout dirty')
    record=batch.verify_study(8)
    path='release_preparation/study-v0.8/revisions/'+NEW.name
    dest=batch.R/path
    need(not dest.exists(),'Successor review tree already exists; preserve it')
    cp(Path(__file__),NEW/'tools/v08_r3.py')
    cp(HERE/'v08_r3_audit/audit.py',NEW/'tools/independent_audit.py')
    for name in ('startup_check.py','verify_package.py'):cp(HELPERS/name,NEW/'tools'/name)
    write(NEW/'tools/README.md','# Preparation and audit tools\n\nThe preparation and separate audit algorithms were run by the same agent; no second reviewer is claimed. These are retained implementation snapshots for the recorded local checks. The helper regression harness uses the recorded historical Q2 fixture path and the two adjacent helper copies. The preparation and independent audit scripts retain their actual local environment paths; they are evidence, not a portable full-study runner. Genuine final startup is separately recorded against the sealed Code ZIP.\n')
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
    save(dest/'PACKAGE_INDEX.json',dict(study_version='v0.8',repository_edition='v1.0',packages=[dict(package=e['package'],zip=dict(path=Path(e['zip']['path']).name,**info(e['zip']['path'])),seal=dict(path=Path(e['seal']['path']).name,**info(e['seal']['path'])),actual_build_root=load(e['seal']['path'])['actual_build_root']) for e in record['packages']],selection_root=str(NEW)))
    cp(batch.B/'OWNER_LICENSE_AUTHORIZATION.json',dest/'OWNER_LICENSE_AUTHORIZATION.json')
    write(dest/'README.md','# Study v0.8 r3 review records\n\nThis successor corrects optimization-sensitive integrity checks, scientific wording, both package helpers and the PowerShell quickstart. Current package explanations and publisher-review guidance are updated. All 83 scientific Python files, the complete selected scientific payload, report PDF/DOCX, legal texts retain their reviewed bytes. Adoption decisions remain unchanged with refreshed scope bindings. The Study wrapper adds PDF viewing guidance; both report files are reused unchanged. Historical all-page QA is retained; pages 37 and 38 received targeted visual/text checks for the external disclosure clarification.\n\n[Package identities](PACKAGE_INDEX.json) · [Separate successor audit](receipts/INDEPENDENT_SUCCESSOR_AUDIT.json) · [Fresh startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Helper regression probes](receipts/HELPER_TEST_RESULTS.json) · [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).\n\nThe exact package contents, including selected source code, are committed under packages/. ZIPs and seals are private draft release assets. r2 remains preserved as historical evidence. Main, other releases, visibility and the Latest designation remain unchanged. This revision does not publish the release.\n')
    batch.git('add',path);batch.git('commit','-m','Prepare corrected v0.8 r3 packages and verified source')
    commit=batch.git('rev-parse','HEAD').decode().strip();batch.git('push','origin',batch.BRANCH)
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==commit,'Remote branch differs')
    guard_other_releases()
    save(NEW/'receipts/REVIEW_BRANCH.json',dict(branch=batch.BRANCH,target_commit=commit,base_main=batch.EXPECTED_BASE,record_path=path,checked_at_utc=now()))
    print(json.dumps(dict(target_commit=commit)))

def upload():
    guard_other_releases()
    for kind in ('Study','Documentation','Code'):
        batch.verify_package(NEW/'dist'/f'QPathformer_v0.8_{kind}.zip',NEW/'dist'/f'QPathformer_v0.8_{kind}.seal.json')
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
    need(r['draft'] and r['tag_name']=='study-v0.8', 'Expected existing private draft')
    save(NEW / 'receipts/DRAFT_BEFORE_RESUME.json', r)
    payload = dict(tag_name='study-v0.8', target_commitish=target, name=TITLE, body=body, draft=True, prerelease=False, make_latest='false')
    req = NEW / 'receipts/RELEASE_MUTATION_REQUEST.json'; save(req,payload)
    r = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}', '--method','PATCH','--input',req)
    batch.check_release(r,8,target,TITLE)
    hist = dict(release_id=RELEASE_ID,status='SUPERSEDED_DRAFT_ASSETS_PRESERVED_BEFORE_REPLACEMENT',assets=[])
    for p in sorted((NEW / 'dist').iterdir()):
        current = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}')
        batch.check_release(current,8,target,TITLE)
        assets = {a['name']:a for a in current['assets']}
        if p.name in assets:
            a = assets[p.name]
            if a['size']==info(p)['bytes'] and a.get('digest')=='sha256:'+info(p)['sha256']: continue
            old = batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','-H','Accept: application/octet-stream',timeout=180)
            need(batch.bytes_info(old)==info(OLD/'dist'/p.name),'Existing draft asset differs from reviewed r02')
            oldpath = NEW/'qa/superseded_remote_assets'/str(a['id'])/p.name
            oldpath.parent.mkdir(parents=True,exist_ok=True); oldpath.write_bytes(old)
            hist['assets'].append(dict(id=a['id'],name=a['name'],path=str(oldpath),**batch.bytes_info(old),preserved_at_utc=now(),replacement=dict(path=str(p),**info(p))))
            save(NEW/'receipts/SUPERSEDED_REMOTE_ASSETS.json',hist)
            batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','--method','DELETE')
        batch.run(batch.GH,'release','upload','study-v0.8',p,'--repo',batch.NAME,timeout=180)
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
        d=NEW/'qa/authenticated_downloads';batch.verify_package(d/f'QPathformer_v0.8_{kind}.zip',d/f'QPathformer_v0.8_{kind}.seal.json')
    guard_other_releases()
    receipt=dict(schema='qpath-draft-release-1',status='PRIVATE_DRAFT_UPLOADED_AND_AUTHENTICATED_DOWNLOAD_VERIFIED',study_version='v0.8',repository=dict(id=batch.REPO_ID,name=batch.NAME,private=True),draft_release=dict(id=RELEASE_ID,url=r['html_url'],tag_name='study-v0.8',target_commitish=target,name=TITLE,draft=True,prerelease=False,published_at=None),assets=downloaded,branch=batch.BRANCH,main_unchanged=batch.EXPECTED_BASE,protected_releases_unchanged=True,other_drafts_unchanged=True,v095_remains_latest=True,checked_at_utc=now(),publication_authorized=False)
    save(NEW/'receipts/DRAFT_RELEASE.json',receipt)
    cp(NEW/'receipts/DRAFT_RELEASE.json',batch.R/path/'DRAFT_RELEASE.json')
    cp(NEW/'receipts/SUPERSEDED_REMOTE_ASSETS.json',batch.R/path/'SUPERSEDED_REMOTE_ASSETS.json')
    batch.git('add',path);batch.git('commit','-m','Record verified v0.8 r3 private draft replacements');batch.git('push','origin',batch.BRANCH)
    evidence=batch.git('rev-parse','HEAD').decode().strip()
    payload['body']=body.rstrip()+f'\n\n[Authenticated draft assets](https://github.com/{batch.NAME}/blob/{evidence}/{path}/DRAFT_RELEASE.json).\n'
    req2=NEW/'receipts/RELEASE_RECEIPT_LINK_REQUEST.json';save(req2,payload)
    r=batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}','--method','PATCH','--input',req2)
    batch.check_release(r,8,target,TITLE)
    verified=[]
    for commit,relative in [(target,'README.md'),(target,'PACKAGE_INDEX.json'),(target,'receipts/PACKAGE_INDEX.json'),(target,'receipts/FRESH_PACKAGE_VERIFICATION.json'),(target,'receipts/QPathformer_v0.8_Code.startup.json'),(target,'receipts/ROOT_PACKAGE_VERIFICATION.json'),(target,'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json'),(evidence,'DRAFT_RELEASE.json')]:
        got=batch.api(f'repos/{batch.NAME}/contents/{path}/{relative}?ref={commit}')
        need(base64.b64decode(got['content'])==(batch.R/path/relative).read_bytes(),'Remote evidence differs '+relative)
        verified.append(dict(commit=commit,path=path+'/'+relative))
    guard_other_releases()
    completion=dict(status='PASS_PRIVATE_DRAFT_READY_FOR_REVIEW',release_id=RELEASE_ID,release_url=r['html_url'],study_version='v0.8',assets_verified=6,draft=True,private=True,target_commit=target,evidence_commit=evidence,links=verified,main_unchanged=True,protected_releases_unchanged=True,other_drafts_unchanged=True,latest='study-v0.9.5',completed_at_utc=now())
    save(NEW/'receipts/COMPLETION.json',completion)
    print(json.dumps(completion,indent=2))

def finalize():
    guard_other_releases()
    need(not batch.git('status','--porcelain').strip(),'Preparation checkout dirty')
    done=load(NEW/'receipts/COMPLETION.json');uploaded=load(NEW/'receipts/DRAFT_RELEASE.json');branch=load(NEW/'receipts/REVIEW_BRANCH.json');fresh=load(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    index=load(batch.B/'REVIEW_INDEX.json');item=next(e for e in index['studies'] if e['study_version']=='v0.8');prior=json.loads(json.dumps(item))
    history=batch.B/'history/before_v08_r3';need(not history.exists(),'Preserve prior review index history')
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md','receipts/COMPLETION.json','tools/batch.py'):cp(batch.B/name,history/name)
    evidence=f'https://github.com/{batch.NAME}/blob/{done["evidence_commit"]}/{branch["record_path"]}/'
    item.update(draft_url=done['release_url'],target_commit=done['target_commit'],local_pack_folder=str(NEW),local_assets=str(NEW/'dist'),record_path=branch['record_path'],evidence_commit=done['evidence_commit'],evidence_url=evidence+'README.md',receipt_url=evidence+'DRAFT_RELEASE.json',assets=uploaded['assets'],startup_status='PASS',startup_scope=fresh['scope'],startup_binding=dict(path=str(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**info(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')))
    scopes=[]
    for kind in ('Study','Documentation','Code'):
        with zipfile.ZipFile(NEW/'dist'/f'QPathformer_v0.8_{kind}.zip') as z:
            prefix=f'QPathformer_v0.8_{kind}/'
            for n in z.namelist():
                rel=n.removeprefix(prefix)
                if '/' not in rel and rel.endswith('_LICENSE_SCOPE.json'):
                    scope=json.loads(z.read(n));scopes.append(dict(package=kind,path=rel,files=len(scope['files']),identity=batch.bytes_info(z.read(n))))
    item['scopes']=scopes
    item['revision_note']='r3 helper, quickstart and current guidance corrections; report/scientific/historical bytes unchanged.'
    index.update(completed_at_utc=now(),latest_revision_note='v0.8 r3 corrections are verified in the private draft. v0.2, v0.3, v0.4, v0.5, v0.6 and v0.7 remain published; v0.9.5 remains Latest; all other selections are unchanged.')
    save(batch.B/'REVIEW_INDEX.json',index)
    for name in ('REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md'):
        text=(batch.B/name).read_text('utf-8')
        for key in ('draft_url','evidence_url','local_pack_folder'):text=text.replace(prior[key],item[key])
        text=text.replace(Path(prior['local_pack_folder']).as_posix(),NEW.as_posix())
        text+='\nThe current v0.8 selection is r3: optimization-safe integrity checks, strict inventory parsing, guarded PowerShell quickstart, exact pre/post startup integrity and corrected release-level metric/verification wording. All three pairs were rebuilt; Study viewing guidance changed while report and scientific bytes remain unchanged. v0.8 remains a private draft.\n'
        write(batch.B/name,text)
    dest=batch.R/'release_preparation/draft_batch_20261029'
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md'):cp(batch.B/name,dest/name)
    for p in history.rglob('*'):
        if p.is_file() and p.name!='LOCAL_REVIEW_INDEX.md':cp(p,dest/'history/before_v08_r3'/p.relative_to(history))
    selector=HERE/'batch.py';source=selector.read_text('utf-8')
    need("8:'draft_20261029_r2'" in source,'Unexpected v0.8 selected-build mapping')
    write(selector,source.replace("8:'draft_20261029_r2'","8:'draft_20261030_r3'",1));cp(selector,batch.B/'tools/batch.py');cp(selector,dest/'tools/batch.py')
    path='release_preparation/study-v0.8/CURRENT.json'
    save(batch.R/path,dict(study_version='v0.8',revision=NEW.name,target_commit=done['target_commit'],evidence_commit=done['evidence_commit'],record_path=branch['record_path'],draft=True,assets=uploaded['assets'],previous_revision=OLD.name))
    need(load(NEW/'receipts/FINAL_BODY_REVIEW.json')['status']=='PASS_GITHUB_RENDERED_BODY_AND_LINKS','Final rendered-body review absent')
    for relative in ('receipts/FINAL_BODY_REVIEW.json','qa/GITHUB_RENDERED_BODY.html'):
        cp(NEW/relative,batch.R/branch['record_path']/relative)
    cp(HERE/'v08_r3_audit/review_draft_body.py',batch.R/branch['record_path']/'tools/review_draft_body.py')
    batch.git('add','release_preparation/draft_batch_20261029',path,branch['record_path']);batch.git('commit','-m','Index reviewed v0.8 successor packages and preserved reports');batch.git('push','origin',batch.BRANCH)
    commit=batch.git('rev-parse','HEAD').decode().strip();guard_other_releases()
    need(not batch.git('status','--porcelain').strip(),'Dirty checkout after index refresh')
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==commit,'Remote branch differs')
    path='release_preparation/draft_batch_20261029/REVIEW_INDEX.md';got=batch.api(f'repos/{batch.NAME}/contents/{path}?ref={commit}')
    need(base64.b64decode(got['content'])==(batch.B/'REVIEW_INDEX.md').read_bytes(),'Remote index differs')
    result=dict(status='PASS_V08_R3_PRIVATE_DRAFT_COMPLETE',release_url=done['release_url'],local_build=str(NEW),revision_summary=str(NEW/'REVISION_SUMMARY.md'),main_unchanged=batch.EXPECTED_BASE,other_releases_unchanged=True,v02_remains_published=True,v03_remains_published=True,v04_remains_published=True,v05_remains_published=True,v06_remains_published=True,v07_remains_published=True,latest='study-v0.9.5',repository_private=True,publication_performed=False,assets_verified=6,rebuilt_assets=6,reused_assets=0,final_evidence_commit=commit,remote_review_index=f'https://github.com/{batch.NAME}/blob/{commit}/{path}',completed_at_utc=now())
    save(NEW/'receipts/FINAL_REVISION_COMPLETION.json',result)
    last=load(history/'receipts/COMPLETION.json');last.update(final_evidence_commit=commit,remote_review_index=result['remote_review_index'],latest_revision='v0.8 r3',completed_at_utc=now());save(batch.B/'receipts/COMPLETION.json',last)
    print(json.dumps(result,indent=2))

if __name__=='__main__':globals()[sys.argv[1]]()
