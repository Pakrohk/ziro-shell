"""Tests for core.tag_cli."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core import tag_cli

import pytest
pytestmark = pytest.mark.unit


class TestTagCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("ZIRO_CONFIG")
        os.environ["ZIRO_CONFIG"] = self.tmp.name
        # seed builtin.toml
        cfg = Path(self.tmp.name)
        (cfg / "tags" / "plugins").mkdir(parents=True)
        (cfg / "tags" / "builtin.toml").write_text(
            '[[tags]]\nname = "@eager"\nstrategy = "eager"\npriority = 10\n'
        )

    def tearDown(self):
        if self._old is not None:
            os.environ["ZIRO_CONFIG"] = self._old
        else:
            os.environ.pop("ZIRO_CONFIG", None)
        self.tmp.cleanup()

    def test_list(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = tag_cli.main(["list"])
        self.assertEqual(rc, 0)
        self.assertIn("@eager", buf.getvalue())

    def test_add_show_remove(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = tag_cli.main(["add", "test-plugin", "@eager"])
        self.assertEqual(rc, 0)

        buf = io.StringIO()
        with redirect_stdout(buf):
            tag_cli.main(["show", "test-plugin"])
        self.assertIn("@eager", buf.getvalue())

        buf = io.StringIO()
        with redirect_stdout(buf):
            tag_cli.main(["remove", "test-plugin", "@eager"])
        self.assertEqual(rc, 0)

    def test_add_unknown_tag(self):
        rc = tag_cli.main(["add", "p", "@nope"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
