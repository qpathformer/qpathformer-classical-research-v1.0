"""Bounded independent synthetic producer/oracle comparison; no study data access."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys,time
import numpy as np
import reference_v08 as reference
import sampler_reference as sampler

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;Q=ROOT/'quantum'
sys.path.insert(0,str(Q))
import models
import sampling

def need(value,message):
    if not value:raise RuntimeError(message)
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    start=time.perf_counter();cpu=time.process_time();utc=datetime.now(timezone.utc).isoformat()
    names=('models.py','study.py','circuits.py','reference_v03.py','prepare_data.py','routers.py','sampling.py','tests/test_v08_science.py','tests/test_routers_data.py')
    before={name:digest(Q/name) for name in names}
    need(np.__version__=='2.5.4','Scientific NumPy differs')
    random=np.random.Generator(np.random.PCG64(812733))
    x=random.uniform(-1,1,(23,2));y=np.arange(23)%2
    # Bank four deliberately absent, testing total-batch rather than per-bank averaging.
    route=np.arange(23)%4;losses=np.linspace(0,11,23)
    scores,p=sampling.priority_distribution(losses);rs,rp=sampler.proposal(losses)
    np.testing.assert_array_equal(scores,rs);np.testing.assert_allclose(p,rp,atol=2e-16,rtol=0)
    uniforms=random.random(64);index,weights=sampling.inverse_cdf_draws(p,uniforms)
    ri,rw=sampler.replay_draws(p,uniforms)
    np.testing.assert_array_equal(index,ri);np.testing.assert_array_equal(weights,rw)
    need(abs(weights.sum()-len(weights))>1e-4,'Fixture would not detect forbidden weight normalization')
    for mode in ('U','P'):
        for number in (1,10,11,12,100,200):
            actual=sampling.selected_distribution(23,number,mode,p if number>10 else None)
            expected=sampler.effective_probabilities(mode,number,23,losses if number>10 else None)['probabilities']
            np.testing.assert_allclose(actual,expected,atol=2e-16,rtol=0)
    results=[]
    for method in reference.METHODS:
        model=models.Model(method,0,{'paired_circuit_core_initialization':812744})
        model.parameters[:]+=random.normal(0,.12,len(model.parameters))
        routes=None if method.endswith('global') else route
        br=None if routes is None else routes[index]
        loss,g,pred,_=model.gradient(x[index],y[index],br,sample_weight=weights)
        expected=reference.weighted_gradient(method,model.parameters,x[index],y[index],br,weights)
        np.testing.assert_allclose(g,expected,atol=1e-11,rtol=1e-9)
        np.testing.assert_allclose(loss,reference.weighted_native_loss(method,model.parameters,x[index],y[index],br,weights),atol=2e-12,rtol=0)
        # Full importance correction recovers the original uniform empirical gradient in expectation.
        _,full,_,_=model.gradient(x,y,routes)
        weighted=np.zeros_like(full)
        for i in range(len(x)):
            _,one,_,_=model.gradient(x[i:i+1],y[i:i+1],None if routes is None else routes[i:i+1],sample_weight=np.array([1/(len(x)*p[i])]))
            weighted+=p[i]*one
        np.testing.assert_allclose(weighted,full,atol=2e-12,rtol=2e-12)
        if routes is not None:np.testing.assert_array_equal(g.reshape(5,-1)[4],0)
        results.append({'method':method,'parameters':len(g),'max_gradient_absolute_error':float(np.max(abs(g-expected))),
            'max_importance_expectation_absolute_error':float(np.max(abs(weighted-full))),
            'absent_bank_zero_raw_gradient':routes is not None,'raw_weight_sum':float(weights.sum()),'batch_size':64})
    need(before=={n:digest(Q/n) for n in names},'Producer sources changed during peer check')
    report={'schema':'qpath-v08-scientific-source-peer-review-1','status':'PASS_SOURCE_AND_INDEPENDENT_SYNTHETIC_CHECKS',
        'started_utc':utc,'completed_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':before,
        'reviewer_source_sha256':{p.name:digest(p) for p in (Path(__file__),HERE/'reference_v08.py',HERE/'sampler_reference.py')},
        'matrix_sha256':digest(ROOT/'governance/RUN_MATRIX.json'),'protocol_sha256':digest(ROOT/'governance/STUDY_PLAN.json'),
        'gradient_fixtures':results,'sampler_modes_rounds_checked':{'modes':['U','P'],'rounds':[1,10,11,12,100,200]},
        'review_findings':[
            'Five registered core/routing methods implement weighted native-logit BCE derivatives with raw record weights before the total-batch mean.',
            'Priority scores use training observed labels and current training logits only; first ten rounds are uniform and later U and P both refresh.',
            'One registered PCG64 stream produces all 4800 per-round uniforms paired across ten arms; priorities only change inverse-CDF assignment.',
            'Unnormalized 1/(N*p_i) weights have no clipping, differentiation through sampler, or validation/test/latent input.',
            'Packed Adam retains all-bank momentum with no early stopping; full horizon ends before earliest minimum validation-BCE checkpoint is chosen for evaluation.',
            'All retained sampler, gradient and round-prediction arrays flush before the ledger; no inference benchmark runs inside training.',
            'Trace replay and numerical-gradient spot checks will be a separate registered endpoint audit; this source receipt is not an endpoint acceptance.'],
        'source_limitations':['Finite synthetic cases do not prove correctness for all numerical inputs.',
            'No official data, endpoint or test-model outcomes were read. Full official trace audits remain mandatory.'],
        'official_jobs_executed':False,'model_test_outcomes_accessed':False,
        'wall_seconds':time.perf_counter()-start,'process_cpu_seconds':time.process_time()-cpu}
    path=HERE/'SCIENTIFIC_SOURCE_PEER_REVIEW_v01.json'
    with path.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':report['status'],'path':str(path),'sha256':digest(path),'wall_seconds':report['wall_seconds'],'process_cpu_seconds':report['process_cpu_seconds'],'gradient_errors':[x['max_gradient_absolute_error'] for x in results]}))

if __name__=='__main__':main()
