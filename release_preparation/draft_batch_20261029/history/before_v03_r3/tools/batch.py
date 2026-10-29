import base64, hashlib, json, os, re, shutil, stat, subprocess, sys, zipfile
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit,unquote

BASE = Path(r'C:\Q2\Release_Preparation\QPathformer_Classical_Research')
B = BASE / 'draft_batch_20261029'
SEED = BASE / 'study-v0.1/final_20261029/checkout'
R = B / 'checkout'
GH = r'C:\Program Files\GitHub CLI\gh.exe'
GIT = r'C:\Program Files\Git\cmd\git.exe'
NAME = 'qpathformer/qpathformer-classical-research-v1.0'
REPO_ID = 1438032349
BRANCH = 'prepare-studies-v0.2-v0.9-20261029'
EXPECTED_BASE = '7c05ea9712d4b21a3b16fd1258f2731972e344c2'
PROTECTED = [427572374,427547832,427529591]

def need(ok, msg):
    if not ok: raise RuntimeError(msg)
def now(): return datetime.now(timezone.utc).isoformat()
def info(p):
    p=Path(p); h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return dict(bytes=p.stat().st_size,sha256=h.hexdigest())
def save(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write(p,t):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8')
def load(p):return json.loads(Path(p).read_text('utf-8-sig'))
def run(exe,*args,cwd=None,timeout=120):
    p=subprocess.run([exe,*map(str,args)],cwd=cwd or B,capture_output=True,timeout=timeout,env=dict(os.environ,GH_PROMPT_DISABLED='1',GIT_TERMINAL_PROMPT='0'))
    need(p.returncode==0,(p.stderr or p.stdout).decode('utf-8','replace'));return p.stdout
def api(path,*args):return json.loads(run(GH,'api',path,*args))
def git(*args):return run(GIT,*args,cwd=R)
def signature(r):
    return {**{k:r[k] for k in ('id','tag_name','name','body','draft','prerelease','target_commitish','published_at')},'assets':sorted([{k:a.get(k) for k in ('id','name','size','digest','created_at','updated_at')} for a in r['assets']],key=lambda a:a['id'])}
def guard():
    b=load(B/'receipts/REMOTE_BASELINE.json');repo=api('repositories/'+str(REPO_ID))
    need(repo['id']==REPO_ID and repo['full_name']==NAME and repo['private'],'Repository identity/privacy changed')
    need(api(f'repos/{NAME}/commits/main')['sha']==b['main'],'Main changed')
    for old in b['protected']:
        need(signature(api(f'repos/{NAME}/releases/{old["id"]}'))==signature(old),'Protected release changed: '+old['tag_name'])
    need(api(f'repos/{NAME}/releases/latest')['id']==427547832,'Latest changed')
    need(api(f'repos/{NAME}/git/matching-refs/tags')==b['tags'],'Existing tags changed or new tag appeared')
    return True
def baseline():
    need(not (B/'receipts/REMOTE_BASELINE.json').exists(),'Baseline already exists; preserve it')
    B.mkdir(parents=True,exist_ok=True)
    repo=api('repositories/'+str(REPO_ID));main=api(f'repos/{NAME}/commits/main')['sha'];releases=api(f'repos/{NAME}/releases?per_page=100')
    need(repo['private'] and repo['full_name']==NAME and main==EXPECTED_BASE,'Unexpected baseline')
    latest=api(f'repos/{NAME}/releases/latest');need(latest['id']==427547832,'Latest differs')
    record=dict(captured_at_utc=now(),repository=repo,main=main,releases=releases,protected=[r for r in releases if r['id'] in PROTECTED],latest=latest,tags=api(f'repos/{NAME}/git/matching-refs/tags'))
    need(len(record['protected'])==3,'Protected release absent');save(B/'receipts/REMOTE_BASELINE.json',record)
    matrix=[]
    for n in range(2,10):
        s=Path(fr'C:\Q2\Improvement_Study_v0.{n}');reports=[p for p in (s/'docs').glob('*.docx') if 'RPT' in p.name.upper()]
        matrix.append(dict(study_version=f'v0.{n}',source=str(s),source_manifest=dict(path=str(s/'DELIVERY_MANIFEST.json'),**info(s/'DELIVERY_MANIFEST.json')),reports=[dict(path=str(p),**info(p)) for p in reports],expected_build=str(BASE/f'study-v0.{n}/draft_20261029'),status='SOURCE_CONFIRMED_PREPARATION_IN_PROGRESS',etel=n>=7))
    save(B/'SOURCE_MATRIX.json',dict(repository_edition='v1.0',studies=matrix))
    write(B/'PREPARATION_BRIEF.md','''# Q Pathformer studies v0.2 through v0.9 draft preparation

The owner authorized private draft preparation on 29 October 2026 and will review on 30 October 2026 Australia/Sydney. Original scientific artifacts remain read-only. All assembly, sealed downloads, QA and receipts belong under C:\\Q2. Repository edition v1.0 is separate from study versions.

The official repository is qpathformer/qpathformer-classical-research-v1.0, ID 1438032349. Its verified main commit is 7c05ea9712d4b21a3b16fd1258f2731972e344c2. The three published releases and all their assets are protected; study-v0.9.5 remains Latest. No release publication, visibility changes, full experiments, or external contact is authorized.

Stages: inventory sources and gaps; prepare each Study, Documentation and Code package with exact rights proposals and preservation reports; verify actual sealed ZIPs and bounded offline Code startup; commit review records only to the dedicated preparation branch; create private draft releases with six authenticated-download-verified assets each. Never overwrite prior sealed evidence or force tags.

The eight source directories and original report identities are in SOURCE_MATRIX.json. Each study's inventory records scientific scope, selections, dependencies, limitations and gaps. Earlier adopted licenses survive in their exact scopes and reused expression. New report/prose CC BY 4.0 and unchanged Platform License 1.0 Python scopes remain proposals for owner review. Anthony Siljeg is licensor; company affiliation is not an ownership transfer.

Excluded downloads: raw datasets, checkpoints, installed environments, credentials and full operational archives. Archive byte totals are neither ZIP sizes nor hardware minimums. Local startup checks do not establish full reproduction or hardware readiness.
''')
    progress()
    print(json.dumps(dict(status='BASELINE_CAPTURED',main=main,protected=3,private=True,latest=latest['tag_name'],requested_studies=len(matrix))))
def progress():
    rows=['# Preparation progress','',f'Last updated {now()}','', '- [x] Verify official repository identity, privacy, main, published releases, assets and tags.', '- [x] Confirm all eight authentic source study directories and original reports.', '- [ ] Complete all per-study inventories and dependency/rights mappings.', '- [ ] Review all final PDF and Word pages.', '- [ ] Verify all ZIP/seal pairs and fresh Code startup.', '- [ ] Commit review records on a dedicated branch.', '- [ ] Upload eight draft releases and compare all 48 downloaded assets.', '- [ ] Final protected-state check and consolidated owner review index.','', '| Study | Local stage | GitHub stage |','| --- | --- | --- |']
    for n in range(2,10):
        d=selected_build(n); p=d/'receipts/PACKAGE_INDEX.json'; up=d/'receipts/DRAFT_RELEASE.json'
        rows.append(f'| v0.{n} | '+('Package index available' if p.exists() else 'Preparation in progress')+' | '+('Draft verified' if up.exists() else 'Pending')+' |')
    write(B/'PROGRESS.md','\n'.join(rows)+'\n')
def checkout():
    guard(); need(not R.exists(),'Checkout exists')
    run(GIT,'clone','--no-hardlinks','-c','core.autocrlf=false',SEED,R,timeout=180)
    git('remote','set-url','origin','https://github.com/'+NAME+'.git')
    for k in ('user.name','user.email'):git('config',k,run(GIT,'config',k,cwd=SEED).decode().strip())
    need(git('rev-parse','HEAD').decode().strip()==EXPECTED_BASE and not git('status','--porcelain').strip(),'Seed differs')
    refs=api(f'repos/{NAME}/git/matching-refs/heads/{BRANCH}');need(not refs,'Preparation branch already exists')
    git('checkout','-b',BRANCH)
    save(B/'receipts/BRANCH_PREPARATION.json',dict(branch=BRANCH,base=EXPECTED_BASE,checkout=str(R),created_at_utc=now(),pushed=False))
    print('Dedicated local preparation checkout ready')

def license_catalog():
    existing=B/'ADOPTED_SCOPE_CATALOG.json'
    if existing.exists() and not (B/'history/ADOPTED_SCOPE_CATALOG_initial.json').exists():
        (B/'history').mkdir(exist_ok=True);shutil.copyfile(existing,B/'history/ADOPTED_SCOPE_CATALOG_initial.json')
    scopes=[]
    v01=BASE/'study-v0.1/final_20261029/assembly'
    for p in v01.glob('*/*LICENSE_SCOPE.json'):scopes.append((p,p.parent,'v0.1'))
    v095=BASE/'study-v0.9.5/final_20261029/repository'
    for n in ('CODE_LICENSE_SCOPE.json','DOCUMENTATION_LICENSE_SCOPE.json','NEW_GUIDANCE_LICENSE_SCOPE.json','REPORT_LICENSE_SCOPE.json'):scopes.append((v095/n,v095,'v0.9.5'))
    for p in (BASE/'study-v0.9.5/final_20261029/assembly').glob('*/WRAPPER_LICENSE_SCOPE.json'):scopes.append((p,p.parent,'v0.9.5'))
    entries=[];payloads={}
    for p in (BASE/'study-v0.9.5/final_20261029/assembly').rglob('*'):
        if p.is_file():payloads.setdefault(info(p)['sha256'],[]).append(p)
    def walk(o,p,root,version,trail=''):
        if isinstance(o,dict):
            if isinstance(o.get('path'),str) and o.get('sha256'):
                actual=root/o['path'];original=str(actual)
                if (not actual.is_file() or info(actual)['sha256']!=o['sha256']) and o['sha256'] in payloads:actual=payloads[o['sha256']][0]
                entries.append(dict(study=version,scope_path=str(p),scope_identity=info(p),json_location=trail,entry=o,scope_relative_resolution=original,local_path=str(actual),local_exists=actual.is_file(),local_matches=actual.is_file() and info(actual)['sha256']==o['sha256'],resolution='Scope-relative file if matching; otherwise exact adopted digest match in preserved final v0.9.5 package payload'))
            for k,v in o.items():walk(v,p,root,version,trail+'/'+k)
        elif isinstance(o,list):
            for i,v in enumerate(o):walk(v,p,root,version,trail+'/'+str(i))
    for p,root,v in scopes:walk(load(p),p,root,v)
    save(B/'ADOPTED_SCOPE_CATALOG.json',dict(schema='qpath-adopted-scope-catalog-1',created_at_utc=now(),purpose='Index of exact identities appearing in already-adopted scope records. Scope semantics, exclusions and canonical license texts remain authoritative. Metadata/license-record entries are not themselves an inferred content grant.',scope_records=[dict(path=str(p),study=v,**info(p)) for p,_,v in scopes],entries=entries))
    print(json.dumps(dict(scope_records=len(scopes),identity_entries=len(entries),file_matches=sum(e['local_matches'] for e in entries))))

def plan():
    details={
      2:('Improvement and baseline comparison','Quantum schedule and classical DBpedia14 text work','quantum; classical; analysis; governance','No ETEL; task-specific dependencies and original benchmark boundaries must be retained.'),
      3:('Shallow circuits and routing','Synthetic shallow circuit and routing comparisons with numerical recovery protocol','quantum; analysis; governance','No ETEL; recovery and historical recommendations remain part of the scientific record.'),
      4:('Routing and circuit contribution','Matched routing and circuit-family comparisons','quantum; analysis; governance','No ETEL; do not generalize matched comparisons beyond studied tasks and arms.'),
      5:('Flexible readouts and classical controls','Eleven arms on circle and ellipse; 66 development and 165 confirmation fits','quantum; analysis; governance','No ETEL; NumPy/SciPy numerical core and optional Qiskit/Aer readiness; inherited circuit kernel matches v0.9.5 grant.'),
      6:('Harder tasks and faster inference','Six arms across four harder task families; 48 development and 120 confirmation fits; separate equivalent classical coefficient conversion','quantum; analysis; governance','No ETEL; local conversion and timing do not establish hardware performance; inherited kernel grant retained.'),
      7:('Internal study with ETEL','Study-specific scientific implementation and ETEL integration','quantum; execution; analysis; governance; reproducibility','ETEL supplied; original absolute paths and archived execution are not a relocatable scheduler.'),
      8:('Internal study with ETEL priority sampling','Ten arms; checkerboard, spiral, noisy annulus and rare disk; 40 engineering, 80 development, 640 confirmation fits','quantum; execution; analysis; governance','ETEL supplied; logical 64-slot bookkeeping is not 64 physical workers. Four clean fits demonstrate same-environment reproduction.'),
      9:('Plan B internal study','Synthetic and Banknote study with ETEL, conversion and clean retraining evidence','evidence/quantum; evidence/execution; evidence/analysis; evidence/governance','ETEL supplied; stale top-level READ_ME pre-study notice conflicts with final report. Banknote one fixed grouped split; five optimizer seeds are not independent population replication.')}
    m=load(B/'SOURCE_MATRIX.json')
    rows=['# Per study preparation matrix','','All eight versions were confirmed from their original report files under C:\\Q2. Exact original report and delivery-manifest hashes are in SOURCE_MATRIX.json. Detailed per-study inventories refine this initial selection before sealing.','','| Study | Original report and scope | Selected implementation | Findings and limitations to verify |','| --- | --- | --- | --- |']
    for e in m['studies']:
        n=int(e['study_version'].split('.')[-1]);title,scope,code,limit=details[n]
        e.update(report_subject=title,scientific_scope=scope,proposed_code_roots=code,limitations=limit,known_licensing='Existing v0.1/v0.9.5 exact scopes and reused expression retained. Newly selected report/prose/Python content is proposed, not adopted.',proposed_selection='Reviewed PDF and Word report editions; study overview and reproduction boundaries; curated source/config/protocol files. Exclude raw datasets, checkpoints, environments, credentials and full archives.',verification_needs=['Original selected source size and SHA-256 against delivery evidence','Report body, figures and tables preservation plus visual all-page QA','Exact inherited grant/partial-expression mapping and new scope proposals','ZIP path/membership/manifest/checksum/seal checks','Fresh actual Code ZIP offline startup in compatible local runtime','Authenticated download identity check for all six draft assets'])
        rows.append(f'| {e["study_version"]} | {title}. {scope}. | {code} | {limit} |')
    save(B/'SOURCE_MATRIX.json',m)
    write(B/'STUDY_MATRIX.md','\n'.join(rows)+'''\n
All new scope decisions remain pending: CC BY 4.0 for controlled original report and selected prose; unchanged Q-Pathformer Platform License 1.0 for newly selected Python expression. Scope proposals must enumerate exact file identities and report figures. Existing grants are not revoked or narrowed. Dependencies, datasets, model artifacts, architecture documents and full archives retain separate terms.

The compatible preserved v0.1 Python environment is a startup candidate; each study must establish its own imports and bounded checks. Historical dependency versions and modern startup results are separate evidence. Startup is not full reproduction, training, official scoring, shot sampling or QPU execution.
''')
    print('Initial per-study source and verification matrix saved')

def adopt_authorization():
    record=dict(schema='qpath-batch-owner-authorization-1',adopted_on='2026-10-29',timezone='Australia/Sydney',owner='Anthony Siljeg',owner_wording=['the licensing decisions can be adopted, if its the same as the first two','this can save recomputing the seals?'],received_via='Originating owner chat 01a17bed-f2d9-7401-8cd8-669ee0a1ccc1 delegated instruction to this preparation chat',condition='Same scoped licensing scheme used in completed study-v0.1 and study-v0.9.5. Exact per-study memberships and identities must be recorded; no blanket grant.',terms=dict(report_and_prose='CC BY 4.0 for identified controlled original report prose, table presentation, original figures, and explicitly listed original explanatory/wrapper/support prose',python='Unchanged Q-Pathformer Platform License 1.0 for exact selected Python implementation and package helpers'),preserve_existing_grants=True,excluded=['Third-party dependencies or expression','Datasets','Model artifacts/checkpoints','Architecture documents','Full archives','Unrelated records'],exceptions='Isolate specific selections needing different terms, genuinely unresolved ownership or conflicting notices; do not invent ownership evidence.',attribution='Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative',affiliation_is_not_ownership_transfer=True,release_constraints=dict(draft=True,private=True,make_latest=False,protected_releases_unchanged=True),sealing_order='Finalize adopted scopes, notices, report visible edition notes and metadata before manifest/checksum/ZIP/seal. Preserve prior sealed candidates; rebuild changed packs and bind rebuilt Code startup.',recorded_at_utc=now())
    save(B/'OWNER_LICENSE_AUTHORIZATION.json',record)
    p=B/'PREPARATION_BRIEF.md';t=p.read_text('utf-8');t=t.replace('New report/prose CC BY 4.0 and unchanged Platform License 1.0 Python scopes remain proposals for owner review.','The owner subsequently adopted the same scoped report/prose CC BY 4.0 and unchanged Platform License 1.0 Python scheme, subject to exact memberships and exclusions. OWNER_LICENSE_AUTHORIZATION.json records the actual wording and condition. Routine matching selections require no repeated adoption question; isolate genuine exceptions.')
    write(p,t)
    m=load(B/'SOURCE_MATRIX.json')
    for e in m['studies']:
        e['known_licensing']='Same scoped scheme adopted by owner conditionally on matching completed release terms; precise final memberships and any genuine exceptions remain to verify. Existing grants and notices preserved.'
        e['verification_needs']=[s.replace('new scope proposals','final adopted scope records') for s in e['verification_needs']]
    save(B/'SOURCE_MATRIX.json',m)
    p=B/'STUDY_MATRIX.md';t=p.read_text('utf-8').replace('All new scope decisions remain pending:','Owner authorization now adopts the same scoped scheme, recorded in OWNER_LICENSE_AUTHORIZATION.json:').replace('Scope proposals must enumerate','Final scope records must enumerate');write(p,t)
    print('Updated owner licensing authorization recorded before sealing')

def selected_build(n):
    revisions={2:'draft_20261029_r4',3:'draft_20261029_r2',4:'draft_20261029_r2',5:'draft_20261029_r02',6:'draft_20261029_r02',7:'draft_20261029_r2',8:'draft_20261029_r2',9:'draft_20261029_r2'}
    return BASE/f'study-v0.{n}'/revisions.get(n,'draft_20261029')
def bytes_info(b):return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def verify_package(zp,sp):
    zp=Path(zp);s=load(sp);root=zp.stem;prefix=root+'/'
    need(s['zip']['path']==zp.name and all(s['zip'][k]==info(zp)[k] for k in ('bytes','sha256')),'ZIP seal identity mismatch')
    need(s['member_path_prefix']==prefix,'Unexpected root')
    need(str(s['actual_build_root']).lower().startswith('c:\\q2\\'),'Build must originate under Q2')
    with zipfile.ZipFile(zp) as z:
        names=z.namelist();need(len(names)==len(set(names))==len({v.casefold() for v in names}),'Duplicate or case-colliding paths')
        need(all(v.startswith(prefix) and not v.endswith('/') and '\\' not in v and ':' not in v and all(c not in ('','.','..') for c in v.split('/')) for v in names),'Unsafe path or wrong root')
        for v in z.infolist():
            mode=(v.external_attr>>16)&0o170000;need(mode in (0,stat.S_IFREG) and not(v.flag_bits&1),'Nonregular or encrypted member')
        content={v[len(prefix):]:z.read(v) for v in names};need(z.testzip() is None,'ZIP CRC fails')
    for key in ('internal_manifest','internal_checksums','source_map'):
        e=s[key];internal=e['path'].removeprefix(prefix);need(internal in content and all(e[k]==bytes_info(content[internal])[k] for k in ('bytes','sha256')),'Sealed internal identity mismatch: '+key)
    manifest=json.loads(content['MANIFEST.json']);fs=manifest['files'];indexed={e['path']:e for e in fs}
    need(len(indexed)==len(fs) and set(indexed)==set(content)-{'MANIFEST.json','CHECKSUMS.sha256'},'Manifest membership mismatch')
    for n,e in indexed.items():need(all(e[k]==bytes_info(content[n])[k] for k in ('bytes','sha256')),'Manifest hash mismatch '+n)
    checksum={}
    for line in content['CHECKSUMS.sha256'].decode('utf-8-sig').splitlines():
        h,n=line.split('  ',1);need(n not in checksum,'Duplicate checksum');checksum[n]=h
    need(set(checksum)==set(content)-{'CHECKSUMS.sha256'},'Checksum membership mismatch')
    for n,h in checksum.items():need(hashlib.sha256(content[n]).hexdigest()==h,'Checksum mismatch '+n)
    jsons=0;links=[]
    import posixpath
    for n,b in content.items():
        if n.lower().endswith('.json'):json.loads(b.decode('utf-8-sig'));jsons+=1
        if n.lower().endswith('.md'):
            for target in re.findall(r'\]\(([^)]+)\)',b.decode('utf-8-sig')):
                target=target.strip('<>');u=urlsplit(target)
                if u.scheme or target.startswith('#'):links.append(dict(source=n,target=target,kind='external_or_anchor'));continue
                resolved=posixpath.normpath(posixpath.join(posixpath.dirname(n),unquote(u.path)))
                need(resolved in content or any(k.startswith(resolved.rstrip('/')+'/') for k in content),'Broken package Markdown link '+n+' -> '+target)
                links.append(dict(source=n,target=target,kind='local_verified'))
    for n in content:
        need(not re.search(r'(^|/)(\.env|\.venv|venv|__pycache__)(/|$)',n,re.I),'Excluded environment content '+n)
        need(not n.lower().endswith(('.pyc','.pt','.pth','.ckpt','.sqlite','.db','.parquet')),'Excluded artifact type '+n)
    for n,b in content.items():
        if n.endswith('QPATHFORMER-PLATFORM-1.0.txt'):need(hashlib.sha256(b).hexdigest()=='efa2911bfa72c36bd471bdf8d047c4a54cebf19e0a0f835184c348ef0e772057','Canonical Platform text changed')
        if n.endswith('CC-BY-4.0.txt'):need(hashlib.sha256(b).hexdigest()=='2ade8c89b8bbe0d859b124a9e47032c8494022f43091e8278ae8e2554a292196','Canonical CC text changed')
    scopes=[]
    for n,b in content.items():
        if '/' not in n and n.endswith('_LICENSE_SCOPE.json'):
            o=json.loads(b);need(o['status']=='ADOPTED','Current scope is not adopted')
            for e in o['files']:
                need(e['path'] in content and all(e[k]==bytes_info(content[e['path']])[k] for k in ('bytes','sha256')),'Scope identity mismatch '+n+' '+e['path'])
            scopes.append(dict(path=n,files=len(o['files']),**bytes_info(b)))
    need('LICENSE_ADOPTION.json' in content and json.loads(content['LICENSE_ADOPTION.json'])['owner_instruction']=='the licensing decisions can be adopted, if its the same as the first two','Owner adoption wording absent')
    return dict(package=root,zip=dict(path=str(zp),**info(zp)),seal=dict(path=str(sp),**info(sp)),files=len(content),json_files=jsons,adopted_scopes=scopes,markdown_links=links,status='PASS_INDEPENDENT_PACKAGE_INTEGRITY')

def verify_study(n):
    d=selected_build(n);files=sorted((d/'dist').iterdir());expected={f'QPathformer_v0.{n}_{kind}{ext}' for kind in ('Study','Documentation','Code') for ext in ('.zip','.seal.json')}
    need({p.name for p in files}==expected,'Expected exactly six assets')
    results=[verify_package(d/'dist'/f'QPathformer_v0.{n}_{kind}.zip',d/'dist'/f'QPathformer_v0.{n}_{kind}.seal.json') for kind in ('Study','Documentation','Code')]
    fresh=load(d/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    for key in ('code_zip','code_seal','code_startup_receipt'):
        e=fresh[key];need(all(e[k]==info(e['path'])[k] for k in ('bytes','sha256')),'Startup binding identity differs '+key)
    need(Path(fresh['code_zip']['path']).resolve()==(d/'dist'/f'QPathformer_v0.{n}_Code.zip').resolve(),'Startup binds another Code ZIP')
    need(fresh['receipt_outside_entire_package'] and fresh['package_bytes_unchanged'],'Startup receipt boundary or integrity not verified')
    startup=load(fresh['code_startup_receipt']['path']);need(startup['status']=='PASS' or 'GAP' in fresh['status'],'Startup unresolved without recorded gap')
    record=dict(status='PASS_ROOT_INDEPENDENT_PACKAGE_VERIFICATION',study_version=f'v0.{n}',checked_at_utc=now(),packages=results,startup_binding=dict(path=str(d/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**info(d/'receipts/FRESH_PACKAGE_VERIFICATION.json')),startup_status=startup['status'],boundary='Independent checks of actual ZIP/seal bytes, safe paths, exact inventories, all JSON, local active Markdown links, adopted-scope identities, canonical license text identities and current final Code/startup binding. Report visual QA is separately reviewed evidence.')
    save(d/'receipts/ROOT_PACKAGE_VERIFICATION.json',record);return record

def verify_one():
    n=int(sys.argv[2]);record=verify_study(n);print(json.dumps(dict(study=f'v0.{n}',status=record['status'],packages=[dict(package=e['package'],files=e['files'],bytes=e['zip']['bytes']) for e in record['packages']])))

def inventory():
    records=[];rows=['# Study source inventory and preparation matrix','','Eight authentic study report and code selections were identified before package sealing. Original artifacts are read-only. Owner authorization subsequently adopted the same scoped licensing scheme as v0.1 and v0.9.5; exact per-study memberships and exceptions are checked before sealing.','','| Study | Report identity | Scientific findings | Boundaries and verification |','| --- | --- | --- | --- |']
    for n in range(2,10):
        d=selected_build(n);p=d/'INVENTORY.json'
        if not p.exists():p=d/'receipts/SOURCE_INVENTORY.json'
        o=load(p);records.append(dict(study_version=f'v0.{n}',inventory_path=str(p),inventory_identity=info(p),inventory=o))
        report=o['report'];ident=report.get('sha256') or report.get('identity',{}).get('sha256','see inventory')
        findings=o.get('findings',o.get('overview','See per-study inventory'));limits=o.get('limitations',o.get('limits','See per-study inventory'))
        if not isinstance(findings,str):findings=json.dumps(findings,ensure_ascii=False)
        if not isinstance(limits,str):limits=json.dumps(limits,ensure_ascii=False)
        rows.append(f'| v0.{n} | `{ident}` | {findings.replace(chr(10)," ").replace("|",";")} | {limits.replace(chr(10)," ").replace("|",";")} |')
    save(B/'PER_STUDY_INVENTORIES.json',dict(recorded_at_utc=now(),status='ALL_EIGHT_SOURCE_SELECTIONS_CONFIRMED',licensing_authorization='OWNER_LICENSE_AUTHORIZATION.json',studies=records))
    write(B/'STUDY_MATRIX.md','\n'.join(rows)+'''\n
PER_STUDY_INVENTORIES.json retains the exact original report/code identities, source paths, dependency evidence, proposed selections and verification needs from each inventory. ADOPTED_SCOPE_CATALOG.json maps earlier adopted scope identities; per-study final rights records map exact full-file matches and retained expression. No whole ZIP, repository, dataset, dependency, model, architecture or full-archive grant is inferred.

Each report receives an explicit edition note and corrected author metadata, source-body/table/media preservation checks, and every-page render review. Each actual final ZIP receives path/membership/JSON/link/hash checks; each actual Code ZIP is freshly extracted and checked offline without training, official scoring, shots or hardware jobs. Runtime/reproduction gaps remain explicit. Full archive logical sizes are not curated ZIP sizes or hardware minima.
''')
    print('All eight detailed source inventories consolidated')

def report_review_v09():
    d=selected_build(9);pages=d/'report/qa/pages';pdfs=list((d/'report/files').glob('*.pdf'));need(len(pdfs)==1,'Expected one final PDF')
    record=dict(status='PASS_ALL_40_PAGES_VISUALLY_INSPECTED',reviewer='Primary release preparation agent /root',method='Opened each page-1.png through page-40.png individually with view_image at original resolution, in ten batches of four. Visual inspection, not text extraction alone.',reviewed_pages=list(range(1,41)),page_count=40,pdf=dict(path=str(pdfs[0]),**info(pdfs[0])),page_images=[dict(page=n,path=str(pages/f'page-{n}.png'),**info(pages/f'page-{n}.png')) for n in range(1,41)],observations=['Readable original report text and numeric tables throughout','All six figures legible, captions and axes retained','Repeated headers on continued tables; no clipped rows or overlaps','No missing glyphs or unintended blank pages','Page 40 edition and scoped rights note clear; historical labels explained'],retained_disclosure_items=[dict(pages=[4],item='Historical host hardware and software configuration'),dict(pages=[36],item='Operational recovery and credit checkpoint discussion'),dict(pages=[37],item='Historical account balance, credit proxies and token usage accounting'),dict(pages=[39],item='Historical evidence paths and archive navigation')],disclosure_handling='Preserved unchanged as requested; identified for owner review before any future publication. No credentials observed during page review. This observation is not a forensic secret audit.',scientific_verification_boundary='Visual/layout review only; original scientific-body and embedded media preservation are separately recorded by the report preparer.',reviewed_at_utc=now())
    save(d/'report/ROOT_VISUAL_REVIEW.json',record);print('All 40 v0.9 page reviews recorded')

def record_study(n):
    guard();record=verify_study(n);d=selected_build(n);record_path=f'release_preparation/study-v0.{n}/revisions/{d.name}';dest=R/record_path
    need(not dest.exists(),'Review records already exist; resume explicitly')
    for folder in ('receipts','report'):
        for p in (d/folder).rglob('*'):
            if p.is_file() and p.suffix.lower() in ('.json','.md') and 'qa' not in p.relative_to(d/folder).parts and 'history' not in p.parts:
                out=dest/folder/p.relative_to(d/folder);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)
    for p in d.glob('*'):
        if p.is_file() and p.suffix.lower() in ('.json','.md'):shutil.copyfile(p,dest/p.name)
    for kind in ('Study','Documentation','Code'):
        zp=d/'dist'/f'QPathformer_v0.{n}_{kind}.zip'
        with zipfile.ZipFile(zp) as z:
            for member in z.namelist():
                out=(dest/'packages'/member).resolve();need(out.is_relative_to((dest/'packages').resolve()),'Unsafe record extraction')
                out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(member))
    save(dest/'PACKAGE_INDEX.json',dict(study_version=f'v0.{n}',repository_edition='v1.0',packages=[dict(package=e['package'],zip=dict(path=Path(e['zip']['path']).name,**info(e['zip']['path'])),seal=dict(path=Path(e['seal']['path']).name,**info(e['seal']['path']))) for e in record['packages']],build_root=str(d)))
    shutil.copyfile(B/'OWNER_LICENSE_AUTHORIZATION.json',dest/'OWNER_LICENSE_AUTHORIZATION.json')
    write(dest/'README.md',f'''# Study v0.{n} review records

The Study, Documentation and Code downloads are prepared for a GitHub draft in the official private repository. Repository edition v1.0 is distinct from this study version. Main and all three previously published releases remain unchanged.

[Package identities](PACKAGE_INDEX.json) · [Independent package verification](receipts/ROOT_PACKAGE_VERIFICATION.json) · [Owner license authorization](OWNER_LICENSE_AUTHORIZATION.json).

Per-study preparation records, source identities, report preservation and page-review evidence, dependency inventories, adopted scopes and bounded offline startup evidence are retained in this directory. Actual ZIPs and external seals are draft release assets; the local build root is `{d}`.

The owner adopted the same precise scoped licensing scheme as the completed v0.1 and v0.9.5 releases. Existing grants remain in force. Any documented exception stays outside the adopted scope. Draft access and publication status are separate from content licensing.
''')
    git('add',record_path);git('commit','-m',f'Prepare study v0.{n} sealed packages and review evidence')
    commit=git('rev-parse','HEAD').decode().strip();git('push','--set-upstream','origin',BRANCH)
    need(api(f'repos/{NAME}/commits/{BRANCH}')['sha']==commit,'Remote branch mismatch');guard()
    save(d/'receipts/REVIEW_BRANCH.json',dict(branch=BRANCH,target_commit=commit,base_main=EXPECTED_BASE,record_path=record_path,checked_at_utc=now()))
    return commit

def prepare_one():
    n=int(sys.argv[2]);print(json.dumps(dict(study=f'v0.{n}',target_commit=record_study(n))))

def check_release(r,n,target,title):
    need(r['tag_name']==f'study-v0.{n}' and r['target_commitish']==target and r['name']==title and r['draft'] and not r['prerelease'] and r['published_at'] is None,'Draft release configuration differs')
    need(api(f'repos/{NAME}/releases/latest')['id']==427547832,'Latest changed')

def upload_one():
    n=int(sys.argv[2]);d=selected_build(n);guard();record=verify_study(n)
    branch=load(d/'receipts/REVIEW_BRANCH.json');target=branch['target_commit'];tag=f'study-v0.{n}'
    record_path=branch['record_path']
    notes=(d/'RELEASE_NOTES.md').read_text('utf-8-sig');title=next((x.lstrip('#').strip() for x in notes.splitlines() if x.startswith('# ')),f'Q-Pathformer Study v0.{n}')
    baseurl=f'https://github.com/{NAME}/blob/{target}/{record_path}/'
    body=notes+'\n\n[Review evidence]('+baseurl+'README.md) · [Exact package identities]('+baseurl+'PACKAGE_INDEX.json) · [Independent verification]('+baseurl+'receipts/ROOT_PACKAGE_VERIFICATION.json).\n\nThis release remains a draft in the private repository. Scoped content licensing is adopted separately from release publication. study-v0.9.5 remains Latest.\n'
    # Expand local release-note links to immutable files only after checking the target exists.
    def replace(m):
        href=m.group(2);u=urlsplit(href)
        if u.scheme or href.startswith('#'):return m.group(0)
        path=(R/record_path/unquote(u.path)).resolve()
        need(path.is_file() and path.is_relative_to(R.resolve()),'Release note link target absent '+href)
        return '['+m.group(1)+']('+baseurl+href+')'
    body=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',replace,body)
    existing=[r for r in api(f'repos/{NAME}/releases?per_page=100') if r['tag_name']==tag];need(len(existing)<=1,'Duplicate requested releases')
    payload=dict(tag_name=tag,target_commitish=target,name=title,body=body,draft=True,prerelease=False,make_latest='false')
    req=d/'receipts/RELEASE_MUTATION_REQUEST.json';save(req,payload)
    if existing:
        need(existing[0]['draft'],'Requested release already published; refuse update')
        before=d/'receipts/DRAFT_BEFORE_RESUME.json'
        if not before.exists():save(before,existing[0])
        r=api(f'repos/{NAME}/releases/{existing[0]["id"]}','--method','PATCH','--input',req)
    else:r=api(f'repos/{NAME}/releases','--method','POST','--input',req)
    check_release(r,n,target,title);guard()
    for p in sorted((d/'dist').iterdir()):
        remote={a['name']:a for a in api(f'repos/{NAME}/releases/{r["id"]}')['assets']}
        if p.name in remote:
            a=remote[p.name]
            if a['size']!=info(p)['bytes'] or a.get('digest')!='sha256:'+info(p)['sha256']:
                # Preserve authenticated old bytes and exact identity before replacing only this draft asset.
                old=run(GH,'api',f'repos/{NAME}/releases/assets/{a["id"]}','-H','Accept: application/octet-stream',timeout=180)
                need(len(old)==a['size'] and a.get('digest')=='sha256:'+bytes_info(old)['sha256'],'Superseded asset identity mismatch')
                oldpath=d/'qa/superseded_remote_assets'/str(a['id'])/a['name'];oldpath.parent.mkdir(parents=True,exist_ok=True)
                if oldpath.exists():need(info(oldpath)==bytes_info(old),'Preserved superseded bytes differ')
                else:oldpath.write_bytes(old)
                oldrec=d/'receipts/SUPERSEDED_REMOTE_ASSETS.json';hist=load(oldrec) if oldrec.exists() else dict(release_id=r['id'],status='SUPERSEDED_DRAFT_ASSETS_PRESERVED_BEFORE_REPLACEMENT',assets=[])
                if not any(e['id']==a['id'] for e in hist['assets']):
                    hist['assets'].append(dict(id=a['id'],name=a['name'],path=str(oldpath),**bytes_info(old),preserved_at_utc=now(),replacement=dict(path=str(p),**info(p))));save(oldrec,hist)
                check_release(api(f'repos/{NAME}/releases/{r["id"]}'),n,target,title)
                run(GH,'api',f'repos/{NAME}/releases/assets/{a["id"]}','--method','DELETE')
                check_release(api(f'repos/{NAME}/releases/{r["id"]}'),n,target,title)
                run(GH,'release','upload',tag,p,'--repo',NAME,timeout=180)
        else:run(GH,'release','upload',tag,p,'--repo',NAME,timeout=180)
        check_release(api(f'repos/{NAME}/releases/{r["id"]}'),n,target,title)
    r=api(f'repos/{NAME}/releases/{r["id"]}');need({a['name'] for a in r['assets']}=={p.name for p in (d/'dist').iterdir()},'Remote membership differs')
    downloads=d/'qa/authenticated_downloads';downloads.mkdir(parents=True,exist_ok=True);assets=[]
    for a in r['assets']:
        p=d/'dist'/a['name'];data=run(GH,'api',f'repos/{NAME}/releases/assets/{a["id"]}','-H','Accept: application/octet-stream',timeout=180)
        need(bytes_info(data)==info(p),'Downloaded bytes differ');out=downloads/a['name']
        if out.exists():need(info(out)==info(p),'Prior authenticated download differs')
        else:out.write_bytes(data)
        need(a['size']==len(data) and a.get('digest')=='sha256:'+bytes_info(data)['sha256'],'Asset metadata mismatch')
        assets.append(dict(id=a['id'],name=a['name'],**info(out),download_verified=True))
    for kind in ('Study','Documentation','Code'):verify_package(downloads/f'QPathformer_v0.{n}_{kind}.zip',downloads/f'QPathformer_v0.{n}_{kind}.seal.json')
    guard()
    receipt=dict(schema='qpath-draft-release-1',status='PRIVATE_DRAFT_UPLOADED_AND_AUTHENTICATED_DOWNLOAD_VERIFIED',study_version=f'v0.{n}',repository=dict(id=REPO_ID,name=NAME,private=True),draft_release=dict(id=r['id'],url=r['html_url'],tag_name=tag,target_commitish=target,name=title,draft=True,prerelease=False,published_at=None),assets=assets,branch=BRANCH,main_unchanged=EXPECTED_BASE,protected_releases_unchanged=True,v095_remains_latest=True,checked_at_utc=now(),licensing='Same scoped scheme adopted with exact per-study membership records; documented exceptions excluded.',publication_authorized=False)
    save(d/'receipts/DRAFT_RELEASE.json',receipt);dest=R/record_path;shutil.copyfile(d/'receipts/DRAFT_RELEASE.json',dest/'DRAFT_RELEASE.json')
    if (d/'receipts/SUPERSEDED_REMOTE_ASSETS.json').exists():shutil.copyfile(d/'receipts/SUPERSEDED_REMOTE_ASSETS.json',dest/'SUPERSEDED_REMOTE_ASSETS.json')
    git('add',record_path);git('commit','-m',f'Record verified study v0.{n} private draft assets');git('push','origin',BRANCH)
    receipt_commit=git('rev-parse','HEAD').decode().strip()
    payload['body']=body+'\n[Authenticated download and draft receipt](https://github.com/'+NAME+'/blob/'+receipt_commit+'/'+record_path+'/DRAFT_RELEASE.json).\n'
    req2=d/'receipts/RELEASE_RECEIPT_LINK_REQUEST.json';save(req2,payload)
    r=api(f'repos/{NAME}/releases/{r["id"]}','--method','PATCH','--input',req2);check_release(r,n,target,title);guard()
    # Resolve evidence links through the authenticated contents API at full commits.
    verified=[]
    for commit,path in [(target,record_path+'/README.md'),(target,record_path+'/PACKAGE_INDEX.json'),(target,record_path+'/receipts/ROOT_PACKAGE_VERIFICATION.json'),(receipt_commit,record_path+'/DRAFT_RELEASE.json')]:
        got=api(f'repos/{NAME}/contents/{path}?ref={commit}');need(base64.b64decode(got['content'])==(R/path).read_bytes(),'Remote evidence bytes differ');verified.append(dict(commit=commit,path=path))
    save(d/'receipts/COMPLETION.json',dict(status='PASS_PRIVATE_DRAFT_READY_FOR_REVIEW',release_id=r['id'],release_url=r['html_url'],study_version=f'v0.{n}',assets_verified=6,draft=True,private=True,target_commit=target,evidence_commit=receipt_commit,links=verified,main_unchanged=True,protected_releases_unchanged=True,latest='study-v0.9.5',completed_at_utc=now()))
    progress();print(json.dumps(load(d/'receipts/COMPLETION.json')))

def continue_batch():
    for n in (5,2,3,4,7,8,9):
        d=selected_build(n)
        if (d/'receipts/COMPLETION.json').exists():
            print(f'v0.{n} final completion already recorded',flush=True);continue
        print(f'Preparing verified final study v0.{n} branch records from {d.name}',flush=True)
        if not (d/'receipts/REVIEW_BRANCH.json').exists():record_study(n)
        print(f'Creating or resuming private draft v0.{n} and checking six downloads',flush=True)
        sys.argv=[sys.argv[0],'upload_one',str(n)];upload_one()
        print(f'v0.{n} final private draft complete',flush=True)

def finish_pending():
    n=int(sys.argv[2]);d=selected_build(n);receipt=load(d/'receipts/DRAFT_RELEASE.json');branch=load(d/'receipts/REVIEW_BRANCH.json');guard()
    need(not (d/'receipts/COMPLETION.json').exists(),'Already completed')
    commit=git('rev-parse','HEAD').decode().strip();need(api(f'repos/{NAME}/commits/{BRANCH}')['sha']==commit,'Pending receipt commit not pushed')
    rp=branch['record_path'];payload=load(d/'receipts/RELEASE_MUTATION_REQUEST.json');rid=receipt['draft_release']['id']
    r=api(f'repos/{NAME}/releases/{rid}');check_release(r,n,branch['target_commit'],payload['name'])
    need({a['name'] for a in r['assets']}=={p.name for p in (d/'dist').iterdir()},'Pending asset membership differs')
    for a in r['assets']:
        local=d/'dist'/a['name'];need(a['size']==info(local)['bytes'] and a['digest']=='sha256:'+info(local)['sha256'],'Pending asset digest differs')
        need(info(d/'qa/authenticated_downloads'/a['name'])==info(local),'Pending downloaded bytes differ')
    payload['body']+='\n[Authenticated download and draft receipt](https://github.com/'+NAME+'/blob/'+commit+'/'+rp+'/DRAFT_RELEASE.json).\n'
    req=d/'receipts/RELEASE_RECEIPT_LINK_REQUEST.json';save(req,payload);r=api(f'repos/{NAME}/releases/{rid}','--method','PATCH','--input',req);check_release(r,n,branch['target_commit'],payload['name']);guard()
    verified=[]
    for rev,path in [(branch['target_commit'],rp+'/README.md'),(branch['target_commit'],rp+'/PACKAGE_INDEX.json'),(branch['target_commit'],rp+'/receipts/ROOT_PACKAGE_VERIFICATION.json'),(commit,rp+'/DRAFT_RELEASE.json')]:
        got=api(f'repos/{NAME}/contents/{path}?ref={rev}');need(base64.b64decode(got['content'])==(R/path).read_bytes(),'Recovery evidence mismatch');verified.append(dict(commit=rev,path=path))
    save(d/'receipts/PUSH_RECOVERY.json',dict(status='PASS_TRANSIENT_PUSH_RETRIED',error='getaddrinfo() thread failed to start',recovery='Retried push of already committed receipt; verified remote commit and continued explicit draft-only receipt-link update.',commit=commit,recovered_at_utc=now()))
    save(d/'receipts/COMPLETION.json',dict(status='PASS_PRIVATE_DRAFT_READY_FOR_REVIEW',release_id=rid,release_url=r['html_url'],study_version=f'v0.{n}',assets_verified=6,draft=True,private=True,target_commit=branch['target_commit'],evidence_commit=commit,links=verified,main_unchanged=True,protected_releases_unchanged=True,latest='study-v0.9.5',completed_at_utc=now()))
    progress();print(json.dumps(load(d/'receipts/COMPLETION.json')))

def finalize():
    from io import BytesIO
    from pypdf import PdfReader
    guard();need(not git('status','--porcelain').strip(),'Preparation checkout dirty before final review index')
    allreleases=api(f'repos/{NAME}/releases?per_page=100');studies=[];page_total=0
    for n in range(2,10):
        d=selected_build(n);done=load(d/'receipts/COMPLETION.json');receipt=load(d/'receipts/DRAFT_RELEASE.json');branch=load(d/'receipts/REVIEW_BRANCH.json');fresh=load(d/'receipts/FRESH_PACKAGE_VERIFICATION.json')
        matches=[r for r in allreleases if r['tag_name']==f'study-v0.{n}'];need(len(matches)==1,'Requested draft missing or duplicate');r=matches[0]
        check_release(r,n,done['target_commit'],receipt['draft_release']['name']);need(len(r['assets'])==6,'Final asset count differs')
        for a in r['assets']:
            local=d/'dist'/a['name'];need(a['size']==info(local)['bytes'] and a['digest']=='sha256:'+info(local)['sha256'],'Final remote asset identity differs')
            need(info(d/'qa/authenticated_downloads'/a['name'])==info(local),'Final authenticated downloaded bytes differ')
        counts={};scopes=[];pdfmeta=None
        for kind in ('Study','Documentation','Code'):
            with zipfile.ZipFile(d/'dist'/f'QPathformer_v0.{n}_{kind}.zip') as z:
                prefix=f'QPathformer_v0.{n}_{kind}/'
                for member in z.namelist():
                    relative=member.removeprefix(prefix)
                    if '/' not in relative and relative.endswith('_LICENSE_SCOPE.json'):
                        scope=json.loads(z.read(member));scopes.append(dict(package=kind,path=relative,files=len(scope['files']),identity=bytes_info(z.read(member))))
                        if relative=='CODE_LICENSE_SCOPE.json':counts['python_files']=len(scope['files'])
                        if relative=='GUIDANCE_LICENSE_SCOPE.json':counts['prose_file_instances']=counts.get('prose_file_instances',0)+len(scope['files'])
                        if relative=='REPORT_LICENSE_SCOPE.json':counts['original_figures']=scope.get('figure_count',len(scope.get('embedded_figures',scope.get('source_figures',scope.get('figure_media',[])))))
                    if kind=='Study' and relative.endswith('.pdf'):
                        pdf=PdfReader(BytesIO(z.read(member)));md=pdf.metadata
                        need(md.author in ('Anthony Siljeg','Anthony Siljeg — Founder, Alnotrea Labs · Company affiliation: Alnotrea Pty Ltd · Q-Pathformer Initiative') and md.title and f'v0.{n}' in md.title,'PDF author/title metadata invalid')
                        counts['report_pages']=len(pdf.pages);page_total+=len(pdf.pages);pdfmeta=dict(title=md.title,author=md.author,pages=len(pdf.pages),path=relative,**bytes_info(z.read(member)))
        need(fresh['status']=='PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP','Final startup not pass')
        item=dict(study_version=f'v0.{n}',title=r['name'],draft_url=r['html_url'],release_id=r['id'],tag_name=r['tag_name'],target_commit=r['target_commitish'],draft=True,private=True,local_pack_folder=str(d),local_assets=str(d/'dist'),record_path=branch['record_path'],evidence_commit=done['evidence_commit'],evidence_url=f'https://github.com/{NAME}/blob/{done["evidence_commit"]}/{branch["record_path"]}/README.md',receipt_url=f'https://github.com/{NAME}/blob/{done["evidence_commit"]}/{branch["record_path"]}/DRAFT_RELEASE.json',assets=receipt['assets'],counts=counts,scopes=scopes,pdf=pdfmeta,startup_status='PASS',startup_scope=fresh['scope'],startup_binding=dict(path=str(d/'receipts/FRESH_PACKAGE_VERIFICATION.json'),**info(d/'receipts/FRESH_PACKAGE_VERIFICATION.json')),etel=n>=7,licensing_decisions_remaining=[])
        studies.append(item)
    need(page_total==275,'Unexpected total final report pages')
    inventory()
    for name in ('PREPARATION_BRIEF.md','STUDY_MATRIX.md'):
        p=B/name;write(p,p.read_text('utf-8').replace('exact rights proposals','exact adopted scope records').replace('proposed selections','final selections'))
    save(B/'CATALOG_HISTORY.json',dict(note='Catalog identity references are historical build-time observations. Both catalog byte identities are retained; use the digest to select the snapshot. Original content grants are the adopted scope records, not this convenience index.',snapshots=[dict(path=str(p),**info(p)) for p in [B/'history/ADOPTED_SCOPE_CATALOG_initial.json',B/'ADOPTED_SCOPE_CATALOG.json']]))
    final=dict(schema='qpath-eight-study-draft-review-index-1',status='PASS_ALL_EIGHT_PRIVATE_DRAFTS_READY_FOR_REVIEW',repository=dict(id=REPO_ID,name=NAME,private=True,edition='v1.0'),branch=BRANCH,main_unchanged=EXPECTED_BASE,protected_release_ids_unchanged=PROTECTED,latest='study-v0.9.5',draft_count=8,asset_count=48,sealed_packages=24,report_pages_visually_reviewed=page_total,code_startup_passes=8,owner_license_authorization='OWNER_LICENSE_AUTHORIZATION.json',licensing_decisions_remaining=[],license_exceptions_identified=[],studies=studies,review_items=['Historical internal/not-for-publication labels and recommendations remain original scientific evidence; appended edition notes explain the current scoped licensing.','Historical local paths, host configuration, execution recoveries and usage/accounting details are retained for owner review; no silent redaction. v0.9 pages 36–37 include credit/account and token accounting.','v0.9 original top-level READ_ME is a stale pre-study notice; the final report and new overview describe completed work.'],reproduction_boundaries=['All selected originals and report identities were checked against source evidence; this packaging task does not claim a new full multi-gigabyte archive rehash.','Raw datasets, checkpoints, installed environments, credentials and full operational archives are excluded. Full scientific repetition needs separately retained inputs and reviewed path/environment bindings.','Startup used compatible existing local environments. No clean-room installation, full training, official scoring, shot sampling or QPU jobs were performed.','Retained full-archive logical byte totals are distinct from ZIP sizes and do not define hardware minima.'],superseded_evidence='Earlier sealed builds remain under each study folder; revision receipts bind their identities. The first v0.5 draft assets were authenticated-downloaded and preserved locally before same-draft replacement, with SUPERSEDED_REMOTE_ASSETS.json retaining old and new identities.',completed_at_utc=now())
    save(B/'REVIEW_INDEX.json',final)
    rows=['# Q Pathformer eight study draft review','','All eight requested releases are drafts in the private official repository. All 48 uploaded assets were downloaded with authentication and matched byte-for-byte, size and SHA-256. Main and the three protected published releases are unchanged; study-v0.9.5 remains Latest.','',f'The 24 packages passed inventory, safe-path, hash, JSON, link and adopted-scope checks. All 275 report pages were visually reviewed, and all eight actual final Code ZIPs passed fresh-extraction offline startup.','', '| Study | GitHub draft | Evidence | Pages | Python files | Original figures | ETEL |','| --- | --- | --- | ---: | ---: | ---: | --- |']
    for e in studies:
        c=e['counts'];rows.append(f'| {e["study_version"]} | [Open draft]({e["draft_url"]}) | [Verification and scopes]({e["evidence_url"]}) | {c["report_pages"]} | {c["python_files"]} | {c["original_figures"]} | '+('Included' if e['etel'] else 'Not supplied')+' |')
    rows+=['','The owner adopted the same separately scoped licensing scheme as v0.1 and v0.9.5 on 29 October 2026. Exact controlled report content and listed prose use CC BY 4.0; exact selected Python files and helpers use unchanged Q-Pathformer Platform License 1.0. Earlier grants survive. Anthony Siljeg is licensor; company affiliation is not an ownership transfer. **No licensing decisions or conflicting-license exceptions remain identified for these selections.**','', 'The owner review should consider retained historical internal labels, local paths, host details, recovery discussions and usage/accounting information. Those were preserved rather than silently removed. The final report resolves the stale v0.9 pre-study README. Any future publication remains a separate action; nothing has been published.','','Full reproduction still requires separately retained data, checkpoints and historical environment/path bindings. Bounded startup is not clean-install validation or a new scientific run. Archive sizes are not ZIP sizes or hardware requirements.','','Local final pack folders:','']
    for e in studies:rows.append(f'- {e["study_version"]}: `{e["local_pack_folder"]}`; downloads are in its `dist` folder.')
    rows+=['','Earlier sealed candidates and superseded identities remain preserved. The v0.5 replacement receipt records the authenticated old bytes before replacement. The complete per-asset hashes, immutable evidence commits, startup scopes and final folder mapping are in REVIEW_INDEX.json.','']
    write(B/'REVIEW_INDEX.md','\n'.join(rows))
    local_index='\n'.join(rows)
    for e in studies:
        old=f'- {e["study_version"]}: `{e["local_pack_folder"]}`; downloads are in its `dist` folder.'
        folder=Path(e['local_pack_folder']).as_posix()
        local_index=local_index.replace(old,f'- {e["study_version"]}: [Open pack folder](<{folder}>) · [Open six assets](<{folder}/dist>)')
    write(B/'LOCAL_REVIEW_INDEX.md',local_index)
    write(B/'PROGRESS.md','# Preparation progress\n\nAll eight studies complete for private draft review.\n\n'+''.join('- [x] '+x+'\n' for x in ['Verified official repository identity/privacy and protected baseline','Inventoried all eight studies and source identities','Finalized exact adopted licenses and inherited coverage','Visually reviewed all 275 report pages','Sealed and verified 24 packages','Passed fresh actual Code ZIP startup for all eight studies','Committed review records only to dedicated preparation branch','Created or updated eight private drafts with 48 authenticated-download-verified assets','Rechecked unchanged main, published releases/assets/tags, private visibility and v0.9.5 Latest'])+'\nSee REVIEW_INDEX.md and REVIEW_INDEX.json. No publication or visibility change performed.\n')
    summary=R/'release_preparation/draft_batch_20261029';summary.mkdir(parents=True,exist_ok=True)
    for p in B.glob('*'):
        if p.is_file() and p.suffix.lower() in ('.md','.json') and p.name!='LOCAL_REVIEW_INDEX.md':shutil.copyfile(p,summary/p.name)
    for sub in ('receipts','history'):
        for p in (B/sub).glob('*.json'):
            dest=summary/sub/p.name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(p,dest)
    toolout=B/'tools/batch.py';toolout.parent.mkdir(exist_ok=True);shutil.copyfile(Path(__file__),toolout);(summary/'tools').mkdir(exist_ok=True);shutil.copyfile(toolout,summary/'tools/batch.py')
    # Clearly mark the first v0.5 record as superseded, retaining its original commit and bytes in history.
    old=R/'release_preparation/study-v0.5/README.md'
    if old.exists() and 'Superseded preparation record' not in old.read_text('utf-8'):
        write(old,'# Superseded preparation record\n\nThe final corrected v0.5 draft is indexed in revisions/draft_20261029_r02. This earlier preparation record and its original asset identities are historical; it is not the current download set.\n\n'+old.read_text('utf-8'))
    git('add','release_preparation/draft_batch_20261029','release_preparation/study-v0.5/README.md');git('commit','-m','Index eight verified private study drafts and review boundaries');git('push','origin',BRANCH)
    commit=git('rev-parse','HEAD').decode().strip();guard();need(not git('status','--porcelain').strip(),'Final checkout dirty');need(api(f'repos/{NAME}/commits/{BRANCH}')['sha']==commit,'Final remote branch differs')
    path='release_preparation/draft_batch_20261029/REVIEW_INDEX.md';got=api(f'repos/{NAME}/contents/{path}?ref={commit}');need(base64.b64decode(got['content'])==(B/'REVIEW_INDEX.md').read_bytes(),'Final review index remote differs')
    completion=dict(status=final['status'],repository_private=True,drafts=8,assets_verified=48,report_pages_reviewed=275,code_startups_passed=8,licensing_decisions_remaining=[],main_unchanged=EXPECTED_BASE,protected_releases_unchanged=True,latest='study-v0.9.5',branch=BRANCH,final_evidence_commit=commit,remote_review_index=f'https://github.com/{NAME}/blob/{commit}/{path}',local_review_index=str(B/'LOCAL_REVIEW_INDEX.md'),completed_at_utc=now())
    save(B/'receipts/COMPLETION.json',completion);print(json.dumps(completion,indent=2))

if __name__=='__main__':globals()[sys.argv[1]]()
