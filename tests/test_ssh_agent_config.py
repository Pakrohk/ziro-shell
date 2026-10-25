"""Tests for lib/ssh-config.zsh SSH agent configuration."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SSH_CONFIG_FILE = REPO_ROOT / "lib" / "ssh-config.zsh"


class TestSshAgentConfig(unittest.TestCase):
    """Test behavior and safety of lib/ssh-config.zsh."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(SSH_CONFIG_FILE.is_file(), f"Missing {SSH_CONFIG_FILE}")

    def test_syntax_clean(self) -> None:
        """ssh-config.zsh parses with zero syntax errors."""
        res = subprocess.run(["zsh", "-n", str(SSH_CONFIG_FILE)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_gcr_socket_unsetting(self) -> None:
        """When SSH_AUTH_SOCK is set to a gcr socket, ssh-config unsets it."""
        script = f'export SSH_AUTH_SOCK="/run/user/1000/gcr/ssh"; source "{SSH_CONFIG_FILE}"; echo "VAL=$SSH_AUTH_SOCK"'
        res = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("VAL=", res.stdout)
        self.assertNotIn("/gcr/", res.stdout)
