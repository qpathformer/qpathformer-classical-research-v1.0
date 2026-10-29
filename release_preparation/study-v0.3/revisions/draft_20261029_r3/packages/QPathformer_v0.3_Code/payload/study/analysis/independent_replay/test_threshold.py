"""Synthetic recovery01 boundary, sensitivity and canonical-metric regressions."""
import unittest
import numpy as np
from threshold_reference import BAND, threshold_diagnostics, class_metrics
from statistics_reference import metrics


def check(p, q, y=None):
    p, q = np.array(p, dtype=float), np.array(q, dtype=float)
    y = np.arange(len(p)) % 2 if y is None else np.array(y)
    return threshold_diagnostics(y, p, q, np.arange(len(p)), np.ones(len(p), dtype=int),
                                 {'hash': np.zeros(len(p), dtype=int), 'kmeans': np.zeros(len(p), dtype=int)})


class ThresholdChecks(unittest.TestCase):
    def test_inside_inclusive_band_preserves_canonical_and_lists_every_disagreement(self):
        p, q = [.5 - BAND, .5 + BAND, .9], [.5 + BAND, .5 - BAND, .9]
        d = check(p, q, [0, 1, 1])
        self.assertEqual(d['counts']['classification_disagreements'], 2)
        self.assertFalse(d['counts']['exact_classifier_agreement'])
        self.assertEqual(d['counts']['outside_band_disagreements'], 0)
        self.assertEqual(len(d['disagreements']), 2)
        self.assertEqual(d['canonical_metrics'], metrics(np.array([0, 1, 1]), np.array(p)))

    def test_outside_either_band_rejects_despite_probability_tolerance(self):
        for p, q in [(.5 - 2 * BAND, .5), (.5, .5 - 2 * BAND)]:
            self.assertLess(abs(p - q), 2e-12)
            with self.assertRaisesRegex(ValueError, 'BOTH-probabilities32eps'): check([p], [q])

    def test_canonical_only_mask_and_all_four_cases(self):
        p = [.5, .5, .1, .9]; q = [.5, .5, .1, .9]; y = [0, 1, 0, 1]
        d = check(p, q, y); s = d['canonical_band_sensitivity']
        self.assertEqual(set(s), {'all_class0', 'all_class1', 'all_incorrect_label_assisted', 'all_correct_label_assisted'})
        for name, pred in [('all_class0', [0, 0, 0, 1]), ('all_class1', [1, 1, 0, 1]),
                           ('all_incorrect_label_assisted', [1, 0, 0, 1]), ('all_correct_label_assisted', [0, 1, 0, 1])]:
            self.assertEqual(s[name], class_metrics(y, pred)); self.assertNotIn('bce', s[name])
        e = check([.5 + 2 * BAND], [.5 + BAND], [0])
        self.assertEqual(e['counts']['canonical_near_band_count'], 0)
        self.assertEqual(e['counts']['reference_near_band_count'], 1)
        self.assertEqual(e['counts']['union_near_band_count'], 1)
        self.assertTrue(all(v == class_metrics([0], [1]) for v in e['canonical_band_sensitivity'].values()))

    def test_no_ambiguity_cases_equal_canonical_metrics(self):
        d = check([.1, .9], [.1, .9], [0, 1])
        self.assertTrue(d['counts']['exact_classifier_agreement'])
        self.assertEqual(d['counts']['union_near_band_count'], 0)
        self.assertTrue(all(v == class_metrics([0, 1], [0, 1]) for v in d['canonical_band_sensitivity'].values()))

    def test_probability_tolerance_still_strict(self):
        with self.assertRaisesRegex(ValueError, 'probability tolerance'): check([.1], [.1 + 3e-12])


if __name__ == '__main__': unittest.main(verbosity=2)
