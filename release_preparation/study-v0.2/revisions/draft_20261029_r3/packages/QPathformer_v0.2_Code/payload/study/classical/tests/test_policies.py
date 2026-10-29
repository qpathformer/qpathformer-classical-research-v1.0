"""Contract tests for scheduling, route identity and candidate isolation."""
from copy import deepcopy
import random
import unittest

from qpath.policies import (CandidateTransaction, EpisodeBudget, RATING_NAMES, ReplayBuffer,
                           ReplayRecord, SNAPSHOT_FIELDS, assess_priority, canonical_route_text,
                           class_budget_probabilities, draw_adaptation_sources,
                           learning_rate, stable_text_route)


class PriorityTests(unittest.TestCase):
    def test_complete_and_unknown_are_distinct(self):
        values = dict(zip(RATING_NAMES, (0.8, 0.9, 0.7, 0.6)))
        evidence = {name: f"evidence:{name}" for name in RATING_NAMES}
        assessed = assess_priority(values, evidence)
        self.assertEqual((assessed.score, assessed.processing_class, assessed.provisional), (0.75, 2, False))
        missing = assess_priority(values, {**evidence, RATING_NAMES[0]: None})
        self.assertIsNone(missing.score)
        self.assertEqual((missing.processing_class, missing.provisional), (8, True))
        low = assess_priority({name: 0.0 for name in RATING_NAMES}, evidence)
        self.assertEqual((low.score, low.processing_class, low.provisional), (0.0, 8, False))

    def test_class_budget_is_not_per_record_priority_monotonic(self):
        probs = class_budget_probabilities([1] * 900 + [8] * 100)
        self.assertAlmostEqual(sum(probs), 1.0)
        self.assertGreater(probs[-1], probs[0])
        self.assertAlmostEqual(sum(probs[:900]), 0.45 + 4 / 9)
        self.assertEqual(class_budget_probabilities([8] * 4), [0.25] * 4)
        with self.assertRaises(ValueError):
            class_budget_probabilities([])

    def test_lr_nominal_horizon_and_endpoint(self):
        self.assertAlmostEqual(learning_rate(1, 2000, 200), 0.0003 / 200)
        self.assertAlmostEqual(learning_rate(200, 2000, 200), 0.0003)
        self.assertAlmostEqual(learning_rate(1100, 2000, 200), 0.00015)
        self.assertEqual(learning_rate(2000, 2000, 200), 0.0)
        with self.assertRaises(ValueError):
            learning_rate(2001, 2000, 200)


class StableRoutingTests(unittest.TestCase):
    def test_unicode_case_whitespace_identity(self):
        first = "  Ｓtraße\tNEWS\nWorld "
        second = "strasse news world"
        self.assertEqual(canonical_route_text(first), second)
        for seed in range(25):
            self.assertEqual(stable_text_route(first, seed, [0.0, 0.2, 0.8]),
                             stable_text_route(second, seed, [0.0, 0.2, 0.8]))
            self.assertNotEqual(stable_text_route(first, seed, [0.0, 0.2, 0.8]), 0)

    def test_route_independent_of_record_order_and_new_identity(self):
        texts = ["new incoming text", "another document", "new incoming text"]
        routes = [stable_text_route(text, 101, [0.1, 0.3, 0.6]) for text in texts]
        self.assertEqual(routes[0], routes[2])
        self.assertEqual(routes[::-1], [stable_text_route(text, 101, [0.1, 0.3, 0.6]) for text in texts[::-1]])
        with self.assertRaises(ValueError):
            stable_text_route(" ", 101, [1.0])


