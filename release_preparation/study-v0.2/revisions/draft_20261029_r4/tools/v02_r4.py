"""Prepare only the reviewed v0.2 successor; preserve earlier evidence."""
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import batch
sys.path.insert(0, str(HERE / 'v02_04'))
import package

BASE = batch.BASE
OLD = BASE / 'study-v0.2/draft_20261029_r3'
NEW = BASE / 'study-v0.2/draft_20261029_r4'
HELPERS = HERE / 'v02_r4_helpers'
PROSE = HERE / 'v02_r4_prose'
PYTHON = Path(r'C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe')
TITLE = 'Q-Pathformer Study v0.2 — Improvement Study and Baseline Comparison'
RELEASE_ID = 427657373
original_selected = batch.selected_build
batch.selected_build = lambda n: NEW if n == 2 else original_selected(n)
package.bpath = lambda n: NEW if n == 2 else original_selected(n)
need, info, load, save, write, now = batch.need, batch.info, batch.load, batch.save, batch.write, batch.now

def files(root):
    return {p.relative_to(root).as_posix(): info(p) for p in sorted(root.rglob('*')) if p.is_file()}

def cp(src, dst):
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

def guard_other_releases():
    batch.guard()
    baseline = load(NEW / 'receipts/REMOTE_BASELINE_V02_REVISION.json')
    current = batch.api(f'repos/{batch.NAME}/releases?per_page=100')
    before = {r['id']: batch.signature(r) for r in baseline['releases'] if r['id'] != RELEASE_ID}
    after = {r['id']: batch.signature(r) for r in current if r['id'] != RELEASE_ID}
    need(before == after, 'Another release changed during v0.2 revision')

