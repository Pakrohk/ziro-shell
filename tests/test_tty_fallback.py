"""Tests for TTY detection, Rich UI integration, and graceful fallbacks.

Layer: 3 (CLI UI fallback tests)
Spec: 008 R6, R7, R8, R9
"""

from __future__ import annotations

import ast
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core import tty
from core import rich_helpers
from core import install_cli

import pytest
pytestmark = pytest.mark.unit


class TestTtyFallback(unittest.TestCase):
    def test_is_tty_non_tty_stream(self) -> None:
        """Non-TTY streams (like StringIO) must return False."""
        buf = io.StringIO()
        self.assertFalse(tty.is_tty(buf))

    def test_is_tty_ci_and_no_color_environment(self) -> None:
        """CI=1 or NO_COLOR must cause is_tty() to return False even on TTY."""
        mock_tty = MagicMock()
        mock_tty.isatty.return_value = True

        with patch.dict(os.environ, {"CI": "1"}):
            self.assertFalse(tty.is_tty(mock_tty))

        with patch.dict(os.environ, {"CI": "true"}):
            self.assertFalse(tty.is_tty(mock_tty))

        with patch.dict(os.environ, {"NO_COLOR": "1", "CI": ""}):
            self.assertFalse(tty.is_tty(mock_tty))

        with patch.dict(os.environ, {"CI": "", "NO_COLOR": ""}):
            self.assertTrue(tty.is_tty(mock_tty))

    def test_ensure_tty_output_with_non_tty_no_crash(self) -> None:
        """ensure_tty_output must not crash when stdout is not a TTY and /dev/tty is absent or mock."""
        orig_stdout = sys.stdout
        buf = io.StringIO()
        try:
            sys.stdout = buf
            # Even if /dev/tty cannot be accessed, ensure_tty_output must safely return without error
            with patch("os.path.exists", return_value=False):
                res = tty.ensure_tty_output()
                self.assertFalse(res)
        finally:
            sys.stdout = orig_stdout

    def test_ensure_tty_output_with_tty_no_redirect(self) -> None:
        """ensure_tty_output must not redirect if stdout is already a TTY."""
        orig_stdout = sys.stdout
        mock_stdout = MagicMock()
        mock_stdout.isatty.return_value = True
        try:
            sys.stdout = mock_stdout
            with patch.dict(os.environ, {"CI": "", "NO_COLOR": ""}):
                res = tty.ensure_tty_output()
                self.assertTrue(res)
                self.assertIs(sys.stdout, mock_stdout)
        finally:
            sys.stdout = orig_stdout

    def test_rich_console_fallback_in_ci(self) -> None:
        """In CI or non-TTY mode, get_console returns None and render helpers return False."""
        with patch.dict(os.environ, {"CI": "true"}):
            self.assertIsNone(rich_helpers.get_console())
            self.assertFalse(rich_helpers.render_tree("test", [("item", True, "ok")]))
            self.assertFalse(rich_helpers.render_table("test", ["A"], [["B"]]))
            self.assertFalse(rich_helpers.render_columns(["theme1", "theme2"]))

    def test_venv_bootstrap_idempotent_and_non_fatal(self) -> None:
        """venv bootstrap is idempotent and non-fatal on failure."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
                # 1. Non-fatal when subprocess fails
                with patch("subprocess.run", side_effect=OSError("disk error")):
                    err_buf = io.StringIO()
                    with patch("sys.stderr", err_buf):
                        res = install_cli._ensure_venv()
                    self.assertIsNone(res)
                    self.assertIn("warning:", err_buf.getvalue())

                # 2. Idempotent when venv python binary exists
                fake_py = tmp_path / "ziro" / "venv" / "bin" / "python3"
                fake_py.parent.mkdir(parents=True, exist_ok=True)
                fake_py.write_text("#!/bin/sh\n")
                res = install_cli._ensure_venv()
                self.assertEqual(res, tmp_path / "ziro" / "venv")

    def test_no_top_level_rich_imports_in_core(self) -> None:
        """Spec 008 R6: No core/*.py module may import rich at module top level."""
        core_dir = REPO_ROOT / "core"
        for py_file in core_dir.glob("*.py"):
            with self.subTest(file=py_file.name):
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in tree.body:
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertNotEqual(
                                alias.name.split(".")[0],
                                "rich",
                                f"{py_file.name} has top-level import '{alias.name}'",
                            )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            self.assertNotEqual(
                                node.module.split(".")[0],
                                "rich",
                                f"{py_file.name} has top-level from-import from '{node.module}'",
                            )


if __name__ == "__main__":
    unittest.main()
