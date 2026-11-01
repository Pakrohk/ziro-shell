"""Tests for core.suggest_cli."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core import suggest_cli

import pytest
pytestmark = pytest.mark.unit


class TestSuggestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("ZIRO_CONFIG")
        os.environ["ZIRO_CONFIG"] = self.tmp.name

    def tearDown(self):
        if self._old is not None:
            os.environ["ZIRO_CONFIG"] = self._old
        else:
            os.environ.pop("ZIRO_CONFIG", None)
        self.tmp.cleanup()

    def test_list(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = suggest_cli.main(["list"])
        self.assertEqual(rc, 0)
        self.assertIn("ziro-ghost", buf.getvalue())

    def test_set_valid(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = suggest_cli.main(["set", "zsh-autosuggestions"])
        self.assertEqual(rc, 0)

    def test_set_invalid(self):
        rc = suggest_cli.main(["set", "foo"])
        self.assertEqual(rc, 2)

    def test_disable(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = suggest_cli.main(["disable"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
