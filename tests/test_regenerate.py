"""Tests for core.regenerate."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.regenerate import regenerate, TRIGGERS

import pytest
pytestmark = pytest.mark.unit


class TestRegenerate(unittest.TestCase):
    def test_unknown_trigger_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                regenerate(Path(tmp), [], trigger="bad-trigger")

    def test_triggers_contains_all(self):
        for t in ("plugin-add", "tag-add", "suggest-set"):
            self.assertIn(t, TRIGGERS)

    def test_empty_regenerate_writes_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = regenerate(Path(tmp), [], trigger="manual")
            self.assertTrue(r.output.is_file())
            self.assertIn("AUTO-GENERATED", r.output.read_text())


if __name__ == "__main__":
    unittest.main()
