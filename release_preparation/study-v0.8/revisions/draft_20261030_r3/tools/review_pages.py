from pathlib import Path
import json,subprocess,zipfile,xml.etree.ElementTree as ET
from pypdf import PdfReader
H=Path(__file__).resolve().parent
S=Path(r'C:\Q2\Release_Preparation\QPathformer_Classical_Research\study-v0.8\draft_20261029_r2\assembly\QPathformer_v0.8_Study')
pdf=S/'reports/QPathformer_v0.8_Report_Edition_1.pdf'
r=PdfReader(pdf)
if len(r.pages)!=45:raise RuntimeError('Page count differs')
exe=r'C:\Users\Alnotrea\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe'
for page in (37,38):
    t=r.pages[page-1].extract_text();(H/f'page{page}.txt').write_text(t,encoding='utf-8')
    subprocess.run([exe,'-f',str(page),'-l',str(page),'-singlefile','-scale-to','1800','-png',str(pdf),str(H/f'page{page}')],check=True,capture_output=True)
    print(f'PAGE {page}\n'+t[:650])
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
tables=[]
for doc in (Path(r'C:\Q2\Improvement_Study_v0.8\docs\QPATH_RPT009_v0.8_Internal_Study_Report.docx'),S/'reports/QPathformer_v0.8_Report_Edition_1.docx'):
    with zipfile.ZipFile(doc) as z:table=ET.fromstring(z.read('word/document.xml')).findall('w:body/w:tbl',ns)[49]
    rows=[[''.join(c.itertext()) for c in row.findall('w:tc',ns)] for row in table.findall('w:tr',ns)]
    tables.append(rows)
if tables[0]!=tables[1] or len(tables[0])!=11:raise RuntimeError('Spiral table differs')
(H/'SPIRAL_TABLE_CHECK.json').write_text(json.dumps(dict(status='PASS',table_number=50,header_rows=1,arm_rows=10,original_matches_edition=True,rows=tables[0]),indent=2),encoding='utf-8')
print(json.dumps(dict(table50_first_column=[row[0] for row in tables[0]])))
