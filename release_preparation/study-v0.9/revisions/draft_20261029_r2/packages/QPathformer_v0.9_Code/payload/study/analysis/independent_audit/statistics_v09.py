"""Independent v0.9 metrics/statistics; no author or SciPy imports.

Student-t(df7) probabilities use the regularized incomplete beta continued
fraction and interval quantiles use bisection. Population summaries use math.fsum.
"""
import math,statistics
import numpy as np
import reference_v09 as ref

SCALARS=('bce','macro_f1','accuracy','brier','ece10','positive_precision','positive_recall','average_precision','native_bce','clipping_frequency')

def metrics(y,p,z):
    y=np.asarray(y);p=np.asarray(p);z=np.asarray(z);n=len(y)
    ref.need(y.ndim==1 and p.shape==z.shape==y.shape and set(np.unique(y))<={0,1} and
      np.isfinite(p).all() and np.isfinite(z).all() and np.all((p>=0)&(p<=1)),'Invalid metric vectors')
    if not n:return {'n':0,**{k:None for k in SCALARS},'confusion':[[0,0],[0,0]],'reliability10':[],
      'limitation':'Empty diagnostic slice; metrics undefined.'}
    base=ref.metrics(y,p);cm=np.asarray(base['confusion']);tp=cm[1,1];fp=cm[0,1];fn=cm[1,0]
    levels,inverse=np.unique(p,return_inverse=True)
    counts=np.bincount(inverse,minlength=len(levels))[::-1];positives=np.bincount(inverse,weights=y,minlength=len(levels))[::-1]
    total=int(y.sum());cumulative_tp=np.cumsum(positives);cumulative_n=np.cumsum(counts)
    ap=float(np.sum((positives/total)*(cumulative_tp/cumulative_n))) if total else None
    f1=[float(2*cm[k,k]/(cm[k].sum()+cm[:,k].sum())) if cm[k].sum()+cm[:,k].sum() else 0. for k in (0,1)]
    clipped=base.pop('clipped');base.update(positives=total,negatives=n-total,per_class_f1=f1,
      positive_precision=float(tp/(tp+fp)) if tp+fp else 0.,positive_recall=float(tp/(tp+fn)) if tp+fn else 0.,
      average_precision=ap,native_bce=float(np.mean(np.where(y==1,np.logaddexp(0.,-z),np.logaddexp(0.,z)))),
      clipped_count=clipped,clipping_frequency=clipped/n,
      clipped_wrong_prediction_count=int(np.sum(((p<ref.CLIP)|(p>1-ref.CLIP))&((p>=.5)!=y))),
      minimum_raw_probability=float(p.min()),maximum_raw_probability=float(p.max()),
      minimum_native_logit=float(z.min()),maximum_native_logit=float(z.max()),
      limitation='Single-class slice; registered two-class macro F1 still includes both classes.' if np.unique(y).size<2 else None)
    return base

def beta_fraction(a,b,x):
    tiny=1e-300;c=1.;d=1-(a+b)*x/(a+1);d=d if abs(d)>=tiny else tiny;d=1/d;h=d
    for m in range(1,401):
        for coefficient in (m*(b-m)*x/((a+2*m-1)*(a+2*m)),
                            -(a+m)*(a+b+m)*x/((a+2*m)*(a+2*m+1))):
            d=1+coefficient*d;d=d if abs(d)>=tiny else tiny
            c=1+coefficient/c;c=c if abs(c)>=tiny else tiny
            d=1/d;change=d*c;h*=change
        if abs(change-1)<4e-15:return h
    raise RuntimeError('Independent beta continued fraction did not converge')

def regularized_beta(a,b,x):
    if x<=0:return 0.
    if x>=1:return 1.
    coefficient=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
    if x<(a+1)/(a+b+2):return coefficient*beta_fraction(a,b,x)/a
    return 1-coefficient*beta_fraction(b,a,1-x)/b

def two_sided_t7(value):
    square=value*value
    # In the centre, 7/(7+t^2) loses t^2 when it is below machine precision.
    # Compute the complementary beta integral directly using the small ratio.
    if abs(value)<1:return 1-regularized_beta(.5,3.5,square/(7+square))
    return regularized_beta(3.5,.5,7/(7+square))

def critical_t7(confidence):
    ref.need(0<confidence<1,'Invalid confidence');lo,hi=0.,1.;target=1-confidence
    while two_sided_t7(hi)>target:hi*=2
    for _ in range(90):
        mid=(lo+hi)/2
        if two_sided_t7(mid)>target:lo=mid
        else:hi=mid
    return (lo+hi)/2

def distribution(values):
    observed=[float(x) for x in values if x is not None];n=len(observed)
    return {'n':len(values),'defined_n':n,'values':values,'mean':math.fsum(observed)/n if n else None,
      'minimum':min(observed) if n else None,'maximum':max(observed) if n else None,
      'sample_sd':statistics.stdev(observed) if n>1 else None}