def build():
    batch.guard()
    need(not NEW.exists(), 'Preserve existing successor; do not overwrite')
    need((HELPERS / 'startup_check.py').is_file() and (HELPERS / 'verify_package.py').is_file(), 'Corrected helpers absent')
    need((PROSE / 'release_body_template.md').is_file(), 'Corrected release prose absent')
    NEW.mkdir()
    save(NEW / 'receipts/REMOTE_BASELINE_V02_REVISION.json', dict(captured_at_utc=now(), releases=batch.api(f'repos/{batch.NAME}/releases?per_page=100')))
    old_assets = {p.name: info(p) for p in (OLD / 'dist').iterdir()}
    prior = {}
    for zp in sorted((OLD / 'dist').glob('*.zip')):
        batch.verify_package(zp, zp.with_suffix('.seal.json'))
        with zipfile.ZipFile(zp) as z:
            for n in z.namelist():
                p = NEW / 'assembly' / n
                need(p.resolve().is_relative_to((NEW / 'assembly').resolve()), 'Unsafe extraction')
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(n))
        root = NEW / 'assembly' / zp.stem
        prior[root.name] = files(root)
        for name in ('MANIFEST.json', 'CHECKSUMS.sha256'):
            (root / name).unlink()
    # Include changed wrappers in nested provenance directories too.
    for p in sorted(PROSE.glob('QPathformer_v0.2_*/**/*')):
        if p.is_file(): cp(p, NEW / 'assembly' / p.relative_to(PROSE))
    code = NEW / 'assembly/QPathformer_v0.2_Code'
    for name in ('startup_check.py', 'verify_package.py'):
        cp(HELPERS / name, code / 'tools' / name)
    p = code / 'QUICKSTART.md'
    write(p, p.read_text('utf-8') + '\nThe startup helper reserves a new receipt exclusively before work, verifies exact package integrity before and after the checks, and records failures or timeouts. Use a new output pathname for each attempt. A pre-existing receipt is preserved. Both the receipt and any work outputs must remain outside the entire package.\n')
    p = code / 'DEPENDENCIES.md'
    write(p, p.read_text('utf-8') + '\nThe direct import inventory includes all 40 retained scientific Python files and both package helpers. Helper imports use the Python standard library and local package helpers; they add no third-party dependency. Historical recorded versions and bounded startup observations remain distinct.\n')
    dep = load(code / 'DEPENDENCY_INVENTORY.json')
    imports = {}
    pyfiles = sorted(code.rglob('*.py'))
    need(len(pyfiles) == 42, 'Expected exactly 42 Python files')
    for p in pyfiles:
        rel = p.relative_to(code).as_posix()
        for node in ast.walk(ast.parse(p.read_text('utf-8-sig'))):
            names = [a.name.split('.')[0] for a in node.names] if isinstance(node, ast.Import) else ([node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else [])
            for name in names: imports.setdefault(name, set()).add(rel)
    dep['direct_import_inventory'] = {k: sorted(v) for k, v in sorted(imports.items())}
    dep['inventory_scope'] = dict(scientific_python_files=40, package_helpers=2, granularity='Syntactic top-level import roots; local modules and the standard library are included, not asserted third-party dependencies.')
    save(code / 'DEPENDENCY_INVENTORY.json', dep)
    inherited = package.inherit(code, [p.relative_to(code).as_posix() for p in pyfiles])
    scope = load(code / 'CODE_LICENSE_SCOPE.json')
    scope['inherited_exact_matches'] = len(inherited['exact_whole_file_matches'])
    scope['shared_expression_records'] = len(inherited['shared_expression_evidence'])
    for e in scope['files']: e.update(info(code / e['path']))
    save(code / 'CODE_LICENSE_SCOPE.json', scope)
    changes = []
    for root in sorted((NEW / 'assembly').iterdir()):
        for p in root.glob('*_LICENSE_SCOPE.json'):
            scope = load(p)
            for e in scope['files']: e.update(info(root / e['path']))
            save(p, scope)
        oldmap = load(root / 'SOURCE_MAP.json')
        mapped = {e['path']: e for e in oldmap['files']}
        mapped_out = []
        for n, ii in files(root).items():
            if n == 'SOURCE_MAP.json': continue
            e = mapped.get(n)
            if e is None or {k:e[k] for k in ('bytes','sha256')} != ii:
                e = dict(path=n, source_absolute_path=str(root / n), source_identity=ii, **ii, handling='Reviewed packaging correction or refreshed exact scope/inventory in this Q2 successor; scientific source and report bytes preserved.')
                if n in prior[root.name]: e['previous_edition_identity'] = prior[root.name][n]
            mapped_out.append(e)
        oldmap.update(actual_build_root=str(NEW), files=mapped_out)
        save(root / 'SOURCE_MAP.json', oldmap)
        for n, ii in files(root).items():
            if prior[root.name].get(n) != ii:
                changes.append(dict(package=root.name, path=n, previous=prior[root.name].get(n), current=ii))
        if root.name.endswith('_Code'):
            selected = [n for n in prior[root.name] if n.startswith('payload/')]
            need(all(info(root / n) == prior[root.name][n] for n in selected), 'Scientific payload changed')
        if root.name.endswith('_Study'):
            need(all(info(root / n) == prior[root.name][n] for n in prior[root.name] if n.startswith('reports/')), 'Report changed')
    cp(OLD / 'receipts/SOURCE_INVENTORY.json', NEW / 'receipts/SOURCE_INVENTORY.json')
    for p in (OLD / 'report').glob('*.json'): cp(p, NEW / 'report' / p.name)
    report_root = NEW / 'assembly/QPathformer_v0.2_Study'
    save(NEW / 'report/REPORT_PRESERVATION_BINDING.json', dict(status='IDENTICAL_REPORT_BYTES_HISTORICAL_VISUAL_QA_RETAINED', prior_review=dict(path=str(OLD / 'report/REPORT_REVIEW.json'), **info(OLD / 'report/REPORT_REVIEW.json')), files=[dict(path=n, **info(report_root/n)) for n in files(report_root) if n.startswith('reports/')], note='PDF and DOCX are byte-identical to r3. The prior render/page-review records retain their actual paths and dates; no new rendering or visual review is claimed.'))
    save(NEW / 'receipts/REVISION_RECORD.json', dict(status='REVIEW_CORRECTIONS_PREPARED', previous_build=str(OLD), actual_build_root=str(NEW), checked_at_utc=now(), authorization='User approved the review and requested resuming the v0.2 work. Publication and visibility changes remain outside this revision.', adopted_license_scheme_unchanged=True, adoption_records_preserved=True, report_pdf_docx_unchanged=True, scientific_python_files_unchanged=40, all_scientific_payload_unchanged=True, previous_assets=old_assets, changed_files=changes, previous_evidence_preserved=True))
    write(NEW / 'PREPARATION_BRIEF.md', '# v0.2 reviewed successor\n\nThis revision applies the accepted scientific-summary and package-helper corrections. The 40 scientific Python files, all retained scientific payload, the report PDF/DOCX, legal texts and historical adoption records remain unchanged. Scope identities, dependency helper mappings, source maps, manifests, ZIPs, seals and startup bindings are refreshed for the affected packages. Previous sealed evidence is preserved.\n\nOnly the v0.2 private draft is updated. Main, other releases, repository visibility and the Latest designation remain unchanged. Publication is not authorized.\n')
    body = (PROSE / 'release_body_template.md').read_text('utf-8')
    for kind, upper in [('Study','STUDY'),('Documentation','DOCUMENTATION'),('Code','CODE')]:
        body = body.replace(f'[{kind} ZIP]({{{{{upper}_ZIP_URL}}}})',f'`QPathformer_v0.2_{kind}.zip`')
        body = body.replace(f'[{kind} seal]({{{{{upper}_SEAL_URL}}}})',f'`QPathformer_v0.2_{kind}.seal.json`')
    body = body.replace(' · [Authenticated draft upload record]({{DRAFT_RELEASE_URL}})', '')
    links = {'PACKAGE_INDEX_URL':'PACKAGE_INDEX.json','OWNER_LICENSE_AUTHORIZATION_URL':'OWNER_LICENSE_AUTHORIZATION.json','ROOT_PACKAGE_VERIFICATION_URL':'receipts/ROOT_PACKAGE_VERIFICATION.json','FRESH_PACKAGE_VERIFICATION_URL':'receipts/FRESH_PACKAGE_VERIFICATION.json','REPORT_REVIEW_URL':'report/REPORT_REVIEW.json','SOURCE_INVENTORY_URL':'receipts/SOURCE_INVENTORY.json'}
    for key, value in links.items(): body = body.replace('{{'+key+'}}',value)
    need('{{' not in body, 'Unresolved release template fields')
    write(NEW / 'RELEASE_NOTES.md', body)
    cp(PROSE / 'PROSE_CHANGES.json', NEW / 'receipts/PROSE_CHANGES.json')
    cp(HELPERS / 'HELPER_TEST_RESULTS.json', NEW / 'receipts/HELPER_TEST_RESULTS.json')
    cp(HELPERS / 'test_helpers.py', NEW / 'tools/test_helpers.py')
    cp(Path(__file__), NEW / 'tools/v02_r4.py')
    package.seal(2)
    need(old_assets == {p.name: info(p) for p in (OLD / 'dist').iterdir()}, 'Prior assets changed')
    guard_other_releases()
    print(json.dumps(dict(status='SEALED_V02_R4', changed_files=len(changes), assets=6)))

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
    code = dest / 'QPathformer_v0.2_Code'
    receipt = NEW / 'receipts/QPathformer_v0.2_Code.startup.json'
    command = [str(PYTHON), '-B', str(code / 'tools/startup_check.py'), '--output', str(receipt)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    env.pop('PYTHONOPTIMIZE', None)
    r = subprocess.run(command, cwd=code, env=env, capture_output=True, text=True, timeout=500)
    save(NEW / 'receipts/STARTUP_INVOCATION.json', dict(command=command, cwd=str(code), returncode=r.returncode, stdout=r.stdout, stderr=r.stderr))
    need(before == files(dest), 'Startup changed package bytes or membership')
    need(r.returncode == 0 and receipt.is_file() and load(receipt)['status'] == 'PASS', 'Genuine startup failed: '+r.stdout+' '+r.stderr)
    cs = next(e for e in packages if e['package'].endswith('_Code'))
    startup = load(receipt)
    need(len(startup['checks']) == 4, 'Expected all four genuine startup checks')
    fresh = dict(status='PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP', checked_at_utc=now(), packages=packages, code_zip=cs['zip'], code_seal=cs['seal'], code_startup_receipt=dict(path=str(receipt), **info(receipt)), package_bytes_unchanged=True, receipt_outside_entire_package=True, scope=startup['scope'], not_verified=startup['not_verified'])
    save(NEW / 'receipts/FRESH_PACKAGE_VERIFICATION.json', fresh)
    pi = load(NEW / 'receipts/PACKAGE_INDEX.json')
    pi.update(status='READY_FOR_DRAFT_REVIEW', startup_binding=dict(path=str(NEW / 'receipts/FRESH_PACKAGE_VERIFICATION.json'), **info(NEW / 'receipts/FRESH_PACKAGE_VERIFICATION.json')))
    save(NEW / 'receipts/PACKAGE_INDEX.json', pi)
    batch.verify_study(2)
    print(json.dumps(dict(status=fresh['status'], startup_checks=len(startup['checks']), code_zip=cs['zip'])))

def commit():
    guard_other_releases()
    need(load(NEW / 'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json')['status']=='PASS', 'Independent audit absent')
    need(not batch.git('status','--porcelain').strip(), 'Preparation checkout dirty')
    record=batch.verify_study(2)
    path='release_preparation/study-v0.2/revisions/'+NEW.name
    dest=batch.R/path
    need(not dest.exists(),'Successor review tree already exists; preserve it')
    cp(Path(__file__),NEW/'tools/v02_r4.py')
    cp(HERE/'v02_r4_audit/audit.py',NEW/'tools/independent_audit.py')
    for name in ('startup_check.py','verify_package.py'):cp(HELPERS/name,NEW/'tools'/name)
    write(NEW/'tools/README.md','# Preparation and audit tools\n\nThese are retained implementation snapshots for the recorded local checks. The helper regression harness uses the recorded historical Q2 fixture path and the two adjacent helper copies. The preparation and independent audit scripts retain their actual local environment paths; they are evidence, not a portable full-study runner. Genuine final startup is separately recorded against the sealed Code ZIP.\n')
    for folder in ('receipts','report','tools'):
        for p in (NEW/folder).rglob('*'):
            if p.is_file() and p.suffix.lower() in ('.json','.md','.py'):cp(p,dest/folder/p.relative_to(NEW/folder))
    for p in NEW.iterdir():
        if p.is_file() and p.suffix.lower() in ('.json','.md'):cp(p,dest/p.name)
    for e in record['packages']:
        with zipfile.ZipFile(e['zip']['path']) as z:
            for n in z.namelist():
                out=(dest/'packages'/n).resolve()
                need(out.is_relative_to((dest/'packages').resolve()),'Unsafe review extraction')
                out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(n))
    save(dest/'PACKAGE_INDEX.json',dict(study_version='v0.2',repository_edition='v1.0',packages=[dict(package=e['package'],zip=dict(path=Path(e['zip']['path']).name,**info(e['zip']['path'])),seal=dict(path=Path(e['seal']['path']).name,**info(e['seal']['path']))) for e in record['packages']],build_root=str(NEW)))
    cp(batch.B/'OWNER_LICENSE_AUTHORIZATION.json',dest/'OWNER_LICENSE_AUTHORIZATION.json')
    write(dest/'README.md','# Study v0.2 r4 review records\n\nThis successor corrects the active scientific summaries and two package helpers. All 40 scientific Python files, the complete selected scientific payload, report PDF/DOCX, legal texts and historical adoption records retain their reviewed bytes. The report retains its prior visual QA; it was not rerendered.\n\n[Package identities](PACKAGE_INDEX.json) · [Independent successor audit](receipts/INDEPENDENT_SUCCESSOR_AUDIT.json) · [Fresh startup binding](receipts/FRESH_PACKAGE_VERIFICATION.json) · [Helper regression probes](receipts/HELPER_TEST_RESULTS.json) · [Owner licensing record](OWNER_LICENSE_AUTHORIZATION.json).\n\nThe exact package contents, including selected source code, are committed under packages/. ZIPs and seals are private draft release assets. r3 remains preserved as historical evidence. Main, other releases, visibility and the Latest designation remain unchanged. This revision does not publish the release.\n')
    batch.git('add',path);batch.git('commit','-m','Prepare corrected v0.2 r4 packages and verified source')
    commit=batch.git('rev-parse','HEAD').decode().strip();batch.git('push','origin',batch.BRANCH)
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==commit,'Remote branch differs')
    guard_other_releases()
    save(NEW/'receipts/REVIEW_BRANCH.json',dict(branch=batch.BRANCH,target_commit=commit,base_main=batch.EXPECTED_BASE,record_path=path,checked_at_utc=now()))
    print(json.dumps(dict(target_commit=commit)))

