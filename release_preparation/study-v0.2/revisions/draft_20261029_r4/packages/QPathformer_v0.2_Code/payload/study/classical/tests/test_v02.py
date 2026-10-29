"""Focused numerical/routing/checkpoint invariants for the v0.2 change."""
from copy import deepcopy
from dataclasses import replace
import tempfile
from pathlib import Path
import unittest
import numpy as np
import torch
from qpath.classical import ModelConfig, QPathTextModel, FrozenRoutingEncoder, adamw_optimizer, train_update
from qpath.policies import stable_text_route


class RoutingTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(4)
        torch.manual_seed(123)
        self.config = replace(ModelConfig.smoke(), dropout=0.0, labels=14)

    def test_grouped_forward_and_gradients_match_loop_with_nonzero_adapters(self):
        a = QPathTextModel(self.config).double()
        with torch.no_grad():
            for adapter in a.adapters:
                adapter.up.weight.normal_(0, 0.1)
        b = deepcopy(a)
        a.dispatch_mode = "loop"
        b.dispatch_mode = "grouped"
        x = torch.randn(21, 32, dtype=torch.double, requires_grad=True)
        y = x.detach().clone().requires_grad_()
        routes = torch.tensor([0, 3, 3, 9, 17, 2, 2] * 3)
        left, right = a.apply_adapters(x, routes), b.apply_adapters(y, routes)
        torch.testing.assert_close(left, right, rtol=1e-12, atol=1e-12)
        weights = torch.randn_like(left)
        (left * weights).sum().backward()
        (right * weights).sum().backward()
        torch.testing.assert_close(x.grad, y.grad, rtol=1e-11, atol=1e-12)
        for pa, pb in zip(a.adapters.parameters(), b.adapters.parameters()):
            if pa.grad is None:
                self.assertIsNone(pb.grad)
            else:
                torch.testing.assert_close(pa.grad, pb.grad, rtol=1e-11, atol=1e-12)

    def test_grouped_inactive_adamw_weights_and_moments_stay_unchanged(self):
        model = QPathTextModel(self.config)
        opt = adamw_optimizer(model)
        raw = torch.randn(8, 32)
        # Populate adapter7 moments first, then train only adapter2.
        for route in [7, 2]:
            opt.zero_grad(set_to_none=True)
            model.apply_adapters(raw, torch.full((8,), route)).square().mean().backward()
            opt.step()
        before = {n: p.detach().clone() for n, p in model.adapters[7].named_parameters()}
        states = {n: deepcopy(opt.state[p]) for n, p in model.adapters[7].named_parameters()}
        opt.zero_grad(set_to_none=True)
        model.apply_adapters(raw, torch.full((8,), 2)).sum().backward()
        opt.step()
        for name, parameter in model.adapters[7].named_parameters():
            self.assertIsNone(parameter.grad)
            self.assertTrue(torch.equal(parameter, before[name]))
            for key, value in states[name].items():
                self.assertTrue(torch.equal(opt.state[parameter][key], value))

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA dispatch numerical check")
    def test_full_width_cuda_float32_dispatch_gradient_equivalence(self):
        import engine as E
        E.configure(71)
        config = replace(ModelConfig(), layers=1, labels=14)
        a = QPathTextModel(config).cuda()
        with torch.no_grad():
            for adapter in a.adapters:
                adapter.up.weight.normal_(0, 0.1)
        b = deepcopy(a)
        a.dispatch_mode, b.dispatch_mode = "loop", "grouped"
        x = torch.randn(64, 256, device="cuda", requires_grad=True)
        y = x.detach().clone().requires_grad_()
        routes = torch.arange(64, device="cuda") % 18
        left, right = a.apply_adapters(x, routes), b.apply_adapters(y, routes)
        torch.testing.assert_close(left, right, rtol=1e-5, atol=2e-6)
        weights = torch.randn_like(left)
        (left * weights).mean().backward()
        (right * weights).mean().backward()
        torch.testing.assert_close(x.grad, y.grad, rtol=2e-5, atol=2e-7)
        for pa, pb in zip(a.adapters.parameters(), b.adapters.parameters()):
            torch.testing.assert_close(pa.grad, pb.grad, rtol=2e-5, atol=2e-7)

    def test_frozen_router_remains_eval_immutable_and_cache_matches_uncached(self):
        model = QPathTextModel(replace(self.config, dropout=0.4))
        model.set_centroids(torch.nn.functional.normalize(torch.randn(18, 32), dim=1), ["train-only"])
        model.frozen_router = FrozenRoutingEncoder(model)
        model.route_mode = "frozen_content"
        tokens = torch.randint(4, 128, (8, 12))
        mask = torch.ones_like(tokens, dtype=torch.bool)
        routes = model.frozen_router(tokens, mask)
        snapshot = deepcopy(model.frozen_router.state_dict())
        optimizer = adamw_optimizer(model)
        train_update(model, optimizer, tokens, mask, torch.arange(8), routing_features=routes)
        self.assertFalse(model.frozen_router.training)
        for name, value in snapshot.items():
            self.assertTrue(torch.equal(model.frozen_router.state_dict()[name], value))
        self.assertTrue(torch.equal(model.frozen_router(tokens, mask), routes))
        self.assertTrue(all(p.grad is None and not p.requires_grad for p in model.frozen_router.parameters()))
        model.eval()
        uncached = model(tokens, mask)
        cached = model(tokens, mask, routing_features=routes)
        torch.testing.assert_close(uncached["logits"], cached["logits"], rtol=0, atol=0)

    def test_hash_routes_use_canonical_text_not_labels_or_ids(self):
        variants = ["Alpha  BETA\nnews", "alpha beta news", "  ALPHA beta NEWS  "]
        expected = stable_text_route(variants[0], 60301, [1 / 18] * 18)
        self.assertEqual([stable_text_route(v, 60301, [1 / 18] * 18) for v in variants], [expected] * 3)
        model = QPathTextModel(self.config)
        model.route_mode, model.route_seed = "hash18", 60301
        tokens = torch.randint(4, 128, (3, 9))
        output = model(tokens, torch.ones_like(tokens, dtype=torch.bool), texts=variants)
        self.assertEqual(output["routes"].tolist(), [expected] * 3)
        with self.assertRaises(TypeError):
            model(tokens, torch.ones_like(tokens, dtype=torch.bool), labels=[1, 2, 3])

    def test_crash_after_ledger_append_preserves_tail_and_restores_committed_prefix(self):
        import engine as E
        import json
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            rows = [{"phase_update": 100}, {"phase_update": 200}]
            (folder / "ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            (folder / "checkpoint_00200.pt").write_bytes(b"uncommitted checkpoint fixture")
            (folder / "checkpoint_00300.tmp.pt").write_bytes(b"partial interrupted save fixture")
            (folder / "validation_00200.npz").write_bytes(b"uncommitted validation fixture")
            E.reconcile_uncommitted_artifacts(folder, 100)
            self.assertEqual([json.loads(x)["phase_update"] for x in (folder / "ledger.jsonl").read_text().splitlines()], [100])
            archive = next(folder.glob("uncommitted_resume_*"))
            self.assertEqual(json.loads((archive / "ledger_tail.jsonl").read_text())["phase_update"], 200)
            self.assertTrue((archive / "checkpoint_00200.pt").exists())
            self.assertTrue((archive / "checkpoint_00300.tmp.pt").exists())
            self.assertTrue((archive / "validation_00200.npz").exists())
            E.append_json(folder / "ledger.jsonl", {"phase_update": 200, "attempt": "resumed"})
            self.assertEqual(len((folder / "ledger.jsonl").read_text().splitlines()), 2)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA checkpoint test")
    def test_frozen_checkpoint_next_update_matches_after_optimizer_rng_restore(self):
        import engine as E
        old_data = E.DATA
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            E.DATA = folder
            (folder / "tokenizer.json").write_text("fixture tokenizer")
            (folder / "manifest.json").write_text("fixture manifest")
            try:
                E.configure(876)
                model = QPathTextModel(replace(self.config, dropout=0.1)).cuda()
                model.set_centroids(torch.nn.functional.normalize(torch.randn(18, 32, device="cuda"), dim=1), ["fixture"])
                model.frozen_router = FrozenRoutingEncoder(model)
                model.route_mode = "frozen_content"
                optimizer = adamw_optimizer(model)
                rng = np.random.default_rng(876)
                tokens = torch.randint(4, 128, (8, 12), device="cuda")
                mask = torch.ones_like(tokens, dtype=torch.bool)
                labels = torch.arange(8, device="cuda")
                routes = model.frozen_router(tokens, mask)
                train_update(model, optimizer, tokens, mask, labels, routing_features=routes)
                path = folder / "checkpoint.pt"
                E.save_checkpoint(path, E.checkpoint_state(model, optimizer, rng, {"phase_update": 1}))
                loss, _ = train_update(model, optimizer, tokens, mask, labels, routing_features=routes)
                restored = E.model_from_checkpoint(path)
                restored_optimizer = adamw_optimizer(restored)
                E.restore_checkpoint(path, restored, restored_optimizer, np.random.default_rng(2))
                restored_loss, _ = train_update(restored, restored_optimizer, tokens, mask, labels, routing_features=routes)
                self.assertEqual(loss, restored_loss)
                for a, b in zip(model.state_dict().values(), restored.state_dict().values()):
                    self.assertTrue(torch.equal(a, b))
            finally:
                E.DATA = old_data

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA phase integration")
    def test_real_phase_loop_saves_and_commits_complete_fixture_endpoint(self):
        import contextlib
        import io
        import json
        import engine as E
        import study as S
        old_data, old_results = E.DATA, E.RESULTS
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            E.DATA, E.RESULTS = folder / "data", folder / "results"
            E.DATA.mkdir()
            E.RESULTS.mkdir()
            (E.DATA / "tokenizer.json").write_text("fixture tokenizer")
            (E.DATA / "manifest.json").write_text(json.dumps({"preparation_seconds": 0}))
            try:
                E.configure(877)
                model = QPathTextModel(self.config).cuda()
                model.route_mode = "shared"
                tokens = torch.randint(4, 128, (20, 12))
                data = {"tokens": tokens, "mask": torch.ones_like(tokens, dtype=torch.bool),
                        "labels": torch.arange(20) % 14, "record_ids": np.array([str(i) for i in range(20)])}
                protocol = {"stage": "engineering_fixture", "schedules": {"warmup_updates": 2, "warmup_ramp": 1,
                            "main_updates": 2, "main_ramp": 1, "evaluation_interval": 1},
                            "resource_cap_seconds_per_method": 60}
                phase_folder = E.RESULTS / "seed_877" / "common_warmup"
                phase_folder.mkdir(parents=True)
                E.write_json(phase_folder / "status.json", {"status": "running", "phase_update": 1,
                             "elapsed_seconds": 2.5, "method_preparation_seconds": 0.1, "protocol_sha256": "fixture-protocol"})
                E.append_json(phase_folder / "ledger.jsonl", {"phase_update": 1, "uncommitted": True})
                (phase_folder / "checkpoint_00001.tmp.pt").write_bytes(b"interrupted first save")
                with contextlib.redirect_stdout(io.StringIO()):
                    state = S.run_phase(877, "common_warmup", model, data, data, data, {}, protocol, "fixture-protocol")
                self.assertEqual(state["status"], "completed")
                self.assertEqual(state["latest_eligible_update"], 2)
                self.assertEqual(state["resumed_segments"], 1)
                self.assertGreaterEqual(state["elapsed_seconds"], 2.5)
                self.assertEqual(state["method_preparation_seconds"], 0.1)
                self.assertTrue(list(phase_folder.glob("uncommitted_resume_*")))
                committed = json.loads((phase_folder / "checkpoint_commit.json").read_text())
                self.assertEqual(committed["state"]["phase_update"], 2)
                self.assertEqual(committed["sha256"], E.digest(E.RESULTS / state["latest_eligible_checkpoint"]))
                self.assertEqual(len((phase_folder / "ledger.jsonl").read_text().splitlines()), 2)
            finally:
                E.DATA, E.RESULTS = old_data, old_results


if __name__ == "__main__":
    unittest.main()
