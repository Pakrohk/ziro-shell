"""Tests for core.plugin_pipeline."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".ziro"))

from core.plugin_pipeline import _clone_repo, add_plugin, remove_plugin


class TestAddPlugin(unittest.TestCase):
    def test_dry_run_no_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            zhome = Path(tmp) / "z"
            zcfg = Path(tmp) / "c"
            zhome.mkdir()
            zcfg.mkdir()
            r = add_plugin(
                "fake/repo",
                name="fake",
                ziro_home=zhome,
                config_dir=zcfg,
                dry_run=True,
            )
            self.assertEqual(r.plugin, "fake")
            self.assertTrue(r.dry_run)
            self.assertFalse((zhome / "plugins" / "fake").is_dir())

    def test_add_with_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            zhome = Path(tmp) / "z"
            zcfg = Path(tmp) / "c"
            zhome.mkdir()
            zcfg.mkdir()
            r = add_plugin(
                "fake/repo",
                name="t",
                tags=["@eager"],
                ziro_home=zhome,
                config_dir=zcfg,
                dry_run=True,
            )
            self.assertEqual(r.plugin, "t")

    def test_add_local_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "local_git_plugin"
            src_dir.mkdir()
            (src_dir / "plugin.plugin.zsh").write_text("# test plugin\n_myfunc() { echo hi; }\n")
            subprocess.run(["git", "init"], cwd=str(src_dir), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(src_dir), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=str(src_dir), check=True, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=str(src_dir), check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(src_dir), check=True, capture_output=True)

            dest = Path(tmp) / "dest"
            result = _clone_repo(str(src_dir), dest, dry_run=False)
            self.assertTrue(result)
            self.assertTrue(dest.is_dir())
            self.assertTrue((dest / "plugin.plugin.zsh").is_file())

    def test_add_local_directory_non_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "non_git_plugin"
            src_dir.mkdir()
            (src_dir / "plugin.plugin.zsh").write_text("# non-git plugin\n_myfunc() { echo hi; }\n")

            dest = Path(tmp) / "dest"
            result = _clone_repo(str(src_dir), dest, dry_run=False)
            self.assertTrue(result)
            self.assertTrue(dest.is_dir())
            self.assertTrue((dest / "plugin.plugin.zsh").is_file())

    def test_add_slug_normalization_remote(self):
        from core import plugin_cli
        self.assertFalse(Path("fake/repo").exists())
        with tempfile.TemporaryDirectory() as tmp:
            orig_home = os.environ.get("ZIRO_HOME")
            orig_cfg = os.environ.get("ZIRO_CONFIG")
            try:
                os.environ["ZIRO_HOME"] = str(Path(tmp) / "home")
                os.environ["ZIRO_CONFIG"] = str(Path(tmp) / "cfg")
                Path(os.environ["ZIRO_HOME"]).mkdir()
                Path(os.environ["ZIRO_CONFIG"]).mkdir()
                rc = plugin_cli.main(["add", "fake/repo", "fake", "--dry-run"])
                self.assertEqual(rc, 0)
            finally:
                if orig_home is not None:
                    os.environ["ZIRO_HOME"] = orig_home
                else:
                    os.environ.pop("ZIRO_HOME", None)
                if orig_cfg is not None:
                    os.environ["ZIRO_CONFIG"] = orig_cfg
                else:
                    os.environ.pop("ZIRO_CONFIG", None)


class TestRemovePlugin(unittest.TestCase):
    def test_remove_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            zhome = Path(tmp) / "z"
            zcfg = Path(tmp) / "c"
            zhome.mkdir()
            zcfg.mkdir()
            ok = remove_plugin("nope", ziro_home=zhome, config_dir=zcfg)
            self.assertFalse(ok)

    def test_remove_existing_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            zhome = Path(tmp) / "z"
            zcfg = Path(tmp) / "c"
            (zhome / "plugins" / "p1").mkdir(parents=True)
            zcfg.mkdir()
            ok = remove_plugin("p1", ziro_home=zhome, config_dir=zcfg, dry_run=True)
            self.assertTrue(ok)
            self.assertTrue((zhome / "plugins" / "p1").is_dir())  # not removed


class TestFix3Enhancements(unittest.TestCase):
    def test_safe_regeneration_preserves_factory_tools(self):
        """add_plugin preserves existing factory tools and appends new plugin."""
        from core.plugin_cli import _existing_configs

        with tempfile.TemporaryDirectory() as tmp:
            zhome = Path(tmp) / "zhome"
            zcfg = Path(tmp) / "zcfg"
            zhome.mkdir()
            zcfg.mkdir()

            (zcfg / "defaults.toml").write_text("[prompt]\ndefault = 'starship'\n")

            existing = _existing_configs()
            self.assertGreaterEqual(len(existing), 13)

            plugin_src = Path(tmp) / "my_plugin_src"
            plugin_src.mkdir()
            (plugin_src / "my_plugin.plugin.zsh").write_text("echo loaded\n")

            r = add_plugin(
                str(plugin_src),
                name="my_plugin",
                ziro_home=zhome,
                config_dir=zcfg,
                all_configs=existing,
                dry_run=False,
                is_local=True,
            )
            self.assertEqual(r.plugin, "my_plugin")
            gen_file = zcfg / "derived" / "plugins.gen.zsh"
            self.assertTrue(gen_file.is_file())
            content = gen_file.read_text()
            self.assertIn("starship", content)
            self.assertIn("zsh-completions", content)
            self.assertIn("my_plugin", content)
            entry_lines = [l for l in content.splitlines() if l.strip() and not l.startswith("#")]
            self.assertGreaterEqual(len(entry_lines), 14)

    def test_local_flag_explicit_path(self):
        """--local with explicit valid path adds local plugin."""
        from core import plugin_cli

        with tempfile.TemporaryDirectory() as tmp:
            plugin_file = Path(tmp) / "my_local.plugin.zsh"
            plugin_file.write_text("echo 'local loaded'\n")

            zhome = Path(tmp) / "home"
            zcfg = Path(tmp) / "cfg"
            zhome.mkdir()
            zcfg.mkdir()

            orig_home = os.environ.get("ZIRO_HOME")
            orig_cfg = os.environ.get("ZIRO_CONFIG")
            try:
                os.environ["ZIRO_HOME"] = str(zhome)
                os.environ["ZIRO_CONFIG"] = str(zcfg)
                rc = plugin_cli.main(["add", "--local", str(plugin_file), "my_local"])
                self.assertEqual(rc, 0)
                installed_plugin = zhome / "plugins" / "my_local" / "my_local.plugin.zsh"
                self.assertTrue(installed_plugin.is_file())
            finally:
                if orig_home is not None:
                    os.environ["ZIRO_HOME"] = orig_home
                else:
                    os.environ.pop("ZIRO_HOME", None)
                if orig_cfg is not None:
                    os.environ["ZIRO_CONFIG"] = orig_cfg
                else:
                    os.environ.pop("ZIRO_CONFIG", None)

    def test_local_flag_missing_path_errors(self):
        """--local with nonexistent or missing path returns error code 1."""
        from core import plugin_cli

        rc1 = plugin_cli.main(["add", "--local", "/nonexistent/path/xyz", "test"])
        self.assertEqual(rc1, 1)

        rc2 = plugin_cli.main(["add", "--local"])
        self.assertEqual(rc2, 1)

    def test_subpath_syntax(self):
        """--subpath isolates repository subpath."""
        from core import plugin_cli

        with tempfile.TemporaryDirectory() as tmp:
            zhome = Path(tmp) / "home"
            zcfg = Path(tmp) / "cfg"
            zhome.mkdir()
            zcfg.mkdir()

            orig_home = os.environ.get("ZIRO_HOME")
            orig_cfg = os.environ.get("ZIRO_CONFIG")
            try:
                os.environ["ZIRO_HOME"] = str(zhome)
                os.environ["ZIRO_CONFIG"] = str(zcfg)
                rc = plugin_cli.main(["add", "ohmyzsh/ohmyzsh", "--subpath=plugins/git", "--name=git_sub", "--dry-run"])
                self.assertEqual(rc, 0)
            finally:
                if orig_home is not None:
                    os.environ["ZIRO_HOME"] = orig_home
                else:
                    os.environ.pop("ZIRO_HOME", None)
                if orig_cfg is not None:
                    os.environ["ZIRO_CONFIG"] = orig_cfg
                else:
                    os.environ.pop("ZIRO_CONFIG", None)

    def test_binary_tool_rejection(self):
        """Binary tools from registry are rejected with helpful message."""
        from core import plugin_cli

        rc1 = plugin_cli.main(["add", "starship", "starship"])
        self.assertEqual(rc1, 1)

        rc2 = plugin_cli.main(["add", "fzf", "fzf"])
        self.assertEqual(rc2, 1)


if __name__ == "__main__":
    unittest.main()