def upload():
    guard_other_releases()
    for kind in ('Study','Documentation','Code'):
        batch.verify_package(NEW/'dist'/f'QPathformer_v0.2_{kind}.zip',NEW/'dist'/f'QPathformer_v0.2_{kind}.seal.json')
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
    need(r['draft'] and r['tag_name']=='study-v0.2', 'Expected existing private draft')
    save(NEW / 'receipts/DRAFT_BEFORE_RESUME.json', r)
    payload = dict(tag_name='study-v0.2', target_commitish=target, name=TITLE, body=body, draft=True, prerelease=False, make_latest='false')
    req = NEW / 'receipts/RELEASE_MUTATION_REQUEST.json'; save(req,payload)
    r = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}', '--method','PATCH','--input',req)
    batch.check_release(r,2,target,TITLE)
    hist = dict(release_id=RELEASE_ID,status='SUPERSEDED_DRAFT_ASSETS_PRESERVED_BEFORE_REPLACEMENT',assets=[])
    for p in sorted((NEW / 'dist').iterdir()):
        current = batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}')
        batch.check_release(current,2,target,TITLE)
        assets = {a['name']:a for a in current['assets']}
        if p.name in assets:
            a = assets[p.name]
            if a['size']==info(p)['bytes'] and a.get('digest')=='sha256:'+info(p)['sha256']: continue
            old = batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','-H','Accept: application/octet-stream',timeout=180)
            need(batch.bytes_info(old)==info(OLD/'dist'/p.name),'Existing draft asset differs from reviewed r3')
            oldpath = NEW/'qa/superseded_remote_assets'/str(a['id'])/p.name
            oldpath.parent.mkdir(parents=True,exist_ok=True); oldpath.write_bytes(old)
            hist['assets'].append(dict(id=a['id'],name=a['name'],path=str(oldpath),**batch.bytes_info(old),preserved_at_utc=now(),replacement=dict(path=str(p),**info(p))))
            save(NEW/'receipts/SUPERSEDED_REMOTE_ASSETS.json',hist)
            batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','--method','DELETE')
        batch.run(batch.GH,'release','upload','study-v0.2',p,'--repo',batch.NAME,timeout=180)
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
        d=NEW/'qa/authenticated_downloads';batch.verify_package(d/f'QPathformer_v0.2_{kind}.zip',d/f'QPathformer_v0.2_{kind}.seal.json')
    guard_other_releases()
    receipt=dict(schema='qpath-draft-release-1',status='PRIVATE_DRAFT_UPLOADED_AND_AUTHENTICATED_DOWNLOAD_VERIFIED',study_version='v0.2',repository=dict(id=batch.REPO_ID,name=batch.NAME,private=True),draft_release=dict(id=RELEASE_ID,url=r['html_url'],tag_name='study-v0.2',target_commitish=target,name=TITLE,draft=True,prerelease=False,published_at=None),assets=downloaded,branch=batch.BRANCH,main_unchanged=batch.EXPECTED_BASE,protected_releases_unchanged=True,other_drafts_unchanged=True,v095_remains_latest=True,checked_at_utc=now(),publication_authorized=False)
    save(NEW/'receipts/DRAFT_RELEASE.json',receipt)
    cp(NEW/'receipts/DRAFT_RELEASE.json',batch.R/path/'DRAFT_RELEASE.json')
    cp(NEW/'receipts/SUPERSEDED_REMOTE_ASSETS.json',batch.R/path/'SUPERSEDED_REMOTE_ASSETS.json')
    batch.git('add',path);batch.git('commit','-m','Record verified v0.2 r4 private draft replacements');batch.git('push','origin',batch.BRANCH)
    evidence=batch.git('rev-parse','HEAD').decode().strip()
    payload['body']=body.rstrip()+f'\n\n[Authenticated draft assets](https://github.com/{batch.NAME}/blob/{evidence}/{path}/DRAFT_RELEASE.json).\n'
    req2=NEW/'receipts/RELEASE_RECEIPT_LINK_REQUEST.json';save(req2,payload)
    r=batch.api(f'repos/{batch.NAME}/releases/{RELEASE_ID}','--method','PATCH','--input',req2)
    batch.check_release(r,2,target,TITLE)
    verified=[]
    for commit,relative in [(target,'README.md'),(target,'PACKAGE_INDEX.json'),(target,'receipts/PACKAGE_INDEX.json'),(target,'receipts/FRESH_PACKAGE_VERIFICATION.json'),(target,'receipts/QPathformer_v0.2_Code.startup.json'),(target,'receipts/ROOT_PACKAGE_VERIFICATION.json'),(target,'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json'),(evidence,'DRAFT_RELEASE.json')]:
        got=batch.api(f'repos/{batch.NAME}/contents/{path}/{relative}?ref={commit}')
        need(base64.b64decode(got['content'])==(batch.R/path/relative).read_bytes(),'Remote evidence differs '+relative)
        verified.append(dict(commit=commit,path=path+'/'+relative))
    guard_other_releases()
    completion=dict(status='PASS_PRIVATE_DRAFT_READY_FOR_REVIEW',release_id=RELEASE_ID,release_url=r['html_url'],study_version='v0.2',assets_verified=6,draft=True,private=True,target_commit=target,evidence_commit=evidence,links=verified,main_unchanged=True,protected_releases_unchanged=True,other_drafts_unchanged=True,latest='study-v0.9.5',completed_at_utc=now())
    save(NEW/'receipts/COMPLETION.json',completion)
    print(json.dumps(completion,indent=2))

