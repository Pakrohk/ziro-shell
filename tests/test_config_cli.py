"""Tests for core.config_cli."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core import config_cli

import pytest
pytestmark = pytest.mark.unit


class TestConfigCli(unittest.TestCase):
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

    def test_show_empty(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = config_cli.main(["show"])
        self.assertEqual(rc, 0)
        self.assertIn("config dir", buf.getvalue())

    def test_edit_missing(self):
        rc = config_cli.main(["edit", "nope.toml"])
        self.assertEqual(rc, 1)

    def test_unknown(self):
        rc = config_cli.main(["bogus"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
