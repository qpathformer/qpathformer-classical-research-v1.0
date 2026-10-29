import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import qstudy as s
import evaluate_confirmation as e


class EvaluationChecks(unittest.TestCase):
    def test_independent_metrics(self):
        y=np.asarray([0,0,1,1]);p=np.asarray([.1,.9,.8,.7])
        result=e.independently_measure(y,p)
        self.assertEqual(result["confusion"],[[1,1],[0,2]])
        self.assertAlmostEqual(result["macro_f1"],(.6666666666666666+.8)/2)
        self.assertAlmostEqual(result["bce"],-(math.log(.9)+math.log(.1)+math.log(.8)+math.log(.7))/4)

    def test_independent_predictions_all_registered_models(self):
        rng=np.random.default_rng(9901)
        pop={"x":rng.uniform(-.9,.9,(16,2)),"depth":np.tile(np.arange(1,5),4)}
        for method in s.METHODS:
            model=s.Model(method,9901)
            np.testing.assert_allclose(model.predict(pop["x"],pop["depth"]),e.independently_predict(model,pop),atol=1e-12)

    def test_unapproved_release_never_reads_test(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(s,"ROOT",Path(directory)):
            for name in ("EVALUATION_RELEASE.json","CONFIRMATION_ENDPOINT_LOCK.json","STAGE_B_FREEZE.json"):
                s.write_json(Path(directory)/name,{})
            with patch.object(e,"endpoints",return_value=({}, {}, [])),patch.object(np,"load") as loader:
                with self.assertRaises(PermissionError):
                    e.evaluate()
                loader.assert_not_called()
            self.assertFalse((Path(directory)/"confirmation_evaluation").exists())

    def test_approved_release_cannot_bypass_failed_endpoint_lock(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(s,"ROOT",Path(directory)):
            root=Path(directory)
            (root/"data").mkdir()
            for name in ("STAGE_B_FREEZE.json","STAGE_A_SELECTION.json","data/DATA_SEAL.json"):
                s.write_json(root/name,{})
            lock={"status":"failed","stage_b_freeze_sha256":s.digest(root/"STAGE_B_FREEZE.json"),
                  "stage_a_selection_sha256":s.digest(root/"STAGE_A_SELECTION.json"),
                  "data_seal_sha256":s.digest(root/"data/DATA_SEAL.json"),"evaluator_sha256":s.digest(e.__file__),
                  "root_analysis_protocol_sha256":e.ANALYSIS_PROTOCOL_SHA256,"selected_candidate":"min_depth2",
                  "test_file_read":False,"endpoints":[]}
            s.write_json(root/"CONFIRMATION_ENDPOINT_LOCK.json",lock)
            s.write_json(root/"EVALUATION_RELEASE.json",{
                "review_status":"approved_by_root","release_id":"synthetic-test-release",
                "endpoint_lock_sha256":s.digest(root/"CONFIRMATION_ENDPOINT_LOCK.json"),
                "stage_b_freeze_sha256":s.digest(root/"STAGE_B_FREEZE.json"),"evaluator_sha256":s.digest(e.__file__)})
            with patch.object(e,"endpoints",return_value=({}, {"selected_candidate":"min_depth2"}, [])),patch.object(np,"load") as loader:
                with self.assertRaisesRegex(ValueError,"Endpoint lock status"):
                    e.evaluate()
                loader.assert_not_called()
            self.assertFalse((root/"confirmation_evaluation").exists())


if __name__=="__main__":
    unittest.main()
