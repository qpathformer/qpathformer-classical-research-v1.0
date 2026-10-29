"""Synthetic-only independent-versus-official arithmetic comparison."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys,tempfile
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'analysis'));sys.path.insert(0,str(ROOT/'analysis/independent_replay'))
import statistics_v06 as official
import statistics_reference as independent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,m):
    if not x:raise RuntimeError(m)
maximum=0.;leaves=0
def compare(a,b):
    global maximum,leaves
    if isinstance(a,dict):
        need(set(a)==set(b),'Dictionary fields differ')
        for key in a:compare(a[key],b[key])
    elif isinstance(a,(list,tuple)):
        need(len(a)==len(b),'Sequence lengths differ')
        for x,y in zip(a,b):compare(x,y)
    elif isinstance(a,(float,int,np.floating,np.integer)) and not isinstance(a,bool):
        error=abs(a-b);maximum=max(maximum,error);leaves+=1;need(error<=2e-10,'Arithmetic disagreement '+str(error))
    else:need(a==b,'Nonnumeric value differs')

protocol=json.loads((ROOT/'governance/ANALYSIS_PROTOCOL.json').read_text(encoding='utf-8-sig'))
rng=np.random.Generator(np.random.PCG64(606027));y=np.array([1,0,0,1,0,0,0,1,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0,0])
p=rng.uniform(0,1,(5,6,len(y)));p[:,:,0]=0.;p[:,:,1]=1.;p[:,:,2:5]=.5
counts=[]
with tempfile.TemporaryDirectory(prefix='statistics_synthetic_',dir=HERE) as tmp:
    for name in independent.POPULATIONS:
        actual=official.analyse_population(name,y,p,list(independent.SEEDS),list(independent.METHODS),Path(tmp)/name)
        expected,c,b=independent.summarise_population(name,y,p,protocol)
        compare(actual['aggregate'],expected['aggregate']);compare(actual['contrasts'],expected['contrasts'])
        need(actual['bootstrap_counts_sha256']==expected['bootstrap_counts_sha256'],'Exact multinomial identity differs')
        counts.append(actual['bootstrap_counts_sha256'])
for yy,pp in [([0,0],[.1,.9]),([1,1],[.1,.9]),([0,1],[.5,.5]),([1,0,1,0,1],[.9,.9,.6,.6,.1])]:
    compare(official.class_quality(yy,pp),independent.class_quality(yy,pp))
    compare(official.calibration(yy,pp),independent.calibration(yy,pp))
names=['analysis/statistics_v06.py','analysis/independent_replay/statistics_reference.py',
       'analysis/independent_replay/threshold_reference.py','analysis/independent_replay/prediction_reference.py',
       'analysis/independent_replay/test_replay_cores.py','analysis/independent_replay/test_prediction_reference.py',
       'governance/ANALYSIS_PROTOCOL.json','analysis/classical_review/crosscheck_statistics_v06.py']
result={'status':'PASS_SYNTHETIC_ONLY','study_id':protocol['study_id'],'created_utc':datetime.now(timezone.utc).isoformat(),
        'source_sha256':{n:sha(ROOT/n) for n in names},'numeric_leaf_comparisons':leaves,'maximum_absolute_difference':maximum,
        'bootstrap_count_hashes':counts,'populations':4,'replicates_per_population':10000,'primary_family':16,
        'scope':'Cross-implementation metrics/calibration/positive-class diagnostics/tie-aware AP, five-seed t intervals and all10 contrasts/population, both conditional bootstrap confidence levels. Same synthetic imbalanced probabilities with ties/boundaries; no actual data or model outcomes.'}
out=HERE/'STATISTICS_CROSSCHECK_01.json'
with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(json.dumps(result,indent=2))
