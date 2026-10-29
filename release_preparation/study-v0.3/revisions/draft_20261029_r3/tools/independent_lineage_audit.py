"""Supplemental direct audit of new helper lineage and preserved input assets."""
from pathlib import Path
from datetime import datetime, timezone
import difflib, hashlib, json, zipfile

ROOT=Path(r'C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.3')
NEW=ROOT/'draft_20261029_r3'
OLD=ROOT/'draft_20261029_r2'
OUT=NEW/'receipts/INDEPENDENT_HELPER_LINEAGE_AUDIT.json'

def ident(b):return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def load(p):return json.loads(Path(p).read_bytes())
def main():
    assert not OUT.exists()
    prior=load(Path(__file__).parent/'PRELIMINARY_R2_CHECKS.json')
    for e in prior['assets']:
        assert ident((OLD/'dist'/e['name']).read_bytes())=={k:e[k] for k in ('bytes','sha256')}
    with zipfile.ZipFile(NEW/'dist/QPathformer_v0.3_Code.zip') as z:
        prefix='QPathformer_v0.3_Code/'
        inherited=json.loads(z.read(prefix+'INHERITED_LICENSE_MAP.json'))
        scope=json.loads(z.read(prefix+'CODE_LICENSE_SCOPE.json'))
        adopted={e['path']:e for e in scope['files']}
        lineage=inherited['package_helper_lineage']
        assert {e['path'] for e in lineage}=={'tools/startup_check.py','tools/verify_package.py'}
        results=[]
        for e in lineage:
            current=z.read(prefix+e['path']);source=Path(e['source_path']).read_bytes()
            assert ident(current)==e['current']=={k:adopted[e['path']][k] for k in ('bytes','sha256')}
            assert ident(source)==e['source_identity']
            scope_bytes=Path(e['scope_record']).read_bytes();prior_scope=json.loads(scope_bytes)
            assert ident(scope_bytes)==e['scope_record_identity']
            assert prior_scope['status']=='ADOPTED' and prior_scope['license']==e['license']=='Q-Pathformer Platform License 1.0'
            original_entry=next(x for x in prior_scope['files'] if x['path']==e['path'])
            assert ident(source)=={k:original_entry[k] for k in ('bytes','sha256')}
            if e['path'].endswith('verify_package.py'):
                assert current==source and e['relation']=='Byte-identical reuse'
                relation='EXACT_ADOPTED_IDENTITY_MATCH'
            else:
                assert current!=source and e['relation'].startswith('Adaptation')
                blocks=difflib.SequenceMatcher(None,current.decode().splitlines(),source.decode().splitlines(),autojunk=False).get_matching_blocks()
                assert max(b.size for b in blocks)>20
                relation='ADAPTATION_WITH_RETAINED_COMMON_RECEIPT_AND_INTEGRITY_LOGIC'
            results.append(dict(path=e['path'],current=e['current'],adopted_source=e['source_identity'],adopted_scope=e['scope_record_identity'],relation_verified=relation))
        assert scope['inherited_exact_matches']==len(inherited['exact_whole_file_matches'])
        assert scope['shared_expression_records']==len(inherited['shared_expression_evidence'])
        result=dict(status='PASS',checked_at_utc=datetime.now(timezone.utc).isoformat(),study_version='v0.3',code_zip=dict(path=str(NEW/'dist/QPathformer_v0.3_Code.zip'),**ident((NEW/'dist/QPathformer_v0.3_Code.zip').read_bytes())),helper_lineage=results,all_six_predecessor_assets_unchanged_from_preliminary_check=True,preliminary_binding=dict(path=str(Path(__file__).parent/'PRELIMINARY_R2_CHECKS.json'),**ident((Path(__file__).parent/'PRELIMINARY_R2_CHECKS.json').read_bytes())),boundary='Direct file identity, adopted scope membership and shared implementation evidence; this is not an independent ownership or enforceability assessment.')
    with OUT.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(status='PASS',helper_lineage_entries=2,predecessor_assets_preserved=6,receipt=str(OUT))))
if __name__=='__main__':main()
