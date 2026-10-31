"""Selected live guides are checked without reinterpreting archived package READMEs."""

import unittest
import test_check_readme_links as fixtures
from check_readme_links import check


class SelectedLinksTests(unittest.TestCase):
    setUp = fixtures.ReadmeLinksTests.setUp
    file = fixtures.ReadmeLinksTests.file

    def test_selected_non_readme_link_fails(self):
        self.file("README.md", "# Main")
        self.file("docs/GUIDE.md", "[broken](missing.md)")
        self.file("archive/README.md", "[historical package path](original.py)")
        failures, count, *_ = check(self.root, ["README.md", "docs/GUIDE.md"])
        self.assertEqual(count, 2)
        self.assertEqual(len(failures), 1)
        self.assertIn("docs/GUIDE.md", failures[0])

    def test_empty_or_untracked_selection_cannot_pass(self):
        self.file("README.md", "# Main")
        for selection in ([], ["docs/missing.md"], ["readme.md"], ["README.md", "absent.md"]):
            with self.subTest(selection=selection):
                failures, *_ = check(self.root, selection)
                self.assertTrue(failures)
