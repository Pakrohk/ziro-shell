"""Integration tests for CLI dispatcher help routing (ziro.zsh).

Layer: 0 (CLI dispatcher tests)
Spec: 008 R1, R2, R10
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

import pytest
pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDispatcherHelp(unittest.TestCase):
    def _run_ziro(self, *args: str) -> subprocess.CompletedProcess[str]:
        cmd = f'source "{REPO_ROOT}/ziro.zsh"; ziro ' + " ".join(f'"{a}"' for a in args)
        env = dict(os.environ)
        env["ZIRO_HOME"] = str(REPO_ROOT)
        return subprocess.run(
            ["zsh", "-c", cmd],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )

    def test_ziro_help_exits_0(self) -> None:
        r = self._run_ziro("help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Usage:", r.stdout)
        self.assertIn("Commands:", r.stdout)

    def test_ziro_double_dash_help(self) -> None:
        r = self._run_ziro("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Usage:", r.stdout)
        self.assertIn("Commands:", r.stdout)

    def test_ziro_single_dash_h(self) -> None:
        r_h = self._run_ziro("-h")
        r_help = self._run_ziro("--help")
        self.assertEqual(r_h.returncode, 0)
        self.assertEqual(r_h.stdout, r_help.stdout)

    def test_ziro_help_command_install(self) -> None:
        r = self._run_ziro("help", "install")
        self.assertEqual(r.returncode, 0)
        self.assertIn("ziro install", r.stdout)
        self.assertIn("Usage:", r.stdout)
        self.assertIn("--default", r.stdout)

    def test_ziro_plugin_double_dash_help(self) -> None:
        r = self._run_ziro("plugin", "--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("ziro plugin", r.stdout)
        self.assertIn("Subcommands:", r.stdout)

    def test_ziro_plugin_add_double_dash_help(self) -> None:
        r = self._run_ziro("plugin", "add", "--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("ziro plugin add", r.stdout)
        self.assertIn("Usage:", r.stdout)

    def test_ziro_version(self) -> None:
        r = self._run_ziro("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn("ziro-shell", r.stdout)

    def test_ziro_nonexistent_command(self) -> None:
        r = self._run_ziro("bogusxyz123")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown command or topic 'bogusxyz123'", r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
