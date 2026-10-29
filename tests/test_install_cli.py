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
        self._old_cfg = os.environ.get("ZIRO_CONFIG")
        self._old_cache = os.environ.get("ZIRO_CACHE")
        self._old_data = os.environ.get("ZIRO_DATA")
        self.cfg = Path(self.tmp.name) / "config"
        self.cfg.mkdir(parents=True, exist_ok=True)
        os.environ["ZIRO_CONFIG"] = str(self.cfg)
        os.environ["ZIRO_CACHE"] = str(Path(self.tmp.name) / "cache")
        os.environ["ZIRO_DATA"] = str(Path(self.tmp.name) / "data")
        os.environ["ZIRO_SKIP_VENDOR_CLONE"] = "1"

    def tearDown(self):
        for k, v in [
            ("ZIRO_CONFIG", self._old_cfg),
            ("ZIRO_CACHE", self._old_cache),
            ("ZIRO_DATA", self._old_data),
        ]:
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
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
        self.assertTrue((self.cfg / "defaults.toml").is_file())
        self.assertTrue((self.cfg / "tools.toml").is_file())

    def test_no_overwrite(self):
        cfg = self.cfg
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / "defaults.toml").write_text("# custom\n")
        install_cli.main(["--default", "--no-rebuild"])
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

    def test_install_man_page(self):
        repo_root = Path(__file__).resolve().parent.parent
        installed = install_cli._install_man_page(repo_root)
        self.assertIsNotNone(installed)
        self.assertTrue(installed.is_file())
        self.assertIn("ziro", installed.read_text())

    def test_custom_install_wizard(self):
        from unittest.mock import patch
        import tomllib

        # Answers:
        # 1. Starship preset: 1 (tokyo-night)
        # 2. Nerd font: y (yes)
        # 3. Ghost text: n (disable)
        # 4. Syntax highlighting: y (enable)
        # 5. Completions: y (enable)
        # 6. Zoxide: n (disable)
        # 7. Aliases: y (enable)
        # 8. Helpers: y (enable)
        wizard_answers = ["1", "y", "n", "y", "y", "n", "y", "y"]

        with patch("core.install_cli._prompt_user", side_effect=wizard_answers):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = install_cli.main(["--custom", "--no-clean", "--no-activate"])
            self.assertEqual(rc, 0)

        cfg = self.cfg
        # prompt.conf must be starship
        pconf = cfg / "prompt.conf"
        self.assertTrue(pconf.is_file())
        self.assertEqual(pconf.read_text().strip(), "starship")

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

    def test_rebuild_prompt_yes_rebuilds_all(self):
        from unittest.mock import patch

        cfg = self.cfg
        (cfg / "defaults.toml").write_text("old_content=true\n")
        (cfg / "tools.toml").write_text("old_tools=true\n")

        # When Ziro is already installed and user confirms rebuild ('y')
        with patch("core.install_cli._prompt_user", return_value="y"):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = install_cli.main(["--default", "--no-clean", "--no-activate"])
            self.assertEqual(rc, 0)
            self.assertIn("Rebuilding all Ziro configurations", buf.getvalue())

        defaults_content = (cfg / "defaults.toml").read_text()
        self.assertIn("[version]", defaults_content)
        self.assertNotIn("old_content=true", defaults_content)

    def test_rebuild_prompt_no_preserves_existing(self):
        from unittest.mock import patch

        cfg = self.cfg
        (cfg / "defaults.toml").write_text("old_content=true\n")

        # When user declines rebuild ('n')
        with patch("core.install_cli._prompt_user", return_value="n"):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = install_cli.main(["--default", "--no-clean", "--no-activate"])
            self.assertEqual(rc, 0)
            self.assertNotIn("Rebuilding all Ziro configurations", buf.getvalue())

        defaults_content = (cfg / "defaults.toml").read_text()
        self.assertEqual(defaults_content, "old_content=true\n")

    def test_rebuild_flag_bypasses_prompt(self):
        cfg = self.cfg
        (cfg / "defaults.toml").write_text("old_content=true\n")

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = install_cli.main(["--default", "--rebuild", "--no-clean", "--no-activate"])
        self.assertEqual(rc, 0)
        self.assertIn("Rebuilding all Ziro configurations", buf.getvalue())
        self.assertNotIn("old_content=true", (cfg / "defaults.toml").read_text())


if __name__ == "__main__":
    unittest.main()
