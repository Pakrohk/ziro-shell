"""Tests for lib/aliases.zsh auto-detect modern CLI aliases."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALIASES_FILE = REPO_ROOT / "lib" / "aliases.zsh"


class TestAliases(unittest.TestCase):
    """Test behavior and safety of lib/aliases.zsh."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(ALIASES_FILE.is_file(), f"Missing {ALIASES_FILE}")

    def test_syntax_clean(self) -> None:
        """aliases.zsh parses with zero syntax errors."""
        res = subprocess.run(["zsh", "-n", str(ALIASES_FILE)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_no_aliases_when_binaries_absent(self) -> None:
        """When modern tools are absent from PATH, no aliases are created."""
        script = f'PATH="/nonexistent" source "{ALIASES_FILE}"; alias'
        res = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        output = res.stdout
        self.assertNotIn("ls=", output)
        self.assertNotIn("cat=", output)
        self.assertNotIn("grep=", output)
        self.assertNotIn("find=", output)
        self.assertNotIn("diff=", output)

    def test_alias_bound_when_fake_binary_present(self) -> None:
        """When bat and rg are present in PATH, aliases cat and grep are defined."""
        with tempfile.TemporaryDirectory() as td:
            # Create fake executable binaries
            for bin_name in ("bat", "rg"):
                bin_path = os.path.join(td, bin_name)
                with open(bin_path, "w") as f:
                    f.write("#!/bin/sh\nexit 0\n")
                os.chmod(bin_path, 0o755)

            script = f'PATH="{td}:$PATH" source "{ALIASES_FILE}"; alias cat; alias grep'
            res = subprocess.run(["zsh", "-f", "-c", script], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("bat", res.stdout)
            self.assertIn("rg", res.stdout)
