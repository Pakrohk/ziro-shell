"""Tests for lib/helpers.zsh shell functions."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPERS_FILE = REPO_ROOT / "lib" / "helpers.zsh"


class TestHelpers(unittest.TestCase):
    """Test behavior and safety of lib/helpers.zsh."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.assertTrue(HELPERS_FILE.is_file(), f"Missing {HELPERS_FILE}")

    def _run_zsh(self, script: str) -> subprocess.CompletedProcess[str]:
        cmd = ["zsh", "-f", "-c", f"source {HELPERS_FILE}; {script}"]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_syntax_clean(self) -> None:
        """helpers.zsh parses with zero zsh syntax errors."""
        res = subprocess.run(["zsh", "-n", str(HELPERS_FILE)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_mkcd_and_take(self) -> None:
        """mkcd and take create target directory and change into it."""
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "sub", "dir", "testdir")
            script = f'mkcd "{target}" && pwd'
            res = self._run_zsh(script)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stdout.strip(), target)
            self.assertTrue(os.path.isdir(target))

            target2 = os.path.join(td, "sub", "take_dir")
            script2 = f'take "{target2}" && pwd'
            res2 = self._run_zsh(script2)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            self.assertEqual(res2.stdout.strip(), target2)
            self.assertTrue(os.path.isdir(target2))

    def test_mkcd_no_args_fails(self) -> None:
        """mkcd with no arguments prints usage and returns 1."""
        res = self._run_zsh("mkcd")
        self.assertEqual(res.returncode, 1)
        self.assertIn("usage: mkcd", res.stderr)

    def test_dot_dot_navigation(self) -> None:
        """.. and ... navigate up directories."""
        with tempfile.TemporaryDirectory() as td:
            d1 = os.path.join(td, "level1", "level2", "level3")
            os.makedirs(d1)
            script = f'cd "{d1}" && .. && pwd && ... && pwd'
            res = self._run_zsh(script)
            self.assertEqual(res.returncode, 0, res.stderr)
            lines = res.stdout.strip().splitlines()
            self.assertEqual(lines[0], os.path.join(td, "level1", "level2"))
            self.assertEqual(lines[1], td)

    def test_extract_tar_gz(self) -> None:
        """extract handles tar.gz archives."""
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src")
            os.makedirs(src)
            dummy = os.path.join(src, "hello.txt")
            with open(dummy, "w") as f:
                f.write("ziro-extract-test")

            archive = os.path.join(td, "test.tar.gz")
            subprocess.run(["tar", "-czf", archive, "-C", src, "hello.txt"], check=True)

            out_dir = os.path.join(td, "dest")
            os.makedirs(out_dir)
            script = f'cd "{out_dir}" && extract "{archive}"'
            res = self._run_zsh(script)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "hello.txt")))

    def test_extract_zip(self) -> None:
        """extract handles zip archives if zip tool is installed."""
        if not shutil_which("zip") or not shutil_which("unzip"):
            self.skipTest("zip or unzip not available")
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src")
            os.makedirs(src)
            dummy = os.path.join(src, "data.txt")
            with open(dummy, "w") as f:
                f.write("zip-test")

            archive = os.path.join(td, "test.zip")
            subprocess.run(["zip", "-q", archive, "-j", dummy], check=True)

            out_dir = os.path.join(td, "dest")
            os.makedirs(out_dir)
            script = f'cd "{out_dir}" && extract "{archive}"'
            res = self._run_zsh(script)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "data.txt")))

    def test_extract_missing_file(self) -> None:
        """extract returns 1 for non-existent archive."""
        res = self._run_zsh('extract "/non/existent/archive.tar.gz"')
        self.assertEqual(res.returncode, 1)
        self.assertIn("not a valid file", res.stderr)

    def test_clipboard_fallback_error_without_tools(self) -> None:
        """clipcopy and clippaste gracefully fail with message when no backend is in PATH."""
        script = 'PATH="/nonexistent" clipcopy "hello" 2>&1'
        res = self._run_zsh(script)
        self.assertEqual(res.returncode, 1)
        self.assertIn("no supported clipboard tool found", res.stdout + res.stderr)

    def test_fzf_helpers_missing_fzf(self) -> None:
        """ff, fy, fb, fl fail gracefully when fzf is not in PATH."""
        for cmd in ("ff", "fy", "fb", "fl"):
            script = f'PATH="/nonexistent" {cmd} 2>&1'
            res = self._run_zsh(script)
            self.assertEqual(res.returncode, 1)
            self.assertIn("fzf not found in PATH", res.stdout + res.stderr)

    def test_fzf_helpers_cancel_returns_cleanly(self) -> None:
        """ff, fy, fb, fl return 0 when fzf is cancelled (exit code 130 or 1)."""
        with tempfile.TemporaryDirectory() as td:
            mock_fzf = os.path.join(td, "fzf")
            with open(mock_fzf, "w") as f:
                f.write("#!/bin/sh\nexit 130\n")
            os.chmod(mock_fzf, 0o755)

            mock_yazi = os.path.join(td, "yazi")
            with open(mock_yazi, "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(mock_yazi, 0o755)

            for cmd in ("ff", "fy", "fb", "fl"):
                script = f'PATH="{td}:$PATH" {cmd}'
                res = self._run_zsh(script)
                self.assertEqual(res.returncode, 0, f"{cmd} failed on cancel: {res.stderr}")




def shutil_which(cmd: str) -> bool:
    import shutil
    return shutil.which(cmd) is not None
