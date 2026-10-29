"""Prepare v0.8 synthetic tests; no execution."""
from pathlib import Path
p=Path(__file__).resolve().parent/'tests/test_v07_science.py'
s=p.read_text().replace('import tempfile','import tempfile\nimport sampling')
s=s.replace("103000000000000000000000000000042,\n         'mlp_initialization':207000000000000000000000000000063", "103000000000000000000000000000042")
s=s.replace('13901','1500').replace('len(models.METHODS),8','len(models.METHODS),5')
start=s.index("        scalar=self.model('qscalar_kmeans')")
end=s.index("        for first,second in ",start)
s=s[:start]+"""        multi=self.model('qmulti_kmeans');hashed=self.model('qmulti_hash')
        np.testing.assert_array_equal(multi.parameters,hashed.parameters)
"""+s[end:]
s=s.replace("'trig_global'","'trig121_global'")
start=s.index("    def test_eight_identical_record_permutations")
end=s.index("    def test_model_accounting",start)
s=s[:start]+"""    def test_shared_uniform_replacement_pairing_and_warmup(self):
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

"""+s[end:]
s=s.replace("150 if stage=='engineering'", "900 if stage=='engineering'")
s=s.replace("{'engineering':32,'A':64,'B':512}", "{'engineering':40,'A':80,'B':640}")
s=s.replace("'paired_circuit_core_initialization','mlp_initialization','sampling_diagnostics'", "'paired_circuit_core_initialization','sampling_diagnostics'")
s=s.replace("'synthetic-contract-only/TrigHash'", "'synthetic-contract-only/TrigHash_P'")
s=s.replace("'arm':'TrigHash','rounds':2", "'arm':'TrigHash_P','base_model':'TrigHash','sampling_policy':'priority','rounds':12")
s=s.replace("'updates':150,", "'updates':900,")
s=s.replace("with tempfile.TemporaryDirectory(prefix='qpath_synthetic_contract_only_') as name:", """fixture_parent=Path(__file__).resolve().parents[1]/'synthetic_fixtures'
        fixture_parent.mkdir(exist_ok=True)
        # Preserve success and failure evidence; never clean up a fit automatically.
        name=tempfile.mkdtemp(prefix='NOTSTUDY_contract_',dir=fixture_parent)
        if True:""")
s=s.replace('qpath-v07','qpath-v08')
s=s.replace("result['optimizer_global_updates'],150", "result['optimizer_global_updates'],900")
s=s.replace("result['completed_rounds'],2", "result['completed_rounds'],12")
s=s.replace("ledger[-1]['optimizer_updates'],150", "ledger[-1]['optimizer_updates'],900")
s=s.replace("('round_parameters.npy','validation_probabilities.npy','validation_logits.npy','record_orders.npy')", """('round_parameters.npy','validation_probabilities.npy','validation_logits.npy','record_orders.npy',
                             'sampler_uniforms.npy','sampling_probabilities.npy','sampling_weights.npy','sampling_counts.npy',
                             'refresh_native_losses.npy','refresh_scores.npy','refresh_priority_probabilities.npy',
                             'minibatch_gradients.npy','training_probabilities.npy','training_logits.npy','training_native_losses.npy')""")
s=s.replace("                    self.assertEqual(ledger[-1]['optimizer_updates'],900)", """                    self.assertEqual(ledger[-1]['optimizer_updates'],900)
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
                with self.assertRaisesRegex(RuntimeError,'Forbidden'):study.load_population(population,'train')""")
(p.parent/'test_v08_science.py').write_text(s,encoding='utf-8',newline='\n')
