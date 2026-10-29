import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import qstudy as study
from prepare_study import generate, DATASETS


class MechanismChecks(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(901)
        self.x = rng.uniform(-.8,.8,(32,2))
        self.depth = np.tile(np.arange(1,5),8)
        self.y = (np.sum(self.x*self.x,axis=1) < 2/np.pi).astype(int)

    def finite_difference(self,model):
        _,g,_,_ = model.gradient(self.x,self.y,self.depth)
        exact = []
        eps = 1e-6
        for i in range(len(model.parameters)):
            old = model.parameters[i]
            model.parameters[i] = old+eps
            a = study.quantum.binary_cross_entropy(self.y,model.predict(self.x,self.depth))
            model.parameters[i] = old-eps
            b = study.quantum.binary_cross_entropy(self.y,model.predict(self.x,self.depth))
            model.parameters[i] = old
            exact.append((a-b)/(2*eps))
        np.testing.assert_allclose(g,exact,atol=2e-7,rtol=2e-5)

    def test_parameter_counts_and_all_gradients(self):
        expected = {"scheduled":16,"min_depth2":16,"fixed4":16,
                    "untied_assigned":40,"untied_balanced":40,"untied_all_records":40,
                    "mlp17":17,"mlp41":41,"mlp129":129,"min_depth2_mlp129":129}
        for method,count in expected.items():
            with self.subTest(method=method):
                model = study.Model(method,901)
                self.assertEqual(model.parameters.size,count)
                self.finite_difference(model)

    def test_untied_initialization_matches_original_prefix(self):
        a,b = study.Model("scheduled",902),study.Model("untied_assigned",902)
        np.testing.assert_allclose(a.predict(self.x,self.depth),b.predict(self.x,self.depth),atol=1e-15)
        for d in range(1,5):
            np.testing.assert_array_equal(a.bank(4)[:d],b.bank(d))

    def test_new_mechanisms_against_independent_matrix_reference(self):
        for method in ("scheduled","min_depth2","fixed4","untied_assigned"):
            model = study.Model(method,903)
            actual = model.predict(self.x,self.depth)
            for i,(x,d) in enumerate(zip(self.x,model.effective_depth(self.depth))):
                u = study.reference.unitary(x,model.bank(int(d)),int(d))
                expected = np.sum(np.abs(u[2:,0])**2)
                self.assertAlmostEqual(actual[i],expected,places=13)

    def test_expanded_exposure_gradient_weights_and_no_new_ids(self):
        model = study.Model("untied_balanced",904)
        data = {"x":self.x,"y":self.y,"depth":self.depth}
        groups = {d:np.flatnonzero(self.depth == d) for d in range(1,5)}
        samplers = {d:study.CyclicSampler(groups[d],904,d) for d in range(1,5)}
        weights = np.asarray([.1,.2,.3,.4])
        loss,g,clips,work,observed = study.expanded_gradient(model,data,np.arange(16),samplers,weights)
        self.assertEqual(sum(len(x) for x in observed),64)
        for d,ids in enumerate(observed,1):
            self.assertTrue(set(ids).issubset(set(groups[d])))
        self.assertEqual(work["circuit_examples"],sum(16*(1+8*d) for d in range(1,5)))
        self.assertEqual(work["layer_applications"],sum(16*d*(1+8*d) for d in range(1,5)))
        def objective():
            return sum(weights[d-1]*study.quantum.binary_cross_entropy(
                self.y[ids],study.quantum.predict_proba(self.x[ids],model.bank(d),d))
                for d,ids in enumerate(observed,1))
        eps = 1e-6
        for i in range(40):
            old = model.parameters[i]
            model.parameters[i] = old+eps
            a = objective()
            model.parameters[i] = old-eps
            b = objective()
            model.parameters[i] = old
            self.assertAlmostEqual(g[i],(a-b)/(2*eps),places=6)

    def test_data_partitions_and_new_streams(self):
        hashes=[]
        for seeds in DATASETS.values():
            data=generate(seeds)
            self.assertEqual([len(data[s]["y"]) for s in ("train","validation","test")],[4800,1600,1600])
            ids=[set(data[s]["ids"]) for s in ("train","validation","test")]
            self.assertFalse(ids[0]&ids[1] or ids[0]&ids[2] or ids[1]&ids[2])
            hashes.append(study.array_hash(data["train"]["x"]))
        self.assertEqual(len(set(hashes)),3)

    def test_training_test_loader_and_freeze_gate(self):
        with self.assertRaises(ValueError):
            study.load_population("confirmation","test")
        with tempfile.TemporaryDirectory() as directory, patch.object(study,"ROOT",Path(directory)):
            with self.assertRaises(RuntimeError):
                study.verify_freeze("A",301,"scheduled")
            with self.assertRaises(RuntimeError):
                study.verify_freeze("B",401,"scheduled")


if __name__ == "__main__":
    unittest.main()
