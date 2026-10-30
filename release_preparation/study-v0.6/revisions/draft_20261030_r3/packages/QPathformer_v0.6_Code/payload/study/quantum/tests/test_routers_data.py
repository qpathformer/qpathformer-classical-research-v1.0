"""Meaningful coordinate/router integrity tests; no model outcome evaluation."""
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np

from routers import (canonical_features, feature_keys, feature_hashes,
                     fit_route_policy, route, _lloyd)
from prepare_data import (DATASETS, generate, labels_for, task_for,
                          _allocate, ROUTER_SOURCE, ROUTER_SOURCE_SHA256,
                          historical_expected_names, validate_registration, validate_generation_approval)


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x = np.random.Generator(np.random.PCG64(721)).uniform(-1, 1, (140, 2))
        cls.policy = fit_route_policy(cls.x, 823)

    def test_original_reviewed_router_bytes_reused(self):
        current = Path(__file__).resolve().parent.parent / "routers.py"
        self.assertEqual(hashlib.sha256(current.read_bytes()).hexdigest(), ROUTER_SOURCE_SHA256)
        self.assertEqual(current.read_bytes(), ROUTER_SOURCE.read_bytes())

    def test_deterministic_training_order_invariance_and_serialization(self):
        other = fit_route_policy(self.x[::-1], 823)
        expected = dict(self.policy)
        expected.pop("training_ordered_features_sha256")
        other.pop("training_ordered_features_sha256")
        self.assertEqual(expected, other)
        policy = json.loads(json.dumps(self.policy))
        for kind in ("hash", "kmeans"):
            np.testing.assert_array_equal(route(self.x, policy, kind), route(self.x, self.policy, kind))

    def test_matched_occupancy_and_exact_hash_boundary_rule(self):
        geometric = np.bincount(route(self.x, self.policy, "kmeans"), minlength=5)
        hashed = np.bincount(route(self.x, self.policy, "hash"), minlength=5)
        np.testing.assert_array_equal(geometric, hashed)
        np.testing.assert_array_equal(geometric, self.policy["kmeans_training_counts"])
        hashes = feature_hashes(self.x, self.policy["hash_salt"])
        for bank, cutoff in enumerate(self.policy["hash_cutpoints_hex"]):
            point = self.x[[hashes.index(cutoff)]]
            self.assertEqual(int(route(point, self.policy, "hash")[0]), bank)

    def test_fixed_heldout_routes_are_batch_independent_and_do_not_refit(self):
        points = np.repeat(self.x[[7]], 19, axis=0)
        before = json.dumps(self.policy, sort_keys=True)
        for kind in ("hash", "kmeans"):
            expected = route(points, self.policy, kind)
            self.assertEqual(len(set(expected)), 1)
            np.testing.assert_array_equal(expected, np.concatenate([route(points[:3], self.policy, kind), route(points[3:], self.policy, kind)]))
            self.assertEqual(route(np.empty((0, 2)), self.policy, kind).shape, (0,))
        self.assertEqual(before, json.dumps(self.policy, sort_keys=True))

    def test_signed_zero_invalid_features_and_no_label_fit_argument(self):
        self.assertEqual(feature_keys([[0., -0.]])[0], feature_keys([[-0., 0.]])[0])
        for value in ([[np.nan, 0]], [[0, np.inf]], [1, 2], [[1, 2, 3]]):
            with self.assertRaises(ValueError):
                canonical_features(value)
        with self.assertRaises(ValueError):
            fit_route_policy(np.repeat(self.x[:1], 20, axis=0), 823)
        with self.assertRaises(TypeError):
            fit_route_policy(self.x, 823, np.zeros(len(self.x)))
        with self.assertRaises(ValueError):
            route(self.x, self.policy, "label")

    def test_geometry_tie_and_empty_cluster_repair(self):
        policy = dict(self.policy)
        policy["centroids"] = [[-1., 0.], [-0.5, 0.], [0., 0.], [0.5, 0.], [1., 0.]]
        np.testing.assert_array_equal(route([[-.75, 0.], [.25, 0.]], policy), [0, 2])
        points = np.column_stack((np.linspace(-1, 1, 51), np.zeros(51)))
        centers, labels, iterations, converged = _lloyd(points, np.zeros((5, 2)))
        self.assertTrue(converged)
        self.assertTrue(np.all(np.bincount(labels, minlength=5) > 0))
        self.assertLessEqual(iterations, 500)
        for bank in range(5):
            np.testing.assert_allclose(centers[bank], points[labels == bank].mean(axis=0), atol=0, rtol=0)