class ReplayTests(unittest.TestCase):
    def test_unique_admission_fixed_quotas_and_staged_rejection(self):
        buffer = ReplayBuffer(["z", "a", "m"], capacity=5, seed=17)
        self.assertEqual(buffer.quotas, {"a": 2, "m": 2, "z": 1})
        initial = [ReplayRecord(f"a-{i}", "a") for i in range(10)]
        summary = buffer.admit(initial + [initial[0], ReplayRecord("heldout", "a", "test")])
        self.assertEqual(summary["unique_eligible_considered"], 10)
        self.assertEqual(len(buffer.ids()), 2)  # Other label quotas remain unused.
        self.assertEqual(buffer.seen_counts["a"], 10)
        before = buffer.ids()
        staged, _ = buffer.stage([ReplayRecord("new-z", "z")])
        self.assertEqual(buffer.ids(), before)
        self.assertNotIn("new-z", buffer.seen_ids)
        self.assertIn("new-z", staged.ids())
        snapshot = deepcopy(buffer.rngs["a"].getstate())
        buffer.admit(initial * 3)
        self.assertEqual(buffer.rngs["a"].getstate(), snapshot)
        self.assertEqual(buffer.seen_counts["a"], 10)

    def test_sorted_admission_is_repeatable(self):
        records = [ReplayRecord(str(i), "a") for i in range(50)]
        first, second = ReplayBuffer(["a"], 5, 8), ReplayBuffer(["a"], 5, 8)
        first.admit(records)
        second.admit(records[::-1])
        self.assertEqual(first.ids(), second.ids())

    def test_sources_empty_pool_rules(self):
        self.assertEqual(draw_adaptation_sources(0, 30, 64, random.Random(1)), [])
        self.assertEqual(draw_adaptation_sources(10, 0, 64, random.Random(1)), ["new"] * 64)
        observed = draw_adaptation_sources(10, 10, 10000, random.Random(1)).count("replay")
        self.assertTrue(1800 < observed < 2200)


class SnapshotBudgetTests(unittest.TestCase):
    def test_invalid_charges_cannot_corrupt_the_episode_counter(self):
        budget = EpisodeBudget(resource_cap_seconds=5)
        for value in (float('nan'), float('inf'), 0.5, True, -1):
            with self.subTest(updates=value), self.assertRaises(ValueError):
                budget.charge(updates=value)
        self.assertEqual(budget.updates_consumed, 0)
        budget.charge(updates=1, seconds=0.5)
        self.assertEqual((budget.updates_consumed, budget.seconds_consumed), (1, 0.5))

    def test_nonfinite_or_noninteger_caps_are_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"), 0, -1):
            with self.subTest(seconds=value), self.assertRaises(ValueError):
                EpisodeBudget(resource_cap_seconds=value)
        for value in (float("nan"), float("inf"), 1.5, True):
            with self.subTest(updates=value), self.assertRaises(ValueError):
                EpisodeBudget(max_updates=value, resource_cap_seconds=5)
            with self.subTest(attempts=value), self.assertRaises(ValueError):
                EpisodeBudget(max_attempts=value, resource_cap_seconds=5)

    def test_episode_budget_and_consumed_counters_cannot_enter_snapshot(self):
        base = {key: {} for key in SNAPSHOT_FIELDS}
        budget = EpisodeBudget(resource_cap_seconds=5)
        for extra in ("budget", "episode_counters", "arbitrary_extra"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                CandidateTransaction({**base, extra: budget})
        with self.assertRaises(ValueError):
            CandidateTransaction({**base, "config": {"nested": [budget]}})
        with self.assertRaises(ValueError):
            CandidateTransaction({**base, "scheduler": {"updates_consumed": 20}})
        transaction = CandidateTransaction(base)
        transaction.candidate["scheduler"]["episode_budget"] = budget
        with self.assertRaises(ValueError):
            transaction.accept({"validation_pass": True})
        self.assertEqual(transaction.accepted, base)
        self.assertEqual(transaction.ledger, [])

    def test_rollback_restores_every_state_without_refunding_budget(self):
        accepted = {key: {"value": [1]} for key in SNAPSHOT_FIELDS}
        transaction = CandidateTransaction(accepted)
        budget = EpisodeBudget(max_updates=10, max_attempts=3, resource_cap_seconds=5)
        self.assertEqual(budget.start_attempt(), 1)
        budget.charge(updates=6, seconds=2)
        for value in transaction.candidate.values():
            value["value"][0] = 99
        transaction.reject({"failed_validation": True})
        self.assertEqual(transaction.accepted, accepted)
        self.assertEqual(transaction.candidate, accepted)
        self.assertEqual((budget.updates_consumed, budget.seconds_consumed), (6, 2))
        self.assertEqual(budget.start_attempt(), 2)
        with self.assertRaises(RuntimeError):
            budget.charge(updates=5)
        budget.charge(updates=4, seconds=4)
        self.assertFalse(budget.checkpoint_eligible)
        with self.assertRaises(RuntimeError):
            budget.start_attempt()
        self.assertEqual(transaction.ledger[0]["decision"], "reject")

    def test_accept_does_not_alias_mutable_candidate(self):
        transaction = CandidateTransaction({key: [1] for key in SNAPSHOT_FIELDS})
        transaction.candidate["replay"].append(2)
        transaction.accept({"validation_pass": True})
        transaction.candidate["replay"].append(3)
        self.assertEqual(transaction.accepted["replay"], [1, 2])


if __name__ == "__main__":
    unittest.main()
