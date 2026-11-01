"""Tests for Spec 016 escape hatch hardening (RC2 / R9).

Validates that ZIRO_ALLOW_TEST_HOME=1 is only honored when running under
an active pytest runner (PYTEST_CURRENT_TEST). Outside pytest, it raises
a clear ValueError.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from core.build import _validate_ziro_home

import pytest
pytestmark = pytest.mark.unit


class TestEscapeHatchHardening(unittest.TestCase):
    """Test suite for ZIRO_ALLOW_TEST_HOME hardening (spec 016 R9)."""

    def test_no_pytest_raises_error(self) -> None:
        """AC7: ZIRO_ALLOW_TEST_HOME=1 outside pytest raises ValueError."""
        env_backup = os.environ.get("PYTEST_CURRENT_TEST")
        try:
            os.environ.pop("PYTEST_CURRENT_TEST", None)
            os.environ["ZIRO_ALLOW_TEST_HOME"] = "1"
            with self.assertRaises(ValueError) as ctx:
                _validate_ziro_home(Path("/tmp/fake_dir"))
            err_msg = str(ctx.exception)
            self.assertIn("ZIRO_ALLOW_TEST_HOME=1 is a test-only escape hatch", err_msg)
            self.assertIn("pytest is not running", err_msg)
        finally:
            if env_backup is not None:
                os.environ["PYTEST_CURRENT_TEST"] = env_backup
            else:
                os.environ.pop("PYTEST_CURRENT_TEST", None)
            os.environ.pop("ZIRO_ALLOW_TEST_HOME", None)

    def test_with_pytest_passes(self) -> None:
        """AC8: ZIRO_ALLOW_TEST_HOME=1 with PYTEST_CURRENT_TEST set bypasses validation."""
        env_backup = os.environ.get("PYTEST_CURRENT_TEST")
        try:
            os.environ["PYTEST_CURRENT_TEST"] = "test_run_123"
            os.environ["ZIRO_ALLOW_TEST_HOME"] = "1"
            # Should not raise even on a nonexistent /tmp path
            _validate_ziro_home(Path("/tmp/nonexistent_test_path"))
        finally:
            if env_backup is not None:
                os.environ["PYTEST_CURRENT_TEST"] = env_backup
            else:
                os.environ.pop("PYTEST_CURRENT_TEST", None)
            os.environ.pop("ZIRO_ALLOW_TEST_HOME", None)

    def test_error_message_clear(self) -> None:
        """R9: Error message instructs user to unset environment variable."""
        env_backup = os.environ.get("PYTEST_CURRENT_TEST")
        try:
            os.environ.pop("PYTEST_CURRENT_TEST", None)
            os.environ["ZIRO_ALLOW_TEST_HOME"] = "1"
            with self.assertRaises(ValueError) as ctx:
                _validate_ziro_home(Path("/tmp/some_dir"))
            self.assertIn("Unset this environment variable", str(ctx.exception))
        finally:
            if env_backup is not None:
                os.environ["PYTEST_CURRENT_TEST"] = env_backup
            else:
                os.environ.pop("PYTEST_CURRENT_TEST", None)
            os.environ.pop("ZIRO_ALLOW_TEST_HOME", None)


if __name__ == "__main__":
    unittest.main()
