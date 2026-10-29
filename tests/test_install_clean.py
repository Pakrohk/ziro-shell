"""Tests for clean install detection, backup, and wipe logic."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.install_cli import (
    _is_ziro_only_zshrc,
    detect_existing_zsh_configs,
    backup_and_clean_zsh_configs,
    cmd_install,
)


class TestInstallClean(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.zsh_dir = self.tmp_path / "user_home"
        self.zsh_dir.mkdir(parents=True, exist_ok=True)
        self.cfg_dir = self.tmp_path / "ziro_cfg"
        self.cfg_dir.mkdir(parents=True, exist_ok=True)

        self._old_home = os.environ.get("HOME")
        self._old_zdot = os.environ.get("ZDOTDIR")
        self._old_cfg = os.environ.get("ZIRO_CONFIG")
        self._old_wipe = os.environ.get("ZIRO_ALLOW_TEST_WIPE")

        os.environ["HOME"] = str(self.zsh_dir)
        os.environ["ZDOTDIR"] = str(self.zsh_dir)
        os.environ["ZIRO_CONFIG"] = str(self.cfg_dir)
        os.environ["ZIRO_ALLOW_TEST_WIPE"] = "1"
        os.environ["ZIRO_SKIP_VENDOR_CLONE"] = "1"

    def tearDown(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        else:
            os.environ.pop("HOME", None)

        if self._old_zdot is not None:
            os.environ["ZDOTDIR"] = self._old_zdot
        else:
            os.environ.pop("ZDOTDIR", None)

        if self._old_cfg is not None:
            os.environ["ZIRO_CONFIG"] = self._old_cfg
        else:
            os.environ.pop("ZIRO_CONFIG", None)

        if self._old_wipe is not None:
            os.environ["ZIRO_ALLOW_TEST_WIPE"] = self._old_wipe
        else:
            os.environ.pop("ZIRO_ALLOW_TEST_WIPE", None)

        self.tmp.cleanup()

    def test_detect_empty_home(self):
        detected = detect_existing_zsh_configs(self.zsh_dir)
        self.assertEqual(detected, [])

    def test_is_ziro_only_zshrc(self):
        zshrc = self.zsh_dir / ".zshrc"

        # Non-existing file
        self.assertFalse(_is_ziro_only_zshrc(zshrc))

        # Only comments / empty
        zshrc.write_text("# Welcome to zsh\n\n", encoding="utf-8")
        self.assertTrue(_is_ziro_only_zshrc(zshrc))

        # Ziro activation lines only
        zshrc.write_text(
            '# Ziro\n[[ ":$PATH:" != *":$HOME/.local/bin:"* ]] && export PATH="$HOME/.local/bin:$PATH"\nsource "/path/to/boot.zsh"\n',
            encoding="utf-8",
        )
        self.assertTrue(_is_ziro_only_zshrc(zshrc))

        # Custom user configuration (oh-my-zsh or plugins)
        zshrc.write_text(
            'export ZSH="$HOME/.oh-my-zsh"\nplugins=(git fzf)\nsource $ZSH/oh-my-zsh.sh\n',
            encoding="utf-8",
        )
        self.assertFalse(_is_ziro_only_zshrc(zshrc))

    def test_detect_existing_configs(self):
        (self.zsh_dir / ".zshrc").write_text("alias ll='ls -la'\n")
        (self.zsh_dir / ".zshenv").write_text("export FOO=BAR\n")
        (self.zsh_dir / ".oh-my-zsh").mkdir()
        (self.zsh_dir / ".oh-my-zsh" / "oh-my-zsh.sh").write_text("# omz\n")
        (self.zsh_dir / ".zcompdump-test").write_text("dump")

        detected = detect_existing_zsh_configs(self.zsh_dir)
        detected_names = [p.name for p in detected]

        self.assertIn(".zshrc", detected_names)
        self.assertIn(".zshenv", detected_names)
        self.assertIn(".oh-my-zsh", detected_names)
        self.assertIn(".zcompdump-test", detected_names)

    def test_backup_and_clean_zsh_configs(self):
        zshrc = self.zsh_dir / ".zshrc"
        zshrc.write_text("alias g=git\n")
        omz = self.zsh_dir / ".oh-my-zsh"
        omz.mkdir()
        (omz / "custom.zsh").write_text("echo custom")

        items = [zshrc, omz]
        backup_dir = backup_and_clean_zsh_configs(items, dry_run=False, zsh_dir=self.zsh_dir)

        self.assertIsNotNone(backup_dir)
        self.assertTrue(backup_dir.is_dir())
        self.assertTrue((backup_dir / ".zshrc").is_file())
        self.assertEqual((backup_dir / ".zshrc").read_text(), "alias g=git\n")
        self.assertTrue((backup_dir / ".oh-my-zsh" / "custom.zsh").is_file())

        # Original files must be wiped
        self.assertFalse(zshrc.exists())
        self.assertFalse(omz.exists())

    def test_cmd_install_clean_flag(self):
        zshrc = self.zsh_dir / ".zshrc"
        zshrc.write_text("alias old_alias=true\n")
        omz = self.zsh_dir / ".oh-my-zsh"
        omz.mkdir()

        # Run with --clean
        rc = cmd_install(["--default", "--clean", "--no-activate"])
        self.assertEqual(rc, 0)

        # Original files wiped
        self.assertFalse(omz.exists())
        # Backup exists
        backups = list(self.zsh_dir.glob(".zsh-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / ".zshrc").is_file())
        self.assertTrue((backups[0] / ".oh-my-zsh").is_dir())

    def test_cmd_install_interactive_clean_yes(self):
        zshrc = self.zsh_dir / ".zshrc"
        zshrc.write_text("alias old_stuff=true\n")

        with patch("core.install_cli._prompt_user", side_effect=["y", "1"]):
            rc = cmd_install(["--default", "--no-activate"])
            self.assertEqual(rc, 0)

        # Backed up and wiped
        backups = list(self.zsh_dir.glob(".zsh-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / ".zshrc").is_file())

    def test_cmd_install_interactive_clean_no(self):
        zshrc = self.zsh_dir / ".zshrc"
        zshrc.write_text("alias old_stuff=true\n")

        with patch("core.install_cli._prompt_user", side_effect=["n", "1"]):
            rc = cmd_install(["--default", "--no-activate"])
            self.assertEqual(rc, 0)

        # Kept in place, no backup directory
        backups = list(self.zsh_dir.glob(".zsh-backup-*"))
        self.assertEqual(len(backups), 0)
        self.assertTrue(zshrc.is_file())
        self.assertIn("old_stuff", zshrc.read_text())


if __name__ == "__main__":
    unittest.main()
