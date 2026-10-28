"""Tests for core.theme_cli."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core import theme_cli


class TestThemeCli(unittest.TestCase):
    def setUp(self):
        self.tmp_cfg = tempfile.TemporaryDirectory()
        self.tmp_home = tempfile.TemporaryDirectory()
        self._old_cfg = os.environ.get("ZIRO_CONFIG")
        self._old_home = os.environ.get("ZIRO_HOME")
        os.environ["ZIRO_CONFIG"] = self.tmp_cfg.name
        os.environ["ZIRO_HOME"] = self.tmp_home.name

    def tearDown(self):
        if self._old_cfg is not None:
            os.environ["ZIRO_CONFIG"] = self._old_cfg
        else:
            os.environ.pop("ZIRO_CONFIG", None)
        if self._old_home is not None:
            os.environ["ZIRO_HOME"] = self._old_home
        else:
            os.environ.pop("ZIRO_HOME", None)
        self.tmp_cfg.cleanup()
        self.tmp_home.cleanup()

    def test_current_no_error(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = theme_cli.main(["current"])
        self.assertEqual(rc, 0)
        self.assertIn("prompt:", buf.getvalue())

    def test_list_empty(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = theme_cli.main(["list"])
        self.assertEqual(rc, 0)

    def test_apply_prompt(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = theme_cli.main(["apply", "minimal"])
        self.assertEqual(rc, 0)
        self.assertIn("applied", buf.getvalue())

    def test_edit_non_tty(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = theme_cli.main(["edit"])
        self.assertEqual(rc, 0)
        self.assertIn("opening", buf.getvalue())

    def test_unknown_subcommand(self):
        rc = theme_cli.main(["bogus"])
        self.assertEqual(rc, 2)



if __name__ == "__main__":
    unittest.main()
