"""One-time source adaptation; reads sealed v0.6, writes only the v0.7 audit tree."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = Path(r"C:\Q2\Improvement_Study_v0.6\analysis\classical_review")


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one source marker, got {text.count(old)}: {old[:100]}")
    return text.replace(old, new)


r = (OLD/"reference_v06.py").read_text(encoding="utf-8")
r = r.replace("Independent v0.6 numerical oracle", "Independent v0.7 numerical oracle")
r = replace(r, "METHODS=('qscalar_kmeans','qmulti_kmeans','mlp8tanh_kmeans','trig_kmeans','trig_global','mlp_global')",
            "METHODS=('qscalar_kmeans','qmulti_kmeans','qmulti_hash','trig_kmeans','trig_hash','trig_global','trig121_global','mlp_global')")
r = replace(r, "PARAMETERS={'qscalar_kmeans':50,'qmulti_kmeans':70,'mlp8tanh_kmeans':165,'trig_kmeans':125,'trig_global':25,'mlp_global':129}",
            "PARAMETERS=dict(zip(METHODS,(50,70,70,125,125,25,121,129)))")
start, end = r.index("def trig_features"), r.index("\ndef inputs")
r = r[:start]+'''def trig_features(x,frequency=2):
    x=np.asarray(x,dtype=np.float64);phase=np.pi*x
    pieces=[np.ones_like(x)]
    for harmonic in range(1,frequency+1):
        pieces.extend([np.cos(harmonic*phase),np.sin(harmonic*phase)])
    f=np.stack(pieces,axis=-1)
    width=2*frequency+1
    return np.einsum('ni,nj->nij',f[:,0],f[:,1]).reshape(len(x),width*width)
'''+r[end:]
r = replace(r, "phi=trig_features(x) if method.startswith('trig') else None",
            "phi=trig_features(x,5 if method=='trig121_global' else 2) if method.startswith('trig') else None")
r = replace(r, "f=[[1.,math.cos(math.pi*t),math.sin(math.pi*t),math.cos(2*math.pi*t),math.sin(2*math.pi*t)] for t in row]\n            z=sum(float(p[5*i+j])*f[0][i]*f[1][j] for i in range(5) for j in range(5))",
'''frequency=5 if method=='trig121_global' else 2
            width=2*frequency+1
            f=[[1.]+[v for k in range(1,frequency+1) for v in (math.cos(k*math.pi*t),math.sin(k*math.pi*t))] for t in row]
            z=sum(float(p[width*i+j])*f[0][i]*f[1][j] for i in range(width) for j in range(width))''')
(HERE/"reference_v07.py").write_text(r, encoding="utf-8")

a = (OLD/"audit_endpoints_v06.py").read_text(encoding="utf-8")
a = a[:a.index("\ndef audit_stage(")]
a = a.replace("import argparse, csv, hashlib, json, sys, time, traceback", "import argparse, csv, hashlib, json, sqlite3, sys, time, traceback")
a = a.replace("import reference_v06 as ref", "import reference_v07 as ref")
start, end = a.index("SEEDS="), a.index("PTOL=")
a = a[:start]+"""ARM_METHODS=dict(zip(('ScalarK','MultiK','MultiHash','TrigK','TrigHash','TrigG25','TrigG121','MLPG129'),ref.METHODS))
STAGE_COUNTS={'engineering':32,'A':64,'B':512}
"""+a[end:]
a = replace(a, "'source_draw_ids','hash_route','kmeans_route')", "'source_draw_ids','hash_route','kmeans_route','margin_bin')")
a = replace(a, "def expected_initial(method,seed):", "def expected_initial(method,streams):")
a = replace(a, "np.random.SeedSequence([seed,1])", "np.random.SeedSequence(int(streams['paired_circuit_core_initialization']['uint128_decimal']))")
a = replace(a, "if family=='trig':\n        master=np.zeros((banks,25));return master.ravel(),master,np.empty(0)",
            "if family.startswith('trig'):\n        master=np.zeros((banks,121 if family=='trig121' else 25));return master.ravel(),master,np.empty(0)")
a = replace(a, "np.random.SeedSequence([seed,4,h])", "np.random.SeedSequence(int(streams['mlp_initialization']['uint128_decimal']))")
a = replace(a, "'trig_feature_values':25*n if family=='trig' else 0", "'trig_feature_values':(121 if family=='trig121' else 25)*n if family.startswith('trig') else 0")
a = replace(a, "def audit_endpoint(folder,stage,population,seed,method,seal,freeze=None,engineering=False):",
"""def audit_endpoint(folder,job,seal,authorization):
    stage=job['stage'];population=job['population_id'];seed=job['training_seed_id']
    method=ARM_METHODS[job['arm']];engineering=stage=='engineering';freeze=read(authorization)
    need(freeze['review_status']=='approved_by_root' and freeze['schema']=='qpath-v07-stage-authorization-1','Root authority missing')
    need(freeze['stage']==stage and freeze['data_seal_sha256']==sha(Q/'data/DATA_SEAL.json'),'Authority stage/data differs')
    need(freeze['matrix_sha256']==sha(ROOT/'governance/RUN_MATRIX.json') and freeze['protocol_sha256']==sha(ROOT/'governance/STUDY_PLAN.json'),'Authority protocol/matrix differs')
    expected_ids=[row['run_id'] for row in read(ROOT/'governance/RUN_MATRIX.json')['runs'] if row['stage']==stage]
    need(freeze['run_ids']==expected_ids,'Authority does not bind complete matrix stage')""")
a = replace(a, "'QPATH-GENERALIZATION-v0.6'", "'QPATH-ROUTING-REPLICATION-v0.7'")
a = replace(a, "rounds=int(c['rounds']);need(rounds>0 and (engineering or rounds==200),'Full horizon not completed')",
            "rounds=int(c['rounds']);need(rounds==job['rounds']==(2 if engineering else 200),'Full horizon not completed')")
a = replace(a, "need(r['completed_rounds']==status['round']==rounds and r['optimizer_global_updates']==75*rounds,'Endpoint update count differs')",
            "need(r['completed_rounds']==status['round']==commit['completed_rounds']==rounds and r['optimizer_global_updates']==commit['optimizer_global_updates']==job['updates']==75*rounds,'Endpoint update count differs')")
start, end = a.index("    if not engineering:\n", a.index("def audit_endpoint")), a.index("    data=[]", a.index("def audit_endpoint"))
a = a[:start]+"""    need(c['source_hashes']==freeze['scientific_source_hashes'],'Source not frozen')
    need(c['settings']==freeze['settings'],'Settings differ from freeze')
    for obj in (c,r,commit):
        need(obj['job_id']==job['run_id'] and obj['arm']==job['arm'],'Exact matrix job/arm identity differs')
        need(obj['authorization_sha256']==sha(authorization),'Authorization binding differs')
        need(obj['matrix_sha256']==sha(ROOT/'governance/RUN_MATRIX.json') and obj['protocol_sha256']==sha(ROOT/'governance/STUDY_PLAN.json'),'Active protocol binding differs')
    need(c['paired_streams']==job['paired_streams'],'Paired RNG stream identity differs')
    for stream in job['paired_streams'].values():
        need(int.from_bytes(hashlib.sha256(stream['namespace'].encode('ascii')).digest()[:16],'little')==int(stream['uint128_decimal']),'RNG derivation differs')
