"""Publish the approved v0.4 r3 release without changing repository access."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import batch

BUILD = batch.BASE / 'study-v0.4/draft_20261029_r3'
PUB = batch.BASE / 'study-v0.4/publication_20261029_r3'
TARGET = '4b3f08eaa14e166c0781d7921f6b157aba48644c'
ID = 427659592
TAG = 'study-v0.4'
need, info, load, save, write, now = batch.need, batch.info, batch.load, batch.save, batch.write, batch.now

def capture():
    paths = dict(repository=f'repositories/{batch.REPO_ID}', releases=f'repos/{batch.NAME}/releases?per_page=100', latest=f'repos/{batch.NAME}/releases/latest', main=f'repos/{batch.NAME}/commits/main', tags=f'repos/{batch.NAME}/git/matching-refs/tags')
    with ThreadPoolExecutor(max_workers=5) as pool:
        return dict(zip(paths, pool.map(batch.api, paths.values())))

def release(state):
    return next(r for r in state['releases'] if r['id'] == ID)

def assets(r):
    return {a['name']: dict(id=a['id'], bytes=a['size'], sha256=a['digest'].removeprefix('sha256:'), state=a['state']) for a in r['assets']}

def guards(state, baseline=None, published=False):
    repo=state['repository']
    need(repo['id']==batch.REPO_ID and repo['full_name']==batch.NAME and repo['private'] and repo['visibility']=='private','Repository identity or private visibility differs')
    need(state['main']['sha']==batch.EXPECTED_BASE,'Main changed')
    need(state['latest']['id']==427547832 and state['latest']['tag_name']=='study-v0.9.5','Latest must remain v0.9.5')
    r=release(state)
    need(r['tag_name']==TAG and r['target_commitish']==TARGET and not r['prerelease'],'Wrong release or target')
    need(r['draft'] is (not published),'Unexpected publication state')
    if published: need(r['published_at'] is not None,'Publication timestamp missing')
    expected={p.name:info(p) for p in (BUILD/'dist').iterdir()}
    actual=assets(r)
    need(set(expected)==set(actual) and len(actual)==6,'Wrong six assets')
    need(all(actual[n]['state']=='uploaded' and all(actual[n][k]==expected[n][k] for k in ('bytes','sha256')) for n in actual),'Asset identities differ')
    tags={e['ref']:e['object'] for e in state['tags']}
    if baseline:
        before={x['id']:batch.signature(x) for x in baseline['releases'] if x['id']!=ID}
        after={x['id']:batch.signature(x) for x in state['releases'] if x['id']!=ID}
        need(before==after,'Another release changed')
        oldtags={e['ref']:e['object'] for e in baseline['tags']}
        if published:
            need(set(tags)==set(oldtags)|{'refs/tags/'+TAG},'Unexpected tag changes')
            need(all(tags[k]==v for k,v in oldtags.items()),'Existing tag changed')
        else: need(tags==oldtags,'Tags changed before publication')
        need(assets(r)==assets(release(baseline)),'Assets replaced during publication')
    if published:
        obj=tags['refs/tags/'+TAG]
        while obj['type']=='tag': obj=batch.api(f'repos/{batch.NAME}/git/tags/{obj["sha"]}')['object']
        need(obj['type']=='commit' and obj['sha']==TARGET,'Published tag targets wrong commit')

def preflight():
    need(not PUB.exists(),'Publication evidence directory exists; preserve it')
    state=capture();guards(state)
    prior=load(BUILD/'receipts/REMOTE_BASELINE_V04_REVISION.json')
    need({r['id']:batch.signature(r) for r in state['releases'] if r['id']!=ID}=={r['id']:batch.signature(r) for r in prior['releases'] if r['id']!=ID},'Another release changed since draft review')
    need(state['tags']==prior['tags'],'Tags changed since draft review')
    need(not batch.git('status','--porcelain').strip(),'Preparation checkout dirty')
    need(not any(x['ref']=='refs/tags/'+TAG for x in state['tags']),'Tag already exists; inspect before publishing')
    need(load(BUILD/'receipts/INDEPENDENT_SUCCESSOR_AUDIT.json')['status']=='PASS','Independent audit absent')
    fresh=load(BUILD/'receipts/FRESH_PACKAGE_VERIFICATION.json')
    need(fresh['status']=='PASS_FRESH_EXTRACTION_AND_BOUNDED_STARTUP','Fresh startup absent')
    for key in ('code_zip','code_seal','code_startup_receipt'):
        e=fresh[key];need(info(e['path'])=={k:e[k] for k in ('bytes','sha256')},'Startup binding changed')
    for kind in ('Study','Documentation','Code'):
        batch.verify_package(BUILD/'dist'/f'QPathformer_v0.4_{kind}.zip',BUILD/'dist'/f'QPathformer_v0.4_{kind}.seal.json')
    r=release(state);body=r['body']
    replacements={
        '**Draft for owner review · Private repository · Study · Documentation · Code**':'**Published release · Private repository · Study · Documentation · Code**',
        "This release remains a draft in the private repository. The publisher's public release remains subject to owner review. This does not limit reuse permitted under the adopted CC BY 4.0 grant. Scoped licensing is adopted separately from publication. **Study v0.9.5 remains Latest.**":'Published on 29 October 2026 in the private repository. Repository access remains restricted; publication does not change the adopted scoped licences. Study v0.9.5 remains designated Latest.',
        '[Authenticated draft assets]':'[Historical prepublication asset verification]'
    }
    for a,b in replacements.items():
        need(body.count(a)==1,'Expected publication wording missing or ambiguous: '+a)
        body=body.replace(a,b)
    need('candidate' not in body and 'private draft' not in body,'Stale publication wording')
    need('draft_20261029_r2' not in body,'Stale predecessor evidence link')
    links=[]
    for commit,path in re.findall(r'https://github\.com/'+re.escape(batch.NAME)+r'/blob/([0-9a-f]{40})/([^\s)]+)',body):
        got=batch.api(f'repos/{batch.NAME}/contents/{path}?ref={commit}')
        need(got['type']=='file','Evidence link is not a file')
        links.append(dict(commit=commit,path=path,sha256=hashlib.sha256(base64.b64decode(got['content'])).hexdigest()))
    independent=Path(__file__).resolve().parent/'v04_publication_check/PREFLIGHT_REVIEW.json'
    review=load(independent)
    need(review['status']=='PASS','Independent publication review absent')
    need(review['release_id']==ID and review['target_commit']==TARGET,'Independent review refers to another release')
    PUB.mkdir()
    shutil.copyfile(independent,PUB/'INDEPENDENT_PUBLICATION_REVIEW.json')
    save(PUB/'BASELINE.json',state)
    save(PUB/'AUTHORIZATION.json',dict(date='2026-10-29',timezone='Australia/Sydney',owner_request="Perfect - lets finalise and publish v0.4, keeping the repo private and v0.9.5 as Latest. we'll resume tomorrow for the 0.5 to 0.9 releases. nice work",release_id=ID,tag=TAG,target_commit=TARGET,assets_unchanged=True))
    request=dict(tag_name=TAG,target_commitish=TARGET,name=r['name'],body=body,draft=False,prerelease=False,make_latest='false')
    save(PUB/'PUBLISH_REQUEST.json',request)
    write(PUB/'PUBLISHED_RELEASE_BODY.md',body)
    save(PUB/'PREFLIGHT.json',dict(status='PASS_READY_TO_PUBLISH',checked_at_utc=now(),release_id=ID,target_commit=TARGET,assets=assets(r),evidence_links=links,repository_private=True,latest='study-v0.9.5',independent_review=dict(path=str(PUB/'INDEPENDENT_PUBLICATION_REVIEW.json'),**info(PUB/'INDEPENDENT_PUBLICATION_REVIEW.json'))))
    print(json.dumps(dict(status='PASS_READY_TO_PUBLISH',release_id=ID,target_commit=TARGET,assets=6,evidence_links=len(links),make_latest=False)))

def publish():
    before=load(PUB/'BASELINE.json');current=capture();guards(current,before)
    need(batch.signature(release(current))==batch.signature(release(before)),'Draft changed since final preflight')
    req=load(PUB/'PUBLISH_REQUEST.json')
    response=batch.api(f'repos/{batch.NAME}/releases/{ID}','--method','PATCH','--input',PUB/'PUBLISH_REQUEST.json')
    save(PUB/'PUBLISH_RESPONSE.json',response)
    after=capture()
    if after['latest']['id']!=427547832:
        save(PUB/'RESTORE_LATEST_REQUEST.json',dict(make_latest='true'))
        batch.api(f'repos/{batch.NAME}/releases/427547832','--method','PATCH','--input',PUB/'RESTORE_LATEST_REQUEST.json')
        after=capture()
    guards(after,before,published=True)
    r=release(after);need(r['body']==req['body'],'Published body differs')
    def download(a):
        data=batch.run(batch.GH,'api',f'repos/{batch.NAME}/releases/assets/{a["id"]}','-H','Accept: application/octet-stream',timeout=180)
        need(batch.bytes_info(data)==info(BUILD/'dist'/a['name']),'Published download differs')
        p=PUB/'authenticated_downloads'/a['name'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        return dict(id=a['id'],name=a['name'],**batch.bytes_info(data),download_verified=True,url=a['browser_download_url'])
    with ThreadPoolExecutor(max_workers=3) as pool: verified=list(pool.map(download,r['assets']))
    save(PUB/'POST_PUBLICATION_STATE.json',after)
    receipt=dict(schema='qpath-publication-receipt-1',status='PASS_PUBLISHED_PRIVATE_REPOSITORY',study_version='v0.4',release_id=ID,release_url=r['html_url'],tag=TAG,target_commit=TARGET,published_at=r['published_at'],checked_at_utc=now(),draft=False,prerelease=False,immutable=r.get('immutable'),repository=dict(id=batch.REPO_ID,name=batch.NAME,private=True,visibility='private'),latest=dict(id=427547832,tag='study-v0.9.5'),assets=verified,main_unchanged=batch.EXPECTED_BASE,other_releases_unchanged=True,prior_tags_unchanged=True,new_tag='refs/tags/'+TAG,package_bytes_unchanged=True,report_and_scientific_source_unchanged=True,automatic_source_archives=dict(zipball_url=r['zipball_url'],tarball_url=r['tarball_url']),historical_draft_evidence=str(BUILD/'receipts/DRAFT_RELEASE.json'),authorization=dict(path=str(PUB/'AUTHORIZATION.json'),**info(PUB/'AUTHORIZATION.json')))
    save(PUB/'PUBLICATION_RECEIPT.json',receipt)
    print(json.dumps({k:receipt[k] for k in ['status','release_url','published_at','target_commit','repository','latest']},indent=2))

def record():
    receipt=load(PUB/'PUBLICATION_RECEIPT.json')
    write(PUB/'NEXT_SESSION.md','# Next release session\n\nv0.4 is published in the private repository using the verified r3 assets. v0.9.5 remains Latest. The owner plans to resume v0.5 through v0.9 tomorrow; those five releases remain unchanged private drafts. Begin the next session with v0.5 review notes and the current review index. No scheduled automation was requested.\n')
    guards(capture(),load(PUB/'BASELINE.json'),published=True)
    need(not batch.git('status','--porcelain').strip(),'Preparation checkout dirty')
    path='release_preparation/study-v0.4/publication_20261029_r3';dest=batch.R/path
    need(not dest.exists(),'Publication already recorded')
    dest.mkdir(parents=True)
    for p in PUB.iterdir():
        if p.is_file() and p.suffix in ('.json','.md'):shutil.copyfile(p,dest/p.name)
    shutil.copyfile(Path(__file__),dest/'publish_v04.py')
    write(dest/'README.md',f'# Published study v0.4\n\n[Open published release]({receipt["release_url"]}) · [Publication receipt](PUBLICATION_RECEIPT.json).\n\nPublished in the private repository on 29 October 2026 at the reviewed commit `{TARGET}`. All six r3 assets were preserved and authenticated-downloaded after publication. v0.9.5 remains Latest; main, all other releases and prior tags are unchanged. Earlier draft receipts retain their historical meaning.\n')
    history=batch.B/'history/before_v04_publication'
    need(not history.exists(),'Prior publication index history exists')
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md','receipts/COMPLETION.json'):
        p=history/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(batch.B/name,p)
    index=load(batch.B/'REVIEW_INDEX.json');item=next(x for x in index['studies'] if x['study_version']=='v0.4');oldurl=item['draft_url']
    item.update(draft=False,publication_status='published',release_url=receipt['release_url'],published_at=receipt['published_at'],publication_record_path=path+'/PUBLICATION_RECEIPT.json')
    item['historical_draft_url']=item.pop('draft_url')
    index.update(status='V02_V03_V04_PUBLISHED_FIVE_PRIVATE_DRAFTS_REMAIN',draft_count=5,published_from_batch_count=3,completed_at_utc=now())
    index['latest_revision_note']='v0.2, v0.3 and v0.4 are published in the private repository; v0.5–v0.9 remain drafts and v0.9.5 remains Latest.'
    index['superseded_evidence']+=' v0.4 publication is separately recorded; its historical draft records and prior index remain preserved.'
    save(batch.B/'REVIEW_INDEX.json',index)
    for name in ('REVIEW_INDEX.md','LOCAL_REVIEW_INDEX.md'):
        text=(batch.B/name).read_text('utf-8')
        text=text.replace('# Q Pathformer eight study draft review','# Q Pathformer study release review')
        text=text.replace('v0.2 and v0.3 are published in the private official repository; v0.4–v0.9 remain drafts.','v0.2, v0.3 and v0.4 are published in the private official repository; v0.5–v0.9 remain drafts.')
        text=text.replace('| GitHub draft |','| GitHub release |')
        text=text.replace(f'[Open draft]({oldurl})',f'[Published v0.4]({receipt["release_url"]})')
        text=text.replace('The owner authorized and completed v0.2 and v0.3 publication. The other six drafts remain unpublished.','The owner authorized and completed v0.2, v0.3 and v0.4 publication. The other five drafts remain unpublished.')
        text=text.replace('v0.4 remains a private draft.','v0.4 is now published in the private repository.')
        text+='\nPublished v0.4 uses the unchanged r3 ZIPs and seals. Its publication receipt is retained separately from the historical draft receipts. Repository access remains private and v0.9.5 remains Latest.\n'
        write(batch.B/name,text)
    review=batch.R/'release_preparation/draft_batch_20261029'
    for name in ('REVIEW_INDEX.json','REVIEW_INDEX.md'):shutil.copyfile(batch.B/name,review/name)
    for p in history.rglob('*'):
        if p.is_file() and p.name!='LOCAL_REVIEW_INDEX.md':
            out=review/'history/before_v04_publication'/p.relative_to(history);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)
    currentpath=batch.R/'release_preparation/study-v0.4/CURRENT.json';current=load(currentpath)
    current.update(draft=False,publication_status='published',release_url=receipt['release_url'],published_at=receipt['published_at'],publication_record_path=path+'/PUBLICATION_RECEIPT.json');save(currentpath,current)
    batch.git('add',path,'release_preparation/draft_batch_20261029','release_preparation/study-v0.4/CURRENT.json')
    batch.git('commit','-m','Record v0.4 publication with private access and retained Latest')
    batch.git('push','origin',batch.BRANCH)
    commit=batch.git('rev-parse','HEAD').decode().strip()
    got=batch.api(f'repos/{batch.NAME}/contents/{path}/PUBLICATION_RECEIPT.json?ref={commit}')
    need(base64.b64decode(got['content'])==(PUB/'PUBLICATION_RECEIPT.json').read_bytes(),'Remote publication receipt differs')
    guards(capture(),load(PUB/'BASELINE.json'),published=True)
    need(not batch.git('status','--porcelain').strip(),'Preparation checkout dirty after recording')
    completion=dict(status=receipt['status'],release_url=receipt['release_url'],publication_receipt=f'https://github.com/{batch.NAME}/blob/{commit}/{path}/PUBLICATION_RECEIPT.json',evidence_commit=commit,tag_commit=TARGET,repository_private=True,latest='study-v0.9.5',assets_verified=6,completed_at_utc=now())
    save(PUB/'COMPLETION.json',completion)
    batch_completion=load(history/'receipts/COMPLETION.json');batch_completion.update(status='V02_V03_V04_PUBLISHED_FIVE_PRIVATE_DRAFTS_REMAIN',drafts=5,published_from_batch=3,final_evidence_commit=commit,remote_review_index=f'https://github.com/{batch.NAME}/blob/{commit}/release_preparation/draft_batch_20261029/REVIEW_INDEX.md',completed_at_utc=now());save(batch.B/'receipts/COMPLETION.json',batch_completion)
    print(json.dumps(completion,indent=2))

if __name__=='__main__': globals()[sys.argv[1]]()
