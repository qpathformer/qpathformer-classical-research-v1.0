"""Synthetic-only cross-implementation test; no official model/data outcomes."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,hashlib,traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'analysis'));sys.path.insert(0,str(ROOT/'analysis/independent_replay'))
import statistics_v05 as official
import statistics_reference as independent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise RuntimeError(m)
def run():
 source_paths=[Path(__file__),ROOT/'analysis/statistics_v05.py',ROOT/'analysis/independent_replay/statistics_reference.py',ROOT/'governance/ANALYSIS_PROTOCOL.json']
 sources={p.relative_to(ROOT).as_posix():sha(p) for p in source_paths}
 protocol=json.loads((ROOT/'governance/ANALYSIS_PROTOCOL.json').read_text());rng=np.random.Generator(np.random.PCG64(5059901));n=37
 y=rng.integers(0,2,n);p=rng.uniform(0,1,(5,11,n));p[:,:,0]=0;p[:,:,1]=1;p[:,:,2]=.5
 p[0,0,3:14]=np.linspace(0,1,11);p[1,2,3:7]=[1e-7,1-1e-7,.5-np.finfo(float).eps,.5+np.finfo(float).eps]
 output=HERE/'statistics_synthetic_crosscheck';output.mkdir(exist_ok=False)
 checks=0;maximum=0.;location=None
 def compare(left,right,path='root'):
  nonlocal checks,maximum,location
  if isinstance(left,dict):
   need(set(left)==set(right),'Keys differ at '+path)
   for k in left:compare(left[k],right[k],path+'.'+k)
  elif isinstance(left,(list,tuple)):
   need(len(left)==len(right),'Length differs at '+path)
   for i,(a,b) in enumerate(zip(left,right)):compare(a,b,path+f'[{i}]')
  elif isinstance(left,float):
   checks+=1;error=abs(left-right)
   if error>maximum:maximum=error;location=path
   need(np.isfinite([left,right]).all() and error<=2e-9,'Numeric difference at '+path)
  else:need(left==right,'Value differs at '+path)
 rows=[]
 for pop in protocol['population_order']:
  actual=official.analyse_population(pop,y,p,list(independent.SEEDS),list(independent.METHODS),output/pop)
  other,counts,boot=independent.summarise_population(pop,y,p,protocol)
  saved=np.load(output/pop/'bootstrap_counts.npy',allow_pickle=False);need(np.array_equal(saved,counts),'Bootstrap identity differs')
  for key in ('aggregate','contrasts','bootstrap_counts_sha256','bootstrap_replicates','primary_family_size','limits','n','seeds','methods'):compare(actual[key],other[key],pop+'.'+key)
  rows.append({'population':pop,'bootstrap_replicates':len(counts),'bootstrap_counts_sha256':actual['bootstrap_counts_sha256'],'contrasts':len(actual['contrasts']),'checkpoint_metrics':5*11*4,'calibration_bins':5*11*10})
 for path,h in sources.items():need(sha(ROOT/path)==h,'Source changed during crosscheck')
 return {'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'scope':'Random and deliberate boundary synthetic probabilities only; no model checkpoint or registered population/test records loaded.',
  'source_sha256':sources,'numeric_comparisons':checks,'maximum_absolute_difference':maximum,'maximum_difference_location':location,
  'populations':rows,'model_test_outcomes_accessed':False}
if __name__=='__main__':
 out=HERE/'STATISTICS_CROSS_IMPLEMENTATION_REVIEW.json'
 if out.exists():raise FileExistsError(out)
 try:r=run()
 except BaseException:r={'status':'FAIL','traceback':traceback.format_exc(),'model_test_outcomes_accessed':False}
 with out.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps(r,indent=2));sys.exit(0 if r['status']=='PASS' else 1)
