"""Independent deployment coefficient, geometry, parity and timing arithmetic.

Pure functions only. No producer imports, fitting, file reads or test release.
"""
import math
import numpy as np
import laurent_reference_v06 as laurent

METHODS=('qscalar_kmeans','qmulti_kmeans','mlp8tanh_kmeans','trig_kmeans','trig_global','mlp_global')
POPULATIONS=tuple('confirmation_'+x for x in ('checkerboard','spiral','annulus','disks'))
SEEDS=(1201,1202,1203,1204,1205)
COEFFICIENT_ATOL=1e-10;COEFFICIENT_RTOL=1e-12;ZTOL=1e-9;PTOL=2e-12;BAND=2e-12
def need(condition,message):
    if not condition:raise ValueError(message)

def route(x,centers):
    x=np.asarray(x,float);centers=np.asarray(centers,float)
    need(x.ndim==2 and x.shape[1]==2 and centers.shape==(5,2) and np.isfinite(x).all() and np.isfinite(centers).all(),'Route inputs invalid')
    return ((x[:,0,None]-centers[None,:,0])**2+(x[:,1,None]-centers[None,:,1])**2).argmin(axis=1).astype(np.int64)

def coefficients(method,parameters,actual):
    expected,detail=laurent.compile_model(method,parameters,return_diagnostics=True)
    actual=np.asarray(actual,float);need(actual.shape==(5,25) and np.isfinite(actual).all(),'Compiled coefficient schema differs')
    delta=abs(actual-expected);bound=COEFFICIENT_ATOL+COEFFICIENT_RTOL*abs(expected)
    need(np.all(delta<=bound),'Coefficient tolerance exceeded')
    l1=delta.sum(axis=1)
    return expected,{'maximum_coefficient_absolute_error':float(delta.max()),
        'maximum_coefficient_tolerance_fraction':float(np.max(delta/bound)),
        'per_bank_coefficient_l1_discrepancy':l1.tolist(),
        'per_bank_polynomial_logit_difference_bound':l1.tolist(),
        'per_bank_sigmoid_difference_bound':(l1/4).tolist(),
        'laurent_diagnostics':detail,
        'scope':'L1 bounds the real polynomial difference for every real input; one quarter bounds the sigmoid difference. Floating-point feature and summation evaluation error is excluded. Per-bank coefficient matching does not make the model globally smooth across fixed router boundaries.'}

def parity(canonical_p,canonical_z,converted_p,converted_z,ids):
    p,z,q,w=map(np.asarray,(canonical_p,canonical_z,converted_p,converted_z));ids=np.asarray(ids)
    need(p.ndim==1 and len(p)>0 and p.shape==q.shape==z.shape==w.shape==ids.shape,'Parity vector shapes differ')
    need(all(np.isfinite(a).all() for a in (p,z,q,w)) and np.all((p>=0)&(p<=1)) and np.all((q>=0)&(q<=1)),'Nonphysical/nonfinite parity values')
    pe=float(np.max(abs(p-q)));ze=float(np.max(abs(z-w)))
    need(pe<=PTOL and ze<=ZTOL,'Compiled predictor parity tolerance exceeded')
    near_p=abs(p-.5)<=BAND;near_q=abs(q-.5)<=BAND;different=(p>=.5)!=(q>=.5)
    need(np.all(~different|(near_p&near_q)),'Compiled class disagreement outside both-probability band')
    return {'maximum_probability_error':pe,'maximum_logit_error':ze,'records':len(p),
        'class_disagreements':int(different.sum()),'canonical_near_band':int(near_p.sum()),'compiled_near_band':int(near_q.sum()),
        'disagreements':[{'record_id':int(ids[i]),'canonical_probability':float(p[i]),'compiled_probability':float(q[i])} for i in np.flatnonzero(different)]}

