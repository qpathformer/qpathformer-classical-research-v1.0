"""Check the final GitHub-rendered body structure and all pinned evidence links."""
from pathlib import Path
from html.parser import HTMLParser
import base64,json,re,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import v08_r3 as p
class Structure(HTMLParser):
    def __init__(self):super().__init__();self.tags={};self.text=[]
    def handle_starttag(self,tag,attrs):self.tags[tag]=self.tags.get(tag,0)+1
    def handle_data(self,data):self.text.append(data)
p.guard_other_releases()
r=p.batch.api(f'repos/{p.batch.NAME}/releases/{p.RELEASE_ID}')
expected=p.load(p.NEW/'receipts/RELEASE_RECEIPT_LINK_REQUEST.json')
p.need(r['draft'] and r['body']==expected['body'],'Draft content differs')
uploaded=p.load(p.NEW/'receipts/DRAFT_RELEASE.json')
p.need({a['name']:(a['id'],a['size'],a['digest']) for a in r['assets']}=={a['name']:(a['id'],a['bytes'],'sha256:'+a['sha256']) for a in uploaded['assets']},'Final draft assets changed')
request=p.NEW/'qa/RENDER_BODY_REQUEST.json';p.save(request,dict(text=r['body'],mode='gfm',context=p.batch.NAME))
html=p.batch.run(p.batch.GH,'api','markdown','--method','POST','--input',request).decode('utf-8')
parser=Structure();parser.feed(html);text=' '.join(parser.text)
p.need(parser.tags.get('table')==2 and parser.tags.get('h3')==5 and not parser.tags.get('h1'),'Unexpected rendered body structure')
for phrase in ('Historical findings','What changed in this study','Historical verification and limitations','Downloads and release-packaging checks','Scoped licensing','0.2.0','v0.9.5 remains Latest'):
    p.need(phrase in text,'Rendered text missing '+phrase)
p.need('{{' not in html and '}}' not in html,'Unresolved template placeholder')
links=[]
for sha,path in re.findall(r'https://github\.com/'+re.escape(p.batch.NAME)+r'/blob/([0-9a-f]{40})/([^\s)]+)',r['body']):
    got=p.batch.api(f'repos/{p.batch.NAME}/contents/{path}?ref={sha}');data=base64.b64decode(got['content']);p.need(data==(p.batch.R/path).read_bytes(),'Pinned body evidence differs '+path)
    links.append(dict(commit=sha,path=path,**p.batch.bytes_info(data)))
p.need(len(links)==7,'Expected seven body evidence links')
out=p.NEW/'qa/GITHUB_RENDERED_BODY.html';p.write(out,html)
p.save(p.NEW/'receipts/FINAL_BODY_REVIEW.json',dict(status='PASS_GITHUB_RENDERED_BODY_AND_LINKS',checked_at_utc=p.now(),release_id=p.RELEASE_ID,body_identity=p.batch.bytes_info(r['body'].encode()),rendered_html=dict(path=str(out),**p.info(out)),rendered_tables=2,rendered_section_headings=5,evidence_links=links,draft=True,repository_private=True,v095_latest=True,boundary='GitHub Markdown renderer output checked for structure, text and exact commit-pinned links. No new browser-page pixel inspection is claimed.'))
print(json.dumps(dict(status='PASS_GITHUB_RENDERED_BODY_AND_LINKS',tables=2,headings=5,evidence_links=7)))
