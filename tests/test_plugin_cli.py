"""Tests for core.plugin_cli."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".ziro"))
from core import plugin_cli


class TestPluginCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("ZIRO_HOME")
        os.environ["ZIRO_HOME"] = self.tmp.name

    def tearDown(self):
        if self._old is not None:
            os.environ["ZIRO_HOME"] = self._old
        else:
            os.environ.pop("ZIRO_HOME", None)
        self.tmp.cleanup()

    def test_list_empty(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = plugin_cli.main(["list"])
        self.assertEqual(rc, 0)

    def test_list_with_load_toml(self):
        """plugin list prints detailed stage, type, and description information."""
        cfg = Path(self.tmp.name) / "config"
        cfg.mkdir(parents=True, exist_ok=True)
        load_toml = cfg / "load.toml"
        load_toml.write_text("""
[[tool]]
name = "starship"
timing = "eager"
method = "eval-cache"
reason = "eager: prompt"

[[tool]]
name = "ziro-ghost"
timing = "deferred"
stage = 5
slot = "b"
method = "source"
reason = "deferred: autocomplete"

[[tool]]
name = "zoxide"
timing = "on-demand"
trigger = "command"
trigger_commands = ["z"]
method = "eval-cache"
reason = "on-demand: navigation"
""", encoding="utf-8")

        old_cfg = os.environ.get("ZIRO_CONFIG")
        os.environ["ZIRO_CONFIG"] = str(cfg)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = plugin_cli.main(["list"])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("starship", out)
            self.assertIn("ziro-ghost", out)
            self.assertIn("zoxide", out)
            self.assertIn("Stage 2/4", out)
            self.assertIn("Stage 5", out)
            self.assertIn("Stage 7", out)

            # Test names only flag
            buf_names = io.StringIO()
            with redirect_stdout(buf_names):
                rc = plugin_cli.main(["list", "--names"])
            self.assertEqual(rc, 0)
            names_out = buf_names.getvalue()
            self.assertIn("starship\n", names_out)
            self.assertNotIn("Stage 2/4", names_out)
        finally:
            if old_cfg is not None:
                os.environ["ZIRO_CONFIG"] = old_cfg
            else:
                os.environ.pop("ZIRO_CONFIG", None)

    def test_add_skeleton(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = plugin_cli.main(["add", "test-plugin", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("test-plugin", buf.getvalue())

    def test_show_missing(self):
        rc = plugin_cli.main(["show", "nope"])
        self.assertEqual(rc, 1)

    def test_unknown_sub(self):
        rc = plugin_cli.main(["bogus"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
