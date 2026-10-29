"""Independent synthetic cross-check of the official recovery helper only."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
import numpy as np
import audit_endpoints_v03 as independent
sys.path.insert(0,str(independent.Q))
import numerical_verification as official

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
names={"official_helper":Path(official.__file__),"independent_auditor":Path(independent.__file__),"this_crosscheck":Path(__file__)}
before={k:sha(p) for k,p in names.items()}
official.verify_protocol()
rng=np.random.default_rng(770031);mapping={'all_zero':'all_ambiguous_to0','all_one':'all_ambiguous_to1','all_incorrect':'label_assisted_all_incorrect','all_correct':'label_assisted_all_correct'}
for attempt in range(300):
    n=int(rng.integers(5,40));y=rng.integers(0,2,n)
    p=rng.uniform(.02,.98,n);r=p.copy();m=n//2
    p[:m]=.5+rng.integers(-32,33,m)*np.finfo(float).eps
    r[:m]=.5+rng.integers(-32,33,m)*np.finfo(float).eps
    pop={'y':y,'ids':np.arange(n)+800,'depth':np.arange(n)%4+1,'hash_route':np.arange(n)%5,'kmeans_route':np.arange(n)[::-1]%5}
    a=independent.numerical_review(p,r,pop);b=official.verify_pair(pop,p,r)
    for left,right in [(a['canonical_metrics'],b['canonical_metrics']),(a['reference_metrics'],b['raw_reference_metrics'])]:
        assert {k:v for k,v in left.items() if k!='bce'}=={k:v for k,v in right.items() if k!='bce'}
        assert abs(left['bce']-right['bce'])<=1e-14  # Independent log1p versus log(1-p) arithmetic.
    assert a['disagreements']==b['counts']['class_disagreements'] and a['canonical_near_band_count']==b['counts']['canonical_near_band']
    assert a['reference_near_band_count']==b['counts']['reference_near_band'] and a['union_near_band_count']==b['counts']['union_near_band']
    assert a['exact_class_agreement']==b['counts']['exact_class_agreement']
    for left,right in mapping.items():
        assert a['canonical_band_sensitivity'][left]=={k:v for k,v in b['sensitivity'][right].items() if k!='n'}
    for x,z in zip(a['disagreement_rows'],b['disagreements']):
        for key in ('record_id','original_depth','label','canonical_probability','reference_probability','hash_route','kmeans_route'):assert x[key]==z[key]
        assert x['canonical_prediction']==z['canonical_class'] and x['reference_prediction']==z['reference_class']
    for depth in range(1,5):
        assert a['slices']['depth'][str(depth)]['disagreements']==b['by_original_depth'][str(depth)]['class_disagreements']

rejections=0
for p,r in [(np.array([.5,.8]),np.array([np.nextafter(.5-independent.BAND,-np.inf),.8])),
            (np.array([np.nextafter(.5+independent.BAND,np.inf),.8]),np.array([.5-np.finfo(float).eps,.8])),
            (np.array([.2,.8]),np.array([.2+3e-12,.8])),(np.array([.2,.8]),np.array([np.nan,.8]))]:
    pop={'y':np.array([0,1]),'ids':np.array([90,91]),'depth':np.array([1,2]),'hash_route':np.array([0,1]),'kmeans_route':np.array([2,3])}
    try:official.verify_pair(pop,p,r)
    except RuntimeError:rejections+=1
    else:raise AssertionError('Official helper accepted invalid numerical case')
assert before=={k:sha(p) for k,p in names.items()}
value={'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':before,
       'numerical_recovery_protocol_sha256':official.PROTOCOL_SHA,'synthetic_random_cases':300,'invalid_cases_rejected':rejections,
       'checks':'Independent implementations match canonical/reference metrics, band counts, disagreement identities, depth slices and all four canonical-mask sensitivities.',
       'scope':'Synthetic engineering verification only. No model execution, data/test loading, official audit or release.',
       'preserved_attempt':'First crosscheck asserted bit-exact independently computed BCE and failed from log1p versus log(1-p) arithmetic. Preserved attempt01 source/log; exact classification remains required, synthetic cross-implementation BCE tolerance1e-14.'}
output=HERE/'NUMERICAL_HELPER_INDEPENDENT_CROSSCHECK_01.json'
with output.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
print(json.dumps(value,indent=2));print(sha(output))
