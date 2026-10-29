"""Independent synthetic producer/oracle comparison before official training."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,sys,traceback,time
import numpy as np
import reference_v05 as ref
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'quantum'))
import models
import circuits

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,msg):
    if not v:raise RuntimeError(msg)
def error(a,b):return float(np.max(abs(np.asarray(a)-np.asarray(b))))
def difference_step(model,x,routed,default):
    # Five-point differences must stay inside one differentiable ReLU region.
    # Each individual W/b perturbation changes a preactivation by <=2h*max(1,|x|).
    if model.activation!='relu':return default,None
    margin=min(float(np.min(abs(x[ids]@model.unpack_mlp(model.parameters[sl])[0]+model.unpack_mlp(model.parameters[sl])[1]))) for ids,_,sl in model.components(x,routed))
    need(margin>0,'Finite differences undefined at an exact ReLU kink')
    return min(default,margin/(8*max(1.,float(abs(x).max())))),margin

def run():
    started=time.perf_counter()
    source={p.relative_to(ROOT).as_posix():sha(p) for p in [Path(__file__),Path(ref.__file__),ROOT/'quantum/models.py',ROOT/'quantum/circuits.py']}
    need(source['quantum/models.py']=='1366920341ee6060cf49adbb0bb3b1845d9e86bfaa7976eddbb6b8d086e402f7','Unexpected model version')
    need(source['quantum/circuits.py']=='2ac3d12903899f8baf9e226e53e0fe5178f9ab700e83a6e929d212cc6e8da90e','Unexpected circuit version')
    need(models.METHODS==ref.METHODS,'Arm inventory differs')
    rng=np.random.Generator(np.random.PCG64(5051901));x=rng.uniform(-.92,.92,(29,2));y=rng.integers(0,2,len(x));route=np.arange(len(x),dtype=np.int64)%5
    rows=[];pmax=zmax=lmax=gmax=0.
    for method in ref.METHODS:
        for variant in ('registered_initial','perturbed_parameters'):
            model=models.Model(method,9731)
            if variant=='perturbed_parameters':model.parameters+=rng.normal(0,.19,len(model.parameters))
            routed=None if method.endswith('_global') else route
            core=model.core_parameters if method=='qfrozen_kmeans' else None
            p,z=model.predict_with_logits(x,routed)
            independent,iz=ref.predict_with_logits(method,model.parameters,x,routed,core)
            scalar,sz=ref.scalar_predict_with_logits(method,model.parameters,x,routed,core)
            pe=max(error(p,independent),error(p,scalar));ze=0 if z is None else max(error(z,iz),error(z,sz))
            need(pe<=2e-12 and ze<=2e-12,'Prediction/logit mismatch: '+method)
            native,gradient,gp,work=model.gradient(x,y,routed)
            d=model.last_gradient_diagnostics
            need(d['minimum_raw_probability']==float(p.min()) and d['maximum_raw_probability']==float(p.max()),'Raw probability extrema differ')
            need(d['minimum_native_logit']==(None if z is None else float(z.min())) and d['maximum_native_logit']==(None if z is None else float(z.max())),'Native logit extrema differ')
            iloss=ref.native_loss(method,model.parameters,x,y,routed,core)
            le=abs(native-iloss);need(le<=1e-10,'Native loss differs')
            step,margin=difference_step(model,x,routed,1e-5)
            fd=ref.central_gradient(method,model.parameters,x,y,routed,core,step=step)
            ge=error(gradient,fd);need(ge<=2e-7,'Native finite-difference gradient mismatch: '+method)
            need(error(p,gp)<=2e-12,'Gradient forward differs')
            need(len(model.parameters)==ref.PARAMETERS[method],'Optimized parameter count differs')
            if model.quantum:
                expected=len(x)*(1 if model.frozen else 17)
                need(work['core_statevector_examples']==expected,'Core evolution count differs')
                need(work['measurement_settings_equivalent']==expected*(2 if method in ('qmulti_kmeans','qfrozen_kmeans') else 1),'Logical setting count differs')
                if model.frozen:
                    need(work['trainable_ry_gates']==0 and work['trainable_rz_gates']==0,'Frozen rotations mislabeled trainable')
                    need(work['fixed_core_ry_gates']==4*len(x) and work['fixed_core_rz_gates']==4*len(x),'Frozen rotation accounting differs')
            elif method.startswith('trig'):need(work['trig_feature_values']==len(x)*25,'Single-pass feature count differs')
            else:need(work['mlp_hidden_evaluations']==len(x)*model.hidden,'Single-pass activation count differs')
            if model.frozen:
                cache=model.cache_features(x,routed);oracle_cache=ref.frozen_features(x,routed,core)
                need(error(cache,oracle_cache)<=2e-12,'Frozen cache differs from independent matrix')
                loss2,g2,p2,w2=model.gradient(x,y,routed,features=cache)
                need(error(gradient,g2)<=2e-12 and error(p,p2)<=2e-12 and abs(native-loss2)<=1e-12,'Frozen cached computation differs')
                need(w2['core_statevector_examples']==0 and w2['measurement_settings_equivalent']==0 and w2['frozen_cached_feature_rows']==len(x),'Cached work charged incorrectly')
            pmax=max(pmax,pe);zmax=max(zmax,ze);lmax=max(lmax,le);gmax=max(gmax,ge)
            rows.append({'method':method,'variant':variant,'parameters':len(model.parameters),'probability_error':pe,'logit_error':ze,'native_loss_error':le,'gradient_max_abs_error':ge,'finite_difference_step':step,'minimum_relu_preactivation_magnitude':margin})
    # Compare moment Jacobians with separate scalar full-matrix finite differences.
    moment_max=jac_max=0.
    for k in range(5):
        core=rng.uniform(-2,2,(2,2,2));points=x[k:k+3]
        measured=circuits.moments(points,core,5)
        independent=np.asarray([ref.scalar_observables(a,core) for a in points])
        moment_max=max(moment_max,error(measured,independent))
        jac=circuits.moment_jacobian(points,core,5)
        for j in range(8):
            plus=core.copy();minus=core.copy();plus.ravel()[j]+=1e-5;minus.ravel()[j]-=1e-5
            fd=(np.asarray([ref.scalar_observables(a,plus) for a in points])-np.asarray([ref.scalar_observables(a,minus) for a in points]))/(2e-5)
            jac_max=max(jac_max,error(jac[:,j,:],fd))
    need(moment_max<=2e-12 and jac_max<2e-9,'Moment/Jacobian reference differs')
    # A wrong confidently positive logit must keep its output-bias derivative.
    saturated=[]
    for method in ref.METHODS[1:]:
        model=models.Model(method,9731);routed=None if model.banks==1 else route
        packed=model.parameters.reshape(model.banks,-1)
        if method.startswith('trig'):packed[:]=0;packed[:,0]=100
        else:packed[:,-1]=100
        native,g,p,_=model.gradient(x,np.zeros(len(x)),routed)
        need(np.all(p>1-1e-7) and native>95,'Saturation fixture missing')
        bias=np.arange(model.banks)*model.bank_width+(0 if method.startswith('trig') else model.bank_width-1)
        need(np.all(g[bias]>0) and abs(g[bias].sum()-1)<1e-12,'Incorrect saturated logit gradient was clipped')
        core=model.core_parameters if model.frozen else None
        step,margin=difference_step(model,x,routed,1e-3)
        fd=ref.central_gradient(method,model.parameters,x,np.zeros(len(x)),routed,core,step=step)
        need(error(g,fd)<2e-7,'Saturated native gradient differs')
        saturated.append({'method':method,'bias_gradient_sum':float(g[bias].sum()),'native_bce':native,'common_clipped_bce':ref.bce(np.zeros(len(x)),p),'finite_difference_error':error(g,fd),'finite_difference_step':step,'minimum_relu_preactivation_magnitude':margin})
    # Legacy hard cap remains deliberate and different from the new native loss.
    legacy=models.Model('q2_kmeans',9731);legacy.parameters[:]=0
    legacy.parameters.reshape(5,8)[:,0]=np.arcsin(2*(1-CLIP/2)-1)
    loss,g,p,_=legacy.gradient(np.zeros((10,2)),np.zeros(10),np.arange(10)%5)
    need(np.all(p>1-CLIP) and np.array_equal(g,np.zeros_like(g)),'Legacy clipping contract changed')
    # Paired initialization and immutable frozen core across actual head-only updates.
    scalar=models.Model('qscalar_kmeans',9731);multi=models.Model('qmulti_kmeans',9731);frozen=models.Model('qfrozen_kmeans',9731)
    need(np.array_equal(scalar.parameters.reshape(5,10)[:,:8],multi.parameters.reshape(5,14)[:,:8]),'Core pairing differs')
    need(np.array_equal(frozen.core_parameters.reshape(5,8),multi.parameters.reshape(5,14)[:,:8]),'Frozen core pairing differs')
    need(np.array_equal(multi.parameters.reshape(5,14)[:,8:],frozen.parameters.reshape(5,6)),'Head pairing differs')
    need(error(scalar.predict(x,route),multi.predict(x,route))<1e-14 and error(multi.predict(x,route),frozen.predict(x,route))<1e-14,'Initial paired predictions differ')
    core_before=frozen.core_parameters.copy();cache=frozen.cache_features(x,route);opt=models.Adam(frozen.parameters.shape)
    for _ in range(40):
        _,g,_,_=frozen.gradient(x,y,route,cache);opt.step(frozen.parameters,g)
    need(np.array_equal(frozen.core_parameters,core_before),'Frozen core changed during head updates')
    for name,h in source.items():need(sha(ROOT/name)==h,'Source changed during audit')
    return {'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':source,'method_variants':rows,
      'maximum_probability_error':pmax,'maximum_logit_error':zmax,'maximum_native_loss_error':lmax,'maximum_native_gradient_error':gmax,
      'maximum_moment_error':moment_max,'maximum_moment_jacobian_error':jac_max,'saturated_logit_fixtures':saturated,
      'legacy_clipping_preserved':True,'paired_initialization_and_frozen_core_40_updates_checked':True,
      'no_official_population_loaded':True,'model_test_outcomes_accessed':False,'elapsed_seconds':time.perf_counter()-started,
      'scope':'Synthetic producer-vs-independent full-matrix/scalar predictions, native objectives, all optimized gradient coordinates, random moment Jacobians, saturated wrong-logit derivatives, frozen caches, initialization and parameter immutability. No official training or data outcomes.'}

CLIP=ref.CLIP
if __name__=='__main__':
    out=Path(__file__).with_name('MODEL_NUMERICAL_AUDIT_ATTEMPT05.json')
    if out.exists():raise FileExistsError(out)
    try:result=run()
    except BaseException:result={'status':'FAIL','traceback':traceback.format_exc(),'model_test_outcomes_accessed':False}
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('method_variants','saturated_logit_fixtures')},indent=2))
    sys.exit(0 if result['status']=='PASS' else 1)