"""+a[end:]
a = replace(a, "expected_initial(method,seed)", "expected_initial(method,job['paired_streams'])")
a = replace(a, "np.random.SeedSequence([seed,2])", "np.random.SeedSequence(int(job['paired_streams']['training_order']['uint128_decimal']))")
a = replace(a, "    best=float('inf');chosen=None;", "    appearances=np.zeros(banks,dtype=np.int64)\n    best=float('inf');chosen=None;")
a = replace(a, "        same(orders[i],sampler.permutation(4800),'Paired sample order differs')",
"""        same(orders[i],sampler.permutation(4800),'Paired sample order differs')
        for batch in orders[i].reshape(75,64):
            counts=np.array([64]) if banks==1 else np.bincount(train[routing+'_route'][batch],minlength=5)
            appearances+=(counts>0)
        need(row['bank_minibatch_appearances_cumulative']==appearances.tolist(),'Per-bank minibatch appearances differ')
        need(row['bank_absent_updates_cumulative']==(75*number-appearances).tolist(),'Absent bank update count differs')
        for key in ('bank_absent_parameter_movement_l2_sum_cumulative','bank_gradient_l2_sum_cumulative'):
            values=np.asarray(row[key],float)
            need(values.shape==(banks,) and np.isfinite(values).all() and np.all(values>=0),'Invalid bank diagnostic '+key)
            if i:need(np.all(values+1e-12>=np.asarray(ledger[i-1][key])),'Nonmonotone bank diagnostic '+key)
        need(np.all(np.asarray(row['bank_absent_parameter_movement_l2_sum_cumulative'])[75*number-appearances==0]==0),'Absent movement without absence')""")
a = replace(a, "    need(r['bank_training_record_visits']==(bank_counts*rounds).tolist(),'Endpoint exposure differs')",
"""    need(r['bank_training_record_visits']==(bank_counts*rounds).tolist(),'Endpoint exposure differs')
    for final_key,row_key in (('bank_minibatch_appearances','bank_minibatch_appearances_cumulative'),
                             ('bank_absent_updates','bank_absent_updates_cumulative'),
                             ('bank_absent_parameter_movement_l2_sum','bank_absent_parameter_movement_l2_sum_cumulative'),
                             ('bank_gradient_l2_sum','bank_gradient_l2_sum_cumulative')):
        need(r[final_key]==ledger[-1][row_key],'Final bank diagnostics differ')
    selected_banks=states[chosen-1].reshape(banks,-1)
    same(np.asarray(r['selected_coefficients_or_heads_by_bank']),selected_banks[:,8:] if method.startswith('q') else selected_banks,'Selected coefficients differ')
    near(r['selected_parameter_l2_norm_by_bank'],np.linalg.norm(selected_banks,axis=1),CTOL,'Selected bank parameter norm differs')""")
a = replace(a, "            if ix.any():metric_check(ref.metrics(val['y'][ix],probs[chosen-1,ix]),r['validation_by_route'][kind][str(bank)])",
"""            subgroup=r['validation_by_route'][kind][str(bank)]
            need(subgroup['n']==int(ix.sum()) and subgroup['positive_count']==int(val['y'][ix].sum()),'Route subgroup membership differs')
            if ix.any():metric_check(ref.metrics(val['y'][ix],probs[chosen-1,ix]),subgroup['metrics'])
            else:need(subgroup['metrics'] is None,'Empty route metrics must be null')
    margin_count=read(Q/'data'/f'{population}_router.json')['margin_bins']['bins']
    need(set(r['validation_by_margin_bin'])=={str(k) for k in range(margin_count)},'Margin bin inventory differs')
    for k in range(margin_count):
        ix=val['margin_bin']==k;subgroup=r['validation_by_margin_bin'][str(k)]
        need(subgroup['n']==int(ix.sum()),'Margin membership differs')
        if ix.any():metric_check(ref.metrics(val['y'][ix],probs[chosen-1,ix]),subgroup['metrics'])
        else:need(subgroup['metrics'] is None,'Empty margin metrics must be null')""")
start, end = a.index("    inf=r['inference'];"), a.index("    cost=seal", a.index("    inf=r['inference'];"))
a = a[:start]+"""    need(r['inference']=={'performed':False,'scope':'Timing deferred to isolated post-training deployment sessions.'},'Training must not perform inference timing')
    train_prediction,train_logits=ref.predict_with_logits(method,states[chosen-1],train['x'],None if banks==1 else train[routing+'_route'])
    metric_check(ref.metrics(train['y'],train_prediction),r['selected_training'])
    near(ref.stable_logit_bce(train['y'],train_logits),r['selected_training_native_bce'],NTOL,'Selected training native loss differs')
    for key in ('training_process_cpu_seconds','invocation_process_cpu_seconds_through_result','invocation_wall_seconds_through_result'):
        need(np.isfinite(r[key]) and r[key]>=0,'Invalid process resource diagnostic')
    need(r['training_process_cpu_seconds']<=r['invocation_process_cpu_seconds_through_result'],'Process CPU scopes inconsistent')
"""+a[end:]
a = replace(a, "return {'population':population,'method':method,'seed':seed,", "return {'job_id':job['run_id'],'arm':job['arm'],'stage':stage,'population':population,'method':method,'seed':seed,")
a += (HERE/"stage_audit_tail.py.txt").read_text(encoding="utf-8")
(HERE/"audit_endpoints_v07.py").write_text(a,encoding="utf-8")
print("Adapted independent oracle and endpoint auditor; no production or study execution.")
