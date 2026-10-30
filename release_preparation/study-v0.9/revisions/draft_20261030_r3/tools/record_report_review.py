from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,zipfile
from pypdf import PdfReader
H=Path(__file__).resolve().parent
OLD=Path(r'C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.9\draft_20261029_r2')
ROOT=OLD/'assembly/QPathformer_v0.9_Study'
NOTES=Path(r'C:\Anthony Siljeg\CPU-QPU git repo prep\v6 final staging\study-v0.9_release_review_and_codex_notes.md')
def info(p):
    b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
pdf=ROOT/'reports/QPathformer_v0.9_Report_Edition_1.pdf';docx=ROOT/'reports/QPathformer_v0.9_Report_Edition_1.docx'
original=Path(r'C:\Q2\Improvement_Study_v0.9\docs\QPATH_RPT010_v0.9_Internal_Study_Report.docx')
expected=[(original,1113738,'6f35101e9d3fda4581c2ef7102d0b330c89cd3bacc1771cf0c0e21b5db556ad8'),(docx,1114685,'6dd007d63937e67518b1fe312cdeb5b28596d06689f03c992be087a18d862244'),(pdf,2177249,'13098d61dd1737f5f8646a3e56f8f85789aaabf909b954c0fc75db9ca2cd38ec')]
for p,size,h in expected:
    if info(p)!=dict(bytes=size,sha256=h):raise RuntimeError('Reviewed report identity differs')
reader=PdfReader(pdf)
if len(reader.pages)!=40:raise RuntimeError('PDF page count differs')
page=reader.pages[36].extract_text().lower()
if not all(word in page for word in ('account','credit','token')):raise RuntimeError('Expected page-37 disclosure context differs')
with zipfile.ZipFile(original) as z:
    if len(z.namelist())!=25:raise RuntimeError('Original DOCX part count differs')
r=dict(status='PASS_V09_REPORT_PRESERVATION',checked_at_utc=datetime.now(timezone.utc).isoformat(),study_version='v0.9',report_pdf=info(pdf),report_docx=info(docx),original_report=dict(path=str(original),**info(original)),supplied_review=dict(path=str(NOTES),**info(NOTES)),historical_visual_receipt=dict(path=str(ROOT/'provenance/VISUAL_REVIEW.json'),**info(ROOT/'provenance/VISUAL_REVIEW.json')),report_pages=40,disclosure_context='The historical page-37 account/credit/token disclosure applies to v0.9. PDF text confirms the context; operational usage is retained with its historical cutoff and qualifications. It is not a current-price claim or a billed study-specific price.',cross_study_correction_applied=False,redactions_applied=False,report_reexported=False,alternate_render=dict(source='Owner-supplied review notes',reported_result='LibreOfficeDev 26.8.0.0.alpha0 produced 40 pages with corresponding whitespace-normalized text; no v0.8-style missing-row finding.',new_alternate_export_performed=False,universal_rendering_equivalence_claimed=False),new_review_scope='Exact reviewed PDF/DOCX identity, page count and bounded text-context confirmation. Separate package audit verifies original XML-prefix, tables and embedded images. No new page-render/all-page visual review, operational account analysis or scientific run.',historical_receipt_and_report_files_unchanged=True,study_wrapper_change='Current introduction names comparison controls and qualifies Banknote inputs and accepted replay prerequisites. Final package bindings added after sealing.',previous_study_zip=info(OLD/'dist/QPathformer_v0.9_Study.zip'),previous_study_seal=info(OLD/'dist/QPathformer_v0.9_Study.seal.json'))
with (H/'REPORT_REVIEW_BOUNDARIES.json').open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
print('Verified unchanged report identities and applicable v0.9 disclosure; no correction or re-export')
