"""Read-only release-gate and pure-array integration tests, synthetic only."""
from pathlib import Path
import importlib.util
import copy
import json
import sys
import unittest
import numpy as np
import replay_evaluation_v08 as replay
import statistics_v08

Q=Path(__file__).resolve().parents[2]/"quantum"
sys.path.insert(0,str(Q))
import routers
official_path=Path(__file__).resolve().parents[1]/"official_evaluation/statistics_core.py"
spec=importlib.util.spec_from_file_location("official_statistics_synthetic_only",official_path)
official=importlib.util.module_from_spec(spec);spec.loader.exec_module(official)


class ReplayIntegrationTests(unittest.TestCase):
    def test_actual_matrix_confirmation_metadata_requires_active_stage(self):
        matrix=json.loads((Q.parent/"governance/RUN_MATRIX.json").read_text(encoding="utf-8-sig"))
        actual=replay.confirmation_populations(matrix)
        self.assertEqual(len(actual),32)
        alternate=copy.deepcopy(matrix)
        for pop in alternate["populations"]:
            if pop["stage"]=="B":pop["stage"]="confirmation"
        with self.assertRaises(RuntimeError):replay.confirmation_populations(alternate)

    def test_gate_rejects_missing_or_partial_release_before_read(self):
        good={"schema":"qpath-v08-test-release-1","review_status":"approved_by_root","stage":"B",
              "test_access_authorized":True,"all_confirmation_endpoints_independently_audited":True,"latent_diagnostics_authorized":True,
              "independent_replay_freeze":{"path":"synthetic not opened"}}
        replay.validate_release_flags(good)
        for key in good:
            altered=good.copy();del altered[key]
            with self.subTest(key=key),self.assertRaises(RuntimeError):replay.validate_release_flags(altered)

    def test_raw_route_reference_matches_fixed_policy_on_new_inputs(self):
        rng=np.random.Generator(np.random.PCG64(827711))
        train=rng.uniform(-1,1,(100,2));heldout=rng.uniform(-1,1,(40,2))
        policy=routers.fit_route_policy(train,123456,"independent-fixture-salt")
        policy["margin_bins"]=routers.fit_margin_bins(train,policy)
        expected=replay.routes_and_margin(heldout,policy)
        np.testing.assert_array_equal(expected["hash_route"],routers.route(heldout,policy,"hash"))
        np.testing.assert_array_equal(expected["kmeans_route"],routers.route(heldout,policy,"kmeans"))
        np.testing.assert_array_equal(expected["margin_bin"],routers.margin_bins(heldout,policy,policy["margin_bins"]))

    def test_synthetic_full_primary_and_descriptive_summary_reconstruction(self):
        populations=[{"population_id":f"{f}_{i}","family":f} for f in statistics_v08.FAMILIES for i in range(8)]
        rows=[];independent=[]
        names=("bce","native_bce","macro_f1","accuracy","brier","ece10","positive_precision","positive_recall","grouped_tie_average_precision")
        for pop in populations:
            for seed in statistics_v08.SEEDS:
                for k,arm in enumerate(statistics_v08.ARMS):
                    bce=.1+.01*k+.001*(seed-1601)+.002*int(pop["population_id"][-1])*k
                    rows.append({"family":pop["family"],"population":pop["population_id"],"seed":seed,"arm":arm,
                                 "test":{n:bce if n in ("bce","native_bce") else .7 for n in names},
                                 "validation_milestones":{str(t):{"reached":seed==1601,"first_observed_updates":150 if seed==1601 else None} for t in (.9,.95,.97)}})
                    independent.append({"population_id":pop["population_id"],"training_seed_id":seed,"arm":arm,"common_bce":bce})
        expected=statistics_v08.primary_contrasts(independent,populations)
        replay.compare_primary(expected,official.primary(rows))
        description=official.descriptive(rows)
        replay.check_descriptive(rows,description)
        duplicate=copy.deepcopy(description);duplicate[-1]=duplicate[0]
        with self.assertRaises(RuntimeError):replay.check_descriptive(rows,duplicate)
        incomplete=copy.deepcopy(description);del incomplete[0]["metrics"]["brier"]
        with self.assertRaises(RuntimeError):replay.check_descriptive(rows,incomplete)
        incomplete=copy.deepcopy(description);del incomplete[0]["validation_milestones"]["0.97"]
        with self.assertRaises(RuntimeError):replay.check_descriptive(rows,incomplete)
        for row in rows:
            slices={}
            for kind in ("hash","kmeans","geometric_margin"):
                count=5 if kind!="geometric_margin" else 3+int(row["population"][-1])%2
                slices[kind]=[{"bin":i,"n":0 if i==count-1 else 10,
                               "metrics":None if i==count-1 else
                               {"bce":row["test"]["bce"]+.01*i,"macro_f1":.5,"positive_prevalence":.2}}
                              for i in range(count)]
            row["diagnostics"]={"test":slices}
        replay.check_diagnostic_summary(rows,official.diagnostic_summary(rows))
        bad=official.primary(rows);bad["contrasts"][0]["degrees_of_freedom"]=15
        with self.assertRaises(ValueError):replay.compare_primary(expected,bad)


if __name__=="__main__":unittest.main(verbosity=2)
