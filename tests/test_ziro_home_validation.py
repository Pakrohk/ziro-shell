"""Tests for Spec 015 ZIRO_HOME validation (N1).

Validates that core/build.py rejects ephemeral temporary directories,
nonexistent paths, and corrupt installations prior to baking paths into boot.zsh.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.build import _validate_ziro_home, build


class TestZiroHomeValidation(unittest.TestCase):
    """Test suite for ZIRO_HOME path validation prior to baking boot.zsh."""

    def test_validate_ziro_home_rejects_tmp(self) -> None:
        """Validation fails if home is directly inside /tmp."""
        with tempfile.TemporaryDirectory(dir="/tmp") as td:
            p = Path(td)
            (p / "core").mkdir()
            (p / "core" / "__main__.py").write_text("")
            (p / ".git").mkdir()
            with self.assertRaises(ValueError) as ctx:
                _validate_ziro_home(p)
            self.assertIn("must not be in a temporary directory", str(ctx.exception))

    def test_validate_ziro_home_rejects_var_tmp(self) -> None:
        """Validation fails if home is inside /var/tmp."""
        var_tmp = Path("/var/tmp")
        if var_tmp.is_dir() and os.access(var_tmp, os.W_OK):
            with tempfile.TemporaryDirectory(dir="/var/tmp") as td:
                p = Path(td)
                (p / "core").mkdir()
                (p / "core" / "__main__.py").write_text("")
                (p / ".git").mkdir()
                with self.assertRaises(ValueError) as ctx:
                    _validate_ziro_home(p)
                self.assertIn("must not be in a temporary directory", str(ctx.exception))

    def test_validate_ziro_home_rejects_nonexistent(self) -> None:
        """Validation fails if directory does not exist."""
        p = Path("/nonexistent/directory/for/ziro/test")
        with self.assertRaises(ValueError) as ctx:
            _validate_ziro_home(p)
        self.assertIn("does not exist or is not a directory", str(ctx.exception))

    def test_validate_ziro_home_rejects_relative(self) -> None:
        """Validation fails if path is relative."""
        p = Path("relative/path/to/ziro")
        with self.assertRaises(ValueError) as ctx:
            _validate_ziro_home(p)
        self.assertIn("must be absolute", str(ctx.exception))

    def test_validate_ziro_home_rejects_missing_core_main(self) -> None:
        """Validation fails if path is missing core/__main__.py."""
        # Create non-temp dir inside user home
        target = Path.home() / ".ziro_fake_missing_main_test"
        try:
            target.mkdir(parents=True, exist_ok=True)
            (target / ".git").mkdir(exist_ok=True)
            with self.assertRaises(ValueError) as ctx:
                _validate_ziro_home(target)
            self.assertIn("core/__main__.py", str(ctx.exception))
        finally:
            if target.is_dir():
                import shutil
                shutil.rmtree(target, ignore_errors=True)

    def test_validate_ziro_home_rejects_missing_markers(self) -> None:
        """Validation fails if path is missing .git, .ziro-root."""
        target = Path.home() / ".ziro_fake_missing_markers_test"
        try:
            target.mkdir(parents=True, exist_ok=True)
            (target / "core").mkdir(exist_ok=True)
            (target / "core" / "__main__.py").write_text("")
            with self.assertRaises(ValueError) as ctx:
                _validate_ziro_home(target)
            self.assertIn("missing both .git/ and .ziro-root marker", str(ctx.exception))
        finally:
            if target.is_dir():
                import shutil
                shutil.rmtree(target, ignore_errors=True)

    def test_validate_ziro_home_accepts_real_checkout(self) -> None:
        """Validation passes for the real ~/.ziro installation."""
        real_home = Path.home() / ".ziro"
        if real_home.is_dir() and (real_home / "core" / "__main__.py").is_file():
            # Should not raise
            _validate_ziro_home(real_home)

    def test_ziro_sync_fails_with_temp_ziro_home(self) -> None:
        """AC8: python3 -m core sync fails when ZIRO_HOME points to /tmp and leaves boot.zsh unchanged."""
        boot_shim = Path.home() / ".config" / "ziro" / "boot.zsh"
        before_content = boot_shim.read_text() if boot_shim.is_file() else None

        env = os.environ.copy()
        env["ZIRO_HOME"] = "/tmp/fake_ziro_sync_attempt"
        res = subprocess.run(
            ["python3", "-m", "core", "sync"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid ZIRO_HOME", res.stderr + res.stdout)

        after_content = boot_shim.read_text() if boot_shim.is_file() else None
        self.assertEqual(before_content, after_content)

    def test_boot_zsh_contains_real_home(self) -> None:
        """AC10: boot.zsh contains non-temp real ZIRO_HOME path."""
        boot_shim = Path.home() / ".config" / "ziro" / "boot.zsh"
        self.assertTrue(boot_shim.is_file())
        content = boot_shim.read_text()
        self.assertIn('export ZIRO_HOME="/home/', content)
        self.assertNotIn("/tmp", content)


if __name__ == "__main__":
    unittest.main()