def contrast(rows,family,first,second,confidence,primary):
    subset=[r for r in rows if r['family']==family];pops=sorted({r['population'] for r in subset})
    ref.need(len(pops)==8,'Eight independent populations required');parts=[]
    for pop in pops:
        byarm={}
        for arm in (first,second):
            chosen=[r for r in subset if r['population']==pop and r['arm']==arm]
            ref.need(len(chosen)==2 and len({r['seed'] for r in chosen})==2,'Two unique seeds required')
            byarm[arm]={r['seed']:r['test']['bce'] for r in chosen}
        ref.need(set(byarm[first])==set(byarm[second]),'Unpaired seeds')
        pairs=[{'seed':s,'first':byarm[first][s],'second':byarm[second][s],
          'difference':byarm[first][s]-byarm[second][s]} for s in sorted(byarm[first])]
        parts.append({'population':pop,'seed_pairs':pairs,'mean_difference':math.fsum(p['difference'] for p in pairs)/2})
    differences=[p['mean_difference'] for p in parts];mean=math.fsum(differences)/8;sd=statistics.stdev(differences);se=sd/math.sqrt(8)
    critical=critical_t7(confidence);low,high=mean-critical*se,mean+critical*se
    statistic=mean/se if se else None;pvalue=two_sided_t7(abs(statistic)) if se else (1. if mean==0 else 0.)
    return {'family':family,'first':first,'second':second,'metric':'bce','direction':'first minus second; negative favors first',
      'primary':primary,'populations':parts,'n_independent_populations':8,'paired_seeds_per_population':2,
      'mean_difference':mean,'population_sample_sd':sd,'standard_error':se,'df':7,'confidence':confidence,
      'critical_t':critical,'interval':[low,high],'t_statistic':statistic,'two_sided_p_unadjusted':pvalue,
      'bonferroni_p':min(1.,12*pvalue) if primary else None,'favors_first':high<0,'favors_second':low>0,
      'first_exceeds_practical_reference':high<-.01 if primary else None,
      'interpretation':'Interval is below zero.' if high<0 else 'Interval is above zero.' if low>0 else 'Interval includes zero; this does not demonstrate equivalence.',
      'multiplicity':'Bonferroni family of 12 primary BCE contrasts' if primary else 'Nominal 95% secondary exploratory interval'}

def analyze(rows,protocol):
    ref.need(len(rows)==len({r['job_id'] for r in rows})==636,'Complete636 endpoint analysis required')
    ref.need(protocol['family_size']==12 and protocol['populations_per_family']==8 and protocol['seeds_per_population']==2,'Analysis registration mismatch')
    primary=[contrast(rows,c['family'],c['first'],c['second'],protocol['nominal_per_contrast_confidence'],True) for c in protocol['primary_contrasts']]
    ref.need(len(primary)==12,'Twelve primary contrasts required');families=sorted({c['family'] for c in protocol['primary_contrasts']})
    secondary=[contrast(rows,f,c['first'],c['second'],.95,False) for f in families for c in protocol['secondary_contrasts']]
    synthetic=[]
    for family in families:
        selected=[r for r in rows if r['family']==family]
        for arm in sorted({r['arm'] for r in selected}):
            records=[r for r in selected if r['arm']==arm];ref.need(len(records)==16,'Synthetic arm requires16fits');populations=[]
            for pop in sorted({r['population'] for r in records}):
                rr=[r for r in records if r['population']==pop]
                populations.append({'population':pop,'seeds':[r['seed'] for r in rr],'metrics':{k:distribution([r['test'][k] for r in rr]) for k in SCALARS}})
            synthetic.append({'family':family,'arm':arm,'population_results':populations,
              'across_population_means':{k:distribution([p['metrics'][k]['mean'] for p in populations]) for k in SCALARS}})
    real=[];records=[r for r in rows if r['family']=='banknote'];ref.need(len(records)==60,'Banknote60 required')
    for arm in sorted({r['arm'] for r in records}):
        rr=sorted((r for r in records if r['arm']==arm),key=lambda r:r['seed']);ref.need(len(rr)==len({r['seed'] for r in rr})==5,'Banknote five unique seeds required')
        real.append({'arm':arm,'seeds':[r['seed'] for r in rr],'metrics':{k:distribution([r['test'][k] for r in rr]) for k in SCALARS},
          'limitation':'Descriptive optimization variation on one fixed grouped split; not independent datasets.'})
    return {'primary_contrasts':primary,'secondary_contrasts':secondary,'synthetic_by_family_and_arm':synthetic,
      'banknote_descriptive':real,'pooling':'No headline average across task families or across synthetic and Banknote data.'}
