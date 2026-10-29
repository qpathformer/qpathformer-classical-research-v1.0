"""Independent behavioral checks for the connected classical reference."""
from copy import deepcopy
from dataclasses import replace
import inspect
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import torch

from qpath.classical import (ModelConfig, QPathTextModel, TextTokenizer, adamw_optimizer,
                            fit_training_centroids, spherical_kmeans, train_update)


class ClassicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        torch.manual_seed(123)
        self.config = replace(ModelConfig.smoke(), dropout=0.0, adapters=3)
        self.model = QPathTextModel(self.config)

    def test_full_reference_shape_and_inference_boundary(self):
        full = QPathTextModel(ModelConfig()).eval()
        self.assertEqual(len(full.blocks), 6)
        self.assertEqual(len(full.adapters), 18)
        self.assertEqual(full.blocks[0].attention.num_heads, 4)
        self.assertEqual(full.blocks[0].linear1.out_features, 1024)
        self.assertEqual(full.adapters[0].down.out_features, 16)
        full.route_mode = "shared"
        with torch.no_grad():
            output = full(torch.tensor([[2, 3, 4, 0], [5, 6, 0, 0]]),
                          torch.tensor([[1, 1, 1, 0], [1, 1, 0, 0]], dtype=torch.bool))
        self.assertEqual(tuple(output["logits"].shape), (2, 4))
        self.assertTrue(torch.isfinite(output["logits"]).all())
        parameters = inspect.signature(full.forward).parameters
        self.assertFalse({"labels", "ratings", "priorities", "record_ids", "split"} & set(parameters))
        with self.assertRaises(TypeError):
            full(torch.tensor([[2]]), torch.tensor([[True]]), labels=torch.tensor([1]))

    def test_raw_residual_and_router_copy(self):
        raw = torch.tensor([[3.0, 4.0] + [0.0] * 30, [0.0] * 32])
        before = raw.clone()
        centroids = torch.eye(32)[:3]
        self.model.set_centroids(centroids, ["train-a", "train-b", "train-c"])
        routes, flags = self.model.select_routes(raw)
        adapted = self.model.apply_adapters(raw, routes)
        self.assertTrue(torch.equal(raw, before))
        self.assertTrue(torch.equal(adapted, raw))  # Zero up-projection preserves magnitude 5, not 1.
        self.assertEqual(routes.tolist(), [1, 0])
        self.assertEqual(flags.tolist(), [False, True])
        scaled_routes, _ = self.model.select_routes(raw * 10)
        self.assertTrue(torch.equal(routes, scaled_routes))

    def test_cosine_ties_choose_first_and_padding_does_not_change_logits(self):
        centers = torch.zeros(3, 32)
        centers[:, 0] = 1
        self.model.set_centroids(centers, ["train-a"])
        routes, _ = self.model.select_routes(torch.ones(2, 32))
        self.assertEqual(routes.tolist(), [0, 0])
        self.model.route_mode = "shared"
        self.model.eval()
        with torch.no_grad():
            first = self.model(torch.tensor([[4, 5]]), torch.tensor([[True, True]]))["logits"]
            padded = self.model(torch.tensor([[4, 5, 0, 0]]), torch.tensor([[True, True, False, False]]))["logits"]
        self.assertTrue(torch.allclose(first, padded, atol=1e-7, rtol=1e-6))
        with self.assertRaises(ValueError):
            self.model(torch.zeros(1, 4, dtype=torch.long), torch.zeros(1, 4, dtype=torch.bool))

    def test_inactive_adapter_weights_and_existing_adamw_moments_do_not_drift(self):
        optimizer = adamw_optimizer(self.model, lr=0.003)
        raw = torch.randn(8, 32)
        labels = torch.arange(8) % 4

        def update(route):
            optimizer.zero_grad(set_to_none=True)
            adapted = self.model.apply_adapters(raw, torch.full((8,), route, dtype=torch.long))
            torch.nn.functional.cross_entropy(self.model.classifier(adapted), labels).backward()
            optimizer.step()

        update(1)  # Initialise momentum/variance for the soon-to-be-inactive adapter.
        inactive_params = list(self.model.adapters[1].parameters())
        weights = [p.detach().clone() for p in inactive_params]
        states = [deepcopy(optimizer.state[p]) for p in inactive_params]
        active_up_before = self.model.adapters[0].up.weight.detach().clone()
        update(0)
        for parameter, weight, state in zip(inactive_params, weights, states):
            self.assertIsNone(parameter.grad)
            self.assertTrue(torch.equal(parameter, weight))
            for key, value in state.items():
                if torch.is_tensor(value):
                    self.assertTrue(torch.equal(optimizer.state[parameter][key], value), key)
                else:
                    self.assertEqual(optimizer.state[parameter][key], value)
        self.assertFalse(torch.equal(self.model.adapters[0].up.weight, active_up_before))

    def test_train_only_tokenizer_and_centroid_guards(self):
        train = [{"id": f"train-{i}", "text": f"training document sample {i}", "split": "train"} for i in range(24)]
        tokenizer = TextTokenizer.fit(train, 64, 16)
        self.assertEqual(set(tokenizer.training_ids), {r["id"] for r in train})
        with self.assertRaises(ValueError):
            TextTokenizer.fit(train + [{"id": "test-x", "text": "unseen", "split": "test"}], 64, 16)
        with self.assertRaises(ValueError):
            fit_training_centroids(self.model, tokenizer, [{"id": "val-x", "text": "a", "split": "validation"}], 2)
        fit = fit_training_centroids(self.model, tokenizer, train, seed=2, batch_size=8)
        self.assertEqual(set(fit["training_ids"]), {r["id"] for r in train})
        self.assertEqual(self.model.centroid_training_ids, tuple(r["id"] for r in train))
        self.assertTrue(torch.allclose(self.model.centroids.norm(dim=1), torch.ones(3), atol=1e-5))

    def test_saved_tokenizer_load_verifies_disk_artifact_and_reproduces_encoding(self):
        records = [{"id": "training-only-1", "text": "A local training document", "split": "train"}]
        tokenizer = TextTokenizer.fit(records, 64, 16)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tokenizer.json"
            tokenizer.save(path)
            provenance = {"training_ids": list(tokenizer.training_ids), "requested_vocab": 64,
                          "actual_vocab": tokenizer.vocab_size, "maximum_length": 16,
                          "fit_splits": ["train"], "tokenizer_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (path.parent / "tokenizer_provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
            restored = TextTokenizer.load(path)
            for original, loaded in zip(tokenizer.encode(["An unseen inference input"]),
                                        restored.encode(["An unseen inference input"])):
                self.assertTrue(torch.equal(original, loaded))
            self.assertEqual(restored.training_ids, tokenizer.training_ids)
            path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash"):
                TextTokenizer.load(path)

    def test_missing_saved_tokenizer_or_provenance_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tokenizer.json"
            with self.assertRaises(FileNotFoundError):
                TextTokenizer.load(path)
            (path.parent / "tokenizer_provenance.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                TextTokenizer.load(path)

    def test_spherical_fit_invariant_to_input_record_order(self):
        vectors = torch.randn(40, 32)
        ids = [f"id-{i:02d}" for i in range(40)]
        one, first = spherical_kmeans(vectors, ids, 3, seed=7)
        two, second = spherical_kmeans(vectors.flip(0), ids[::-1], 3, seed=7)
        self.assertTrue(torch.equal(one, two))
        self.assertEqual(first["training_ids"], second["training_ids"])

    def test_actual_gradient_update_changes_connected_backbone_and_head(self):
        self.model.route_mode = "shared"
        optimizer = adamw_optimizer(self.model, lr=0.003)
        backbone = self.model.token_embedding.weight.detach().clone()
        head = self.model.classifier.weight.detach().clone()
        loss, routes = train_update(self.model, optimizer, torch.tensor([[4, 5], [6, 7]]),
                                   torch.ones(2, 2, dtype=torch.bool), torch.tensor([0, 1]))
        self.assertGreater(loss, 0)
        self.assertEqual(routes.tolist(), [0, 0])
        self.assertFalse(torch.equal(backbone, self.model.token_embedding.weight))
        self.assertFalse(torch.equal(head, self.model.classifier.weight))


if __name__ == "__main__":
    unittest.main()
