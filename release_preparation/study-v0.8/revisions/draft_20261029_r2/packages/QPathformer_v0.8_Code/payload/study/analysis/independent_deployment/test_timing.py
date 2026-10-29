"""Synthetic values and public protocol metadata only; no official outcomes/timings."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import audit_timing as audit
import statistics_timing as stats


class IndependentTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads((audit.ROOT/"governance/RUN_MATRIX.json").read_text(encoding="utf-8"))
        cls.jobs = [j for j in cls.matrix["runs"] if j["stage"] == "B"]
        cls.populations = [p for p in cls.matrix["populations"] if p["stage"] == "B"]
        cls.order = stats.ordered_jobs(cls.jobs, cls.populations)

    def test_actual_metadata_complete_coverage_and_order(self):
        self.assertEqual((len(self.jobs), len(self.populations)), (640, 32))
        for session in (1, 2, 3):
            rows = list(stats.expected_trials(self.order, session))
            self.assertEqual(len(rows), 40320)
            keys = {(r[1], r[2], r[3]) for r in rows}
            self.assertEqual(len(keys), 2688)
            self.assertEqual(len(keys)*2, 5376)
            self.assertEqual(len({r[1] for r in rows if r[2] == "converted"}), 256)
        self.assertEqual([j["run_id"] for j in self.order],
                         [j["run_id"] for j in stats.ordered_jobs(self.jobs[::-1], self.populations[::-1])])

    def test_pair_alternation(self):
        job = {"run_id": "synthetic", "arm": "MultiK_U"}
        first = list(stats.expected_trials([job], 1))
        second = list(stats.expected_trials([job], 2))
        self.assertEqual([r[2] for r in first[:4]], ["converted", "original", "original", "converted"])
        self.assertEqual([r[2] for r in second[:4]], ["original", "converted", "converted", "original"])

    def test_linear_quantiles_and_drift(self):
        record = stats.condition_statistics(list(range(1, 16)))
        self.assertEqual(record["median_ns"], 8)
        self.assertAlmostEqual(record["p10_ns"], 2.4)
        self.assertAlmostEqual(record["p90_ns"], 13.6)
        self.assertEqual((record["first5_median_ns"], record["last5_median_ns"]), (3, 13))
        with self.assertRaises(RuntimeError):
            stats.condition_statistics(list(range(15)))

    def test_matched_metrics_and_construction_scope(self):
        record = stats.matched_statistics([30]*15, [10]*15, 100)
        self.assertEqual(record["median_original_over_converted_trial_ratio"], 3)
        self.assertEqual(record["ratio_of_median_latencies"], 3)
        self.assertEqual(record["median_matched_per_call_saving_ns"], 20)
        self.assertEqual(record["construction_only_break_even_calls"], 5)
        self.assertIsNone(stats.matched_statistics([10]*15, [20]*15, 100)["construction_only_break_even_calls"])
        self.assertIsNone(stats.matched_statistics([10]*15, [10]*15, 100)["construction_only_break_even_calls"])

    def synthetic_rows(self):
        jobs = [{"run_id": "synthetic", "arm": "MultiK_U"}]
        rows = [{"sequence": str(a), "job_id": b, "representation": c, "batch_size": str(d),
                 "trial": str(e), "elapsed_ns": str(100+a), "probability_sum": str(d/2),
                 "logit_sum": "0", "measured_utc": "2026-01-01T00:00:01+00:00"}
                for a, b, c, d, e in stats.expected_trials(jobs, 1)]
        return jobs, rows

    def test_synthetic_raw_csv_inventory(self):
        jobs, rows = self.synthetic_rows()
        values = audit.validate_csv_rows(rows, jobs, 1, audit.timestamp("2026-01-01T00:00:00+00:00"),
                                         audit.timestamp("2026-01-01T00:00:02+00:00"))
        self.assertEqual(len(values), 6)
        self.assertTrue(all(len(v) == 15 for v in values.values()))

    def test_synthetic_raw_reject_corruption(self):
        jobs, original = self.synthetic_rows()
        for mutate in (lambda r: r.pop(), lambda r: r[0].update(trial="14"),
                       lambda r: r[0].update(representation="original"),
                       lambda r: r[0].update(elapsed_ns="0"),
                       lambda r: r[0].update(probability_sum="NaN"),
                       lambda r: r[0].update(measured_utc="2025-01-01T00:00:01+00:00")):
            rows = deepcopy(original)
            mutate(rows)
            with self.assertRaises(RuntimeError):
                audit.validate_csv_rows(rows, jobs, 1, audit.timestamp("2026-01-01T00:00:00+00:00"),
                                         audit.timestamp("2026-01-01T00:00:02+00:00"))

    def test_duplicate_summary_rejected(self):
        with self.assertRaises(RuntimeError):
            audit.index_records([{"id": 1}, {"id": 1}], ("id",))

    def test_allthree_root_binding_gate(self):
        release = {"schema": "qpath-v08-independent-timing-release-1", "review_status": "approved_by_root",
                   "phase": "timing_evidence", "max_parallel_tasks": 1, "required_blas_threads": 1,
                   "timing_evidence_access_authorized": True, "output": str(audit.HERE/"synthetic_unused"),
                   "session_commits": [{"sha256": str(n)} for n in (1, 2, 3)]}
        audit.validate_header(release, release["output"])
        for mutation in ({"session_commits": release["session_commits"][:2]},
                         {"session_commits": [release["session_commits"][0]]*3},
                         {"review_status": "unapproved"}, {"required_blas_threads": 2}):
            with self.assertRaises(RuntimeError):
                audit.validate_header({**release, **mutation}, release["output"])

    def test_population_summaries_do_not_inflate_n(self):
        sessions = []
        for session in (1, 2, 3):
            condition_values, matched = {}, {}
            for job in self.jobs:
                for batch in stats.BATCHES:
                    labels = ("original", "converted") if job["arm"] in stats.CIRCUIT_ARMS else ("original",)
                    for label in labels:
                        condition_values[(job["run_id"], label, batch)] = [session*100 if label == "original" else session*50]*15
                    if job["arm"] in stats.CIRCUIT_ARMS:
                        matched[(job["run_id"], batch)] = stats.matched_statistics([session*100]*15, [session*50]*15, 500)
            sessions.append({"condition_values": condition_values, "matched": matched})
        summary = stats.across_sessions(sessions, self.jobs)
        self.assertEqual(len(summary["condition_session_drift"]), 2688)
        self.assertTrue(all(row["count"] == 8 for row in summary["family_latency_descriptive"]))
        self.assertTrue(all(row["median"] == 200 for row in summary["family_latency_descriptive"]
                            if row["representation"] == "original"))
        self.assertTrue(all(row["median"] == 100 for row in summary["family_latency_descriptive"]
                            if row["representation"] == "converted"))

    def test_process_creation_identity_cannot_be_disguised(self):
        identities = [{"pid": n, "creation_token": str(n*100), "identity_source": "Win32_GetProcessTimes"} for n in (1, 2, 3)]
        audit.distinct_processes(identities)
        with self.assertRaises(RuntimeError):
            audit.distinct_processes([identities[0], identities[0], identities[2]])
        with self.assertRaises(RuntimeError):
            audit.distinct_processes([identities[0], {**identities[0], "session": 2}, identities[2]])
        # The same PID reused by a different kernel creation identity is a fresh process.
        audit.distinct_processes([identities[0], {**identities[0], "creation_token": "999"}, identities[2]])

    def test_conversion_authority_chain(self):
        conversion_folder, independent_folder = audit.HERE/"synthetic_conversion", audit.HERE/"synthetic_independent"
        release = {"evaluation_release": {"hash": 1}, "evaluation_commit": {"hash": 2},
                   "conversion_commit": {"hash": 3}}
        conversion = {"registration": {"hash": 4}}
        common = {"review_status": "approved_by_root", "phase": "conversion",
                  "test_access_authorized": True, "max_parallel_tasks": 1, "required_blas_threads": 1,
                  "evaluation_release": release["evaluation_release"], "evaluation_commit": release["evaluation_commit"]}
        producer = {**common, "schema": "qpath-v08-deployment-release-1",
                    "output": str(conversion_folder), "registration": conversion["registration"]}
        independent = {"phase": "conversion", "authorization": {"hash": 5}}
        summary = {"authorization": independent["authorization"], "producer_commit": release["conversion_commit"]}
        approval = {**common, "schema": "qpath-v08-independent-deployment-release-1",
                    "output": str(independent_folder), "producer_commit": release["conversion_commit"]}
        args = (release, conversion, conversion_folder.resolve(), producer, independent, independent_folder.resolve(), summary, approval)
        audit.validate_conversion_authorizations(*args)
        for which, changes in ((3, {"phase": "shots"}), (3, {"registration": {"hash": 99}}),
                               (7, {"producer_commit": {"hash": 99}}), (7, {"evaluation_commit": {"hash": 99}}),
                               (6, {"authorization": {"hash": 99}})):
            modified = list(args)
            modified[which] = {**modified[which], **changes}
            with self.assertRaises(RuntimeError):
                audit.validate_conversion_authorizations(*modified)


if __name__ == "__main__":
    unittest.main()