def finalize():
    """Refresh only the v0.2 entry in the existing owner review index."""
    guard_other_releases()
    need(not batch.git('status','--porcelain').strip(), 'Preparation checkout dirty')
    done=load(NEW/'receipts/COMPLETION.json')
    upload_record=load(NEW/'receipts/DRAFT_RELEASE.json')
    branch=load(NEW/'receipts/REVIEW_BRANCH.json')
    fresh=load(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    index=load(batch.B/'REVIEW_INDEX.json')
    olditem=next(e for e in index['studies'] if e['study_version']=='v0.2')
    olditem=json.loads(json.dumps(olditem))
    history=batch.B/'history/before_v02_r4'
    need(not history.exists(),'Prior index history exists; preserve it')
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md','receipts/COMPLETION.json','tools/batch.py'):
        cp(batch.B/name,history/name)
    item=next(e for e in index['studies'] if e['study_version']=='v0.2')
    evidence_base=f'https://github.com/{batch.NAME}/blob/{done["evidence_commit"]}/{branch["record_path"]}/'
    item.update(draft_url=done['release_url'],target_commit=done['target_commit'],local_pack_folder=str(NEW),local_assets=str(NEW/'dist'),record_path=branch['record_path'],evidence_commit=done['evidence_commit'],evidence_url=evidence_base+'README.md',receipt_url=evidence_base+'DRAFT_RELEASE.json',assets=upload_record['assets'],startup_status='PASS',startup_scope=fresh['scope'],startup_binding=dict(path=str(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**info(NEW/'receipts/FRESH_PACKAGE_VERIFICATION.json')))
    scopes=[]
    for kind in ('Study','Documentation','Code'):
        with zipfile.ZipFile(NEW/'dist'/f'QPathformer_v0.2_{kind}.zip') as z:
            prefix=f'QPathformer_v0.2_{kind}/'
            for n in z.namelist():
                rel=n.removeprefix(prefix)
                if '/' not in rel and rel.endswith('_LICENSE_SCOPE.json'):
                    scope=json.loads(z.read(n));scopes.append(dict(package=kind,path=rel,files=len(scope['files']),identity=batch.bytes_info(z.read(n))))
    item['scopes']=scopes
    index['completed_at_utc']=now()
    index['latest_revision_note']='v0.2 r4 corrects active summaries and package helpers; its unchanged report retains prior visual QA. Other study selections and release assets are unchanged.'
    save(batch.B/'REVIEW_INDEX.json',index)
    for name in ('REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md'):
        text=(batch.B/name).read_text('utf-8')
        for key in ('draft_url','evidence_url','local_pack_folder'):
            text=text.replace(olditem[key],item[key])
        text=text.replace(Path(olditem['local_pack_folder']).as_posix(),NEW.as_posix())
        text += '\nThe current v0.2 selection is r4: corrected scientific summaries, exclusive startup receipts, strict inventories and pre/post startup integrity checks. Its 40 scientific Python files and report PDF/DOCX retain their reviewed bytes. r3 assets, records and the previous index remain preserved. Other study drafts are unchanged.\n'
        write(batch.B/name,text)
    record_root=batch.R/'release_preparation/draft_batch_20261029'
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md'):
        cp(batch.B/name,record_root/name)
    for p in history.rglob('*'):
        if p.is_file() and p.name!='LOCAL_REVIEW_INDEX.md':cp(p,record_root/'history/before_v02_r4'/p.relative_to(history))
    selector=HERE/'batch.py'
    source=selector.read_text('utf-8')
    need("revisions={2:'draft_20261029_r3'" in source,'Unexpected selected-build mapping')
    write(selector,source.replace("revisions={2:'draft_20261029_r3'","revisions={2:'draft_20261029_r4'",1))
    cp(selector,batch.B/'tools/batch.py')
    cp(selector,record_root/'tools/batch.py')
    current_path='release_preparation/study-v0.2/CURRENT.json'
    save(batch.R/current_path,dict(study_version='v0.2',revision=NEW.name,target_commit=done['target_commit'],evidence_commit=done['evidence_commit'],record_path=branch['record_path'],draft=True,assets=upload_record['assets'],previous_revision='draft_20261029_r3'))
    batch.git('add','release_preparation/draft_batch_20261029',current_path)
    batch.git('commit','-m','Point owner review index to corrected v0.2 r4 draft')
    batch.git('push','origin',batch.BRANCH)
    commit=batch.git('rev-parse','HEAD').decode().strip()
    guard_other_releases()
    need(not batch.git('status','--porcelain').strip(),'Checkout dirty after index refresh')
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==commit,'Remote branch differs')
    path='release_preparation/draft_batch_20261029/REVIEW_INDEX.md'
    got=batch.api(f'repos/{batch.NAME}/contents/{path}?ref={commit}')
    need(base64.b64decode(got['content'])==(batch.B/'REVIEW_INDEX.md').read_bytes(),'Remote index differs')
    final=dict(status='PASS_V02_R4_PRIVATE_DRAFT_COMPLETE',revision=NEW.name,release_url=done['release_url'],local_build=str(NEW),main_unchanged=batch.EXPECTED_BASE,other_releases_unchanged=True,latest='study-v0.9.5',repository_private=True,publication_performed=False,final_evidence_commit=commit,remote_review_index=f'https://github.com/{batch.NAME}/blob/{commit}/{path}',local_review_index=str(batch.B/'LOCAL_REVIEW_INDEX.md'),completed_at_utc=now())
    save(NEW/'receipts/FINAL_REVISION_COMPLETION.json',final)
    prior_completion=load(history/'receipts/COMPLETION.json')
    prior_completion.update(final_evidence_commit=commit,remote_review_index=final['remote_review_index'],completed_at_utc=now(),latest_revision='v0.2 r4')
    save(batch.B/'receipts/COMPLETION.json',prior_completion)
    print(json.dumps(final,indent=2))

if __name__=='__main__':
    globals()[sys.argv[1]]()
