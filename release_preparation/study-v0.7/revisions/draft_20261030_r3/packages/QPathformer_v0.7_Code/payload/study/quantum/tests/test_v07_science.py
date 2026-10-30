"""Bounded synthetic verification; never loads study data or sealed outcomes."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import models
import circuits
import reference_v03
import study

STREAMS={'paired_circuit_core_initialization':103000000000000000000000000000042,
         'mlp_initialization':207000000000000000000000000000063}


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
        return models.Model(method,13901,STREAMS)

    def test_counts_and_true_hash_input(self):
        self.assertEqual(len(models.METHODS),8)
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
        scalar=self.model('qscalar_kmeans');multi=self.model('qmulti_kmeans');hashed=self.model('qmulti_hash')
        np.testing.assert_array_equal(scalar.parameters.reshape(5,10)[:,:8],multi.parameters.reshape(5,14)[:,:8])
        np.testing.assert_array_equal(multi.parameters,hashed.parameters)
        # Extra multi-readout head weights start at zero; identical scalar predictions.
        np.testing.assert_allclose(scalar.predict(self.x,self.route),multi.predict(self.x,self.route),atol=0,rtol=0)
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
        m=self.model('trig_global');m.parameters[0]=1000
        loss,gradient,_,_=m.gradient(self.x,np.zeros(len(self.x),int))
        self.assertGreater(loss,999);self.assertAlmostEqual(gradient[0],1)

    def test_eight_identical_record_permutations_from_shared_stream(self):
        stream=987000000000000000000000000000017
        orders=[]
        for _ in models.METHODS:
            rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence(stream)))
            orders.append(np.array([rng.permutation(4800) for _ in range(2)],dtype=np.uint16))
        for order in orders[1:]:np.testing.assert_array_equal(order,orders[0])
        for order in orders[0]:np.testing.assert_array_equal(np.sort(order),np.arange(4800))

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
            self.assertEqual(actual['updates'],150 if stage=='engineering' else 15000)
        self.assertEqual(counts,{'engineering':32,'A':64,'B':512})

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
        for key in ('training_order','paired_circuit_core_initialization','mlp_initialization','sampling_diagnostics'):
            namespace='synthetic-endpoint-not-official|'+key
            streams[key]={'namespace':namespace,'uint128_decimal':str(int.from_bytes(hashlib.sha256(namespace.encode()).digest()[:16],'little'))}
        job={'run_id':'synthetic-contract-only/TrigHash','stage':'engineering','population_id':population,
             'training_seed_id':13901,'arm':'TrigHash','rounds':2,'updates_per_round':75,'updates':150,'batch_size':64,
             'paired_streams':streams}
        with tempfile.TemporaryDirectory(prefix='qpath_synthetic_contract_only_') as name:
            root=Path(name);data=root/'data';data.mkdir()
            matrix=root/'matrix.json';protocol=root/'protocol.json';authorization=root/'synthetic_authorization.json'
            matrix.write_text(json.dumps({'populations':[{'population_id':population}],'runs':[job]}))
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
                approval={'schema':'qpath-v07-stage-authorization-1','review_status':'approved_by_root','stage':'engineering',
                          'run_ids':[job['run_id']],'scientific_source_hashes':sources,'settings':study.SETTINGS,
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
                self.assertEqual(result['optimizer_global_updates'],150)
                self.assertEqual(result['completed_rounds'],2)
                self.assertFalse(result['test_accessed'])
                with self.assertRaises(FileExistsError):study.train(job['run_id'],first,authorization)
                for file in ('round_parameters.npy','validation_probabilities.npy','validation_logits.npy','record_orders.npy'):
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
                    self.assertEqual(ledger[-1]['optimizer_updates'],150)


if __name__=='__main__':unittest.main(verbosity=2)
