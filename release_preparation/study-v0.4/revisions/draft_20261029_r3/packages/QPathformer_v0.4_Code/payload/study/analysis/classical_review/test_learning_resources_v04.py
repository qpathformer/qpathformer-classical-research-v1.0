from pathlib import Path
import sys,unittest,tempfile,shutil
from unittest import mock
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from learning_resources_v04 import milestones,reaching_summary
import learning_resources_v04 as subject

class MilestoneTests(unittest.TestCase):
    def test_first_crossing_and_later_sequence_are_distinct(self):
        r=milestones([.97,.969,.97,.98,.97,.95],np.arange(6)+1.)
        self.assertEqual((r['first_update'],r['confirmed_sequence_start_update'],r['confirmed_update']),(75,225,375))
        self.assertEqual(r['confirmed_elapsed_seconds'],5.)
    def test_exact_threshold_and_earliest_third_check(self):
        r=milestones([.97,.97,.97,.99,.99])
        self.assertEqual((r['first_round'],r['confirmed_round']),(1,3))
    def test_last_two_qualifying_checks_never_confirm(self):
        r=milestones([.8,.9,.97,.98]);self.assertTrue(r['first_reached']);self.assertFalse(r['confirmed_reached'])
        self.assertIsNone(r['confirmed_update']);self.assertEqual(r['horizon_updates'],300)
    def test_three_qualifying_checks_at_horizon_confirm(self):
        r=milestones([.9]*197+[.97]*3);self.assertEqual(r['confirmed_update'],15000)
        self.assertEqual(r['confirmed_sequence_start_update'],14850)
    def test_nonreachers_remain_counted(self):
        rows=[{'milestones':milestones([.97]*200)},{'milestones':milestones([.1]*200)},{'milestones':milestones([.1]*199+[.97])}]
        a=reaching_summary(rows,'confirmed');self.assertEqual((a['reached'],a['not_reached']),(1,2))
        self.assertEqual(a['conditional_update_summary']['median'],225.)
        b=reaching_summary(rows[1:],'confirmed');self.assertIsNone(b['conditional_update_summary'])
    def test_invalid_history_and_clock_rejected(self):
        for values,elapsed in [([],None),([float('nan')],None),([1.1],None),([.8,.9],[2.,1.]),([.8],[-1.])]:
            with self.assertRaises(RuntimeError):milestones(values,elapsed)

class RelocationTests(unittest.TestCase):
    def test_relocated_engineering_payload_is_read_from_current_root(self):
        original=subject.ROOT
        relative=Path('quantum/engineering_pilot_v01/engineering_circle/seed_9701/q2_global/selected_checkpoint.npz')
        with tempfile.TemporaryDirectory(prefix='relocated_engineering_',dir=Path(__file__).resolve().parent) as temp:
            current=Path(temp);destination=current/relative;destination.parent.mkdir(parents=True)
            shutil.copyfile(original/relative,destination)
            old_hash=subject.sha(original/relative)
            with mock.patch.object(subject,'ROOT',current),mock.patch.object(subject,'Q',current/'quantum'):
                mapped=subject.mapped_historical_path(str(original/relative),original)
                self.assertEqual(mapped,destination.resolve());self.assertNotEqual(mapped,(original/relative).resolve())
                self.assertEqual(subject.sha(mapped),old_hash)
                with np.load(mapped,allow_pickle=False) as z:self.assertEqual(z['parameters'].shape,(8,))
                source=subject.mapped_historical_path(str(original/'governance/ANALYSIS_PROTOCOL.json'),original)
                self.assertEqual(source,(current/'governance/ANALYSIS_PROTOCOL.json').resolve())
            self.assertEqual(subject.sha(original/relative),old_hash)
    def test_endpoint_identity_and_outside_root_rejected(self):
        original=subject.ROOT;row={'population':'development_circle','seed':701,'method':'q2_global',
             'path':str(original/'quantum/stage_A/development_circle/seed_701/q2_global')}
        with tempfile.TemporaryDirectory(prefix='relocated_identity_',dir=Path(__file__).resolve().parent) as temp:
            current=Path(temp)
            with mock.patch.object(subject,'ROOT',current),mock.patch.object(subject,'Q',current/'quantum'):
                self.assertEqual(subject.endpoint_folder('A',row,original),(current/'quantum/stage_A/development_circle/seed_701/q2_global').resolve())
                with self.assertRaises(RuntimeError):subject.mapped_historical_path(str(original.parent/'unrelated.py'),original)
                with self.assertRaises(RuntimeError):subject.mapped_historical_path('../outside.py',original)
                wrong={**row,'method':'q2_hash'}
                with self.assertRaises(RuntimeError):subject.endpoint_folder('A',wrong,original)

if __name__=='__main__':unittest.main()
