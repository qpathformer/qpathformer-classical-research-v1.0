"""Final-check and publish the approved v0.9 r3 release in the private repository."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import batch

BUILD=batch.BASE/'study-v0.9/draft_20261030_r3'
PUB=batch.BASE/'study-v0.9/publication_20261030_r3'
TARGET='51926b4c4f2ea003a7c5224d54cfb33089a73522'
ID=427666199
TAG='study-v0.9'
RECORD='release_preparation/study-v0.9/revisions/draft_20261030_r3'
PYTHON=Path(r'C:\Q2\Implementation_v0.1\.venv\Scripts\python.exe')
need,info,load,save,write,now=batch.need,batch.info,batch.load,batch.save,batch.write,batch.now

def capture():
    paths=dict(repository=f'repositories/{batch.REPO_ID}',releases=f'repos/{batch.NAME}/releases?per_page=100',latest=f'repos/{batch.NAME}/releases/latest',main=f'repos/{batch.NAME}/commits/main',tags=f'repos/{batch.NAME}/git/matching-refs/tags')
    with ThreadPoolExecutor(max_workers=5) as pool:return dict(zip(paths,pool.map(batch.api,paths.values())))

def release(state):return next(r for r in state['releases'] if r['id']==ID)

def assets(r):
    return {a['name']:dict(id=a['id'],bytes=a['size'],sha256=a['digest'].removeprefix('sha256:'),state=a['state']) for a in r['assets']}

def guards(state,baseline=None,published=False):
    repo=state['repository']
    need(repo['id']==batch.REPO_ID and repo['full_name']==batch.NAME and repo['private'] and repo['visibility']=='private','Repository identity/private visibility differs')
    need(state['main']['sha']==batch.EXPECTED_BASE,'Main changed')
    need(state['latest']['id']==427547832 and state['latest']['tag_name']=='study-v0.9.5','Latest must remain v0.9.5')
    r=release(state)
    need(r['tag_name']==TAG and r['target_commitish']==TARGET and not r['prerelease'],'Wrong release or target')
    need(r['draft'] is (not published),'Unexpected publication state')
    if published:need(r['published_at'] is not None,'Publication timestamp missing')
    expected={p.name:info(p) for p in (BUILD/'dist').iterdir()};actual=assets(r)
    need(set(expected)==set(actual) and len(actual)==6,'Wrong six assets')
    need(all(actual[n]['state']=='uploaded' and all(actual[n][k]==expected[n][k] for k in ('bytes','sha256')) for n in actual),'Asset identities differ')
    tags={e['ref']:e['object'] for e in state['tags']}
    if baseline:
        need({x['id']:batch.signature(x) for x in baseline['releases'] if x['id']!=ID}=={x['id']:batch.signature(x) for x in state['releases'] if x['id']!=ID},'Another release changed')
        oldtags={e['ref']:e['object'] for e in baseline['tags']}
        if published:
            need(set(tags)==set(oldtags)|{'refs/tags/'+TAG},'Unexpected tag changes')
            need(all(tags[k]==v for k,v in oldtags.items()),'Existing tag changed')
        else:need(tags==oldtags,'Tags changed before publication')
        need(assets(r)==assets(release(baseline)),'Assets replaced during publication')
    if published:
        obj=tags['refs/tags/'+TAG]
        while obj['type']=='tag':obj=batch.api(f'repos/{batch.NAME}/git/tags/{obj["sha"]}')['object']
        need(obj['type']=='commit' and obj['sha']==TARGET,'Published tag targets wrong commit')

def download_all(r,folder):
    folder.mkdir(parents=True,exist_ok=False)
    def one(a):
        data=batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','-H','Accept: application/octet-stream',timeout=180)
        ident=batch.bytes_info(data);need(ident==info(BUILD/'dist'/a['name']),'Authenticated download differs')
        need(a['size']==ident['bytes'] and a['digest']=='sha256:'+ident['sha256'],'Remote digest/size differs')
        (folder/a['name']).write_bytes(data)
        return dict(id=a['id'],name=a['name'],**ident,download_verified=True,url=a['browser_download_url'])
    with ThreadPoolExecutor(max_workers=3) as pool:return list(pool.map(one,r['assets']))

def snapshot(root):return {p.relative_to(root).as_posix():info(p) for p in sorted(root.rglob('*')) if p.is_file()}

def preflight():
    need(not PUB.exists(),'Publication evidence directory exists; preserve and inspect it')
    state=capture();guards(state)
    prior=load(BUILD/'receipts/REMOTE_BASELINE_V09_REVISION.json')
    need({r['id']:batch.signature(r) for r in state['releases'] if r['id']!=ID}=={r['id']:batch.signature(r) for r in prior['releases'] if r['id']!=ID},'Another release changed since approved draft preparation')
    need(state['tags']==prior['tags'],'Tags changed since draft preparation')
    need(not batch.git('status','--porcelain').strip(),'Preparation checkout dirty')
    need(not any(x['ref']=='refs/tags/'+TAG for x in state['tags']),'Tag already exists; inspect before publishing')
    audit=load(BUILD/'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json')
    need(audit['status']=='PASS','Separate successor audit absent')
    for p in audit['packages']:
        for key in ('zip','seal'):need(info(p[key]['path'])=={k:p[key][k] for k in ('bytes','sha256')},'Approved audit binds different assets')
    fresh=load(BUILD/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    need(fresh['status']=='PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP','Approved fresh startup absent')
    for key in ('code_zip','code_seal','code_startup_receipt'):
        e=fresh[key];need(info(e['path'])=={k:e[k] for k in ('bytes','sha256')},'Approved startup binding changed')
    body_review=load(BUILD/'receipts/FINAL_BODY_REVIEW.json');need(body_review['status']=='PASS_GITHUB_RENDERED_BODY_AND_LINKS','Approved rendered-body review absent')
    r=release(state);need(batch.bytes_info(r['body'].encode())==body_review['body_identity'],'Reviewed rendered body differs')
    approved=load(BUILD/'receipts/RELEASE_RECEIPT_LINK_REQUEST.json')
    need(r['body']==approved['body'] and r['name']==approved['name'],'Draft body/name changed since approval')
    need(batch.git('branch','--show-current').decode().strip()==batch.BRANCH,'Wrong preparation branch')
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==batch.git('rev-parse','HEAD').decode().strip(),'Preparation branch remote differs')
    PUB.mkdir()
    save(PUB/'BASELINE.json',state)
    save(PUB/'AUTHORIZATION.json',dict(date='2026-10-30',timezone='Australia/Sydney',owner_request='Perfect - approved. Lets run one final check and publish v0.9, keeping the repo private and v0.9.5 as Latest.',prior_approval='Updated v0.9 r3 private draft approved in the originating conversation',release_id=ID,tag=TAG,target_commit=TARGET,assets_unchanged=True))
    downloaded=download_all(r,PUB/'prepublication_downloads')
    dest=PUB/'final_check/fresh_extraction';packages=[];contents={}
    for kind in ('Study','Documentation','Code'):
        stem=f'QPathformer_v0.9_{kind}';zp=PUB/'prepublication_downloads'/(stem+'.zip');sp=zp.with_suffix('.seal.json')
        packages.append(batch.verify_package(zp,sp))
        with zipfile.ZipFile(zp) as z:
            for n in z.namelist():
                out=(dest/n).resolve();need(out.is_relative_to(dest.resolve()),'Unsafe extraction')
                data=z.read(n);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data);contents[n]=data
        root=dest/stem
        for e in load(root/'LICENSE_ADOPTION.json')['satisfied_by']:need(info(root/e['path'])=={k:e[k] for k in ('bytes','sha256')},'Adoption scope binding differs')
    clarify=load(BUILD/'report/REPORT_REVIEW_BOUNDARIES.json')
    need(info(PUB/'prepublication_downloads/QPathformer_v0.9_Study.zip')==clarify['study_zip'] and info(PUB/'prepublication_downloads/QPathformer_v0.9_Study.seal.json')==clarify['study_seal'],'Retained Study asset binding differs')
    need(info(dest/'QPathformer_v0.9_Study/reports/QPathformer_v0.9_Report_Edition_1.pdf')==clarify['report_pdf'],'Report preservation PDF binding differs')
    need(info(dest/'QPathformer_v0.9_Study/reports/QPathformer_v0.9_Report_Edition_1.docx')==clarify['report_docx'],'Report preservation DOCX binding differs')
    # Verify the full packaged source/report/guidance tree at the intended remote tag commit.
    commit=batch.api(f'repos/{batch.NAME}/git/commits/{TARGET}')
    tree=batch.api(f'repos/{batch.NAME}/git/trees/{commit["tree"]["sha"]}?recursive=1')
    need(not tree.get('truncated'),'Remote tree truncated')
    prefix=RECORD+'/packages/'
    remote={e['path'].removeprefix(prefix):e for e in tree['tree'] if e['path'].startswith(prefix) and e['type']=='blob'}
    need(set(remote)==set(contents),'Target package tree membership differs')
    for n,data in contents.items():
        git_sha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        need(remote[n]['sha']==git_sha,'Target packaged file differs: '+n)
    before=snapshot(dest);code=dest/'QPathformer_v0.9_Code';receipt=PUB/'FINAL_STARTUP.json'
    command=[str(PYTHON),'-B',str(code/'tools/startup_check.py'),'--output',str(receipt)]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1');env.pop('PYTHONOPTIMIZE',None)
    run=subprocess.run(command,cwd=code,env=env,capture_output=True,text=True,timeout=240)
    save(PUB/'FINAL_STARTUP_INVOCATION.json',dict(command=command,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr))
    need(run.returncode==0 and receipt.is_file(),'Final bounded startup failed')
    startup=load(receipt)
    need(startup['status']=='PASS' and len(startup['checks'])==4 and startup['cli_help_checks']==3 and startup['numerical_input_records']==2 and startup['parsed_python_files']==57,'Final startup scope differs')
    need(before==snapshot(dest),'Startup changed extracted package bytes or membership')
    need(not startup['errors'] and startup['package_bytes_unchanged'] and all(e['status']=='PASS' and e['returncode']==0 for e in startup['checks']),'Final startup failure details present')
    old_startup=load(fresh['code_startup_receipt']['path'])
    need(startup['integrity_after']['package_fingerprint_sha256']==old_startup['integrity_after']['package_fingerprint_sha256'],'Final fingerprint differs from approved startup')
    need([e['label'] for e in startup['checks']]==[e['label'] for e in old_startup['checks']],'Final check identities differ from approved startup')
    need({e['label'] for e in startup['checks'][1:]}=={x+' --help' for x in ('payload/study/quantum/study.py','payload/study/execution/launcher.py','payload/study/execution/bind_stage.py')},'Required CLI paths differ')
    need(all('usage:' in e['stdout'].lower() for e in startup['checks'][1:]),'Required CLI help output missing')
    codepack=next(e for e in packages if e['package'].endswith('_Code'))
    save(PUB/'FINAL_CHECK.json',dict(status='PASS_AUTHENTICATED_DOWNLOADS_TARGET_TREE_AND_FRESH_STARTUP',checked_at_utc=now(),assets=downloaded,packages=packages,target_commit=TARGET,target_tree=commit['tree']['sha'],target_packaged_files_verified=len(contents),code_zip=codepack['zip'],code_seal=codepack['seal'],startup=dict(path=str(receipt),**info(receipt)),package_bytes_unchanged=True,startup_checks=4,cli_help_checks=3,numerical_input_records=2,parsed_python_files=57,numpy_version=startup['numpy_version'],scipy_version=startup['scipy_version'],independent_successor_audit=dict(path=str(BUILD/'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json'),**info(BUILD/'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json')),boundary='Final publication check of exact approved assets and the numerical smoke check and three CLI help paths; no model-family suite, Banknote preprocessing, complete accepted replay, ETEL fit/recovery execution, scientific training, official scoring, conversion-parity, sampling or QPU execution.'))
    finish_preflight()

def finish_preflight():
    state=load(PUB/'BASELINE.json');r=release(state)
    final=load(PUB/'FINAL_CHECK.json')
    need(final['status']=='PASS_AUTHENTICATED_DOWNLOADS_TARGET_TREE_AND_FRESH_STARTUP' and final['target_commit']==TARGET,'Final asset/startup check absent')
    need(info(final['startup']['path'])=={k:final['startup'][k] for k in ('bytes','sha256')},'Final startup receipt changed')
    for a in final['assets']:
        need(info(PUB/'prepublication_downloads'/a['name'])==info(BUILD/'dist'/a['name'])=={k:a[k] for k in ('bytes','sha256')},'Final download changed')
    guards(capture(),state)
    body=r['body']
    replacements={
        '**Draft for owner review · Private repository · Study · Documentation · Code**':'**Published release · Private repository · Study · Documentation · Code**',
        'This remains a draft in the private repository. **Study v0.9.5 remains Latest.**':'Published on 30 October 2026 in the private repository. Repository access remains restricted; publication does not change the adopted scoped licences. Study v0.9.5 remains designated Latest.',
        '[Authenticated draft assets]':'[Historical prepublication asset verification]'
    }
    for a,b in replacements.items():
        need(body.count(a)==1,'Expected publication wording missing or ambiguous: '+a);body=body.replace(a,b)
    need('private draft' not in body and 'draft_20261029_r2' not in body,'Stale draft wording or predecessor evidence')
    links=[]
    for sha,path in re.findall(r'https://github\.com/'+re.escape(batch.NAME)+r'/blob/([0-9a-f]{40})/([^\s)]+)',body):
        got=batch.api(f'repos/{batch.NAME}/contents/{path}?ref={sha}')
        need(got['type']=='file','Evidence link is not a file')
        data=base64.b64decode(got['content']);need(data==(batch.R/path).read_bytes(),'Evidence differs from reviewed checkout')
        links.append(dict(commit=sha,path=path,**batch.bytes_info(data)))
    guards(capture(),state)
    need(len(links)==7,'Expected seven final body evidence links')
    render_request=PUB/'FINAL_BODY_RENDER_REQUEST.json';save(render_request,dict(text=body,mode='gfm',context=batch.NAME))
    html=batch.run(batch.GH,'api','markdown','--method','POST','--input',render_request).decode('utf-8')
    class Structure(HTMLParser):
        def __init__(self):super().__init__();self.tags={}
        def handle_starttag(self,tag,attrs):self.tags[tag]=self.tags.get(tag,0)+1
    parser=Structure();parser.feed(html)
    need(parser.tags.get('table')==2 and parser.tags.get('h3')==5 and not parser.tags.get('h1'),'Final body structure differs')
    need('Published release' in html and 'remains designated Latest' in html and 'Draft for owner review' not in html,'Final publication wording differs')
    write(PUB/'FINAL_RENDERED_BODY.html',html)
    save(PUB/'FINAL_RENDERED_BODY_REVIEW.json',dict(status='PASS_GITHUB_RENDERED_PUBLICATION_BODY',rendered_html=dict(path=str(PUB/'FINAL_RENDERED_BODY.html'),**info(PUB/'FINAL_RENDERED_BODY.html')),tables=2,headings=5,evidence_links=7,scope='GitHub Markdown renderer output; only publication-status wording changed. No browser pixel inspection claimed.'))
    request=dict(tag_name=TAG,target_commitish=TARGET,name=r['name'],body=body,draft=False,prerelease=False,make_latest='false')
    save(PUB/'PUBLISH_REQUEST.json',request);write(PUB/'PUBLISHED_RELEASE_BODY.md',body)
    save(PUB/'PREFLIGHT.json',dict(status='PASS_READY_TO_PUBLISH',checked_at_utc=now(),release_id=ID,target_commit=TARGET,assets=assets(r),evidence_links=links,repository_private=True,latest='study-v0.9.5',final_check=dict(path=str(PUB/'FINAL_CHECK.json'),**info(PUB/'FINAL_CHECK.json'))))
    print(json.dumps(dict(status='PASS_READY_TO_PUBLISH',release_id=ID,target_commit=TARGET,assets=6,packaged_files=final['target_packaged_files_verified'],evidence_links=len(links),startup_checks=4,cli_help_checks=3,make_latest=False)))

def publish():
    preflight=load(PUB/'PREFLIGHT.json');need(preflight['status']=='PASS_READY_TO_PUBLISH','Preflight incomplete')
    binding=preflight['final_check'];need(info(binding['path'])=={k:binding[k] for k in ('bytes','sha256')},'Final check changed')
    before=load(PUB/'BASELINE.json');current=capture();guards(current,before)
    need(batch.signature(release(current))==batch.signature(release(before)),'Draft changed since final preflight')
    req=load(PUB/'PUBLISH_REQUEST.json')
    response=batch.api(f'repos/{batch.NAME}/releases/{ID}','--method','PATCH','--input',PUB/'PUBLISH_REQUEST.json')
    save(PUB/'PUBLISH_RESPONSE.json',response)
    after=capture()
    if after['latest']['id']!=427547832:
        save(PUB/'RESTORE_LATEST_REQUEST.json',dict(make_latest='true'))
        batch.api(f'repos/{batch.NAME}/releases/427547832','--method','PATCH','--input',PUB/'RESTORE_LATEST_REQUEST.json');after=capture()
    guards(after,before,published=True)
    r=release(after);need(r['body']==req['body'],'Published body differs')
    verified=download_all(r,PUB/'authenticated_downloads')
    after=capture();guards(after,before,published=True)
    save(PUB/'POST_PUBLICATION_STATE.json',after)
    receipt=dict(schema='qpath-publication-receipt-1',status='PASS_PUBLISHED_PRIVATE_REPOSITORY',study_version='v0.9',release_id=ID,release_url=r['html_url'],tag=TAG,target_commit=TARGET,published_at=r['published_at'],checked_at_utc=now(),draft=False,prerelease=False,immutable=r.get('immutable'),repository=dict(id=batch.REPO_ID,name=batch.NAME,private=True,visibility='private'),latest=dict(id=427547832,tag='study-v0.9.5'),assets=verified,main_unchanged=batch.EXPECTED_BASE,other_releases_unchanged=True,prior_tags_unchanged=True,new_tag='refs/tags/'+TAG,package_bytes_unchanged=True,report_and_scientific_source_unchanged=True,automatic_source_archives=dict(zipball_url=r['zipball_url'],tarball_url=r['tarball_url']),historical_draft_evidence=str(BUILD/'receipts/DRAFT_RELEASE.json'),authorization=dict(path=str(PUB/'AUTHORIZATION.json'),**info(PUB/'AUTHORIZATION.json')),final_check=binding)
    save(PUB/'PUBLICATION_RECEIPT.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','release_url','published_at','target_commit','repository','latest')},indent=2))

def record():
    receipt=load(PUB/'PUBLICATION_RECEIPT.json');guards(capture(),load(PUB/'BASELINE.json'),published=True)
    need(not batch.git('status','--porcelain').strip(),'Preparation checkout dirty')
    path='release_preparation/study-v0.9/publication_20261030_r3';dest=batch.R/path
    need(not dest.exists(),'Publication already recorded');dest.mkdir(parents=True)
    for p in PUB.iterdir():
        if p.is_file() and p.suffix in ('.json','.md','.html'):shutil.copyfile(p,dest/p.name)
    shutil.copyfile(Path(__file__),dest/'publish_v09.py')
    write(dest/'README.md',f'# Published study v0.9\n\n[Open published release]({receipt["release_url"]}) · [Publication receipt](PUBLICATION_RECEIPT.json) · [Final check](FINAL_CHECK.json).\n\nPublished in the private repository on 30 October 2026 at reviewed commit `{TARGET}`. All six r3 assets were preserved and authenticated-downloaded before and after publication. All 116 packaged files match the reviewed target commit; final startup passed its two-input numerical smoke check and all three CLI help paths, with 57 Python files parsed. This does not test all model variants, Banknote preprocessing, complete accepted replay or ETEL execution/recovery. v0.9.5 remains Latest; main, other releases and prior tags are unchanged. Earlier draft receipts retain their historical meaning.\n')
    history=batch.B/'history/before_v09_publication';need(not history.exists(),'Preserve previous index history')
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md','receipts/COMPLETION.json'):
        p=history/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(batch.B/name,p)
    index=load(batch.B/'REVIEW_INDEX.json');item=next(x for x in index['studies'] if x['study_version']=='v0.9');oldurl=item['draft_url']
    item.update(draft=False,publication_status='published',release_url=receipt['release_url'],published_at=receipt['published_at'],publication_record_path=path+'/PUBLICATION_RECEIPT.json')
    item['historical_draft_url']=item.pop('draft_url')
    status='V02_V03_V04_V05_V06_V07_V08_V09_PUBLISHED_NO_PRIVATE_DRAFTS_REMAIN'
    need(sum(x['draft'] for x in index['studies'])==0,'Expected all eight study drafts to be published')
    index.update(status=status,draft_count=0,published_from_batch_count=8,completed_at_utc=now())
    index['latest_revision_note']='v0.2 through v0.9 are published in the private repository; all eight studies in this batch are published and v0.9.5 remains Latest.'
    index['superseded_evidence']+=' v0.9 publication is separately recorded; its historical draft records and prior index remain preserved.'
    save(batch.B/'REVIEW_INDEX.json',index)
    for name in ('REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md'):
        text=(batch.B/name).read_text('utf-8')
        text=text.replace('v0.2 through v0.8 are published in the private official repository; v0.9 remains a draft.','v0.2 through v0.9 are published in the private official repository; all eight studies in this batch are published.')
        text=text.replace(f'[Open draft]({oldurl})',f'[Published v0.9]({receipt["release_url"]})')
        text=text.replace('The owner authorized and completed v0.2 through v0.8 publication. v0.9 remains unpublished.','The owner authorized and completed v0.2 through v0.9 publication. All eight studies in this batch are published.')
        text=text.replace('v0.9 remains a private draft.','v0.9 is now published in the private repository.')
        text+='\nPublished v0.9 uses the unchanged r3 ZIPs and seals. Its final publication check and receipt are retained separately from historical draft receipts. Repository access remains private and v0.9.5 remains Latest.\n'
        write(batch.B/name,text)
    review=batch.R/'release_preparation/draft_batch_20261029'
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md'):shutil.copyfile(batch.B/name,review/name)
    for p in history.rglob('*'):
        if p.is_file() and p.name!='LOCAL_REVIEW_INDEX.md':
            out=review/'history/before_v09_publication'/p.relative_to(history);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)
    currentpath=batch.R/'release_preparation/study-v0.9/CURRENT.json';current=load(currentpath)
    current.update(draft=False,publication_status='published',release_url=receipt['release_url'],published_at=receipt['published_at'],publication_record_path=path+'/PUBLICATION_RECEIPT.json');save(currentpath,current)
    batch.git('add',path,'release_preparation/draft_batch_20261029','release_preparation/study-v0.9/CURRENT.json')
    batch.git('commit','-m','Record v0.9 publication with private access and retained Latest');batch.git('push','origin',batch.BRANCH)
    commit=batch.git('rev-parse','HEAD').decode().strip()
    for relative in (path+'/PUBLICATION_RECEIPT.json','release_preparation/draft_batch_20261029/REVIEW_INDEX.json','release_preparation/study-v0.9/CURRENT.json'):
        got=batch.api(f'repos/{batch.NAME}/contents/{relative}?ref={commit}')
        need(base64.b64decode(got['content'])==(batch.R/relative).read_bytes(),'Remote publication evidence differs')
    guards(capture(),load(PUB/'BASELINE.json'),published=True)
    need(not batch.git('status','--porcelain').strip(),'Preparation checkout dirty after recording')
    need(batch.api(f'repos/{batch.NAME}/commits/{batch.BRANCH}')['sha']==commit,'Remote branch differs')
    completion=dict(status=receipt['status'],release_url=receipt['release_url'],publication_receipt=f'https://github.com/{batch.NAME}/blob/{commit}/{path}/PUBLICATION_RECEIPT.json',evidence_commit=commit,tag_commit=TARGET,repository_private=True,latest='study-v0.9.5',assets_verified=6,startup_checks_passed=4,cli_help_checks=3,numerical_input_records=2,completed_at_utc=now())
    save(PUB/'COMPLETION.json',completion)
    batch_completion=load(history/'receipts/COMPLETION.json');batch_completion.update(status=status,drafts=0,published_from_batch=8,latest_revision='v0.9 publication',final_evidence_commit=commit,remote_review_index=f'https://github.com/{batch.NAME}/blob/{commit}/release_preparation/draft_batch_20261029/REVIEW_INDEX.md',completed_at_utc=now());save(batch.B/'receipts/COMPLETION.json',batch_completion)
    print(json.dumps(completion,indent=2))

if __name__=='__main__':globals()[sys.argv[1]]()
