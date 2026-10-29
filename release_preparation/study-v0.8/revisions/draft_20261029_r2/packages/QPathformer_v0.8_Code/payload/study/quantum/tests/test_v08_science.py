"""Bounded synthetic verification; never loads study data or sealed outcomes."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import sampling
import unittest
from unittest import mock
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import models
import circuits
import reference_v03
import study

STREAMS={'paired_circuit_core_initialization':103000000000000000000000000000042}


def independent_logits(model,x,route):
    """Scalar Kronecker-unitary / explicit basis / scalar MLP oracle."""
    I=np.eye(2);X=np.array([[0.,1.],[1.,0.]]);Z=np.diag([1.,-1.])
    ops=[np.kron(X,I),np.kron(I,X),np.kron(Z,I),np.kron(I,Z),np.kron(Z,Z)]
    result=[]
    for i,xy in enumerate(x):
        bank=0 if route is None else int(route[i])
        theta=model.parameters[bank*model.bank_width:(bank+1)*model.bank_width]
        if model.quantum:
            psi=reference_v03.unitary(xy,theta[:8].reshape(2,2,2),2,beta=0)[:,0]
            moments=[float(np.real(np.vdot(psi,op@psi))) for op in ops[:model.moment_count]]
            value=sum(float(theta[8+j])*moments[j] for j in range(model.moment_count))+float(theta[-1])
        elif model.family.startswith('trig'):
            def phi(t):
                out=[1.]
                for k in range(1,model.max_frequency+1):out.extend((math.cos(k*math.pi*t),math.sin(k*math.pi*t)))
                return out
            a,b=phi(xy[0]),phi(xy[1]);w=len(a)
            value=sum(float(theta[j*w+k])*a[j]*b[k] for j in range(w) for k in range(w))
        else:
            h=model.hidden
            values=[max(0.,float(xy[0]*theta[j]+xy[1]*theta[h+j]+theta[2*h+j])) for j in range(h)]
            value=sum(values[j]*theta[3*h+j] for j in range(h))+theta[-1]
        result.append(value)
    return np.asarray(result)


class ScienceTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(99347)
        self.x=rng.uniform(-.9,.9,(13,2))
        self.y=np.asarray([0,1,0,1,1,0,1,0,0,1,0,1,1])
        self.route=np.array([0,0,1,1,2,2,3,3,4,4,0,2,4])

    def model(self,method):
        return models.Model(method,1500,STREAMS)

    def test_counts_and_true_hash_input(self):
        self.assertEqual(len(models.METHODS),5)
        pop={'kmeans_route':self.route,'hash_route':self.route[::-1]}
        for method,count in models.PARAMETER_COUNTS.items():
            m=self.model(method)
            self.assertEqual(m.parameters.size,count)
            if m.routing=='global':self.assertIsNone(m.route_for(pop))
            else:np.testing.assert_array_equal(m.route_for(pop),pop[m.routing+'_route'])
        with self.assertRaises(ValueError):models.Model('qmulti_kmeans',1,{})

    def test_all_native_logits_against_independent_scalar_reference(self):
        for method in models.METHODS:
            m=self.model(method)
            # Nonzero learned heads/coefficients exercise every feature.
            m.parameters+=np.random.default_rng(191).normal(0,.07,m.parameters.shape)
            route=None if m.routing=='global' else self.route
            p,z=m.predict_with_logits(self.x,route)
            ref=independent_logits(m,self.x,route)
            np.testing.assert_allclose(z,ref,atol=4e-14,rtol=4e-14,err_msg=method)
            np.testing.assert_allclose(p,models.sigmoid(ref),atol=4e-14,rtol=4e-14,err_msg=method)

    def test_all_parameters_native_gradient_central_difference(self):
        step=1e-6
        for method in models.METHODS:
            m=self.model(method)
            m.parameters+=np.random.default_rng(286).normal(0,.035,m.parameters.shape)
            route=None if m.routing=='global' else self.route
            _,gradient,_,_=m.gradient(self.x,self.y,route)
            numeric=np.zeros_like(gradient)
            for j in range(len(gradient)):
                original=m.parameters[j]
                m.parameters[j]=original+step
                plus=models.logit_cross_entropy(self.y,m.predict_with_logits(self.x,route)[1])
                m.parameters[j]=original-step
                minus=models.logit_cross_entropy(self.y,m.predict_with_logits(self.x,route)[1])
                m.parameters[j]=original
                numeric[j]=(plus-minus)/(2*step)
            np.testing.assert_allclose(gradient,numeric,atol=3e-9,rtol=3e-5,err_msg=method)

    def test_paired_cores_heads_and_matching_route_update_identity(self):
        multi=self.model('qmulti_kmeans');hashed=self.model('qmulti_hash')
        np.testing.assert_array_equal(multi.parameters,hashed.parameters)
        for first,second in [('qmulti_kmeans','qmulti_hash'),('trig_kmeans','trig_hash')]:
            a,b=self.model(first),self.model(second);oa,ob=models.Adam(a.parameters.shape),models.Adam(b.parameters.shape)
            for _ in range(5):
                ga=a.gradient(self.x,self.y,self.route)[1];gb=b.gradient(self.x,self.y,self.route)[1]
                np.testing.assert_array_equal(ga,gb)
                oa.step(a.parameters,ga);ob.step(b.parameters,gb)
            np.testing.assert_array_equal(a.parameters,b.parameters)
            np.testing.assert_array_equal(oa.m,ob.m);np.testing.assert_array_equal(oa.v,ob.v)

    def test_total_minibatch_normalization_absent_bank_adam_movement(self):
        m=self.model('trig_kmeans')
        n=len(self.y);mixed=m.gradient(self.x,self.y,self.route)[1]
        gsum=np.zeros_like(mixed)
        for bank in range(5):
            mask=self.route==bank
            local=m.gradient(self.x[mask],self.y[mask],self.route[mask])[1]
            gsum+=local*sum(mask)/n
        np.testing.assert_allclose(mixed,gsum,atol=2e-17,rtol=2e-15)
        opt=models.Adam(m.parameters.shape);opt.step(m.parameters,mixed)
        x,y,r=self.x[:2],self.y[:2],np.zeros(2,dtype=int)
        grad=m.gradient(x,y,r)[1];before=m.parameters.copy()
        self.assertTrue(np.array_equal(grad[m.bank_width:],np.zeros(100)))
        opt.step(m.parameters,grad)
        self.assertTrue(np.any(m.parameters[m.bank_width:]!=before[m.bank_width:]))

    def test_frequency25_embedded_in121_and_extreme_native_loss(self):
        phi25=models.trig_features(self.x,2);phi121=models.trig_features(self.x,5)
        index=[a*11+b for a in range(5) for b in range(5)]
        np.testing.assert_array_equal(phi25,phi121[:,index])
        self.assertEqual(models.logit_cross_entropy(np.array([0,1]),np.array([1000.,-1000.])),1000.)
        self.assertTrue(np.isfinite(models.binary_cross_entropy(np.array([0,1]),np.array([1.,0.]))))
        m=self.model('trig121_global');m.parameters[0]=1000
        loss,gradient,_,_=m.gradient(self.x,np.zeros(len(self.x),int))
        self.assertGreater(loss,999);self.assertAlmostEqual(gradient[0],1)

    def test_shared_uniform_replacement_pairing_and_warmup(self):
        stream=987000000000000000000000000000017
        all_uniforms=[]
        for _ in models.ARM_METHODS:
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(stream)))
            all_uniforms.append(np.array([rng.random(4800) for _ in range(12)]))
        for draws in all_uniforms[1:]:np.testing.assert_array_equal(draws,all_uniforms[0])
        scores,proposed=sampling.priority_distribution(np.linspace(0,10,4800))
        for r in range(1,13):
            a=sampling.selected_distribution(4800,r,'U',proposed)
            b=sampling.selected_distribution(4800,r,'P',proposed)
            ia,wa=sampling.inverse_cdf_draws(a,all_uniforms[0][r-1])
            ib,wb=sampling.inverse_cdf_draws(b,all_uniforms[0][r-1])
            if r<=10:
                np.testing.assert_array_equal(ia,ib);np.testing.assert_array_equal(wa,wb)
            else:self.assertFalse(np.array_equal(ia,ib))
            self.assertLess(len(np.unique(ia)),4800)

    def test_weighted_native_gradients_all_parameters_finite_difference(self):
        weights=np.linspace(.2,1.9,len(self.y));step=1e-6
        for method in models.METHODS:
            m=self.model(method);m.parameters+=np.random.default_rng(286).normal(0,.035,m.parameters.shape)
            route=None if m.routing=='global' else self.route
            loss,gradient,_,_=m.gradient(self.x,self.y,route,sample_weight=weights)
            objective=lambda:float(np.mean(weights*models.native_losses(self.y,independent_logits(m,self.x,route))))
            self.assertAlmostEqual(loss,objective(),places=13)
            numeric=np.zeros_like(gradient)
            for j in range(len(gradient)):
                original=m.parameters[j];m.parameters[j]=original+step;plus=objective()
                m.parameters[j]=original-step;minus=objective();m.parameters[j]=original
                numeric[j]=(plus-minus)/(2*step)
            np.testing.assert_allclose(gradient,numeric,atol=3e-9,rtol=3e-5,err_msg=method)
            twice=m.gradient(self.x,self.y,route,sample_weight=2*weights)[1]
            np.testing.assert_array_equal(twice,2*gradient)

    def test_expected_importance_gradient_equals_uniform_empirical_gradient(self):
        p=np.arange(1,len(self.y)+1,dtype=float);p/=p.sum()
        for method in models.METHODS:
            m=self.model(method);m.parameters+=np.random.default_rng(103).normal(0,.04,m.parameters.shape)
            route=None if m.routing=='global' else self.route
            full=m.gradient(self.x,self.y,route)[1];expected=np.zeros_like(full)
            for i in range(len(self.y)):
                local=m.gradient(self.x[i:i+1],self.y[i:i+1],None if route is None else route[i:i+1],
                                 sample_weight=np.array([1/(len(self.y)*p[i])]))[1]
                expected+=p[i]*local
            np.testing.assert_allclose(expected,full,atol=4e-16,rtol=5e-14)

    def test_priority_formula_boundary_failures_and_loss_cap_not_gradient_cap(self):
        losses=np.array([0.,.2,5.,1000.])
        scores,p=sampling.priority_distribution(losses)
        np.testing.assert_array_equal(scores,np.sqrt(np.minimum(losses,5.)+.001))
        np.testing.assert_array_equal(p,.5/4+.5*scores/scores.sum())
        self.assertTrue(np.all(p>=.5/4))
        ids,w=sampling.inverse_cdf_draws(np.array([.25,.75]),np.array([0.,.25,np.nextafter(1.,0.)]))
        np.testing.assert_array_equal(ids,[0,1,1]);np.testing.assert_array_equal(w,[2.,2/3,2/3])
        for bad in ([np.nan,0],[-1,0],[np.inf,1],[]):
            with self.assertRaises(ValueError):sampling.priority_distribution(bad)
        for badp in ([.1,.1],[0.,1.],[-1.,2.]):
            with self.assertRaises(ValueError):sampling.inverse_cdf_draws(badp,np.array([.5]))
        with self.assertRaises(ValueError):sampling.selected_distribution(4,11,'P',None)
        with self.assertRaises(ValueError):sampling.inverse_cdf_draws([.5,.5],[1.])
        m=self.model('trig121_global');m.parameters[0]=1000
        loss,g,_,_=m.gradient(self.x,np.zeros(len(self.x),int),sample_weight=np.full(len(self.x),1.7))
        self.assertGreater(loss,1600);self.assertAlmostEqual(g[0],1.7)
        for weights in (np.zeros(len(self.x)),np.full(len(self.x),np.nan),np.ones(3)):
            with self.assertRaises(ValueError):m.gradient(self.x,self.y,sample_weight=weights)

    def test_model_accounting_exact_passes_and_feature_counts(self):
        for method in models.METHODS:
            m=self.model(method);r=None if m.routing=='global' else self.route
            work=m.gradient(self.x,self.y,r)[3]
            self.assertEqual(work['model_record_visits'],len(self.x))
            if m.quantum:
                self.assertEqual(work['core_statevector_examples'],17*len(self.x))
                self.assertEqual(work['cx_gates'],34*len(self.x))
                self.assertEqual(work['moment_values_computed'],17*len(self.x)*m.moment_count)
            if m.family.startswith('trig'):
                self.assertEqual(work['trig_feature_values'],m.bank_width*len(self.x))

    def test_all_registered_matrix_identities_and_complete_stage_budgets(self):
        """Read registration metadata only; no official data or models initialized."""
        matrix=study.read_json(study.MATRIX_PATH)
        counts={'engineering':0,'A':0,'B':0}
        for row in matrix['runs']:
            actual=study.registered_job(row['run_id'])
            self.assertEqual(actual,row)
            stage=study.STAGE_MAP[row['stage']]
            counts[stage]+=1
            self.assertEqual(actual['updates'],900 if stage=='engineering' else 15000)
        self.assertEqual(counts,{'engineering':40,'A':80,'B':640})

    def test_synthetic_endpoint_serialization_and_gate_fail_closed(self):
        """Temporary synthetic fixture only; not a registered study population."""
        import routers
        rng=np.random.default_rng(99000037)
        train_x=rng.uniform(-1,1,(4800,2));val_x=rng.uniform(-1,1,(1600,2))
        policy=routers.fit_route_policy(train_x,99000038,'synthetic-test-not-official')
        bins=routers.fit_margin_bins(train_x,policy)
        policy['margin_bins']=bins
        population='synthetic_contract_fixture_only'
        streams={}
        for key in ('training_order','paired_circuit_core_initialization','sampling_diagnostics'):
            namespace='synthetic-endpoint-not-official|'+key
            streams[key]={'namespace':namespace,'uint128_decimal':str(int.from_bytes(hashlib.sha256(namespace.encode()).digest()[:16],'little'))}
        job={'run_id':'synthetic-contract-only/TrigHash_P','stage':'engineering','population_id':population,
             'training_seed_id':1500,'arm':'TrigHash_P','base_model':'TrigHash','sampling_policy':'priority','rounds':12,'updates_per_round':75,'updates':900,'batch_size':64,
             'paired_streams':streams}
        fixture_parent=Path(__file__).resolve().parents[1]/'synthetic_fixtures'
        fixture_parent.mkdir(exist_ok=True)
        # Preserve success and failure evidence; never clean up a fit automatically.
        name=tempfile.mkdtemp(prefix='NOTSTUDY_contract_',dir=fixture_parent)
        if True:
            root=Path(name);data=root/'data';data.mkdir()
            matrix=root/'matrix.json';protocol=root/'protocol.json';authorization=root/'synthetic_authorization.json'
            uniform_job=dict(job,run_id='synthetic-contract-only/TrigHash_U',arm='TrigHash_U',sampling_policy='uniform')
            matrix.write_text(json.dumps({'populations':[{'population_id':population}],'runs':[job,uniform_job]}))
            protocol.write_text('{"classification":"SYNTHETIC_UNIT_TEST_ONLY"}')
            files={}
            for split,x,offset in [('train',train_x,0),('validation',val_x,4800)]:
                path=data/f'{population}_{split}.npz'
                np.savez(path,x=x,y=(x[:,0]*x[:,1]>0).astype(int),ids=np.arange(offset,offset+len(x)),
                         source_draw_ids=np.arange(offset,offset+len(x)),
                         hash_route=routers.route(x,policy,'hash'),kmeans_route=routers.route(x,policy,'kmeans'),
                         margin_bin=routers.margin_bins(x,policy,bins))
                files[path.name]={'sha256':study.digest(path)}
            router=data/f'{population}_router.json';router.write_text(json.dumps(policy))
            seal={'files':files,'routers':{population:{'sha256':study.digest(router)}},'datasets':{population:{
                'generation_seconds':0.,'router_fit_seconds':0.,
                'route_application_seconds_by_split':{split:{'hash':0.,'kmeans':0.} for split in ('train','validation')}}}}
            (data/'DATA_SEAL.json').write_text(json.dumps(seal))
            # Source introspection is mocked in this serialization unit only;
            # the separate gate checks below still bind and reject changed hashes.
            sources={'synthetic_fixture_only':'0'*64}
            with mock.patch.object(study,'ROOT',root),mock.patch.object(study,'MATRIX_PATH',matrix), \
                 mock.patch.object(study,'PROTOCOL_PATH',protocol),mock.patch.object(study,'source_hashes',return_value=sources):
                approval={'schema':'qpath-v08-stage-authorization-1','review_status':'approved_by_root','stage':'engineering',
                          'run_ids':[job['run_id'],uniform_job['run_id']],'scientific_source_hashes':sources,'settings':study.SETTINGS,
                          'data_seal_sha256':study.digest(data/'DATA_SEAL.json'),
                          'matrix_sha256':study.digest(matrix),'protocol_sha256':study.digest(protocol),
                          'classification':'SYNTHETIC_UNIT_TEST_ONLY_NOT_ROOT_STUDY_APPROVAL'}
                authorization.write_text(json.dumps(approval))
                with self.assertRaises(ValueError):study.load_population(population,'test')
                for key in ('scientific_source_hashes','data_seal_sha256','matrix_sha256','protocol_sha256','run_ids','settings'):
                    altered=dict(approval);altered[key]=None;authorization.write_text(json.dumps(altered))
                    with self.assertRaises(RuntimeError):study.verify_freeze(job,authorization)
                authorization.write_text(json.dumps(approval))
                first,second=root/'first',root/'second'
                result=study.train(job['run_id'],first,authorization)
                study.train(job['run_id'],second,authorization)
                uniform_output=root/'uniform_control'
                study.train(uniform_job['run_id'],uniform_output,authorization)
                np.testing.assert_array_equal(np.load(first/'round_parameters.npy')[:10],
                                              np.load(uniform_output/'round_parameters.npy')[:10])
                np.testing.assert_array_equal(np.load(first/'sampler_uniforms.npy'),
                                              np.load(uniform_output/'sampler_uniforms.npy'))
                np.testing.assert_array_equal(np.load(first/'refresh_native_losses.npy')[0],
                                              np.load(uniform_output/'refresh_native_losses.npy')[0])
                np.testing.assert_array_equal(np.load(uniform_output/'sampling_probabilities.npy'),
                                              np.full((12,4800),1/4800))
                self.assertFalse(np.array_equal(np.load(first/'round_parameters.npy')[10],
                                                np.load(uniform_output/'round_parameters.npy')[10]))
                self.assertEqual(result['optimizer_global_updates'],900)
                self.assertEqual(result['completed_rounds'],12)
                self.assertFalse(result['test_accessed'])
                with self.assertRaises(FileExistsError):study.train(job['run_id'],first,authorization)
                for file in ('round_parameters.npy','validation_probabilities.npy','validation_logits.npy','record_orders.npy',
                             'sampler_uniforms.npy','sampling_probabilities.npy','sampling_weights.npy','sampling_counts.npy',
                             'refresh_native_losses.npy','refresh_scores.npy','refresh_priority_probabilities.npy',
                             'minibatch_gradients.npy','training_probabilities.npy','training_logits.npy','training_native_losses.npy'):
                    np.testing.assert_array_equal(np.load(first/file),np.load(second/file))
                for endpoint in (first,second):
                    commit=study.read_json(endpoint/'endpoint_commit.json')
                    self.assertEqual(commit['job_id'],job['run_id'])
                    for file,record in commit['files'].items():
                        self.assertEqual(study.digest(endpoint/file),record['sha256'])
                        self.assertEqual((endpoint/file).stat().st_size,record['bytes'])
                    ledger=[json.loads(line) for line in (endpoint/'ledger.jsonl').read_text().splitlines()]
                    minimum=min((row['validation']['bce'],row['round']) for row in ledger)
                    self.assertEqual(result['selected_round'],minimum[1])
                    self.assertEqual(ledger[-1]['optimizer_updates'],900)
                    self.assertEqual(result['sampling_diagnostics']['refresh_count'],2)
                    gradients=np.load(endpoint/'minibatch_gradients.npy')
                    replay=models.Model('trig_hash',1500,{k:int(v['uint128_decimal']) for k,v in streams.items()})
                    optimizer=models.Adam(replay.parameters.shape);states=np.load(endpoint/'round_parameters.npy')
                    for idx,gradient in enumerate(gradients):
                        optimizer.step(replay.parameters,gradient)
                        if idx%75==74:np.testing.assert_array_equal(replay.parameters,states[idx//75])
                    trace=np.load(endpoint/'sampling_probabilities.npy')
                    np.testing.assert_array_equal(trace[:10],np.full((10,4800),1/4800))
                    self.assertFalse(np.array_equal(trace[10],trace[9]))
                    self.assertFalse(np.array_equal(trace[10],trace[11]))
                    # Loader refuses any accidental hidden-label field, even when hash-sealed.
                trpath=data/f'{population}_train.npz'
                with np.load(trpath) as saved:trainpayload={k:saved[k] for k in saved.files}
                np.savez(trpath,**trainpayload,clean_y=trainpayload['y'])
                seal['files'][trpath.name]['sha256']=study.digest(trpath)
                (data/'DATA_SEAL.json').write_text(json.dumps(seal))
                with self.assertRaisesRegex(RuntimeError,'Forbidden'):study.load_population(population,'train')


if __name__=='__main__':unittest.main(verbosity=2)
