"""Compare production subjects with independent references on engineering inputs."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,sys,time
import numpy as np
import reference_v04 as ref
ROOT=Path(__file__).resolve().parents[2];Q=ROOT/'quantum';HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(Q))
import models as subject

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def expected_initial(method,seed):
    family,routing=method.split('_');banks=1 if routing=='global' else 5
    if family=='q2':
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,1])))
        master=rng.uniform(-.1,.1,(5,4,2,2));return master[:banks,:2].reshape(-1)
    if family=='trig':return np.zeros(banks*25)
    h=32 if routing=='global' else 2;rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,4,h])))
    out=[]
    for _ in range(banks):out.extend(np.r_[rng.uniform(-np.sqrt(6/(2+h)),np.sqrt(6/(2+h)),2*h),np.zeros(h),rng.uniform(-np.sqrt(6/(h+1)),np.sqrt(6/(h+1)),h),0.])
    return np.array(out)

def run():
    source_paths={'models':Q/'models.py','circuits':Q/'circuits.py','independent_reference':HERE/'reference_v04.py','this_audit':Path(__file__)}
    before={k:sha(p) for k,p in source_paths.items()};rng=np.random.default_rng(790031)
    x=rng.uniform(-.9,.9,(17,2));y=rng.integers(0,2,len(x));routes=[np.arange(len(x))%5,np.where(np.arange(len(x))%3==0,4,0)]
    cases=[];feature_work=[]
    for method in ref.METHODS:
        model=subject.Model(method,17009);np.testing.assert_array_equal(model.parameters,expected_initial(method,17009))
        for case in range(2):
            if case:model.parameters[:]=rng.normal(0,.55,len(model.parameters))
            route=None if method.endswith('_global') else routes[case]
            loss,g,p,work=model.gradient(x,y,route)
            independent=ref.predict(method,model.parameters,x,route)
            scalar=ref.scalar_predict(method,model.parameters,x,route)
            error=float(max(abs(p-independent).max(),abs(p-scalar).max()));assert error<=2e-12
            bce_error=abs(loss-ref.bce(y,independent));assert bce_error<=1e-8
            numerical=ref.central_gradient(method,model.parameters,x,y,route)
            gradient_error=float(abs(numerical-g).max())
            np.testing.assert_allclose(g,numerical,atol=5e-7,rtol=2e-5)
            if route is not None:
                for absent in sorted(set(range(5))-set(route)):
                    assert np.count_nonzero(g.reshape(5,-1)[absent])==0
            n=len(x);q=method.startswith('q2_')
            assert work['model_record_visits']==work['bank_record_visits']==n
            assert work['circuit_examples']==(17*n if q else 0)
            assert work['layer_applications']==work['cx_gates']==(34*n if q else 0)
            assert work['classical_forward_examples']==work['classical_backward_examples']==(0 if q else n)
            assert work['trig_feature_values']==(50*n if method.startswith('trig_') else 0)
            assert work['mlp_hidden_evaluations']==(2*n*(32 if method.endswith('_global') else 2) if method.startswith('mlp_') else 0)
            cases.append({'method':method,'parameter_case':case,'maximum_probability_error':error,'bce_error':bce_error,'maximum_gradient_absolute_error':gradient_error})
        if method.startswith('trig_'):
            called=[];original=subject.trig_features
            def trace(features):called.append(len(features));return original(features)
            subject.trig_features=trace
            try:_,_,_,work=model.gradient(x,y,route)
            finally:subject.trig_features=original
            assert 25*sum(called)==work['trig_feature_values']
            feature_work.append({'method':method,'actual_basis_values':25*sum(called),'declared':work['trig_feature_values']})
    clipped=[]
    for family in ('mlp','trig','q2'):
        model=subject.Model(family+'_global',17011);xx=np.zeros((11,2));yy=np.arange(11)%2
        for sign in (-1,1):
            model.parameters[:]=0
            if family=='q2':model.parameters[-4:]=[sign*np.pi/2,0,np.pi/2,0]
            elif family=='mlp':model.parameters[-1]=40*sign
            else:model.parameters[0]=40*sign
            loss,g,p,work=model.gradient(xx,yy)
            assert np.all((p<ref.CLIP)|(p>1-ref.CLIP)) and np.count_nonzero(g)==0
            independent=ref.predict(model.method,model.parameters,xx)
            err=abs(loss-ref.bce(yy,independent));assert err<=1e-8
            numeric=ref.central_gradient(model.method,model.parameters,xx,yy)
            assert np.max(abs(numeric))<1e-8
            clipped.append({'family':family,'sign':sign,'probability_min':float(p.min()),'probability_max':float(p.max()),'gradient_all_zero':True,'bce_error':err})
    # Direct close-to-clip perturbations make the loss-sensitivity distinction explicit.
    yy=np.array([0,1,0,1]);base=np.array([1e-7,1e-7,1-1e-7,1-1e-7]);delta=8*np.finfo(float).eps
    perturb=base+np.array([delta,-delta,-delta,delta])
    clipping_fixture={'maximum_probability_delta':float(abs(base-perturb).max()),'aggregate_BCE_delta':abs(ref.bce(yy,base)-ref.bce(yy,perturb)),
       'scope':'Engineering illustration of loss sensitivity near a fixed clip; not an allowed classifier ambiguity or a formal error bound.'}
    assert clipping_fixture['maximum_probability_delta']<=2e-12 and clipping_fixture['aggregate_BCE_delta']<=1e-8
    # Profile a full200-round validation replay without official data/model states.
    xx=rng.uniform(-1,1,(1600,2));params=rng.uniform(-1,1,(200,40));route=np.arange(1600)%5
    started=time.perf_counter();values=ref.predict_many('q2_kmeans',params,xx,route);elapsed=time.perf_counter()-started
    assert values.shape==(200,1600)
    assert before=={k:sha(p) for k,p in source_paths.items()},'Source changed during review'
    return {'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':before,'cases':cases,'saturated_clipped_cases':clipped,
            'actual_trig_work_checks':feature_work,'clipping_sensitivity_fixture':clipping_fixture,
            'full200round1600record_reference_seconds':elapsed,'numerical_protocol':'Probability2e-12; cross-oracle aggregate clipped BCE1e-8; canonical saved-probability recomputation2e-12; gradient engineering5e-7atol+2e-5rtol, no threshold relaxation.',
            'scope':'Synthetic engineering only, no official populations/test outcomes. Independent references import no trainer/circuit source. Source under test is imported only by this audit harness.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    result=run()
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','saturated_clipped_cases')},indent=2));print(sha(args.output))
