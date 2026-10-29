"""Tests for core.install_cli."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".ziro"))
from core import install_cli


class TestInstallCli(unittest.TestCase):
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

    def test_dry_run(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = install_cli.main(["--default", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("dry-run", buf.getvalue())

    def test_default_writes_files(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = install_cli.main(["--default"])
        self.assertEqual(rc, 0)
        self.assertTrue((Path(self.tmp.name) / "defaults.toml").is_file())
        self.assertTrue((Path(self.tmp.name) / "tools.toml").is_file())

    def test_no_overwrite(self):
        cfg = Path(self.tmp.name)
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / "defaults.toml").write_text("# custom\n")
        install_cli.main(["--default"])
        self.assertEqual((cfg / "defaults.toml").read_text(), "# custom\n")

    def test_verify_starship_missing(self):
        from unittest.mock import patch
        with patch("shutil.which", return_value=None):
            ok, msg = install_cli._verify_starship()
            self.assertFalse(ok)
            self.assertIn("not found on PATH", msg)

            err_buf = io.StringIO()
            with redirect_stdout(io.StringIO()), patch("sys.stderr", err_buf):
                rc = install_cli.main(["--default"])
            self.assertEqual(rc, 0)
            self.assertIn("Starship not available", err_buf.getvalue())

    def test_custom_install_wizard(self):
        from unittest.mock import patch
        import tomllib

        # Answers:
        # prompt: 2 (pure)
        # ghost: n (disable)
        # fsh: y (enable)
        # comp: y (enable)
        # zoxide: n (disable)
        # aliases: y (enable)
        # helpers: y (enable)
        wizard_answers = ["2", "n", "y", "y", "n", "y", "y"]

        with patch("core.install_cli._prompt_user", side_effect=wizard_answers):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = install_cli.main(["--custom", "--no-clean", "--no-activate"])
            self.assertEqual(rc, 0)

        cfg = Path(self.tmp.name)
        # prompt.conf must be pure
        pconf = cfg / "prompt.conf"
        self.assertTrue(pconf.is_file())
        self.assertEqual(pconf.read_text().strip(), "pure")

        # load.toml must have ziro-ghost and zoxide disabled
        load_toml = cfg / "load.toml"
        self.assertTrue(load_toml.is_file())
        with load_toml.open("rb") as f:
            data = tomllib.load(f)

        tools = {t["name"]: t for t in data.get("tool", [])}
        self.assertIn("ziro-ghost", tools)
        self.assertFalse(tools["ziro-ghost"].get("enabled", True))
        self.assertIn("zoxide", tools)
        self.assertFalse(tools["zoxide"].get("enabled", True))
        self.assertIn("fast-syntax-highlighting", tools)
        self.assertTrue(tools["fast-syntax-highlighting"].get("enabled", True))
        self.assertIn("ziro-aliases-core", tools)
        self.assertTrue(tools["ziro-aliases-core"].get("enabled", True))


if __name__ == "__main__":
    unittest.main()
