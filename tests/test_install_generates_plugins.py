"""Tests for install-time generation of plugins.gen.zsh and prompt adapter integration.

Spec: 001 FR-006a, 004 R1 §7, 006 Principle XIII
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

from core import install_cli
from core.generator import default_output_path


class TestInstallGeneratesPlugins(unittest.TestCase):
    """Test suite covering BUG-A, BUG-B, BUG-C blocker fixes."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.config_dir = self.test_dir / "config"
        self.data_dir = self.test_dir / "data"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.old_cfg = os.environ.get("ZIRO_CONFIG")
        self.old_data = os.environ.get("ZIRO_DATA")
        self.old_home = os.environ.get("ZIRO_HOME")
        os.environ["ZIRO_CONFIG"] = str(self.config_dir)
        os.environ["ZIRO_DATA"] = str(self.data_dir)
        os.environ["ZIRO_HOME"] = str(REPO_ROOT)

    def tearDown(self) -> None:
        if self.old_cfg is not None:
            os.environ["ZIRO_CONFIG"] = self.old_cfg
        else:
            os.environ.pop("ZIRO_CONFIG", None)

        if self.old_data is not None:
            os.environ["ZIRO_DATA"] = self.old_data
        else:
            os.environ.pop("ZIRO_DATA", None)

        if self.old_home is not None:
            os.environ["ZIRO_HOME"] = self.old_home
        else:
            os.environ.pop("ZIRO_HOME", None)

        self.temp_dir.cleanup()

    def test_install_default_creates_plugins_gen(self) -> None:
        """Case 1: install --default creates plugins.gen.zsh (FR-006a)."""
        rc = install_cli.main(["--default"])
        self.assertEqual(rc, 0)

        gen_file = default_output_path(self.config_dir)
        self.assertTrue(gen_file.is_file(), f"Expected {gen_file} to exist after install")
        self.assertGreater(gen_file.stat().st_size, 0)

    def test_plugins_gen_contains_starship(self) -> None:
        """Case 2: plugins.gen.zsh contains starship line (Spec 004 R1 §7)."""
        rc = install_cli.main(["--default"])
        self.assertEqual(rc, 0)

        gen_file = default_output_path(self.config_dir)
        content = gen_file.read_text(encoding="utf-8")
        self.assertIn("starship", content)
        self.assertIn("znap eval starship", content)

    def test_plugins_gen_contains_zcolors(self) -> None:
        """Case 3: plugins.gen.zsh contains zcolors line (Spec 004 R1 §11)."""
        rc = install_cli.main(["--default"])
        self.assertEqual(rc, 0)

        gen_file = default_output_path(self.config_dir)
        content = gen_file.read_text(encoding="utf-8")
        self.assertIn("zcolors", content)
        self.assertIn("znap eval marlonrichert/zcolors", content)

    def test_install_regenerates_idempotent(self) -> None:
        """Case 4: plugins.gen.zsh is regenerated on second install (idempotent)."""
        rc1 = install_cli.main(["--default"])
        self.assertEqual(rc1, 0)
        gen_file = default_output_path(self.config_dir)
        content1 = gen_file.read_text(encoding="utf-8")

        rc2 = install_cli.main(["--default"])
        self.assertEqual(rc2, 0)
        content2 = gen_file.read_text(encoding="utf-8")

        # Strip generated timestamp comments for exact comparison
        lines1 = [line for line in content1.splitlines() if not line.startswith("# Generated:")]
        lines2 = [line for line in content2.splitlines() if not line.startswith("# Generated:")]
        self.assertEqual(lines1, lines2)

    # Moved to tests/_deprecated/ in cleanup phase — prompt.conf is no longer read by integration.zsh.
    # In post-integration architecture (ADL-014), integration.zsh is a 4-line shim to boot.zsh,
    # and prompt configuration flows declaratively through load.toml -> ziro-boot.zsh.


if __name__ == "__main__":
    unittest.main()
