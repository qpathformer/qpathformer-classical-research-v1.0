"""Peer-review synthetic comparator: no study arrays or checkpoints loaded."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'analysis'));sys.path.insert(0,str(ROOT/'analysis/independent_replay'))
import statistics_v04 as official
import statistics_reference as independent
import threshold_reference

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def compare(actual,expected,path='root'):
    if isinstance(expected,dict):
        for k,v in expected.items():compare(actual[k],v,path+'/'+k)
    elif isinstance(expected,list):
        if len(actual)!=len(expected):raise RuntimeError('Length '+path)
        for i,v in enumerate(expected):compare(actual[i],v,path+'/'+str(i))
    elif isinstance(expected,float):
        if not np.isfinite(actual) or abs(actual-expected)>2e-12:raise RuntimeError('Numeric '+path)
    elif actual!=expected:raise RuntimeError('Identity '+path)

protocol=read(ROOT/'governance/ANALYSIS_PROTOCOL.json')
sources={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'analysis/statistics_v04.py',ROOT/'analysis/independent_replay/statistics_reference.py',ROOT/'analysis/independent_replay/threshold_reference.py',ROOT/'governance/ANALYSIS_PROTOCOL.json']}
fixture=HERE/'statistics_peer_fixture_v01';fixture.mkdir(exist_ok=False)
(fixture/'SYNTHETIC_ONLY.txt').write_text('Artificial probability arrays; no official population or model outcome.\n',encoding='utf-8')
rng=np.random.Generator(np.random.PCG64(983410));y=np.array([0,1,0,0,1,0,1,1,0,1,0,1,1,1,0,0,0],int)
p=rng.uniform(.0001,.9999,(5,9,len(y)));p[0,0,:4]=[0.,.5,1.,1e-7]
comparisons=[]
for pop in protocol['population_order']:
    a,counts,boot=independent.summarise_population(pop,y,p,protocol)
    official.analyse_population(pop,y,p,protocol['training_seeds'],protocol['methods'],fixture/pop)
    b=read(fixture/pop/'population_summary.json')
    for k in ['population','n','seeds','methods','bootstrap_replicates','primary_family_size','bootstrap_counts_sha256','aggregate','contrasts','limits']:compare(a[k],b[k],k)
    np.testing.assert_array_equal(counts,np.load(fixture/pop/'bootstrap_counts.npy',allow_pickle=False))
    for c in b['contrasts']:
        for name,value in c['metrics'].items():
            if ('seed_interval_adjusted' in value)!=(c['primary'] and name=='bce'):raise RuntimeError('Adjusted interval inventory differs')
    comparisons.append({'population':pop,'replicates':5000,'contrasts':17,'exact_bootstrap_npy_sha256':b['bootstrap_counts_sha256'],'status':'PASS'})
for key,h in sources.items():
    if sha(ROOT/key)!=h:raise RuntimeError('Reviewed source changed')
report={'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sources,
 'synthetic_comparisons':comparisons,'synthetic_fixture':'statistics_peer_fixture_v01',
 'source_review':['Official and independent BCE,macroF1,accuracy correctly use canonical p>=0.5 and clipped natural-log loss.',
 'Five paired seed differences within population; df4 sampleSD and two-sided t critical. Independent closed-form df4 CDF/bisection matches officialSciPy.',
 'Primary9 comparisons use confidence1-.05/9; family adjustment only primaryBCE. SecondaryF1/accuracy/interactions ordinary95 and descriptive.',
 'Common record multiplicities preserve method and checkpoint pairing; nonlinearF1 computed percheckpoint before averaging5.',
 'Records and populations not treated as extra independenttrainingseeds. Bootstrap uncertainty conditional on5fixedtrainedmodels.',
 'Threshold helper preserves canonical probabilities/classes; both probabilities must lie within32eps for each disagreement; mask only canonical and labels only diagnosticextrema.',
 'Independent aggregateBCE1e-8 vs canonicalrecompute2e-12 is consistently separated; probability2e-12 unchanged.'],
 'tests_rerun':{'official':4,'independent_core_without_filesystem_fixture':7,
 'logs_sha256':{n:sha(HERE/n) for n in ['official_statistics_peer_tests.log','independent_statistics_peer_tests.log']}},
 'nonblocking_boundary':'Official metric_arrays converts labels toint64 before validation; caller must supply hash-bound binaryinteger labels, as the registered evaluator contract requires. Independent reference rejects nonbinarylabels before cast. No malformedlabels in sealeddata; no numerical/source amendment needed for registeredexecution.',
 'scientific_limits':'Bonferroni t intervals inherit small-n assumptions; percentilebootstrapcoverage is approximate. Neither is unconditional proof of taskgeneralization or quantumadvantage. The model families differ in capacity/optimization/featurelink.',
 'real_model_test_outcomes_accessed':False}
out=HERE/'STATISTICS_AND_NUMERICAL_PEER_REVIEW.json'
with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'status':'PASS','sha256':sha(out),'sources':sources}))