def verify_boundary_fixtures(centers,points,records):
    centers=np.asarray(centers,float);points=np.asarray(points,float)
    need(points.shape==(len(records),2) and len(records)%3==0 and np.isfinite(points).all(),'Boundary fixture shape differs')
    expected_pairs=[]
    for i in range(5):
        for j in range(i+1,5):
            n=2*(centers[j]-centers[i]);b=float(centers[j]@centers[j]-centers[i]@centers[i]);candidates=[]
            constraints=[(np.array([1.,0]),1.),(np.array([-1.,0]),1.),(np.array([0.,1]),1.),(np.array([0.,-1.]),1.)]
            constraints.extend((2*(centers[k]-centers[i]),float(centers[k]@centers[k]-centers[i]@centers[i])) for k in range(5) if k not in (i,j))
            for a,limit in constraints:
                matrix=np.stack([n,a])
                if abs(np.linalg.det(matrix))<1e-14:continue
                point=np.linalg.solve(matrix,np.array([b,limit]))
                if all(float(v@point)<=upper+2e-12 for v,upper in constraints):candidates.append(point)
            if len(candidates)>=2 and max(float(np.linalg.norm(a-b)) for k,a in enumerate(candidates) for b in candidates[k+1:])>1e-12:expected_pairs.append((i,j))
    identities=[];maximum_tie_error=0.
    for start in range(0,len(records),3):
        rr=records[start:start+3];xy=points[start:start+3];pair=rr[0]['centroid_pair'];i,j=pair
        need(0<=i<j<5 and all(a['centroid_pair']==pair for a in rr),'Boundary pair invalid')
        need([a['side'] for a in rr]==[-1,0,1] and [a['normal_offset'] for a in rr]==[-1e-10,0.,1e-10],'Boundary offsets differ')
        delta=centers[j]-centers[i];normal=delta/np.linalg.norm(delta);middle=xy[1]
        need(np.max(abs(xy-(middle+np.array([-1e-10,0,1e-10])[:,None]*normal)))<2e-15,'Boundary displacement differs')
        squared=np.sum((centers-middle)**2,axis=1);err=abs(squared[i]-squared[j]);maximum_tie_error=max(maximum_tie_error,float(err))
        need(err<=2e-12 and squared[i]<=squared.min()+2e-12 and np.all(abs(middle)<=1+2e-12),'Not an actual clipped nearest-centroid edge')
        # Independent endpoint enumeration: intersect the bisector with each
        # box edge and every third-centroid bisector, then retain feasible ones.
        n=2*(centers[j]-centers[i]);b=float(centers[j]@centers[j]-centers[i]@centers[i]);candidates=[]
        constraints=[(np.array([1.,0]),1.),(np.array([-1.,0]),1.),(np.array([0.,1]),1.),(np.array([0.,-1.]),1.)]
        constraints.extend((2*(centers[k]-centers[i]),float(centers[k]@centers[k]-centers[i]@centers[i])) for k in range(5) if k not in pair)
        for a,limit in constraints:
            matrix=np.stack([n,a])
            if abs(np.linalg.det(matrix))<1e-14:continue
            candidate=np.linalg.solve(matrix,np.array([b,limit]))
            if all(float(v@candidate)<=upper+2e-12 for v,upper in constraints):candidates.append(candidate)
        need(len(candidates)>=2,'No two finite edge endpoints')
        farthest=max(((float(np.linalg.norm(a-b)),a,b) for k,a in enumerate(candidates) for b in candidates[k+1:]),key=lambda v:v[0])
        need(farthest[0]>1e-12 and np.max(abs((farthest[1]+farthest[2])/2-middle))<=2e-12,'Not midpoint of full feasible Voronoi edge')
        identities.append(tuple(pair))
    need(identities==expected_pairs,'Missing, duplicate or unordered feasible Voronoi edges')
    return {'edge_count':len(identities),'point_count':len(points),'maximum_equidistance_error':maximum_tie_error,'centroid_pairs':[list(p) for p in identities]}

def trial_order(population_index,seed_index,trial):
    shift=(population_index*5+seed_index+trial+2)%len(METHODS)
    order=METHODS[shift:]+METHODS[:shift]
    return order[::-1] if trial%2 else order

def timing_summary(rows):
    need(len(rows)==17 and [r['trial'] for r in rows]==list(range(-2,15)),'Complete two warmup/fifteen timing trials required')
    initial=rows[0];size=initial['batch_size'];need(size in (1,32,1024),'Unregistered timing batch size')
    calls,n={1:(128,128),32:(32,1024),1024:(32,32768)}[size]
    keys=('key','population','seed','method','representation','batch_size')
    for row in rows:
        need(all(row[k]==initial[k] for k in keys),'Timing condition identities differ')
        need(row['warmup']==(row['trial']<0) and row['calls']==calls and row['prediction_records']==n,'Timing input work differs')
        need(type(row['elapsed_ns']) is int and row['elapsed_ns']>=0 and np.isfinite(row['ns_per_record']),'Invalid timing clock')
        need(row['ns_per_record']==row['elapsed_ns']/n,'Timing per-record arithmetic differs')
        need(row['probability_sha256']==initial['probability_sha256'] and row['logit_sha256']==initial['logit_sha256'],'Timing outputs changed between repeats')
    values=sorted(row['ns_per_record'] for row in rows if not row['warmup'])
    # Fifteen values => median index7, linear quartiles between indices3/4,10/11.
    return {k:initial[k] for k in keys}|{'timed_repeats':15,'median_ns_per_record':values[7],
        'q25_ns_per_record':(values[3]+values[4])/2,'q75_ns_per_record':(values[10]+values[11])/2}
