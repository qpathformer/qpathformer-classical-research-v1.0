"""Synthetic-only v0.7 coordinate/router and authority-boundary tests."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest import mock
import numpy as np
import prepare_data as d
import routers as r


def make_stream(namespace):
    return {"namespace": namespace,
            "uint128_decimal": str(int.from_bytes(hashlib.sha256(namespace.encode("ascii")).digest()[:16], "little"))}


def fixture_population(family="annulus", tag="fixture_a"):
    roles = ("coordinates", "annulus_noise", "split", "record_ids",
             "kmeans_initialization", "hash_salt", "boundary_diagnostic", "shot_fixture", "deployment_order")
    return {"population_id": "TEST_ONLY_"+tag, "family": family,
            "proposed_streams": {role: make_stream("qpath-v07-unit-fixture/"+tag+"/"+role) for role in roles}}


def accepted_order(parts, latent):
    joined = {}
    for key in next(iter(parts.values())):
        joined[key] = np.concatenate([parts[s][key] for s in ("train", "validation", "test")])
    for key in ("clean_y", "label_flip"):
        joined[key] = np.concatenate([latent[s][key] for s in ("train", "validation", "test")])
    order = np.argsort(joined["source_draw_ids"])
    return {key: value[order] for key, value in joined.items()}


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x = np.random.Generator(np.random.PCG64(71011)).uniform(-1, 1, (180, 2))
        cls.policy = r.fit_route_policy(cls.x, 2**120+31, "unit-fixture-salt")

    def test_kmeans_source_semantics_exactly_inherited(self):
        old = ast.parse(d.OLD_ROUTER.read_text(encoding="utf-8"))
        new = ast.parse(Path(r.__file__).read_text(encoding="utf-8"))
        oldf = {n.name: n for n in old.body if isinstance(n, ast.FunctionDef)}
        newf = {n.name: n for n in new.body if isinstance(n, ast.FunctionDef)}
        for name in ("canonical_features", "feature_keys", "_distance", "_canonical_order", "_initial_centers", "_lloyd"):
            self.assertEqual(ast.dump(oldf[name], include_attributes=False), ast.dump(newf[name], include_attributes=False))
        self.assertEqual(d.digest(d.OLD_ROUTER), d.OLD_ROUTER_SHA)
        self.assertEqual((r.K, r.RESTARTS, r.MAX_ITER), (5, 20, 500))

    def test_order_invariance_and_serialization(self):
        other = r.fit_route_policy(self.x[::-1], 2**120+31, "unit-fixture-salt")
        a = dict(self.policy); b = dict(other)
        a.pop("training_ordered_features_sha256"); b.pop("training_ordered_features_sha256")
        self.assertEqual(a, b)
        restored = json.loads(json.dumps(self.policy))
        for kind in ("kmeans", "hash"):
            np.testing.assert_array_equal(r.route(self.x, restored, kind), r.route(self.x, self.policy, kind))

    def test_exact_training_occupancy_and_inclusive_hash_cuts(self):
        counts = np.bincount(r.route(self.x, self.policy, "kmeans"), minlength=5)
        np.testing.assert_array_equal(np.bincount(r.route(self.x, self.policy, "hash"), minlength=5), counts)
        hashes = r.feature_hashes(self.x, self.policy["hash_salt"])
        for i, cut in enumerate(self.policy["hash_cutpoints_hex"]):
            point = self.x[[hashes.index(cut)]]
            self.assertEqual(int(r.route(point, self.policy, "hash")[0]), i)

    def test_batch_invariance_and_immutable_heldout_policy(self):
        points = np.repeat(self.x[[9]], 19, axis=0)
        before = json.dumps(self.policy, sort_keys=True)
        for kind in ("hash", "kmeans"):
            np.testing.assert_array_equal(r.route(points, self.policy, kind),
                                          np.concatenate([r.route(points[:3], self.policy, kind),
                                                          r.route(points[3:], self.policy, kind)]))
            self.assertEqual(len(set(r.route(points, self.policy, kind))), 1)
            self.assertEqual(r.route(np.empty((0, 2)), self.policy, kind).shape, (0,))
        self.assertEqual(before, json.dumps(self.policy, sort_keys=True))

    def test_geometry_ties_and_empty_cluster_repair(self):
        policy = dict(self.policy)
        policy["centroids"] = [[-1., 0.], [-.5, 0.], [0., 0.], [.5, 0.], [1., 0.]]
        np.testing.assert_array_equal(r.route([[-.75, 0.], [.25, 0.]], policy), [0, 2])
        points = np.column_stack((np.linspace(-1, 1, 51), np.zeros(51)))
        centers, labels, iterations, converged = r._lloyd(points, np.zeros((5, 2)))
        self.assertTrue(converged)
        self.assertLessEqual(iterations, 500)
        self.assertTrue(np.all(np.bincount(labels, minlength=5) > 0))
        for bank in range(5):
            np.testing.assert_array_equal(centers[bank], points[labels == bank].mean(axis=0))

    def test_signed_zero_invalid_features_and_duplicate_fit_inputs(self):
        self.assertEqual(r.feature_keys([[0., -0.]])[0], r.feature_keys([[-0., 0.]])[0])
        for x in ([[np.nan, 0]], [[0, np.inf]], [1, 2], [[1, 2, 3]]):
            with self.assertRaises(ValueError):
                r.canonical_features(x)
        with self.assertRaises(ValueError):
            r.fit_route_policy(np.repeat(self.x[:1], 20, axis=0), 823, "fixture")
        with self.assertRaises(TypeError):
            r.fit_route_policy(self.x, 823, "fixture", np.zeros(len(self.x)))

    def test_hash_salt_is_explicit_independent_and_collision_aborts(self):
        with self.assertRaises(TypeError):
            r.fit_route_policy(self.x, 823)
        for salt in ("", "\u00e9", None):
            with self.assertRaises(ValueError):
                r.feature_hashes(self.x, salt)
        other = r.fit_route_policy(self.x, 2**120+31, "other-fixture-salt")
        np.testing.assert_array_equal(other["centroids"], self.policy["centroids"])
        self.assertNotEqual(other["hash_cutpoints_hex"], self.policy["hash_cutpoints_hex"])
        with mock.patch.object(r, "feature_hashes", return_value=["0"*64]*len(self.x)):
            with self.assertRaisesRegex(RuntimeError, "collision"):
                r.fit_route_policy(self.x, 823, "fixture")

    def test_margin_training_quantiles_and_batch_invariance(self):
        bins = r.fit_margin_bins(self.x, self.policy)
        margin = r.geometric_margin(self.x, self.policy)
        expected = np.quantile(margin, [0., .1, .25, .5, 1.], method="linear")
        np.testing.assert_array_equal(bins["raw_edges"], expected)
        a = r.margin_bins(self.x, self.policy, bins)
        b = np.concatenate([r.margin_bins(self.x[:70], self.policy, bins),
                            r.margin_bins(self.x[70:], self.policy, bins)])
        np.testing.assert_array_equal(a, b)
        self.assertEqual(bins["bins"], 4)
        self.assertEqual(set(a), {0, 1, 2, 3})
        collapsed = r.fit_margin_bins(np.repeat(self.x[:1], 10, axis=0), self.policy)
        self.assertEqual(collapsed["bins"], 1)
        np.testing.assert_array_equal(r.margin_bins(self.x, self.policy, collapsed), np.zeros(len(self.x), dtype=np.int64))
        changed = copy.deepcopy(bins); changed["unique_edges"][1] = changed["unique_edges"][0]
        with self.assertRaises(ValueError):
            r.margin_bins(self.x, self.policy, changed)


class GenerationTests(unittest.TestCase):
    counts = {"train": 120, "validation": 40, "test": 40}

    def test_exact_formula_boundaries(self):
        np.testing.assert_array_equal(d.labels_for([[0, 0], [.6, 0], [.5, 0], [1, 1]], "annulus"), [0, 1, 0, 0])
        np.testing.assert_array_equal(d.labels_for([[-.55, -.45], [.5, -.35], [0, .55], [0, 0]], "disks"), [1, 1, 1, 0])
        np.testing.assert_array_equal(d.labels_for([[0, 0], [1/3, 0], [2/3, 0]], "checkerboard"), [1, 0, 1])
        self.assertEqual(d.labels_for([[0, 0]], "spiral")[0], 0)
        with self.assertRaises(ValueError):
            d.labels_for([[0, 0]], "invalid")

    def test_largest_remainder(self):
        np.testing.assert_array_equal(d._allocate([4001, 3999], .6, 4800), [2401, 2399])
        np.testing.assert_array_equal(d._allocate([4001, 3999], .2, 1600), [800, 800])
        with self.assertRaises(ValueError):
            d._allocate([10, 10], .2, 10)

    def test_stream_derivation_checked(self):
        good = make_stream("test-only-value")
        self.assertGreater(d.stream_value(good), 0)
        changed = dict(good); changed["uint128_decimal"] = "1"
        with self.assertRaises(ValueError):
            d.stream_value(changed)

    def test_annulus_noise_is_independent_and_separate_from_training(self):
        pop = fixture_population()
        parts, latent, meta, keys = d.generate(pop, set(), 7000000000000000000, n=200, counts=self.counts)
        joined = accepted_order(parts, latent)
        expected = np.random.Generator(np.random.PCG64(d.stream_value(pop["proposed_streams"]["annulus_noise"]))).random(200) < .1
        np.testing.assert_array_equal(joined["label_flip"], expected)
        np.testing.assert_array_equal(joined["clean_y"], d.labels_for(joined["x"], "annulus"))
        np.testing.assert_array_equal(joined["y"], joined["clean_y"] ^ expected.astype(np.int64))
        for split, part in parts.items():
            self.assertEqual(set(part), {"x", "y", "ids", "source_draw_ids"})
            self.assertEqual(set(latent[split]), {"ids", "clean_y", "label_flip"})
            np.testing.assert_array_equal(part["ids"], latent[split]["ids"])
            self.assertEqual(len(part["x"]), self.counts[split])
        self.assertEqual(len(keys), 200)
        self.assertEqual(meta["accepted"], 200)

    def test_noise_changes_labels_not_coordinates_record_ids_or_clean_target(self):
        a = fixture_population()
        b = copy.deepcopy(a)
        b["proposed_streams"]["annulus_noise"] = make_stream("independent-noise-fixture")
        pa, la, _, _ = d.generate(a, set(), 7000000000000000000, n=200, counts=self.counts)
        pb, lb, _, _ = d.generate(b, set(), 7000000000000000000, n=200, counts=self.counts)
        aa, bb = accepted_order(pa, la), accepted_order(pb, lb)
        for key in ("x", "ids", "clean_y", "source_draw_ids"):
            np.testing.assert_array_equal(aa[key], bb[key])
        self.assertFalse(np.array_equal(aa["label_flip"], bb["label_flip"]))

    def test_record_metadata_does_not_change_membership_or_labels(self):
        a = fixture_population()
        b = copy.deepcopy(a)
        b["proposed_streams"]["record_ids"] = make_stream("independent-record-id-fixture")
        pa, la, ma, ka = d.generate(a, set(), 7000000000000000000, n=200, counts=self.counts)
        pb, lb, mb, kb = d.generate(b, set(), 7000000000000000000, n=200, counts=self.counts)
        self.assertEqual(ma, mb); self.assertEqual(ka, kb)
        for split in pa:
            for key in ("x", "y", "source_draw_ids"):
                np.testing.assert_array_equal(pa[split][key], pb[split][key])
            self.assertFalse(np.array_equal(pa[split]["ids"], pb[split]["ids"]))

    def test_forced_duplicate_exclusion_keeps_same_stream_and_caller_set(self):
        pop = fixture_population()
        seed = d.stream_value(pop["proposed_streams"]["coordinates"])
        original = np.random.Generator(np.random.PCG64(seed)).uniform(-1, 1, (201, 2))
        excluded = {r.feature_keys(original[:1])[0]}
        parts, latent, meta, keys = d.generate(pop, excluded, 7000000000000000000, n=200, counts=self.counts)
        self.assertEqual(meta["draws_consumed"], 201)
        self.assertEqual(meta["rejected"][0]["draw_index"], 0)
        self.assertEqual(excluded, {r.feature_keys(original[:1])[0]})
        self.assertTrue(keys.isdisjoint(excluded))
        self.assertEqual(keys, set(r.feature_keys(original[1:])))
        np.testing.assert_array_equal(accepted_order(parts, latent)["source_draw_ids"], np.arange(1, 201))

    def test_new_populations_and_splits_are_disjoint(self):
        a = fixture_population("checkerboard", "a")
        b = fixture_population("spiral", "b")
        pa, _, _, ka = d.generate(a, set(), 7000000000000000000, n=200, counts=self.counts)
        pb, _, _, kb = d.generate(b, ka, 7000000000001000000, n=200, counts=self.counts)
        self.assertTrue(ka.isdisjoint(kb))
        ids_a = set(np.concatenate([p["ids"] for p in pa.values()]))
        ids_b = set(np.concatenate([p["ids"] for p in pb.values()]))
        self.assertTrue(ids_a.isdisjoint(ids_b))
        for parts in (pa, pb):
            sets = [set(r.feature_keys(p["x"])) for p in parts.values()]
            self.assertEqual(len(set.union(*sets)), 200)
            self.assertEqual(sum(map(len, sets)), 200)

    def test_clean_families_do_not_consume_noise_targets(self):
        for family in ("checkerboard", "spiral", "disks"):
            pop = fixture_population(family)
            parts, latent, _, _ = d.generate(pop, set(), 7000000000000000000, n=200, counts=self.counts)
            for split in parts:
                self.assertFalse(latent[split]["label_flip"].any())
                np.testing.assert_array_equal(parts[split]["y"], latent[split]["clean_y"])

    def test_root_generation_approval_hash_binding(self):
        sources = {"prepare_data.py": "a"*64, "routers.py": "b"*64}
        active = {"STUDY_PLAN.json": "c"*64, "RUN_MATRIX.json": "d"*64}
        approval = {"status": "approved_by_root", "registration_sha256": "e"*64,
                    "source_sha256": sources, "active_input_sha256": active,
                    "freshness_preflight_sha256": "f"*64}
        with mock.patch.object(d, "digest", return_value="f"*64):
            d.validate_generation_approval(approval, "e"*64, active, sources)
            for key, bad in (("status", "draft"), ("registration_sha256", "x"*64),
                             ("source_sha256", {}), ("active_input_sha256", {}),
                             ("freshness_preflight_sha256", "x"*64)):
                changed = copy.deepcopy(approval); changed[key] = bad
                with self.subTest(field=key), self.assertRaises(ValueError):
                    d.validate_generation_approval(changed, "e"*64, active, sources)
            unreadable = [{"path": "fixture/last_checkpoint.npz", "sha256": "1"*64}]
            with self.assertRaises(ValueError):
                d.validate_generation_approval(approval, "e"*64, active, sources, unreadable)
            wrong = copy.deepcopy(approval); wrong["historical_nondata_stub_hashes"] = ["2"*64]
            with self.assertRaises(ValueError):
                d.validate_generation_approval(wrong, "e"*64, active, sources, unreadable)
            accepted = copy.deepcopy(approval); accepted["historical_nondata_stub_hashes"] = ["1"*64]
            d.validate_generation_approval(accepted, "e"*64, active, sources, unreadable)

    def test_historical_rescan_must_bind_exact_reviewed_stub_inventory(self):
        historical = {"coordinate_sources": [{"path": "data.npz", "sha256": "a"}],
                      "seed_sources": [{"path": "protocol.json", "sha256": "b"}],
                      "unreadable_npz": [{"path": "fixture/last_checkpoint.npz", "sha256": "c"}]}
        previous = copy.deepcopy(historical)
        registration = {"historical_unique_observed": 294400,
                        "unreadable_historical_npz": copy.deepcopy(historical["unreadable_npz"])}
        d.validate_historical_rescan(historical, previous, registration, 294400)
        for changed_key in historical:
            changed = copy.deepcopy(historical)
            changed[changed_key].append({"path": "unexpected.npz", "sha256": "d"})
            with self.subTest(field=changed_key), self.assertRaises(ValueError):
                d.validate_historical_rescan(changed, previous, registration, 294400)
        altered_registration = copy.deepcopy(registration)
        altered_registration["unreadable_historical_npz"][0]["sha256"] = "unknown"
        with self.assertRaises(ValueError):
            d.validate_historical_rescan(historical, previous, altered_registration, 294400)
        with self.assertRaises(ValueError):
            d.validate_historical_rescan(historical, previous, registration, 294399)

    def test_declared_seed_parser_does_not_collect_outcome_numbers(self):
        values = d.declared_seeds({"seeds": [1, 2], "macro_f1": .8, "n": 600,
                                  "data": {"coordinate_seed": 7}, "seed_note": "abc"})
        self.assertEqual({v for _, v in values}, {1, 2, 7})


if __name__ == "__main__":
    unittest.main()
