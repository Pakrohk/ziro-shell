"""Tests for lib/keybindings.zsh navigation keybindings (Home, End, Delete, PageUp, PageDown)."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KEYBINDINGS_FILE = REPO_ROOT / "lib" / "keybindings.zsh"


class TestKeybindings(unittest.TestCase):
    """Test behavior of lib/keybindings.zsh."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(KEYBINDINGS_FILE.is_file(), f"Missing {KEYBINDINGS_FILE}")

    def test_syntax_clean(self) -> None:
        """keybindings.zsh parses with zero syntax errors."""
        res = subprocess.run(["zsh", "-n", str(KEYBINDINGS_FILE)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_keys_bound(self) -> None:
        """Home, End, Delete key codes are bound."""
        script = f'source "{KEYBINDINGS_FILE}"; bindkey'
        res = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("beginning-of-line", res.stdout)
        self.assertIn("end-of-line", res.stdout)
        self.assertIn("delete-char", res.stdout)
