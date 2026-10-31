"""Exercise identity failures against actual tracked files and historical Git bytes."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_content_scope import check


class ContentScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "core.autocrlf", "false")
        self.put("Paper.txt", b"released bytes\r\n")
        self.original = self.identity()
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "source")
        self.commit = self.git("rev-parse", "HEAD").decode().strip()
        self.put("Paper.txt", b"current clarification\n")
        self.record({"file": self.identity(), "previous_source_commit": self.commit,
                     "changes": [{"before": self.original, "after": self.identity()}]})

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def put(self, name, data):
        (self.root / name).write_bytes(data)
        self.git("add", "--", name)

    def identity(self):
        data = (self.root / "Paper.txt").read_bytes()
        return {"path": "Paper.txt", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def record(self, value):
        self.put("record.json", json.dumps(value).encode())

    def test_current_and_historical_bytes_are_distinguished(self):
        self.assertEqual(check(self.root, ("record.json",)), 3)

    def test_changed_bytes_fail(self):
        (self.root / "Paper.txt").write_bytes(b"unexpected edit")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            check(self.root, ("record.json",))

    def test_wrong_before_image_fails(self):
        self.record({"previous_source_commit": self.commit, "before": self.identity()})
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            check(self.root, ("record.json",))

    def test_untracked_wrong_case_and_escape_fail(self):
        for name in ("paper.txt", "untracked.txt", "../outside.txt", "C:/outside.txt"):
            with self.subTest(name=name):
                value = self.identity(); value["path"] = name
                self.record({"file": value})
                with self.assertRaises(ValueError):
                    check(self.root, ("record.json",))

    def test_empty_record_and_unbound_history_fail(self):
        for value in ({}, {"before": self.original}):
            self.record(value)
            with self.assertRaises(ValueError):
                check(self.root, ("record.json",))


if __name__ == "__main__":
    unittest.main()
