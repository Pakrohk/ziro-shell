"""Tests for lib/aliases-core.zsh core aliases (ls color, cd navigation, eza fallback)."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_ALIASES_FILE = REPO_ROOT / "lib" / "aliases-core.zsh"


class TestAliasesCore(unittest.TestCase):
    """Test behavior and safety of lib/aliases-core.zsh."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(CORE_ALIASES_FILE.is_file(), f"Missing {CORE_ALIASES_FILE}")

    def test_syntax_clean(self) -> None:
        """aliases-core.zsh parses with zero syntax errors."""
        res = subprocess.run(["zsh", "-n", str(CORE_ALIASES_FILE)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_core_aliases_defined(self) -> None:
        """Core aliases ls, grep, .., ..., .... are always defined."""
        script = f'source "{CORE_ALIASES_FILE}"; alias ls; alias grep; alias ..; alias ...; alias ....'
        res = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue("ls=" in res.stdout and "-F" in res.stdout)
        self.assertIn("grep='grep --color=auto'", res.stdout)
        self.assertIn("..='cd ..'", res.stdout)
        self.assertIn("...='cd ../..'", res.stdout)
        self.assertIn("....='cd ../../..'", res.stdout)

    def test_ll_fallback_when_eza_absent(self) -> None:
        """When eza is absent, ll/la/lt fallback to ls with classification."""
        script = f'PATH="/nonexistent" source "{CORE_ALIASES_FILE}"; alias ll; alias la; alias lt'
        res = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue("ll='ls -la" in res.stdout)
        self.assertTrue("la='ls -a" in res.stdout)
        self.assertIn("lt='ls -R'", res.stdout)

    def test_ll_uses_eza_when_present(self) -> None:
        """When eza is present, ll/la/lt use eza."""
        with tempfile.TemporaryDirectory() as td:
            eza_path = os.path.join(td, "eza")
            with open(eza_path, "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(eza_path, 0o755)

            script = f'PATH="{td}:$PATH" source "{CORE_ALIASES_FILE}"; alias ll; alias la; alias lt'
            res = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("eza", res.stdout)

    def test_chpwd_zoxide_hook_registered(self) -> None:
        """_ziro_chpwd_zoxide hook is attached to chpwd."""
        script = f'source "{CORE_ALIASES_FILE}"; typeset -p chpwd_functions'
        res = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("_ziro_chpwd_zoxide", res.stdout)

    def test_chpwd_syncs_with_zoxide_on_cd(self) -> None:
        """When cd is executed, _ziro_chpwd_zoxide calls zoxide add or un-stubs proxy."""
        with tempfile.TemporaryDirectory() as td:
            log_file = Path(td) / "zoxide.log"
            mock_bin = Path(td) / "bin"
            mock_bin.mkdir()
            mock_zoxide = mock_bin / "zoxide"
            mock_zoxide.write_text(f"#!/bin/sh\necho \"$@\" >> '{log_file}'\n")
            mock_zoxide.chmod(0o755)

            target_dir = Path(td) / "sub_dir"
            target_dir.mkdir()

            script = f'''
            PATH="{mock_bin}:$PATH"
            source "{CORE_ALIASES_FILE}"
            cd "{target_dir}"
            '''
            res = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(log_file.exists())
            self.assertIn(f"add -- {target_dir}", log_file.read_text())