class GenerationTests(unittest.TestCase):
    @staticmethod
    def accepted_order(parts):
        joined = {key: np.concatenate([p[key] for p in parts.values()]) for key in next(iter(parts.values()))}
        order = np.argsort(joined['source_draw_ids'])
        return {key: value[order] for key, value in joined.items()}

    def test_version_specific_historical_inventory_covers_all65_sources(self):
        self.assertEqual([len(historical_expected_names(v)) for v in ('v0.2','v0.3','v0.4','v0.5')], [9,9,21,21])
        self.assertEqual(sum(len(historical_expected_names(v)) for v in ('v0.2','v0.3','v0.4','v0.5'))+5, 65)
        for v in ('v0.4','v0.5'):
            self.assertIn('confirmation_circle_2_SEALED_test.npz', historical_expected_names(v))
            self.assertNotIn('confirmation_annulus_SEALED_test.npz', historical_expected_names(v))
        with self.assertRaises(ValueError):
            historical_expected_names('v0.6')

    def test_root_registered_seeds_geometry_counts_and_runtime_are_bound(self):
        path = Path(__file__).resolve().parents[2] / 'governance/DATA_REGISTRATION.json'
        registration = json.loads(path.read_text(encoding='utf-8'))
        validate_registration(registration)
        mutations = [('study_id','wrong'),('status','draft'),('population_n',7999),
                     ('historical_unique_features',112000),('historical_npz_sources',44),
                     ('new_unique_features',56000),('numpy_version','wrong'),
                     ('router_source_sha256','0'*64),('router_seed_rule','feature_seed+1'),
                     ('seed_roles',['features','record_id_permutation','label_noise','stratified_split'])]
        for key, value in mutations:
            changed=json.loads(json.dumps(registration)); changed[key]=value
            with self.subTest(field=key), self.assertRaises(ValueError):
                validate_registration(changed)
        for mutate in (
            lambda r: r['populations']['engineering_annulus'].__setitem__(3, 1),
            lambda r: r['split_counts'].__setitem__('test',1599),
            lambda r: r['task_semantics']['annulus'].__setitem__('label_noise_probability',0),
            lambda r: r['task_semantics']['disks'].__setitem__('radius',.3),
        ):
            changed=json.loads(json.dumps(registration)); mutate(changed)
            with self.assertRaises(ValueError): validate_registration(changed)

    def test_separate_generation_approval_requires_current_exact_bindings(self):
        source={'prepare_data.py':'a'*64,'routers.py':'b'*64,'tests/test_routers_data.py':'c'*64}
        approval={'status':'approved_by_root','study_id':'QPATH-GENERALIZATION-v0.6',
                  'registration_sha256':'d'*64,'source_sha256':source}
        validate_generation_approval(approval,'d'*64,source)
        for key,value in [('status','draft'),('study_id','wrong'),('registration_sha256','e'*64),('source_sha256',{})]:
            changed=dict(approval); changed[key]=value
            with self.subTest(field=key), self.assertRaises(ValueError):
                validate_generation_approval(changed,'d'*64,source)

    def test_fresh_seed_blocks_all_roles_and_historical_id_ranges(self):
        old=(1430017,1440017,1530017,1540017,1630017,1640017,1650017)
        current=[s[0] for s in DATASETS.values()]
        self.assertEqual(len(DATASETS),12)
        self.assertEqual(len({s for seeds in DATASETS.values() for s in seeds}),48)
        self.assertTrue(set(current).isdisjoint(old))
        for role in ('engineering','development','confirmation'):
            self.assertEqual({task_for(n) for n in DATASETS if n.startswith(role+'_')}, {'checkerboard','spiral','annulus','disks'})
        for a in current:
            for b in old:
                self.assertTrue(a*1000000+7999 < b*1000000 or b*1000000+7999 < a*1000000)

    def test_known_geometries_symmetries_and_strict_boundaries(self):
        np.testing.assert_array_equal(labels_for([[0,0],[.6,0],[.5,0],[1,1]],'annulus'),[0,1,0,0])
        np.testing.assert_array_equal(labels_for([[-.55,-.45],[.5,-.35],[0,.55],[0,0],[1,1]],'disks'),[1,1,1,0,0])
        np.testing.assert_array_equal(labels_for([[0,0],[1/3,0],[2/3,0]],'checkerboard'),[1,0,1])
        self.assertEqual(labels_for([[0,0]],'spiral')[0],0)
        points=np.array([[.13,.21],[-.35,.17],[.28,-.42],[-.61,-.13]])
        rotated=np.column_stack((-points[:,1],points[:,0]))
        np.testing.assert_array_equal(labels_for(points,'spiral'),1-labels_for(rotated,'spiral'))
        for name in ('ellipse','circle','invalid'):
            with self.assertRaises(ValueError): labels_for(points,name)
        with self.assertRaises(ValueError): task_for('confirmation_invalid')

    def test_largest_remainder_tie_and_minority_prevalence(self):
        np.testing.assert_array_equal(_allocate([4001,3999],.6,4800),[2401,2399])
        np.testing.assert_array_equal(_allocate([4001,3999],.2,1600),[800,800])
        np.testing.assert_array_equal(_allocate([1,7999],.6,4800),[1,4799])
        np.testing.assert_array_equal(_allocate([1,7999],.2,1600),[0,1600])
        parts,meta,_=generate((1731,1733,1737,1739),set(),'disks')
        observed=np.asarray(meta['stratum_counts'])
        for split,fraction in [('train',.6),('validation',.2),('test',.2)]:
            counts=np.bincount(parts[split]['y'],minlength=2)
            self.assertLessEqual(np.abs(counts-observed*fraction).max(),1.0)
            self.assertLess(counts[1]/counts.sum(),.2)
        with self.assertRaises(ValueError): _allocate([10,10],.2,10)

    def test_forced_exclusion_same_stream_and_immutable_exclusions(self):
        seeds=(723,727,729,733)
        original=np.random.Generator(np.random.PCG64(seeds[0])).uniform(-1,1,(8001,2))
        excluded={feature_keys(original[:1])[0]}
        parts,meta,keys=generate(seeds,excluded,'annulus')
        self.assertEqual(meta['draws_consumed'],8001)
        self.assertEqual(meta['rejected'][0]['draw_index'],0)
        self.assertEqual(excluded,{feature_keys(original[:1])[0]})
        self.assertTrue(keys.isdisjoint(excluded))
        self.assertEqual(keys,set(feature_keys(original[1:])))
        joined=self.accepted_order(parts)
        np.testing.assert_array_equal(joined['source_draw_ids'],np.arange(1,8001))
        np.testing.assert_array_equal(np.sort(joined['ids']),723000000+np.arange(8000))
        for split,n in [('train',4800),('validation',1600),('test',1600)]:
            self.assertEqual(len(parts[split]['x']),n)
            self.assertEqual(set(parts[split]),{'x','y','clean_y','label_flip','ids','source_draw_ids'})

    def test_annulus_exact_independent_bernoulli_stream_before_observed_stratification(self):
        seeds=(1823,1827,1829,1831)
        parts,meta,_=generate(seeds,set(),'annulus')
        joined=self.accepted_order(parts)
        expected=np.random.Generator(np.random.PCG64(seeds[3])).random(8000)<.1
        np.testing.assert_array_equal(joined['label_flip'],expected)
        np.testing.assert_array_equal(joined['clean_y'],labels_for(joined['x'],'annulus'))
        np.testing.assert_array_equal(joined['y'],joined['clean_y']^expected.astype(np.int64))
        self.assertEqual(meta['realized_flip_count'],int(expected.sum()))
        self.assertEqual(joined['label_flip'].dtype,np.bool_)
        self.assertNotEqual(int(expected.sum()),800) # Fixture demonstrates iid, not fixed-count flips.
        counts=np.bincount(joined['y'],minlength=2)
        np.testing.assert_array_equal(np.bincount(parts['train']['y'],minlength=2),_allocate(counts,.6,4800))
        np.testing.assert_array_equal(np.bincount(parts['validation']['y'],minlength=2),_allocate(counts,.2,1600))

    def test_noise_seed_only_changes_noise_and_observed_membership_not_coordinates_ids_or_latent(self):
        a,_,_=generate((1923,1927,1929,1931),set(),'annulus')
        b,_,_=generate((1923,1927,1929,1933),set(),'annulus')
        aa,bb=self.accepted_order(a),self.accepted_order(b)
        for key in ('x','clean_y','ids','source_draw_ids'):
            np.testing.assert_array_equal(aa[key],bb[key])
        self.assertFalse(np.array_equal(aa['label_flip'],bb['label_flip']))
        self.assertFalse(np.array_equal(aa['y'],bb['y']))

    def test_clean_tasks_no_flips_and_noise_seed_unused(self):
        for family in ('checkerboard','spiral','disks'):
            a,info_a,_=generate((2023,2027,2029,2031),set(),family)
            b,info_b,_=generate((2023,2027,2029,2033),set(),family)
            self.assertEqual(info_a,info_b)
            for split in a:
                self.assertFalse(a[split]['label_flip'].any())
                np.testing.assert_array_equal(a[split]['y'],a[split]['clean_y'])
                for key in a[split]: np.testing.assert_array_equal(a[split][key],b[split][key])

    def test_record_metadata_cannot_change_coordinates_labels_or_split_membership(self):
        a,info_a,keys_a=generate((1723,1727,1729,1731),set(),'annulus')
        b,info_b,keys_b=generate((1723,2701,1729,1731),set(),'annulus')
        self.assertEqual(info_a,info_b); self.assertEqual(keys_a,keys_b)
        for split in a:
            for key in ('x','y','clean_y','label_flip','source_draw_ids'):
                np.testing.assert_array_equal(a[split][key],b[split][key])
            self.assertFalse(np.array_equal(a[split]['ids'],b[split]['ids']))

    def test_new_populations_splits_disjoint_and_ids_unique(self):
        a,_,keys_a=generate((2723,2727,2729,2731),set(),'checkerboard')
        b,_,keys_b=generate((3723,3727,3729,3731),keys_a,'spiral')
        self.assertTrue(keys_a.isdisjoint(keys_b))
        self.assertTrue(set(np.concatenate([p['ids'] for p in a.values()])).isdisjoint(np.concatenate([p['ids'] for p in b.values()])))
        for parts in (a,b):
            ids=np.concatenate([p['source_draw_ids'] for p in parts.values()])
            np.testing.assert_array_equal(np.sort(ids),np.arange(8000))
            keys=[set(feature_keys(p['x'])) for p in parts.values()]
            for i in range(3):
                for j in range(i+1,3): self.assertTrue(keys[i].isdisjoint(keys[j]))


if __name__ == '__main__':
    unittest.main()
